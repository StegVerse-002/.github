#!/usr/bin/env python3
"""Run one federation cycle at the supplied epoch and record it.

The epoch is ``--hb-epoch``, else ``STEGVERSE_HB_EPOCH``. An absent or invalid
one is refused six-field before any frame is consumed and before
``latest-cycle.json`` is written. The cycle's heartbeat, its response frames
and its receipts are stamped from that epoch, never from a clock.
"""
from __future__ import annotations
import argparse, importlib.util, json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("org_kernel",ROOT/"org-kernel"/"kernel.py")
K=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(K)
GWSPEC=importlib.util.spec_from_file_location("federation_gateway_transport",ROOT/"resident-runtime"/"federation_gateway_transport.py")
GW=importlib.util.module_from_spec(GWSPEC); GWSPEC.loader.exec_module(GW)

EPOCH_RETRY_ENTRYPOINT="resident-runtime/federation_cycle.py (--hb-epoch, or "+K.SUPPLIED_EPOCH_ENV+")"
OUT=ROOT/"resident-runtime"/"federation"/"latest-cycle.json"

def heartbeat(hb_epoch:int)->dict:
    # Marked derived_from_clock false with no sample: it is the supplied epoch.
    return {**K.hb_reference(K.epoch_now_ns(hb_epoch)),"epoch_source":"SUPPLIED"}

def cycle(hb_epoch:int, *, gateway:bool)->dict:
    if gateway:
        receipt=GW.resident_gateway_cycle(ROOT,hb_epoch=hb_epoch)
        receipt["heartbeat_reference"]=heartbeat(hb_epoch)
        receipt["transport"]="SHARED_SERVICE_GATEWAY"
        return receipt
    results=K.consume_and_respond(ROOT,hb_epoch=hb_epoch)
    consumed=sum(1 for x in results if (x.get("result") or {}).get("status")=="CONSUMED")
    refused=sum(1 for x in results if (x.get("result") or {}).get("status")=="REFUSED_QUARANTINED")
    responses=sum(1 for x in results if x.get("response_publication"))
    return {
      "schema_version":"stegverse.org-federation-cycle.v1",
      "organization":K.load_registry(ROOT)["organization"],
      "heartbeat_reference":heartbeat(hb_epoch),
      "frames_seen":len(results),
      "frames_consumed":consumed,
      "frames_refused_quarantined":refused,
      "responses_emitted":responses,
      "authority_effect":"NONE_CARRIER_ONLY",
      "transport":"LOCAL_SPOOL_FALLBACK"
    }

def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The raw text goes to the shared epoch rule: argparse's int() would take
    # "+33", " 33" or fullwidth digits as 33.
    ap.add_argument("--hb-epoch",default=None)
    ap.add_argument("--out",type=Path,default=OUT)
    a=ap.parse_args(argv)
    gateway=bool(os.getenv("STEGVERSE_ORG_FEDERATION_GATEWAY_URL","").strip())
    try:
        hb_epoch=K.supplied_epoch(K.caller_epoch(a.hb_epoch),retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
        receipt=cycle(hb_epoch,gateway=gateway)
    except ValueError as exc:
        # Each loaded kernel has its own SuppliedEpochRefused class.
        if not isinstance(getattr(exc,"refusal",None),dict):
            raise
        print(json.dumps(exc.refusal,sort_keys=True))
        return 1
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print(json.dumps(receipt,sort_keys=True))
    return 0

if __name__=="__main__":
    sys.exit(main())
