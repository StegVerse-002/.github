#!/usr/bin/env python3
"""Resident-only SV002 pre-T0 readiness evaluator.

This script never executes the authentic principal. It performs a synthetic
cross-repository rehearsal against locally materialized repositories, then
optionally verifies live runtime identity + explicit resident-node eligibility
evidence and emits one PRE-T0 readiness receipt.
"""
from __future__ import annotations

import argparse, base64, copy, hashlib, importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path
from typing import Any

EXPERIMENT_ID="STEGVERSE-002-SELF-CHARACTERIZATION-001"
IMPLEMENTATION_VERSION="v0.9"
HOSTED_GUARDS=("GITHUB_ACTIONS","CI","RENDER","VERCEL","CF_PAGES","CLOUDFLARE_WORKERS")
LEGACY_MASTER_RECORDS_HANDOFF_RECEIPT="MASTER_RECORDS_CUSTODY_HANDOFF.json"
LEGACY_MASTER_RECORDS_RECORD_ESTABLISHED_FIELD="master_records_custody_established"
LEGACY_MASTER_RECORDS_OBSERVATION_SOURCE="MASTER_RECORDS_CUSTODY_ONLY"
FROZEN_SHA256={
 "experiments/self-characterization-001/EXPERIMENT_CONTRACT.v0.3.json":"b9b4745ec98417ae161930ff1cc39cadb90976b0cead29b1c53220fa9b2836a6",
 "experiments/self-characterization-001/EXPERIMENT_MANIFEST.v0.3.json":"15e78f576587450f5031e344f802bc233f5b57e7a1e391969578b8965b6b5678",
 "experiments/self-characterization-001/ENVIRONMENT_AVAILABILITY_MANIFEST.v0.2.json":"9d654a4e625c7a02c4860217aeca9284247fc7c72ca8e0f29761d50dad9bf560",
 "experiments/self-characterization-001/SUBJECT_IDENTITY_MANIFEST.v0.1.json":"97b00ee59e87ff0670e7b2150f529a2e7fcda92f800c2b2a08e304b38cf476b3",
 "experiments/self-characterization-001/ORGANIZATION_CAPABILITY_SNAPSHOT.v0.1.json":"a691449e40e87ffae8f6c51efde915bae1d35e491137aee18a734fc7ad5f2462",
 "experiments/self-characterization-001/EVIDENCE_RECONSTRUCTION_PROTOCOL.v0.2.json":"93c14ebecd53c1eb2069acf52d6df02e1b09376b968e292bbba511f38892272d",
 "tools/run_self_characterization_principal.py":"ae2d2bddb825dbadc7c00d5cdd29e0a9dc7a28931835fbf217c0a08b3c58af7e",
 "tools/verify_self_characterization_experiment.py":"ace3e95723e8b3b0fc34b18e2937db8ee37b6d5b2e5f25e7b2272c0bc5239e86",
 "tools/verify_self_characterization_runtime_identity.py":"13a51ee29fe90e0cd80e2fc82b4757a453a34d760ac737fa42b68439bc49f3bc",
}

def load_json(path:Path)->dict[str,Any]:
    v=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(v,dict): raise RuntimeError(f"object required:{path}")
    return v

def sha256_file(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_head(root:Path)->str:
    return subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()

def import_file(name:str,path:Path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"cannot import:{path}")
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

def run(cmd:list[str],cwd:Path,env:dict[str,str]|None=None)->subprocess.CompletedProcess[str]:
    return subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True,check=False,timeout=180)

def master_records_handoff_receipt_path(state:Path)->Path:
    path=state/"MASTER_RECORDS_ORGANIZATION_RECORD_HANDOFF.json"
    return path if path.is_file() else state/LEGACY_MASTER_RECORDS_HANDOFF_RECEIPT

def master_records_organization_record_established(app:dict[str,Any])->bool:
    return app.get("master_records_organization_record_established",app.get(LEGACY_MASTER_RECORDS_RECORD_ESTABLISHED_FIELD)) is True

def master_records_organization_record_only(source:Any)->bool:
    return source in ("MASTER_RECORDS_ORGANIZATION_RECORD_ONLY",LEGACY_MASTER_RECORDS_OBSERVATION_SOURCE)

def require_clean_principal_state(state_root:Path)->dict[str,Any]:
    blockers=[]
    for name in ("EXPERIMENT_EXECUTION_RECEIPT.json","S0.json","TRANSITION_RECEIPTS.live.jsonl"):
        if (state_root/name).exists(): blockers.append(name)
    return {"pass":not blockers,"state_root":str(state_root),"occupancy_blockers":blockers}

def verify_node_evidence(path:Path)->dict[str,Any]:
    e=load_json(path)
    required={
      "schema":"stegverse.resident-node-eligibility/v1",
      "declared":True,
      "eligible":True,
      "owned_or_federated_by_stegverse":True,
      "authority_effect":"NONE",
    }
    mismatches={k:{"expected":v,"actual":e.get(k)} for k,v in required.items() if e.get(k)!=v}
    if not isinstance(e.get("node_id"),str) or not e["node_id"].strip(): mismatches["node_id"]="missing"
    return {"pass":not mismatches,"mismatches":mismatches,"node_id":e.get("node_id"),"evidence":e}

