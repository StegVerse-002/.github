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
import hashlib
import importlib.util
import inspect
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
            # Legacy CLOCK form: the kernel default is WU-B13 slice b's to mark.
            self.assertNotIn("derived_from_clock", reference)
            self.assertIn("sampled_unix_ns", reference)
        else:
            self.assertEqual(reference["epoch"], epoch)
            self.assertIs(reference["derived_from_clock"], False)
            self.assertNotIn("sampled_unix_ns", reference)
        return frame

    def unmarked_frame(self, service, payload, packet_id):
        """A frame whose heartbeat has neither a flag nor a sample: UNMARKED."""
        packet = self.K.build_packet(origin_org=PEER, origin_service="stegverse-org.org-control",
                                     destination_org=THIS, destination_service=service, payload=payload,
                                     packet_id=packet_id)
        frame = self.K.carrier_frame(packet, now_ns=self.K.epoch_now_ns(SUPPLIED))
        body = {key: value for key, value in frame.items() if key != "frame_sha256"}
        body["heartbeat_reference"] = {key: value for key, value in body["heartbeat_reference"].items()
                                       if key != "derived_from_clock"}
        return {**body, "frame_sha256": self.K.sha(body)}

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

    def test_a_valid_frame_stays_pending_in_a_cycle_without_an_epoch_and_is_consumed_at_4096(self):
        # §Q: the cycle lacks the epoch, not the frame, so the frame is never quarantined.
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("absent-consume"), "absent-consume")
        reads = self.clock_reads()
        for _ in range(2):
            pending, = self.K.consume_and_respond(self.root, mesh_root=self.mesh)
            self.assertEqual(pending["result"]["status"], "PENDING_EPOCH_NOT_SUPPLIED")
            self.assertRefusal(pending["result"]["refusal"], "HB_EPOCH_NOT_SUPPLIED")
            self.assertIsNone(pending["seen_marker"])
            self.assertFalse((self.root / "resident-runtime/federation/seen.d").exists())
            self.assertNoLedger()
        consumed, = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=str(SUPPLIED))
        self.assertEqual(consumed["result"]["status"], "CONSUMED")
        self.assertEqual(consumed["response_publication"]["frame"]["heartbeat_reference"]["epoch"], SUPPLIED)
        self.assertAllSupplied()
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED), [])
        self.assertEqual(self.clock_reads(), reads)
        self.assertNoUnmarkedClock()

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

    def test_a_clock_frame_lends_no_epoch_so_its_response_needs_the_callers(self):
        payload = {"message_class": "ecosystem.communication", "subject": "s", "body": {}}
        self.publish_inbound(THIS.lower() + ".org-control", {**payload, "communication_id": "clock-a"}, "clock-a")
        reads = self.clock_reads()
        # No caller epoch: no response can be stamped, so it stays pending, unseen.
        result, = self.K.consume_and_respond(self.root, mesh_root=self.mesh)
        self.assertEqual(result["result"]["status"], "PENDING_EPOCH_NOT_SUPPLIED")
        self.assertIsNone(result["seen_marker"])
        self.assertEqual([frame["destination_org"] for frame in self.frames()], [THIS])
        # §Q: 0 files, with no seen or quarantine marker and no intake.
        self.assertFalse((self.root / "resident-runtime/federation/seen.d").exists())
        self.assertFalse((self.root / "resident-runtime/control").exists())
        self.assertNoLedger()
        # With the cycle's epoch: the same frame is answered at that epoch, never at the clock's.
        result, = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual(result["result"]["status"], "CONSUMED")
        reference = result["response_publication"]["frame"]["heartbeat_reference"]
        self.assertEqual((reference["epoch"], reference["derived_from_clock"]), (SUPPLIED, False))
        self.assertEqual(self.clock_reads(), reads)
        self.assertNoUnmarkedClock()

    def test_the_response_frame_and_receipts_carry_the_supplied_epoch(self):
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("supplied-consume"), "supplied-consume",
                             epoch=SUPPLIED)
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
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("cycle-supplied"), "cycle-supplied",
                             epoch=SUPPLIED)
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
                                     "gateway-cycle", epoch=SUPPLIED)
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

    def test_the_gateway_acknowledges_a_refused_frame_blocked_so_it_is_not_redelivered(self):
        gateway = _load("marker_gateway_refused", self.root, "resident-runtime/federation_gateway_transport.py")
        clock_frame = self.unmarked_frame(THIS.lower() + ".intr-destination", diagnostic("gateway-unmarked"),
                                          "gateway-unmarked")
        submitted, acknowledged = [], []
        with mock.patch.object(gateway, "fetch_frame",
                               return_value={"state": "FRAME_AVAILABLE", "frame": clock_frame}), \
                mock.patch.object(gateway, "submit_frame",
                                  side_effect=lambda value: submitted.append(value) or {"state": "STORED"}), \
                mock.patch.object(gateway, "_json_request",
                                  side_effect=lambda method, path, body=None, headers=None:
                                  acknowledged.append(body) or {"state": "ACKNOWLEDGED"}):
            reads = self.clock_reads()
            result = gateway.resident_gateway_cycle(self.root, hb_epoch=str(SUPPLIED))
        self.assertEqual(self.clock_reads(), reads)
        self.assertEqual(result["state"], "REFUSED_QUARANTINED")
        self.assertEqual(result["failure_code"], "FRAME_REFUSED_QUARANTINED")
        self.assertEqual(result["refusal"]["failure_code"], "HB_EPOCH_PROVENANCE_UNMARKED")
        self.assertEqual(submitted, [])
        self.assertEqual([(value["state"], value["observed_at"]) for value in acknowledged],
                         [("BLOCKED", f"hb-epoch:{SUPPLIED}")])
        self.assertFalse((self.root / "resident-runtime/control").exists())
        self.assertNoLedger()


