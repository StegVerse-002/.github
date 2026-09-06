#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "stegverse.sv002-native-org-execution-envelope/v1.1"
EXPERIMENT = "STEGVERSE-002-SELF-CHARACTERIZATION-001"
OBJECTIVE = "Determine what constitutes the entity identified as StegVerse-002 and produce a representation sufficient for another system to evaluate and reconstruct your conclusion."
REQUEST_ID = "RESIDENT-EXEC-SV002-ORG-RUNTIME-ACTIVATION-001"
TASK_ID = "SHWP-SV002-ORG-RUNTIME-ACTIVATION-001"
MODEL_ID = "stegverse-sv002-native-evidence-principal-v1"
MODEL_SHA = "111151ada104032e9a1c36bd1987ad4de1218d98b4df33879e5efc7c0adfb120"
SERVICE = "stegverse-002.self-characterization"
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


def _exact_keys(value: Mapping[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        raise EnvelopeError(f"{name} fields mismatch")


def _sha(value: Any, name: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(ch not in HEX for ch in text):
        raise EnvelopeError(f"{name} invalid")
    return text


def expected_ingress_admission(ingress: Mapping[str, Any]) -> dict[str, Any]:
    payload_sha = _sha(ingress.get("payload_sha256"), "ingress.payload_sha256")
    subject = {
        "packet_id": ingress.get("packet_id"),
        "service_id": ingress.get("destination_service"),
        "payload_hash": payload_sha,
        "kind": "INGRESS_ACCEPTED",
        "previous_receipt_id": None,
    }
    evidence_hash = digest(subject)
    return {
        "kind": "INGRESS_ACCEPTED",
        "receipt_id": "ingress_accepted-" + evidence_hash[:24],
        "evidence_hash": evidence_hash,
        "subject": SERVICE,
        "previous_receipt_id": None,
    }


def validate_supplied_ingress_receipt(ingress: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise EnvelopeError("target-org ingress receipt must be object")
    expected = expected_ingress_admission(ingress)
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise EnvelopeError(f"target-org ingress receipt {key} mismatch")
    observed_at = receipt.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise EnvelopeError("target-org ingress receipt observed_at missing")
    return expected


def validate(value: dict[str, Any]) -> dict[str, Any]:
    value = _obj(value, "envelope")
    _exact_keys(value, {"schema","experiment_id","frozen_condition_version","operation","transport","ingress","ingress_admission","resident_request","execution","principal","resource_bundle","governance","envelope_sha256"}, "envelope")
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
    _exact_keys(ingress, {"packet_id","origin_organization","origin_service","destination_organization","destination_service","source_organization_id","manifest_id","manifest_sha256","payload_sha256","objective","knowledge_policy","authority_transfer","authority_effect_resolution"}, "ingress")
    for key in ("packet_id", "origin_organization", "origin_service"):
        if not str(ingress.get(key) or "").strip():
            raise EnvelopeError(f"ingress.{key} missing")
    expected_ingress = {
        "destination_organization": "StegVerse-002",
        "destination_service": SERVICE,
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
    _sha(ingress.get("payload_sha256"), "ingress.payload_sha256")

    admission = _obj(value["ingress_admission"], "ingress_admission")
    _exact_keys(admission, {"kind","receipt_id","evidence_hash","subject","previous_receipt_id"}, "ingress_admission")
    if admission != expected_ingress_admission(ingress):
        raise EnvelopeError("target-org INGRESS_ACCEPTED binding mismatch")

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


def bind_envelope(*, ingress: dict[str, Any], ingress_receipt: Mapping[str, Any], resource_bundle_sha256: str) -> dict[str, Any]:
    _sha(resource_bundle_sha256, "resource_bundle.bundle_sha256")
    admission = validate_supplied_ingress_receipt(ingress, ingress_receipt)
    envelope = {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT,
        "frozen_condition_version": "v0.3",
        "operation": "REQUEST_SELF_CHARACTERIZATION",
        "transport": "InTr",
        "ingress": ingress,
        "ingress_admission": admission,
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
