#!/usr/bin/env python3
import argparse, hashlib, json, os, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path

KINDS=["INGRESS_ACCEPTED","DISPATCHED","CONSUMED","RESULT_BOUND","EGRESS_EMITTED"]
ROOT=Path(__file__).resolve().parents[2]

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")
def hid(prefix,v): return prefix+"-"+hashlib.sha256(canon(v)).hexdigest()[:24]
def load(path): return json.loads(Path(path).read_text())
def now(): return datetime.now(timezone.utc).isoformat()

def make_receipt(kind, base, previous_receipt_id, *, disposition=None):
    subject={**base,"kind":kind,"previous_receipt_id":previous_receipt_id}
    rid=hid(kind.lower(),subject)
    row={
        "kind":kind,
        "receipt_id":rid,
        "subject":base["service_id"],
        "evidence_hash":hashlib.sha256(canon(subject)).hexdigest(),
        "previous_receipt_id":previous_receipt_id,
        "observed_at":now(),
    }
    if disposition is not None:
        row["application_disposition"]=disposition
    return row

def append_live_receipt(path, receipt):
    if path is None:
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as handle:
        handle.write(json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n")

def digest(v): return hashlib.sha256(canon(v)).hexdigest()

def build_org_ledger_root(state_root, boundary_bundle):
    repo_path=state_root/"REPOSITORY_LEDGER_ROOT.json"
    s0_path=state_root/"S0.json"
    if not repo_path.is_file() or not s0_path.is_file():
        raise SystemExit("hierarchical-ledger-descendant-root-missing")
    repo_root=load(repo_path); s0=load(s0_path)
    run_id=s0.get("run_id")
    if not isinstance(run_id,str) or not run_id:
        raise SystemExit("hierarchical-ledger-run-id-missing")
    child={
        "scope_type":"repository",
        "scope_id":repo_root.get("scope_id"),
        "root_id":repo_root.get("root_id"),
        "root_hash":repo_root.get("root_hash"),
        "range":repo_root.get("range"),
    }
    receipts=boundary_bundle.get("receipts") or []
    if not receipts:
        raise SystemExit("hierarchical-ledger-org-receipts-missing")
    ordered={
        "children":[child],
        "organization_receipts":[
            {"kind":row.get("kind"),"receipt_id":row.get("receipt_id"),"evidence_hash":row.get("evidence_hash")}
            for row in receipts
        ],
    }
    ordered_root_hash=digest(ordered)
    body={
        "schema_version":"stegverse.hierarchical-ledger-root/v1",
        "scope_type":"organization",
        "scope_id":"StegVerse-002",
        "root_id":"ORG-"+digest({"run_id":run_id,"ordered_root_hash":ordered_root_hash})[:32].upper(),
        "generated_at":receipts[-1].get("observed_at") or now(),
        "run_id":run_id,
        "previous_root_hash":None,
        "range":{
            "first_receipt_id":receipts[0].get("receipt_id"),
            "last_receipt_id":receipts[-1].get("receipt_id"),
            "receipt_count":len(receipts),
            "ordered_root_hash":ordered_root_hash,
        },
        "children":[child],
        "reconstruction":{
            "status":"NOT_ATTEMPTED",
            "descendant_resolution_required":True,
            "reference":"ORG_BOUNDARY_RECEIPTS.json",
        },
    }
    return {**body,"root_hash":digest(body)}

def endpoint_result(env,svc,envelope_path):
    adapter=svc.get("endpoint_adapter")
    if svc.get("service_id")=="stegverse-002.self-characterization" and adapter:
        binding=load(ROOT/svc["entity_binding"])
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"self-characterization-result.json"
            completed=subprocess.run(
                ["python3",str(ROOT/adapter),"--ingress",str(Path(envelope_path).resolve()),"--entity-id",binding["entity_id"],"--out",str(out)],
                cwd=ROOT,capture_output=True,text=True,check=False,timeout=int(binding.get("timeout_seconds",1900))+30
            )
            if not out.is_file():
                raise SystemExit("endpoint-adapter-produced-no-result")
            result=load(out)
            result["adapter_returncode"]=completed.returncode
            return result
    if svc.get("boundary_role")=="INTERNAL_ENDPOINT" and adapter:
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"endpoint-result.json"
            completed=subprocess.run(
                ["python3",str(ROOT/adapter),"--ingress",str(Path(envelope_path).resolve()),"--out",str(out)],
                cwd=ROOT,capture_output=True,text=True,check=False,timeout=120
            )
            if not out.is_file():
                raise SystemExit("endpoint-adapter-produced-no-result")
            result=load(out)
            result["adapter_returncode"]=completed.returncode
            return result
    if svc.get("boundary_role")=="BOUNDARY_LOCAL_DIAGNOSTIC":
        return {"echo":env["payload"]}
    raise SystemExit("endpoint-adapter-not-installed")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--envelope",required=True)
    ap.add_argument("--registry",default="org-boundary/registry/services.json")
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    env=load(a.envelope); reg=load(a.registry)
    req=["schema_version","packet_id","direction","origin","destination","carrier","intr_profile","transition","payload","evidence"]
    miss=[k for k in req if k not in env]
    if miss: raise SystemExit("missing:"+",".join(miss))
    if env["destination"]["org"]!=reg["organization"]: raise SystemExit("wrong-destination-org")
    svc=next((s for s in reg["services"] if s["service_id"]==env["destination"]["service"]),None)
    if not svc: raise SystemExit("unknown-service")
    base={"packet_id":env["packet_id"],"service_id":svc["service_id"],"payload_hash":hashlib.sha256(canon(env["payload"])).hexdigest()}
    live_path=None
    prior_boundary_bundle=None
    if svc.get("service_id")=="stegverse-002.self-characterization":
        state_root=Path(os.environ.get("STEGVERSE_SELF_CHAR_STATE_ROOT",str(Path.home()/".stegverse/self-characterization-001"))).expanduser().resolve()
        state_root.mkdir(parents=True,exist_ok=True)
        live_path=state_root/"ORG_BOUNDARY_RECEIPTS.live.jsonl"
        prior_bundle_path=state_root/"ORG_BOUNDARY_RECEIPTS.json"
        if live_path.exists():
            if not prior_bundle_path.is_file():
                raise SystemExit("org-boundary-partial-live-history-without-terminal-bundle")
            prior_boundary_bundle=load(prior_bundle_path)
            if prior_boundary_bundle.get("packet_id")!=env["packet_id"] or prior_boundary_bundle.get("payload_sha256")!=base["payload_hash"]:
                raise SystemExit("org-boundary-receipt-write-once-collision")

    receipts=[]; prev=None
    if prior_boundary_bundle is None:
        ingress_receipt=make_receipt("INGRESS_ACCEPTED",base,prev)
        receipts.append(ingress_receipt); prev=ingress_receipt["receipt_id"]; append_live_receipt(live_path,ingress_receipt)
        dispatched_receipt=make_receipt("DISPATCHED",base,prev)
        receipts.append(dispatched_receipt); prev=dispatched_receipt["receipt_id"]; append_live_receipt(live_path,dispatched_receipt)

    application_result=endpoint_result(env,svc,a.envelope)
    disposition=str(application_result.get("state") or "UNKNOWN")
    if prior_boundary_bundle is not None:
        receipts=list(prior_boundary_bundle.get("receipts") or [])
        prev=receipts[-1].get("receipt_id") if receipts else None
    else:
        consumed_receipt=make_receipt("CONSUMED",base,prev,disposition=disposition)
        receipts.append(consumed_receipt); prev=consumed_receipt["receipt_id"]; append_live_receipt(live_path,consumed_receipt)
        result_receipt=make_receipt("RESULT_BOUND",base,prev,disposition=disposition)
        receipts.append(result_receipt); prev=result_receipt["receipt_id"]; append_live_receipt(live_path,result_receipt)
        egress_receipt=make_receipt("EGRESS_EMITTED",base,prev,disposition=disposition)
        receipts.append(egress_receipt); prev=egress_receipt["receipt_id"]; append_live_receipt(live_path,egress_receipt)
    if svc.get("service_id")=="stegverse-002.self-characterization" and application_result.get("state_root"):
        state_root=Path(application_result["state_root"]).expanduser().resolve()
        if state_root.is_dir():
            target=state_root/"ORG_BOUNDARY_RECEIPTS.json"
            if prior_boundary_bundle is None:
                boundary_bundle={
                    "schema":"stegverse.self-characterization-org-boundary-receipts/v0.2",
                    "experiment_id":"STEGVERSE-002-SELF-CHARACTERIZATION-001",
                    "packet_id":env["packet_id"],
                    "service_id":svc["service_id"],
                    "payload_sha256":base["payload_hash"],
                    "manifest_sha256":application_result.get("manifest_sha256"),
                    "receipts":receipts,
                    "application_disposition":str(application_result.get("state") or "UNKNOWN"),
                    "live_receipt_log":"ORG_BOUNDARY_RECEIPTS.live.jsonl",
                    "authority_effect":env["transition"]["authority_effect"],
                    "authority_transfer_assumed":False,
                    "master_records_required":True,
                }
                boundary_bundle["bundle_sha256"]=hashlib.sha256(canon(boundary_bundle)).hexdigest()
                if target.exists():
                    if load(target)!=boundary_bundle: raise SystemExit("org-boundary-receipt-write-once-collision")
                else:
                    target.write_text(json.dumps(boundary_bundle,indent=2,sort_keys=True)+"\n")
            else:
                boundary_bundle=prior_boundary_bundle
                if not target.is_file() or load(target)!=boundary_bundle:
                    raise SystemExit("org-boundary-prior-bundle-unavailable")
            application_result["org_boundary_receipts_path"]=str(target)
            application_result["org_boundary_receipts_sha256"]=boundary_bundle["bundle_sha256"]
            org_root_path=state_root/"ORGANIZATION_LEDGER_ROOT.json"
            if org_root_path.is_file():
                organization_ledger_root=load(org_root_path)
            else:
                organization_ledger_root=build_org_ledger_root(state_root,boundary_bundle)
                org_root_path.write_text(json.dumps(organization_ledger_root,indent=2,sort_keys=True)+"\n")
            application_result["organization_ledger_root_path"]=str(org_root_path)
            application_result["organization_ledger_root_hash"]=organization_ledger_root["root_hash"]
    result={
        "schema_version":reg["organization"].lower().replace(" ","-")+".boundary-execution.v1",
        "packet_id":env["packet_id"],
        "organization":reg["organization"],
        "service_id":svc["service_id"],
        "consumed":application_result.get("state")!="BLOCKED",
        "application_completed":application_result.get("state")=="COMPLETED",
        "application_disposition":application_result.get("state"),
        "application_result":application_result,
        "authority_effect":env["transition"]["authority_effect"],
        "receipts":receipts,
        "reconstruction":{
            "same_execution_required":True,
            "status":"RECONSTRUCTED" if svc.get("boundary_role")=="BOUNDARY_LOCAL_DIAGNOSTIC" else "PENDING_MASTER_RECORDS",
            "terminal_receipt_id":prev
        }
    }
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"PASS","terminal_receipt_id":prev,"service_id":svc["service_id"]}))
if __name__=="__main__": main()
