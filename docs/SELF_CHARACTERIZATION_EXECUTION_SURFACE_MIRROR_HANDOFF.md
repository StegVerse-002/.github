# Organization AI Self-Characterization Execution Surface Mirror Handoff

Status: ACTIVE
Updated: 2026-09-17
Organization: StegVerse-002
Repository: StegVerse-002/.github

## Source of truth

This handoff governs the organization-local StegVerse-002 self-characterization execution surface. The frozen experiment contract remains owned by `StegVerse-002/micro-node-runtime` and remains `v0.3 FROZEN / OPERATIVE`.

Current execution successor:

```text
Goal Task ID: SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001
Parent Goal Task ID: SHWP-SV002-ORG-RUNTIME-ACTIVATION-001
Parent disposition: PROMPT LIMIT REACHED / DO NOT EXTEND
COSV: 50000000107000
Canonical registry shard: StegVerse-Labs/.github/data/canonical-task-records/SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001.json
Registry handoff: StegVerse-Labs/.github/docs/SV002_ACTION_TRANSITION_EVIDENCE_MIRROR_HANDOFF.md
Tracking issue: StegVerse-Labs/.github#2060
Callable-ownership repair: StegVerse-Labs/.github#2063 / a040d37c3809f3d78b6478b1f2e4ff9a3e59e500
```

The exact task shard is present on canonical `main`. Aggregate registry refresh is non-authorizing reconciliation and does not gate this successor.

## Callable-ownership correction — 2026-09-17

The first ephemeral discovery implementation incorrectly assigned the same callable task to both `StegVerseNode` and `StegBrowser`. That was a routing defect because `RT-STEGBROWSER-RUNTIME-CONSUMPTION-001` is explicitly scoped to the StegBrowser manifest-defined transport operation and its existing runner/ingress implementation binds StegBrowser-specific task, COSV, manifest, and packet semantics.

PR `StegVerse-Labs/.github#2063` corrected the split and merged as `a040d37c3809f3d78b6478b1f2e4ff9a3e59e500` after exact-head validation passed for ephemeral discovery, organization control plane, deterministic repository suite, and heartbeat validation.

Canonical callable ownership is now:

```text
StegVerseNode
  class: ephemeral
  availability: AVAILABLE_TO_INVOKE
  instance_state: NOT_MATERIALIZED
  runtime_class: EVENT_EPHEMERAL
  materialization: ON_INVOCATION
  callable_task: SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001
  execution_owner: StegVerse-002/.github
  operation: REQUEST_SELF_CHARACTERIZATION

StegBrowser
  class: ephemeral
  availability: AVAILABLE_TO_INVOKE
  instance_state: NOT_MATERIALIZED
  runtime_class: EVENT_EPHEMERAL
  materialization: ON_INVOCATION
  callable_task: RT-STEGBROWSER-RUNTIME-CONSUMPTION-001
  operation: STEGBROWSER_MANIFEST_DEFINED_INTR_INGRESS

connected_count: 0
zero_connected_devices_is_runtime_blocker: false
```

The StegBrowser reusable task remains valid provenance for the already-validated registered-Node -> Interlock -> Universal InTr materialization -> bounded lease -> event-ephemeral mechanics. It is **not** the callable owner for the SV002 self-characterization operation.

## Ownership and authority

Execution ownership remains:

```text
registered StegVerseNode
-> Interlock/InTr organization ingress
-> StegVerse-002/.github
-> resident-runtime/self_characterization_surface.py
-> StegVerse-002/micro-node-runtime/tools/run_self_characterization_principal.py
-> frozen v0.3 principal
-> StegVerse-002/.github egress
-> Master Records custody/reconstruction
```

Authority invariants:

- execution owner = `StegVerse-002/.github`;
- principal owner = `StegVerse-002/micro-node-runtime`;
- Task Registry = intent/coordination only;
- WorkerCoordinator = claim/fence authority;
- Interlock/InTr = governed transition authority;
- TV/TVC = credential/provider authority;
- Master Records = observed-reality custody/reconstruction authority;
- HeartBeat = timing/freshness/liveness/observability only;
- GitHub/CI/source runtime authority = `NONE`;
- model output does not self-grant authority;
- second user-operated device required = `false`;
- standing runtime required = `false`.

## Universal action-transition evidence invariant

Every StegVerse action is canonically complete only when every required governed state transition is authentically emitted, retained, same-execution correlated, and reconstructable through canonical Master Records custody.

This is ecosystem-wide. Missing transition evidence means the action is not proven complete; source, CI, scheduling, discovery metadata, runtime declarations, or partial receipts cannot substitute for the complete transition chain.

## Frozen v0.3 semantics

```text
experiment condition: v0.3 FROZEN / OPERATIVE
implementation: evolving
external evaluation: separate revision stream
```

