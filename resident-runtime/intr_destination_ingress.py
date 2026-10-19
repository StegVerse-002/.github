#!/usr/bin/env python3
"""``ORGANIZATION_INTR_DESTINATION_INGRESS`` -- acknowledge a purpose-neutral diagnostic.

``intr-destination`` is the capability every organization can advertise so a
peer can address it without a purpose-specific route. Governance stays a
purpose route where an organization has one. This operation is the mesh
primitive underneath purpose routes: a diagnostic crossing arrives, both
ledger levels record the disposition, and the disposition is transition
evidence only. Authority and time stay constraint variables. StegVerse-002 has no
governance or remediation destination binding, and this operation does not
add one.

The payload is an ``ecosystem.communication``. That is a request class the
transport profile answers, and it carries the ``communication_id`` a closure
correlates on, so an outbound diagnostic can be emitted and closed. The body
schema is ``stegverse.org-intr-destination-diagnostic/v1``. A body that is not
that schema is a refusal, recorded, not an acknowledgement.

``diagnostic_self_closure`` emits that diagnostic to the address this
organization serves, consumes it here, and closes it. The repository and
organization receipts, including ``communication_id``, are appended wherever
emission is pointed: by default the published organization ledger ref.

The profile name ``InTr:Destination`` is local to this binding. The pinned SDK
baseline does not declare the profile, and the canonical StegOS connector
registry was not readable from the change that added it, so this repository
does not claim StegOS already named it.

Authority and time are constraint variables. The address does not select a
processor, and this operation does not re-decide either. The disposition is
transition evidence only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]

OPERATION_ID = "ORGANIZATION_INTR_DESTINATION_INGRESS"
REFUSED_CLASS = "ORGANIZATION_INTR_DESTINATION_INGRESS_REFUSED"
OWNER_REPOSITORY = "StegVerse-002/.github"
PROFILE_ID = "intr-destination"
PROFILE_NAME = "InTr:Destination"
OPERATION = "DIAGNOSTIC_CROSSING"
PAYLOAD_SCHEMA = "stegverse.org-intr-destination-diagnostic/v1"
RESULT_SCHEMA = "stegverse.org-intr-destination-result/v1"
COMMUNICATION_CLASS = "ecosystem.communication"
ALLOW = "ALLOW"
DENY = "DENY"
FAIL_CLOSED = "FAIL_CLOSED"
ACK_EFFECT = "NONE_DIAGNOSTIC_ACK_ONLY"
REFUSAL_EFFECT = "NONE_REFUSAL_ONLY"
CONSTRAINT = "CONSTRAINT_VARIABLE"
DISPOSITION_ROLE = "TRANSITION_EVIDENCE_ONLY"
CONSTRAINT_FIELDS = {
    "routing_authority_constraint": CONSTRAINT,
    "admission_authority_constraint": CONSTRAINT,
    "execution_authority_constraint": CONSTRAINT,
    "time_constraint": CONSTRAINT,
    "disposition_role": DISPOSITION_ROLE,
}


def _module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repository_ledger = _module("repo_transition_emit", ".stegverse/transition-ledger/emit.py")
organization_ledger = _module("aggregate_repo_transition",
                              "resident-runtime/aggregate_repo_transition.py")
kernel = repository_ledger.kernel


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canon(value)).hexdigest()


def payload_sha(payload: Any) -> str:
    if isinstance(payload, Mapping):
        return sha(dict(payload))
    return sha(payload)


def shape_refusal(payload: Any) -> tuple[str, str] | None:
    """Why this payload is not a diagnostic this operation acknowledges."""
    if not isinstance(payload, Mapping):
        return ("SUBMISSION_IS_AN_ECOSYSTEM_COMMUNICATION", "payload is not an object")
    if payload.get("message_class") != COMMUNICATION_CLASS:
        return ("SUBMISSION_DECLARES_A_RESPONDED_REQUEST_CLASS",
                str(payload.get("message_class")))
    identifier = payload.get("communication_id")
    if not isinstance(identifier, str) or not identifier.strip():
        return ("SUBMISSION_CARRIES_THE_COMMUNICATION_ID_CLOSURE_CORRELATES_ON",
                repr(identifier))
    body = payload.get("body")
    observed = body.get("schema") if isinstance(body, Mapping) else body
    if not isinstance(body, Mapping) or observed != PAYLOAD_SCHEMA:
        return ("SUBMISSION_BODY_DECLARES_THE_BOUND_PAYLOAD_SCHEMA", str(observed))
    return None


def _evidence(payload: Any, packet_id: str, disposition: str, *,
              failed_predicate: str | None = None, detail: str | None = None) -> dict[str, Any]:
    communication_id = payload.get("communication_id") if isinstance(payload, Mapping) else None
    effect = ACK_EFFECT if disposition == ALLOW else REFUSAL_EFFECT
    record: dict[str, Any] = {
        "profile_id": PROFILE_ID,
        "profile_name": PROFILE_NAME,
        "operation": OPERATION,
        "receiving_operation": OPERATION_ID,
        "owner_repository": OWNER_REPOSITORY,
        "packet_id": packet_id,
        "communication_id": communication_id if isinstance(communication_id, str) else None,
        "payload_sha256": payload_sha(payload),
        "payload_schema": PAYLOAD_SCHEMA,
        "disposition": disposition,
        "authority_effect": effect,
        **CONSTRAINT_FIELDS,
        "selects_processing": False,
        "purpose_specific_route": False,
        "standing_rechecked_here": False,
    }
    if failed_predicate is not None:
        record["failed_predicate"] = failed_predicate
        record["detail"] = detail
    return record


class PacketIdCollision(ValueError):
    """A packet id already bound to a different diagnostic: refused six-field, nothing written."""

    def __init__(self, packet_id: str, evidence: Mapping[str, Any]) -> None:
        self.refusal = {
            "disposition": FAIL_CLOSED,
            "failure_code": "PACKET_ID_BINDS_ANOTHER_DIAGNOSTIC",
            "failed_predicate": "ONE_PACKET_ID_BINDS_ONE_DIAGNOSTIC",
            "detail": "packet " + str(packet_id) + " is already recorded with another diagnostic; payload "
                      + str(evidence.get("payload_sha256")) + " is not that one",
            "required_evidence_or_repair": "the sender emits this diagnostic under a new packet id",
            "retry_entrypoint": "the sender's hop",
            "owning_existing_goal": "INTERLOCK-INTR-RUNTIME-INDEPENDENT-PROTOCOL-001",
            "next_attempt": "none for this packet id; the recorded transition stands",
            "derived_from_clock": False,
            "consequence_committed": False,
        }
        super().__init__(self.refusal["failure_code"] + ": " + self.refusal["detail"])


def _result(evidence: Mapping[str, Any], appended: Mapping[str, Any] | None, *,
            replayed: bool, received: bool) -> dict[str, Any]:
    disposition = evidence["disposition"]
    acknowledged = disposition == ALLOW and received
    result = {
        "schema": RESULT_SCHEMA,
        "organization": organization_ledger.C["organization"],
        "receiving_operation": OPERATION_ID,
        "owner_repository": OWNER_REPOSITORY,
        "profile_id": PROFILE_ID,
        "profile_name": PROFILE_NAME,
        "operation": OPERATION,
        "disposition": disposition,
        "received": received,
        "communication_acknowledged": acknowledged,
        "communication_id": evidence.get("communication_id"),
        "payload_schema": PAYLOAD_SCHEMA,
        "payload_sha256": evidence["payload_sha256"],
        "transition_replayed": replayed,
        "standing_rechecked_here": False,
        "selects_processing": False,
        "purpose_specific_route": False,
        **CONSTRAINT_FIELDS,
        "authority_effect": evidence["authority_effect"],
    }
    if evidence.get("failed_predicate") is not None:
        result["failed_predicate"] = evidence["failed_predicate"]
        result["detail"] = evidence.get("detail")
    if appended is None:
        result["repository_receipt_observed"] = False
        result["organization_receipt_observed"] = False
        result["refusal_recorded"] = False
        return result
    repository_receipt = appended["repository_receipt"]
    organization_receipt = appended["organization_receipt"]
    result.update({
        "repository_receipt_observed": True,
        "organization_receipt_observed": True,
        "repository_receipt_sha256": repository_receipt["receipt_sha256"],
        "organization_receipt_sha256": organization_receipt["receipt_sha256"],
        "organization_receipt_preserves_repository_receipt":
            organization_receipt["repo_receipt_sha256"] == repository_receipt["receipt_sha256"],
        "refusal_recorded": disposition != ALLOW,
    })
    return result


def _append(transition_class: str, packet_id: str, evidence: Mapping[str, Any],
            hb_epoch: int | None) -> tuple[dict[str, Any], bool]:
    """Append at both levels. A replay of the same packet returns the recorded pair."""
    predecessor = evidence["payload_sha256"]
    successor = sha({"disposition": evidence["disposition"], "packet_id": packet_id,
                     "communication_id": evidence.get("communication_id"),
                     "payload_sha256": evidence["payload_sha256"]})
    transition_id = transition_class + ":" + packet_id
    prior = repository_ledger.recorded(transition_id, transition_class)
    repository_receipt = repository_ledger.append(
        transition_id, transition_class, predecessor, successor, dict(evidence),
        "NONE", hb_epoch=hb_epoch,
        idempotent_on=("communication_id", "payload_sha256", "disposition"))
    # The organization writer takes the epoch supplied here, never one read back
    # from the repository receipt: a replayed receipt's epoch was not supplied to
    # this call. A replay still returns the recorded organization receipt.
    organization_receipt = organization_ledger.append(
        repository_receipt, "REPO_STATE_PROPAGATION", predecessor, successor,
        {"operation": OPERATION_ID, "profile_id": PROFILE_ID,
         "disposition": evidence["disposition"],
         "communication_id": evidence.get("communication_id")},
        "NONE", hb_epoch=hb_epoch, idempotent=True)
    return ({"repository_receipt": repository_receipt,
             "organization_receipt": organization_receipt}, prior is not None)


def _recorded(disposition: str, payload: Any, packet_id: str, hb_epoch: int | None, *,
              failed_predicate: str | None = None, detail: str | None = None) -> dict[str, Any]:
    evidence = _evidence(payload, packet_id, disposition,
                         failed_predicate=failed_predicate, detail=detail)
    transition_class = OPERATION_ID if disposition == ALLOW else REFUSED_CLASS
    try:
        appended, replayed = _append(transition_class, packet_id, evidence, hb_epoch)
    except ValueError as exc:
        if str(exc) != "ledger_receipt_collision":
            raise
        # The packet id already bound a different diagnostic. The recorded
        # transition stands; this attempt is refused before anything is written
        # or answered. A store-side collision is not this: the store raises it
        # as its own write fault (ledger_store.LedgerWriteFailed).
        raise PacketIdCollision(packet_id, evidence) from None
    return _result(evidence, appended, replayed=replayed, received=disposition == ALLOW)


def receive(payload: Any, *, registry: Mapping[str, Any], standing: Mapping[str, Any] | None = None,
            packet_id: str = "organization-intr-destination",
            hb_epoch: int | None = None, mesh_root: Path | None = None) -> dict[str, Any]:
    """Acknowledge one diagnostic, or record the refusal.

    ``standing`` and ``mesh_root`` are accepted because the capability resolver
    passes them to every receiving operation. This kernel's packet does not
    carry standing, and a diagnostic does not leave, so neither is used.
    """
    del standing, mesh_root
    hb_epoch = kernel.supplied_epoch(_supplied_epoch(hb_epoch),
                                     retry_entrypoint=RECEIVE_EPOCH_RETRY_ENTRYPOINT)
    if not isinstance(registry, Mapping):
        return _recorded(DENY, payload, packet_id, hb_epoch,
                         failed_predicate="CAPABILITY_MAP_IS_A_MAPPING",
                         detail="registry is not an object")
    refusal = shape_refusal(payload)
    if refusal is not None:
        return _recorded(DENY, payload, packet_id, hb_epoch,
                         failed_predicate=refusal[0], detail=refusal[1])
    return _recorded(ALLOW, payload, packet_id, hb_epoch)


SELF_CLOSURE_SCHEMA = "stegverse.org-intr-destination-self-closure/v1"

#: The epoch a caller supplied for a crossing, carried to the receiving
#: operation when the kernel's dispatch does not pass one. Unset is no epoch;
#: it is never filled from a clock.
SUPPLIED_EPOCH_ENV = "STEGVERSE_HB_EPOCH"


RECEIVE_EPOCH_RETRY_ENTRYPOINT = ("resident-runtime/intr_destination_ingress.py::receive "
                                  "(hb_epoch=, --hb-epoch, or " + SUPPLIED_EPOCH_ENV + ")")
SELF_CLOSURE_EPOCH_RETRY_ENTRYPOINT = ("resident-runtime/intr_destination_ingress.py::"
                                       "diagnostic_self_closure (hb_epoch=, or --hb-epoch)")


def _supplied_epoch(hb_epoch: Any) -> Any:
    """The caller's epoch, else the environment's raw text. The shared rule judges it.

    Unset is no epoch. Set but empty is an epoch that was supplied and is invalid.
    """
    if hb_epoch is not None:
        return hb_epoch
    return os.environ.get(SUPPLIED_EPOCH_ENV)


def diagnostic_self_closure(communication_id: str, *, mesh_root: Path,
                            hb_epoch: int | None = None) -> dict[str, Any]:
    """Close one diagnostic against this organization's own intr-destination.

    The far side is this boundary: the diagnostic is emitted to the address
    this organization serves, consumed here, answered with this kernel's
    receipt chain, and closed. Repository and organization receipts at each
    of those steps carry ``communication_id``. The mesh is only the queue for
    this run. Which ledger those receipts land on is the ledger location
    already selected for emission.

    Authority and time stay constraint variables. The disposition is
    transition evidence only. Resolution still does not prove a separate
    peer installed the capability.
    """
    if not isinstance(communication_id, str) or not communication_id.strip():
        return {
            "schema": SELF_CLOSURE_SCHEMA,
            "disposition": DENY,
            "closed": False,
            "communication_id": communication_id if isinstance(communication_id, str) else None,
            "failed_predicate": "PAYLOAD_CARRIES_THE_COMMUNICATION_ID_CLOSURE_CORRELATES_ON",
            "detail": repr(communication_id),
            "receipts_appended": False,
            **CONSTRAINT_FIELDS,
            "authority_effect": REFUSAL_EFFECT,
        }
    egress = _module("egress_self_closure", "resident-runtime/organization_egress_boundary.py")
    kernel_mod = _module("kernel_self_closure", "org-kernel/kernel.py")
    hb_epoch = kernel_mod.supplied_epoch(hb_epoch, retry_entrypoint=SELF_CLOSURE_EPOCH_RETRY_ENTRYPOINT)
    origin = kernel_mod.load_registry(ROOT)["organization"]
    payload = {
        "message_class": COMMUNICATION_CLASS,
        "communication_id": communication_id,
        "subject": "purpose-neutral mesh diagnostic",
        "body": {"schema": PAYLOAD_SCHEMA, "probe": "diagnostic-self-closure"},
    }
    standing = {
        "mode": "ESTABLISH_GENESIS",
        "node_ref": "intr-destination-self-closure",
        "predecessor": None,
    }
    emitted = egress.emit(
        origin, payload, standing=standing, capability=PROFILE_ID, root=ROOT,
        mesh_root=mesh_root, hb_epoch=hb_epoch)
    result = {
        "schema": SELF_CLOSURE_SCHEMA,
        "organization": origin,
        "receiving_operation": OPERATION_ID,
        "owner_repository": OWNER_REPOSITORY,
        "profile_id": PROFILE_ID,
        "communication_id": communication_id,
        "disposition": DENY,
        "closed": False,
        "emission_disposition": emitted.get("disposition"),
        "emission_repository_receipt_sha256": emitted.get("emission_repository_receipt_sha256"),
        "emission_organization_receipt_sha256": emitted.get("emission_organization_receipt_sha256"),
        "packet_id": emitted.get("packet_id"),
        "destination_service": emitted.get("destination_service"),
        "peer_serves_this_capability_is_proven_here": False,
        "selects_processing": False,
        "purpose_specific_route": False,
        **CONSTRAINT_FIELDS,
        "authority_effect": "NONE_CLOSURE_RECORD_ONLY",
    }
    if emitted.get("disposition") != ALLOW or not emitted.get("emitted"):
        result["failed_predicate"] = emitted.get("failed_predicate")
        result["detail"] = emitted.get("detail")
        return result
    # The kernel's dispatch carries the supplied epoch to the receiving operation.
    consumed_frames = kernel_mod.consume_addressed_frames(ROOT, mesh_root=mesh_root,
                                                          hb_epoch=hb_epoch)
    if len(consumed_frames) != 1 or consumed_frames[0]["result"].get("status") != "CONSUMED":
        result["failed_predicate"] = "SELF_DIAGNOSTIC_IS_CONSUMED_AT_THIS_ADDRESS"
        result["detail"] = "the emitted frame was not consumed here"
        return result
    consumed = consumed_frames[0]["result"]
    execution = consumed["execution_result"]
    operation = (execution.get("application_result") or {}).get("receiving_operation_result") or {}
    result["ingress_disposition"] = operation.get("disposition")
    result["ingress_repository_receipt_sha256"] = operation.get("repository_receipt_sha256")
    result["ingress_organization_receipt_sha256"] = operation.get("organization_receipt_sha256")
    if operation.get("disposition") != ALLOW:
        result["failed_predicate"] = operation.get("failed_predicate")
        result["detail"] = operation.get("detail")
        return result
    response = kernel_mod.build_control_response(consumed["packet"], execution)
    kernel_mod.publish_packet(response, root=mesh_root, now_ns=kernel_mod.epoch_now_ns(hb_epoch))
    closed = egress.close(
        origin, emitted["packet_id"], communication_id, root=ROOT,
        mesh_root=mesh_root, hb_epoch=hb_epoch)
    result.update({
        "disposition": closed.get("disposition"),
        "closed": bool(closed.get("closed")),
        "closure_findings": closed.get("closure_findings"),
        "closure_repository_receipt_sha256": closed.get("closure_repository_receipt_sha256"),
        "closure_organization_receipt_sha256": closed.get("closure_organization_receipt_sha256"),
        "repository_receipt_sha256": closed.get("closure_repository_receipt_sha256"),
        "organization_receipt_sha256": closed.get("closure_organization_receipt_sha256"),
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-closure", action="store_true",
                        help="emit, receive, and close one diagnostic against this organization")
    parser.add_argument("--communication-id", default=None)
    parser.add_argument("--mesh-root", type=Path, default=None)
    parser.add_argument("--payload", type=Path, default=None)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--packet-id", default="organization-intr-destination")
    # The raw text goes to the shared epoch rule: argparse's int() would take
    # "+33", " 33" or fullwidth digits as 33.
    parser.add_argument("--hb-epoch", default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    try:
        if args.self_closure:
            if args.mesh_root is None or args.communication_id is None:
                raise SystemExit("self-closure requires --communication-id and --mesh-root")
            result = diagnostic_self_closure(
                args.communication_id, mesh_root=args.mesh_root, hb_epoch=args.hb_epoch)
        else:
            if args.payload is None or args.registry is None:
                raise SystemExit("receive requires --payload and --registry")
            result = receive(
                json.loads(args.payload.read_text(encoding="utf-8")),
                registry=json.loads(args.registry.read_text(encoding="utf-8")),
                packet_id=args.packet_id, hb_epoch=args.hb_epoch)
    except ValueError as exc:
        # Each loaded kernel has its own SuppliedEpochRefused class.
        if not isinstance(getattr(exc, "refusal", None), dict):
            raise
        print(json.dumps(exc.refusal, sort_keys=True))
        return 1
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("disposition") == ALLOW else 1


if __name__ == "__main__":
    sys.exit(main())