class RefusedFramesAreTerminal(ConsumingRoutes):
    """B-P36j: a refused frame is quarantined once and never blocks a later cycle."""

    def run_cycle(self):
        out = self.work / "latest-cycle.json"
        driver = (f"import sys, runpy; sys.argv={[str(self.root / 'resident-runtime/federation_cycle.py'), '--out', str(out)]!r}; "
                  f"runpy.run_path(sys.argv[0], run_name='__main__')")
        with mock.patch.dict(os.environ, {"STEGVERSE_HB_EPOCH": str(SUPPLIED)}):
            completed = subprocess.run([sys.executable, "-c", driver], capture_output=True, text=True,
                                       env=dict(os.environ), check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        return json.loads(out.read_text())

    def seen_markers(self):
        directory = self.root / "resident-runtime/federation/seen.d"
        return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))] if directory.is_dir() else []

    def test_a_mixed_batch_consumes_the_valid_frame_and_quarantines_the_refused_frame_once(self):
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("mixed-valid"), "mixed-valid",
                             epoch=SUPPLIED)
        self.K.publish_frame(self.unmarked_frame(THIS.lower() + ".intr-destination", diagnostic("mixed-unmarked"),
                                                 "mixed-unmarked"), root=self.mesh)
        reads = self.clock_reads()
        first = self.run_cycle()
        self.assertEqual((first["frames_seen"], first["frames_consumed"], first["frames_refused_quarantined"]),
                         (2, 1, 1))
        markers = self.seen_markers()
        quarantined = [marker for marker in markers if marker["status"] == "REFUSED"]
        self.assertEqual([marker["packet_id"] for marker in quarantined], ["mixed-unmarked"])
        marker = quarantined[0]
        self.assertRefusal(marker, "FRAME_REFUSED_QUARANTINED")
        self.assertEqual(marker["refused_failure_code"], "HB_EPOCH_PROVENANCE_UNMARKED")
        receipts = len(self.receipts())
        # The second cycle proceeds: the quarantined frame is not retried. A CLOCK
        # frame is consumed at the cycle's epoch (NARROW S1), never at the clock's.
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("later-valid"), "later-valid",
                             epoch=SUPPLIED)
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("later-clock"), "later-clock")
        self.assertEqual(self.clock_reads(), reads + 1)  # the fabricated CLOCK frame's own sample
        reads = self.clock_reads()
        second = self.run_cycle()
        self.assertEqual((second["frames_seen"], second["frames_consumed"], second["frames_refused_quarantined"]),
                         (2, 2, 0))
        self.assertEqual(len([m for m in self.seen_markers() if m["status"] == "REFUSED"]), 1)
        self.assertGreater(len(self.receipts()), receipts)
        self.assertEqual(self.clock_reads(), reads)
        self.assertAllSupplied()
        self.assertNoUnmarkedClock()

    def test_an_invalid_frame_is_quarantined_too(self):
        frame = self.publish_inbound(THIS.lower() + ".boundary-diagnostic", {"probe": "x"}, "invalid", epoch=SUPPLIED)
        path = next((self.mesh / "frames.d").glob("*.json"))
        path.write_text(json.dumps({**frame, "packet_base64": "not-base64!"}))
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh)
        self.assertEqual([row["result"]["status"] for row in results], ["REFUSED_QUARANTINED"])
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh), [])


