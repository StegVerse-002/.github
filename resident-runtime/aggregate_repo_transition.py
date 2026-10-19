#!/usr/bin/env python3
"""Append organization receipts onto the published organization ledger.

The default location is `org-contract.json` `organization_ledger_ref` in this
repository. `STEGVERSE_ORG_LEDGER_ROOT` overrides that for a redirected run.
A repository receipt is verified, retained under `source-receipts/`, and
linked by its own digest. The organization receipt records only the
organization-level state consequence.

Authority and time are constraint variables. A disposition is transition
evidence only.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger_store import HEAD_KEY, RECEIPT_PREFIX, SOURCE_PREFIX, open_store, parse_locator, receipt_key, source_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
C = json.loads((ROOT / ".stegverse/transition-ledger/org-contract.json").read_text())
_spec = importlib.util.spec_from_file_location("org_ledger_kernel", ROOT / "org-kernel/kernel.py")
kernel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kernel)

#: An append's epoch is supplied by its caller. An absent or invalid one is
#: refused six-field FAIL_CLOSED before the store opens; no clock is read.
EPOCH_RETRY_ENTRYPOINT = "resident-runtime/aggregate_repo_transition.py::append (hb_epoch=, or --hb-epoch)"
OrgLedgerEpochRefused = kernel.SuppliedEpochRefused


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(value):
    return "sha256:" + hashlib.sha256(canon(value)).hexdigest()


def published_locator():
    """The organization ledger on its published ref, in this checkout."""
    return "git+" + str(ROOT) + "#" + C["organization_ledger_ref"]


def ledger_root():
    """The organization ledger location: the override, or the published ref."""
    override = os.getenv("STEGVERSE_ORG_LEDGER_ROOT")
    if override:
        return parse_locator(override)
    return parse_locator(published_locator())


def load(path):
    return json.loads(Path(path).read_text())


def verify_repo(receipt):
    if not isinstance(receipt, dict):
        raise ValueError("source_receipt_required")
    if receipt.get("schema") != "stegverse.repo-transition-receipt/v1":
        raise ValueError("repo receipt schema mismatch")
    if not str(receipt.get("repository", "")).startswith(C["organization"] + "/"):
        raise ValueError("repo outside organization")
    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if claimed != sha(body):
        raise ValueError("repo receipt hash mismatch")
    return claimed


def _heartbeat(hb_epoch):
    return {
        "epoch": hb_epoch,
        "progression_dependency": "OSCILLATOR_ONLY",
        "authority_effect": "NONE",
    }


def _validate_existing_head(store):
    """Refuse to extend a chain whose reachable receipts do not verify."""
    head = store.get(HEAD_KEY)
    if head is None:
        if store.list_prefix(RECEIPT_PREFIX):
            raise ValueError("ORG_LEDGER_HEAD_MISSING_WITH_EXISTING_RECEIPTS")
        return None
    previous = head.get("receipt_sha256") if isinstance(head, dict) else None
    if not isinstance(previous, str) or not previous.startswith("sha256:"):
        raise ValueError("ORG_LEDGER_HEAD_INVALID")
    reachable = set()
    cursor = previous
    while cursor:
        if cursor in reachable:
            raise ValueError("ORG_LEDGER_PREDECESSOR_CYCLE")
        reachable.add(cursor)
        record = store.get(receipt_key(cursor))
        if not isinstance(record, dict):
            raise ValueError("ORG_LEDGER_PREDECESSOR_MISSING")
        body = dict(record)
        body.pop("receipt_sha256", None)
        if record.get("receipt_sha256") != cursor or sha(body) != cursor:
            raise ValueError("ORG_LEDGER_HEAD_RECEIPT_HASH_MISMATCH")
        cursor = record.get("previous_receipt_sha256")
    if store.list_prefix(RECEIPT_PREFIX) != {receipt_key(digest) for digest in reachable}:
        raise ValueError("ORG_LEDGER_UNPUBLISHED_OR_ORPHAN_RECEIPTS_RECOVERY_REQUIRED")
    sources = set()
    for digest in reachable:
        record = store.get(receipt_key(digest))
        source_digest = record.get("source_transition_sha256") if isinstance(record, dict) else None
        if isinstance(source_digest, str):
            sources.add(source_key(source_digest))
    if not store.list_prefix(SOURCE_PREFIX) <= sources:
        raise ValueError("ORG_LEDGER_ORPHAN_SOURCE_RECEIPTS_RECOVERY_REQUIRED")
    return previous


def _recorded(store, head, source_digest):
    """The organization receipt this chain already holds for a repository receipt."""
    cursor = (head or {}).get("receipt_sha256") if isinstance(head, dict) else None
    seen = set()
    while isinstance(cursor, str) and cursor and cursor not in seen:
        seen.add(cursor)
        receipt = store.get(receipt_key(cursor))
        if not isinstance(receipt, dict):
            return None
        if receipt.get("repo_receipt_sha256") == source_digest or receipt.get("source_transition_sha256") == source_digest:
            return receipt
        cursor = receipt.get("previous_receipt_sha256")
    return None


def append(source_receipt, org_transition_class, predecessor_state, successor_state,
           boundary_evidence=None, authority_effect="NONE", hb_epoch=None, idempotent=True, store=None):
    """Append the organization receipt for one repository receipt. A replay returns the recorded one."""
    hb_epoch = kernel.supplied_epoch(hb_epoch, retry_entrypoint=EPOCH_RETRY_ENTRYPOINT)
    claimed = verify_repo(source_receipt)
    target = store or open_store(ledger_root())
    target.initialize()
    observed = f"hb-epoch:{hb_epoch}"
    retained = {source_key(claimed): source_receipt}
    for _attempt in range(128):
        expected_head = target.get(HEAD_KEY)
        _validate_existing_head(target)
        if idempotent:
            prior = _recorded(target, expected_head, claimed)
            if prior is not None:
                return prior
        previous = (expected_head or {}).get("receipt_sha256") if isinstance(expected_head, dict) else None
        built = {
            "schema": "stegverse.organization-transition-receipt/v1",
            "organization": C["organization"],
            "source_repository": source_receipt["repository"],
            "source_receipt_schema": source_receipt.get("schema"),
            "source_transition_sha256": claimed,
            "source_transition_id": source_receipt.get("transition_id"),
            "repo_receipt_sha256": claimed,
            "repo_transition_id": source_receipt.get("transition_id"),
            "org_transition_class": org_transition_class,
            "predecessor_org_state_sha256": predecessor_state,
            "successor_org_state_sha256": successor_state,
            "boundary_evidence": dict(boundary_evidence or {}),
            "authority_effect": authority_effect,
            "hb_reference": _heartbeat(hb_epoch),
            "observed_at": observed,
            "previous_receipt_sha256": previous,
        }
        digest = sha(built)
        record = {**built, "receipt_sha256": digest}
        key = receipt_key(digest)
        new_head = {
            "organization": C["organization"],
            "receipt_sha256": digest,
            "receipt_path": target.locator(key),
        }
        if target.append_transaction(key, record, expected_head, new_head, immutable=retained):
            return record
    raise SystemExit("ORG_LEDGER_APPEND_CONTENTION_EXHAUSTED")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-receipt", required=True)
    parser.add_argument("--org-transition-class", default="REPO_STATE_PROPAGATION")
    parser.add_argument("--predecessor-org-state-sha256", required=True)
    parser.add_argument("--successor-org-state-sha256", required=True)
    parser.add_argument("--boundary-evidence-json", default="{}")
    parser.add_argument("--authority-effect", default="NONE")
    parser.add_argument("--hb-epoch", type=int, default=None)
    args = parser.parse_args()
    try:
        record = append(
            load(args.repo_receipt), args.org_transition_class, args.predecessor_org_state_sha256,
            args.successor_org_state_sha256, json.loads(args.boundary_evidence_json),
            args.authority_effect, hb_epoch=args.hb_epoch)
    except OrgLedgerEpochRefused as exc:
        print(json.dumps(exc.refusal, sort_keys=True))
        raise SystemExit(1)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
