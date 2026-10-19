"""No receipt or frame on a consuming route takes its time from the clock unmarked.

The clock is fixed to one heartbeat epoch and counted, in this process and in
every subprocess (a ``sitecustomize`` on ``PYTHONPATH``). Each route runs with
the epoch absent, where it refuses six-field before anything is written, and
with ``"4096"`` supplied, where everything it writes carries 4096 and the clock
is never read. A clock value anywhere must carry its marker: ``derived_from_clock``
true or ``sampled_unix_ns``.

The routes run against a copy of this repository with the mesh, both ledger
roots and the self-characterization state redirected. Inbound frames are
fabricated by the test at the clock and are the only clock values written.
"""
from __future__ import annotations

import base64
import datetime as datetime_module
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SIX_FIELDS = ("failure_code", "failed_predicate", "required_evidence_or_repair",
              "retry_entrypoint", "owning_existing_goal", "next_attempt")
SUPPLIED = 4096
THIS = "StegVerse-002"
PEER = "StegVerse-org"


def _load(name, root, relative):
    spec = importlib.util.spec_from_file_location(name, root / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_anchor = _load("marker_anchor_kernel", ROOT, "org-kernel/kernel.py")
CLOCK_EPOCH = 5000
#: Mid-period, so the epoch survives the float round trip through a timestamp.
CLOCK_NS = (_anchor.HB_ANCHOR_UNIX_NS + (CLOCK_EPOCH - _anchor.HB_ANCHOR_EPOCH) * _anchor.HB_PERIOD_NS
            + _anchor.HB_PERIOD_NS // 2)
CLOCK_ISO = datetime_module.datetime.fromtimestamp(CLOCK_NS / 1e9, timezone.utc).isoformat()
REAL_DATETIME = datetime_module.datetime

SITECUSTOMIZE = textwrap.dedent(f"""
    import datetime as _d, os
    _base = _d.datetime
    class _FixedClock(_base):
        @classmethod
        def now(cls, tz=None):
            with open(os.environ["STEGVERSE_TEST_CLOCK_LOG"], "a") as handle:
                handle.write("now\\n")
            return _base.fromtimestamp({CLOCK_NS} / 1e9, tz)
    _d.datetime = _FixedClock
""")


class _FixedClock(REAL_DATETIME):
    @classmethod
    def now(cls, tz=None):
        with open(os.environ["STEGVERSE_TEST_CLOCK_LOG"], "a") as handle:
            handle.write("now\n")
        return REAL_DATETIME.fromtimestamp(CLOCK_NS / 1e9, tz)


def _is_clock(key, value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return (key in {"epoch", "generation"} and value == CLOCK_EPOCH) or abs(value - CLOCK_NS) < _anchor.HB_PERIOD_NS
    if isinstance(value, str):
        return CLOCK_ISO[:19] in value or value in {f"hb-epoch:{CLOCK_EPOCH}", f"HB:{CLOCK_EPOCH}"}
    return False


def unmarked_clock_values(value, path="$"):
    """Every clock value not carried beside its marker, as a JSON path."""
    found = []
    if isinstance(value, dict):
        marked = value.get("derived_from_clock") is True or "sampled_unix_ns" in value
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                found += unmarked_clock_values(item, path + "." + key)
            elif _is_clock(key, item) and not marked:
                found.append(path + "." + key)
        packed = value.get("packet_base64")
        if isinstance(packed, str):
            found += unmarked_clock_values(json.loads(base64.b64decode(packed)), path + ".<packet>")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, (dict, list)):
                found += unmarked_clock_values(item, f"{path}[{index}]")
            elif _is_clock(None, item):
                found.append(f"{path}[{index}]")
    return found


def supplied_marked_wrongly(value, path="$"):
    """References marked supplied that carry a clock sample or the clock's epoch."""
    found = []
    if isinstance(value, dict):
        if value.get("derived_from_clock") is False and (
                "sampled_unix_ns" in value or value.get("epoch") == CLOCK_EPOCH):
            found.append(path)
        for key, item in value.items():
            found += supplied_marked_wrongly(item, path + "." + key)
        packed = value.get("packet_base64")
        if isinstance(packed, str):
            found += supplied_marked_wrongly(json.loads(base64.b64decode(packed)), path + ".<packet>")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += supplied_marked_wrongly(item, f"{path}[{index}]")
    return found


def marked_clock_values(value):
    """How many marked clock heartbeats a value carries, decoding packed frames."""
    count = 0
    if isinstance(value, dict):
        if "sampled_unix_ns" in value and value.get("epoch") == CLOCK_EPOCH:
            count += 1
        for item in value.values():
            count += marked_clock_values(item)
        packed = value.get("packet_base64")
        if isinstance(packed, str):
            count += marked_clock_values(json.loads(base64.b64decode(packed)))
    elif isinstance(value, list):
        count += sum(marked_clock_values(item) for item in value)
    return count


def diagnostic(communication_id):
    return {"message_class": "ecosystem.communication", "communication_id": communication_id,
            "subject": "purpose-neutral mesh diagnostic",
            "body": {"schema": "stegverse.org-intr-destination-diagnostic/v1",
                     "probe": "diagnostic-crossing"}}


class ConsumingRoutes(unittest.TestCase):
    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        work = Path(self._work.name)
        self.work = work
        self.root = work / "root"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.mesh = work / "mesh"
        self.repo_ledger, self.org_ledger = work / "repo-ledger", work / "org-ledger"
        self.self_char = work / "self-characterization"
        self.clock_log = work / "clock.log"
        self.clock_log.write_text("")
        site = work / "site"
        site.mkdir()
        (site / "sitecustomize.py").write_text(SITECUSTOMIZE)
        env = {key: value for key, value in os.environ.items()
               if key not in {"STEGVERSE_HB_EPOCH", "STEGVERSE_ORG_FEDERATION_GATEWAY_URL"}}
        env.update({"STEGVERSE_REPO_LEDGER_ROOT": str(self.repo_ledger),
                    "STEGVERSE_ORG_LEDGER_ROOT": str(self.org_ledger),
                    "STEGVERSE_ORG_FEDERATION_ROOT": str(self.mesh),
                    "STEGVERSE_SELF_CHAR_STATE_ROOT": str(self.self_char),
                    "STEGVERSE_TEST_CLOCK_LOG": str(self.clock_log),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(site)})
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Modules loaded from here on bind the fixed clock; so does this kernel.
        clock = mock.patch.object(datetime_module, "datetime", _FixedClock)
        clock.start()
        self.addCleanup(clock.stop)
        self.K = _load("marker_kernel", self.root, "org-kernel/kernel.py")

    def clock_reads(self):
        return len(self.clock_log.read_text().splitlines())

    def publish_inbound(self, service, payload, packet_id, *, epoch=None):
        """A peer's frame. With no epoch it is stamped at the clock, and marked so; with one, it carries it."""
        packet = self.K.build_packet(
            origin_org=PEER, origin_service="stegverse-org.org-control", destination_org=THIS,
            destination_service=service, payload=payload,
            transition_reference="probe:" + packet_id, authority_effect="NONE", packet_id=packet_id)
        now_ns = None if epoch is None else self.K.epoch_now_ns(epoch)
        frame = self.K.publish_packet(packet, root=self.mesh, now_ns=now_ns)["frame"]
        reference = frame["heartbeat_reference"]
        if epoch is None:
            self.assertEqual(reference["epoch"], CLOCK_EPOCH)
            self.assertIs(reference["derived_from_clock"], True)
            self.assertIn("sampled_unix_ns", reference)
        else:
            self.assertEqual(reference["epoch"], epoch)
            self.assertIs(reference["derived_from_clock"], False)
            self.assertNotIn("sampled_unix_ns", reference)
        return frame

    def frames(self):
        directory = self.mesh / "frames.d"
        return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))] if directory.is_dir() else []

    def written(self):
        rows = []
        for path in sorted(self.work.rglob("*")):
            if self.root in path.parents and "resident-runtime" not in path.parts:
                continue
            if path.suffix == ".json" and path.is_file():
                try:
                    rows.append((path, json.loads(path.read_text())))
                except ValueError:
                    continue
            elif path.suffix == ".jsonl" and path.is_file():
                rows += [(path, json.loads(line)) for line in path.read_text().splitlines() if line]
        return rows

    def receipts(self):
        found = []
        for root in (self.repo_ledger, self.org_ledger):
            if root.exists():
                found += [json.loads(path.read_text()) for path in root.rglob("receipts/*.json")]
        return found

    def assertRefusal(self, refusal, code="HB_EPOCH_NOT_SUPPLIED"):
        self.assertEqual(refusal["disposition"], "FAIL_CLOSED")
        for field in SIX_FIELDS:
            self.assertTrue(refusal.get(field), field)
        self.assertEqual(refusal["failure_code"], code)
        self.assertIs(refusal["derived_from_clock"], False)
        self.assertIs(refusal["consequence_committed"], False)

    def assertNoLedger(self):
        self.assertFalse(self.repo_ledger.exists())
        self.assertFalse(self.org_ledger.exists())

    def assertAllSupplied(self):
        written = self.receipts()
        self.assertTrue(written)
        for receipt in written:
            self.assertEqual(receipt["hb_reference"]["epoch"], SUPPLIED)
            self.assertEqual(receipt["observed_at"], f"hb-epoch:{SUPPLIED}")
            self.assertIs(receipt["hb_reference"]["derived_from_clock"], False)
            self.assertNotIn("sampled_unix_ns", receipt["hb_reference"])

    def assertNoUnmarkedClock(self):
        for path, value in self.written():
            self.assertEqual(unmarked_clock_values(value), [], str(path))
            self.assertEqual(supplied_marked_wrongly(value), [], str(path))


