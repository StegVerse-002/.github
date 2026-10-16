#!/usr/bin/env python3
import argparse,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=json.loads((ROOT/".stegverse/transition-ledger/org-contract.json").read_text())
def canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(v):return "sha256:"+hashlib.sha256(canon(v)).hexdigest()
def ledger_root():
 o=os.getenv("STEGVERSE_ORG_LEDGER_ROOT")
 if o:return Path(o).expanduser().resolve()
 return (Path(os.getenv("XDG_STATE_HOME",str(Path.home()/".local/state")))/"stegverse/org-ledgers"/C["organization"]).resolve()
def load(p):return json.loads(Path(p).read_text())
def verify_repo(r):
 if r.get("schema")!="stegverse.repo-transition-receipt/v1":raise SystemExit("repo receipt schema mismatch")
 if not str(r.get("repository","")).startswith(C["organization"]+"/"):raise SystemExit("repo outside organization")
 claimed=r.get("receipt_sha256"); body=dict(r);body.pop("receipt_sha256",None)
 if claimed!=sha(body):raise SystemExit("repo receipt hash mismatch")
 return claimed
def append(source_receipt, org_transition_class, predecessor_state, successor_state, boundary_evidence=None, authority_effect="NONE", hb_epoch=None, idempotent=True):
    """Append the organization receipt for one repository receipt. A replay returns the recorded one."""
    if not isinstance(source_receipt,dict): raise ValueError("source_receipt_required")
    claimed=source_receipt.get("receipt_sha256"); body=dict(source_receipt); body.pop("receipt_sha256",None)
    if claimed!=sha(body): raise ValueError("repo receipt hash mismatch")
    if not str(source_receipt.get("repository","")).startswith(C["organization"]+"/"): raise ValueError("repo outside organization")
    root=ledger_root(); receipts=root/"receipts"; receipts.mkdir(parents=True,exist_ok=True); head_path=root/"HEAD.json"
    if idempotent:
        for path in receipts.glob("*.json"):
            record=json.loads(path.read_text())
            if record.get("schema")=="stegverse.organization-transition-receipt/v1" and record.get("repo_receipt_sha256")==claimed:
                return record
    prev=json.loads(head_path.read_text()).get("receipt_sha256") if head_path.is_file() else None
    observed=f"hb-epoch:{hb_epoch}" if hb_epoch is not None else datetime.now(timezone.utc).isoformat()
    built={"schema":"stegverse.organization-transition-receipt/v1","organization":C["organization"],"source_repository":source_receipt["repository"],"repo_receipt_sha256":claimed,"repo_transition_id":source_receipt.get("transition_id"),"org_transition_class":org_transition_class,"predecessor_org_state_sha256":predecessor_state,"successor_org_state_sha256":successor_state,"boundary_evidence":dict(boundary_evidence or {}),"authority_effect":authority_effect,"hb_reference":{"epoch":hb_epoch,"progression_dependency":"OSCILLATOR_ONLY","authority_effect":"NONE"},"observed_at":observed,"previous_receipt_sha256":prev}
    digest=sha(built); record={**built,"receipt_sha256":digest}; path=receipts/(digest.split(":",1)[1]+".json")
    if path.exists() and json.loads(path.read_text())!=record: raise ValueError("org receipt collision")
    if not path.exists(): path.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    head_path.write_text(json.dumps({"organization":C["organization"],"receipt_sha256":digest,"receipt_path":str(path)},indent=2,sort_keys=True)+"\n")
    return record
def main():
 p=argparse.ArgumentParser();p.add_argument("--repo-receipt",required=True);p.add_argument("--org-transition-class",default="REPO_STATE_PROPAGATION");p.add_argument("--predecessor-org-state-sha256",required=True);p.add_argument("--successor-org-state-sha256",required=True);p.add_argument("--boundary-evidence-json",default="{}");p.add_argument("--authority-effect",default="NONE");a=p.parse_args()
 rr=load(a.repo_receipt);rd=verify_repo(rr);root=ledger_root();d=root/"receipts";d.mkdir(parents=True,exist_ok=True);h=root/"HEAD.json";prev=load(h).get("receipt_sha256") if h.exists() else None
 b={"schema":"stegverse.organization-transition-receipt/v1","organization":C["organization"],"source_repository":rr["repository"],"repo_receipt_sha256":rd,"repo_transition_id":rr["transition_id"],"org_transition_class":a.org_transition_class,"predecessor_org_state_sha256":a.predecessor_org_state_sha256,"successor_org_state_sha256":a.successor_org_state_sha256,"boundary_evidence":json.loads(a.boundary_evidence_json),"authority_effect":a.authority_effect,"observed_at":datetime.now(timezone.utc).isoformat(),"previous_receipt_sha256":prev}
 dg=sha(b);rec={**b,"receipt_sha256":dg};fp=d/(dg.split(":",1)[1]+".json")
 if fp.exists() and load(fp)!=rec:raise SystemExit("org receipt collision")
 if not fp.exists():fp.write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n")
 h.write_text(json.dumps({"organization":C["organization"],"receipt_sha256":dg,"receipt_path":str(fp)},indent=2,sort_keys=True)+"\n");print(json.dumps(rec,sort_keys=True))
if __name__=="__main__":main()
