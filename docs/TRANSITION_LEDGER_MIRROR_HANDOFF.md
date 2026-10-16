# Transition Ledger Mirror Handoff

Repository: `StegVerse-002/.github`

Every durable transition owned here is recorded first in this repository ledger. Repo replay/reconstruction must terminate without org/ecosystem replay.

Contract: `.stegverse/transition-ledger/contract.json`  
Emitter: `.stegverse/transition-ledger/emit.py`  
Store: `resident-runtime/ledger_store.py`  
Durable root: the repository subtree `repository-ledger/StegVerse-002/.github/` of the published organization ledger ref `refs/stegverse/organization-ledger`, addressed as `git+<checkout>#refs/stegverse/organization-ledger:repository-ledger/StegVerse-002/.github`. `STEGVERSE_REPO_LEDGER_ROOT`, when set, overrides that location. There is no host-state default.

`organization-ledger-transition.yml` binds both roots from the contracts, appends an intr-destination diagnostic self-closure, fast-forward pushes the ref, and reads both chains back (`resident-runtime/organization_ledger_readback.py --repository-namespace`).

Receipts are append-only and hash-linked. Only evidence needed for organization reconstruction propagates upward. A recorded disposition is transition evidence only. Authority and time stay constraint variables.