class CarriedClaimsAreNeverStripped(ConsumingRoutes):
    """B-P36k: a self-asserted CARRIED heartbeat is refused at ingest on every route; nothing is written."""

    FORGED = "sha256:" + "f" * 64

    def carried_frame(self, service, payload, packet_id):
        packet = self.K.build_packet(
            origin_org=PEER, origin_service="stegverse-org.org-control", destination_org=THIS,
            destination_service=service, payload=payload,
            transition_reference="probe:" + packet_id, authority_effect="NONE", packet_id=packet_id)
        frame = self.K.carrier_frame(packet, now_ns=self.K.epoch_now_ns(SUPPLIED))
        body = {key: value for key, value in frame.items() if key != "frame_sha256"}
        body["heartbeat_reference"] = {**body["heartbeat_reference"], "source": "CARRIED:ORGANIZATION_LEDGER_HEAD",
                                       "head_receipt_sha": self.FORGED}
        frame = {**body, "frame_sha256": self.K.sha(body)}
        self.K.publish_frame(frame, root=self.mesh)
        return frame

    def files(self):
        return sorted(str(path) for path in self.work.rglob("*") if path.is_file()
                      and self.root not in path.parents and "site" not in path.parts
                      and path != self.clock_log and "frames.d" not in path.parts)

    def test_a_forged_head_is_refused_on_every_route_with_nothing_written(self):
        routes = (
            (THIS.lower() + ".org-control", {"message_class": "ecosystem.work.request",
                                             "communication_id": "forged-work", "subject": "s", "body": {}}),
            (THIS.lower() + ".boundary-diagnostic", {"probe": "forged"}),
            (THIS.lower() + ".intr-destination", diagnostic("forged-intr")),
            (THIS.lower() + ".capability-discovery", {"operation": "LIST_CAPABILITIES"}),
            (THIS.lower() + ".self-characterization", {"probe": "forged"}),
        )
        before = self.files()
        reads = self.clock_reads()
        for index, (service, payload) in enumerate(routes):
            with self.subTest(service=service):
                frame = self.carried_frame(service, payload, f"forged-{index}")
                for caller in (None, SUPPLIED):
                    with self.assertRaises(self.K.SuppliedEpochRefused) as refused:
                        self.K.ingest_frame(self.root, frame, mesh_root=self.mesh, hb_epoch=caller)
                    self.assertRefusal(refused.exception.refusal, "CARRIED_PROVENANCE_UNVERIFIED")
        addressed = self.K.consume_addressed_frames(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual({row["result"]["refusal"]["failure_code"] for row in addressed},
                         {"CARRIED_PROVENANCE_UNVERIFIED"})
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / "resident-runtime/control").exists())
        self.assertFalse((self.root / "resident-runtime/federation").exists())
        self.assertFalse(self.self_char.exists())
        self.assertNoLedger()
        # The cycle writes only the B-P36j quarantine markers.
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual({row["result"]["status"] for row in results}, {"REFUSED_QUARANTINED"})
        written = sorted(path.relative_to(self.root).parts[:3] for path in
                         (self.root / "resident-runtime").rglob("*.json") if "seen.d" in path.parts)
        self.assertEqual(len(written), len(routes))
        self.assertFalse((self.root / "resident-runtime/control").exists())
        self.assertNoLedger()
        self.assertEqual(self.clock_reads(), reads)

    def test_the_gateway_refuses_a_forged_head_without_ingesting(self):
        gateway = _load("marker_gateway_forged", self.root, "resident-runtime/federation_gateway_transport.py")
        frame = self.carried_frame(THIS.lower() + ".org-control",
                                   {"message_class": "ecosystem.work.request", "communication_id": "g",
                                    "subject": "s", "body": {}}, "forged-gateway")
        acknowledged = []
        with mock.patch.object(gateway, "fetch_frame", return_value={"state": "FRAME_AVAILABLE", "frame": frame}), \
                mock.patch.object(gateway, "submit_frame", side_effect=AssertionError("nothing is submitted")), \
                mock.patch.object(gateway, "_json_request",
                                  side_effect=lambda method, path, body=None, headers=None:
                                  acknowledged.append(body) or {"state": "ACKNOWLEDGED"}):
            result = gateway.resident_gateway_cycle(self.root, hb_epoch=SUPPLIED)
        self.assertEqual(result["refusal"]["failure_code"], "CARRIED_PROVENANCE_UNVERIFIED")
        self.assertEqual([value["state"] for value in acknowledged], ["BLOCKED"])
        self.assertFalse((self.root / "resident-runtime/control").exists())
        self.assertNoLedger()


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
        self.assertRefusal(refused.exception.refusal, "HB_EPOCH_NOT_SUPPLIED")
        self.assertFalse(self.self_char.exists())
        self.assertEqual(self.clock_reads(), reads)

    def test_the_live_receipts_carry_the_supplied_epoch(self):
        frame = self.publish_inbound(THIS.lower() + ".self-characterization", {"probe": "self"}, "self-supplied",
                                     epoch=SUPPLIED)
        reads = self.clock_reads()
        result = self.K.ingest_frame(self.root, frame, mesh_root=self.mesh)
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

    def test_a_clock_frame_is_consumed_at_roles_stamping_no_time_and_lends_no_epoch(self):
        # NARROW S1: CLOCK frames from the WU-B13-scoped publishers are consumed, lending no epoch.
        for service, payload in (
                (THIS.lower() + ".org-control", {"message_class": "ecosystem.communication",
                                                 "communication_id": "role-control", "subject": "s", "body": {}}),
                (THIS.lower() + ".boundary-diagnostic", {"probe": "ping"})):
            with self.subTest(service=service):
                frame = self.publish_inbound(service, payload, "role-" + service)
                self.assertIsNone(self.K.frame_epoch(frame))
                reads = self.clock_reads()
                for caller in (None, SUPPLIED):
                    result = self.K.ingest_frame(self.root, frame, mesh_root=self.mesh, hb_epoch=caller)
                    self.assertEqual(result["status"], "CONSUMED")
                self.assertEqual(self.clock_reads(), reads)
        self.assertNoLedger()
        self.assertFalse((self.root / "resident-runtime/control").exists())

    def test_an_unmarked_frame_is_refused_at_every_role(self):
        for index, (service, payload) in enumerate((
                (THIS.lower() + ".org-control", {"message_class": "ecosystem.communication",
                                                 "communication_id": "unmarked", "subject": "s", "body": {}}),
                (THIS.lower() + ".boundary-diagnostic", {"probe": "ping"}),
                (THIS.lower() + ".intr-destination", diagnostic("unmarked-intr")))):
            with self.subTest(service=service):
                frame = self.unmarked_frame(service, payload, f"unmarked-{index}")
                reads = self.clock_reads()
                for caller in (None, SUPPLIED):
                    with self.assertRaises(self.K.SuppliedEpochRefused) as refused:
                        self.K.ingest_frame(self.root, frame, mesh_root=self.mesh, hb_epoch=caller)
                    self.assertRefusal(refused.exception.refusal, "HB_EPOCH_PROVENANCE_UNMARKED")
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

    def test_roles_that_stamp_time_refuse_a_clock_frame_with_no_caller_epoch_and_take_a_supplied_one(self):
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
                self.assertRefusal(refused.exception.refusal, "HB_EPOCH_NOT_SUPPLIED")
                frame = self.publish_inbound(service, payload, "supplied-" + service, epoch=SUPPLIED)
                result = self.K.ingest_frame(self.root, frame, mesh_root=self.mesh)
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


