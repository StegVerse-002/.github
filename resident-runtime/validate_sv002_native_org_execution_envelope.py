#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "stegverse.sv002-native-org-execution-envelope/v1"
EXPERIMENT = "STEGVERSE-002-SELF-CHARACTERIZATION-001"
OBJECTIVE = "Determine what constitutes the entity identified as StegVerse-002 and produce a representation sufficient for another system to evaluate and reconstruct your conclusion."
REQUEST_ID = "RESIDENT-EXEC-SV002-ORG-RUNTIME-ACTIVATION-001"
TASK_ID = "SHWP-SV002-ORG-RUNTIME-ACTIVATION-001"
MODEL_ID = "stegverse-sv002-native-evidence-principal-v1"
MODEL_SHA = "111151ada104032e9a1c36bd1987ad4de1218d98b4df33879e5efc7c0adfb120"
POLICY = {
    "prescribe_self_ontology": False,
    "prescribe_formalism": False,
    "prescribe_transition_elements": False,
    "prescribe_external_followup": False,
    "prescribe_admissible_existence_connection": False,
}
HEX = set("0123456789abcdef")

class EnvelopeError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _obj(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EnvelopeError(f"{name} must be object")
    return value


def _exact_keys(value: dict[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        raise EnvelopeError(f"{name} fields mismatch")


def _sha(value: Any, name: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(ch not in HEX for ch in text):
        raise EnvelopeError(f"{name} invalid")
    return text


def validate(value: dict[str, Any]) -> dict[str, Any]:
    value = _obj(value, "envelope")
    _exact_keys(value, {"schema","experiment_id","frozen_condition_version","operation","transport","ingress","resident_request","execution","principal","resource_bundle","governance","envelope_sha256"}, "envelope")
    expected_top = {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT,
        "frozen_condition_version": "v0.3",
        "operation": "REQUEST_SELF_CHARACTERIZATION",
        "transport": "InTr",
    }
    for key, expected in expected_top.items():
        if value.get(key) != expected:
            raise EnvelopeError(f"{key} mismatch")

    ingress = _obj(value["ingress"], "ingress")
    _exact_keys(ingress, {"packet_id","origin_organization","origin_service","destination_organization","destination_service","source_organization_id","manifest_id","manifest_sha256","objective","knowledge_policy","authority_transfer","authority_effect_resolution"}, "ingress")
    for key in ("packet_id", "origin_organization", "origin_service"):
        if not str(ingress.get(key) or "").strip():
            raise EnvelopeError(f"ingress.{key} missing")
    expected_ingress = {
        "destination_organization": "StegVerse-002",
        "destination_service": "stegverse-002.self-characterization",
        "source_organization_id": "StegVerse-SDK-Evaluator",
        "manifest_id": "SDK-SV002-FIRST-SELF-CHARACTERIZATION-001",
        "objective": OBJECTIVE,
        "knowledge_policy": POLICY,
        "authority_transfer": False,
        "authority_effect_resolution": "DERIVED_FROM_APPLICABLE_TRANSITION_ELEMENTS",
    }
    for key, expected in expected_ingress.items():
        if ingress.get(key) != expected:
            raise EnvelopeError(f"ingress.{key} mismatch")
    _sha(ingress.get("manifest_sha256"), "ingress.manifest_sha256")

    request = _obj(value["resident_request"], "resident_request")
    _exact_keys(request, {"request_id","task_id","state","mode"}, "resident_request")
    if request != {
        "request_id": REQUEST_ID,
        "task_id": TASK_ID,
        "state": "REQUESTED",
        "mode": "TARGETED_INDEPENDENT_TASK_CONTROL",
    }:
        raise EnvelopeError("resident request identity/state mismatch")

    execution = _obj(value["execution"], "execution")
    _exact_keys(execution, {"execution_owner_repository","physical_substrate","principal_substrate","second_machine_required","hosted_runtime_allowed","runtime_network_resource_fetch_allowed"}, "execution")
    if execution != {
        "execution_owner_repository": "StegVerse-002/.github",
        "physical_substrate": "CURRENT_USER_IPHONE",
        "principal_substrate": "RESIDENT_LOOPBACK_NATIVE_IOS",
        "second_machine_required": False,
        "hosted_runtime_allowed": False,
        "runtime_network_resource_fetch_allowed": False,
    }:
        raise EnvelopeError("execution boundary mismatch")

    principal = _obj(value["principal"], "principal")
    _exact_keys(principal, {"owner_repository","package_schema","model_id","runtime_engine","model_artifact_sha256","reference_model"}, "principal")
    if principal != {
        "owner_repository": "StegVerse-002/micro-node-runtime",
        "package_schema": "stegverse.sv002-native-principal-package/v0.1",
        "model_id": MODEL_ID,
        "runtime_engine": "stegverse-sv002-native-action-policy",
        "model_artifact_sha256": MODEL_SHA,
        "reference_model": False,
    }:
        raise EnvelopeError("principal identity mismatch")

    resources = _obj(value["resource_bundle"], "resource_bundle")
    _exact_keys(resources, {"owner_repository","schema","bundle_sha256","runtime_network_fetch_allowed"}, "resource_bundle")
    if resources.get("owner_repository") != "StegVerse-002/micro-node-runtime" or resources.get("schema") != "stegverse.sv002-native-resource-bundle/v1" or resources.get("runtime_network_fetch_allowed") is not False:
        raise EnvelopeError("resource bundle boundary mismatch")
    _sha(resources.get("bundle_sha256"), "resource_bundle.bundle_sha256")

    governance = _obj(value["governance"], "governance")
    _exact_keys(governance, {"credential_authority","github_runtime_authority","workercoordinator_required","intr_admission_required","master_records_required","authority_transfer","authority_effect"}, "governance")
    if governance != {
        "credential_authority": "TV/TVC",
        "github_runtime_authority": "NONE",
        "workercoordinator_required": True,
        "intr_admission_required": True,
        "master_records_required": True,
        "authority_transfer": False,
        "authority_effect": "NONE_EXECUTION_REQUEST_ONLY",
    }:
        raise EnvelopeError("governance boundary mismatch")

    claimed = _sha(value.get("envelope_sha256"), "envelope_sha256")
    body = dict(value)
    body.pop("envelope_sha256")
    actual = digest(body)
    if claimed != actual:
        raise EnvelopeError("envelope SHA-256 mismatch")
    return value


def bind_envelope(*, ingress: dict[str, Any], resource_bundle_sha256: str) -> dict[str, Any]:
    _sha(resource_bundle_sha256, "resource_bundle.bundle_sha256")
    envelope = {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT,
        "frozen_condition_version": "v0.3",
        "operation": "REQUEST_SELF_CHARACTERIZATION",
        "transport": "InTr",
        "ingress": ingress,
        "resident_request": {
            "request_id": REQUEST_ID,
            "task_id": TASK_ID,
            "state": "REQUESTED",
            "mode": "TARGETED_INDEPENDENT_TASK_CONTROL",
        },
        "execution": {
            "execution_owner_repository": "StegVerse-002/.github",
            "physical_substrate": "CURRENT_USER_IPHONE",
            "principal_substrate": "RESIDENT_LOOPBACK_NATIVE_IOS",
            "second_machine_required": False,
            "hosted_runtime_allowed": False,
            "runtime_network_resource_fetch_allowed": False,
        },
        "principal": {
            "owner_repository": "StegVerse-002/micro-node-runtime",
            "package_schema": "stegverse.sv002-native-principal-package/v0.1",
            "model_id": MODEL_ID,
            "runtime_engine": "stegverse-sv002-native-action-policy",
            "model_artifact_sha256": MODEL_SHA,
            "reference_model": False,
        },
        "resource_bundle": {
            "owner_repository": "StegVerse-002/micro-node-runtime",
            "schema": "stegverse.sv002-native-resource-bundle/v1",
            "bundle_sha256": resource_bundle_sha256,
            "runtime_network_fetch_allowed": False,
        },
        "governance": {
            "credential_authority": "TV/TVC",
            "github_runtime_authority": "NONE",
            "workercoordinator_required": True,
            "intr_admission_required": True,
            "master_records_required": True,
            "authority_transfer": False,
            "authority_effect": "NONE_EXECUTION_REQUEST_ONLY",
        },
    }
    envelope["envelope_sha256"] = digest(envelope)
    return validate(envelope)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    args = ap.parse_args()
    value = json.loads(args.path.read_text(encoding="utf-8"))
    validate(value)
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
