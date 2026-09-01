#!/usr/bin/env python3
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path

KINDS=["INGRESS_ACCEPTED","DISPATCHED","CONSUMED","RESULT_BOUND","EGRESS_EMITTED"]
ROOT=Path(__file__).resolve().parents[2]

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def hid(prefix,v): return prefix+"-"+hashlib.sha256(canon(v)).hexdigest()[:24]
def load(path): return json.loads(Path(path).read_text())

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
    application_result=endpoint_result(env,svc,a.envelope)
    base={"packet_id":env["packet_id"],"service_id":svc["service_id"],"payload_hash":hashlib.sha256(canon(env["payload"])).hexdigest()}
    receipts=[]; prev=None
    for kind in KINDS:
        subject={**base,"kind":kind,"previous_receipt_id":prev}
        rid=hid(kind.lower(),subject)
        receipts.append({"kind":kind,"receipt_id":rid,"subject":svc["service_id"],"evidence_hash":hashlib.sha256(canon(subject)).hexdigest(),"previous_receipt_id":prev})
        prev=rid
    if svc.get("service_id")=="stegverse-002.self-characterization" and application_result.get("state_root"):
        state_root=Path(application_result["state_root"]).expanduser().resolve()
        if state_root.is_dir():
            boundary_bundle={
                "schema":"stegverse.self-characterization-org-boundary-receipts/v0.1",
                "experiment_id":"STEGVERSE-002-SELF-CHARACTERIZATION-001",
                "packet_id":env["packet_id"],
                "service_id":svc["service_id"],
                "payload_sha256":base["payload_hash"],
                "manifest_sha256":application_result.get("manifest_sha256"),
                "receipts":receipts,
                "authority_effect":env["transition"]["authority_effect"],
                "authority_transfer_assumed":False,
                "master_records_required":True,
            }
            boundary_bundle["bundle_sha256"]=hashlib.sha256(canon(boundary_bundle)).hexdigest()
            target=state_root/"ORG_BOUNDARY_RECEIPTS.json"
            if target.exists():
                if load(target)!=boundary_bundle: raise SystemExit("org-boundary-receipt-write-once-collision")
            else:
                target.write_text(json.dumps(boundary_bundle,indent=2,sort_keys=True)+"\n")
            application_result["org_boundary_receipts_path"]=str(target)
            application_result["org_boundary_receipts_sha256"]=boundary_bundle["bundle_sha256"]
    result={
        "schema_version":reg["organization"].lower().replace(" ","-")+".boundary-execution.v1",
        "packet_id":env["packet_id"],
        "organization":reg["organization"],
        "service_id":svc["service_id"],
        "consumed":application_result.get("state")!="BLOCKED",
        "application_result":application_result,
        "authority_effect":env["transition"]["authority_effect"],
        "receipts":receipts,
        "reconstruction":{"same_execution_required":True,"status":"PENDING_MASTER_RECORDS","terminal_receipt_id":prev}
    }
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"PASS","terminal_receipt_id":prev,"service_id":svc["service_id"]}))
if __name__=="__main__": main()
