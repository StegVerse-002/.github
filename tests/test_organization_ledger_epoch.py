"""The committed supplied-epoch carrier (resident-runtime/organization_ledger_epoch.py). Not an InTr hop.

Temp ledgers are the tree of the pinned ledger tip (git archive), never the
published ref. Receipts written here are NOT LEDGERED and NOT AUTHENTIC.
SKAP Vault inside KV is the only PII and credential store for every user, the
ecosystem's own included; the ecosystem holds none (HST citation pending P1 #163).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER_TIP = json.loads((ROOT / "tests/fixtures/intr-path-ingress/pin.json").read_text())["ledger_tip"]
NAMESPACE = json.loads((ROOT / ".stegverse/transition-ledger/contract.json").read_text())[
    "repository_ledger_location"]["namespace"]
SIX = ("failure_code", "failed_predicate", "required_evidence_or_repair", "retry_entrypoint",
       "owning_existing_goal", "next_attempt")


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ep = load("organization_ledger_epoch_under_test", "resident-runtime/organization_ledger_epoch.py")


class Ledger:
    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        subprocess.run("git -C '%s' archive %s | tar -x -C '%s'" % (ROOT, LEDGER_TIP, self.root), shell=True, check=True)
        self.saved = {k: os.environ.get(k) for k in ("STEGVERSE_ORG_LEDGER_ROOT", "STEGVERSE_REPO_LEDGER_ROOT")}
        os.environ["STEGVERSE_ORG_LEDGER_ROOT"] = str(self.root)
        os.environ["STEGVERSE_REPO_LEDGER_ROOT"] = str(self.root / NAMESPACE)

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def close(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.dir.cleanup()


class Packet(unittest.TestCase):
    def test_the_committed_packet_carries_a_supplied_epoch_and_its_source(self):
        packet, failed = ep.load_packet()
        self.assertIsNone(failed, failed)
        self.assertEqual(packet["organization"], json.loads((ROOT / ".stegverse/transition-ledger/org-contract.json").read_text())["organization"])
        self.assertIs(type(packet["hb_epoch"]), int)
        self.assertGreaterEqual(packet["hb_epoch"], 32)
        self.assertTrue(packet["epoch_source"]["head_receipt_sha256"].startswith("sha256:"))

    def test_an_invalid_packet_writes_nothing_and_carries_six_fields(self):
        ledger = Ledger()
        try:
            before = ledger.files()
            bad = ledger.root / "bad.json"
            bad.write_text(json.dumps({"schema": ep.SCHEMA, "packet_id": "x", "hb_epoch": 5, "epoch_source": {}}))
            result = ep.append(bad)
            self.assertEqual(result["disposition"], "FAIL_CLOSED")
            self.assertTrue(all(result.get(f) for f in SIX), result)
            after = {k: v for k, v in ledger.files().items() if k != "bad.json"}
            self.assertEqual(after, before)
        finally:
            ledger.close()

    def test_it_is_not_an_intr_hop(self):
        packet, _ = ep.load_packet()
        evidence = ep.evidence(packet)
        self.assertIs(evidence["intr_hop"], False)
        self.assertIsNone(evidence["communication_id"])
        self.assertNotIn("intr-destination", json.dumps(packet))
        self.assertNotEqual(ep.OPERATION, "ORGANIZATION_INTR_DESTINATION_INGRESS")


class Append(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()

    def tearDown(self):
        self.ledger.close()

    def test_append_supplies_the_head_epoch_once_then_is_not_required(self):
        packet, _ = ep.load_packet()
        first = ep.append()
        self.assertIn(first["disposition"], ("ALLOW", "NOT_REQUIRED"), first)
        self.assertEqual(ep.verify(), {"disposition": "ALLOW", "head_epoch": ep.verify()["head_epoch"]})
        if first["disposition"] == "ALLOW":
            self.assertEqual(ep.verify()["head_epoch"], packet["hb_epoch"])
        files = self.ledger.files()
        second = ep.append()
        self.assertEqual(second["disposition"], "NOT_REQUIRED", second)
        self.assertEqual(self.ledger.files(), files)

    def test_the_main_merge_transfer_is_admitted_after_the_epoch(self):
        ep.append()
        epoch, failed = ep.mt().head_epoch(ep.mt().org_store())
        self.assertIsNone(failed, failed)
        self.assertIs(type(epoch), int)


if __name__ == "__main__":
    unittest.main()
