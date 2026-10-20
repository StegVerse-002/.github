#!/usr/bin/env python3
"""Bind the canonical SV002 rerun task to the existing federation publisher.

This module does not create a runtime, transport, listener, scheduler, bridge, or
second request. It constructs the frozen REQUEST_SELF_CHARACTERIZATION request
from the existing organization-local binding and submits exactly one immutable
carrier frame through either the already-configured shared federation gateway or
the already-configured same-host federation mesh.

REQUEST_BOUND is retained before submission. A retry after an interrupted
submission reuses the exact persisted frame; it never mints a second request.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOAL_TASK_ID = "STEGVERSE-002-EXPERIMENT-RERUN-001"
COSV_ID = "50000000107000"
EXPERIMENT_ID = "STEGVERSE-002-SELF-CHARACTERIZATION-001"
OPERATION = "REQUEST_SELF_CHARACTERIZATION"
DESTINATION_ORG = "StegVerse-002"
DESTINATION_SERVICE = "stegverse-002.self-characterization"
ORIGIN_ORG = "StegVerse-org"
ORIGIN_SERVICE = "stegverse-sdk.external-evaluator"
INVOCATION_COUNT = 1
REQUEST_BOUND_ORGANIZATION_RECORD = "RERUN_REQUEST_BOUND_MASTER_RECORDS_ORGANIZATION_RECORD.json"
LEGACY_REQUEST_BOUND_ORGANIZATION_RECORD = "RERUN_REQUEST_BOUND_MASTER_RECORDS_CUSTODY.json"
HOSTED = ("GITHUB_ACTIONS", "CI", "RENDER", "VERCEL", "CF_PAGES", "CLOUDFLARE_WORKERS")

K_SPEC = importlib.util.spec_from_file_location("org_kernel", ROOT / "org-kernel" / "kernel.py")
K = importlib.util.module_from_spec(K_SPEC)
K_SPEC.loader.exec_module(K)

GW_SPEC = importlib.util.spec_from_file_location(
    "federation_gateway_transport",
    ROOT / "resident-runtime" / "federation_gateway_transport.py",
)
GW = importlib.util.module_from_spec(GW_SPEC)
GW_SPEC.loader.exec_module(GW)

BINDING_PATH = ROOT / "resident-runtime" / "self-characterization" / "stegverse-002.json"
SERVICES_PATH = ROOT / "org-boundary" / "registry" / "services.json"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() not in {"", "0", "false", "no"}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"object required: {path}")
    return value


def _write_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = _load(path)
        if existing != value:
            raise RuntimeError(f"write-once collision: {path}")
        return
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _request_bound_organization_record_path(state_root: Path) -> Path | None:
    for name in (REQUEST_BOUND_ORGANIZATION_RECORD, LEGACY_REQUEST_BOUND_ORGANIZATION_RECORD):
        if (state_root / name).is_file():
            return state_root / name
    return None


def _state_root() -> Path:
    raw = os.environ.get(
        "STEGVERSE_SELF_CHAR_STATE_ROOT",
        str(Path.home() / ".stegverse" / "self-characterization-001"),
    )
    return Path(raw).expanduser().resolve()


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _canonical_custody_client() -> Any:
    raw = (os.environ.get("STEGVERSE_REPO_ROOTS_JSON") or "").strip()
    try:
        roots = json.loads(raw) if raw else {}
    except Exception as exc:
        raise RuntimeError("canonical Master Records organization-record client repository roots invalid") from exc
    labs_root_raw = str(roots.get("StegVerse-Labs/.github") or "").strip()
    if not labs_root_raw:
        raise RuntimeError("canonical Master Records organization-record client unavailable")
    client_path = Path(labs_root_raw).expanduser().resolve() / "workers" / "canonical_state_transition_custody.py"
    if not client_path.is_file():
        raise RuntimeError("canonical Master Records organization-record client unavailable")
    spec = importlib.util.spec_from_file_location("canonical_state_transition_custody", client_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical Master Records organization-record client import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _custody_request_bound(state_root: Path, bound: dict[str, Any]) -> dict[str, Any]:
    receipt_path = state_root / "RERUN_REQUEST_BOUND_MASTER_RECORDS_RECEIPT.json"
    custody_path = state_root / REQUEST_BOUND_ORGANIZATION_RECORD
    client = _canonical_custody_client()
    bound_path = state_root / "RERUN_REQUEST_BOUND.json"
    if not bound_path.is_file():
        raise RuntimeError("REQUEST_BOUND exact evidence missing before custody")
    bound_bytes = bound_path.read_bytes()
    required_evidence_manifest = [{
        "evidence_id": "SV002_REQUEST_BOUND_EXACT_BYTES",
        "evidence_type": "stegverse.sv002-rerun-request-bound/v1",
        "origin_transition_id": "SV002_REQUEST_BOUND",
        "encoding": "base64",
        "sha256": hashlib.sha256(bound_bytes).hexdigest(),
        "content": base64.b64encode(bound_bytes).decode("ascii"),
    }]
    if receipt_path.is_file():
        receipt = _load(receipt_path)
        if receipt.get("required_evidence_manifest") != required_evidence_manifest:
            raise RuntimeError("persisted REQUEST_BOUND custody receipt required-evidence mismatch")
    else:
        receipt = client.build_state_receipt(
            transition_id="SV002_REQUEST_BOUND",
            transition_sequence=1,
            subject_or_correlation_id=bound["packet_id"],
            transition_outcome="OBSERVED",
            prior_state_ref_or_hash=bound["request_sha256"],
            resulting_state_ref_or_hash=bound["frame_sha256"],
            governance_decision_ref_where_applicable=None,
            transition_evidence={
                "goal_task_id": bound["goal_task_id"],
                "cosv_id": bound["cosv_id"],
                "experiment_id": bound["experiment_id"],
                "operation": bound["operation"],
                "invocation_count": bound["invocation_count"],
                "state": bound["state"],
                "packet_id": bound["packet_id"],
                "packet_sha256": bound["packet_sha256"],
                "request_sha256": bound["request_sha256"],
                "manifest_sha256": bound["manifest_sha256"],
                "frame_sha256": bound["frame_sha256"],
            },
            required_evidence_manifest=required_evidence_manifest,
        )
        _write_once(receipt_path, receipt)
    result = client.submit_state_receipt(receipt)
    if (
        result.get("state") != "RECORDED"
        or result.get("reconstruction_status") != "PASS"
        or result.get("required_evidence_validation_status") != "PASS"
        or result.get("required_evidence_count") != 1
    ):
        raise RuntimeError(
            "canonical Master Records REQUEST_BOUND organization record/required evidence not recorded: "
            + str(result.get("reason") or result.get("state") or "UNKNOWN")
        )
    if result.get("receipt_sha256") != result.get("reconstructed_receipt_sha256"):
        raise RuntimeError("canonical Master Records REQUEST_BOUND receipt reconstruction hash mismatch")
    response = {
        "schema": "stegverse.sv002-request-bound-master-records-organization-record/v1",
        "state": "RECORDED",
        "reconstruction_status": "PASS",
        "required_evidence_validation_status": result.get("required_evidence_validation_status"),
        "required_evidence_count": result.get("required_evidence_count"),
        "packet_id": bound["packet_id"],
        "receipt_sha256": result.get("receipt_sha256"),
        "reconstructed_receipt_sha256": result.get("reconstructed_receipt_sha256"),
        "custody_receipt_id": result.get("custody_receipt_id"),
        "master_record_ref": result.get("master_record_ref"),
        "master_records_grants_transition_authority": result.get("master_records_grants_transition_authority"),
        "authority_effect": result.get("authority_effect"),
    }
    _write_once(custody_path, response)
    return response


def _request_bound_evidence() -> dict[str, Any]:
    path = _state_root() / "RERUN_REQUEST_BOUND.json"
    base = {
        "request_bound_claimed": False,
        "request_bound_ref": str(path),
    }
    if not path.is_file():
        return base
    try:
        bound = _load(path)
        expected = {
            "goal_task_id": GOAL_TASK_ID,
            "cosv_id": COSV_ID,
            "experiment_id": EXPERIMENT_ID,
            "operation": OPERATION,
            "invocation_count": INVOCATION_COUNT,
            "state": "REQUEST_BOUND",
        }
        for key, wanted in expected.items():
            if bound.get(key) != wanted:
                raise RuntimeError(f"persisted REQUEST_BOUND {key} mismatch")
        frame = bound.get("frame")
        if not isinstance(frame, dict):
            raise RuntimeError("persisted REQUEST_BOUND frame missing")
        packet = K.recover_packet(frame)
        if packet.get("packet_id") != bound.get("packet_id"):
            raise RuntimeError("persisted REQUEST_BOUND packet_id mismatch")
        if frame.get("packet_sha256") != bound.get("packet_sha256"):
            raise RuntimeError("persisted REQUEST_BOUND packet_sha256 mismatch")
        if frame.get("frame_sha256") != bound.get("frame_sha256"):
            raise RuntimeError("persisted REQUEST_BOUND frame_sha256 mismatch")
        custody_path = _request_bound_organization_record_path(_state_root())
        custody = _load(custody_path) if custody_path is not None else None
        return {
            **base,
            "request_bound_claimed": True,
            "request_bound_schema": bound.get("schema"),
            "goal_task_id": bound["goal_task_id"],
            "cosv_id": bound["cosv_id"],
            "experiment_id": bound["experiment_id"],
            "operation": bound["operation"],
            "invocation_count": bound["invocation_count"],
            "packet_id": bound["packet_id"],
            "packet_sha256": bound["packet_sha256"],
            "manifest_sha256": bound["manifest_sha256"],
            "frame_sha256": bound["frame_sha256"],
            "request_bound_master_records_state": custody.get("state") if custody else None,
            "request_bound_master_records_reconstruction_status": custody.get("reconstruction_status") if custody else None,
            "request_bound_master_records_required_evidence_validation_status": custody.get("required_evidence_validation_status") if custody else None,
            "request_bound_master_records_required_evidence_count": custody.get("required_evidence_count") if custody else None,
            "request_bound_master_records_receipt_sha256": custody.get("receipt_sha256") if custody else None,
            "request_bound_master_records_reconstructed_receipt_sha256": custody.get("reconstructed_receipt_sha256") if custody else None,
            "request_bound_master_record_ref": custody.get("master_record_ref") if custody else None,
            "request_bound_custody_receipt_id": custody.get("custody_receipt_id") if custody else None,
        }
    except Exception as exc:
        return {**base, "request_bound_validation_error": str(exc)}


def _blocked_result(exc: Exception) -> dict[str, Any]:
    return {
        "schema": "stegverse.sv002-rerun-callable-result/v1",
        "goal_task_id": GOAL_TASK_ID,
        "cosv_id": COSV_ID,
        "state": "BLOCKED",
        "reason": str(exc),
        **_request_bound_evidence(),
        "principal_execution_claimed": False,
    }


def build_frozen_request() -> tuple[dict[str, Any], dict[str, Any]]:
    binding = _load(BINDING_PATH)
    expected = binding.get("expected_request") or {}
    required = {
        "schema_version",
        "request_class",
        "operation",
        "transport",
        "experiment_id",
        "source_organization_id",
        "manifest_id",
        "objective",
        "authority_effect_resolution",
        "knowledge_policy",
    }
    missing = sorted(required - set(expected))
    if missing:
        raise RuntimeError("expected_request incomplete: " + ",".join(missing))
    if expected["experiment_id"] != EXPERIMENT_ID or expected["operation"] != OPERATION:
        raise RuntimeError("frozen experiment binding mismatch")
    if binding.get("service_id") != DESTINATION_SERVICE:
        raise RuntimeError("self-characterization service mismatch")

    registry = _load(SERVICES_PATH)
    service = next(
        (row for row in registry.get("services", []) if row.get("service_id") == DESTINATION_SERVICE),
        None,
    )
    if not service or service.get("profile_status") != "ACTIVE":
        raise RuntimeError("self-characterization service not ACTIVE")
    if OPERATION not in (service.get("accepts") or []):
        raise RuntimeError("self-characterization operation not accepted")

    manifest = {
        "schema": "stegverse.external_organization.interaction_manifest.v1",
        "manifest_id": expected["manifest_id"],
        "experiment_id": expected["experiment_id"],
        "source_organization": {"organization_id": expected["source_organization_id"]},
        "target": {"entity_id": "StegVerse-002"},
        "operation": expected["operation"],
        "objective": expected["objective"],
        "knowledge_policy": expected["knowledge_policy"],
        "authority_transfer": False,
        "authority_effect_resolution": expected["authority_effect_resolution"],
    }
    manifest["manifest_sha256"] = _canonical_sha256(manifest)

    request = {
        "schema_version": expected["schema_version"],
        "request_class": expected["request_class"],
        "operation": expected["operation"],
        "transport": expected["transport"],
        "authority_transfer": False,
        "authority_effect_resolution": expected["authority_effect_resolution"],
        "payload": {"manifest": manifest},
        "bindings": {
            "experiment_id": expected["experiment_id"],
            "source_organization_id": expected["source_organization_id"],
            "target_entity_id": "StegVerse-002",
            "manifest_id": expected["manifest_id"],
            "manifest_sha256": manifest["manifest_sha256"],
        },
    }
    return request, manifest


def build_packet() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    request, manifest = build_frozen_request()
    task_binding = {
        "goal_task_id": GOAL_TASK_ID,
        "cosv_id": COSV_ID,
        "invocation_count": INVOCATION_COUNT,
        "experiment_id": EXPERIMENT_ID,
        "operation": OPERATION,
    }
    packet_seed = {
        "task_binding": task_binding,
        "manifest_sha256": manifest["manifest_sha256"],
        "destination_org": DESTINATION_ORG,
        "destination_service": DESTINATION_SERVICE,
    }
    packet_id = "SV002-RERUN-" + _canonical_sha256(packet_seed)[:24].upper()
    packet = K.build_packet(
        origin_org=ORIGIN_ORG,
        origin_service=ORIGIN_SERVICE,
        destination_org=DESTINATION_ORG,
        destination_service=DESTINATION_SERVICE,
        payload={"request": request, "task_binding": task_binding},
        transition_reference="sv002.self-characterization.rerun.v0.3",
        authority_effect="NONE_REQUEST_ONLY",
        packet_id=packet_id,
    )
    return packet, request, manifest


EPOCH_RETRY_ENTRYPOINT = ("resident-runtime/invoke_sv002_experiment_rerun.py (--hb-epoch, or "
                          + K.SUPPLIED_EPOCH_ENV + ")")


def _load_or_bind_frame(state_root: Path, hb_epoch: int) -> tuple[dict[str, Any], dict[str, Any]]:
    packet, request, manifest = build_packet()
    bound_path = state_root / "RERUN_REQUEST_BOUND.json"
    if bound_path.is_file():
        bound = _load(bound_path)
        frame = bound.get("frame")
        if not isinstance(frame, dict):
            raise RuntimeError("persisted REQUEST_BOUND frame missing")
        recovered = K.recover_packet(frame)
        if recovered != packet:
            raise RuntimeError("persisted REQUEST_BOUND packet mismatch")
        if bound.get("state") != "REQUEST_BOUND":
            raise RuntimeError("persisted request binding state mismatch")
        if bound.get("invocation_count") != INVOCATION_COUNT:
            raise RuntimeError("persisted invocation_count mismatch")
        return frame, bound

    frame = K.carrier_frame(packet, now_ns=K.epoch_now_ns(hb_epoch))
    bound = {
        "schema": "stegverse.sv002-rerun-request-bound/v1",
        "goal_task_id": GOAL_TASK_ID,
        "cosv_id": COSV_ID,
        "experiment_id": EXPERIMENT_ID,
        "operation": OPERATION,
        "invocation_count": INVOCATION_COUNT,
        "state": "REQUEST_BOUND",
        "packet_id": packet["packet_id"],
        "packet_sha256": frame["packet_sha256"],
        "request_sha256": "sha256:" + _canonical_sha256(request),
        "manifest_sha256": manifest["manifest_sha256"],
        "frame_sha256": frame["frame_sha256"],
        "frame": frame,
        "authority_effect": "NONE_REQUEST_BINDING_ONLY",
    }
    _write_once(bound_path, bound)
    return frame, bound


def invoke_once(hb_epoch: Any = None) -> dict[str, Any]:
    """Bind and submit the one rerun request, stamped at the supplied epoch.

    An absent or invalid epoch is refused six-field before the state root is
    created, so no frame or submission is written and no clock is read.
    """
    bad = [name for name in HOSTED if _truthy(os.environ.get(name))]
    if bad:
        raise RuntimeError("hosted execution prohibited: " + ",".join(bad))
    hb_epoch = K.supplied_epoch(K.caller_epoch(hb_epoch), retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)

    state_root = _state_root()
    state_root.mkdir(parents=True, exist_ok=True)
    frame, bound = _load_or_bind_frame(state_root, hb_epoch)
    custody = _custody_request_bound(state_root, bound)
    submission_path = state_root / "RERUN_REQUEST_SUBMISSION.json"

    if submission_path.is_file():
        prior = _load(submission_path)
        if prior.get("frame_sha256") != frame.get("frame_sha256"):
            raise RuntimeError("submission receipt frame mismatch")
        return {
            **prior,
            "state": "ALREADY_SUBMITTED_NO_SECOND_REQUEST",
            "request_bound_claimed": True,
            "request_bound_state": bound["state"],
            "goal_task_id": bound["goal_task_id"],
            "cosv_id": bound["cosv_id"],
            "experiment_id": bound["experiment_id"],
            "operation": bound["operation"],
            "invocation_count": bound["invocation_count"],
            "packet_id": bound["packet_id"],
            "packet_sha256": bound["packet_sha256"],
            "request_sha256": bound["request_sha256"],
            "manifest_sha256": bound["manifest_sha256"],
            "frame_sha256": bound["frame_sha256"],
            "request_bound_master_records_state": custody["state"],
            "request_bound_master_records_reconstruction_status": custody["reconstruction_status"],
            "request_bound_master_records_required_evidence_validation_status": custody["required_evidence_validation_status"],
            "request_bound_master_records_required_evidence_count": custody["required_evidence_count"],
            "request_bound_master_records_receipt_sha256": custody["receipt_sha256"],
            "request_bound_master_records_reconstructed_receipt_sha256": custody["reconstructed_receipt_sha256"],
            "request_bound_master_record_ref": custody["master_record_ref"],
            "request_bound_custody_receipt_id": custody["custody_receipt_id"],
        }

    gateway_url = os.environ.get("STEGVERSE_ORG_FEDERATION_GATEWAY_URL", "").strip()
    mesh_root_raw = os.environ.get("STEGVERSE_ORG_FEDERATION_ROOT", "").strip()
    if gateway_url:
        stored = GW.submit_frame(frame)
        if stored.get("state") != "PENDING":
            raise RuntimeError("shared federation gateway did not retain frame as PENDING")
        transport = "SHARED_SERVICE_GATEWAY"
        transport_evidence = {
            "gateway_state": stored.get("state"),
            "gateway_execution_authority": stored.get("gateway_execution_authority", "NONE"),
        }
    elif mesh_root_raw:
        mesh_root = Path(mesh_root_raw).expanduser().resolve()
        path = K.publish_frame(frame, root=mesh_root)
        transport = "LOCAL_SPOOL_SAME_HOST_FALLBACK"
        transport_evidence = {"frame_path": str(path)}
    else:
        raise RuntimeError(
            "existing federation publication edge not configured; "
            "set the already-defined shared gateway URL or same-host federation root"
        )

    submission = {
        "schema": "stegverse.sv002-rerun-request-submission/v1",
        "goal_task_id": GOAL_TASK_ID,
        "cosv_id": COSV_ID,
        "experiment_id": EXPERIMENT_ID,
        "operation": OPERATION,
        "invocation_count": INVOCATION_COUNT,
        "state": "SUBMITTED_EXISTING_FEDERATION_EDGE",
        "request_bound_claimed": True,
        "request_bound_state": "REQUEST_BOUND",
        "packet_sha256": bound["packet_sha256"],
        "request_sha256": bound["request_sha256"],
        "manifest_sha256": bound["manifest_sha256"],
        "request_bound_master_records_state": custody["state"],
        "request_bound_master_records_reconstruction_status": custody["reconstruction_status"],
        "request_bound_master_record_ref": custody["master_record_ref"],
        "request_bound_custody_receipt_id": custody["custody_receipt_id"],
        "packet_id": bound["packet_id"],
        "frame_sha256": bound["frame_sha256"],
        "transport": transport,
        "transport_evidence": transport_evidence,
        "submitted_at": f"hb-epoch:{hb_epoch}",
        "authority_effect": "NONE_SUBMISSION_ONLY",
    }
    _write_once(submission_path, submission)
    return submission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    # The raw text goes to the shared epoch rule.
    parser.add_argument("--hb-epoch", default=None)
    args = parser.parse_args(argv)
    try:
        result = invoke_once(args.hb_epoch)
    except ValueError as exc:
        # The six-field refusal of an absent or invalid epoch (each kernel has its own class).
        if not isinstance(getattr(exc, "refusal", None), dict):
            print(json.dumps(_blocked_result(exc), sort_keys=True))
            return 2
        print(json.dumps(exc.refusal, sort_keys=True))
        return 1
    except Exception as exc:
        print(json.dumps(_blocked_result(exc), sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