class ExplicitEpochAgainstTheFrame(ConsumingRoutes):
    """B-P36l: an explicit epoch is judged on its own, and never silently loses to the frame's."""

    def test_an_invalid_explicit_epoch_is_refused_whatever_the_frame_carries(self):
        frame = self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("explicit-invalid"),
                                     "explicit-invalid", epoch=SUPPLIED)
        for explicit in ("abc", "+33", 31, True, ""):
            with self.subTest(explicit=explicit):
                with self.assertRaises(self.K.SuppliedEpochRefused) as refused:
                    self.K.ingest_frame(self.root, frame, mesh_root=self.mesh, hb_epoch=explicit)
                self.assertRefusal(refused.exception.refusal, "HB_EPOCH_INVALID")
        self.assertNoLedger()

    def test_an_explicit_epoch_that_differs_from_the_frames_is_a_conflict_and_nothing_is_written(self):
        frame = self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("explicit-conflict"),
                                     "explicit-conflict", epoch=39)
        reads = self.clock_reads()
        for explicit in (SUPPLIED, str(SUPPLIED)):
            with self.subTest(explicit=explicit):
                with self.assertRaises(self.K.SuppliedEpochRefused) as refused:
                    self.K.ingest_frame(self.root, frame, mesh_root=self.mesh, hb_epoch=explicit)
                self.assertRefusal(refused.exception.refusal, "HB_EPOCH_CONFLICT")
        self.assertNoLedger()
        self.assertEqual(self.clock_reads(), reads)

    def test_exactly_one_epoch_present_is_the_supplied_one(self):
        agreeing = self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("explicit-agree"),
                                        "explicit-agree", epoch=SUPPLIED)
        self.assertEqual(self.K.consuming_epoch(agreeing, SUPPLIED), SUPPLIED)
        self.assertEqual(self.K.consuming_epoch(agreeing), SUPPLIED)
        clock = self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("explicit-clock"),
                                     "explicit-clock")
        self.assertEqual(self.K.consuming_epoch(clock, SUPPLIED), SUPPLIED)
        self.assertIsNone(self.K.consuming_epoch(clock))
        result = self.K.ingest_frame(self.root, clock, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual(result["status"], "CONSUMED")
        self.assertAllSupplied()
        # A cycle's epoch is a fallback, not an explicit one: it never conflicts with a frame's.
        self.assertEqual(self.K.consuming_epoch(agreeing, 39, explicit=False), SUPPLIED)


class MalformedClockFrames(ConsumingRoutes):
    """F-S1a: a CLOCK frame whose own epoch is malformed is quarantined, never consumed or raised."""

    def malformed_clock_frame(self, service, payload, packet_id, epoch):
        packet = self.K.build_packet(origin_org=PEER, origin_service="stegverse-org.org-control",
                                     destination_org=THIS, destination_service=service, payload=payload,
                                     packet_id=packet_id)
        frame = self.K.carrier_frame(packet, now_ns=self.K.epoch_now_ns(SUPPLIED))
        body = {key: value for key, value in frame.items() if key != "frame_sha256"}
        body["heartbeat_reference"] = {**body["heartbeat_reference"], "epoch": epoch, "derived_from_clock": True}
        frame = {**body, "frame_sha256": self.K.sha(body)}
        self.K.publish_frame(frame, root=self.mesh)
        return frame

    def test_a_malformed_clock_frame_is_quarantined_by_the_cycle(self):
        for index, epoch in enumerate(("abc", 7, None, [4096])):
            self.malformed_clock_frame(THIS.lower() + ".boundary-diagnostic", {"probe": index},
                                       f"malformed-{index}", epoch)
        reads = self.clock_reads()
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual([row["result"]["status"] for row in results], ["REFUSED_QUARANTINED"] * 4)
        self.assertEqual({row["result"]["refusal"]["failure_code"] for row in results},
                         {"HB_EPOCH_INVALID", "HB_EPOCH_NOT_SUPPLIED"})
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED), [])
        self.assertEqual(self.clock_reads(), reads)
        self.assertNoLedger()


class BadFrames(ConsumingRoutes):
    """Writers of broken frames, offered ahead of the valid one."""

    def write_first(self, name, frame):
        # "0-" sorts before every hex frame name, so these are offered before the valid one.
        directory = self.mesh / "frames.d"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ("0-" + name + ".json")).write_text(json.dumps(frame))

    def reframed(self, frame, **heartbeat):
        body = {key: value for key, value in frame.items() if key != "frame_sha256"}
        body["heartbeat_reference"] = {**body["heartbeat_reference"], **heartbeat}
        return {**body, "frame_sha256": self.K.sha(body)}

    def supplied_frame(self, service, payload, packet_id):
        packet = self.K.build_packet(origin_org=PEER, origin_service="stegverse-org.org-control",
                                     destination_org=THIS, destination_service=service, payload=payload,
                                     packet_id=packet_id)
        return self.K.carrier_frame(packet, now_ns=self.K.epoch_now_ns(SUPPLIED))


class OneBadFrameNeverStopsTheCycle(BadFrames):
    """B-P36o: any error ingesting one frame is that frame's six-field refusal and quarantine."""

    maxDiff = None

    def test_a_mixed_batch_quarantines_each_bad_frame_and_ledgers_the_valid_one(self):
        intr = THIS.lower() + ".intr-destination"
        base = self.supplied_frame(intr, diagnostic("bad-generation"), "bad-generation")
        self.write_first("a-generation", self.reframed(base, generation=SUPPLIED + 1))
        base = self.supplied_frame(intr, diagnostic("bad-id"), "bad-id")
        self.write_first("b-heartbeat-id", self.reframed(base, heartbeat_id="HB:1"))
        base = self.supplied_frame(intr, diagnostic("bad-frame-sha"), "bad-frame-sha")
        self.write_first("c-frame-sha", {**base, "frame_sha256": "sha256:" + "0" * 64})
        base = self.supplied_frame(intr, diagnostic("bad-packet-sha"), "bad-packet-sha")
        body = {key: value for key, value in base.items() if key != "frame_sha256"}
        body["packet_sha256"] = "sha256:" + "1" * 64
        self.write_first("d-packet-sha", {**body, "frame_sha256": self.K.sha(body)})
        self.write_first("e-adapter", self.supplied_frame(intr, {"manifest": {"probe": True}}, "bad-adapter"))
        self.write_first("f-epoch", self.reframed(self.supplied_frame(intr, diagnostic("bad-epoch"), "bad-epoch"),
                                                  epoch="abc"))
        self.publish_inbound(intr, diagnostic("good"), "good", epoch=SUPPLIED)
        reads = self.clock_reads()
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        codes = {row["result"].get("packet_id") or row["result"]["packet"]["packet_id"]: (row["result"]["status"],
                                                  (row["result"].get("refusal") or {}).get("failure_code"))
                 for row in results}
        self.assertEqual(codes, {
            "bad-generation": ("REFUSED_QUARANTINED", "HB_REFERENCE_INVALID"),
            "bad-id": ("REFUSED_QUARANTINED", "HB_REFERENCE_INVALID"),
            "bad-frame-sha": ("REFUSED_QUARANTINED", "FRAME_INTEGRITY_INVALID"),
            "bad-packet-sha": ("REFUSED_QUARANTINED", "FRAME_INTEGRITY_INVALID"),
            "bad-adapter": ("REFUSED_QUARANTINED", "FRAME_INGEST_FAILED"),
            "bad-epoch": ("REFUSED_QUARANTINED", "HB_EPOCH_INVALID"),
            "good": ("CONSUMED", None),
        })
        adapter = next(row for row in results if row["result"].get("packet_id") == "bad-adapter")
        self.assertEqual(adapter["result"]["refusal"]["failed_predicate"], "ValueError")
        for row in results:
            if row["result"]["status"] == "REFUSED_QUARANTINED":
                self.assertRefusal(row["result"]["refusal"], row["result"]["refusal"]["failure_code"])
        # Only the valid frame is ledgered, all at 4096, with no clock read.
        repository = [r for r in self.receipts() if r["schema"] == "stegverse.repo-transition-receipt/v1"]
        self.assertEqual({r["evidence"]["communication_id"] for r in repository}, {"good"})
        self.assertEqual(self.clock_reads(), reads)
        self.assertAllSupplied()
        # A second cycle offers none of the bad frames again.
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED), [])


