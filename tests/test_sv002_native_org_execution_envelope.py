from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "resident-runtime" / "validate_sv002_native_org_execution_envelope.py"
spec = importlib.util.spec_from_file_location("sv002_native_org_execution_envelope", MODULE_PATH)
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
        "objective": mod.OBJECTIVE,
        "knowledge_policy": dict(mod.POLICY),
        "authority_transfer": False,
        "authority_effect_resolution": "DERIVED_FROM_APPLICABLE_TRANSITION_ELEMENTS",
    }


def envelope():
    return mod.bind_envelope(ingress=ingress(), resource_bundle_sha256="b" * 64)


def rehash(value):
    value = deepcopy(value)
    value.pop("envelope_sha256", None)
    value["envelope_sha256"] = mod.digest(value)
    return value


def test_valid_envelope_is_deterministic_and_reuses_existing_request():
    one = envelope()
    two = envelope()
    assert one == two
    assert mod.validate(one) == one
    assert one["resident_request"]["request_id"] == "RESIDENT-EXEC-SV002-ORG-RUNTIME-ACTIVATION-001"
    assert one["resident_request"]["task_id"] == "SHWP-SV002-ORG-RUNTIME-ACTIVATION-001"
    assert one["execution"]["execution_owner_repository"] == "StegVerse-002/.github"
    assert one["execution"]["physical_substrate"] == "CURRENT_USER_IPHONE"


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("resident_request", "request_id", "NEW-DUPLICATE-REQUEST"),
        ("resident_request", "task_id", "NEW-DUPLICATE-TASK"),
        ("execution", "execution_owner_repository", "StegVerse-Labs/StegOS"),
        ("execution", "physical_substrate", "OTHER_MACHINE"),
        ("execution", "second_machine_required", True),
        ("execution", "hosted_runtime_allowed", True),
        ("execution", "runtime_network_resource_fetch_allowed", True),
        ("principal", "model_id", "stegverse-reference-lm-v1"),
        ("principal", "reference_model", True),
        ("resource_bundle", "runtime_network_fetch_allowed", True),
        ("governance", "credential_authority", "OTHER"),
        ("governance", "github_runtime_authority", "EXECUTION"),
        ("governance", "authority_transfer", True),
        ("governance", "master_records_required", False),
    ],
)
def test_boundary_drift_fails_closed(section, key, value):
    value_obj = envelope()
    value_obj[section][key] = value
    value_obj = rehash(value_obj)
    with pytest.raises(mod.EnvelopeError):
        mod.validate(value_obj)


def test_frozen_ingress_contract_drift_fails_closed():
    value = envelope()
    value["ingress"]["objective"] = "different objective"
    value = rehash(value)
    with pytest.raises(mod.EnvelopeError, match="objective"):
        mod.validate(value)


def test_manifest_and_resource_hashes_are_required():
    value = envelope()
    value["ingress"]["manifest_sha256"] = "not-a-hash"
    value = rehash(value)
    with pytest.raises(mod.EnvelopeError):
        mod.validate(value)
    value = envelope()
    value["resource_bundle"]["bundle_sha256"] = "not-a-hash"
    value = rehash(value)
    with pytest.raises(mod.EnvelopeError):
        mod.validate(value)


def test_envelope_hash_tamper_fails_closed():
    value = envelope()
    value["envelope_sha256"] = "0" * 64
    with pytest.raises(mod.EnvelopeError, match="envelope SHA-256 mismatch"):
        mod.validate(value)


def test_unknown_fields_fail_closed():
    value = envelope()
    value["unexpected"] = True
    value = rehash(value)
    with pytest.raises(mod.EnvelopeError, match="fields mismatch"):
        mod.validate(value)
