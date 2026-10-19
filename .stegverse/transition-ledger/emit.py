#!/usr/bin/env python3
"""Append repository transition receipts to the store the materializer names.

The default location is the repository subtree of this organization's published
ledger ref (`contract.json` `repository_ledger_location`), not a host state
directory. `STEGVERSE_REPO_LEDGER_ROOT` overrides that for a redirected run.
A plain path stays a POSIX root. `git+<repository>#<ref>[:<namespace>]` is a
git ref. Authority and time are constraint variables. A disposition is
transition evidence only.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = json.loads((ROOT / ".stegverse/transition-ledger/contract.json").read_text())
_spec = importlib.util.spec_from_file_location(
    "ledger_store", ROOT / "resident-runtime/ledger_store.py")
ledger_store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ledger_store)
_spec = importlib.util.spec_from_file_location("repo_ledger_kernel", ROOT / "org-kernel/kernel.py")
kernel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kernel)

CHAIN_BREAK = "REPO_LEDGER_CHAIN_BREAK"
EPOCH_RETRY_ENTRYPOINT = ".stegverse/transition-ledger/emit.py::append (hb_epoch=, or --hb-epoch)"
RepoLedgerEpochRefused = kernel.SuppliedEpochRefused
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(value):
    raw = value if isinstance(value, (bytes, bytearray)) else canon(value)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def published_locator():
    """The repository chain inside the published organization ledger ref."""
    location = C["repository_ledger_location"]
    return "git+" + str(ROOT) + "#" + location["ref"] + ":" + location["namespace"]


def lr():
    """The repository ledger location: the override, or the published ref."""
    override = os.getenv("STEGVERSE_REPO_LEDGER_ROOT")
    if override:
        return ledger_store.parse_locator(override)
    return ledger_store.parse_locator(published_locator())


class RepoLedgerChainBreak(ValueError):
    """A node reachable from HEAD is missing, malformed, or not the receipt its digest names."""

    failed_predicate = CHAIN_BREAK

    def __init__(self, receipt_sha256, detail):
        super().__init__(CHAIN_BREAK + ": " + detail + ": " + repr(receipt_sha256))
        self.receipt_sha256 = receipt_sha256
        self.detail = detail


def chain_break_refusal(exc):
    """The append attempt's disposition when the chain it would extend is broken."""
    return {
        "schema": "stegverse.repo-ledger-append-refusal/v1",
        "repository": C["repository"],
        "disposition": "FAIL_CLOSED",
        "failed_predicate": exc.failed_predicate,
        "detail": exc.detail,
        "receipt_sha256": exc.receipt_sha256,
        "failure_code": "REPO_LEDGER_CHAIN_BROKEN",
        "required_evidence_or_repair": (
            "restore the receipt addressed by receipt_sha256, byte-for-byte as recorded; "
            "a chain is never re-minted over a break"
        ),
        "retry_entrypoint": ".stegverse/transition-ledger/emit.py::append",
        "owning_existing_goal": "ORGANIZATION-LEDGER-PUBLISHED-REF",
        "next_attempt": "rerun the same append once the addressed receipt is restored; nothing was appended",
        "consequence_committed": False,
        "authority_effect": "NONE_REFUSAL_ONLY",
    }


def node(target, cursor):
    """The receipt `cursor` addresses, recomputed and proven to be that receipt."""
    if not isinstance(cursor, str) or not DIGEST.match(cursor):
        raise RepoLedgerChainBreak(cursor, "malformed_receipt_address")
    try:
        receipt = target.get(ledger_store.receipt_key(cursor))
    except ValueError:
        raise RepoLedgerChainBreak(cursor, "unreadable_receipt") from None
    if receipt is None:
        raise RepoLedgerChainBreak(cursor, "missing_receipt")
    if not isinstance(receipt, dict):
        raise RepoLedgerChainBreak(cursor, "malformed_receipt")
    if sha({key: value for key, value in receipt.items() if key != "receipt_sha256"}) != cursor:
        raise RepoLedgerChainBreak(cursor, "receipt_body_does_not_hash_to_its_address")
    if receipt.get("receipt_sha256") != cursor:
        raise RepoLedgerChainBreak(cursor, "stored_receipt_sha256_is_not_its_address")
    return receipt