class WrongTypedFields(BadFrames):
    """F-TYPE: the per-frame guard is total. A wrong-typed field is that frame's refusal, before or after a valid one."""

    def write_last(self, name, frame):
        # "z-" sorts after every hex frame name, so these are offered after the valid one.
        directory = self.mesh / "frames.d"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ("z-" + name + ".json")).write_text(json.dumps(frame))

    def retyped(self, field, value, packet_id):
        base = self.supplied_frame(THIS.lower() + ".intr-destination", diagnostic(packet_id), packet_id)
        body = {key: item for key, item in base.items() if key != "frame_sha256"}
        body[field] = value
        # Re-hashed, so the carrier hash holds and the wrong type reaches the decode.
        return {**body, "frame_sha256": self.K.sha(body)}

    def test_wrong_typed_fields_are_quarantined_and_the_valid_frame_is_ledgered(self):
        wrong = {"int": 123, "null": None, "list": ["a"], "dict": {"a": 1}}
        for index, (label, value) in enumerate(wrong.items()):
            write = self.write_first if index % 2 == 0 else self.write_last
            write("b64-" + label, self.retyped("packet_base64", value, "b64-" + label))
        self.write_last("hb-list", self.retyped("heartbeat_reference", [SUPPLIED], "hb-list"))
        self.write_first("sha-int", self.retyped("packet_sha256", 123, "sha-int"))
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("typed-good"), "typed-good",
                             epoch=SUPPLIED)
        reads = self.clock_reads()
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        rows = {row["result"].get("packet_id") or row["result"]["packet"]["packet_id"]: row["result"]
                for row in results}
        self.assertEqual(rows.pop("typed-good")["status"], "CONSUMED")
        self.assertEqual(set(rows), {"b64-int", "b64-null", "b64-list", "b64-dict", "hb-list", "sha-int"})
        for packet_id, result in rows.items():
            with self.subTest(frame=packet_id):
                self.assertEqual(result["status"], "REFUSED_QUARANTINED")
                self.assertRefusal(result["refusal"], result["refusal"]["failure_code"])
        for label in wrong:
            refusal = rows["b64-" + label]["refusal"]
            self.assertEqual(refusal["failure_code"], "FRAME_INGEST_FAILED")
            self.assertIn(refusal["failed_predicate"], {"AttributeError", "TypeError"})
        repository = [r for r in self.receipts() if r["schema"] == "stegverse.repo-transition-receipt/v1"]
        self.assertEqual({r["evidence"]["communication_id"] for r in repository}, {"typed-good"})
        self.assertAllSupplied()
        self.assertEqual(self.clock_reads(), reads)
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED), [])

    def test_the_gateway_blocks_a_wrong_typed_frame(self):
        gateway = _load("marker_gateway_typed", self.root, "resident-runtime/federation_gateway_transport.py")
        acknowledged = []
        with mock.patch.object(gateway, "fetch_frame", return_value={
                    "state": "FRAME_AVAILABLE", "frame": self.retyped("packet_base64", 123, "gw-typed")}), \
                mock.patch.object(gateway, "_json_request", side_effect=lambda method, path, body=None, headers=None:
                                  acknowledged.append(body) or {"state": "ACKNOWLEDGED"}):
            result = gateway.resident_gateway_cycle(self.root, hb_epoch=SUPPLIED)
        self.assertEqual(result["state"], "REFUSED_QUARANTINED")
        self.assertEqual(result["refusal"]["failure_code"], "FRAME_INGEST_FAILED")
        self.assertEqual([value["state"] for value in acknowledged], ["BLOCKED"])
        self.assertNoLedger()


