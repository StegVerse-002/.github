"""Both ledger writers take the epoch their caller supplies, or refuse.

An absent or invalid epoch is a six-field FAIL_CLOSED raised before the store
opens. No clock stands in for it. The stores here are temporary directories,
not the published organization ledger ref.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SIX_FIELDS = ("failure_code", "failed_predicate", "required_evidence_or_repair",
              "retry_entrypoint", "owning_existing_goal", "next_attempt")
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repository = _load("epoch_repo_emit", ".stegverse/transition-ledger/emit.py")
organization = _load("epoch_org_append", "resident-runtime/aggregate_repo_transition.py")


class _ClockRead(AssertionError):
    pass


class _NoClock(datetime):
    @classmethod
    def now(cls, tz=None):
        raise _ClockRead("a receipt writer read the clock")


class _Unopened:
    """A store that fails any use, so a refusal is proven to precede it."""

    def __getattr__(self, name):
        raise AssertionError("the store was used before the epoch was checked: " + name)


class LedgerWriterSuppliedEpoch(unittest.TestCase):
    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        self.repo_root = Path(self._work.name) / "repo"
        self.org_root = Path(self._work.name) / "org"
        patcher = mock.patch.dict(os.environ, {"STEGVERSE_REPO_LEDGER_ROOT": str(self.repo_root),
                                               "STEGVERSE_ORG_LEDGER_ROOT": str(self.org_root)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertSixFieldRefusal(self, refused, code, entrypoint):
        refusal = refused.exception.refusal
        self.assertEqual(refusal["disposition"], "FAIL_CLOSED")
        for field in SIX_FIELDS:
            self.assertTrue(refusal.get(field), field)
        self.assertEqual(refusal["failure_code"], code)
        self.assertEqual(refusal["failed_predicate"], "SUBMISSION_CARRIES_THE_SUPPLIED_HB_EPOCH")
        self.assertIn(entrypoint, refusal["retry_entrypoint"])
        self.assertIs(refusal["derived_from_clock"], False)
        self.assertIs(refusal["consequence_committed"], False)

    def repository_receipt(self, epoch=32):
        return repository.append("epoch-1", "TEST", DIGEST_A, DIGEST_B, {"n": 1}, "NONE", hb_epoch=epoch)

    def test_the_repository_writer_refuses_an_absent_epoch_before_the_store_opens(self):
        for store in (None, _Unopened()):
            with self.assertRaises(repository.RepoLedgerEpochRefused) as refused:
                repository.append("epoch-1", "TEST", DIGEST_A, DIGEST_B, {"n": 1}, "NONE", store=store)
            self.assertSixFieldRefusal(refused, "HB_EPOCH_NOT_SUPPLIED", "emit.py::append")
        self.assertFalse(self.repo_root.exists())

    def test_the_organization_writer_refuses_an_absent_epoch_before_the_store_opens(self):
        source = self.repository_receipt()
        for store in (None, _Unopened()):
            with self.assertRaises(organization.OrgLedgerEpochRefused) as refused:
                organization.append(source, "REPO_STATE_PROPAGATION", DIGEST_A, DIGEST_B, {}, "NONE",
                                    store=store)
            self.assertSixFieldRefusal(refused, "HB_EPOCH_NOT_SUPPLIED", "aggregate_repo_transition.py::append")
        self.assertFalse(self.org_root.exists())

    def test_an_invalid_epoch_is_refused_by_both_writers(self):
        source = self.repository_receipt()
        for epoch in (True, 31, -1, "32a", "", 32.0, "３２"):
            with self.assertRaises(repository.RepoLedgerEpochRefused) as refused:
                repository.append("epoch-2", "TEST", DIGEST_A, DIGEST_B, {}, "NONE",
                                  hb_epoch=epoch, store=_Unopened())
            self.assertSixFieldRefusal(refused, "HB_EPOCH_INVALID", "emit.py::append")
            with self.assertRaises(organization.OrgLedgerEpochRefused) as refused:
                organization.append(source, "REPO_STATE_PROPAGATION", DIGEST_A, DIGEST_B, {}, "NONE",
                                    hb_epoch=epoch, store=_Unopened())
            self.assertSixFieldRefusal(refused, "HB_EPOCH_INVALID", "aggregate_repo_transition.py::append")

    def test_a_supplied_epoch_is_written_and_no_clock_is_read(self):
        for writer in (repository, organization):
            self.assertFalse(hasattr(writer, "datetime"), writer.__name__)
        with mock.patch.object(repository.kernel, "datetime", _NoClock), \
                mock.patch.object(organization.kernel, "datetime", _NoClock):
            source = self.repository_receipt(epoch="40")
            receipt = organization.append(source, "REPO_STATE_PROPAGATION", DIGEST_A, DIGEST_B,
                                          {}, "NONE", hb_epoch=source["hb_reference"]["epoch"])
        for written in (source, receipt):
            self.assertEqual(written["hb_reference"]["epoch"], 40)
            self.assertEqual(written["observed_at"], "hb-epoch:40")

    def test_the_writer_clis_print_the_refusal_and_exit_nonzero(self):
        env = {**os.environ, "STEGVERSE_REPO_LEDGER_ROOT": str(self.repo_root),
               "STEGVERSE_ORG_LEDGER_ROOT": str(self.org_root)}
        completed = subprocess.run(
            [sys.executable, str(ROOT / ".stegverse/transition-ledger/emit.py"),
             "--transition-id", "cli-1", "--transition-class", "TEST",
             "--predecessor-state-sha256", DIGEST_A, "--successor-state-sha256", DIGEST_B],
            capture_output=True, text=True, env=env, check=False)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        refusal = json.loads(completed.stdout)
        self.assertEqual(refusal["failure_code"], "HB_EPOCH_NOT_SUPPLIED")
        for field in SIX_FIELDS:
            self.assertTrue(refusal.get(field), field)
        self.assertFalse(self.repo_root.exists())

        receipt_path = Path(self._work.name) / "repo-receipt.json"
        receipt_path.write_text(json.dumps(self.repository_receipt()))
        completed = subprocess.run(
            [sys.executable, str(ROOT / "resident-runtime/aggregate_repo_transition.py"),
             "--repo-receipt", str(receipt_path),
             "--predecessor-org-state-sha256", DIGEST_A, "--successor-org-state-sha256", DIGEST_B],
            capture_output=True, text=True, env=env, check=False)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        refusal = json.loads(completed.stdout)
        self.assertEqual(refusal["failure_code"], "HB_EPOCH_NOT_SUPPLIED")
        self.assertFalse(self.org_root.exists())


if __name__ == "__main__":
    unittest.main()
