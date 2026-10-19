#!/usr/bin/env python3
import argparse, hashlib, importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path

KINDS=["INGRESS_ACCEPTED","DISPATCHED","CONSUMED","RESULT_BOUND","EGRESS_EMITTED"]
ROOT=Path(__file__).resolve().parents[2]
_spec=importlib.util.spec_from_file_location("process_boundary_kernel",ROOT/"org-kernel/kernel.py")
kernel=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(kernel)

#: A boundary receipt's time is the epoch its caller supplies (``--hb-epoch``,
#: else ``STEGVERSE_HB_EPOCH``). An absent or invalid one is refused six-field
#: before anything is written; no clock stands in for it.
EPOCH_RETRY_ENTRYPOINT="org-boundary/runtime/process_boundary.py (--hb-epoch, or "+kernel.SUPPLIED_EPOCH_ENV+")"

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")
def hid(prefix,v): return prefix+"-"+hashlib.sha256(canon(v)).hexdigest()[:24]
def load(path): return json.loads(Path(path).read_text())
def make_receipt(kind, base, previous_receipt_id, *, hb_epoch=None, disposition=None):
    hb_epoch=kernel.supplied_epoch(hb_epoch,retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    subject={**base,"kind":kind,"previous_receipt_id":previous_receipt_id}
    rid=hid(kind.lower(),subject)
    row={
        "kind":kind,
        "receipt_id":rid,
        "subject":base["service_id"],
        "evidence_hash":hashlib.sha256(canon(subject)).hexdigest(),
        "previous_receipt_id":previous_receipt_id,
        "observed_at":f"hb-epoch:{hb_epoch}",
    }
    if disposition is not None:
        row["application_disposition"]=disposition
    return row

#: The exit status of a fault writing this boundary's own state (B-P36q). The
#: caller retries, and the interrupted history resumes; nothing is refused for good.
EX_WRITE_FAULT=kernel.OWN_STATE_WRITE_FAULT_EXIT

def append_live_receipt(path, receipt):
    if path is None:
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as handle:
        handle.write(json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n")
        handle.flush()
        os.fsync(handle.fileno())

def write_json_atomic(path, value):
    """Publish a JSON document by same-directory replacement, so a fault leaves the old state or the new."""
    path=Path(path)
    fd,temp=tempfile.mkstemp(prefix=".boundary-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            handle.write(json.dumps(value,indent=2,sort_keys=True)+"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def expected_receipt_id(kind, base, previous_receipt_id):
    return hid(kind.lower(),{**base,"kind":kind,"previous_receipt_id":previous_receipt_id})

def resume_live_history(live_path, base):
    """The live rows already recorded for this packet, as the prefix an interrupted run left (B-P36q).

    A receipt's id is a function of the packet, its kind and its predecessor,
    so each recorded row is checked against the one this run would write. The
    longest matching prefix is kept, byte for byte, and anything after it (a
    torn last line) is dropped by rewriting the log atomically. A first row
    that is another packet's ingress is that packet's history: a collision.
    """
    if not live_path.exists():
        return []
    rows=[]; previous=None
    lines=live_path.read_text(encoding="utf-8").split("\n")
    complete=lines[:-1]  # the text after the last newline is a torn write, if any
    for index,line in enumerate(complete):
        try:
            row=json.loads(line)
        except ValueError:
            break
        kind=KINDS[len(rows)] if len(rows)<len(KINDS) else None
        if (not isinstance(row,dict) or kind is None or row.get("kind")!=kind
                or row.get("previous_receipt_id")!=previous
                or row.get("receipt_id")!=expected_receipt_id(kind,base,previous)):
            if index==0 and isinstance(row,dict) and row.get("kind")==KINDS[0]:
                raise SystemExit("org-boundary-receipt-write-once-collision")
            break
        rows.append(row); previous=row["receipt_id"]
    kept="".join(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n" for row in rows)
    if kept!=live_path.read_text(encoding="utf-8"):
        fd,temp=tempfile.mkstemp(prefix=".boundary-",suffix=".tmp",dir=str(live_path.parent))
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as handle:
                handle.write(kept)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp,live_path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return rows

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
    # The root takes its time from the last receipt it binds, never a clock.
    generated_at=receipts[-1].get("observed_at")
    if not isinstance(generated_at,str) or not generated_at:
        raise SystemExit("hierarchical-ledger-org-receipt-time-missing")
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
        "generated_at":generated_at,
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
    # A fault writing this boundary's own state is six-field and non-terminal, with
    # no traceback; the caller retries and the interrupted history resumes (B-P36q).
    # Bad input is a six-field refusal (F-WRITER-TRACE).
    return kernel.run_writer_cli(run,EPOCH_RETRY_ENTRYPOINT)

def run():
    ap=argparse.ArgumentParser()
    ap.add_argument("--envelope",required=True)
    ap.add_argument("--registry",default="org-boundary/registry/services.json")
    ap.add_argument("--out",required=True)
    # The raw text goes to the shared epoch rule: argparse's int() would take
    # "+33", " 33" or fullwidth digits as 33.
    ap.add_argument("--hb-epoch",default=None)
    a=ap.parse_args()
    refusal=kernel.writer_epoch_refusal(kernel.caller_epoch(a.hb_epoch),retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    if refusal is not None:
        print(json.dumps(refusal,sort_keys=True))
        sys.exit(1)
    hb_epoch=int(kernel.caller_epoch(a.hb_epoch))
    env=kernel.read_json_input(a.envelope,argument="--envelope",retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    reg=kernel.read_json_input(a.registry,argument="--registry",retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    req=["schema_version","packet_id","direction","origin","destination","carrier","intr_profile","transition","payload","evidence"]
    miss=[k for k in req if k not in env]
    if miss: raise SystemExit("missing:"+",".join(miss))
    if env["destination"]["org"]!=reg["organization"]: raise SystemExit("wrong-destination-org")
    svc=next((s for s in reg["services"] if s["service_id"]==env["destination"]["service"]),None)
    if not svc: raise SystemExit("unknown-service")
    base={"packet_id":env["packet_id"],"service_id":svc["service_id"],"payload_hash":hashlib.sha256(canon(env["payload"])).hexdigest()}
    live_path=None
    prior_boundary_bundle=None
    resumed=[]
    if svc.get("service_id")=="stegverse-002.self-characterization":
        state_root=Path(os.environ.get("STEGVERSE_SELF_CHAR_STATE_ROOT",str(Path.home()/".stegverse/self-characterization-001"))).expanduser().resolve()
        state_root.mkdir(parents=True,exist_ok=True)
        live_path=state_root/"ORG_BOUNDARY_RECEIPTS.live.jsonl"
        prior_bundle_path=state_root/"ORG_BOUNDARY_RECEIPTS.json"
        if prior_bundle_path.is_file():
            prior_boundary_bundle=load(prior_bundle_path)
            if prior_boundary_bundle.get("packet_id")!=env["packet_id"] or prior_boundary_bundle.get("payload_sha256")!=base["payload_hash"]:
                raise SystemExit("org-boundary-receipt-write-once-collision")
        else:
            # An interrupted run resumes from the rows it recorded (B-P36q).
            resumed=resume_live_history(live_path,base)

    receipts=[]; prev=None
    def extend(kind, disposition=None):
        nonlocal prev
        if len(receipts)<len(resumed):
            row=resumed[len(receipts)]
        else:
            row=make_receipt(kind,base,prev,hb_epoch=hb_epoch,disposition=disposition)
            append_live_receipt(live_path,row)
        receipts.append(row); prev=row["receipt_id"]
    if prior_boundary_bundle is None:
        extend("INGRESS_ACCEPTED")
        extend("DISPATCHED")

    application_result=endpoint_result(env,svc,a.envelope)
    disposition=str(application_result.get("state") or "UNKNOWN")
    if prior_boundary_bundle is not None:
        receipts=list(prior_boundary_bundle.get("receipts") or [])
        prev=receipts[-1].get("receipt_id") if receipts else None
    else:
        extend("CONSUMED",disposition)
        extend("RESULT_BOUND",disposition)
        extend("EGRESS_EMITTED",disposition)
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
                    write_json_atomic(target,boundary_bundle)
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
                write_json_atomic(org_root_path,organization_ledger_root)
            application_result["organization_ledger_root_path"]=str(org_root_path)
            application_result["organization_ledger_root_hash"]=organization_ledger_root["root_hash"]
            if application_result.get("state")=="COMPLETED":
                handoff_script=ROOT/"resident-runtime/submit_sv002_self_characterization_to_master_records.py"
                handoff_receipt=state_root/"MASTER_RECORDS_ORGANIZATION_RECORD_HANDOFF.json"
                legacy_handoff_receipt=state_root/"MASTER_RECORDS_CUSTODY_HANDOFF.json"
                if handoff_script.is_file():
                    handoff_done=subprocess.run(
                        ["python3",str(handoff_script),"--state-root",str(state_root),"--hb-epoch",str(hb_epoch)],
                        cwd=ROOT,capture_output=True,text=True,check=False,timeout=120
                    )
                    handoff_value=None
                    if not handoff_receipt.is_file() and legacy_handoff_receipt.is_file():
                        handoff_receipt=legacy_handoff_receipt
                    if handoff_receipt.is_file():
                        try: handoff_value=load(handoff_receipt)
                        except Exception: handoff_value=None
                    application_result["master_records_handoff"]={
                        "state":(handoff_value or {}).get("state") or ("PENDING" if handoff_done.returncode else "PUBLISHED_FOR_MASTER_RECORDS_ORGANIZATION_RECORD"),
                        "receipt_path":str(handoff_receipt) if handoff_receipt.is_file() else None,
                        "receipt":handoff_value,
                        "publisher_returncode":handoff_done.returncode,
                        "stderr_tail":handoff_done.stderr[-1024:],
                        "authority_effect":"NONE",
                    }
    result={
        "schema_version":reg["organization"].lower().replace(" ","-")+".boundary-execution.v1",
        "packet_id":env["packet_id"],
        "organization":reg["organization"],
        "service_id":svc["service_id"],
        "consumed":application_result.get("state")!="BLOCKED",
        "application_completed":application_result.get("state")=="COMPLETED",
        "application_disposition":disposition,
        "application_result":application_result,
        "authority_effect":env["transition"]["authority_effect"],
        "receipts":receipts,
        "reconstruction":{
            "same_execution_required":True,
            "status":(
                "RECONSTRUCTED" if svc.get("boundary_role")=="BOUNDARY_LOCAL_DIAGNOSTIC"
                else ("PUBLISHED_TO_MASTER_RECORDS" if isinstance(application_result.get("master_records_handoff"),dict) and application_result["master_records_handoff"].get("receipt") else "PENDING_MASTER_RECORDS")
            ),
            "terminal_receipt_id":prev
        }
    }
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"PASS","terminal_receipt_id":prev,"service_id":svc["service_id"]}))
if __name__=="__main__": sys.exit(main())
