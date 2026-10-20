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


#: Text a CLI or STEGVERSE_HB_EPOCH can carry. int() would take the first
#: three as 33; the shared rule takes only ASCII digits. "" is supplied and
#: empty, so invalid; None is absent (an unset STEGVERSE_HB_EPOCH).
REFUSED_EPOCH_TEXT = ("+33", "\uff13\uff13", " 33", "True", "abc", "33.7", "", None)
ACCEPTED_EPOCH_TEXT = "4096"
INGRESS = ROOT / "resident-runtime/intr_destination_ingress.py"
EGRESS = ROOT / "resident-runtime/organization_egress_boundary.py"


class EpochTextIsJudgedByTheSharedRule(unittest.TestCase):
    """Every CLI --hb-epoch and STEGVERSE_HB_EPOCH reaches the shared rule as raw text."""

    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        self.work = Path(self._work.name)
        self.repo_root = self.work / "repo"
        self.org_root = self.work / "org"
        self.env = {k: v for k, v in os.environ.items() if k != "STEGVERSE_HB_EPOCH"}
        self.env.update({"STEGVERSE_REPO_LEDGER_ROOT": str(self.repo_root),
                         "STEGVERSE_ORG_LEDGER_ROOT": str(self.org_root)})
        diagnostic = {"message_class": "ecosystem.communication",
                      "communication_id": "epoch-text-diagnostic",
                      "subject": "purpose-neutral mesh diagnostic",
                      "body": {"schema": "stegverse.org-intr-destination-diagnostic/v1",
                               "probe": "diagnostic-crossing"}}
        self.payload = self.work / "payload.json"
        self.payload.write_text(json.dumps(diagnostic))
        self.standing = self.work / "standing.json"
        self.standing.write_text(json.dumps({"mode": "ESTABLISH_GENESIS",
                                             "node_ref": "epoch-text", "predecessor": None}))
        self.registry = ROOT / "org-boundary/registry/services.json"
        self.mesh = self.work / "mesh"
        self.out = self.work / "out.json"

    def run_cli(self, argv, epoch, *, via_env=False):
        env = dict(self.env)
        argv = list(argv)
        if epoch is not None:
            if via_env:
                env["STEGVERSE_HB_EPOCH"] = epoch
            else:
                argv += ["--hb-epoch", epoch]
        return subprocess.run([sys.executable, *map(str, argv)], capture_output=True,
                              text=True, env=env, check=False)

    def assertRefusedAndNothingWritten(self, completed, epoch):
        self.assertEqual(completed.returncode, 1, (epoch, completed.stdout, completed.stderr))
        refusal = json.loads(completed.stdout)
        self.assertEqual(refusal["disposition"], "FAIL_CLOSED", epoch)
        for field in SIX_FIELDS:
            self.assertTrue(refusal.get(field), (epoch, field))
        self.assertEqual(refusal["failure_code"],
                         "HB_EPOCH_NOT_SUPPLIED" if epoch is None else "HB_EPOCH_INVALID", epoch)
        self.assertEqual(refusal["failed_predicate"], "SUBMISSION_CARRIES_THE_SUPPLIED_HB_EPOCH")
        self.assertIn("--hb-epoch", refusal["retry_entrypoint"])
        self.assertIs(refusal["derived_from_clock"], False)
        self.assertFalse(self.repo_root.exists(), epoch)
        self.assertFalse(self.org_root.exists(), epoch)
        self.assertFalse(self.out.exists(), epoch)
        self.assertFalse((self.mesh / "frames.d").exists(), epoch)

    def repository_cli(self):
        return [ROOT / ".stegverse/transition-ledger/emit.py", "--transition-id", "epoch-text",
                "--transition-class", "TEST", "--predecessor-state-sha256", DIGEST_A,
                "--successor-state-sha256", DIGEST_B]

    def organization_cli(self):
        receipt_path = self.work / "repo-receipt.json"
        if not receipt_path.exists():
            with mock.patch.dict(os.environ, {"STEGVERSE_REPO_LEDGER_ROOT": str(self.work / "source"),
                                              "STEGVERSE_ORG_LEDGER_ROOT": str(self.org_root)}):
                receipt = repository.append("epoch-source", "TEST", DIGEST_A, DIGEST_B,
                                            {"n": 1}, "NONE", hb_epoch=32)
            receipt_path.write_text(json.dumps(receipt))
        return [ROOT / "resident-runtime/aggregate_repo_transition.py",
                "--repo-receipt", receipt_path,
                "--predecessor-org-state-sha256", DIGEST_A, "--successor-org-state-sha256", DIGEST_B]

    def receive_cli(self, packet_id="epoch-text"):
        return [INGRESS, "--payload", self.payload, "--registry", self.registry,
                "--packet-id", packet_id, "--out", self.out]

    def self_closure_cli(self):
        return [INGRESS, "--self-closure", "--communication-id", "epoch-text-closure",
                "--mesh-root", self.mesh, "--out", self.out]

    def emit_cli(self):
        return [EGRESS, "--destination-organization", "StegVerse-002", "--capability",
                "intr-destination", "--payload", self.payload, "--standing", self.standing,
                "--mesh-root", self.mesh, "--out", self.out]

    def test_every_cli_refuses_epoch_text_int_would_take(self):
        for name, argv in (("repository", self.repository_cli()),
                           ("organization", self.organization_cli()),
                           ("receive", self.receive_cli()),
                           ("self-closure", self.self_closure_cli()),
                           ("emit", self.emit_cli())):
            for epoch in REFUSED_EPOCH_TEXT:
                with self.subTest(cli=name, epoch=epoch):
                    self.assertRefusedAndNothingWritten(self.run_cli(argv, epoch), epoch)

    def test_the_environment_epoch_is_refused_by_the_same_rule(self):
        for epoch in REFUSED_EPOCH_TEXT:
            with self.subTest(epoch=epoch):
                self.assertRefusedAndNothingWritten(
                    self.run_cli(self.receive_cli(), epoch, via_env=True), epoch)

    def test_ascii_digits_are_accepted_from_the_cli_and_the_environment(self):
        for name, argv, via_env in (("repository", self.repository_cli(), False),
                                    ("organization", self.organization_cli(), False),
                                    ("receive --hb-epoch", self.receive_cli("epoch-cli"), False),
                                    ("receive STEGVERSE_HB_EPOCH", self.receive_cli("epoch-env"), True)):
            with self.subTest(cli=name):
                completed = self.run_cli(argv, ACCEPTED_EPOCH_TEXT, via_env=via_env)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                result = json.loads(completed.stdout)
                if name.startswith("receive"):
                    self.assertEqual(result["disposition"], "ALLOW")
                    self.assertIs(result["transition_replayed"], False)
                    root = self.repo_root
                    digest = result["repository_receipt_sha256"]
                    written = [json.loads(path.read_text()) for path in root.glob("receipts/*.json")]
                    result = next(row for row in written if row.get("receipt_sha256") == digest)
                self.assertEqual(result["observed_at"], "hb-epoch:4096")
                self.assertEqual(result["hb_reference"]["epoch"], 4096)



