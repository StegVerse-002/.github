#!/usr/bin/env python3
"""Persistent StegVerse organization resident executor.

Continuously runs the canonical federation cycle and consumes the callable
self-characterization binding declared by the existing activation manifest.
GitHub Actions and other hosted CI environments are rejected as runtime
authority.

Every route it runs stamps time, so it takes the supplied epoch (``--hb-epoch``,
else ``STEGVERSE_HB_EPOCH``) and refuses six-field before anything is written
when there is none. Its heartbeat and its children are stamped from that epoch;
no clock is read.
"""
from __future__ import annotations
import argparse, importlib.util, json, os, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
_SPEC=importlib.util.spec_from_file_location("resident_executor_kernel",ROOT/"org-kernel"/"kernel.py")
K=importlib.util.module_from_spec(_SPEC); _SPEC.loader.exec_module(K)
EPOCH_RETRY_ENTRYPOINT="resident-runtime/resident_executor.py (--hb-epoch, or "+K.SUPPLIED_EPOCH_ENV+")"
HOSTED=("GITHUB_ACTIONS","CI","RENDER","VERCEL","CF_PAGES","CLOUDFLARE_WORKERS")
STATE=ROOT/"resident-runtime"/"state"
ACTIVATION_MANIFEST=ROOT/"resident-runtime"/"activation-manifest.json"
EXPECTED_CALLABLE_TASK_ID="STEGVERSE-002-EXPERIMENT-RERUN-001"
EXPECTED_CALLABLE_OPERATION="REQUEST_SELF_CHARACTERIZATION"
EXPECTED_CALLABLE_BINDING="resident-runtime/invoke_sv002_experiment_rerun.py"
HEARTBEAT=STATE/"resident-executor.latest.json"

def truthy(v):
    return str(v or "").strip().lower() not in {"","0","false","no"}

def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name("."+path.name+".tmp")
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    os.replace(temp,path)

def run_json(cmd, timeout):
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,check=False,env=dict(os.environ),timeout=timeout)
    payload=None
    for line in reversed(p.stdout.splitlines()):
        try:
            v=json.loads(line)
            if isinstance(v,dict):
                payload=v
                break
        except Exception:
            pass
    return p,payload

def consume_declared_sv002_callable():
    if not ACTIVATION_MANIFEST.is_file():
        raise RuntimeError("activation manifest missing")
    activation=json.loads(ACTIVATION_MANIFEST.read_text(encoding="utf-8"))
    surface=activation.get("self_characterization_surface") or {}

    task_id=surface.get("callable_task_id")
    operation=surface.get("callable_operation")
    binding_rel=surface.get("callable_publisher_binding")
    invocation_count=surface.get("callable_invocation_count")

    if task_id!=EXPECTED_CALLABLE_TASK_ID:
        raise RuntimeError("SV002 callable task binding mismatch")
    if operation!=EXPECTED_CALLABLE_OPERATION:
        raise RuntimeError("SV002 callable operation binding mismatch")
    if binding_rel!=EXPECTED_CALLABLE_BINDING:
        raise RuntimeError("SV002 callable publisher binding mismatch")
    if invocation_count!=1:
        raise RuntimeError("SV002 callable invocation count must equal one")

    binding=(ROOT/binding_rel).resolve()
    try:
        binding.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError("SV002 callable publisher escapes repository root") from exc
    if not binding.is_file():
        raise RuntimeError("SV002 callable publisher binding missing")

    p,result=run_json([sys.executable,str(binding)],2200)
    if not isinstance(result,dict):
        raise RuntimeError("SV002 callable publisher emitted no result")
    if result.get("goal_task_id")!=EXPECTED_CALLABLE_TASK_ID:
        raise RuntimeError("SV002 callable result task mismatch")
    if result.get("cosv_id")!="50000000107000":
        raise RuntimeError("SV002 callable result COSV mismatch")
    if p.returncode!=0:
        if result.get("state")!="BLOCKED":
            raise RuntimeError(
                "SV002 callable publisher failed without BLOCKED result: "
                +str(result.get("reason") or p.stderr[-1024:] or "unknown")
            )
        return result
    if result.get("state") not in {
        "SUBMITTED_EXISTING_FEDERATION_EDGE",
        "ALREADY_SUBMITTED_NO_SECOND_REQUEST",
    }:
        raise RuntimeError("SV002 callable publisher terminal state invalid")
    return result

def cycle():
    script=ROOT/"resident-runtime"/"federation_cycle.py"
    p,result=run_json([sys.executable,str(script)],120)
    if p.returncode!=0:
        raise RuntimeError("federation cycle failed: "+p.stderr[-1024:])
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--once",action="store_true")
    ap.add_argument("--poll-seconds",type=float,default=1.0)
    # The raw text goes to the shared epoch rule.
    ap.add_argument("--hb-epoch",default=None)
    a=ap.parse_args()
    bad=[k for k in HOSTED if truthy(os.getenv(k))]
    if bad:
        raise SystemExit("hosted runtime prohibited: "+",".join(bad))
    refusal=K.writer_epoch_refusal(K.caller_epoch(a.hb_epoch),retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    if refusal is not None:
        # Before the callable, the cycle or the heartbeat: nothing is written.
        print(json.dumps(refusal,sort_keys=True))
        return 1
    hb_epoch=K.supplied_epoch(K.caller_epoch(a.hb_epoch),retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    # The callable publisher and the federation cycle inherit it (run_json passes the environment).
    os.environ[K.SUPPLIED_EPOCH_ENV]=str(hb_epoch)
    iteration=0
    callable_attempted=False
    callable_completed=False
    callable_result=None
    while True:
        iteration+=1
        error=None
        try:
            if not callable_attempted:
                callable_attempted=True
                callable_result=consume_declared_sv002_callable()
                if callable_result.get("state")=="BLOCKED":
                    raise RuntimeError(
                        "SV002 callable publisher failed: "
                        +str(callable_result.get("reason") or "unknown")
                    )
                callable_completed=True
            fed=cycle()
        except Exception as exc:
            fed=None
            error=str(exc)
        state={
            "schema":"stegverse.organization-resident-executor/v1",
            "organization":"StegVerse-002",
            "observed_at":f"hb-epoch:{hb_epoch}",
            "iteration":iteration,
            "state":"RUNNING" if error is None else "DEGRADED",
            "federation_cycle":fed,
            "sv002_callable":callable_result,
            "sv002_callable_attempted":callable_attempted,
            "sv002_callable_completed":callable_completed,
            "sv002_request_bound_observed":bool(
                isinstance(callable_result,dict)
                and callable_result.get("request_bound_claimed") is True
            ),
            "error":error,
            "persistent":not a.once,
            "github_actions_runtime_authority":"NONE",
            "authority_effect":"NONE_EXECUTOR_ONLY",
        }
        atomic_json(HEARTBEAT,state)
        print(json.dumps(state,sort_keys=True),flush=True)
        if a.once:
            return 0 if error is None else 2
        time.sleep(max(0.25,a.poll_seconds))

if __name__=="__main__":
    raise SystemExit(main())
