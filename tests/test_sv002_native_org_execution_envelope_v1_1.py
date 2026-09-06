from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "resident-runtime" / "validate_sv002_native_org_execution_envelope_v1_1.py"
spec = importlib.util.spec_from_file_location("sv002_native_org_execution_envelope_v1_1", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def ingress():
    return {
        "packet_id": "INTR-SV002-TEST-001",
        "origin_organization": "StegVerse-org",
        "origin_service": "stegverse-sdk.external-evaluator",
        "destination_organization": "StegVerse-002",
        "destination_service": "stegverse-002.self-characterization",
        "source_organization_id": "StegVerse-SDK-Evaluator",
        "manifest_id": "SDK-SV002-FIRST-SELF-CHARACTERIZATION-001",
        "manifest_sha256": "a" * 64,
        "payload_sha256": "c" * 64,
        "objective": mod.OBJECTIVE,
        "knowledge_policy": dict(mod.POLICY),
        "authority_transfer": False,
        "authority_effect_resolution": "DERIVED_FROM_APPLICABLE_TRANSITION_ELEMENTS",
    }


def receipt(i=None):
    i = ingress() if i is None else i
    expected = mod.expected_ingress_admission(i)
    return {**expected, "observed_at": "2026-09-06T05:00:00+00:00"}


def envelope():
    i = ingress()
    return mod.bind_envelope(ingress=i, ingress_receipt=receipt(i), resource_bundle_sha256="b" * 64)


def rehash(value):
    value = deepcopy(value)
    value.pop("envelope_sha256", None)
    value["envelope_sha256"] = mod.digest(value)
    return value


class NativeOrgExecutionEnvelopeV11Tests(unittest.TestCase):
    def test_v11_binds_supplied_target_org_ingress_receipt(self):
        i = ingress()
        expected = mod.expected_ingress_admission(i)
        value = mod.bind_envelope(ingress=i, ingress_receipt=receipt(i), resource_bundle_sha256="b" * 64)
        self.assertEqual(value["schema"], "stegverse.sv002-native-org-execution-envelope/v1.1")
        self.assertEqual(value["ingress_admission"], expected)
        self.assertEqual(mod.validate(value), value)

    def test_ingress_receipt_identity_matches_canonical_org_boundary_formula(self):
        i = ingress()
        subject = {
            "packet_id": i["packet_id"],
            "service_id": i["destination_service"],
            "payload_hash": i["payload_sha256"],
            "kind": "INGRESS_ACCEPTED",
            "previous_receipt_id": None,
        }
        evidence = mod.digest(subject)
        expected = mod.expected_ingress_admission(i)
        self.assertEqual(expected["receipt_id"], "ingress_accepted-" + evidence[:24])
        self.assertEqual(expected["evidence_hash"], evidence)
        self.assertEqual(expected["subject"], "stegverse-002.self-characterization")
        self.assertIsNone(expected["previous_receipt_id"])

    def test_binder_refuses_to_synthesize_missing_admission_receipt(self):
        with self.assertRaises(mod.EnvelopeError):
            mod.bind_envelope(ingress=ingress(), ingress_receipt={}, resource_bundle_sha256="b" * 64)

    def test_receipt_tampering_fails_before_envelope_creation(self):
        cases = [
            ("kind", "DISPATCHED"),
            ("receipt_id", "ingress_accepted-" + "0" * 24),
            ("evidence_hash", "0" * 64),
            ("subject", "other.service"),
            ("previous_receipt_id", "prior"),
            ("observed_at", ""),
        ]
        i = ingress()
        for key, changed in cases:
            with self.subTest(key=key):
                r = receipt(i)
                r[key] = changed
                with self.assertRaises(mod.EnvelopeError):
                    mod.bind_envelope(ingress=i, ingress_receipt=r, resource_bundle_sha256="b" * 64)

    def test_payload_hash_change_invalidates_bound_admission(self):
        value = envelope()
        value["ingress"]["payload_sha256"] = "d" * 64
        value = rehash(value)
        with self.assertRaisesRegex(mod.EnvelopeError, "INGRESS_ACCEPTED"):
            mod.validate(value)

    def test_v1_shape_is_rejected_by_v11_validator(self):
        value = envelope()
        value["schema"] = "stegverse.sv002-native-org-execution-envelope/v1"
        value.pop("ingress_admission")
        value["ingress"].pop("payload_sha256")
        value = rehash(value)
        with self.assertRaises(mod.EnvelopeError):
            mod.validate(value)

    def test_existing_request_authority_and_physical_boundaries_remain_exact(self):
        value = envelope()
        self.assertEqual(value["resident_request"]["request_id"], "RESIDENT-EXEC-SV002-ORG-RUNTIME-ACTIVATION-001")
        self.assertEqual(value["resident_request"]["task_id"], "SHWP-SV002-ORG-RUNTIME-ACTIVATION-001")
        self.assertEqual(value["execution"]["physical_substrate"], "CURRENT_USER_IPHONE")
        self.assertFalse(value["execution"]["second_machine_required"])
        self.assertFalse(value["execution"]["hosted_runtime_allowed"])
        self.assertFalse(value["execution"]["runtime_network_resource_fetch_allowed"])
        self.assertEqual(value["governance"]["credential_authority"], "TV/TVC")
        self.assertEqual(value["governance"]["github_runtime_authority"], "NONE")
        self.assertFalse(value["governance"]["authority_transfer"])
        self.assertTrue(value["governance"]["master_records_required"])


if __name__ == "__main__":
    unittest.main()