class ConsumeAndRespond(ConsumingRoutes):
    """Row 1: the response frame takes the supplied epoch, never ``publish_packet(None)``."""

    def test_an_absent_epoch_is_refused_before_any_frame_is_consumed(self):
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("absent-consume"), "absent-consume")
        reads = self.clock_reads()
        with self.assertRaises(self.K.SuppliedEpochRefused) as refused:
            self.K.consume_and_respond(self.root, mesh_root=self.mesh)
        self.assertRefusal(refused.exception.refusal)
        self.assertEqual(len(self.frames()), 1)
        self.assertFalse((self.root / "resident-runtime/federation/seen.d").exists())
        self.assertNoLedger()
        self.assertEqual(self.clock_reads(), reads)

    def test_a_frame_at_a_supplied_epoch_is_answered_at_that_epoch(self):
        self.publish_inbound(THIS.lower() + ".org-control",
                             {"message_class": "ecosystem.communication", "communication_id": "carried",
                              "subject": "s", "body": {}}, "carried", epoch=SUPPLIED)
        reads = self.clock_reads()
        # No caller epoch: the frame's own supplied epoch is the one everything answers at.
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh)
        self.assertEqual(self.clock_reads(), reads)
        reference = results[0]["response_publication"]["frame"]["heartbeat_reference"]
        self.assertEqual(reference["epoch"], SUPPLIED)
        self.assertIs(reference["derived_from_clock"], False)
        self.assertNotIn("sampled_unix_ns", reference)
        self.assertNoUnmarkedClock()

    def test_the_response_frame_and_receipts_carry_the_supplied_epoch(self):
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("supplied-consume"), "supplied-consume")
        reads = self.clock_reads()
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=str(SUPPLIED))
        self.assertEqual(self.clock_reads(), reads)
        published = results[0]["response_publication"]
        self.assertEqual(published["frame"]["heartbeat_reference"]["epoch"], SUPPLIED)
        self.assertAllSupplied()
        self.assertNoUnmarkedClock()


