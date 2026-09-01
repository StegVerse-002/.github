#!/usr/bin/env python3
"""Publish the canonical SV002 self-characterization artifact set to Master Records.

This is an organization-local handoff. It does not re-run the principal, grant
authority, or treat publication as custody acceptance/reconstruction success.
"""
from __future__ import annotations

import argparse, base64, hashlib, importlib.util, json
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
EXPERIMENT_ID="STEGVERSE-002-SELF-CHARACTERIZATION-001"
HANDOFF_RECEIPT="MASTER_RECORDS_CUSTODY_HANDOFF.json"
REQUIRED=(
    "S0.json",
    "EXPERIMENT_EXECUTION_RECEIPT.json",
    "SELF_CHARACTERIZATION.md",
    "SELF_CHARACTERIZATION_FORMAL.json",
    "INTERACTION_RECEIPT_CHAIN.json",
    "TRANSITION_EFFECTS.json",
    "TRANSITION_RECEIPTS.json",
    "TRANSITION_RECEIPTS.live.jsonl",
    "ORG_BOUNDARY_RECEIPTS.json",
    "ORG_BOUNDARY_RECEIPTS.live.jsonl",
    "REPOSITORY_LEDGER_ROOT.json",
    "ORGANIZATION_LEDGER_ROOT.json",
)
spec=importlib.util.spec_from_file_location("org_kernel",ROOT/"org-kernel/kernel.py")
K=importlib.util.module_from_spec(spec);spec.loader.exec_module(K)

def canon(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def sha256_bytes(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def load(path:Path)->dict[str,Any]:
    v=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(v,dict): raise RuntimeError(f"expected object:{path}")
    return v

def artifact_bundle(state_root:Path)->tuple[list[dict[str,Any]],str,str]:
    missing=[name for name in REQUIRED if not (state_root/name).is_file()]
    if missing: raise RuntimeError("canonical artifact set incomplete:"+",".join(missing))
    s0=load(state_root/"S0.json")
    execution=load(state_root/"EXPERIMENT_EXECUTION_RECEIPT.json")
    if s0.get("experiment_id")!=EXPERIMENT_ID or execution.get("experiment_id")!=EXPERIMENT_ID:
        raise RuntimeError("experiment binding mismatch")
    if execution.get("schema")!="stegverse.self-characterization-execution-receipt/v0.3":
        raise RuntimeError("v0.3 execution receipt required")
    if execution.get("state")!="COMPLETED" or execution.get("principal_run_completed") is not True:
        raise RuntimeError("principal completion required before custody handoff")
    run_id=str(execution.get("run_id") or s0.get("run_id") or "")
    if not run_id.startswith("SV002-RUN-"): raise RuntimeError("run_id invalid")
    artifacts=[]
    for name in REQUIRED:
        raw=(state_root/name).read_bytes()
        artifacts.append({
            "name":name,
            "sha256":sha256_bytes(raw),
            "size":len(raw),
            "base64":base64.b64encode(raw).decode("ascii"),
        })
    root_hash=sha256_bytes(canon([
        {"name":a["name"],"sha256":a["sha256"],"size":a["size"]} for a in artifacts
    ]))
    return artifacts,root_hash,run_id

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--state-root",type=Path,required=True)
    args=ap.parse_args()
    state_root=args.state_root.expanduser().resolve()
    artifacts,artifact_set_sha256,run_id=artifact_bundle(state_root)
    receipt_path=state_root/HANDOFF_RECEIPT
    if receipt_path.is_file():
        prior=load(receipt_path)
        if prior.get("artifact_set_sha256")!=artifact_set_sha256 or prior.get("run_id")!=run_id:
            raise SystemExit("master-records-custody-handoff-write-once-collision")
        print(json.dumps({**prior,"state":"ALREADY_PUBLISHED_NO_REPUBLISH"},sort_keys=True))
        return 0
    org_root=load(state_root/"ORGANIZATION_LEDGER_ROOT.json")
    payload={
        "operation":"CUSTODY_SV002_SELF_CHARACTERIZATION",
        "experiment_id":EXPERIMENT_ID,
        "run_id":run_id,
        "artifact_set_sha256":artifact_set_sha256,
        "organization_ledger_root_hash":org_root.get("root_hash"),
        "artifacts":artifacts,
        "authority_transfer":False,
    }
    packet=K.build_packet(
        origin_org="StegVerse-002",
        origin_service="stegverse-002.self-characterization",
        destination_org="master-records",
        destination_service="master-records.sv002-self-characterization-reconstruction",
        payload=payload,
        transition_reference="sv002.self-characterization.master-records-custody.v1",
        authority_effect="NONE",
    )
    published=K.publish_packet(packet)
    receipt={
        "schema":"stegverse.sv002-master-records-custody-handoff/v1",
        "experiment_id":EXPERIMENT_ID,
        "run_id":run_id,
        "artifact_set_sha256":artifact_set_sha256,
        "organization_ledger_root_hash":org_root.get("root_hash"),
        "packet_id":packet["packet_id"],
        "frame_sha256":published["frame"]["frame_sha256"],
        "frame_path":published["path"],
        "state":"PUBLISHED_FOR_MASTER_RECORDS_CUSTODY",
        "principal_rerun_required":False,
        "authority_transfer":False,
        "authority_effect":"NONE",
    }
    receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
