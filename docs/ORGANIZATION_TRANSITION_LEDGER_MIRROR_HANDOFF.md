# Organization Transition Ledger Mirror Handoff

Organization: `StegVerse-002`

Repository-level transitions remain owned and replayable in their originating repositories. This `.github` layer verifies a repo receipt, records only the organization-level state consequence, and links the exact repo receipt hash. The source receipt is retained under `source-receipts/` in the same transaction.

Contract: `.stegverse/transition-ledger/org-contract.json`  
Rollup: `resident-runtime/aggregate_repo_transition.py`  
Published ref: `refs/stegverse/organization-ledger` in `StegVerse-002/.github`  
Readback: `resident-runtime/organization_ledger_readback.py`

`STEGVERSE_ORG_LEDGER_ROOT`, when set, overrides the published ref. A plain path remains a POSIX root. `git+<repository>#<ref>` is that ref.

Organization replay must terminate using verified repo receipts plus this org chain; it must not depend on Master Records ecosystem reconstruction.

Only the organization receipt and evidence required for ecosystem reconstruction propagate to `master-records/.github`. A recorded disposition is transition evidence only. Authority and time stay constraint variables.

An intr-destination diagnostic self-closure (`resident-runtime/intr_destination_ingress.py --self-closure`) appends repository and organization receipts that carry `communication_id` onto this ref. `organization-ledger-transition.yml` is the `workflow_dispatch` run that publishes the ref and reads those receipts back.