class FederationCycle(ConsumingRoutes):
    """Row 2: the cycle takes the supplied epoch, stamps its record and frames from it, or refuses."""

    def run_cycle(self, *argv):
        out = self.work / "latest-cycle.json"
        driver = (f"import sys, runpy; sys.argv={[str(self.root / 'resident-runtime/federation_cycle.py'), '--out', str(out), *argv]!r}; "
                  f"runpy.run_path(sys.argv[0], run_name='__main__')")
        return subprocess.run([sys.executable, "-c", driver], capture_output=True, text=True,
                              env=dict(os.environ), check=False), out

    def test_a_clock_stamped_frame_without_an_epoch_is_a_six_field_refusal(self):
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("cycle-absent"), "cycle-absent")
        reads = self.clock_reads()
        for argv in ((), ("--hb-epoch", "+33")):
            with self.subTest(argv=argv):
                completed, out = self.run_cycle(*argv)
                self.assertEqual(completed.returncode, 1, completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
                self.assertRefusal(json.loads(completed.stdout),
                                   "HB_EPOCH_NOT_SUPPLIED" if not argv else "HB_EPOCH_INVALID")
                self.assertFalse(out.exists())
        self.assertEqual(len(self.frames()), 1)
        self.assertFalse((self.root / "resident-runtime/federation/seen.d").exists())
        self.assertNoLedger()
        self.assertEqual(self.clock_reads(), reads)

    def test_the_cycle_record_and_frames_carry_the_supplied_epoch(self):
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("cycle-supplied"), "cycle-supplied")
        reads = self.clock_reads()
        with mock.patch.dict(os.environ, {"STEGVERSE_HB_EPOCH": str(SUPPLIED)}):
            completed, out = self.run_cycle()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.clock_reads(), reads)
        record = json.loads(out.read_text())
        self.assertEqual(record["heartbeat_reference"]["epoch"], SUPPLIED)
        self.assertIs(record["heartbeat_reference"]["derived_from_clock"], False)
        self.assertNotIn("sampled_unix_ns", record["heartbeat_reference"])
        self.assertEqual(record["frames_consumed"], 1)
        self.assertEqual(record["responses_emitted"], 1)
        responses = [frame for frame in self.frames() if frame["destination_org"] == PEER]
        self.assertEqual([frame["heartbeat_reference"]["epoch"] for frame in responses], [SUPPLIED])
        self.assertEqual([frame["heartbeat_reference"]["derived_from_clock"] for frame in responses], [False])
        self.assertAllSupplied()
        self.assertNoUnmarkedClock()

    def test_the_gateway_cycle_answers_and_acknowledges_at_the_supplied_epoch(self):
        gateway = _load("marker_gateway", self.root, "resident-runtime/federation_gateway_transport.py")
        frame = self.publish_inbound(THIS.lower() + ".org-control",
                                     {"message_class": "ecosystem.communication",
                                      "communication_id": "gateway-cycle", "subject": "s", "body": {}},
                                     "gateway-cycle")
        submitted, acknowledged = [], []
        fetch = mock.patch.object(gateway, "fetch_frame",
                                  return_value={"state": "FRAME_AVAILABLE", "frame": frame})
        submit = mock.patch.object(gateway, "submit_frame",
                                   side_effect=lambda value: submitted.append(value) or {"state": "STORED"})
        ack = mock.patch.object(gateway, "_json_request",
                                side_effect=lambda method, path, body=None, headers=None:
                                acknowledged.append(body) or {"state": "ACKNOWLEDGED"})
        with fetch as fetched, submit, ack:
            reads = self.clock_reads()
            with self.assertRaises(gateway.K.SuppliedEpochRefused) as refused:
                gateway.resident_gateway_cycle(self.root)
            self.assertRefusal(refused.exception.refusal)
            fetched.assert_not_called()
            result = gateway.resident_gateway_cycle(self.root, hb_epoch=str(SUPPLIED))
        self.assertEqual(self.clock_reads(), reads)
        self.assertEqual(result["responses_emitted"], 1)
        self.assertEqual([value["heartbeat_reference"]["epoch"] for value in submitted], [SUPPLIED])
        self.assertEqual([value["observed_at"] for value in acknowledged], [f"hb-epoch:{SUPPLIED}"])
        for value in submitted + acknowledged:
            self.assertEqual(unmarked_clock_values(value), [])


