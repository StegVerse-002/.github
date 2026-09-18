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

from datetime import datetime, timezone
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


def _load_or_bind_frame(state_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
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

    frame = K.carrier_frame(packet)
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


def invoke_once() -> dict[str, Any]:
    bad = [name for name in HOSTED if _truthy(os.environ.get(name))]
    if bad:
        raise RuntimeError("hosted execution prohibited: " + ",".join(bad))

    state_root = _state_root()
    state_root.mkdir(parents=True, exist_ok=True)
    frame, bound = _load_or_bind_frame(state_root)
    submission_path = state_root / "RERUN_REQUEST_SUBMISSION.json"

    if submission_path.is_file():
        prior = _load(submission_path)
        if prior.get("frame_sha256") != frame.get("frame_sha256"):
            raise RuntimeError("submission receipt frame mismatch")
        return {
            **prior,
            "state": "ALREADY_SUBMITTED_NO_SECOND_REQUEST",
            "request_bound_state": bound["state"],
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
        "request_bound_state": "REQUEST_BOUND",
        "packet_id": bound["packet_id"],
        "frame_sha256": bound["frame_sha256"],
        "transport": transport,
        "transport_evidence": transport_evidence,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "authority_effect": "NONE_SUBMISSION_ONLY",
    }
    _write_once(submission_path, submission)
    return submission


def main() -> int:
    try:
        result = invoke_once()
    except Exception as exc:
        print(json.dumps({
            "schema": "stegverse.sv002-rerun-callable-result/v1",
            "goal_task_id": GOAL_TASK_ID,
            "cosv_id": COSV_ID,
            "state": "BLOCKED",
            "reason": str(exc),
            "request_bound_claimed": False,
            "principal_execution_claimed": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
