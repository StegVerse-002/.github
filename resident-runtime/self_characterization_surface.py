#!/usr/bin/env python3
"""Organization-local AI self-characterization execution surface.

This module is intentionally organization-local. It accepts an already-admitted
InTr ingress envelope, validates the bound self-characterization request, resolves
an org-local AI entity binding, and invokes that entity's principal launcher on
the sovereign resident process. It does not create cross-organization routes,
mint transport authority, fetch source, or select another organization's entity.
"""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BINDINGS = ROOT / "resident-runtime" / "self-characterization"

def canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object: {path}")
    return value

def binding_path(entity_id: str) -> Path:
    safe = entity_id.lower().replace("_", "-")
    return BINDINGS / f"{safe}.json"

def validate_binding(binding: dict[str, Any], entity_id: str) -> None:
    if binding.get("schema") != "stegverse.org-ai-self-characterization-binding/v1":
        raise RuntimeError("binding schema mismatch")
    if binding.get("entity_id") != entity_id:
        raise RuntimeError("entity binding mismatch")
    org = str(binding.get("organization") or "")
    if not org or binding.get("execution_owner_repository") != f"{org}/.github":
        raise RuntimeError("self-characterization execution must be owned by entity organization .github")
    principal = binding.get("principal") or {}
    if principal.get("repository_organization") != org:
        raise RuntimeError("cross-organization principal execution prohibited")
    if binding.get("master_records_required") is not True:
        raise RuntimeError("Master Records custody/reconstruction must remain required")

def extract_request(envelope: dict[str, Any]) -> dict[str, Any]:
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("ingress payload missing")
    request = payload.get("request") if isinstance(payload.get("request"), dict) else payload
    if request.get("request_class") != "EXTERNAL_ORGANIZATION_INTERACTION":
        raise RuntimeError("request class mismatch")
    if request.get("transport") != "InTr":
        raise RuntimeError("transport mismatch")
    if request.get("operation") != "REQUEST_SELF_CHARACTERIZATION":
        raise RuntimeError("operation mismatch")
    if request.get("authority_transfer") is not False:
        raise RuntimeError("authority transfer prohibited")
    return request

def validate_manifest(request: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    expected = binding.get("expected_request") or {}
    payload = request.get("payload") or {}
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict):
        raise RuntimeError("bound interaction manifest missing")
    if request.get("schema_version") != expected.get("schema_version"):
        raise RuntimeError("request schema mismatch")
    if request.get("request_class") != expected.get("request_class"):
        raise RuntimeError("request class mismatch")
    if request.get("operation") != expected.get("operation") or manifest.get("operation") != expected.get("operation"):
        raise RuntimeError("operation mismatch")
    if request.get("transport") != expected.get("transport"):
        raise RuntimeError("transport mismatch")
    target = manifest.get("target") or {}
    entity_id = binding["entity_id"]
    if target.get("entity_id") != entity_id:
        raise RuntimeError("manifest target does not match org-local entity")
    if manifest.get("experiment_id") != expected.get("experiment_id"):
        raise RuntimeError("experiment binding mismatch")
    if (manifest.get("source_organization") or {}).get("organization_id") != expected.get("source_organization_id"):
        raise RuntimeError("source organization mismatch")
    if manifest.get("manifest_id") != expected.get("manifest_id"):
        raise RuntimeError("manifest id mismatch")
    if manifest.get("objective") != expected.get("objective"):
        raise RuntimeError("frozen objective mismatch")
    if manifest.get("authority_transfer") is not False or request.get("authority_transfer") is not False:
        raise RuntimeError("authority transfer prohibited")
    if manifest.get("authority_effect_resolution") != expected.get("authority_effect_resolution") or request.get("authority_effect_resolution") != expected.get("authority_effect_resolution"):
        raise RuntimeError("transition-effect semantics mismatch")
    policy = manifest.get("knowledge_policy") or {}
    if policy != expected.get("knowledge_policy"):
        raise RuntimeError("knowledge policy mismatch")
    body = dict(manifest)
    claimed = str(body.pop("manifest_sha256", ""))
    actual = hashlib.sha256(canon(body)).hexdigest()
    if claimed != actual:
        raise RuntimeError("manifest SHA-256 mismatch")
    bindings = request.get("bindings") or {}
    exact_bindings = {
        "experiment_id": expected.get("experiment_id"),
        "source_organization_id": expected.get("source_organization_id"),
        "target_entity_id": entity_id,
        "manifest_id": expected.get("manifest_id"),
        "manifest_sha256": claimed,
    }
    for key, value in exact_bindings.items():
        if bindings.get(key) != value:
            raise RuntimeError(f"bindings.{key} mismatch")
    return manifest