class SelfCharacterizationReceipts(ConsumingRoutes):
    """Row 3: the five boundary receipts take the supplied epoch, or nothing is written."""

    def setUp(self):
        super().setUp()
        # The far endpoint is a stub: the boundary receipts around it are under test.
        (self.root / "resident-runtime/self_characterization_surface.py").write_text(textwrap.dedent("""
            import argparse, json
            from pathlib import Path
            ap = argparse.ArgumentParser()
            for name in ("--ingress", "--entity-id", "--out"):
                ap.add_argument(name)
            a = ap.parse_args()
            Path(a.out).write_text(json.dumps({"state": "ATTEMPT_RECORDED"}))
        """))

    def test_an_absent_epoch_writes_no_live_receipt(self):
        frame = self.publish_inbound(THIS.lower() + ".self-characterization", {"probe": "self"}, "self-absent")
        reads = self.clock_reads()
        with self.assertRaises(self.K.SuppliedEpochRefused) as refused:
            self.K.ingest_frame(self.root, frame, mesh_root=self.mesh)
        self.assertRefusal(refused.exception.refusal)
        self.assertFalse(self.self_char.exists())
        self.assertEqual(self.clock_reads(), reads)

    def test_the_live_receipts_carry_the_supplied_epoch(self):
        frame = self.publish_inbound(THIS.lower() + ".self-characterization", {"probe": "self"}, "self-supplied")
        reads = self.clock_reads()
        result = self.K.ingest_frame(self.root, frame, mesh_root=self.mesh, hb_epoch=str(SUPPLIED))
        self.assertEqual(self.clock_reads(), reads)
        self.assertEqual(result["status"], "CONSUMED")
        live = [json.loads(line) for line in
                (self.self_char / "ORG_BOUNDARY_RECEIPTS.live.jsonl").read_text().splitlines()]
        self.assertEqual([row["kind"] for row in live],
                         ["INGRESS_ACCEPTED", "DISPATCHED", "CONSUMED", "RESULT_BOUND", "EGRESS_EMITTED"])
        self.assertEqual({row["observed_at"] for row in live}, {f"hb-epoch:{SUPPLIED}"})
        self.assertEqual(result["execution_result"]["receipts"], live)
        self.assertNoUnmarkedClock()