SUPPLIED = 4096
#: The epoch a patched clock reads. No receipt may carry it.
CLOCK_EPOCH = 5000
PEER = "StegVerse-org"
STANDING = {"mode": "ESTABLISH_GENESIS", "node_ref": "epoch-provenance", "predecessor": None}
REGISTRY = json.loads((ROOT / "org-boundary/registry/services.json").read_text(encoding="utf-8"))
datetime_module = sys.modules["datetime"]


class _FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        kernel = repository.kernel
        now_ns = kernel.HB_ANCHOR_UNIX_NS + (CLOCK_EPOCH - kernel.HB_ANCHOR_EPOCH) * kernel.HB_PERIOD_NS
        return datetime.fromtimestamp(now_ns / 1_000_000_000, tz)


def _diagnostic(communication_id):
    return {"message_class": "ecosystem.communication", "communication_id": communication_id,
            "subject": "purpose-neutral mesh diagnostic",
            "body": {"schema": "stegverse.org-intr-destination-diagnostic/v1",
                     "probe": "diagnostic-crossing"}}


class AnEpochIsForwardedOnlyAsSupplied(unittest.TestCase):
    """The organization writer gets the epoch supplied to the ingress, never one read back.

    Each ingress runs with the epoch absent and the clock patched to a fixed
    value: nothing is written. A repository receipt already recorded at another
    epoch does not lend that epoch to the organization receipt.
    """

    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        work = Path(self._work.name)
        self.repo_root, self.org_root, self.mesh = work / "repo", work / "org", work / "mesh"
        env = {k: v for k, v in os.environ.items() if k != "STEGVERSE_HB_EPOCH"}
        env.update({"STEGVERSE_REPO_LEDGER_ROOT": str(self.repo_root),
                    "STEGVERSE_ORG_LEDGER_ROOT": str(self.org_root)})
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ingress = _load("provenance_ingress", "resident-runtime/intr_destination_ingress.py")
        self.egress = _load("provenance_egress", "resident-runtime/organization_egress_boundary.py")
        # Modules loaded later (self-closure, dispatch) bind the patched clock too.
        clocks = [mock.patch.object(datetime_module, "datetime", _FixedClock)]
        for module in (self.ingress.kernel, self.ingress.repository_ledger.kernel,
                       self.ingress.organization_ledger.kernel, self.egress.kernel,
                       self.egress.repository_ledger.kernel, self.egress.organization_ledger.kernel):
            clocks.append(mock.patch.object(module, "datetime", _FixedClock))
        for clock in clocks:
            clock.start()
            self.addCleanup(clock.stop)

    def receipts(self):
        found = []
        for root in (self.repo_root, self.org_root):
            if root.exists():
                found += [json.loads(path.read_text()) for path in root.rglob("receipts/*.json")]
        return found

    def assertNothingWritten(self):
        self.assertFalse(self.repo_root.exists())
        self.assertFalse(self.org_root.exists())
        self.assertFalse((self.mesh / "frames.d").exists())

    def assertOnlySupplied(self, *epochs):
        written = self.receipts()
        self.assertTrue(written)
        for receipt in written:
            reference = receipt["hb_reference"]
            self.assertIn(reference["epoch"], epochs, receipt.get("schema"))
            self.assertNotEqual(reference["epoch"], CLOCK_EPOCH)
            self.assertIs(reference["derived_from_clock"], False)
            self.assertNotIn("sampled_unix_ns", reference)
            self.assertEqual(receipt["observed_at"], "hb-epoch:" + str(reference["epoch"]))

    def test_the_patched_clock_reads_the_fixed_epoch(self):
        self.assertEqual(self.ingress.kernel.hb_reference()["epoch"], CLOCK_EPOCH)

    def test_receive_without_an_epoch_writes_nothing(self):
        with self.assertRaises(ValueError) as refused:
            self.ingress.receive(_diagnostic("absent-receive"), registry=REGISTRY,
                                 packet_id="absent-receive")
        self.assertEqual(refused.exception.refusal["failure_code"], "HB_EPOCH_NOT_SUPPLIED")
        self.assertNothingWritten()

    def test_emit_without_an_epoch_writes_nothing(self):
        with self.assertRaises(ValueError) as refused:
            self.egress.emit(PEER, _diagnostic("absent-emit"), standing=STANDING,
                             capability="intr-destination", mesh_root=self.mesh)
        self.assertEqual(refused.exception.refusal["failure_code"], "HB_EPOCH_NOT_SUPPLIED")
        self.assertNothingWritten()

    def test_self_closure_without_an_epoch_writes_nothing(self):
        with self.assertRaises(ValueError) as refused:
            self.ingress.diagnostic_self_closure("absent-closure", mesh_root=self.mesh)
        self.assertEqual(refused.exception.refusal["failure_code"], "HB_EPOCH_NOT_SUPPLIED")
        self.assertNothingWritten()

    def test_close_without_an_epoch_writes_no_closure(self):
        kernel = self.egress.kernel
        emitted = self.egress.emit(PEER, _diagnostic("absent-close"), standing=STANDING,
                                   capability="intr-destination", mesh_root=self.mesh,
                                   hb_epoch=SUPPLIED)
        self.assertEqual(emitted["disposition"], "ALLOW", emitted.get("detail"))
        before = self.receipts()
        packet = kernel.recover_packet(json.loads(next((self.mesh / "frames.d").rglob("*.json")).read_text()))
        chain, previous = [], None
        for kind in self.egress.FAR_SIDE_RECEIPT_KINDS:
            receipt = kernel.receipt(kind, packet["packet_id"], packet["destination"]["service"],
                                     previous, {"payload_hash": kernel.sha(packet["payload"])})
            chain.append(receipt["receipt_id"])
            previous = receipt["receipt_id"]
        response = kernel.build_control_response(
            packet, {"application_result": {"disposition": "ALLOW"},
                     "reconstruction": {"terminal_receipt_id": chain[-1]}})
        kernel.publish_packet(response, root=self.mesh,
                              now_ns=kernel.HB_ANCHOR_UNIX_NS + 2 * kernel.HB_PERIOD_NS)
        refused = self.egress.close(PEER, packet["packet_id"], "absent-close", mesh_root=self.mesh)
        self.assertEqual(refused["disposition"], "FAIL_CLOSED")
        self.assertEqual(refused["failure_code"], "HB_EPOCH_NOT_SUPPLIED")
        self.assertIs(refused["closure_recorded"], False)
        self.assertEqual(len(self.receipts()), len(before))
        self.assertOnlySupplied(SUPPLIED)

    def test_the_supplied_epoch_reaches_both_receipts(self):
        result = self.ingress.receive(_diagnostic("supplied"), registry=REGISTRY,
                                      packet_id="supplied", hb_epoch=str(SUPPLIED))
        self.assertEqual(result["disposition"], "ALLOW", result.get("detail"))
        by_digest = {receipt["receipt_sha256"]: receipt for receipt in self.receipts()}
        for digest in (result["repository_receipt_sha256"], result["organization_receipt_sha256"]):
            self.assertEqual(by_digest[digest]["hb_reference"]["epoch"], SUPPLIED)
        self.assertOnlySupplied(SUPPLIED)

    def test_self_closure_writes_only_the_supplied_epoch(self):
        result = self.ingress.diagnostic_self_closure("supplied-closure", mesh_root=self.mesh,
                                                      hb_epoch=str(SUPPLIED))
        self.assertEqual(result["disposition"], "ALLOW", result.get("detail"))
        self.assertOnlySupplied(SUPPLIED)

    def test_a_recorded_repository_epoch_is_not_forwarded_by_receive(self):
        # A repository receipt already recorded at 40, with no organization receipt.
        evidence = self.ingress._evidence(_diagnostic("recorded"), "recorded", "ALLOW")
        transition = self.ingress.OPERATION_ID + ":recorded"
        successor = self.ingress.sha({"disposition": "ALLOW", "packet_id": "recorded",
                                      "communication_id": "recorded",
                                      "payload_sha256": evidence["payload_sha256"]})
        self.ingress.repository_ledger.append(
            transition, self.ingress.OPERATION_ID, evidence["payload_sha256"], successor,
            dict(evidence), "NONE", hb_epoch=40)
        result = self.ingress.receive(_diagnostic("recorded"), registry=REGISTRY,
                                      packet_id="recorded", hb_epoch=SUPPLIED)
        self.assertIs(result["transition_replayed"], True)
        organization, = [r for r in self.receipts()
                         if r["schema"] == "stegverse.organization-transition-receipt/v1"]
        self.assertEqual(organization["hb_reference"]["epoch"], SUPPLIED)
        self.assertEqual(organization["observed_at"], "hb-epoch:" + str(SUPPLIED))

    def test_a_recorded_repository_epoch_is_not_forwarded_by_egress(self):
        record = {"intended_action": "EMIT", "disposition": "ALLOW",
                  "crossed_an_organization_boundary": True, "communication_id": "egress-recorded",
                  "payload_sha256": DIGEST_A}
        self.egress.repository_ledger.append(
            "EGRESS:recorded", "EGRESS", DIGEST_A, DIGEST_B, dict(record), "NONE", hb_epoch=40)
        appended = self.egress._record("EGRESS:recorded", "EGRESS", DIGEST_A, DIGEST_B,
                                       record, SUPPLIED)
        self.assertEqual(appended["repository_receipt"]["hb_reference"]["epoch"], 40)
        self.assertEqual(appended["organization_receipt"]["hb_reference"]["epoch"], SUPPLIED)


if __name__ == "__main__":
    unittest.main()
