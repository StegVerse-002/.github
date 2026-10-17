#!/usr/bin/env python3
"""Read the organization ledger back and verify it, independently of the writer.

The evidence of an append is a readback from the ledger itself. This opens the
ledger at the location it is given (for the published ref, a fresh fetch of
`refs/stegverse/organization-ledger`). It walks the chain from HEAD and checks,
for every receipt:

- its `receipt_sha256` is the digest of its own body;
- `previous_receipt_sha256` names the receipt before it, ending at genesis
  (null), so the chain has no gaps and no forks;
- the source receipt it consumed is retained under `source-receipts/` and
  verifies against its own body.

Given a diagnostic self-closure (`--closure-result`), it also checks that each
named repository and organization receipt is in its chain, that the
organization receipt consumed that repository receipt, and that both carry the
closure's `communication_id`.

`--repository-namespace` reads the repository chain kept in that subtree of the
same ref. Repository replay walks repository receipts only.

Authority and time are constraint variables. A disposition is transition
evidence only. Stdlib and `git` only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger_store import HEAD_KEY, open_store, parse_locator, receipt_key, source_key  # noqa: E402

RETRY = "resident-runtime/organization_ledger_readback.py::main"
GOAL = "ORGANIZATION-LEDGER-PUBLISHED-REF"

# Repository and organization receipt names a self-closure result carries.
CLOSURE_PAIRS = (
    ("emission_repository_receipt_sha256", "emission_organization_receipt_sha256"),
    ("ingress_repository_receipt_sha256", "ingress_organization_receipt_sha256"),
    ("closure_repository_receipt_sha256", "closure_organization_receipt_sha256"),
)


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(value):
    return "sha256:" + hashlib.sha256(canon(value)).hexdigest()


class ReadbackRefused(Exception):
    def __init__(self, failed_predicate, detail):
        super().__init__(failed_predicate + ": " + detail)
        self.failed_predicate = failed_predicate
        self.detail = detail


def self_verifies(document):
    if not isinstance(document, dict):
        return False
    body = {key: value for key, value in document.items() if key != "receipt_sha256"}
    return document.get("receipt_sha256") == sha(body)


def _repository_emitter():
    """The repository ledger's own chain walker."""
    import importlib.util
    emit = Path(__file__).resolve().parents[1] / ".stegverse/transition-ledger/emit.py"
    spec = importlib.util.spec_from_file_location("repository_ledger_readback_emit", emit)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def readback(location):
    """Verify the organization chain at `location`."""
    store = open_store(parse_locator(location))
    head = store.get(HEAD_KEY)
    if head is None:
        raise ReadbackRefused("ORGANIZATION_LEDGER_HEAD_PRESENT", "no HEAD at " + str(location))
    chain, cursor, seen = [], head.get("receipt_sha256"), set()
    while cursor is not None:
        if cursor in seen:
            raise ReadbackRefused("ORGANIZATION_LEDGER_CHAIN_IS_ACYCLIC", str(cursor))
        seen.add(cursor)
        receipt = store.get(receipt_key(cursor))
        if receipt is None:
            raise ReadbackRefused("ORGANIZATION_LEDGER_CHAIN_IS_COMPLETE", "missing " + str(cursor))
        if receipt.get("receipt_sha256") != cursor or not self_verifies(receipt):
            raise ReadbackRefused("ORGANIZATION_RECEIPT_VERIFIES_AGAINST_ITS_BODY", str(cursor))
        source_digest = receipt.get("source_transition_sha256")
        source = store.get(source_key(source_digest)) if source_digest else None
        if source is None or source.get("receipt_sha256") != source_digest or not self_verifies(source):
            raise ReadbackRefused("SOURCE_RECEIPT_RETAINED_AND_VERIFIES", str(source_digest))
        chain.append(receipt)
        cursor = receipt.get("previous_receipt_sha256")
    chain.reverse()
    return {
        "schema": "stegverse.organization-ledger-readback/v1",
        "location": str(location),
        "disposition": "ALLOW",
        "head_receipt_sha256": head["receipt_sha256"],
        "chain_length": len(chain),
        "genesis_receipt_sha256": chain[0]["receipt_sha256"],
        "chain": [{"receipt_sha256": receipt["receipt_sha256"],
                   "previous_receipt_sha256": receipt.get("previous_receipt_sha256"),
                   "source_transition_id": receipt.get("source_transition_id"),
                   "communication_id": (receipt.get("boundary_evidence") or {}).get("communication_id"),
                   "predecessor_org_state_sha256": receipt.get("predecessor_org_state_sha256"),
                   "successor_org_state_sha256": receipt.get("successor_org_state_sha256")}
                  for receipt in chain],
        "receipts": chain,
        "every_receipt_verifies_against_its_body": True,
        "every_source_receipt_retained_and_verifies": True,
        "authority_effect": "NONE_READBACK_ONLY",
    }