class IngestByRole(ConsumingRoutes):
    """Row 4: a role that stamps time refuses an absent epoch; one that does not reads no clock."""

    def test_an_epoch_less_frame_is_refused_at_every_role(self):
        for service, payload in (
                (THIS.lower() + ".org-control", {"message_class": "ecosystem.communication",
                                                 "communication_id": "role-control", "subject": "s", "body": {}}),
                (THIS.lower() + ".boundary-diagnostic", {"probe": "ping"})):
            with self.subTest(service=service):
                frame = self.publish_inbound(service, payload, "role-" + service)
                reads = self.clock_reads()
                with self.assertRaises(self.K.SuppliedEpochRefused) as refused:
                    self.K.ingest_frame(self.root, frame, mesh_root=self.mesh)
                self.assertRefusal(refused.exception.refusal)
                self.assertEqual(self.clock_reads(), reads)
        self.assertNoLedger()
        self.assertFalse((self.root / "resident-runtime/control").exists())

    def test_roles_that_stamp_no_time_consume_a_supplied_frame_without_the_clock(self):
        for service, payload in (
                (THIS.lower() + ".org-control", {"message_class": "ecosystem.communication",
                                                 "communication_id": "role-control", "subject": "s", "body": {}}),
                (THIS.lower() + ".boundary-diagnostic", {"probe": "ping"})):
            with self.subTest(service=service):
                frame = self.publish_inbound(service, payload, "role-" + service, epoch=SUPPLIED)
                reads = self.clock_reads()
                result = self.K.ingest_frame(self.root, frame, mesh_root=self.mesh)
                self.assertEqual(result["status"], "CONSUMED")
                self.assertEqual(self.clock_reads(), reads)
                self.assertEqual(unmarked_clock_values(result), [])
        self.assertNoLedger()
        self.assertFalse((self.root / "resident-runtime/control").exists())

    def test_roles_that_stamp_time_refuse_an_absent_epoch_and_take_a_supplied_one(self):
        for service, payload in (
                (THIS.lower() + ".org-control", {"message_class": "ecosystem.monitor.request",
                                                 "communication_id": "role-monitor", "subject": "s", "body": {}}),
                (THIS.lower() + ".capability-discovery", {"operation": "LIST_CAPABILITIES"}),
                (THIS.lower() + ".intr-destination", diagnostic("role-intr"))):
            with self.subTest(service=service):
                frame = self.publish_inbound(service, payload, "stamped-" + service)
                reads = self.clock_reads()
                with self.assertRaises(ValueError) as refused:
                    self.K.ingest_frame(self.root, frame, mesh_root=self.mesh)
                self.assertRefusal(refused.exception.refusal)
                result = self.K.ingest_frame(self.root, frame, mesh_root=self.mesh, hb_epoch=SUPPLIED)
                self.assertEqual(result["status"], "CONSUMED")
                self.assertEqual(self.clock_reads(), reads)
                self.assertEqual(unmarked_clock_values(result), [])
                execution = result["execution_result"]
                if service.endswith(".org-control"):
                    status = execution["application_result"]["monitor_status"]
                    self.assertEqual(status["heartbeat_reference"]["epoch"], SUPPLIED)
                if service.endswith(".capability-discovery"):
                    self.assertEqual({row["observed_at"] for row in execution["receipts"]},
                                     {f"hb-epoch:{SUPPLIED}"})
        self.assertAllSupplied()