def verify_runtime_identity(micro:Path, identity:Path)->dict[str,Any]:
    mod=import_file("sv002_runtime_identity_preflight",micro/"tools/verify_self_characterization_runtime_identity.py")
    value=load_json(identity)
    verified=mod.verify_runtime_identity(value,live=True,verify_ollama=True)
    return {
      "pass":True,
      "model_id":verified.get("model_id"),
      "endpoint":verified.get("endpoint"),
      "model_digest":verified.get("model_digest"),
      "runtime_digest":verified.get("runtime_digest"),
      "runtime_executable":verified.get("runtime_executable"),
      "process_id":verified.get("process_id"),
      "runtime_engine":verified.get("runtime_engine"),
      "identity_verified_live":verified.get("identity_verified_live"),
    }

def synthetic_rehearsal(roots:dict[str,Path])->dict[str,Any]:
    fixture_mod=import_file("sv002_reconstruction_fixture_pre_t0",roots["orchestration"]/"tests/test_sv002_self_characterization_reconstruction.py")
    org_kernel=import_file("sv002_org_kernel_pre_t0",roots["org"]/"org-kernel/kernel.py")
    monitoring=import_file("sv002_monitoring_pre_t0",roots["monitoring"]/"tools/project_ecosystem_transition_ledger.py")
    observer=import_file("sv002_observer_pre_t0",roots["labs"]/"scripts/serve_sv002_observation_intr_runtime.py")
    checks={};negative={}
    with tempfile.TemporaryDirectory(prefix="sv002-resident-rehearsal-") as td:
        tmp=Path(td);state=tmp/"state";state.mkdir()
        fixture_mod.SV002SelfCharacterizationReconstructionTests().build_artifacts(state,version="v0.3")
        mesh=tmp/"mesh";env=dict(os.environ);env["STEGVERSE_ORG_FEDERATION_ROOT"]=str(mesh)
        publisher=roots["org"]/"resident-runtime/submit_sv002_self_characterization_to_master_records.py"
        first=run(["python3",str(publisher),"--state-root",str(state)],roots["org"],env)
        if first.returncode: raise RuntimeError("organization-record publisher failed:"+first.stderr[-600:])
        handoff=load_json(master_records_handoff_receipt_path(state))
        second=run(["python3",str(publisher),"--state-root",str(state)],roots["org"],env)
        frames=sorted((mesh/"frames.d").glob("*.json"))
        checks["exactly_once_publication"]={
          "pass":second.returncode==0 and json.loads(second.stdout).get("state")=="ALREADY_PUBLISHED_NO_REPUBLISH" and len(frames)==1 and handoff.get("principal_rerun_required") is False,
          "frame_count":len(frames),
        }
        frame=load_json(frames[0]);packet=org_kernel.recover_packet(frame)
        packet_path=tmp/"packet.json";packet_path.write_text(json.dumps(packet,indent=2,sort_keys=True)+"\n")
        custody=tmp/"custody";mr_env=dict(os.environ)
        mr_env["MASTER_RECORDS_ORCHESTRATION_ROOT"]=str(roots["orchestration"])
        mr_env["STEGVERSE_MASTER_RECORDS_SV002_CUSTODY_ROOT"]=str(custody)
        out=tmp/"mr.json"
        boundary=roots["master"]/"org-boundary/runtime/process_boundary.py"
        done=run(["python3",str(boundary),"--envelope",str(packet_path),"--out",str(out)],roots["master"],mr_env)
        mr=load_json(out) if out.exists() else {};app=mr.get("application_result") or {}
        receipt=Path(str(app.get("reconstruction_receipt_path") or ""))
        checks["master_records_organization_record_reconstruction"]={
          "pass":done.returncode==0 and mr.get("consumed") is True and app.get("state")=="RECORDED_AND_RECONSTRUCTED" and master_records_organization_record_established(app) and receipt.is_file() and (app.get("reconstruction_receipt") or {}).get("status")=="PASS",
          "state":app.get("state"),
        }
        prior=os.environ.get("STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT")
        try:
            os.environ.pop("STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT",None)
            missing=observer.build_projection(tmp/"obs-missing",roots["micro"])
            os.environ["STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT"]=str(receipt)
            projected=observer.build_projection(tmp/"obs-pass",roots["micro"])
        finally:
            if prior is None: os.environ.pop("STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT",None)
            else: os.environ["STEGVERSE_SV002_MASTER_RECORDS_RECONSTRUCTION_RECEIPT"]=prior
        checks["organization_record_only_projection"]={
          "pass":missing.get("state",{}).get("master_records_reconstruction")=="NOT_OBSERVED" and master_records_organization_record_only(projected.get("observation_source")) and projected.get("state",{}).get("master_records_reconstruction")=="PASS" and bool(projected.get("artifacts",{}).get("ordered_transition_receipts")),
          "observation_source":projected.get("observation_source"),
        }
        monroot=tmp/"monitor";(monroot/"receipts").mkdir(parents=True)
        mon=monitoring.build_projection(monroot,receipt);ref=mon.get("sv002_self_characterization_reference") or {}
        checks["monitoring_sequence_reference"]={
          "pass":mon.get("custody_authority") is False and ref.get("status")=="PASS" and bool(ref.get("ordered_transition_receipts")) and bool(ref.get("repository_ledger_root")) and bool(ref.get("organization_ledger_root")),
        }
        site_js=(roots["site"]/"assets/sv002-observe.js").read_text()
        inv=load_json(roots["site"]/"data/sv002-viewer-evidence-invariants.v1.json")
        checks["viewer_verification_contract"]={
          "pass":"verifyRuntimeEvidenceProjection" in site_js and "repository ordered receipt root mismatch" in site_js and "organization ledger does not include repository root" in site_js and inv.get("cross_viewer_reconstructed_runtime_evidence_equality_required") is True,
        }
        def negative_case(name:str,mutator,fragment:str):
            bad=copy.deepcopy(packet);mutator(bad)
            p=tmp/(name+".json");o=tmp/(name+".out.json")
            p.write_text(json.dumps(bad,indent=2,sort_keys=True)+"\n")
            d=run(["python3",str(boundary),"--envelope",str(p),"--out",str(o)],roots["master"],mr_env)
            value=load_json(o) if o.exists() else {};a=value.get("application_result") or {};reason=str(a.get("reason") or "")
            negative[name]={"pass":a.get("state")=="BLOCKED" and fragment in reason,"reason":reason,"returncode":d.returncode}
        def bad_bytes(p):
            row=p["payload"]["artifacts"][0];raw=base64.b64decode(row["base64"]);row["base64"]=base64.b64encode(raw+b"x").decode()
        negative_case("altered_artifact_bytes",bad_bytes,"artifact digest mismatch")
        negative_case("wrong_run_id",lambda p:p["payload"].__setitem__("run_id","SV002-RUN-"+"f"*32),"run_id artifact binding mismatch")
        negative_case("wrong_organization_root",lambda p:p["payload"].__setitem__("organization_ledger_root_hash","0"*64),"organization ledger root handoff binding mismatch")
    return {"pass":all(v["pass"] for v in checks.values()) and all(v["pass"] for v in negative.values()),"checks":checks,"negative_cases":negative}