Implementation may repair invocation, transport, custody, reconstruction, physical-substrate portability, and evidence retention without changing v0.3. It may not change the principal-visible objective, frozen resources, subject-visible discovery condition, permitted actions, stopping semantics, or frozen snapshot content.

## Required invocation path

The corrected operation-specific path is:

```text
REGISTERED_STEGVERSE_NODE
-> INTERLOCK
-> UNIVERSAL_INTR_MATERIALIZATION
-> BOUNDED_INVOCATION_LEASE
-> EVENT_EPHEMERAL_RUNTIME
-> EXECUTION_TIME_RUNTIME_IDENTITY
-> WORKERCOORDINATOR_CLAIM_FENCE
-> AUTHENTIC_INTR_INGRESS
-> STEGVERSE_002_ORG_SELF_CHARACTERIZATION_SURFACE
-> FROZEN_V0_3_PRINCIPAL_EXECUTION
-> GOVERNED_EGRESS
-> MASTER_RECORDS_CUSTODY_RECONSTRUCTION
```

No attached or continuously connected device is required. `NOT_MATERIALIZED` is the correct resting state before invocation.

## Required transition evidence

The same invocation must retain, at minimum, authentic evidence for:

```text
REQUEST_BOUND
STEGVERSE_NODE_BOUND_TO_INVOCATION
INTERLOCK_BOUND_TO_NODE_AND_MANIFEST
INTR_MATERIALIZATION_ADMITTED
INVOCATION_SCOPED_LEASE_ESTABLISHED
EVENT_EPHEMERAL_RUNTIME_MATERIALIZED
EXECUTION_TIME_RUNTIME_IDENTITY_BOUND
T0_CAPTURED
CURRENT_WORKERCOORDINATOR_CLAIM_FENCE_OBSERVED
AUTHENTIC_INTR_INGRESS_OBSERVED
PRINCIPAL_EXECUTION_TRANSITIONS_RETAINED
EGRESS_EMITTED
MASTER_RECORDS_CUSTODY_OBSERVED
MASTER_RECORDS_RECONSTRUCTION_PASS
ALL_REQUIRED_ACTION_TRANSITIONS_RECONSTRUCTABLE
```

The actual internal principal-transition set must come from the frozen v0.3 contract and authentic runtime receipts. This handoff must not invent transition occurrence.

## Organization-boundary receipt custody

The organization boundary continues to preserve the canonical live transition lineage:

```text
INGRESS_ACCEPTED
DISPATCHED
<principal executes>
CONSUMED
RESULT_BOUND
EGRESS_EMITTED
```

`ORG_BOUNDARY_RECEIPTS.live.jsonl` is the append-only live surface. `ORG_BOUNDARY_RECEIPTS.json` is the terminal bundle. Exactly-once replay reuses the frozen bundle instead of minting a second history.

Transport consumption and principal completion remain distinct. A fail-closed or partial endpoint result may be transported without being promoted to successful experiment completion.

## Master Records rule

StegVerse-002 is the event source and receipt issuer. Master Records is the canonical custody/reconstruction authority. `resident-runtime/submit_sv002_self_characterization_to_master_records.py` remains the canonical artifact-custody path for a completed v0.3 artifact set. Publication alone is not reconstruction success; Master Records must establish custody and return reconstruction PASS.

## Current runtime truth

```text
frozen v0.3 contract: OPERATIVE / UNCHANGED
parent SHWP-SV002-ORG-RUNTIME-ACTIVATION-001: PROMPT LIMIT REACHED
successor SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001: ACTIVE
successor canonical registry shard: PRESENT ON MAIN
successor COSV: 50000000107000
callable ownership defect: REPAIRED / MERGED
repair merge: a040d37c3809f3d78b6478b1f2e4ff9a3e59e500
StegVerseNode callable task: SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001
StegVerseNode execution owner: StegVerse-002/.github
StegVerseNode operation: REQUEST_SELF_CHARACTERIZATION
StegBrowser callable task: RT-STEGBROWSER-RUNTIME-CONSUMPTION-001
zero connected devices: NOT A BLOCKER
standing runtime required: false
second user-operated device required: false
successor invocation consumed: NOT YET OBSERVED
T0 for successor rerun: NOT YET OBSERVED
principal execution for successor rerun: NOT YET OBSERVED
complete same-execution transition evidence: NOT YET OBSERVED
Master Records reconstruction PASS for successor rerun: NOT YET OBSERVED
SYSTEM_AI_ACTIVE from this rerun: false
```

## Next action

Consume `SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001` through the corrected `StegVerseNode -> Interlock -> InTr -> bounded EVENT_EPHEMERAL -> StegVerse-002/.github self-characterization` path. Capture each required transition as it occurs and preserve the exact same-invocation lineage through Master Records. Do not route this operation through the StegBrowser manifest task, and do not add a host, bridge, listener, scheduler, alternate dispatcher, second request, second device, or synthetic receipt.

## Manual work

None.