class OwnStateWriteFaults(ConsumingRoutes):
    """F-TRANSIENT-RT: a fault writing this repository's own state leaves the frame pending, never terminal."""

    def failing_replace(self, target, error):
        real = os.replace

        def replace(source, destination, *args, **kwargs):
            if target(Path(destination)):
                raise error
            return real(source, destination, *args, **kwargs)
        return mock.patch.object(os, "replace", replace)

    def chain(self, root):
        return sorted(path.name for path in root.glob("receipts/*.json")) if root.exists() else []

    def assertPendingNoMarker(self, results, predicate):
        result, = results
        self.assertEqual(result["result"]["status"], "PENDING_DISPATCH_IO_FAILED")
        refusal = result["result"]["refusal"]
        self.assertRefusal(refusal, "FRAME_DISPATCH_IO_FAILED")
        self.assertIs(refusal["terminal"], False)
        self.assertEqual(refusal["failed_predicate"], predicate)
        self.assertIsNone(result["seen_marker"])
        self.assertFalse((self.root / "resident-runtime/federation/seen.d").exists())

    def assertConsumedOnce(self):
        consumed, = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual(consumed["result"]["status"], "CONSUMED")
        self.assertEqual(len(self.chain(self.repo_ledger)), 1)
        self.assertEqual(len(self.chain(self.org_ledger)), 1)
        organization, = [r for r in self.receipts() if r["schema"] != "stegverse.repo-transition-receipt/v1"]
        repository, = [r for r in self.receipts() if r["schema"] == "stegverse.repo-transition-receipt/v1"]
        self.assertEqual(organization["repo_receipt_sha256"], repository["receipt_sha256"])
        self.assertAllSupplied()
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED), [])

    def publish(self, packet_id):
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic(packet_id), packet_id, epoch=SUPPLIED)

    def test_an_oserror_on_the_repository_ledger_write_leaves_the_frame_pending(self):
        self.publish("io-repo")
        reads = self.clock_reads()
        with self.failing_replace(lambda path: self.repo_ledger in path.parents and path.parent.name == "receipts",
                                  OSError(28, "No space left on device")):
            results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertPendingNoMarker(results, "OSError")
        self.assertEqual(self.chain(self.repo_ledger), [])
        self.assertEqual(self.chain(self.org_ledger), [])
        self.assertConsumedOnce()
        self.assertEqual(self.clock_reads(), reads)

    def test_an_oserror_on_the_organization_head_leaves_no_orphan_and_lands_once(self):
        self.publish("io-org-head")
        with self.failing_replace(lambda path: path == self.org_ledger / "HEAD.json", OSError(5, "I/O error")):
            results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertPendingNoMarker(results, "OSError")
        self.assertEqual(len(self.chain(self.repo_ledger)), 1)
        # The organization receipt written before HEAD failed is rolled back: no orphan.
        self.assertEqual(self.chain(self.org_ledger), [])
        self.assertConsumedOnce()

    def test_a_lost_comparison_on_each_append_leaves_the_frame_pending(self):
        self.publish("lost-comparison")
        with self.failing_replace(lambda path: path.name == "HEAD.json"
                                  and (self.repo_ledger in path.parents or self.org_ledger in path.parents),
                                  RuntimeError("ledger_append_lost_comparison")):
            results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertPendingNoMarker(results, "LEDGER_APPEND_LOST_COMPARISON")
        self.assertEqual(self.chain(self.repo_ledger), [])
        self.assertConsumedOnce()

    def test_exhausted_contention_is_the_writers_dedicated_class_not_a_system_exit(self):
        emit = _load("marker_emit_losing", self.root, ".stegverse/transition-ledger/emit.py")

        class LosingStore:
            attempts = 0
            def initialize(self): pass
            def get(self, key): return None
            def locator(self, key): return key
            def append_transaction(self, *args, **kwargs):
                LosingStore.attempts += 1
                return False
        with self.assertRaises(emit.ledger_store.LedgerWriteFailed) as raised:
            emit.append("t", "C", "a", "b", {}, hb_epoch=SUPPLIED, store=LosingStore())
        self.assertEqual(LosingStore.attempts, 128)
        self.assertEqual(raised.exception.failed_predicate, "LEDGER_APPEND_LOST_COMPARISON")
        self.assertTrue(self.K.own_state_fault(raised.exception))
        refusal = self.K.frame_failure_refusal(raised.exception)
        self.assertEqual(refusal["failure_code"], "FRAME_DISPATCH_IO_FAILED")
        self.assertIs(refusal["frame_left_pending"], True)

    def test_a_valid_frame_after_a_faulted_one_is_still_consumed(self):
        self.publish_inbound(THIS.lower() + ".org-control",
                             {"message_class": "ecosystem.communication", "communication_id": "after-io",
                              "subject": "s", "body": {}}, "after-io", epoch=SUPPLIED)
        self.publish("io-first")
        with self.failing_replace(lambda path: self.repo_ledger in path.parents, OSError(28, "full")):
            results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        statuses = {row["result"].get("packet_id") or row["result"]["packet"]["packet_id"]: row["result"]["status"]
                    for row in results}
        self.assertEqual(statuses, {"io-first": "PENDING_DISPATCH_IO_FAILED", "after-io": "CONSUMED"})
        self.assertConsumedOnce()

    def test_the_gateway_leaves_a_faulted_frame_unacknowledged(self):
        gateway = _load("marker_gateway_io", self.root, "resident-runtime/federation_gateway_transport.py")
        frame = self.K.carrier_frame(self.K.build_packet(
            origin_org=PEER, origin_service="stegverse-org.org-control", destination_org=THIS,
            destination_service=THIS.lower() + ".intr-destination", payload=diagnostic("gw-io"),
            packet_id="gw-io"), now_ns=self.K.epoch_now_ns(SUPPLIED))
        acknowledged = []
        patches = (mock.patch.object(gateway, "fetch_frame", return_value={"state": "FRAME_AVAILABLE", "frame": frame}),
                   mock.patch.object(gateway, "submit_frame", return_value={"state": "STORED"}),
                   mock.patch.object(gateway, "_json_request", side_effect=lambda method, path, body=None, headers=None:
                                     acknowledged.append(body) or {"state": "ACKNOWLEDGED"}))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        with self.failing_replace(lambda path: self.repo_ledger in path.parents, OSError(28, "full")):
            result = gateway.resident_gateway_cycle(self.root, hb_epoch=SUPPLIED)
        self.assertEqual(result["state"], "PENDING_DISPATCH_IO_FAILED")
        self.assertIs(result["refusal"]["terminal"], False)
        self.assertEqual(acknowledged, [])
        self.assertEqual(self.chain(self.repo_ledger), [])
        result = gateway.resident_gateway_cycle(self.root, hb_epoch=SUPPLIED)
        self.assertEqual(result["state"], "CONSUMED")
        self.assertEqual([value["state"] for value in acknowledged], ["CONSUMED"])
        self.assertEqual(len(self.chain(self.repo_ledger)), 1)
        self.assertEqual(len(self.chain(self.org_ledger)), 1)


class EcosystemControlStampsTheSuppliedEpoch(ConsumingRoutes):
    """EPOCH_FREE is not provable for ecosystem_control: every route that stamps takes the supplied epoch."""

    def run_control(self, *argv):
        completed = subprocess.run([sys.executable, str(self.root / "resident-runtime/ecosystem_control.py"), *argv],
                                   capture_output=True, text=True, env=dict(os.environ), check=False)
        self.assertNotIn("Traceback", completed.stderr)
        return completed

    def test_status_and_send_refuse_without_an_epoch_and_write_nothing(self):
        reads = self.clock_reads()
        for argv in (("status",), ("send-message", "--subject", "s", "--body-json", "{}"),
                     ("send-monitor", "--subject", "s", "--body-json", "{}"),
                     ("send-work", "--subject", "s", "--body-json", "{}"),
                     ("--hb-epoch", "abc", "status")):
            with self.subTest(argv=argv):
                completed = self.run_control(*argv)
                self.assertEqual(completed.returncode, 1)
                refusal = json.loads(completed.stdout)
                self.assertRefusal(refusal, "HB_EPOCH_INVALID" if "abc" in argv else "HB_EPOCH_NOT_SUPPLIED")
        self.assertEqual(self.frames(), [])
        self.assertEqual(self.clock_reads(), reads)

    def test_status_and_send_stamp_the_supplied_epoch_with_no_clock(self):
        reads = self.clock_reads()
        completed = self.run_control("--hb-epoch", str(SUPPLIED), "status")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        reference = json.loads(completed.stdout)["heartbeat_reference"]
        self.assertEqual(reference["epoch"], SUPPLIED)
        self.assertIs(reference["derived_from_clock"], False)
        self.assertNotIn("sampled_unix_ns", reference)
        completed = self.run_control("--hb-epoch", str(SUPPLIED), "send-message", "--subject", "s", "--body-json", "{}",
                                     "--communication-id", "control-4096")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        frames = self.frames()
        self.assertTrue(frames)
        for frame in frames:
            self.assertEqual(frame["heartbeat_reference"]["epoch"], SUPPLIED)
            self.assertIs(frame["heartbeat_reference"]["derived_from_clock"], False)
            self.assertNotIn("sampled_unix_ns", frame["heartbeat_reference"])
        # collect only reads, and takes no epoch.
        completed = self.run_control("collect", "--communication-id", "control-4096")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.clock_reads(), reads)
        self.assertNoUnmarkedClock()


