#!/usr/bin/env python3
import argparse,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];C=json.loads((ROOT/".stegverse/transition-ledger/contract.json").read_text())
def canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(v):return "sha256:"+hashlib.sha256(v if isinstance(v,(bytes,bytearray)) else canon(v)).hexdigest()
def lr():
 o=os.getenv("STEGVERSE_REPO_LEDGER_ROOT")
 if o:return Path(o).expanduser().resolve()
 return (Path(os.getenv("XDG_STATE_HOME",str(Path.home()/".local/state")))/"stegverse/repo-ledgers"/C["repository"]).resolve()
def recorded(transition_id, transition_class):
    """The receipt already bound to this transition, walking back from HEAD."""
    root=lr(); head=root/"HEAD.json"
    if not head.is_file(): return None
    cursor=json.loads(head.read_text()).get("receipt_sha256"); seen=set()
    while isinstance(cursor,str) and cursor and cursor not in seen:
        seen.add(cursor)
        path=root/"receipts"/(cursor.split(":",1)[-1]+".json")
        if not path.is_file(): return None
        receipt=json.loads(path.read_text())
        if receipt.get("transition_id")==transition_id and receipt.get("transition_class")==transition_class:
            return receipt
        cursor=receipt.get("previous_receipt_sha256")
    return None
def append(transition_id, transition_class, predecessor_state_sha256, successor_state_sha256, evidence=None, authority_effect="NONE", hb_epoch=None, idempotent_on=None, store=None):
    """Append one repository receipt. A replay of the same transition returns the recorded one."""
    del store
    evidence=dict(evidence or {})
    root=lr(); receipts=root/"receipts"; receipts.mkdir(parents=True,exist_ok=True); head_path=root/"HEAD.json"
    existing=recorded(transition_id, transition_class)
    if existing is not None:
        prior=existing.get("evidence") if isinstance(existing.get("evidence"),dict) else {}
        keys=tuple(idempotent_on) if idempotent_on else tuple(evidence.keys())
        if all(prior.get(key)==evidence.get(key) for key in keys): return existing
        raise ValueError("ledger_receipt_collision")
    prev=json.loads(head_path.read_text()).get("receipt_sha256") if head_path.is_file() else None
    observed=f"hb-epoch:{hb_epoch}" if hb_epoch is not None else datetime.now(timezone.utc).isoformat()
    body={"schema":"stegverse.repo-transition-receipt/v1","repository":C["repository"],"transition_id":transition_id,"transition_class":transition_class,"predecessor_state_sha256":predecessor_state_sha256,"successor_state_sha256":successor_state_sha256,"evidence":evidence,"authority_effect":authority_effect,"hb_reference":{"epoch":hb_epoch,"progression_dependency":"OSCILLATOR_ONLY","authority_effect":"NONE"},"observed_at":observed,"previous_receipt_sha256":prev}
    digest=sha(body); record={**body,"receipt_sha256":digest}; path=receipts/(digest.split(":",1)[1]+".json")
    if path.exists() and json.loads(path.read_text())!=record: raise ValueError("ledger_receipt_collision")
    if not path.exists(): path.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    head_path.write_text(json.dumps({"repository":C["repository"],"receipt_sha256":digest,"receipt_path":str(path)},indent=2,sort_keys=True)+"\n")
    return record
def main():
 p=argparse.ArgumentParser();p.add_argument("--transition-id",required=True);p.add_argument("--transition-class",required=True);p.add_argument("--predecessor-state-sha256",required=True);p.add_argument("--successor-state-sha256",required=True);p.add_argument("--evidence-json",default="{}");p.add_argument("--authority-effect",default="NONE");p.add_argument("--hb-ref");a=p.parse_args()
 root=lr();d=root/"receipts";d.mkdir(parents=True,exist_ok=True);h=root/"HEAD.json";prev=json.loads(h.read_text()).get("receipt_sha256") if h.exists() else None
 b={"schema":"stegverse.repo-transition-receipt/v1","repository":C["repository"],"transition_id":a.transition_id,"transition_class":a.transition_class,"predecessor_state_sha256":a.predecessor_state_sha256,"successor_state_sha256":a.successor_state_sha256,"evidence":json.loads(a.evidence_json),"authority_effect":a.authority_effect,"hb_reference":a.hb_ref,"observed_at":datetime.now(timezone.utc).isoformat(),"previous_receipt_sha256":prev};dg=sha(b);r={**b,"receipt_sha256":dg};fp=d/(dg.split(":",1)[1]+".json")
 if fp.exists() and json.loads(fp.read_text())!=r:raise SystemExit("receipt collision")
 if not fp.exists():fp.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
 h.write_text(json.dumps({"repository":C["repository"],"receipt_sha256":dg,"receipt_path":str(fp)},indent=2,sort_keys=True)+"\n");print(json.dumps(r,sort_keys=True))
if __name__=="__main__":main()