def chain(target, head):
    """Every receipt reachable from `head`, newest first, each one verified."""
    if head is None:
        return
    cursor = head.get("receipt_sha256") if isinstance(head, dict) else None
    if cursor is None:
        raise RepoLedgerChainBreak(None, "malformed_head")
    seen = set()
    while cursor is not None:
        if cursor in seen:
            raise RepoLedgerChainBreak(cursor, "cycle")
        seen.add(cursor)
        receipt = node(target, cursor)
        yield receipt
        cursor = receipt.get("previous_receipt_sha256")


def recorded(transition_id, transition_class, store=None):
    """The receipt already bound to this transition, walking back from HEAD.

    The whole chain is verified even after a match, so an answer is never read
    off a chain that is broken further back.
    """
    target = store or ledger_store.open_store(lr())
    found = None
    for receipt in chain(target, target.get(ledger_store.HEAD_KEY)):
        if (found is None and receipt.get("transition_id") == transition_id
                and receipt.get("transition_class") == transition_class):
            found = receipt
    return found


def _heartbeat(hb_epoch):
    return {
        "epoch": hb_epoch,
        "progression_dependency": "OSCILLATOR_ONLY",
        "authority_effect": "NONE",
    }


def append(transition_id, transition_class, predecessor_state_sha256, successor_state_sha256,
           evidence=None, authority_effect="NONE", hb_epoch=None, idempotent_on=None, store=None):
    """Append one repository receipt. A replay of the same transition returns the recorded one.

    The epoch is the caller's. An absent or invalid one is refused six-field
    FAIL_CLOSED before the store opens; no clock stands in for it.
    """
    hb_epoch = kernel.supplied_epoch(hb_epoch, retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    evidence = dict(evidence or {})
    target = store or ledger_store.open_store(lr())
    target.initialize()
    observed = f"hb-epoch:{hb_epoch}"
    for _attempt in range(128):
        expected_head = target.get(ledger_store.HEAD_KEY)
        prior = recorded(transition_id, transition_class, store=target)
        if prior is not None:
            theirs = prior.get("evidence") if isinstance(prior.get("evidence"), dict) else {}
            keys = tuple(idempotent_on) if idempotent_on else tuple(evidence.keys())
            if all(theirs.get(key) == evidence.get(key) for key in keys):
                return prior
            raise ValueError("ledger_receipt_collision")
        previous = (expected_head or {}).get("receipt_sha256") if isinstance(expected_head, dict) else None
        body = {
            "schema": "stegverse.repo-transition-receipt/v1",
            "repository": C["repository"],
            "transition_id": transition_id,
            "transition_class": transition_class,
            "predecessor_state_sha256": predecessor_state_sha256,
            "successor_state_sha256": successor_state_sha256,
            "evidence": evidence,
            "authority_effect": authority_effect,
            "hb_reference": _heartbeat(hb_epoch),
            "observed_at": observed,
            "previous_receipt_sha256": previous,
        }
        digest = sha(body)
        record = {**body, "receipt_sha256": digest}
        key = ledger_store.receipt_key(digest)
        new_head = {
            "repository": C["repository"],
            "receipt_sha256": digest,
            "receipt_path": target.locator(key),
        }
        if target.append_transaction(key, record, expected_head, new_head):
            return record
    raise SystemExit("REPO_LEDGER_APPEND_CONTENTION_EXHAUSTED")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transition-id", required=True)
    parser.add_argument("--transition-class", required=True)
    parser.add_argument("--predecessor-state-sha256", required=True)
    parser.add_argument("--successor-state-sha256", required=True)
    parser.add_argument("--evidence-json", default="{}")
    parser.add_argument("--authority-effect", default="NONE")
    # The raw text goes to the shared epoch rule: argparse's int() would take
    # "+33", " 33" or fullwidth digits as 33.
    parser.add_argument("--hb-epoch", default=None)
    args = parser.parse_args()
    try:
        record = append(
            args.transition_id, args.transition_class, args.predecessor_state_sha256,
            args.successor_state_sha256, json.loads(args.evidence_json), args.authority_effect,
            hb_epoch=args.hb_epoch)
    except RepoLedgerChainBreak as exc:
        print(json.dumps(chain_break_refusal(exc), sort_keys=True))
        raise SystemExit(1)
    except RepoLedgerEpochRefused as exc:
        print(json.dumps(exc.refusal, sort_keys=True))
        raise SystemExit(1)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
