# STEGVERSE_002_ORG_BOUNDARY_MIRROR_HANDOFF.md

Status: ACTIVE
Updated: 2026-08-31

## Goal
Establish StegVerse-002/.github as the canonical organizational ingress/egress definition for StegVerse-002.

## Current task authority
1. This handoff is the source of truth for org-boundary/* in this repository.
2. Cross-organization traffic is represented as governed InTr envelopes at this boundary.
3. Individual repositories expose application/runtime profiles and must not independently redefine organization-level transport semantics.
4. HB or HB-derived carriers provide synchronization/carrier capability only; they grant no admission, execution, credential, routing, transition, receiving, publication, or release authority.
5. GitHub Actions may validate source/evidence, but GitHub runtime is not execution authority.

## Canonical layering
HB or HB-derived carrier -> InTr org boundary -> ingestion/normalization -> core-lite registry/routing -> repository/runtime profile.
Return path: endpoint result -> evidence binding -> org egress -> InTr -> carrier.

## Organization repositories currently registered for boundary profiling
- StegVerse-002/StegProfile
- StegVerse-002/legacy_core_lite
- StegVerse-002/micro-node-runtime
- StegVerse-002/capability-registry
- StegVerse-002/core-lite
- StegVerse-002/StegGuardian
- StegVerse-002/admissibility-gateway
- StegVerse-002/stegguardian-wiki

## Immediate implementation
- org-boundary/README.md
- org-boundary/schemas/intr-envelope.schema.json
- org-boundary/evidence/receipt-chain.schema.json
- org-boundary/registry/services.json
- stegverse.architecture.json

## Evidence semantics
Source presence, CI success, merge, deployment, activation, ingress receipt, dispatch, consumption, observation, egress, and same-execution reconstruction are distinct states.

## Next
Replace generic INTERNAL_ENDPOINT entries with tighter endpoint-specific profiles as each repository's own handoff and runtime contract are reconciled.


## Canonical resident-runtime activation rule — 2026-08-31
- Every StegVerse-002 resident runtime activation surface MUST be kept in `StegVerse-002/.github`.
- No application repository is the organization resident-runtime activation authority.
- Application repositories expose capabilities/endpoints to the organizational boundary; the organization `.github` owns activation, ingress, egress, and organization-crossing transport behavior.
- All communication crossing the StegVerse-002 organizational boundary MUST be generated through this `.github` boundary using Interlock/InTr semantics.
- Ingress responsibilities: carrier observation, InTr envelope validation, provenance binding, transition-context binding, destination/profile resolution, dispatch evidence.
- Egress responsibilities: result/evidence validation, destination-org resolution, InTr envelope generation, egress evidence, reconstruction linkage.
- HB/HB-derived carrier presence remains non-authorizing. Authority is determined by applicable transition elements.
- GitHub Actions may validate or transport evidence, but GitHub-hosted workflow execution is not required as sovereign runtime authority.
- Canonical implementation paths: `org-boundary/runtime/`, `org-boundary/registry/`, `org-boundary/schemas/`, `org-boundary/evidence/`, `resident-runtime/`.
- Any legacy resident activation implementation outside `StegVerse-002/.github` becomes an endpoint/provider to this boundary or must be migrated here; it must not remain a competing organizational activation point.


## Self-characterization execution ownership — 2026-09-01

The reusable organization-local AI self-characterization execution surface is now installed here:

- `resident-runtime/self_characterization_surface.py`
- `resident-runtime/self-characterization/stegverse-002.json`
- `docs/SELF_CHARACTERIZATION_EXECUTION_SURFACE_MIRROR_HANDOFF.md`
- service `stegverse-002.self-characterization`

Canonical path:

```text
StegVerse-org/StegVerse-SDK
-> StegVerse-org/.github
-> StegVerse-002/.github
-> stegverse-002.self-characterization
-> StegVerse-002/micro-node-runtime
-> StegVerse-002/.github egress
-> Master Records
```

This supersedes any use of another organization's resident worker as the execution authority for StegVerse-002. External organizations may observe Master Records-derived evidence or validate published receipt schemas, but they do not execute the StegVerse-002 principal.


## Recursive transition ledger scope — 2026-09-01

The repository-level transition-ledger invariant applies to **all StegVerse-002 repositories**, not only the experiment principal and organization boundary.

Current organization census:

- StegVerse-002/StegProfile
- StegVerse-002/legacy_core_lite
- StegVerse-002/micro-node-runtime
- StegVerse-002/capability-registry
- StegVerse-002/core-lite
- StegVerse-002/StegGuardian
- StegVerse-002/admissibility-gateway
- StegVerse-002/.github
- StegVerse-002/stegguardian-wiki

Each repository owns and records its durable transitions first through:

- `.stegverse/transition-ledger/contract.json`
- `.stegverse/transition-ledger/emit.py`
- `docs/TRANSITION_LEDGER_MIRROR_HANDOFF.md`

Repository replay terminates at repository level. Organization-level consequences are verified and hash-linked by this `.github` organization ledger, and only the evidence required for ecosystem reconstruction propagates to Master Records.

The StegVerse-002 self-characterization-specific receipt chains remain canonical specialized evidence and are not replaced by this universal ledger layer.


## Organization capability discovery surface — 2026-09-01

Every StegVerse-002 repository owns `.stegverse/capability/descriptor.json`. This organization boundary maintains an exact-source-commit projection in:

- `org-boundary/registry/capabilities.json`
- `org-boundary/registry/capability-descriptors.snapshot.json`

Read-only discovery service:

`stegverse-002.capability-discovery`

Operations:
- `LIST_CAPABILITIES`
- `SEARCH_CAPABILITIES`
- `READ_CAPABILITY_DESCRIPTOR`

The service is discovery-only and grants no authority. Descriptor availability does not prescribe identity constitution, self-characterization relevance, use, standing, or admissibility.

For the still-unexecuted self-characterization experiment, the pinned capability snapshot is exposed through the principal's ordinary resource-search/read interface without injecting the sibling list or an ontology into the objective.


## v0.3 organization-boundary source closure — 2026-09-01

Canonical remaining boundary deltas were merged by PR #12 as `f77e4fe49a13b9ca2fae898053d87569b52361aa`.

Validated source behavior now includes:
- live boundary receipt ordering around the principal execution surface;
- normalized endpoint/application disposition separate from transport consumption and principal completion;
- exactly-once reuse of an already frozen boundary bundle;
- repository-root -> organization-root hierarchical aggregation;
- pull-request validation of both the boundary processor and self-characterization hierarchical organization ledger.

PR validation for Org Boundary Execution and SV002 Capability Discovery passed before merge.

Source readiness does not establish resident execution. The next machine-owned transition is a single authentic `STEGVERSE-002-SELF-CHARACTERIZATION-001` execution on an eligible StegVerse-002 resident runtime, followed by Master Records reconstruction. GitHub Actions remains validation-only and MUST NOT substitute for that runtime.


## 2026-09-26 — separate source-owned open-source audit

Central goal `ECOSYSTEM-OPEN-SOURCE-STRATEGY-001` / COSV `20010010100000`; organization source evidence in `docs/OPEN_SOURCE_ORGANIZATION_INVENTORY_20260926.json`. Nine entries (two public, six private, one internal) checked at root LICENSE and LICENSE.md paths: two observed identical MIT root texts, seven checked roots not found. Nonpublic names stay source-owned; central public census aggregates counts only. Legal rights, complete file provenance, third-party dependencies and release approval remain unverified. This does not affect original organization boundary, execution authority, SDK, Master Records or runtime.
