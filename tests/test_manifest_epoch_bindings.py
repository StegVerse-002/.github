"""Every manifest-declared entrypoint that needs an epoch declares where it comes from.

An entrypoint needs an epoch when its source applies the shared rule or
consumes frames, or when it runs another declared entrypoint that does. Since
the supplied-epoch rule, such an entrypoint invoked as declared with no epoch
bound is a standing refusal (MANIFEST_ENTRYPOINT_LACKS_EPOCH_BINDING). Each
binding's declared supplier is checked to pass the epoch.
"""
import copy
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVATION = "resident-runtime/activation-manifest.json"
INTERLOCK = "org-runtime/interlock-intr.json"
MANIFESTS = (ACTIVATION, INTERLOCK, "org-runtime/activation.json", "org-boundary/registry/services.json",
             "resident-runtime/self-characterization/stegverse-002.json")
NEEDS_EPOCH = re.compile(r"supplied_epoch\(|writer_epoch_refusal\(|SUPPLIED_EPOCH_ENV|consume_and_respond\(|ingest_frame\(")
PY_PATH = re.compile(r"^([A-Za-z0-9_./-]+\.py)(?:::[A-Za-z_]+)?$")
KINDS = {"environment", "argument", "frame_heartbeat", "dispatch_input"}


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def declared_paths(document):
    return {match.group(1) for text in strings(document) if (match := PY_PATH.match(text))
            and (ROOT / match.group(1)).is_file()}


def needs_epoch(path, declared):
    """The source applies the rule or consumes frames, or runs (as a subprocess) a declared one that does.

    Loading the kernel as a library is not running it: only frame-only kernel
    calls (WU-B13) are reached that way, and those take no epoch.
    """
    source = (ROOT / path).read_text(encoding="utf-8")
    if NEEDS_EPOCH.search(source):
        return True
    if "subprocess." not in source:
        return False
    return any('"' + Path(other).name + '"' in source and other != path and NEEDS_EPOCH.search(
        (ROOT / other).read_text(encoding="utf-8")) for other in declared)


def bindings(documents):
    """Entrypoint path -> its declared binding, from every manifest."""
    found = dict(documents[ACTIVATION].get("hb_epoch_bindings") or {})

    def walk(value):
        if isinstance(value, dict):
            binding = value.get("hb_epoch_binding")
            if isinstance(binding, dict):
                for text in strings({k: v for k, v in value.items() if k != "hb_epoch_binding"}):
                    match = PY_PATH.match(text)
                    if match:
                        found.setdefault(match.group(1), binding)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(documents[INTERLOCK])
    return found


def unbound_entrypoints(documents):
    """The six-field MANIFEST_ENTRYPOINT_LACKS_EPOCH_BINDING rows for these manifests."""
    declared = set().union(*(declared_paths(document) for document in documents.values()))
    bound = bindings(documents)
    rows = []
    for path in sorted(declared):
        if needs_epoch(path, declared) and path not in bound:
            rows.append({
                "failure_code": "MANIFEST_ENTRYPOINT_LACKS_EPOCH_BINDING",
                "failed_predicate": "EVERY_EPOCH_REQUIRING_ENTRYPOINT_DECLARES_ITS_EPOCH_BINDING",
                "required_evidence_or_repair": "declare hb_epoch_bindings[" + path + "] and its supplier",
                "retry_entrypoint": "tests/test_manifest_epoch_bindings.py",
                "owning_existing_goal": "INTERLOCK-INTR-RUNTIME-INDEPENDENT-PROTOCOL-001",
                "next_attempt": "after the manifest declares the binding",
                "entrypoint": path,
            })
    return rows


def source_of(reference):
    return (ROOT / reference.split("::", 1)[0]).read_text(encoding="utf-8")


class ManifestEpochBindings(unittest.TestCase):
    def setUp(self):
        self.documents = {name: load(name) for name in MANIFESTS}

    def test_every_epoch_requiring_entrypoint_is_bound(self):
        self.assertEqual(unbound_entrypoints(self.documents), [])

    def test_the_resident_cycle_is_one_of_them(self):
        declared = declared_paths(self.documents[ACTIVATION])
        self.assertTrue(needs_epoch("resident-runtime/resident_executor.py", declared))
        self.assertTrue(needs_epoch("resident-runtime/federation_cycle.py", declared))

    def test_a_manifest_without_the_binding_is_found(self):
        documents = copy.deepcopy(self.documents)
        documents[ACTIVATION].pop("hb_epoch_bindings")
        rows = unbound_entrypoints(documents)
        self.assertIn("resident-runtime/resident_executor.py", {row["entrypoint"] for row in rows})
        for row in rows:
            self.assertEqual(row["failure_code"], "MANIFEST_ENTRYPOINT_LACKS_EPOCH_BINDING")

    def test_each_declared_supplier_passes_the_epoch(self):
        for path, binding in bindings(self.documents).items():
            with self.subTest(entrypoint=path):
                self.assertIs(binding.get("requires_hb_epoch"), True)
                self.assertIn(binding.get("from"), KINDS)
                supplier = binding["supplied_by"]
                self.assertTrue((ROOT / supplier.split("::", 1)[0]).is_file(), supplier)
                kind = binding["from"]
                if kind == "environment":
                    self.assertEqual(binding["variable"], "STEGVERSE_HB_EPOCH")
                    if supplier.endswith(".service"):
                        unit = source_of(supplier)
                        # Required, not optional ("-"): the unit does not start without it.
                        self.assertIn("\n" + binding["supplied_via"] + "\n", unit)
                        self.assertNotIn("EnvironmentFile=-", unit)
                        self.assertIn("env=dict(os.environ)", source_of(binding["forwarded_by"]))
                    else:
                        self.assertIn("env=dict(os.environ)", source_of(supplier))
                elif kind == "argument":
                    self.assertIn(binding["argument"].rstrip("="), source_of(supplier))
                elif kind == "frame_heartbeat":
                    kernel = source_of(binding["rule"])
                    self.assertIn("def consuming_epoch(", kernel)
                    self.assertIn("hb_epoch=consuming_epoch(frame,hb_epoch)", source_of(supplier))
                elif kind == "dispatch_input":
                    workflow = source_of(supplier)
                    self.assertRegex(workflow, r"workflow_dispatch:\s*\n\s*inputs:[\s\S]*\n\s+" + binding["input"] + ":")
                    self.assertIn('--hb-epoch "$HB_EPOCH"', workflow)
                    self.assertIn("HB_EPOCH: ${{ github.event.inputs." + binding["input"] + " }}", workflow)


if __name__ == "__main__":
    unittest.main()