def main()->int:
    ap=argparse.ArgumentParser()
    for name in ("micro","org","master","orchestration","monitoring","labs","site","sdk"):
        ap.add_argument("--"+name,type=Path,required=True)
    ap.add_argument("--state-root",type=Path,required=True)
    ap.add_argument("--runtime-identity",type=Path)
    ap.add_argument("--resident-node-evidence",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    roots={n:getattr(a,n).expanduser().resolve() for n in ("micro","org","master","orchestration","monitoring","labs","site","sdk")}
    result={
      "schema":"stegverse.sv002-pre-t0-readiness/v1",
      "experiment_id":EXPERIMENT_ID,
      "experiment_condition_version":"v0.3",
      "implementation_version":IMPLEMENTATION_VERSION,
      "principal_executed":False,
      "authority_effect":"NONE",
      "hosted_environment_guard_clear":not any(os.getenv(k) for k in HOSTED_GUARDS),
      "repository_heads":{k:git_head(v) for k,v in roots.items()},
      "frozen_v03":{},
    }
    for rel,expected in FROZEN_SHA256.items():
        actual=sha256_file(roots["micro"]/rel);result["frozen_v03"][rel]={"expected":expected,"actual":actual,"pass":actual==expected}
    result["frozen_v03_pass"]=all(v["pass"] for v in result["frozen_v03"].values())
    result["synthetic_rehearsal"]=synthetic_rehearsal(roots)
    result["principal_state_clean"]=require_clean_principal_state(a.state_root.expanduser().resolve())
    result["resident_node"]=verify_node_evidence(a.resident_node_evidence.expanduser().resolve()) if a.resident_node_evidence else {"pass":False,"state":"NOT_OBSERVED"}
    try:
        result["runtime_identity"]=verify_runtime_identity(roots["micro"],a.runtime_identity.expanduser().resolve()) if a.runtime_identity else {"pass":False,"state":"NOT_OBSERVED"}
    except Exception as exc:
        result["runtime_identity"]={"pass":False,"state":"FAIL_CLOSED","reason":str(exc)}
    source_ready=result["frozen_v03_pass"] and result["synthetic_rehearsal"]["pass"] and result["hosted_environment_guard_clear"]
    runtime_ready=result["resident_node"]["pass"] and result["runtime_identity"]["pass"] and result["principal_state_clean"]["pass"]
    result["source_ready"]=source_ready
    result["runtime_ready"]=runtime_ready
    result["readiness_state"]="READY_FOR_T0" if source_ready and runtime_ready else ("SOURCE_READY_RUNTIME_PENDING" if source_ready else "FAIL_CLOSED_NOT_READY")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
    return 0 if result["readiness_state"]!="FAIL_CLOSED_NOT_READY" else 2

if __name__=="__main__": raise SystemExit(main())
