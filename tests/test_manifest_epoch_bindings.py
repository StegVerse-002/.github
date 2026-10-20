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
KINDS = {"argument", "frame_heartbeat", "dispatch_input"}
WORKFLOWS = ROOT / ".github" / "workflows"


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


#: The only admissible owner of an entrypoint whose code is not in this tree: a
#: repository of this organization, declared beside the entrypoint as
#: ``<key>_dispatcher: {status: PENDING_IN_OTHER_REPO, repo: ...}``
#: (MANIFEST_DISPATCHER_IN_OTHER_REPO, OPEN until that repo's dispatcher lands).
OTHER_REPO_PREFIX = "StegVerse-002/"


def other_repo_dispatchers(value):
    """Entrypoint path -> its declared other-repository dispatcher, from ``<key>`` / ``<key>_dispatcher`` pairs."""
    found = {}
    if isinstance(value, dict):
        for key, item in value.items():
            dispatcher = value.get(key + "_dispatcher")
            if isinstance(item, str) and PY_PATH.match(item) and isinstance(dispatcher, dict):
                found[PY_PATH.match(item).group(1)] = dispatcher
            found.update(other_repo_dispatchers(item))
    elif isinstance(value, list):
        for item in value:
            found.update(other_repo_dispatchers(item))
    return found


def tree_files():
    for path in ROOT.rglob("*"):
        if (path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts
                and "tests" not in path.relative_to(ROOT).parts[:1]
                and path.suffix in {".py", ".yml", ".yaml", ".service", ".sh"}):
            yield path


def in_tree_callers(path, documents):
    """In-tree files that invoke ``path``, including through the service registry's endpoint adapters."""
    callers = [str(other.relative_to(ROOT)) for other in tree_files()
               if str(other.relative_to(ROOT)) != path and Path(path).name in other.read_text(errors="ignore")]
    adapters = {service.get("endpoint_adapter") for service in documents["org-boundary/registry/services.json"]["services"]}
    if path in adapters:
        # process_boundary.py runs ROOT/<endpoint_adapter> for its service.
        callers.append("org-boundary/runtime/process_boundary.py::endpoint_result")
    return callers


class ManifestDispatchersInTree(unittest.TestCase):
    def setUp(self):
        self.documents = {name: load(name) for name in MANIFESTS}

    def test_every_declared_entrypoint_has_an_in_tree_caller_or_a_declared_other_repo_dispatcher(self):
        declared = set()
        foreign = {}
        for document in self.documents.values():
            declared |= {match.group(1) for text in strings(document) if (match := PY_PATH.match(text))}
            foreign.update(other_repo_dispatchers(document))
        gaps = {path for path in declared
                if not (ROOT / path).is_file() or not in_tree_callers(path, self.documents)}
        for path in sorted(gaps):
            with self.subTest(entrypoint=path):
                # Only code that is not in this tree may be owned elsewhere, and only as declared.
                self.assertFalse((ROOT / path).is_file(), "MANIFEST_DISPATCHER_NOT_IN_TREE: " + path)
                dispatcher = foreign.get(path)
                self.assertIsInstance(dispatcher, dict, "MANIFEST_DISPATCHER_NOT_IN_TREE: " + path)
                self.assertEqual(dispatcher["status"], "PENDING_IN_OTHER_REPO")
                self.assertTrue(dispatcher["repo"].startswith(OTHER_REPO_PREFIX), dispatcher["repo"])
        self.assertEqual(gaps, {"tools/run_self_characterization_principal.py"})

    def test_ecosystem_control_is_bound_and_dispatched_in_tree_with_the_epoch(self):
        """EPOCH_FREE is not provable for it: status and send-* stamp a heartbeat, so it is bound."""
        declared = set().union(*(declared_paths(document) for document in self.documents.values()))
        path = "resident-runtime/ecosystem_control.py"
        self.assertTrue(needs_epoch(path, declared))
        self.assertNotIn("epoch_free_entrypoints", self.documents[ACTIVATION])
        binding = bindings(self.documents)[path]
        self.assertIs(binding["requires_hb_epoch"], True)
        workflow = source_of(binding["dispatcher"])
        self.assertIn("python3 " + path + " " + binding["invoked_as"], workflow)
        self.assertEqual(binding["invoked_as"], '--hb-epoch "$HB_EPOCH" status')


