#!/usr/bin/env python3
"""Operator commands for the resident federation, stamped at the supplied epoch.

``status`` and the ``send-*`` commands stamp a heartbeat (the status record,
the published frames), so they take ``--hb-epoch``, else ``STEGVERSE_HB_EPOCH``,
and refuse six-field before anything is read or written when there is none.
No clock stands in. ``collect`` only reads frames and takes no epoch.
"""
from __future__ import annotations
import argparse, importlib.util, json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("org_kernel",ROOT/"org-kernel"/"kernel.py")
K=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(K)
GWSPEC=importlib.util.spec_from_file_location("federation_gateway_transport",ROOT/"resident-runtime"/"federation_gateway_transport.py")
GW=importlib.util.module_from_spec(GWSPEC); GWSPEC.loader.exec_module(GW)

EPOCH_RETRY_ENTRYPOINT="resident-runtime/ecosystem_control.py (--hb-epoch, or "+K.SUPPLIED_EPOCH_ENV+")"

def _main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The raw text goes to the shared epoch rule: argparse's int() would take
    # "+33", " 33" or fullwidth digits as 33.
    ap.add_argument("--hb-epoch",default=None)
    sub=ap.add_subparsers(dest="cmd",required=True)
    for name,cls in (("send-monitor","ecosystem.monitor.request"),("send-work","ecosystem.work.request"),("send-message","ecosystem.communication")):
        p=sub.add_parser(name)
        p.add_argument("--subject",required=True)
        p.add_argument("--body-json",required=True)
        p.add_argument("--requested-action")
        p.add_argument("--communication-id")
        p.set_defaults(message_class=cls)
    p=sub.add_parser("collect")
    p.add_argument("--communication-id",required=True)
    sub.add_parser("status")
    args=ap.parse_args(argv)
    now_ns=None
    if args.cmd!="collect":
        try:
            now_ns=K.epoch_now_ns(K.supplied_epoch(K.caller_epoch(args.hb_epoch),retry_entrypoint=EPOCH_RETRY_ENTRYPOINT))
        except ValueError as exc:
            # Each loaded kernel has its own SuppliedEpochRefused class.
            if not isinstance(getattr(exc,"refusal",None),dict):
                raise
            print(json.dumps(exc.refusal,sort_keys=True))
            return 1
    reg=K.load_registry(ROOT)
    org=reg["organization"]
    if args.cmd=="status":
        print(json.dumps(K.resident_status(ROOT,now_ns=now_ns),indent=2,sort_keys=True))
        return 0
    if args.cmd=="collect":
        if os.getenv("STEGVERSE_ORG_FEDERATION_GATEWAY_URL","").strip():
            result=GW.collect_local_responses(ROOT,args.communication_id)
        else:
            result=K.collect_ecosystem_responses(org,args.communication_id)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    body=json.loads(args.body_json)
    if os.getenv("STEGVERSE_ORG_FEDERATION_GATEWAY_URL","").strip():
        out=GW.publish_ecosystem_via_gateway(
            repo_root=ROOT,
            message_class=args.message_class,
            subject=args.subject,
            body=body,
            requested_action=args.requested_action,
            communication_id=args.communication_id,
            now_ns=now_ns
        )
    else:
        out=K.publish_ecosystem_from_directory(
            ROOT,
            message_class=args.message_class,
            subject=args.subject,
            body=body,
            requested_action=args.requested_action,
            communication_id=args.communication_id,
            now_ns=now_ns
        )
    print(json.dumps({
      "status":"PUBLISHED",
      "organization":org,
      "communication_id":out["communication_id"],
      "published_count":out["published_count"]
    },indent=2,sort_keys=True))
    return 0


def main(argv=None)->int:
    """Run one operator command.

    F-WRITER-TRACE: a fault writing this repository's own state is a six-field,
    non-terminal record with exit status K.OWN_STATE_WRITE_FAULT_EXIT, never a
    raw OSError or a traceback.
    """
    try:
        return _main(argv)
    except Exception as exc:
        if not K.own_state_fault(exc):
            raise
        return K.own_state_write_exit(exc, EPOCH_RETRY_ENTRYPOINT)


if __name__=="__main__":
    sys.exit(main())
