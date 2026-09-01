#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "STEGVERSE-002-SELF-CHARACTERIZATION-001"

FROZEN_SHA256 = {
    "experiments/self-characterization-001/EXPERIMENT_CONTRACT.v0.3.json": "b9b4745ec98417ae161930ff1cc39cadb90976b0cead29b1c53220fa9b2836a6",
    "experiments/self-characterization-001/EXPERIMENT_MANIFEST.v0.3.json": "15e78f576587450f5031e344f802bc233f5b57e7a1e391969578b8965b6b5678",
    "experiments/self-characterization-001/ENVIRONMENT_AVAILABILITY_MANIFEST.v0.2.json": "9d654a4e625c7a02c4860217aeca9284247fc7c72ca8e0f29761d50dad9bf560",
    "experiments/self-characterization-001/SUBJECT_IDENTITY_MANIFEST.v0.1.json": "97b00ee59e87ff0670e7b2150f529a2e7fcda92f800c2b2a08e304b38cf476b3",
    "experiments/self-characterization-001/ORGANIZATION_CAPABILITY_SNAPSHOT.v0.1.json": "a691449e40e87ffae8f6c51efde915bae1d35e491137aee18a734fc7ad5f2462",
    "experiments/self-characterization-001/EVIDENCE_RECONSTRUCTION_PROTOCOL.v0.2.json": "93c14ebecd53c1eb2069acf52d6df02e1b09376b968e292bbba511f38892272d",
    "tools/run_self_characterization_principal.py": "ae2d2bddb825dbadc7c00d5cdd29e0a9dc7a28931835fbf217c0a08b3c58af7e",
    "tools/verify_self_characterization_experiment.py": "ace3e95723e8b3b0fc34b18e2937db8ee37b6d5b2e5f25e7b2272c0bc5239e86",
    "tools/verify_self_characterization_runtime_identity.py": "13a51ee29fe90e0cd80e2fc82b4757a453a34d760ac737fa42b68439bc49f3bc",
}

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=False, timeout=180)

