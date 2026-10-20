#!/usr/bin/env python3
import json, os, subprocess, tempfile
from pathlib import Path
reg=json.loads(Path("org-boundary/registry/services.json").read_text()); svc=next(s["service_id"] for s in reg["services"] if s.get("boundary_role")=="BOUNDARY_LOCAL_DIAGNOSTIC")
env={"schema_version":"test","packet_id":"pkt-001","direction":"INGRESS","origin":{"org":"peer","service":"peer.boundary-diagnostic"},"destination":{"org":reg["organization"],"service":svc},"carrier":{"kind":"HB_DERIVED","reference":"HB-test"},"intr_profile":"stegverse.intr.org-boundary.v1","transition":{"reference":"test","authority_effect":"NONE"},"payload":{"probe":"ping"},"evidence":{"ingress_receipt":None,"dispatch_receipt":None,"consumption_receipt":None,"egress_receipt":None,"reconstruction_reference":None}}
unepoched={k:v for k,v in os.environ.items() if k!="STEGVERSE_HB_EPOCH"}
with tempfile.TemporaryDirectory() as td:
 p=Path(td); (p/"in.json").write_text(json.dumps(env))
 # No supplied epoch: a six-field refusal, and nothing written.
 refused=subprocess.run(["python3","org-boundary/runtime/process_boundary.py","--envelope",str(p/"in.json"),"--out",str(p/"out.json")],env=unepoched,capture_output=True,text=True)
 assert refused.returncode==1, refused.stderr; refusal=json.loads(refused.stdout); assert refusal["failure_code"]=="HB_EPOCH_NOT_SUPPLIED"; assert refusal["derived_from_clock"] is False; assert not (p/"out.json").exists()
 subprocess.run(["python3","org-boundary/runtime/process_boundary.py","--envelope",str(p/"in.json"),"--out",str(p/"out.json"),"--hb-epoch","4096"],env=unepoched,check=True); out=json.loads((p/"out.json").read_text()); assert out["consumed"] is True; assert out["reconstruction"]["status"]=="RECONSTRUCTED"; assert out["authority_effect"]=="NONE"; assert [r["kind"] for r in out["receipts"]]==["INGRESS_ACCEPTED","DISPATCHED","CONSUMED","RESULT_BOUND","EGRESS_EMITTED"]; assert all(r.get("observed_at")=="hb-epoch:4096" for r in out["receipts"]); assert out["application_disposition"]=="UNKNOWN"
print("PASS")
