import base64
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "invoke_sv002_experiment_rerun",
    ROOT / "resident-runtime" / "invoke_sv002_experiment_rerun.py",
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

EXEC_SPEC = importlib.util.spec_from_file_location(
    "sv002_resident_executor",
    ROOT / "resident-runtime" / "resident_executor.py",
)
E = importlib.util.module_from_spec(EXEC_SPEC)
EXEC_SPEC.loader.exec_module(E)

#: The epoch the resident executor supplies to the callable; no clock stands in.
HB_EPOCH = 4096


class SV002ExperimentRerunCallableBindingTests(unittest.TestCase):
    def test_an_absent_epoch_is_refused_six_field_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            env = {"STEGVERSE_SELF_CHAR_STATE_ROOT": str(state), "GITHUB_ACTIONS": "", "CI": ""}
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("STEGVERSE_HB_EPOCH", None)
                with self.assertRaises(ValueError) as refused:
                    M.invoke_once()
            self.assertEqual(refused.exception.refusal["failure_code"], "HB_EPOCH_NOT_SUPPLIED")
            self.assertFalse(state.exists())

    def test_builds_exact_frozen_request(self):
        request, manifest = M.build_frozen_request()
        self.assertEqual(request["operation"], "REQUEST_SELF_CHARACTERIZATION")
        self.assertEqual(request["transport"], "InTr")
        self.assertEqual(manifest["experiment_id"], "STEGVERSE-002-SELF-CHARACTERIZATION-001")
        self.assertEqual(manifest["target"]["entity_id"], "StegVerse-002")
        self.assertEqual(
            request["bindings"]["manifest_sha256"],
            manifest["manifest_sha256"],
        )

    def test_exactly_once_same_host_publication(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            mesh = Path(td) / "mesh"
            env = {
                "STEGVERSE_SELF_CHAR_STATE_ROOT": str(state),
                "STEGVERSE_ORG_FEDERATION_ROOT": str(mesh),
                "STEGVERSE_ORG_FEDERATION_GATEWAY_URL": "",
                "GITHUB_ACTIONS": "",
                "CI": "",
                "STEGVERSE_HB_EPOCH": str(HB_EPOCH),
            }
            custody = {
                "state": "RECORDED",
                "reconstruction_status": "PASS",
                "master_record_ref": "master-record:state-transition:sha256:test",
                "custody_receipt_id": "master-records-state-transition-receipt:test",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                M, "_custody_request_bound", return_value=custody
            ):
                first = M.invoke_once()
                second = M.invoke_once()

            self.assertEqual(first["state"], "SUBMITTED_EXISTING_FEDERATION_EDGE")
            self.assertEqual(first["submitted_at"], f"hb-epoch:{HB_EPOCH}")
            self.assertEqual(second["state"], "ALREADY_SUBMITTED_NO_SECOND_REQUEST")
            self.assertEqual(first["frame_sha256"], second["frame_sha256"])
            self.assertEqual(len(list((mesh / "frames.d").glob("*.json"))), 1)
            bound = json.loads((state / "RERUN_REQUEST_BOUND.json").read_text())
            self.assertEqual(bound["state"], "REQUEST_BOUND")
            self.assertEqual(bound["frame"]["heartbeat_reference"]["epoch"], HB_EPOCH)
            self.assertIs(bound["frame"]["heartbeat_reference"]["derived_from_clock"], False)
            self.assertEqual(bound["invocation_count"], 1)

    def test_blocked_submission_preserves_request_bound_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            env = {
                "STEGVERSE_SELF_CHAR_STATE_ROOT": str(state),
                "STEGVERSE_ORG_FEDERATION_ROOT": "",
                "STEGVERSE_ORG_FEDERATION_GATEWAY_URL": "",
                "GITHUB_ACTIONS": "",
                "CI": "",
                "STEGVERSE_HB_EPOCH": str(HB_EPOCH),
            }
            custody = {
                "state": "RECORDED",
                "reconstruction_status": "PASS",
                "master_record_ref": "master-record:state-transition:sha256:test",
                "custody_receipt_id": "master-records-state-transition-receipt:test",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                M, "_custody_request_bound", return_value=custody
            ):
                with self.assertRaisesRegex(RuntimeError, "publication edge not configured") as caught:
                    M.invoke_once()
                result = M._blocked_result(caught.exception)

            bound = json.loads((state / "RERUN_REQUEST_BOUND.json").read_text())
            self.assertTrue(result["request_bound_claimed"])
            self.assertEqual(result["goal_task_id"], "STEGVERSE-002-EXPERIMENT-RERUN-001")
            self.assertEqual(result["cosv_id"], "50000000107000")
            self.assertEqual(result["experiment_id"], "STEGVERSE-002-SELF-CHARACTERIZATION-001")
            self.assertEqual(result["operation"], "REQUEST_SELF_CHARACTERIZATION")
            self.assertEqual(result["invocation_count"], 1)
            self.assertEqual(result["packet_id"], bound["packet_id"])
            self.assertEqual(result["packet_sha256"], bound["packet_sha256"])
            self.assertEqual(result["manifest_sha256"], bound["manifest_sha256"])
            self.assertEqual(result["frame_sha256"], bound["frame_sha256"])
            self.assertFalse((state / "RERUN_REQUEST_SUBMISSION.json").exists())

    def test_resident_executor_preserves_structured_blocked_callable_result(self):
        blocked = {
            "schema": "stegverse.sv002-rerun-callable-result/v1",
            "goal_task_id": "STEGVERSE-002-EXPERIMENT-RERUN-001",
            "cosv_id": "50000000107000",
            "state": "BLOCKED",
            "reason": "existing federation publication edge not configured",
            "request_bound_claimed": True,
            "packet_id": "SV002-RERUN-TEST",
            "frame_sha256": "sha256:" + "a" * 64,
        }
        proc = SimpleNamespace(returncode=2, stderr="")
        with patch.object(E, "run_json", return_value=(proc, blocked)):
            result = E.consume_declared_sv002_callable()
        self.assertEqual(result, blocked)
        self.assertTrue(result["request_bound_claimed"])

    def test_request_bound_requires_canonical_master_records_organization_record(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            frame, bound = M._load_or_bind_frame(state, HB_EPOCH)
            class FakeCustody:
                @staticmethod
                def build_state_receipt(**kwargs):
                    return {
                        "schema": "stegverse.canonical-state-transition-receipt/v1",
                        **kwargs,
                        "recorded_at": "2026-09-18T00:00:00Z",
                        "authority_effect": "NONE_STATE_RECEIPT_ONLY",
                        "proof_scope": "THIS_TRANSITION_ONLY",
                        "proof_ceiling": "OBSERVED_STATE_TRANSITION_AND_CUSTODY_ONLY",
                        "master_records_may_grant_transition_authority": False,
                        "master_records_may_grant_execution_authority": False,
                    }

                @staticmethod
                def submit_state_receipt(receipt):
                    self.assertEqual(receipt["transition_id"], "SV002_REQUEST_BOUND")
                    self.assertEqual(receipt["transition_sequence"], 1)
                    self.assertEqual(receipt["subject_or_correlation_id"], bound["packet_id"])
                    self.assertEqual(receipt["transition_evidence"]["goal_task_id"], "STEGVERSE-002-EXPERIMENT-RERUN-001")
                    self.assertEqual(receipt["transition_evidence"]["cosv_id"], "50000000107000")
                    self.assertEqual(receipt["transition_evidence"]["manifest_sha256"], bound["manifest_sha256"])
                    self.assertEqual(receipt["transition_evidence"]["frame_sha256"], bound["frame_sha256"])
                    required = receipt["required_evidence_manifest"]
                    self.assertEqual(len(required), 1)
                    item = required[0]
                    self.assertEqual(item["evidence_id"], "SV002_REQUEST_BOUND_EXACT_BYTES")
                    self.assertEqual(item["origin_transition_id"], "SV002_REQUEST_BOUND")
                    self.assertEqual(item["encoding"], "base64")
                    exact = base64.b64decode(item["content"])
                    self.assertEqual(exact, (state / "RERUN_REQUEST_BOUND.json").read_bytes())
                    self.assertEqual(hashlib.sha256(exact).hexdigest(), item["sha256"])
                    return {
                        "state": "RECORDED",
                        "reconstruction_status": "PASS",
                        "required_evidence_validation_status": "PASS",
                        "required_evidence_count": 1,
                        "receipt_sha256": "a" * 64,
                        "reconstructed_receipt_sha256": "a" * 64,
                        "custody_receipt_id": "master-records-state-transition-receipt:test",
                        "master_record_ref": "master-record:state-transition:sha256:" + "a" * 64,
                        "master_records_grants_transition_authority": False,
                        "authority_effect": "NONE_CUSTODY_RECONSTRUCTION_ONLY",
                    }

            with patch.object(M, "_canonical_custody_client", return_value=FakeCustody()):
                result = M._custody_request_bound(state, bound)
            self.assertEqual(result["state"], "RECORDED")
            self.assertEqual(result["reconstruction_status"], "PASS")
            self.assertEqual(result["required_evidence_validation_status"], "PASS")
            self.assertEqual(result["required_evidence_count"], 1)
            self.assertTrue((state / "RERUN_REQUEST_BOUND_MASTER_RECORDS_RECEIPT.json").is_file())
            self.assertTrue((state / "RERUN_REQUEST_BOUND_MASTER_RECORDS_ORGANIZATION_RECORD.json").is_file())
            self.assertFalse((state / M.LEGACY_REQUEST_BOUND_ORGANIZATION_RECORD).exists())
            self.assertEqual(result["schema"], "stegverse.sv002-request-bound-master-records-organization-record/v1")
            self.assertIsNotNone(frame)

    def test_request_bound_evidence_reads_new_and_legacy_organization_record(self):
        for name in (M.REQUEST_BOUND_ORGANIZATION_RECORD, M.LEGACY_REQUEST_BOUND_ORGANIZATION_RECORD):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                state = Path(td) / "state"
                M._load_or_bind_frame(state, HB_EPOCH)
                (state / name).write_text(json.dumps({
                    "state": "RECORDED",
                    "reconstruction_status": "PASS",
                    "receipt_sha256": "c" * 64,
                    "master_record_ref": "master-record:test",
                }), encoding="utf-8")
                with patch.dict(os.environ, {"STEGVERSE_SELF_CHAR_STATE_ROOT": str(state)}):
                    evidence = M._request_bound_evidence()
                self.assertTrue(evidence["request_bound_claimed"])
                self.assertEqual(evidence["request_bound_master_records_state"], "RECORDED")
                self.assertEqual(evidence["request_bound_master_records_reconstruction_status"], "PASS")
                self.assertEqual(evidence["request_bound_master_record_ref"], "master-record:test")

    def test_hosted_execution_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            env = {
                "STEGVERSE_SELF_CHAR_STATE_ROOT": str(Path(td) / "state"),
                "STEGVERSE_ORG_FEDERATION_ROOT": str(Path(td) / "mesh"),
                "GITHUB_ACTIONS": "true",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(RuntimeError, "hosted execution prohibited"):
                    M.invoke_once()


if __name__ == "__main__":
    unittest.main()