class MalformedFrameFiles(ConsumingRoutes):
    """F-SCAN: a file in frames.d that is not a frame is quarantined by name; the scan goes on."""

    def test_malformed_files_before_a_valid_frame_never_block_the_cycle(self):
        directory = self.mesh / "frames.d"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "0-a-not-json.json").write_text("{not json")
        (directory / "0-b-array.json").write_text("[1,2,3]")
        (directory / "0-c-string.json").write_text('"frame"')
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("after-malformed"), "after-malformed",
                             epoch=SUPPLIED)
        reads = self.clock_reads()
        addressed = self.K.consume_addressed_frames(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertEqual([row["result"]["status"] for row in addressed][:3], ["REFUSED"] * 3)
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        by_name = {Path(row["path"]).name: row["result"] for row in results}
        for name in ("0-a-not-json.json", "0-b-array.json", "0-c-string.json"):
            self.assertEqual(by_name[name]["status"], "REFUSED_QUARANTINED", name)
            self.assertRefusal(by_name[name]["refusal"], "FRAME_INGEST_FAILED")
        self.assertEqual(by_name["0-a-not-json.json"]["refusal"]["failed_predicate"], "JSONDecodeError")
        self.assertEqual(by_name["0-b-array.json"]["refusal"]["failed_predicate"], "ValueError")
        valid = [row for name, row in by_name.items() if not name.startswith("0-")]
        self.assertEqual([row["status"] for row in valid], ["CONSUMED"])
        repository = [r for r in self.receipts() if r["schema"] == "stegverse.repo-transition-receipt/v1"]
        self.assertEqual({r["evidence"]["communication_id"] for r in repository}, {"after-malformed"})
        self.assertEqual(self.clock_reads(), reads)
        self.assertAllSupplied()
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED), [])

    def test_each_kind_of_corrupt_file_is_quarantined_by_name_and_the_valid_frame_is_ledgered(self):
        # B-P36p: a read error, non-UTF-8, non-JSON and an oversized file, each ahead of a valid frame.
        directory = self.mesh / "frames.d"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "0-a-read-error.json").mkdir()
        (directory / "0-b-not-utf8.json").write_bytes(b'{"destination_org": "\xff\xfe"}')
        (directory / "0-c-not-json.json").write_text("{not json")
        (directory / "0-d-oversized.json").write_text("{" + " " * self.K.FRAME_FILE_MAX_BYTES + "}")
        self.publish_inbound(THIS.lower() + ".intr-destination", diagnostic("after-corrupt"), "after-corrupt",
                             epoch=SUPPLIED)
        reads = self.clock_reads()
        results = self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        by_name = {Path(row["path"]).name: row for row in results}
        for name, predicate in (("0-a-read-error.json", "IsADirectoryError"),
                                ("0-b-not-utf8.json", "UnicodeDecodeError"),
                                ("0-c-not-json.json", "JSONDecodeError"),
                                ("0-d-oversized.json", "ValueError")):
            with self.subTest(file=name):
                row = by_name[name]
                self.assertEqual(row["result"]["status"], "REFUSED_QUARANTINED")
                self.assertRefusal(row["result"]["refusal"], "FRAME_INGEST_FAILED")
                self.assertEqual(row["result"]["refusal"]["failed_predicate"], predicate)
                marker = json.loads(Path(row["seen_marker"]).read_text())
                self.assertEqual((marker["frame_name"], marker["failure_code"]), (name, "FRAME_REFUSED_QUARANTINED"))
        self.assertIn("exceeds_max_bytes", by_name["0-d-oversized.json"]["result"]["refusal"]["detail"])
        valid = [row["result"] for name, row in by_name.items() if not name.startswith("0-")]
        self.assertEqual([row["status"] for row in valid], ["CONSUMED"])
        repository = [r for r in self.receipts() if r["schema"] == "stegverse.repo-transition-receipt/v1"]
        self.assertEqual({r["evidence"]["communication_id"] for r in repository}, {"after-corrupt"})
        self.assertEqual(self.clock_reads(), reads)
        self.assertEqual(self.K.consume_and_respond(self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED), [])

    def test_collecting_responses_skips_a_malformed_file(self):
        directory = self.mesh / "frames.d"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "0-not-json.json").write_text("{not json")
        self.assertEqual(self.K.collect_ecosystem_responses(THIS, "x", mesh_root=self.mesh)["response_count"], 0)


