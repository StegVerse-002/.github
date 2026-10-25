#!/usr/bin/env python3
"""Supply this organization ledger's epoch from a committed packet. Not an InTr hop.

The main-merge transfer, the path transfer and the destination ingress take
their epoch from the ledger head (resident-runtime/merge_transfer.py head_epoch:
hb_reference.epoch, an int >= 32 with derived_from_clock exactly false). A
ledger whose head carries no supplied epoch refuses them all
(HB_EPOCH_SOURCE_UNOBSERVED). This module is the carrier for that one value.

``append`` reads .stegverse/organization-ledger/epoch-packet.json. When the
head already carries a supplied epoch it writes nothing (NOT_REQUIRED). When it
does not, it appends one repository receipt and one organization receipt
through the existing two-level append (intr_destination_ingress._append over
emit.py / aggregate_repo_transition.py), operation
ORGANIZATION_LEDGER_SUPPLIED_EPOCH, at the packet's hb_epoch. No clock is read.

It is an organization ledger transition, not an InTr hop: it names no
intr-destination address, no peer and no communication, and nothing crosses an
organization boundary (Rigel: no InTr hop exists inside an organization; the
intr-destination self-closure is not used here).

SKAP Vault inside KV is the only PII and credential store for every user, the
ecosystem's own included; the ecosystem holds none (HST citation pending P1
#163). Nothing here reads, mints or stores a credential.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / ".stegverse/organization-ledger/epoch-packet.json"
SCHEMA = "stegverse.organization-ledger-supplied-epoch-packet/v1"
OPERATION = "ORGANIZATION_LEDGER_SUPPLIED_EPOCH"
PROFILE_ID = "organization-ledger"
GOAL = "StegVerse-org/.github#162"
ENTRYPOINT = ".github/workflows/organization-ledger-writer.yml (push to main touching .stegverse/organization-ledger/epoch-packet.json)"
SIX = ("failure_code", "failed_predicate", "required_evidence_or_repair", "retry_entrypoint",
       "owning_existing_goal", "next_attempt")


def _load(name: str, relative: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def mt() -> Any:
    return _load("merge_transfer", "resident-runtime/merge_transfer.py")


def refusal(code: str, predicate: str, repair: str, next_attempt: str, **extra: Any) -> dict[str, Any]:
    return {"disposition": "FAIL_CLOSED", "failure_code": code, "failed_predicate": predicate,
            "required_evidence_or_repair": repair, "retry_entrypoint": ENTRYPOINT,
            "owning_existing_goal": GOAL, "next_attempt": next_attempt,
            "consequence_committed": False, **extra}


def load_packet(path: Path = PACKET) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        packet = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        return None, refusal("EPOCH_PACKET_UNREADABLE", "EPOCH_PACKET_IS_COMMITTED_JSON",
                             "commit .stegverse/organization-ledger/epoch-packet.json", "commit the packet; nothing was appended",
                             detail=type(exc).__name__ + ": " + str(exc))
    epoch = packet.get("hb_epoch") if isinstance(packet, Mapping) else None
    ok = (isinstance(packet, Mapping) and packet.get("schema") == SCHEMA
          and isinstance(packet.get("packet_id"), str) and packet["packet_id"]
          and type(epoch) is int and epoch >= 32
          and isinstance(packet.get("epoch_source"), Mapping))
    if not ok:
        return None, refusal("EPOCH_PACKET_INVALID", "EPOCH_PACKET_CARRIES_A_SUPPLIED_EPOCH_AND_ITS_SOURCE",
                             "schema " + SCHEMA + ", a packet_id, hb_epoch an int >= 32 and an epoch_source",
                             "commit a corrected packet; nothing was appended")
    return dict(packet), None


def evidence(packet: Mapping[str, Any]) -> dict[str, Any]:
    ingress = mt().ingress
    return {"schema": "stegverse.organization-ledger-supplied-epoch/v1", "disposition": "ALLOW",
            "packet_id": packet["packet_id"], "communication_id": None,
            "payload_sha256": ingress.sha(dict(packet)), "hb_epoch": packet["hb_epoch"],
            "epoch_source": dict(packet["epoch_source"]), "intr_hop": False}


def append(path: Path = PACKET) -> dict[str, Any]:
    packet, failed = load_packet(path)
    if failed is not None:
        return failed
    m = mt()
    epoch, unobserved = m.head_epoch(m.org_store())
    if unobserved is None:
        return {"disposition": "NOT_REQUIRED", "head_epoch": epoch, "packet_id": packet["packet_id"],
                "note": "the ledger head already carries a supplied epoch; nothing was appended"}
    try:
        appended, replayed = m.ingress._append(
            OPERATION, packet["packet_id"], evidence(packet), packet["hb_epoch"],
            operation=OPERATION, profile_id=PROFILE_ID,
            boundary_extra={"packet_id": packet["packet_id"], "hb_epoch_source": dict(packet["epoch_source"])})
    except (ValueError, SystemExit) as exc:
        return refusal("EPOCH_APPEND_REFUSED", "LEDGER_WRITER_ADMITS_THE_EPOCH_APPEND",
                       "the ledger writer refused the append; see detail", "repair and push again; nothing was published",
                       detail=str(exc))
    org = appended["organization_receipt"]
    return {"disposition": "ALLOW", "packet_id": packet["packet_id"], "hb_epoch": packet["hb_epoch"],
            "replayed": replayed, "organization_receipt_sha256": org["receipt_sha256"],
            "repository_receipt_sha256": appended["repository_receipt"]["receipt_sha256"]}


def verify() -> dict[str, Any]:
    """The head carries a supplied epoch (read from the ledger the environment names)."""
    m = mt()
    epoch, unobserved = m.head_epoch(m.org_store())
    if unobserved is not None:
        return {**unobserved, "retry_entrypoint": ENTRYPOINT, "owning_existing_goal": GOAL}
    return {"disposition": "ALLOW", "head_epoch": epoch}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("append", "verify"))
    parser.add_argument("--packet", default=str(PACKET))
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    result = append(Path(args.packet)) if args.command == "append" else verify()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0 if result["disposition"] in ("ALLOW", "NOT_REQUIRED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
