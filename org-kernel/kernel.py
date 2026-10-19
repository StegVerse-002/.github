#!/usr/bin/env python3
"""Universal StegVerse organization resident kernel.

Organization-neutral runtime behavior extracted from StegVerse-Labs/.github.
No GitHub, hosted scheduler, provider, or carrier sets an authority or time constraint. Authority and time are constraint variables; a disposition is transition evidence only.
"""
from __future__ import annotations
import base64, hashlib, importlib.util, json, os, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HB_ANCHOR_EPOCH=32
HB_ANCHOR_UNIX_NS=1_787_511_600_000_000_000
HB_PERIOD_NS=10_000_000
HB_HZ=100
CHANNEL_COUNT=16
SCHEMA="stegverse.org-resident-kernel/v1"
CARRIER_SCHEMA="stegverse.org-resident-kernel.carrier/v1"
PACKET_SCHEMA="stegverse.intr.org-boundary.v1"

def canon(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def sha(v:Any)->str:
    raw=v if isinstance(v,(bytes,bytearray)) else canon(v)
    return "sha256:"+hashlib.sha256(bytes(raw)).hexdigest()

def hb_reference(now_ns:int|None=None)->dict[str,Any]:
    """A heartbeat reference.

    A caller's ``now_ns`` (a supplied epoch's sample time) is SUPPLIED:
    ``derived_from_clock`` false and no ``sampled_unix_ns``. With none, the
    clock is read and the reference keeps its legacy CLOCK form, the sample it
    took and no flag; that default is WU-B13 slice b's to mark.
    """
    supplied=now_ns is not None
    if not supplied:
        now_ns=int(datetime.now(timezone.utc).timestamp()*1_000_000_000)
    if now_ns<HB_ANCHOR_UNIX_NS:
        raise ValueError("sample_precedes_hb32_anchor")
    q,phase=divmod(now_ns-HB_ANCHOR_UNIX_NS,HB_PERIOD_NS)
    epoch=HB_ANCHOR_EPOCH+q
    reference={"epoch":epoch,"generation":epoch,"heartbeat_id":f"HB:{epoch}",
               "phase_offset_ns":phase,"frequency_hz":HB_HZ,"progression_dependency":"OSCILLATOR_ONLY",
               "authority_effect":"NONE"}
    if supplied:
        reference["derived_from_clock"]=False
    else:
        reference["sampled_unix_ns"]=now_ns
    return reference

HB_EPOCH_NOT_SUPPLIED="HB_EPOCH_NOT_SUPPLIED"
HB_EPOCH_INVALID="HB_EPOCH_INVALID"
HB_EPOCH_PROVENANCE_UNMARKED="HB_EPOCH_PROVENANCE_UNMARKED"
CARRIED_PROVENANCE_UNVERIFIED="CARRIED_PROVENANCE_UNVERIFIED"
CARRIED_NOT_ACCEPTED_BY_DESTINATION="CARRIED_NOT_ACCEPTED_BY_DESTINATION"
#: This organization accepts no CARRIED crossings (activation-manifest.json
#: ``accepts_carried_crossings``): it has no admission verifier for a carried
#: head, so every sender forwards a SUPPLIED epoch.
ACCEPTS_CARRIED_CROSSINGS=False
CARRIED_RETRY_ENTRYPOINT="the sender's hop, re-sending the crossing with the SUPPLIED epoch"
HB_EPOCH_PREDICATE="SUBMISSION_CARRIES_THE_SUPPLIED_HB_EPOCH"
HB_EPOCH_OWNING_EXISTING_GOAL="StegVerse-Labs/.github#2897 / StegVerse-org/.github#162 P0-runtime-and-custody"

class SuppliedEpochRefused(ValueError):
    """A receipt writer's refusal of an absent or invalid supplied epoch.

    `refusal` is the six-field FAIL_CLOSED from `writer_epoch_refusal`. Raised
    before the store opens; no clock is read to stand in for the epoch.
    """
    def __init__(self, refusal:dict[str,Any])->None:
        super().__init__(refusal["failure_code"]+": "+refusal["detail"])
        self.disposition=refusal["disposition"]
        self.failed_predicate=refusal["failed_predicate"]
        self.refusal=dict(refusal)

#: sha256 of ``inspect.getsource(supplied_epoch_failure)``: the shared rule as
#: published FINAL on StegVerse-Labs/.github#3282, byte for byte.
SHARED_VALIDATOR_SHA256="ad8ff52936d5bcd9a2ad6caceb2d9a637a099518989b34bbb3370301c7a4cce2"

def supplied_epoch_failure(hb_epoch: Any, reference: Any = None) -> tuple[str, str] | None:
    """The shared supplied-epoch rule (SUBMISSION_CARRIES_THE_SUPPLIED_HB_EPOCH).

    Byte-identical in StegVerse-org/.github#185 and StegVerse-Labs/.github#3212
    and #3213. `hb_epoch` absent (None) is HB_EPOCH_NOT_SUPPLIED. Otherwise it
    must be ASCII [0-9]+ only -- an int is read as its decimal text; a bool, a
    float or anything coerced ('+33', ' 33', '3_3', '33.0') is refused -- with
    integer value >= 32 (the HB32 anchor). `reference`, the carrier frame's
    heartbeat reference when there is one, must be an object, and a
    `derived_from_clock` it carries must be exactly false. Any failure is
    HB_EPOCH_INVALID. Returns (failure_code, detail), or None when the epoch is
    supplied. No clock is read.
    """
    if reference is not None and not isinstance(reference, dict):
        return "HB_EPOCH_INVALID", "the carrier's heartbeat reference is not an object"
    if hb_epoch is None:
        return "HB_EPOCH_NOT_SUPPLIED", "no hb_epoch was supplied and no clock is read"
    if isinstance(hb_epoch, bool):
        text = None
    elif isinstance(hb_epoch, int):
        text = str(hb_epoch)
    elif isinstance(hb_epoch, str):
        text = hb_epoch
    else:
        text = None
    if text is None or not text.isascii() or not text.isdigit():
        return "HB_EPOCH_INVALID", "hb_epoch " + repr(hb_epoch) + " is not ASCII [0-9]+"
    if int(text) < 32:
        return "HB_EPOCH_INVALID", "hb_epoch " + text + " is below the HB32 anchor (32)"
    if reference is not None and "derived_from_clock" in reference \
            and reference["derived_from_clock"] is not False:
        return "HB_EPOCH_INVALID", ("the carrier's derived_from_clock is not exactly false; "
                                    "a clock-derived epoch is not a supplied one")
    if reference is not None and "sampled_unix_ns" in reference: return "HB_EPOCH_INVALID", "the carrier's heartbeat reference carries sampled_unix_ns; a sampled clock value is CLOCK, never a supplied epoch"
    if reference is not None and "derived_from_clock" not in reference: return "HB_EPOCH_PROVENANCE_UNMARKED", "the carrier's heartbeat reference carries no derived_from_clock; an unmarked clock value is laundering, and a carrier cannot self-assert CARRIED provenance"
    return None

def writer_epoch_refusal(hb_epoch:Any, *, retry_entrypoint:str)->dict[str,Any]|None:
    """The six-field FAIL_CLOSED of a writer's epoch, or None when it is supplied.

    The rule is ``supplied_epoch_failure``. ``hb_epoch`` is the epoch, or a
    heartbeat reference judged as the carrier's by its own ``epoch``. The rule
    runs first, so its codes are uniform; a reference it passes that carries a
    CARRIED claim is then refused CARRIED_NOT_ACCEPTED_BY_DESTINATION: this
    organization accepts no CARRIED crossings, genuine or not.
    """
    if isinstance(hb_epoch,dict):
        failure=supplied_epoch_failure(hb_epoch.get("epoch"),hb_epoch)
        if failure is None and _carried(hb_epoch):
            return carried_refusal(hb_epoch,retry_entrypoint)
    else:
        failure=supplied_epoch_failure(hb_epoch)
    if failure is None:
        return None
    return _epoch_refusal(failure[0],failure[1],retry_entrypoint)

def carried_refusal(reference:dict[str,Any], retry_entrypoint:str)->dict[str,Any]:
    """CARRIED_NOT_ACCEPTED_BY_DESTINATION: this organization accepts no CARRIED crossings.

    It is not a finding of forgery: with no admission verifier here, a
    genuine claim and a forged one are refused alike, and the sender re-sends
    the crossing with the SUPPLIED epoch. ``retry_entrypoint`` (this hop) is
    named in the detail; the retry is the sender's.
    """
    refusal=_epoch_refusal(CARRIED_NOT_ACCEPTED_BY_DESTINATION,
                           "this destination accepts no CARRIED crossings (accepts_carried_crossings false); "
                           "the claim on head "+repr(reference.get("head_receipt_sha"))+" is neither verified nor "
                           "taken as supplied at "+retry_entrypoint,CARRIED_RETRY_ENTRYPOINT,
                           repair="re-send with the SUPPLIED epoch")
    refusal["failed_predicate"]="DESTINATION_ACCEPTS_CARRIED_CROSSINGS"
    return refusal

def _carried(reference:dict[str,Any])->bool:
    return any(isinstance(reference.get(key),str) and reference[key].upper().startswith("CARRIED")
               for key in ("source","provenance","epoch_source")) or "head_receipt_sha" in reference

def _epoch_refusal(code:str, detail:str, retry_entrypoint:str, *, repair:str|None=None)->dict[str,Any]:
    return {"disposition":"FAIL_CLOSED","failure_code":code,"failed_predicate":HB_EPOCH_PREDICATE,
            "detail":detail,
            "required_evidence_or_repair":repair or ("the caller supplies hb_epoch= (or --hb-epoch): an integer "
                                                     ">= "+str(HB_ANCHOR_EPOCH)+", or a heartbeat reference marked "
                                                     "derived_from_clock false; it is never derived from a clock"),
            "retry_entrypoint":retry_entrypoint,
            "owning_existing_goal":HB_EPOCH_OWNING_EXISTING_GOAL,
            "next_attempt":"call again with the supplied epoch; nothing was written",
            "derived_from_clock":False,"consequence_committed":False}

def supplied_epoch(hb_epoch:Any, *, retry_entrypoint:str)->int:
    """The supplied epoch as an integer, or SuppliedEpochRefused. No clock is read."""
    refusal=writer_epoch_refusal(hb_epoch,retry_entrypoint=retry_entrypoint)
    if refusal is not None:
        raise SuppliedEpochRefused(refusal)
    return int(hb_epoch["epoch"] if isinstance(hb_epoch,dict) else hb_epoch)

def frame_epoch(frame:dict[str,Any])->int|None:
    """The epoch a SUPPLIED frame lends, else None. Only the shared rule decides."""
    reference=frame.get("heartbeat_reference") if isinstance(frame,dict) else None
    if not isinstance(reference,dict) or _carried(reference):
        return None
    if supplied_epoch_failure(reference.get("epoch"),reference) is not None:
        return None
    return int(reference["epoch"])

def _clock_flagged(reference:Any)->bool:
    """A CLOCK heartbeat: flagged derived_from_clock true, or the legacy form (a sample, no flag)."""
    return isinstance(reference,dict) and (reference.get("derived_from_clock") is True or (
        "sampled_unix_ns" in reference and "derived_from_clock" not in reference))

#: The environment a caller supplies an epoch through when a call path has no
#: argument for it. Unset is no epoch; it is never filled from a clock.
SUPPLIED_EPOCH_ENV="STEGVERSE_HB_EPOCH"

def caller_epoch(hb_epoch:Any=None)->Any:
    """The caller's epoch, else the environment's raw text, for the shared rule to judge."""
    return hb_epoch if hb_epoch is not None else os.environ.get(SUPPLIED_EPOCH_ENV)

def epoch_now_ns(hb_epoch:int)->int:
    """The heartbeat sample time of a supplied epoch, so a frame is stamped from it, not a clock."""
    return HB_ANCHOR_UNIX_NS+(hb_epoch-HB_ANCHOR_EPOCH)*HB_PERIOD_NS

def derive_channel(payload_hash:str)->dict[str,Any]:
    if not isinstance(payload_hash,str) or not payload_hash.startswith("sha256:") or len(payload_hash)!=71:
        raise ValueError("payload_hash_invalid")
    slot=int(payload_hash[7:23],16)%CHANNEL_COUNT
    return {"channel_id":f"HB:H1:P{slot}","phase_slot":slot,"phase_slot_count":CHANNEL_COUNT,
            "derivation":"PAYLOAD_SHA256_FIRST64_MOD_16","authority_effect":"NONE_CARRIER_ONLY"}

def carrier_frame(packet:dict[str,Any], *, now_ns:int|None=None)->dict[str,Any]:
    raw=canon(packet); payload_hash=sha(packet.get("payload",{})); ref=hb_reference(now_ns); channel=derive_channel(payload_hash)
    body={"schema":CARRIER_SCHEMA,"packet_id":packet["packet_id"],"packet_sha256":sha(raw),
          "packet_base64":base64.b64encode(raw).decode("ascii"),"heartbeat_reference":ref,
          "channel":channel,"origin_org":packet["origin"]["org"],"destination_org":packet["destination"]["org"],
          "intr_profile":packet["intr_profile"],"authority_effect":"NONE_CARRIER_ONLY"}
    return {**body,"frame_sha256":sha(body)}

def recover_packet(frame:dict[str,Any])->dict[str,Any]:
    body=dict(frame); claimed=body.pop("frame_sha256",None)
    if claimed!=sha(body): raise ValueError("carrier_frame_hash_mismatch")
    raw=base64.b64decode(frame["packet_base64"].encode("ascii"),validate=True)
    if sha(raw)!=frame["packet_sha256"]: raise ValueError("packet_hash_mismatch")
    packet=json.loads(raw)
    if packet["packet_id"]!=frame["packet_id"]: raise ValueError("packet_id_mismatch")
    if packet["destination"]["org"]!=frame["destination_org"]: raise ValueError("destination_org_mismatch")
    return packet

def receipt(kind:str, packet_id:str, subject:str, previous:str|None, detail:dict[str,Any])->dict[str,Any]:
    body={"kind":kind,"packet_id":packet_id,"subject":subject,"previous_receipt_id":previous,"detail":detail}
    rid=kind.lower()+"-"+hashlib.sha256(canon(body)).hexdigest()[:24]
    return {**body,"receipt_id":rid,"evidence_hash":sha(body)}

def load_registry(root:Path)->dict[str,Any]:
    return json.loads((root/"org-boundary/registry/services.json").read_text())

#: The boundary role whose dispatch resolves a bound capability's address.
#:
#: The role vocabulary is this kernel's, as `BOUNDARY_LOCAL_DIAGNOSTIC` and
#: `BOUNDARY_LOCAL_CONTROL` already are. `capability_ingress.ROLE` is that
#: module's assertion of which role it serves. A resolver serving a role the
#: kernel never dispatches would be unreachable.
CAPABILITY_INGRESS_ROLE="BOUNDARY_LOCAL_CAPABILITY_INGRESS"

def capability_ingress(root:Path):
    """Load the organization's capability-ingress module from its boundary runtime.

    A registered capability is bound to a receiving operation in the
    organization's own overlay. This resolves the address to that operation.
    Loaded only when a capability address is dispatched: a root that never
    serves one is not defective for having no resolver until it is addressed.
    """
    path=root/"org-boundary/runtime/capability_ingress.py"
    if not path.is_file(): raise ValueError("org_boundary_capability_ingress_missing")
    spec=importlib.util.spec_from_file_location("capability_ingress",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

DISPATCH_EPOCH_RETRY_ENTRYPOINT="org-kernel/kernel.py::ingest_frame (hb_epoch=, or "+SUPPLIED_EPOCH_ENV+")"

def dispatch(root:Path, packet:dict[str,Any], *, mesh_root:Path|None=None,
             hb_epoch:Any=None)->dict[str,Any]:
    """Run one addressed packet at its service.

    A role that stamps time takes the supplied epoch (``hb_epoch``, else
    ``STEGVERSE_HB_EPOCH``) and refuses six-field before anything is written
    when there is none: an internal endpoint, whose boundary receipts carry
    it; a capability ingress, whose operation appends both ledger levels; and
    a monitor request, whose status carries a heartbeat. No clock stands in.
    """
    registry=load_registry(root)
    if packet["destination"]["org"]!=registry["organization"]: raise ValueError("wrong_destination_org")
    service=next((s for s in registry["services"] if s["service_id"]==packet["destination"]["service"]),None)
    if service is None: raise ValueError("unknown_service")
    role=service.get("boundary_role")
    adapter=service.get("endpoint_adapter")
    if stamps_time(service,packet):
        hb_epoch=supplied_epoch(caller_epoch(hb_epoch),retry_entrypoint=DISPATCH_EPOCH_RETRY_ENTRYPOINT)
    if role=="INTERNAL_ENDPOINT" and adapter:
        processor=root/"org-boundary/runtime/process_boundary.py"
        if not processor.is_file(): raise ValueError("org_boundary_processor_missing")
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); envelope=td/"packet.json"; out=td/"execution.json"
            envelope.write_text(json.dumps(packet,indent=2,sort_keys=True)+"\n")
            completed=subprocess.run(["python3",str(processor),"--envelope",str(envelope),"--out",str(out),
                                      "--hb-epoch",str(hb_epoch)],cwd=root,capture_output=True,text=True,check=False)
            if completed.returncode!=0 or not out.is_file():
                raise ValueError("endpoint_adapter_execution_failed:"+completed.stderr[-512:])
            result=json.loads(out.read_text())
            if not isinstance(result,dict): raise ValueError("endpoint_adapter_result_invalid")
            return result
    if role not in {"BOUNDARY_LOCAL_DIAGNOSTIC","BOUNDARY_LOCAL_CONTROL",CAPABILITY_INGRESS_ROLE}:
        raise ValueError("endpoint_adapter_not_installed")
    prev=None; receipts=[]
    for kind in ("INGRESS_ACCEPTED","DISPATCHED","CONSUMED","RESULT_BOUND","EGRESS_EMITTED"):
        r=receipt(kind,packet["packet_id"],service["service_id"],prev,{"payload_hash":sha(packet["payload"])})
        receipts.append(r); prev=r["receipt_id"]
    if role=="BOUNDARY_LOCAL_CONTROL":
        application_result=handle_control_message(root,packet,registry,hb_epoch=hb_epoch)
    elif role==CAPABILITY_INGRESS_ROLE:
        # The address resolves to the receiving operation the overlay binds.
        # That operation records both ledger levels itself. A refusal here is
        # this boundary's refusal, not a consumed crossing with the refusal
        # buried in the application result. Loaded only for this role.
        try:
            application_result=capability_ingress(root).receive(
                root,service,packet,registry=registry,mesh_root=mesh_root,hb_epoch=hb_epoch)
        except SystemExit as refused:
            raise ValueError("capability_ingress_refused:"+str(refused)) from None
    else:
        application_result={"echo":packet["payload"]}
    result={"schema_version":SCHEMA,"organization":registry["organization"],"packet_id":packet["packet_id"],
            "service_id":service["service_id"],"consumed":True,"application_result":application_result,
            "authority_effect":packet["transition"]["authority_effect"],"receipts":receipts,
            "reconstruction":{"same_execution_required":True,"status":"RECONSTRUCTED","terminal_receipt_id":prev}}
    if role==CAPABILITY_INGRESS_ROLE:
        # This kernel has no manifest processor selector. At this role nothing
        # is selected: the overlay names the receiving operation, and that
        # operation acknowledges the diagnostic.
        result["processing_selection"]="BOUNDARY_LOCAL_NO_PROCESSOR_SELECTED"
    return result

def persist_outbox(root:Path, frame:dict[str,Any])->Path:
    out=root/"resident-runtime/federation/outbox"; out.mkdir(parents=True,exist_ok=True)
    path=out/(hashlib.sha256(frame["packet_id"].encode()).hexdigest()+".json")
    if path.exists():
        if json.loads(path.read_text())!=frame: raise ValueError("write_once_collision")
        return path
    path.write_text(json.dumps(frame,indent=2,sort_keys=True)+"\n")
    return path

INGEST_EPOCH_RETRY_ENTRYPOINT=("org-kernel/kernel.py::ingest_frame (a frame whose heartbeat is supplied, "
                               "or hb_epoch=, or "+SUPPLIED_EPOCH_ENV+")")

HB_EPOCH_CONFLICT="HB_EPOCH_CONFLICT"

def consuming_epoch(frame:dict[str,Any], hb_epoch:Any=None, *, explicit:bool=True)->int|None:
    """The epoch a frame is consumed at, None when it has none, or SuppliedEpochRefused.

    Nothing is written. ``hb_epoch`` is the caller's epoch: ``explicit`` when a
    caller passed it for this frame (B-P36l), or a cycle's fallback for frames
    that lend none. ``STEGVERSE_HB_EPOCH`` is a fallback too. Frame classes
    (NARROW S1):

    - SUPPLIED (the shared rule passes): consumed at the heartbeat's epoch. An
      explicit epoch that differs is HB_EPOCH_CONFLICT. A cycle's supplied
      epoch stamps this organization's receipts and responses instead; the
      frame's epoch is then inbound provenance only (B-P36l, 08:48Z).
    - CARRIED (a self-asserted ``source``/``head_receipt_sha``): refused
      CARRIED_NOT_ACCEPTED_BY_DESTINATION, never stripped and taken as supplied.
    - CLOCK (``derived_from_clock`` true, or the legacy sample with no flag,
      from the WU-B13-scoped frame-only publishers): consumed, lending no
      epoch. The caller's epoch is used when there is one; otherwise None, and
      a route that needs an epoch refuses HB_EPOCH_NOT_SUPPLIED.
    - Anything else the rule refuses (UNMARKED, an invalid epoch or reference):
      refused with the rule's code.

    An explicit epoch the rule refuses is refused whatever the frame carries.
    A frame with no heartbeat at all lends none, as a CLOCK frame: it takes the
    caller's epoch, else None (§Q: a cycle with none leaves it pending).
    """
    if explicit and hb_epoch is not None:
        hb_epoch=supplied_epoch(hb_epoch,retry_entrypoint=INGEST_EPOCH_RETRY_ENTRYPOINT)
        stated=hb_epoch
    else:
        stated=None
    def caller()->int|None:
        raw=caller_epoch(hb_epoch)
        return None if raw is None else supplied_epoch(raw,retry_entrypoint=INGEST_EPOCH_RETRY_ENTRYPOINT)
    reference=frame.get("heartbeat_reference") if isinstance(frame,dict) else None
    if reference is None:
        return caller()
    if isinstance(reference,dict) and _carried(reference):
        raise SuppliedEpochRefused(carried_refusal(reference,INGEST_EPOCH_RETRY_ENTRYPOINT))
    failure=supplied_epoch_failure(reference.get("epoch") if isinstance(reference,dict) else None,reference)
    if failure is None:
        _check_reference_identity(reference)
        carried=int(reference["epoch"])
        if stated is not None and stated!=carried:
            raise SuppliedEpochRefused(_epoch_refusal(
                HB_EPOCH_CONFLICT,"the explicit hb_epoch "+str(stated)+" differs from the frame's supplied epoch "
                +str(carried),INGEST_EPOCH_RETRY_ENTRYPOINT,
                repair="supply no epoch, or the frame's own; two supplied epochs that differ are never reconciled"))
        if stated is None and not explicit:
            # A cycle's supplied epoch stamps this organization's own receipts and
            # responses; the frame's epoch is inbound provenance only.
            cycle=caller()
            if cycle is not None:
                return cycle
        return carried
    if _clock_flagged(reference):
        # F-S1a: a CLOCK frame whose own epoch is malformed is refused (and so
        # quarantined by a cycle), not consumed.
        malformed=supplied_epoch_failure(reference.get("epoch"))
        if malformed is not None:
            raise SuppliedEpochRefused(_epoch_refusal(malformed[0],"the CLOCK frame's own epoch is malformed: "
                                                      +malformed[1],INGEST_EPOCH_RETRY_ENTRYPOINT))
        _check_reference_identity(reference)
        return caller()
    raise SuppliedEpochRefused(_epoch_refusal(failure[0],failure[1],INGEST_EPOCH_RETRY_ENTRYPOINT))

HB_REFERENCE_INVALID="HB_REFERENCE_INVALID"
FRAME_INTEGRITY_INVALID="FRAME_INTEGRITY_INVALID"
FRAME_INGEST_FAILED="FRAME_INGEST_FAILED"
FRAME_DISPATCH_IO_FAILED="FRAME_DISPATCH_IO_FAILED"

#: Collisions in this boundary's own write-once state, not in what a frame carries.
OWN_STATE_COLLISIONS={"federation_seen_marker_collision"}

def own_state_fault(error:BaseException)->bool:
    """Whether ``error`` is a fault writing this repository's own state (F-TRANSIENT-RT).

    The ledgers' dedicated ``LedgerWriteFailed`` (an I/O error, a lost
    compare-and-swap, a store collision), any OSError met after the frame was
    read, a lost comparison raised by another store, and a collision in this
    boundary's seen markers. None is a defect of the frame.
    """
    if getattr(error,"own_state_write_failure",False) or isinstance(error,OSError):
        return True
    if isinstance(error,RuntimeError) and "lost_comparison" in str(error).lower():
        return True
    return isinstance(error,ValueError) and str(error) in OWN_STATE_COLLISIONS

def own_state_write_refusal(error:BaseException, retry_entrypoint:str)->dict[str,Any]:
    """The six-field, non-terminal refusal for a fault writing this repository's own state.

    Nothing the ledgers name was published, so the same call is retried and
    lands once; the frame or input is not at fault.
    """
    return {"disposition":"FAIL_CLOSED","failure_code":FRAME_DISPATCH_IO_FAILED,
            "failed_predicate":getattr(error,"failed_predicate",None) or type(error).__name__,
            "detail":type(error).__name__+": "+str(error),
            "required_evidence_or_repair":"this repository's own state is writable again; the same input is retried",
            "retry_entrypoint":retry_entrypoint,
            "owning_existing_goal":HB_EPOCH_OWNING_EXISTING_GOAL,
            "next_attempt":"the next cycle retries it; no marker was written and no ledger entry was left unnamed",
            "terminal":False,"derived_from_clock":False,"consequence_committed":False}

def _check_reference_identity(reference:dict[str,Any])->None:
    """A heartbeat whose generation or id names another epoch than its own is HB_REFERENCE_INVALID."""
    epoch=int(reference["epoch"])
    if "generation" in reference and reference["generation"]!=epoch:
        raise SuppliedEpochRefused(_epoch_refusal(
            HB_REFERENCE_INVALID,"heartbeat generation "+repr(reference["generation"])+" is not its epoch "+str(epoch),
            INGEST_EPOCH_RETRY_ENTRYPOINT,repair="the sender re-emits the crossing with a consistent heartbeat"))
    if "heartbeat_id" in reference and reference["heartbeat_id"]!="HB:"+str(epoch):
        raise SuppliedEpochRefused(_epoch_refusal(
            HB_REFERENCE_INVALID,"heartbeat id "+repr(reference["heartbeat_id"])+" is not HB:"+str(epoch),
            INGEST_EPOCH_RETRY_ENTRYPOINT,repair="the sender re-emits the crossing with a consistent heartbeat"))

def frame_failure_refusal(error:BaseException, *, own_state:bool=True)->dict[str,Any]:
    """The six-field refusal for an error raised while ingesting one frame (B-P36o). Nothing is written.

    The guard is total. A fault writing this repository's own state
    (``own_state_fault``) is checked first: FRAME_DISPATCH_IO_FAILED,
    ``terminal: false`` and ``frame_left_pending``, so the frame is retried.
    ``own_state=False`` is for an error reading the frame file itself
    (B-P36p), which is the frame's. A carrier or packet hash, or a packet
    binding that does not match its frame, is FRAME_INTEGRITY_INVALID. Any
    other error, of any class, is FRAME_INGEST_FAILED, with the exception
    class as the failed predicate.
    """
    if own_state and own_state_fault(error):
        return {**own_state_write_refusal(error,INGEST_EPOCH_RETRY_ENTRYPOINT),"frame_left_pending":True}
    carried=getattr(error,"refusal",None)
    if isinstance(error,ValueError) and isinstance(carried,dict) and carried.get("failure_code"):
        # A six-field refusal raised by this kernel or a receiving operation
        # (each loaded kernel has its own SuppliedEpochRefused class).
        return dict(carried)
    detail=str(error)
    if isinstance(error,ValueError) and detail.endswith("_mismatch"):
        refusal=_epoch_refusal(FRAME_INTEGRITY_INVALID,"the frame does not recover its packet: "+detail,
                               INGEST_EPOCH_RETRY_ENTRYPOINT,repair="the sender re-emits the crossing as an intact frame")
        refusal["failed_predicate"]="FRAME_RECOVERS_ITS_PACKET"
        return refusal
    refusal=_epoch_refusal(FRAME_INGEST_FAILED,type(error).__name__+": "+detail,INGEST_EPOCH_RETRY_ENTRYPOINT,
                           repair="the sender re-emits the crossing as a frame this boundary can ingest")
    refusal["failed_predicate"]=type(error).__name__
    return refusal

def _clock_frame_refusal()->dict[str,Any]:
    return _epoch_refusal(HB_EPOCH_NOT_SUPPLIED,
                          "the frame's heartbeat is CLOCK and lends no epoch, and no caller epoch was supplied; this route needs one and no clock is read",
                          INGEST_EPOCH_RETRY_ENTRYPOINT,
                          repair="the sender re-emits the crossing as a frame whose heartbeat is supplied")

def stamps_time(service:dict[str,Any], packet:dict[str,Any])->bool:
    """Whether dispatching ``packet`` at ``service`` stamps time, so needs a supplied epoch."""
    role=service.get("boundary_role")
    return bool((role=="INTERNAL_ENDPOINT" and service.get("endpoint_adapter")) or role==CAPABILITY_INGRESS_ROLE
                or (role=="BOUNDARY_LOCAL_CONTROL"
                    and (packet.get("payload") or {}).get("message_class")=="ecosystem.monitor.request"))

def answers(packet:dict[str,Any])->bool:
    """Whether consuming ``packet`` publishes a response frame, which is stamped at an epoch."""
    return (packet.get("payload") or {}).get("message_class") in {
        "ecosystem.monitor.request","ecosystem.work.request","ecosystem.communication"}

def _service(root:Path, packet:dict[str,Any])->dict[str,Any]|None:
    destination=(packet.get("destination") or {}).get("service")
    return next((s for s in load_registry(root)["services"] if s["service_id"]==destination),None)

FRAME_REFUSED_QUARANTINED="FRAME_REFUSED_QUARANTINED"

def admit_frame(frame:dict[str,Any], hb_epoch:Any=None, *,
                root:Path|None=None)->tuple[int|None,dict[str,Any]|None]:
    """A frame's consuming epoch (None when it has none), or its refusal. Nothing is written.

    ``hb_epoch`` is a cycle's fallback, not an explicit epoch for each frame.
    A refusal for what the frame itself carries (UNMARKED, CARRIED, an invalid
    epoch, an integrity or ingest error) makes the frame terminal. With
    ``root``, a valid frame that lends no epoch, addressed to a route that
    stamps time or answers it, met by a cycle with none, is refused
    HB_EPOCH_NOT_SUPPLIED with ``frame_left_pending``: it is not the frame's
    defect, so it stays unseen for a cycle that carries an epoch (§Q).
    """
    try:
        packet=recover_packet(frame)
        epoch=consuming_epoch(frame,hb_epoch,explicit=False)
        if epoch is None and root is not None:
            service=_service(root,packet)
            if service is not None and (stamps_time(service,packet) or answers(packet)):
                return None,{**_clock_frame_refusal(),"frame_left_pending":True}
        return epoch,None
    except (Exception,SystemExit) as error:
        return None,frame_failure_refusal(error)

def admit_item(item:dict[str,Any], hb_epoch:Any=None, *,
               root:Path|None=None)->tuple[int|None,dict[str,Any]|None]:
    """``admit_frame`` for a scanned item. A file that is not a frame is FRAME_INGEST_FAILED (F-SCAN)."""
    if "unreadable" in item:
        return None,frame_failure_refusal(item["unreadable"],own_state=False)
    return admit_frame(item["frame"],hb_epoch,root=root)

def ingest_frame(root:Path, frame:dict[str,Any], *, mesh_root:Path|None=None,
                 hb_epoch:Any=None, explicit:bool=True)->dict[str,Any]:
    """Consume one frame at its supplied epoch (see ``consuming_epoch``), or refuse it.

    ``hb_epoch`` is explicit by default: an invalid one is refused, and one
    that differs from the frame's supplied epoch is HB_EPOCH_CONFLICT. A cycle
    passes its own epoch with ``explicit=False``, and that epoch stamps.
    """
    packet=recover_packet(frame)
    registry=load_registry(root)
    if frame["destination_org"]!=registry["organization"]:
        return {"status":"IGNORED_NOT_ADDRESSED","packet_id":frame["packet_id"]}
    hb_epoch=consuming_epoch(frame,hb_epoch,explicit=explicit)
    if hb_epoch is None:
        # A CLOCK frame lends no epoch, and the caller supplied none.
        service=_service(root,packet)
        if service is not None and stamps_time(service,packet):
            raise SuppliedEpochRefused(_clock_frame_refusal())
    result=dispatch(root,packet,mesh_root=mesh_root,hb_epoch=hb_epoch)
    return {"status":"CONSUMED","packet":packet,"execution_result":result}

__all__=["hb_reference","HB_EPOCH_NOT_SUPPLIED","HB_EPOCH_INVALID","SuppliedEpochRefused","writer_epoch_refusal","supplied_epoch",
         "HB_EPOCH_PROVENANCE_UNMARKED","CARRIED_PROVENANCE_UNVERIFIED","CARRIED_NOT_ACCEPTED_BY_DESTINATION",
         "ACCEPTS_CARRIED_CROSSINGS","HB_EPOCH_CONFLICT",
         "SHARED_VALIDATOR_SHA256","supplied_epoch_failure","stamps_time",
         "SUPPLIED_EPOCH_ENV","caller_epoch","epoch_now_ns","frame_epoch","consuming_epoch","carried_refusal",
         "FRAME_REFUSED_QUARANTINED","admit_frame","FRAME_DISPATCH_IO_FAILED","own_state_fault","own_state_write_refusal","frame_failure_refusal","FRAME_FILE_MAX_BYTES","answers",
         "HB_REFERENCE_INVALID","FRAME_INTEGRITY_INVALID","FRAME_INGEST_FAILED","derive_channel","carrier_frame","recover_packet","dispatch","persist_outbox","ingest_frame",
         "capability_ingress","CAPABILITY_INGRESS_ROLE"]


# --- Federation mesh v1.1 additions ---
FEDERATION_ROOT_ENV="STEGVERSE_ORG_FEDERATION_ROOT"

def federation_root(env:dict[str,str]|None=None)->Path:
    values=os.environ if env is None else env
    override=values.get(FEDERATION_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    base=Path(values.get("XDG_STATE_HOME",str(Path.home()/".local"/"state")))
    return (base/"stegverse"/"org-federation").resolve()

def publish_frame(frame:dict[str,Any], *, root:Path|None=None)->Path:
    mesh=(root or federation_root()).resolve()
    frames=mesh/"frames.d"
    frames.mkdir(parents=True,exist_ok=True)
    frame_id=hashlib.sha256((frame["packet_id"]+"|"+frame["frame_sha256"]).encode()).hexdigest()
    path=frames/(frame_id+".json")
    if path.exists():
        existing=json.loads(path.read_text())
        if existing!=frame:
            raise ValueError("federation_frame_write_once_collision")
        return path
    path.write_text(json.dumps(frame,indent=2,sort_keys=True)+"\n")
    return path

#: The largest frames.d file a scan reads (B-P36p). A carrier frame is a few KiB.
FRAME_FILE_MAX_BYTES=1<<20

def scan_addressed_frames(organization:str, *, root:Path|None=None, seen:set[str]|None=None,
                          include_unreadable:bool=False)->list[dict[str,Any]]:
    """The frames in ``frames.d`` addressed to ``organization``, in name order.

    Each file is read on its own (F-SCAN, B-P36p). One that cannot be read,
    exceeds FRAME_FILE_MAX_BYTES, is not UTF-8, or is not a JSON object is
    skipped, or, with ``include_unreadable``, returned as ``{"path",
    "frame": None, "unreadable": <error>}`` for its consumer to quarantine.
    One bad file never stops the scan.
    """
    mesh=(root or federation_root()).resolve()
    frames=mesh/"frames.d"
    if not frames.exists():
        return []
    consumed=seen or set()
    out=[]
    for path in sorted(frames.glob("*.json")):
        if path.name in consumed:
            continue
        try:
            if path.stat().st_size>FRAME_FILE_MAX_BYTES:
                raise ValueError("frame_file_exceeds_max_bytes: "+str(path.stat().st_size)+" > "+str(FRAME_FILE_MAX_BYTES))
            frame=json.loads(path.read_bytes().decode("utf-8"))
            if not isinstance(frame,dict):
                raise ValueError("frame_is_not_a_json_object: "+type(frame).__name__)
        except (OSError,ValueError) as error:
            if include_unreadable:
                out.append({"path":str(path),"frame":None,"unreadable":error})
            continue
        if frame.get("destination_org")==organization:
            out.append({"path":str(path),"frame":frame})
    return out

def build_packet(*, origin_org:str, origin_service:str, destination_org:str, destination_service:str,
                 payload:dict[str,Any], transition_reference:str="federation.v1",
                 authority_effect:str="NONE", packet_id:str|None=None)->dict[str,Any]:
    pid=packet_id or "pkt-"+hashlib.sha256(canon({
        "origin_org":origin_org,"origin_service":origin_service,"destination_org":destination_org,
        "destination_service":destination_service,"payload":payload,"transition_reference":transition_reference
    })).hexdigest()[:24]
    return {
      "schema_version":PACKET_SCHEMA,
      "packet_id":pid,
      "direction":"INGRESS",
      "origin":{"org":origin_org,"service":origin_service},
      "destination":{"org":destination_org,"service":destination_service},
      "carrier":{"kind":"HB_DERIVED","reference":"org-federation"},
      "intr_profile":"stegverse.intr.org-boundary.v1",
      "transition":{"reference":transition_reference,"authority_effect":authority_effect,"conditions":[]},
      "payload":payload,
      "evidence":{"ingress_receipt":None,"dispatch_receipt":None,"consumption_receipt":None,"egress_receipt":None,"reconstruction_reference":None}
    }

def publish_packet(packet:dict[str,Any], *, root:Path|None=None, now_ns:int|None=None)->dict[str,Any]:
    frame=carrier_frame(packet,now_ns=now_ns)
    path=publish_frame(frame,root=root)
    return {"packet":packet,"frame":frame,"path":str(path)}

def consume_addressed_frames(repo_root:Path, *, mesh_root:Path|None=None, seen:set[str]|None=None,
                             hb_epoch:Any=None)->list[dict[str,Any]]:
    registry=load_registry(repo_root)
    organization=registry["organization"]
    items=scan_addressed_frames(organization,root=mesh_root,seen=seen,include_unreadable=True)
    # Every frame is admitted or refused before the first is consumed. A refused
    # frame is reported, not consumed, and does not stop the frames after it.
    admitted=[admit_item(item,hb_epoch,root=repo_root) for item in items]
    results=[]
    for item,(epoch,refusal) in zip(items,admitted):
        if refusal is not None:
            results.append({"path":item["path"],"result":{
                                "status":"PENDING" if refusal.get("frame_left_pending") else "REFUSED",
                                                          "packet_id":(item["frame"] or {}).get("packet_id"),
                                                          "refusal":refusal}})
            continue
        try:
            result=ingest_frame(repo_root,item["frame"],mesh_root=mesh_root,hb_epoch=epoch,explicit=False)
        except (Exception,SystemExit) as error:
            # B-P36o: one frame's failure is that frame's refusal; the next frame proceeds.
            refusal=frame_failure_refusal(error)
            result={"status":"PENDING" if refusal.get("frame_left_pending") else "REFUSED",
                    "packet_id":item["frame"].get("packet_id"),"refusal":refusal}
        results.append({"path":item["path"],"result":result,"inbound_frame_epoch":frame_epoch(item["frame"])})
    return results


# --- Ecosystem-wide communication v1.2 additions ---
def organization_slug(organization:str)->str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in organization).strip("-")

def build_ecosystem_packets(*, origin_org:str, origin_service:str, organizations:list[str],
                            message_class:str, subject:str, body:dict[str,Any],
                            requested_action:str|None=None, transition_reference:str="ecosystem.communication.v1",
                            authority_effect:str="NONE", communication_id:str|None=None)->dict[str,Any]:
    ordered=sorted(dict.fromkeys(organizations))
    if not ordered:
        raise ValueError("organizations_required")
    comm_id=communication_id or "ecosystem-"+hashlib.sha256(canon({
        "origin_org":origin_org,"origin_service":origin_service,"organizations":ordered,
        "message_class":message_class,"subject":subject,"body":body,
        "requested_action":requested_action,"transition_reference":transition_reference
    })).hexdigest()[:24]
    packets=[]
    for org in ordered:
        service=organization_slug(org)+".org-control"
        payload={
          "communication_id":comm_id,
          "message_class":message_class,
          "subject":subject,
          "body":body,
          "requested_action":requested_action,
          "audience":"ECOSYSTEM",
          "target_organization":org,
          "target_count":len(ordered)
        }
        packet=build_packet(
          origin_org=origin_org,
          origin_service=origin_service,
          destination_org=org,
          destination_service=service,
          payload=payload,
          transition_reference=transition_reference,
          authority_effect=authority_effect,
          packet_id=comm_id+":"+organization_slug(org)
        )
        packets.append(packet)
    return {"communication_id":comm_id,"organization_count":len(ordered),"packets":packets}

def publish_ecosystem_message(*, origin_org:str, origin_service:str, organizations:list[str],
                              message_class:str, subject:str, body:dict[str,Any],
                              requested_action:str|None=None, transition_reference:str="ecosystem.communication.v1",
                              authority_effect:str="NONE", communication_id:str|None=None,
                              root:Path|None=None, now_ns:int|None=None)->dict[str,Any]:
    built=build_ecosystem_packets(
      origin_org=origin_org,origin_service=origin_service,organizations=organizations,
      message_class=message_class,subject=subject,body=body,requested_action=requested_action,
      transition_reference=transition_reference,authority_effect=authority_effect,
      communication_id=communication_id
    )
    publications=[publish_packet(packet,root=root,now_ns=now_ns) for packet in built["packets"]]
    return {"communication_id":built["communication_id"],"organization_count":built["organization_count"],
            "published_count":len(publications),"publications":publications}

def aggregate_ecosystem_results(communication_id:str, results_by_org:dict[str,list[dict[str,Any]]])->dict[str,Any]:
    rows=[]
    for org,items in sorted(results_by_org.items()):
        matched=[]
        for item in items:
            result=item.get("result") or {}
            packet=result.get("packet") or {}
            payload=packet.get("payload") or {}
            if payload.get("communication_id")==communication_id:
                matched.append(item)
        status="CONSUMED" if any((x.get("result") or {}).get("status")=="CONSUMED" for x in matched) else "NOT_OBSERVED"
        terminal=None
        for x in matched:
            er=(x.get("result") or {}).get("execution_result") or {}
            terminal=(er.get("reconstruction") or {}).get("terminal_receipt_id") or terminal
        rows.append({"organization":org,"status":status,"terminal_receipt_id":terminal})
    consumed=sum(1 for row in rows if row["status"]=="CONSUMED")
    return {"communication_id":communication_id,"organization_count":len(rows),
            "consumed_count":consumed,"pending_count":len(rows)-consumed,
            "complete":consumed==len(rows) and len(rows)>0,"organizations":rows}


# --- Ecosystem control/response v1.3 additions ---
def load_federation_directory(root:Path)->dict[str,Any]:
    path=root/"org-boundary/registry/federation.json"
    value=json.loads(path.read_text())
    if value.get("denominator")!=len(value.get("organizations") or []):
        raise ValueError("federation_directory_denominator_mismatch")
    return value

def resident_status(root:Path, registry:dict[str,Any]|None=None, *, now_ns:int|None=None)->dict[str,Any]:
    reg=registry or load_registry(root)
    activation_path=root/"resident-runtime/activation-manifest.json"
    activation=json.loads(activation_path.read_text()) if activation_path.exists() else {}
    kernel=(activation.get("kernel") or {})
    return {
      "organization":reg["organization"],
      "kernel_version":kernel.get("version"),
      "activation_state":activation.get("state"),
      "registered_service_count":len(reg.get("services") or []),
      "registered_services":[s.get("service_id") for s in reg.get("services") or []],
      "org_control_service":organization_slug(reg["organization"])+".org-control",
      "heartbeat_reference":hb_reference(now_ns),
      "runtime_observation_claimed":False
    }

def persist_work_request(root:Path, packet:dict[str,Any])->dict[str,Any]:
    payload=packet.get("payload") or {}
    communication_id=payload.get("communication_id")
    inbox=root/"resident-runtime/control/inbox"
    inbox.mkdir(parents=True,exist_ok=True)
    name=hashlib.sha256((packet["packet_id"]+"|"+str(communication_id)).encode()).hexdigest()+".json"
    path=inbox/name
    record={
      "schema_version":"stegverse.ecosystem-work-intake.v1",
      "communication_id":communication_id,
      "packet_id":packet["packet_id"],
      "origin":packet["origin"],
      "destination":packet["destination"],
      "requested_action":payload.get("requested_action"),
      "body":payload.get("body"),
      "transition":packet["transition"],
      "state":"QUEUED_FOR_LOCAL_ADMISSION_EVALUATION",
      "execution_authority_inferred":False,
      "execution_authority_constraint":"CONSTRAINT_VARIABLE",
      "time_constraint":"CONSTRAINT_VARIABLE"
    }
    if path.exists():
        if json.loads(path.read_text())!=record:
            raise ValueError("work_intake_write_once_collision")
    else:
        path.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    return {"state":record["state"],"intake_ref":str(path),"execution_authority_inferred":False}

def handle_control_message(root:Path, packet:dict[str,Any], registry:dict[str,Any], *,
                           hb_epoch:int|None=None)->dict[str,Any]:
    payload=packet.get("payload") or {}
    message_class=payload.get("message_class")
    result={
      "message_received":True,
      "message_class":message_class,
      "communication_id":payload.get("communication_id"),
      "requested_action":payload.get("requested_action"),
      "execution_authority_inferred":False,
      "execution_authority_effect":packet["transition"]["authority_effect"]
    }
    if message_class=="ecosystem.monitor.request":
        # A monitor request is dispatched only with a supplied epoch.
        result["monitor_status"]=resident_status(root,registry,now_ns=epoch_now_ns(hb_epoch))
    elif message_class=="ecosystem.work.request":
        result["work_intake"]=persist_work_request(root,packet)
    elif message_class=="ecosystem.communication":
        result["communication_acknowledged"]=True
    elif message_class in {"ecosystem.monitor.response","ecosystem.work.ack","ecosystem.communication.ack"}:
        result["response_acknowledged"]=True
    return result

def response_message_class(request_class:str|None)->str:
    return {
      "ecosystem.monitor.request":"ecosystem.monitor.response",
      "ecosystem.work.request":"ecosystem.work.ack",
      "ecosystem.communication":"ecosystem.communication.ack"
    }.get(request_class or "","ecosystem.communication.ack")

def build_control_response(request_packet:dict[str,Any], execution_result:dict[str,Any])->dict[str,Any]:
    req_payload=request_packet.get("payload") or {}
    origin_org=request_packet["origin"]["org"]
    local_org=request_packet["destination"]["org"]
    cls=response_message_class(req_payload.get("message_class"))
    payload={
      "communication_id":req_payload.get("communication_id"),
      "message_class":cls,
      "subject":"response:"+str(req_payload.get("subject") or ""),
      "body":{
        "request_packet_id":request_packet["packet_id"],
        "responding_organization":local_org,
        "application_result":execution_result.get("application_result"),
        "receipt_terminal":(execution_result.get("reconstruction") or {}).get("terminal_receipt_id")
      },
      "requested_action":None,
      "audience":"ORIGIN",
      "target_organization":origin_org,
      "target_count":1
    }
    return build_packet(
      origin_org=local_org,
      origin_service=organization_slug(local_org)+".org-control",
      destination_org=origin_org,
      destination_service=organization_slug(origin_org)+".org-control",
      payload=payload,
      transition_reference=str((request_packet.get("transition") or {}).get("reference") or "ecosystem.communication.v1")+".response",
      authority_effect="NONE",
      packet_id=str(req_payload.get("communication_id"))+":response:"+organization_slug(local_org)
    )

def build_endpoint_response(request_packet:dict[str,Any], execution_result:dict[str,Any])->dict[str,Any]:
    payload={
      "schema":"stegverse.org-endpoint-response/v1",
      "response_to_packet_id":request_packet["packet_id"],
      "request_manifest_sha256":((request_packet.get("payload") or {}).get("request") or {}).get("bindings",{}).get("manifest_sha256"),
      "execution_result":execution_result,
      "authority_transfer":False
    }
    return build_packet(
      origin_org=request_packet["destination"]["org"],
      origin_service=request_packet["destination"]["service"],
      destination_org=request_packet["origin"]["org"],
      destination_service=request_packet["origin"]["service"],
      payload=payload,
      transition_reference=str((request_packet.get("transition") or {}).get("reference") or "endpoint")+".response",
      authority_effect="NONE_RESPONSE_ONLY",
      packet_id=request_packet["packet_id"]+":response"
    )

CONSUME_EPOCH_RETRY_ENTRYPOINT="org-kernel/kernel.py::consume_and_respond (hb_epoch=, or "+SUPPLIED_EPOCH_ENV+")"

def consume_and_respond(repo_root:Path, *, mesh_root:Path|None=None, seen:set[str]|None=None,
                        hb_epoch:Any=None)->list[dict[str,Any]]:
    """Consume addressed frames and publish each response at that frame's epoch.

    Every frame is admitted at the epoch its heartbeat supplies (see
    ``consuming_epoch``), or refused, before the first is consumed. A refused
    frame (CLOCK, CARRIED, invalid) gets a six-field FRAME_REFUSED_QUARANTINED
    seen marker and is terminal: it is never re-processed and never blocks a
    later cycle. Nothing is stamped from a clock.
    """
    if caller_epoch(hb_epoch) is not None:
        hb_epoch=supplied_epoch(caller_epoch(hb_epoch),retry_entrypoint=CONSUME_EPOCH_RETRY_ENTRYPOINT)
    registry=load_registry(repo_root)
    organization=registry["organization"]
    durable_seen=federation_seen_frame_names(repo_root)
    effective_seen=set(seen or set())|durable_seen
    out=[]
    items=scan_addressed_frames(organization,root=mesh_root,seen=effective_seen,include_unreadable=True)
    admitted=[admit_item(item,hb_epoch,root=repo_root) for item in items]
    def pending(item:dict[str,Any], refusal:dict[str,Any])->dict[str,Any]:
        # §Q, F-TRANSIENT-RT: the cycle lacks the epoch, or this repository's own
        # state could not be written; neither is the frame's defect. No seen
        # marker and no quarantine, so a later cycle consumes it once.
        status=("PENDING_DISPATCH_IO_FAILED" if refusal.get("failure_code")==FRAME_DISPATCH_IO_FAILED
                else "PENDING_EPOCH_NOT_SUPPLIED")
        return {"path":item["path"],
                "result":{"status":status,"packet_id":(item["frame"] or {}).get("packet_id"),"refusal":refusal},
                "response_publication":None,"seen_marker":None}
    def quarantined(item:dict[str,Any], refusal:dict[str,Any])->dict[str,Any]:
        try:
            marker=quarantine_refused_frame(repo_root,item["path"],item["frame"],refusal)
        except (Exception,SystemExit) as error:
            if not own_state_fault(error):
                raise
            return pending(item,{**own_state_write_refusal(error,INGEST_EPOCH_RETRY_ENTRYPOINT),
                                 "frame_left_pending":True})
        return {"path":item["path"],
                "result":{"status":"REFUSED_QUARANTINED","packet_id":(item["frame"] or {}).get("packet_id"),
                          "refusal":refusal},
                "response_publication":None,"seen_marker":str(marker)}
    for item,(epoch,refusal) in zip(items,admitted):
        if refusal is not None and refusal.get("frame_left_pending"):
            out.append(pending(item,refusal))
        elif refusal is not None:
            out.append(quarantined(item,refusal))
    def respond(item:dict[str,Any], epoch:int|None)->dict[str,Any]:
        packet=recover_packet(item["frame"])
        payload=packet.get("payload") or {}
        message_class=payload.get("message_class")
        result=ingest_frame(repo_root,item["frame"],mesh_root=mesh_root,hb_epoch=epoch,explicit=False)
        response_publication=None
        if epoch is None:
            # A CLOCK frame at a route that neither stamps time nor answers: consumed,
            # with nothing to stamp. One that would be answered is left pending above.
            marker=mark_federation_frame_seen(repo_root,item["path"],item["frame"],result)
            return {"path":item["path"],"result":result,"response_publication":None,"seen_marker":str(marker),
                    "inbound_frame_epoch":frame_epoch(item["frame"])}
        now_ns=epoch_now_ns(epoch)
        if result.get("status")=="CONSUMED" and message_class in {
            "ecosystem.monitor.request","ecosystem.work.request","ecosystem.communication"}:
            response=build_control_response(packet,result["execution_result"])
            response_publication=publish_response_once(repo_root,packet["packet_id"],response,
                                                       mesh_root=mesh_root,now_ns=now_ns)
        elif result.get("status")=="CONSUMED" and not payload.get("response_to_packet_id"):
            service=next((svc for svc in registry["services"] if svc.get("service_id")==packet["destination"]["service"]),None)
            if service and service.get("endpoint_adapter"):
                response=build_endpoint_response(packet,result["execution_result"])
                response_publication=publish_response_once(repo_root,packet["packet_id"],response,
                                                           mesh_root=mesh_root,now_ns=now_ns)
        marker=mark_federation_frame_seen(repo_root,item["path"],item["frame"],result)
        # The frame's own epoch, when it lent one, is inbound provenance; this
        # organization stamped at ``epoch``.
        return {"path":item["path"],"result":result,"response_publication":response_publication,"seen_marker":str(marker),
                "inbound_frame_epoch":frame_epoch(item["frame"])}

    for item,(epoch,refusal) in zip(items,admitted):
        if refusal is not None:
            continue
        try:
            out.append(respond(item,epoch))
        except (Exception,SystemExit) as error:
            # B-P36o: an error ingesting one frame is that frame's six-field refusal and a
            # terminal quarantine; a fault writing this repository's own state leaves it
            # pending instead. The cycle continues to the next frame.
            refusal=frame_failure_refusal(error)
            out.append(pending(item,refusal) if refusal.get("frame_left_pending") else quarantined(item,refusal))
    return out

def collect_ecosystem_responses(origin_org:str, communication_id:str, *, mesh_root:Path|None=None)->dict[str,Any]:
    responses=[]
    for item in scan_addressed_frames(origin_org,root=mesh_root):
        packet=recover_packet(item["frame"])
        payload=packet.get("payload") or {}
        if payload.get("communication_id")!=communication_id:
            continue
        if payload.get("message_class") not in {
            "ecosystem.monitor.response","ecosystem.work.ack","ecosystem.communication.ack"}:
            continue
        body=payload.get("body") or {}
        responses.append({
          "organization":body.get("responding_organization") or packet["origin"]["org"],
          "message_class":payload.get("message_class"),
          "request_packet_id":body.get("request_packet_id"),
          "application_result":body.get("application_result"),
          "receipt_terminal":body.get("receipt_terminal"),
          "response_packet_id":packet["packet_id"],
          "frame_sha256":item["frame"].get("frame_sha256")
        })
    dedup={}
    for row in responses:
        dedup[row["organization"]]=row
    rows=[dedup[k] for k in sorted(dedup)]
    return {
      "communication_id":communication_id,
      "response_count":len(rows),
      "organizations":rows
    }

def publish_ecosystem_from_directory(repo_root:Path, *, message_class:str, subject:str, body:dict[str,Any],
                                     requested_action:str|None=None, authority_effect:str="NONE",
                                     communication_id:str|None=None, mesh_root:Path|None=None,
                                     now_ns:int|None=None)->dict[str,Any]:
    registry=load_registry(repo_root)
    directory=load_federation_directory(repo_root)
    organizations=[row["organization"] for row in directory["organizations"]]
    origin=registry["organization"]
    return publish_ecosystem_message(
      origin_org=origin,
      origin_service=organization_slug(origin)+".org-control",
      organizations=organizations,
      message_class=message_class,
      subject=subject,
      body=body,
      requested_action=requested_action,
      authority_effect=authority_effect,
      communication_id=communication_id,
      root=mesh_root,
      now_ns=now_ns
    )


# --- Federation replay/dedup v1.3.1 additions ---
def federation_seen_frame_names(repo_root:Path)->set[str]:
    seen_dir=repo_root/"resident-runtime/federation/seen.d"
    if not seen_dir.exists():
        return set()
    names=set()
    for path in seen_dir.glob("*.json"):
        try:
            value=json.loads(path.read_text())
            if isinstance(value.get("frame_name"),str):
                names.add(value["frame_name"])
        except Exception:
            continue
    return names

def _write_json_atomic(path:Path, value:dict[str,Any])->Path:
    """Write a JSON document by same-directory replacement, so a failed write leaves no partial file."""
    fd,temp=tempfile.mkstemp(prefix=".write-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w") as stream:
            stream.write(json.dumps(value,indent=2,sort_keys=True)+"\n")
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return path

def _write_once_marker(marker_path:Path, marker:dict[str,Any])->Path:
    """Write a seen marker once, atomically, so a failed write leaves no partial marker."""
    if marker_path.exists():
        try:
            existing=json.loads(marker_path.read_text())
        except ValueError:
            existing=None  # not a marker: no frame is recorded as seen by it
        if existing==marker:
            return marker_path
        if existing is not None:
            raise ValueError("federation_seen_marker_collision")
    return _write_json_atomic(marker_path,marker)

RESPONSES_DIR="resident-runtime/federation/responses.d"

def response_frame_once(repo_root:Path, request_packet_id:str, response:dict[str,Any], *,
                        now_ns:int)->tuple[dict[str,Any],dict[str,Any]]:
    """The response packet and frame for a request, built once and then reused byte for byte (F-REPUB).

    A fault after a response is published (the seen marker, a gateway
    acknowledgement) leaves the request pending. Its retry publishes this same
    frame again, never a second response for the same request packet id.
    """
    directory=repo_root/RESPONSES_DIR
    path=directory/(hashlib.sha256(str(request_packet_id).encode()).hexdigest()+".json")
    if path.exists():
        try:
            stored=json.loads(path.read_text())
        except ValueError:
            stored=None  # a torn earlier write: rebuilt below
        if isinstance(stored,dict) and stored.get("request_packet_id")==request_packet_id:
            return stored["packet"],stored["frame"]
    frame=carrier_frame(response,now_ns=now_ns)
    directory.mkdir(parents=True,exist_ok=True)
    _write_json_atomic(path,{"request_packet_id":request_packet_id,"packet":response,"frame":frame})
    return response,frame

def publish_response_once(repo_root:Path, request_packet_id:str, response:dict[str,Any], *,
                          mesh_root:Path|None, now_ns:int)->dict[str,Any]:
    """``publish_packet`` for a response, idempotent per request packet id (see ``response_frame_once``)."""
    packet,frame=response_frame_once(repo_root,request_packet_id,response,now_ns=now_ns)
    path=publish_frame(frame,root=mesh_root)
    return {"packet":packet,"frame":frame,"path":str(path)}

def quarantine_refused_frame(repo_root:Path, frame_path:str, frame:dict[str,Any], refusal:dict[str,Any])->Path:
    """The six-field seen marker that makes a refused frame terminal. No clock is read."""
    seen_dir=repo_root/"resident-runtime/federation/seen.d"
    seen_dir.mkdir(parents=True,exist_ok=True)
    frame_name=Path(frame_path).name
    marker={
      "schema_version":"stegverse.federation-frame-consumption.v1",
      "frame_name":frame_name,
      "frame_sha256":frame.get("frame_sha256") if isinstance(frame,dict) else None,
      "packet_id":frame.get("packet_id") if isinstance(frame,dict) else None,
      "destination_org":frame.get("destination_org") if isinstance(frame,dict) else None,
      "status":"REFUSED",
      "disposition":"FAIL_CLOSED",
      "failure_code":FRAME_REFUSED_QUARANTINED,
      "failed_predicate":refusal.get("failed_predicate"),
      "detail":str(refusal.get("failure_code"))+": "+str(refusal.get("detail")),
      "refused_failure_code":refusal.get("failure_code"),
      "required_evidence_or_repair":("the sender re-emits the crossing as a new frame whose heartbeat is supplied "
                                     "(derived_from_clock false, no sampled_unix_ns, no unverified CARRIED claim); "
                                     "this frame is terminal and is never re-processed"),
      "retry_entrypoint":"the sending organization's emission of a new frame",
      "owning_existing_goal":refusal.get("owning_existing_goal") or HB_EPOCH_OWNING_EXISTING_GOAL,
      "next_attempt":"none for this frame; later cycles proceed past it",
      "derived_from_clock":False,
      "consequence_committed":False,
      "authority_effect":"NONE_CARRIER_ONLY"
    }
    return _write_once_marker(seen_dir/(hashlib.sha256(frame_name.encode()).hexdigest()+".json"),marker)

def mark_federation_frame_seen(repo_root:Path, frame_path:str, frame:dict[str,Any], result:dict[str,Any])->Path:
    seen_dir=repo_root/"resident-runtime/federation/seen.d"
    seen_dir.mkdir(parents=True,exist_ok=True)
    frame_name=Path(frame_path).name
    marker={
      "schema_version":"stegverse.federation-frame-consumption.v1",
      "frame_name":frame_name,
      "frame_sha256":frame.get("frame_sha256"),
      "packet_id":frame.get("packet_id"),
      "destination_org":frame.get("destination_org"),
      "status":result.get("status"),
      "authority_effect":"NONE_CARRIER_ONLY"
    }
    return _write_once_marker(seen_dir/(hashlib.sha256(frame_name.encode()).hexdigest()+".json"),marker)