class HeartbeatMarkers(ConsumingRoutes):
    """SUPPLIED is derived_from_clock false with no sample; CLOCK is derived_from_clock true."""

    def test_a_supplied_epoch_is_marked_supplied_and_reads_no_clock(self):
        reads = self.clock_reads()
        reference = self.K.hb_reference(self.K.epoch_now_ns(SUPPLIED))
        packet = self.K.build_packet(origin_org=PEER, origin_service="p", destination_org=THIS,
                                     destination_service="s", payload={})
        frame = self.K.carrier_frame(packet, now_ns=self.K.epoch_now_ns(SUPPLIED))
        self.assertEqual(self.clock_reads(), reads)
        for value in (reference, frame["heartbeat_reference"]):
            self.assertEqual(value["epoch"], SUPPLIED)
            self.assertIs(value["derived_from_clock"], False)
            self.assertNotIn("sampled_unix_ns", value)
        self.assertEqual(self.K.frame_epoch(frame), SUPPLIED)

    def test_the_clock_path_is_marked_clock(self):
        reads = self.clock_reads()
        reference = self.K.hb_reference()
        self.assertEqual(self.clock_reads(), reads + 1)
        self.assertEqual(reference["epoch"], CLOCK_EPOCH)
        self.assertIs(reference["derived_from_clock"], True)
        self.assertIn("sampled_unix_ns", reference)
        packet = self.K.build_packet(origin_org=PEER, origin_service="p", destination_org=THIS,
                                     destination_service="s", payload={})
        self.assertIsNone(self.K.frame_epoch(self.K.carrier_frame(packet)))
        # A bare sample with no flag is legacy CLOCK, never SUPPLIED.
        self.assertIsNone(self.K.frame_epoch({"heartbeat_reference": {"epoch": SUPPLIED,
                                                                      "sampled_unix_ns": CLOCK_NS}}))