def repo_candidates(binding: dict[str, Any]) -> list[Path]:
    principal = binding["principal"]
    override_env = str(principal.get("root_env") or "")
    out: list[Path] = []
    if override_env and os.environ.get(override_env):
        out.append(Path(os.environ[override_env]).expanduser())
    org = principal["repository_organization"]
    repo = principal["repository_name"]
    home = Path(os.environ.get("HOME", str(Path.home())))
    out.extend([
        home / ".stegverse" / "repos" / org / repo,
        Path("/var/lib/stegverse/source") / org / repo,
        Path("/srv/stegverse/repos") / org / repo,
        Path("/opt/stegverse/repos") / org / repo,
    ])
    return [p.resolve() for p in out]

def resolve_principal_root(binding: dict[str, Any]) -> Path:
    principal = binding["principal"]
    required = [principal["launcher"], principal["contract"]]
    for root in repo_candidates(binding):
        if root.is_dir() and all((root / rel).is_file() for rel in required):
            return root
    raise RuntimeError("org-local principal source not materialized")

def run(envelope_path: Path, entity_id: str) -> dict[str, Any]:
    envelope = load(envelope_path)
    if envelope.get("direction") != "INGRESS":
        raise RuntimeError("self-characterization surface consumes ingress only")
    binding = load(binding_path(entity_id))
    validate_binding(binding, entity_id)
    destination = envelope.get("destination") or {}
    if destination.get("org") != binding["organization"]:
        raise RuntimeError("wrong destination organization")
    if destination.get("service") != binding["service_id"]:
        raise RuntimeError("wrong destination service")
    request = extract_request(envelope)
    manifest = validate_manifest(request, binding)
    root = resolve_principal_root(binding)
    principal = binding["principal"]
    env = dict(os.environ)
    causal_ingress = {
        "schema": "stegverse.self-characterization-causal-ingress/v0.1",
        "packet_id": str(envelope.get("packet_id") or ""),
        "origin_organization": str((envelope.get("origin") or {}).get("org") or ""),
        "origin_service": str((envelope.get("origin") or {}).get("service") or ""),
        "destination_organization": str((envelope.get("destination") or {}).get("org") or ""),
        "destination_service": str((envelope.get("destination") or {}).get("service") or ""),
        "experiment_id": str(manifest.get("experiment_id") or ""),
        "operation": str(manifest.get("operation") or ""),
        "manifest_id": str(manifest.get("manifest_id") or ""),
        "manifest_sha256": str(manifest.get("manifest_sha256") or ""),
        "source_organization_id": str((manifest.get("source_organization") or {}).get("organization_id") or ""),
        "objective": str(manifest.get("objective") or ""),
    }
    env["STEGVERSE_SELF_CHARACTERIZATION_CAUSAL_INGRESS_JSON"] = json.dumps(causal_ingress, sort_keys=True, separators=(",", ":"))
    state_root=Path(env.get("STEGVERSE_SELF_CHAR_STATE_ROOT",str(Path.home()/".stegverse/self-characterization-001"))).expanduser().resolve()
    completed = subprocess.run(
        ["python3", str(root / principal["launcher"])],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=int(binding.get("timeout_seconds", 1900)),
    )
    principal_status=None
    for line in reversed(completed.stdout.splitlines()):
        try:
            candidate=json.loads(line)
            if isinstance(candidate,dict):
                principal_status=candidate
                break
        except Exception:
            continue
    replay_without_rerun=bool(isinstance(principal_status,dict) and principal_status.get("state")=="ALREADY_COMPLETED_NO_RERUN")
    result = {
        "schema": "stegverse.org-ai-self-characterization-execution/v1",
        "organization": binding["organization"],
        "entity_id": entity_id,
        "service_id": binding["service_id"],
        "ingress_packet_id": envelope.get("packet_id"),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "principal_repository": f"{principal['repository_organization']}/{principal['repository_name']}",
        "state_root": str(state_root),
        "principal_execution_attempted": not replay_without_rerun,
        "principal_replay_without_rerun": replay_without_rerun,
        "principal_status": principal_status,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-8192:],
        "stderr_tail": completed.stderr[-8192:],
        "master_records_required": True,
        "authority_transfer_assumed": False,
        "authority_effect_resolution": "DERIVED_FROM_APPLICABLE_TRANSITION_ELEMENTS",
    }
    return result

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingress", type=Path, required=True)
    ap.add_argument("--entity-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        result = run(args.ingress.resolve(), args.entity_id)
    except Exception as exc:
        result = {
            "schema": "stegverse.org-ai-self-characterization-execution/v1",
            "entity_id": args.entity_id,
            "state": "BLOCKED",
            "reason": str(exc),
            "principal_execution_attempted": False,
            "master_records_required": True,
            "authority_effect": "NONE_BLOCKED",
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 2
    result["state"] = "COMPLETED" if result["returncode"] == 0 else "ATTEMPT_RECORDED"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["returncode"] == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