def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"object required: {path}")
    return value

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--micro", type=Path, required=True)
    ap.add_argument("--org", type=Path, required=True)
    ap.add_argument("--master-github", type=Path, required=True)
    ap.add_argument("--orchestration", type=Path, required=True)
    ap.add_argument("--monitoring", type=Path, required=True)
    ap.add_argument("--labs-github", type=Path, required=True)
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--sdk", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    roots = {k: getattr(args, k).resolve() for k in (
        "micro", "org", "master_github", "orchestration", "monitoring", "labs_github", "site", "sdk"
    )}
    report: dict[str, Any] = {
        "schema": "stegverse.sv002-pre-t0-cross-repo-rehearsal/v1",
        "experiment_id": EXPERIMENT_ID,
        "experiment_condition": "v0.3 FROZEN",
        "evaluation_kind": "SYNTHETIC_NON_PRINCIPAL_VALIDATION_ONLY",
        "authority_effect": "NONE",
        "principal_executed": False,
        "repository_heads": {k: git_head(v) for k, v in roots.items()},
        "checks": {},
        "negative_cases": {},
    }

    frozen = {}
    for rel, expected in FROZEN_SHA256.items():
        actual = sha256_file(roots["micro"] / rel)
        frozen[rel] = {"expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected}
    report["checks"]["frozen_v03_bytes"] = {
        "pass": all(v["pass"] for v in frozen.values()),
        "artifacts": frozen,
    }
    if not report["checks"]["frozen_v03_bytes"]["pass"]:
        raise RuntimeError("frozen v0.3 byte check failed")

    version_domains = (roots["org"] / "docs/SV002_EXPERIMENT_VERSION_DOMAINS.md").read_text(encoding="utf-8")
    report["checks"]["version_domain"] = {
        "pass": "experiment condition: v0.3" in version_domains and "implementation: v0.8" in version_domains,
        "v03_frozen_declared": "v0.3" in version_domains and "FROZEN" in version_domains,
        "v08_implementation_declared": "v0.8" in version_domains,
    }
    if not report["checks"]["version_domain"]["pass"]:
        raise RuntimeError("version-domain declaration mismatch")

    fixture_mod = load_module(
        "sv002_reconstruction_fixture",
        roots["orchestration"] / "tests/test_sv002_self_characterization_reconstruction.py",
    )
    org_kernel = load_module("sv002_org_kernel_eval", roots["org"] / "org-kernel/kernel.py")
    monitoring_mod = load_module(
        "sv002_monitoring_eval",
        roots["monitoring"] / "tools/project_ecosystem_transition_ledger.py",
    )
    labs_obs = load_module(
        "sv002_labs_observation_eval",
        roots["labs_github"] / "scripts/serve_sv002_observation_intr_runtime.py",
    )

    with tempfile.TemporaryDirectory(prefix="sv002-pre-t0-") as td:
        temp = Path(td)
        state_root = temp / "principal-state"
        state_root.mkdir()
        fixture = fixture_mod.SV002SelfCharacterizationReconstructionTests()
        fixture.build_artifacts(state_root, version="v0.3")

        mesh = temp / "mesh"
        env = dict(os.environ)
        env["STEGVERSE_ORG_FEDERATION_ROOT"] = str(mesh)

        publisher = roots["org"] / "resident-runtime/submit_sv002_self_characterization_to_master_records.py"
        first = run(["python3", str(publisher), "--state-root", str(state_root)], cwd=roots["org"], env=env)
        if first.returncode != 0:
            raise RuntimeError("publisher failed: " + first.stderr[-1000:])
        handoff = load_json(state_root / "MASTER_RECORDS_CUSTODY_HANDOFF.json")
        frames = sorted((mesh / "frames.d").glob("*.json"))
        if len(frames) != 1:
            raise RuntimeError(f"expected exactly one federation frame, got {len(frames)}")

        second = run(["python3", str(publisher), "--state-root", str(state_root)], cwd=roots["org"], env=env)
        if second.returncode != 0:
            raise RuntimeError("publisher replay failed closed incorrectly: " + second.stderr[-1000:])
        second_value = json.loads(second.stdout)
        frames_after = sorted((mesh / "frames.d").glob("*.json"))
        report["checks"]["exactly_once_publication"] = {
            "pass": second_value.get("state") == "ALREADY_PUBLISHED_NO_REPUBLISH" and len(frames_after) == 1,
            "first_state": handoff.get("state"),
            "second_state": second_value.get("state"),
            "frame_count": len(frames_after),
            "principal_rerun_required": handoff.get("principal_rerun_required"),
        }
        if not report["checks"]["exactly_once_publication"]["pass"]:
            raise RuntimeError("exactly-once publication check failed")

        frame = load_json(frames[0])
        packet = org_kernel.recover_packet(frame)
        packet_path = temp / "master-records-packet.json"
        packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        custody_root = temp / "master-records-custody"
        mr_env = dict(os.environ)
        mr_env["MASTER_RECORDS_ORCHESTRATION_ROOT"] = str(roots["orchestration"])
        mr_env["STEGVERSE_MASTER_RECORDS_SV002_CUSTODY_ROOT"] = str(custody_root)
        mr_out = temp / "master-records-boundary.json"
        boundary = roots["master_github"] / "org-boundary/runtime/process_boundary.py"
        consumed = run(
            ["python3", str(boundary), "--envelope", str(packet_path), "--out", str(mr_out)],
            cwd=roots["master_github"],
            env=mr_env,
        )
        if consumed.returncode != 0 or not mr_out.is_file():
            raise RuntimeError("Master Records boundary rehearsal failed: " + consumed.stderr[-1200:])
        mr_result = load_json(mr_out)
        app = mr_result.get("application_result") or {}
        reconstruction_receipt = Path(str(app.get("reconstruction_receipt_path") or ""))
        positive_pass = (
            mr_result.get("consumed") is True
            and app.get("state") == "RECORDED_AND_RECONSTRUCTED"
            and app.get("master_records_custody_established") is True
            and reconstruction_receipt.is_file()
            and (app.get("reconstruction_receipt") or {}).get("status") == "PASS"
            and (app.get("reconstruction_receipt") or {}).get("reconstruction") == "PASS"
        )
        report["checks"]["cross_repo_custody_reconstruction"] = {
            "pass": positive_pass,
            "boundary_consumed": mr_result.get("consumed"),
            "intake_state": app.get("state"),
            "master_records_custody_established": app.get("master_records_custody_established"),
            "reconstruction_status": (app.get("reconstruction_receipt") or {}).get("status"),
            "reconstruction": (app.get("reconstruction_receipt") or {}).get("reconstruction"),
            "custody_root": app.get("custody_root"),
            "reconstruction_receipt_path": app.get("reconstruction_receipt_path"),
        }
        if not positive_pass:
            raise RuntimeError("cross-repo custody/reconstruction did not PASS")

        prior_source = os.environ.get("STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT")
        try:
            os.environ.pop("STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT", None)
            missing_projection = labs_obs.build_projection(temp / "observer-missing", roots["micro"])
            os.environ["STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT"] = str(reconstruction_receipt)
            pass_projection = labs_obs.build_projection(temp / "observer-pass", roots["micro"])
        finally:
            if prior_source is None:
                os.environ.pop("STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT", None)
            else:
                os.environ["STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT"] = prior_source

        projection_pass = (
            missing_projection.get("state", {}).get("master_records_reconstruction") == "NOT_OBSERVED"
            and pass_projection.get("observation_source") == "MASTER_RECORDS_CUSTODY_ONLY"
            and pass_projection.get("state", {}).get("master_records_reconstruction") == "PASS"
            and bool(pass_projection.get("artifacts", {}).get("ordered_transition_receipts"))
            and bool(pass_projection.get("artifacts", {}).get("repository_ledger_root"))
            and bool(pass_projection.get("artifacts", {}).get("organization_ledger_root"))
        )
        report["checks"]["public_projection_from_custody_only"] = {
            "pass": projection_pass,
            "missing_custody_state": missing_projection.get("state", {}).get("master_records_reconstruction"),
            "observation_source": pass_projection.get("observation_source"),
            "reconstruction_state": pass_projection.get("state", {}).get("master_records_reconstruction"),
            "ordered_transition_count": len(pass_projection.get("artifacts", {}).get("ordered_transition_receipts") or []),
        }
        if not projection_pass:
            raise RuntimeError("public projection custody-only rehearsal failed")

        monitoring_root = temp / "monitoring"
        (monitoring_root / "receipts").mkdir(parents=True)
        monitor = monitoring_mod.build_projection(monitoring_root, reconstruction_receipt)
        ref = monitor.get("sv002_self_characterization_reference") or {}
        monitor_pass = (
            monitor.get("custody_authority") is False
            and ref.get("status") == "PASS"
            and bool(ref.get("ordered_transition_receipts"))
            and bool(ref.get("repository_ledger_root"))
            and bool(ref.get("organization_ledger_root"))
        )
        report["checks"]["monitoring_independent_sequence_reference"] = {
            "pass": monitor_pass,
            "custody_authority": monitor.get("custody_authority"),
            "reference_status": ref.get("status"),
            "ordered_transition_count": len(ref.get("ordered_transition_receipts") or []),
        }
        if not monitor_pass:
            raise RuntimeError("monitoring sequence reference rehearsal failed")

        site_js = (roots["site"] / "assets/sv002-observe.js").read_text(encoding="utf-8")
        invariant = load_json(roots["site"] / "data/sv002-viewer-evidence-invariants.v1.json")
        site_pass = (
            "verifyRuntimeEvidenceProjection" in site_js
            and "repository ordered receipt root mismatch" in site_js
            and "organization ledger does not include repository root" in site_js
            and invariant.get("cross_viewer_reconstructed_runtime_evidence_equality_required") is True
            and invariant.get("cross_viewer_projection_hash_equality_required") is False
        )
        report["checks"]["viewer_verification_contract"] = {
            "pass": site_pass,
            "viewer_invariant_count": len(invariant.get("viewer_invariant_runtime_evidence") or []),
            "viewer_bound_count": len(invariant.get("viewer_bound_observation_evidence") or []),
        }
        if not site_pass:
            raise RuntimeError("viewer verification contract check failed")

        def master_negative(mutator, name: str, expected_fragment: str) -> None:
            bad = copy.deepcopy(packet)
            mutator(bad)
            p = temp / f"{name}.json"
            o = temp / f"{name}.out.json"
            p.write_text(json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            done = run(["python3", str(boundary), "--envelope", str(p), "--out", str(o)], cwd=roots["master_github"], env=mr_env)
            value = load_json(o) if o.is_file() else {}
            app_value = value.get("application_result") or {}
            reason = str(app_value.get("reason") or "")
            passed = app_value.get("state") == "BLOCKED" and expected_fragment in reason
            report["negative_cases"][name] = {
                "pass": passed,
                "boundary_returncode": done.returncode,
                "state": app_value.get("state"),
                "reason": reason,
            }
            if not passed:
                raise RuntimeError(f"negative case {name} did not fail closed as expected: {reason}")

        def mutate_artifact_digest(p: dict[str, Any]) -> None:
            rows = p["payload"]["artifacts"]
            raw = base64.b64decode(rows[0]["base64"])
            rows[0]["base64"] = base64.b64encode(raw + b"x").decode("ascii")

        master_negative(mutate_artifact_digest, "altered_artifact_bytes", "artifact digest mismatch")
        master_negative(lambda p: p["payload"].__setitem__("run_id", "SV002-RUN-" + "f" * 32), "wrong_run_id", "run_id artifact binding mismatch")
        master_negative(lambda p: p["payload"].__setitem__("organization_ledger_root_hash", "0" * 64), "wrong_organization_root", "organization ledger root handoff binding mismatch")

    report["overall"] = "PASS" if (
        all(v.get("pass") for v in report["checks"].values())
        and all(v.get("pass") for v in report["negative_cases"].values())
    ) else "FAIL"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall"] == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