class SharedRuleProvenance(ConsumingRoutes):
    """The shared rule takes a reference only when it is marked supplied; writers never take a CARRIED one."""

    def setUp(self):
        super().setUp()
        self.repository = _load("marker_repo_emit", self.root, ".stegverse/transition-ledger/emit.py")
        self.organization = _load("marker_org_append", self.root, "resident-runtime/aggregate_repo_transition.py")

    def append_repository(self, epoch, transition_id="provenance"):
        return self.repository.append(transition_id, "TEST", "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                      {"n": 1}, "NONE", hb_epoch=epoch)

    def test_an_unmarked_or_clock_reference_is_refused(self):
        for reference in ({"epoch": SUPPLIED}, {"epoch": SUPPLIED, "derived_from_clock": True},
                          {"epoch": SUPPLIED, "derived_from_clock": None},
                          {"epoch": SUPPLIED, "derived_from_clock": "false"}):
            with self.subTest(reference=reference):
                refusal = self.K.writer_epoch_refusal(reference, retry_entrypoint="probe")
                self.assertRefusal(refusal, "HB_EPOCH_PROVENANCE_UNMARKED")
                with self.assertRaises(self.repository.RepoLedgerEpochRefused) as refused:
                    self.append_repository(reference)
                self.assertRefusal(refused.exception.refusal, "HB_EPOCH_PROVENANCE_UNMARKED")
        self.assertNoLedger()

    def test_a_reference_marked_supplied_is_taken_at_its_epoch(self):
        receipt = self.append_repository({"epoch": SUPPLIED, "derived_from_clock": False})
        self.assertEqual(receipt["hb_reference"]["epoch"], SUPPLIED)
        self.assertIs(receipt["hb_reference"]["derived_from_clock"], False)
        self.assertRefusal(self.K.writer_epoch_refusal({"epoch": "+33", "derived_from_clock": False},
                                                       retry_entrypoint="probe"), "HB_EPOCH_INVALID")

    def test_a_carried_reference_with_an_invented_head_is_refused_and_nothing_written(self):
        invented = {"epoch": SUPPLIED, "derived_from_clock": False, "source": "CARRIED:ORGANIZATION_LEDGER_HEAD",
                    "head_receipt_sha": "sha256:" + "0123456789abcdef" * 4}
        with self.assertRaises(self.repository.RepoLedgerEpochRefused) as refused:
            self.append_repository(invented)
        self.assertRefusal(refused.exception.refusal, "CARRIED_PROVENANCE_UNVERIFIED")
        source = None
        with mock.patch.dict(os.environ, {"STEGVERSE_REPO_LEDGER_ROOT": str(self.work / "source")}):
            source = self.append_repository(SUPPLIED, "carried-source")
        with self.assertRaises(self.organization.OrgLedgerEpochRefused) as refused:
            self.organization.append(source, "REPO_STATE_PROPAGATION", "sha256:" + "a" * 64,
                                     "sha256:" + "b" * 64, {}, "NONE", hb_epoch=invented)
        self.assertRefusal(refused.exception.refusal, "CARRIED_PROVENANCE_UNVERIFIED")
        self.assertNoLedger()

    def test_a_clock_provenance_source_receipt_is_refused_and_nothing_written(self):
        with mock.patch.dict(os.environ, {"STEGVERSE_REPO_LEDGER_ROOT": str(self.work / "source")}):
            supplied = self.append_repository(SUPPLIED, "clock-source")
        clock_reference = {"epoch": CLOCK_EPOCH, "progression_dependency": "OSCILLATOR_ONLY",
                           "authority_effect": "NONE", "derived_from_clock": True, "sampled_unix_ns": CLOCK_NS}
        legacy_reference = {"epoch": CLOCK_EPOCH, "progression_dependency": "OSCILLATOR_ONLY",
                            "authority_effect": "NONE"}
        for reference in (clock_reference, legacy_reference):
            with self.subTest(reference=reference):
                body = {key: value for key, value in supplied.items() if key != "receipt_sha256"}
                body["hb_reference"] = reference
                body["observed_at"] = CLOCK_ISO
                seeded = {**body, "receipt_sha256": self.repository.sha(body)}
                with self.assertRaises(self.organization.OrgLedgerEpochRefused) as refused:
                    self.organization.append(seeded, "REPO_STATE_PROPAGATION", "sha256:" + "a" * 64,
                                             "sha256:" + "b" * 64, {}, "NONE", hb_epoch=SUPPLIED)
                refusal = refused.exception.refusal
                self.assertRefusal(refusal, "SOURCE_RECEIPT_IS_CLOCK_PROVENANCE")
                self.assertIn("CARRIED:LEGACY_CLOCK_RECEIPT", refusal["required_evidence_or_repair"])
                self.assertIn("existing receipts are never mutated", refusal["required_evidence_or_repair"])
        self.assertFalse(self.org_ledger.exists())


class ClockMarkerSweep(ConsumingRoutes):
    """Row 6: with the clock fixed, every route runs; any clock value written carries its marker."""

    def test_every_written_clock_value_is_marked(self):
        inbound = [
            (THIS.lower() + ".intr-destination", diagnostic("sweep-intr")),
            (THIS.lower() + ".org-control", {"message_class": "ecosystem.monitor.request",
                                             "communication_id": "sweep-monitor", "subject": "s", "body": {}}),
            (THIS.lower() + ".org-control", {"message_class": "ecosystem.work.request",
                                             "communication_id": "sweep-work", "subject": "s", "body": {}}),
            (THIS.lower() + ".boundary-diagnostic", {"probe": "ping"}),
            (THIS.lower() + ".capability-discovery", {"operation": "LIST_CAPABILITIES"}),
        ]
        for index, (service, payload) in enumerate(inbound):
            self.publish_inbound(service, payload, f"sweep-{index}")
        self.publish_inbound(THIS.lower() + ".boundary-diagnostic", {"probe": "carried"}, "sweep-carried",
                             epoch=SUPPLIED)
        reads = self.clock_reads()
        self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        egress = _load("marker_egress", self.root, "resident-runtime/organization_egress_boundary.py")
        egress.emit(PEER, diagnostic("sweep-emit"),
                    standing={"mode": "ESTABLISH_GENESIS", "node_ref": "sweep", "predecessor": None},
                    capability="intr-destination", mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual(self.clock_reads(), reads)
        written = self.written()
        # The probe sees the clock: each fabricated inbound frame carries one, marked.
        self.assertGreaterEqual(sum(marked_clock_values(value) for _, value in written), len(inbound))
        for path, value in written:
            self.assertEqual(unmarked_clock_values(value), [], str(path))
            self.assertEqual(supplied_marked_wrongly(value), [], str(path))
        self.assertAllSupplied()

    def test_the_clock_is_fixed_and_counted_in_subprocesses(self):
        reads = self.clock_reads()
        completed = subprocess.run(
            [sys.executable, "-c", "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())"],
            capture_output=True, text=True, env=dict(os.environ), check=True)
        self.assertEqual(completed.stdout.strip(), CLOCK_ISO)
        self.assertEqual(self.clock_reads(), reads + 1)

    def test_the_probe_catches_an_unmarked_clock_value(self):
        self.assertEqual(unmarked_clock_values({"observed_at": CLOCK_ISO}), ["$.observed_at"])
        self.assertEqual(unmarked_clock_values({"hb_reference": {"epoch": CLOCK_EPOCH, "derived_from_clock": False}}),
                         ["$.hb_reference.epoch"])
        self.assertEqual(unmarked_clock_values({"epoch": CLOCK_EPOCH, "sampled_unix_ns": CLOCK_NS}), [])
        self.assertEqual(unmarked_clock_values({"epoch": CLOCK_EPOCH, "derived_from_clock": True}), [])


if __name__ == "__main__":
    unittest.main()