def repository_readback(location, namespace):
    """Read the repository chain kept in `namespace` of the same ref and verify it."""
    emitter = _repository_emitter()
    locator = parse_locator(location)
    repository_location = str(locator) + ":" + namespace
    store = open_store(repository_location)
    organization_store = open_store(locator)
    head = store.get(HEAD_KEY)
    if head is None:
        raise ReadbackRefused("REPOSITORY_LEDGER_HEAD_PRESENT", "no HEAD at " + repository_location)
    try:
        chain = list(emitter.chain(store, head))
    except emitter.RepoLedgerChainBreak as exc:
        raise ReadbackRefused("REPOSITORY_CHAIN_VERIFIES", str(exc)) from None
    chain.reverse()
    for receipt in chain:
        retained = organization_store.get(source_key(receipt["receipt_sha256"]))
        if retained != receipt:
            raise ReadbackRefused("REPOSITORY_RECEIPT_RETAINED_IN_ORGANIZATION_LEDGER",
                                  receipt["receipt_sha256"])
    return {
        "location": repository_location,
        "namespace": namespace,
        "head_receipt_sha256": head["receipt_sha256"],
        "chain_length": len(chain),
        "genesis_receipt_sha256": chain[0]["receipt_sha256"],
        "chain": [{"receipt_sha256": receipt["receipt_sha256"],
                   "previous_receipt_sha256": receipt.get("previous_receipt_sha256"),
                   "transition_id": receipt.get("transition_id"),
                   "transition_class": receipt.get("transition_class"),
                   "communication_id": (receipt.get("evidence") or {}).get("communication_id")}
                  for receipt in chain],
        "receipts": chain,
        "every_receipt_verifies_against_its_body": True,
        "every_receipt_retained_in_organization_ledger": True,
        "replay_read_organization_receipts": False,
    }


def _communication_id(receipt, field):
    container = receipt.get(field)
    if not isinstance(container, dict):
        return None
    return container.get("communication_id")


def bind_closure(organization_result, repository_result, closure):
    """Each named pair is in its chain, linked, and carries `communication_id`."""
    communication_id = closure.get("communication_id")
    if not isinstance(communication_id, str) or not communication_id.strip():
        raise ReadbackRefused("CLOSURE_CARRIES_A_COMMUNICATION_ID", repr(communication_id))
    organization_by_digest = {receipt["receipt_sha256"]: receipt
                              for receipt in organization_result["receipts"]}
    repository_by_digest = {receipt["receipt_sha256"]: receipt
                            for receipt in repository_result["receipts"]}
    bound = []
    for repository_field, organization_field in CLOSURE_PAIRS:
        repository_digest = closure.get(repository_field)
        organization_digest = closure.get(organization_field)
        repository_receipt = repository_by_digest.get(repository_digest)
        organization_receipt = organization_by_digest.get(organization_digest)
        if repository_receipt is None:
            raise ReadbackRefused("CLOSURE_REPOSITORY_RECEIPT_IS_IN_THE_REPOSITORY_LEDGER",
                                  str(repository_field))
        if organization_receipt is None:
            raise ReadbackRefused("CLOSURE_ORGANIZATION_RECEIPT_IS_IN_THE_ORGANIZATION_LEDGER",
                                  str(organization_field))
        if organization_receipt.get("source_transition_sha256") != repository_digest:
            raise ReadbackRefused("ORGANIZATION_RECEIPT_CONSUMES_THE_REPOSITORY_RECEIPT",
                                  str(organization_field))
        if _communication_id(repository_receipt, "evidence") != communication_id:
            raise ReadbackRefused("REPOSITORY_RECEIPT_CARRIES_THE_COMMUNICATION_ID",
                                  str(repository_field))
        if _communication_id(organization_receipt, "boundary_evidence") != communication_id:
            raise ReadbackRefused("ORGANIZATION_RECEIPT_CARRIES_THE_COMMUNICATION_ID",
                                  str(organization_field))
        bound.append({
            "repository_receipt_sha256": repository_digest,
            "organization_receipt_sha256": organization_digest,
            "communication_id": communication_id,
        })
    return {
        "communication_id": communication_id,
        "pairs_bound": len(bound),
        "pairs": bound,
        "closure_receipts_carry_communication_id": True,
    }


def present(result):
    """The readback a caller prints: chain summaries, not the receipt bodies."""
    presented = dict(result)
    presented.pop("receipts", None)
    repository = presented.get("repository_ledger")
    if isinstance(repository, dict):
        repository = dict(repository)
        repository.pop("receipts", None)
        presented["repository_ledger"] = repository
    return presented


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--location", required=True, help="ledger locator, e.g. git+<repo>#<ref>")
    parser.add_argument("--repository-namespace", default=None,
                        help="also read back the repository chain kept in this subtree of the same ref")
    parser.add_argument("--closure-result", type=Path, default=None,
                        help="diagnostic self-closure result whose receipts must read back")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    try:
        result, code = readback(args.location), 0
        if args.repository_namespace:
            result["repository_ledger"] = repository_readback(args.location, args.repository_namespace)
        if args.closure_result:
            closure = json.loads(args.closure_result.read_text(encoding="utf-8"))
            if result.get("repository_ledger") is None:
                raise ReadbackRefused("REPOSITORY_LEDGER_NAMESPACE_SUPPLIED",
                                      "a closure readback names both chains")
            result["closure"] = bind_closure(result, result["repository_ledger"], closure)
    except (ReadbackRefused, ValueError, RuntimeError, FileNotFoundError) as exc:
        result, code = {
            "schema": "stegverse.organization-ledger-readback/v1",
            "location": args.location,
            "disposition": "FAIL_CLOSED",
            "failure_code": "ORGANIZATION_LEDGER_READBACK_FAILED",
            "failed_predicate": getattr(exc, "failed_predicate", "ORGANIZATION_LEDGER_READS_BACK"),
            "required_evidence_or_repair": getattr(exc, "detail", str(exc)),
            "retry_entrypoint": RETRY,
            "owning_existing_goal": GOAL,
            "next_attempt": "fetch the ledger ref again and rerun the readback; nothing is written by it",
            "authority_effect": "NONE_READBACK_ONLY",
        }, 1
    text = json.dumps(present(result), indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