class SeededLegacySource(ConsumingRoutes):
    """O-1 ordering: a frame never leaves when its receipt pair would be refused."""

    def setUp(self):
        super().setUp()
        self.egress = _load("marker_egress_seeded", self.root, "resident-runtime/organization_egress_boundary.py")

    def seed_legacy(self, transition_id, transition_class):
        legacy = lambda epoch: {"epoch": epoch, "progression_dependency": "OSCILLATOR_ONLY", "authority_effect": "NONE"}
        with mock.patch.object(self.egress.repository_ledger, "_heartbeat", legacy):
            self.egress.repository_ledger.append(transition_id, transition_class, "sha256:" + "a" * 64,
                                                 "sha256:" + "b" * 64, {"seeded": True}, "NONE", hb_epoch=40)

    def packet_id(self, payload):
        origin = self.egress.this_organization(self.root)
        resolved = self.egress.resolve_destination(PEER, capability="intr-destination", root=self.root)
        return self.K.build_packet(
            origin_org=origin, origin_service=self.egress.peer_capability_service(origin, "intr-destination"),
            destination_org=resolved["destination_organization"], destination_service=resolved["destination_service"],
            payload=dict(payload), transition_reference="ecosystem.transition.interorg.v1",
            authority_effect="NONE")["packet_id"]

    def test_emit_refuses_before_publishing_when_the_recorded_source_is_legacy(self):
        payload = diagnostic("seeded-emit")
        self.seed_legacy(self.egress.EMITTED_CLASS + ":" + self.packet_id(payload), self.egress.EMITTED_CLASS)
        with self.assertRaises(ValueError) as refused:
            self.egress.emit(PEER, payload, standing={"mode": "ESTABLISH_GENESIS", "node_ref": "s", "predecessor": None},
                             capability="intr-destination", root=self.root, mesh_root=self.mesh, hb_epoch=SUPPLIED)
        self.assertRefusal(refused.exception.refusal, "SOURCE_RECEIPT_IS_CLOCK_PROVENANCE")
        self.assertEqual(self.frames(), [])
        self.assertFalse(self.org_ledger.exists())


class HeartbeatMarkers(ConsumingRoutes):
    """SUPPLIED is derived_from_clock false with no sample; the clock default keeps its legacy form."""

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

    def test_the_clock_default_keeps_its_legacy_clock_form_and_is_never_taken_as_supplied(self):
        # CLOCK_MARKER_LEGACY_FORM_IN_KERNEL_DEFAULT: marking this branch is WU-B13 slice b's.
        reads = self.clock_reads()
        reference = self.K.hb_reference()
        self.assertEqual(self.clock_reads(), reads + 1)
        self.assertEqual(reference["epoch"], CLOCK_EPOCH)
        self.assertNotIn("derived_from_clock", reference)
        self.assertIn("sampled_unix_ns", reference)
        self.assertRefusal(self.K.writer_epoch_refusal(reference, retry_entrypoint="probe"),
                           "HB_EPOCH_INVALID")
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
        for reference, code in (({"epoch": SUPPLIED}, "HB_EPOCH_PROVENANCE_UNMARKED"),
                                ({"epoch": SUPPLIED, "derived_from_clock": True}, "HB_EPOCH_INVALID"),
                                ({"epoch": SUPPLIED, "derived_from_clock": None}, "HB_EPOCH_INVALID"),
                                ({"epoch": SUPPLIED, "derived_from_clock": "false"}, "HB_EPOCH_INVALID")):
            with self.subTest(reference=reference):
                refusal = self.K.writer_epoch_refusal(reference, retry_entrypoint="probe")
                self.assertRefusal(refusal, code)
                with self.assertRaises(self.repository.RepoLedgerEpochRefused) as refused:
                    self.append_repository(reference)
                self.assertRefusal(refused.exception.refusal, code)
        self.assertNoLedger()

    def test_the_shared_rule_is_the_pinned_final_text(self):
        source = inspect.getsource(self.K.supplied_epoch_failure)
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), self.K.SHARED_VALIDATOR_SHA256)
        self.assertEqual(self.K.SHARED_VALIDATOR_SHA256,
                         "ad8ff52936d5bcd9a2ad6caceb2d9a637a099518989b34bbb3370301c7a4cce2")

    def test_the_shared_rule_negatives(self):
        rule = self.K.supplied_epoch_failure
        forged = "sha256:" + "f" * 64
        for reference, expected in (
                ({"epoch": SUPPLIED, "sampled_unix_ns": CLOCK_NS}, "HB_EPOCH_INVALID"),
                ({"epoch": SUPPLIED, "source": "ORGANIZATION_LEDGER_HEAD", "head_receipt_sha": forged},
                 "HB_EPOCH_PROVENANCE_UNMARKED"),
                ({"epoch": SUPPLIED, "derived_from_clock": False, "sampled_unix_ns": CLOCK_NS}, "HB_EPOCH_INVALID"),
                ({"epoch": SUPPLIED, "derived_from_clock": False, "source": "X"}, None)):
            with self.subTest(reference=reference):
                failure = rule(SUPPLIED, reference)
                self.assertEqual(failure if failure is None else failure[0], expected)
        # The rule passes false + a source, so the writers keep refusing a CARRIED claim themselves.
        carried = {"epoch": SUPPLIED, "derived_from_clock": False, "source": "CARRIED:ORGANIZATION_LEDGER_HEAD",
                   "head_receipt_sha": forged}
        self.assertIsNone(rule(SUPPLIED, carried))
        self.assertRefusal(self.K.writer_epoch_refusal(carried, retry_entrypoint="probe"),
                           "CARRIED_PROVENANCE_UNVERIFIED")

    def test_a_reference_marked_supplied_is_taken_at_its_epoch(self):
        receipt = self.append_repository({"epoch": SUPPLIED, "derived_from_clock": False})
        self.assertEqual(receipt["hb_reference"]["epoch"], SUPPLIED)
        self.assertIs(receipt["hb_reference"]["derived_from_clock"], False)
        self.assertRefusal(self.K.writer_epoch_refusal({"epoch": "+33", "derived_from_clock": False},
                                                       retry_entrypoint="probe"), "HB_EPOCH_INVALID")

    def test_the_rule_runs_before_the_carried_check_so_codes_are_uniform(self):
        sampled_carried = {"epoch": "33", "derived_from_clock": False, "sampled_unix_ns": CLOCK_NS,
                           "source": "CARRIED:ORGANIZATION_LEDGER_HEAD", "head_receipt_sha": "sha256:" + "f" * 64}
        self.assertRefusal(self.K.writer_epoch_refusal(sampled_carried, retry_entrypoint="probe"), "HB_EPOCH_INVALID")
        unmarked_carried = {"epoch": 33, "source": "CARRIED:X", "head_receipt_sha": "sha256:" + "f" * 64}
        self.assertRefusal(self.K.writer_epoch_refusal(unmarked_carried, retry_entrypoint="probe"),
                           "HB_EPOCH_PROVENANCE_UNMARKED")

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
            self.publish_inbound(service, payload, f"sweep-{index}", epoch=SUPPLIED)
            self.publish_inbound(service, payload, f"sweep-clock-{index}")
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