class OpenRecords(unittest.TestCase):
    """The open six-field records live in the manifest, not only in its status fields."""

    SIX = ("failure_code", "failed_predicate", "required_evidence_or_repair", "retry_entrypoint",
           "owning_existing_goal", "next_attempt")

    def test_the_open_records_are_six_field(self):
        records = {row["failure_code"]: row for row in load(ACTIVATION)["open_records"]}
        self.assertEqual(set(records), {"RUNTIME_DISPATCHER_PENDING_SUBSTRATE", "MANIFEST_DISPATCHER_IN_OTHER_REPO"})
        for code, row in records.items():
            with self.subTest(record=code):
                for field in self.SIX:
                    self.assertIsInstance(row.get(field), str, field)
                    self.assertTrue(row[field].strip(), field)
                self.assertEqual(row["status"], "OPEN")
        self.assertEqual(records["MANIFEST_DISPATCHER_IN_OTHER_REPO"]["next_attempt"],
                         "flips when StegVerse-002/micro-node-runtime#96 merges")
        launcher = load("resident-runtime/self-characterization/stegverse-002.json")["principal"]["launcher_dispatcher"]
        self.assertIn("#" + str(launcher["pr"]), records["MANIFEST_DISPATCHER_IN_OTHER_REPO"]["next_attempt"])
        self.assertIn("CARRIED-epoch transition from the organization ledger head",
                      records["RUNTIME_DISPATCHER_PENDING_SUBSTRATE"]["detail"])

    def test_the_destination_declares_it_accepts_no_carried_crossings(self):
        self.assertIs(load(ACTIVATION)["accepts_carried_crossings"], False)


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
                if kind == "argument":
                    self.assertIn(binding["argument"].rstrip("="), source_of(supplier))
                elif kind == "frame_heartbeat":
                    kernel = source_of(binding["rule"])
                    self.assertIn("def consuming_epoch(", kernel)
                    self.assertIn("hb_epoch=consuming_epoch(frame,hb_epoch", source_of(supplier))
                elif kind == "dispatch_input":
                    self.assertEqual(supplier, binding["dispatcher"])

    def test_each_binding_has_an_in_tree_workflow_dispatch_that_supplies_the_epoch(self):
        """No host outside the tree binds an epoch: each binding names an in-repo dispatcher."""
        for path, binding in bindings(self.documents).items():
            with self.subTest(entrypoint=path):
                workflow_path = binding["dispatcher"]
                self.assertTrue(workflow_path.startswith(".github/workflows/"), workflow_path)
                workflow = source_of(workflow_path)
                on = workflow.split("\njobs:")[0]
                self.assertRegex(on, r"workflow_dispatch:\s*\n\s*inputs:[\s\S]*\n\s+hb_epoch:\s*\n[\s\S]*?required: true")
                self.assertNotRegex(on, r"\n\s*schedule:")
                # The "" -> NOT_SUPPLIED gate runs the shared rule before anything else.
                self.assertIn('if hb_epoch == "":', workflow)
                self.assertIn("kernel.writer_epoch_refusal(", workflow)
                self.assertIn("HB_EPOCH: ${{ github.event.inputs.hb_epoch }}", workflow)
                self.assertIn('--hb-epoch "$HB_EPOCH"', workflow)
                gate = workflow.index("kernel.writer_epoch_refusal(")
                reached = Path(binding.get("reached_from", path)).name
                self.assertIn(reached, workflow[gate:])
                self.assertNotIn("EnvironmentFile", workflow)

    def test_no_schedule_or_push_trigger_reaches_an_epoch_requiring_entrypoint(self):
        """A schedule or push run never invokes an entrypoint that needs an epoch."""
        declared = set().union(*(declared_paths(document) for document in self.documents.values()))
        requiring = {Path(path).name for path in declared if needs_epoch(path, declared)}
        for workflow_path in sorted(WORKFLOWS.glob("*.yml")):
            workflow = workflow_path.read_text(encoding="utf-8")
            on, _, jobs = workflow.partition("\njobs:")
            with self.subTest(workflow=workflow_path.name):
                self.assertNotRegex(on, r"\n\s*schedule:")
                if not re.search(r"\n\s*(push|pull_request):", on):
                    continue  # dispatched only: the dispatch carries its own hb_epoch
                for job in re.split(r"\n  (?=[A-Za-z0-9_-]+:\n)", jobs):
                    if "if: github.event_name == 'workflow_dispatch'" in job:
                        continue
                    for line in job.splitlines():
                        invoked = re.search(r"python3?\s+([\w./-]+\.py)", line)
                        if invoked:
                            self.assertNotIn(Path(invoked.group(1)).name, requiring, line)


if __name__ == "__main__":
    unittest.main()
