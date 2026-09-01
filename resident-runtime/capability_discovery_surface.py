#!/usr/bin/env python3
import argparse,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/"org-boundary/registry/capability-descriptors.snapshot.json"

def load(p): return json.loads(Path(p).read_text())

def run(ingress):
    env=load(ingress)
    if (env.get("destination") or {}).get("org")!="StegVerse-002": raise RuntimeError("wrong destination organization")
    if (env.get("destination") or {}).get("service")!="stegverse-002.capability-discovery": raise RuntimeError("wrong destination service")
    payload=env.get("payload") or {}
    request=payload.get("request") if isinstance(payload.get("request"),dict) else payload
    op=request.get("operation")
    snap=load(SNAP)
    entries=snap["entries"]
    if op=="LIST_CAPABILITIES":
        result=entries
    elif op=="SEARCH_CAPABILITIES":
        q=str(request.get("query") or "").strip().lower()
        result=[]
        for e in entries:
            hay=json.dumps(e,sort_keys=True).lower()
            if q and q in hay: result.append(e)
    elif op=="READ_CAPABILITY_DESCRIPTOR":
        cid=str(request.get("capability_id") or "")
        hit=next((e for e in entries if e["capability_id"]==cid),None)
        if hit is None: raise RuntimeError("unknown capability")
        result=hit
    else:
        raise RuntimeError("unsupported operation")
    return {
      "schema":"stegverse-002.capability-discovery-response/v1",
      "operation":op,
      "result":result,
      "epistemic_rules":snap["epistemic_rules"],
      "authority_effect":"NONE_DISCOVERY_ONLY",
      "authority_transfer":False,
      "identity_constitution_prescribed":False
    }

def main():
    p=argparse.ArgumentParser();p.add_argument("--ingress",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    try: result=run(a.ingress);code=0
    except Exception as exc:
        result={"schema":"stegverse-002.capability-discovery-response/v1","state":"BLOCKED","reason":str(exc),"authority_effect":"NONE_BLOCKED","authority_transfer":False};code=2
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(code)
if __name__=="__main__":main()
