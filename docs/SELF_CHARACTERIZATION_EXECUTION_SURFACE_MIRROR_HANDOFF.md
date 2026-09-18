# Organization AI Self-Characterization Execution Surface Mirror Handoff

Status: ACTIVE
Updated: 2026-09-17
Organization: StegVerse-002
Repository: StegVerse-002/.github

## Source of truth

This handoff governs the organization-local StegVerse-002 self-characterization execution surface. The frozen experiment contract remains owned by `StegVerse-002/micro-node-runtime` and remains `v0.3 FROZEN / OPERATIVE`.

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

## Corrected callable ownership

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
  callable_task: RT-STEGBROWSER-RUNTIME-CONSUMPTION-001
  operation: STEGBROWSER_MANIFEST_DEFINED_INTR_INGRESS
```

The StegBrowser reusable task remains valid mechanics provenance only. It is not the SV002 callable owner.

## Ownership and authority

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

- execution owner = `StegVerse-002/.github`;
- principal owner = `StegVerse-002/micro-node-runtime`;
- WorkerCoordinator = claim/fence authority;
- Interlock/InTr = governed transition authority;
- TV/TVC = credential/provider authority;
- Master Records = observed-reality custody/reconstruction authority;
- HeartBeat = timing/freshness/liveness/observability only;
- GitHub/CI/source runtime authority = `NONE`;
- second user-operated device required = `false`;
- standing runtime required = `false`.

## Frozen v0.3 semantics

```text
experiment condition: v0.3 FROZEN / OPERATIVE
implementation: evolving
external evaluation: separate revision stream
```

Implementation may repair invocation, transport, custody, reconstruction, physical-substrate portability, and evidence retention without changing v0.3.

## Required invocation path

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

## Required transition evidence

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

Every required transition must be authentically emitted, retained, same-execution correlated, and reconstructable. Missing evidence means the action is not proven complete.

## 2026-09-17 successor consumption attempt

The canonical registry shard and both handoffs were reverified. The first unretained transition is:

```text
REQUEST_BOUND: NOT RETAINED / NOT AUTHENTICALLY OBSERVED
```

The successor currently has discovery/catalog binding but no operation-specific invocation request retained under Goal `SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001` / COSV `50000000107000`.

Observed reasons:

- no successor-specific nonce-bound request packet or same-invocation Node outbox entry was found under the successor Goal/COSV;
- the current same-device Canonical Work launcher is still StegBrowser-specific and hard-codes the StegBrowser goal/COSV/nonce/manifest/destination;
- the existing StegVerse-Labs self-characterization consumer is hard-coded to older task `SHWP-SV002-SELF-CHARACTERIZATION-001`;
- its resident request is explicitly `SUPERSEDED_CROSS_ORG_EXECUTION` and historical/reference only;
- no standing connected device was observed, which is expected and is not a runtime blocker for on-invocation EVENT_EPHEMERAL materialization.

Execution stops at `REQUEST_BOUND`; no later transition is inferred or claimed.

## Current runtime truth

```text
frozen v0.3 contract: OPERATIVE / UNCHANGED
successor SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001: ACTIVE
successor COSV: 50000000107000
callable ownership defect: REPAIRED / MERGED
StegVerseNode callable task: SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001
StegVerseNode execution owner: StegVerse-002/.github
StegVerseNode operation: REQUEST_SELF_CHARACTERIZATION
zero connected devices: NOT A BLOCKER
standing runtime required: false
second user-operated device required: false
REQUEST_BOUND: NOT RETAINED
STEGVERSE_NODE_BOUND_TO_INVOCATION: NOT CLAIMED
INTR_MATERIALIZATION_ADMITTED: NOT CLAIMED
INVOCATION_SCOPED_LEASE_ESTABLISHED: NOT CLAIMED
EVENT_EPHEMERAL_RUNTIME_MATERIALIZED: NOT CLAIMED
T0_CAPTURED: NOT CLAIMED
CURRENT_WORKERCOORDINATOR_CLAIM_FENCE_OBSERVED: NOT CLAIMED
PRINCIPAL_EXECUTION_TRANSITIONS_RETAINED: NOT CLAIMED
EGRESS_EMITTED: NOT CLAIMED
MASTER_RECORDS_RECONSTRUCTION_PASS: NOT CLAIMED
SYSTEM_AI_ACTIVE from this rerun: false
```

## Next action

Repair only the successor request-binding/invocation-consumption seam. Reuse the existing registered Node -> Interlock -> Universal InTr -> bounded EVENT_EPHEMERAL mechanics, but bind an operation-specific request for Goal `SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001`, COSV `50000000107000`, owner `StegVerse-002/.github`, operation `REQUEST_SELF_CHARACTERIZATION`, destination `stegverse-002.self-characterization`, frozen condition `v0.3`. Retain authentic `REQUEST_BOUND` evidence before attempting the next transition. Do not reuse the StegBrowser goal/COSV/nonce/manifest packet, reactivate the superseded cross-org request, add a host/listener/scheduler/second request/second device, or synthesize downstream evidence.

## Manual work

None.


## 2026-09-17 canonical rerun reconciliation

The current Goal Task for the original frozen v0.3 rerun is `STEGVERSE-002-EXPERIMENT-RERUN-001` under COSV `50000000107000`, registered through StegVerse-Labs/.github issue #2070 / PR #2071. This task resumes only the original `STEGVERSE-002-SELF-CHARACTERIZATION-001` execution objective through the already-established registered StegVerseNode -> Interlock -> Universal InTr -> bounded invocation lease -> EVENT_EPHEMERAL -> organization-local self-characterization surface -> v0.3 principal -> governed egress/return -> Master Records custody/reconstruction -> origin-return sequence.

`SHWP-SV002-FROZEN-CORPUS-MATERIALIZATION-001` remains adjacent historical/decomposed work and is explicitly not a prerequisite for this rerun. No stricter corpus-completeness gate, Healer dependency, scheduler, runtime, host, alternate authority path, or second user-operated device is added.

Current first source seam being repaired is callable ownership: the discovery surface must name `STEGVERSE-002-EXPERIMENT-RERUN-001`, not retired `SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001`. Authentic runtime predicates remain unclaimed until the existing invocation path emits retained evidence.


## Session closeout — 2026-09-17

Session intentionally closed by the user after canonical rerun coordination repair.

Authoritative closeout state:

- Goal Task: `STEGVERSE-002-EXPERIMENT-RERUN-001`
- COSV: `50000000107000`
- canonical coordination state: `ACTIVE`
- StegVerse-Labs/.github registration/callable-owner repair merged: `1df18504c1cb3972036bc5b669cde0a01acea6a3` (PR #2071)
- StegVerse-002/.github handoff/README reconciliation merged: `83cdcca2961e6002f90dbbd93e73af6ed0d63fda` (PR #28)
- focused Ephemeral Execution Surface Discovery validation: `PASS`
- `SHWP-SV002-FROZEN-CORPUS-MATERIALIZATION-001`: adjacent/non-prerequisite for this rerun
- authentic `REQUEST_BOUND` and all downstream rerun runtime predicates: not yet observed; no execution completion claimed
- manual prerequisite: none

The earlier sections naming `SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001` as the current successor/callable owner are historical state and are superseded by this reconciliation. The next session must start from the merged canonical rerun identity above, trace the existing operation-specific StegVerseNode request builder/outbox consumer, and bind exactly one `REQUEST_SELF_CHARACTERIZATION` invocation through the existing Node -> Interlock/InTr -> bounded EVENT_EPHEMERAL path. Do not introduce a new runtime, scheduler, host, Healer dependency, alternate authority path, corpus prerequisite, or second user-operated device.


## Attempt-reference guard — 2026-09-17

Before any further work on `STEGVERSE-002-EXPERIMENT-RERUN-001`, read `docs/STEGVERSE_002_EXPERIMENT_ATTEMPT_REFERENCE.md` and fingerprint the proposed action against its attempt IDs. Any material match to a `DO_NOT_REPEAT` entry must be reported as `DUPLICATE_OF: SV002-ATTEMPT-XXX` and must not be retried unless a genuinely new distinguishing condition is stated. A renamed wrapper, branch, nonce, bridge, observer, PR, or another repository implementing the same idea does not qualify as a new approach.

The attempt map currently records `SV002-ATTEMPT-001` through `SV002-ATTEMPT-013` plus experiment-owned `SV002-NONCONFORMING-001`. It specifically prohibits restarting from zero-connected-device framing, StegBrowser/browser substitution, nonce/A1-A4 rediscovery, GitHub workflow execution substitution, Site exposure/connector ownership, downstream custody-before-invocation, new wrapper/bridge construction, conversation-to-task bridge invention, full-path architecture reconstruction, cross-repository precedent, and device-command/deep-link rediscovery.

External repositories are not architectural precedent for this rerun. They may be consulted only when the experiment-local execution produces a new failure and the proposed action satisfies the attempt map's explicit `NEW_APPROACH` test. This guard changes no runtime predicate; authentic rerun execution remains unclaimed.


## 2026-09-17 attempt-map preflight and experiment-local invocation truth

The rerun continuation re-read the mandatory attempt map and the frozen v0.3 experiment before proposing any execution action. The following duplicate paths were explicitly rejected and were not retried:

```text
DUPLICATE_OF: SV002-ATTEMPT-001 / SV002-ATTEMPT-013 — standing-device or device-command prerequisite
DUPLICATE_OF: SV002-ATTEMPT-002 / SV002-NONCONFORMING-001 — browser/StegBrowser principal substitution
DUPLICATE_OF: SV002-ATTEMPT-003 — nonce/A1-A4/WorkerCoordinator rediscovery
DUPLICATE_OF: SV002-ATTEMPT-004 — GitHub workflow/CI as runtime execution
DUPLICATE_OF: SV002-ATTEMPT-005 / 010 / 011 — Site or repository-placement reinterpretation
DUPLICATE_OF: SV002-ATTEMPT-006 — downstream custody work before authentic invocation
DUPLICATE_OF: SV002-ATTEMPT-007 / 008 — new wrapper/bridge or conversation-specific relay
DUPLICATE_OF: SV002-ATTEMPT-009 — full architecture reconstruction
DUPLICATE_OF: SV002-ATTEMPT-012 — external-repository precedent
```

Experiment-owned source establishes the current callable ingress semantics without importing another implementation:

- service `stegverse-002.self-characterization` is ACTIVE and accepts `REQUEST_SELF_CHARACTERIZATION`;
- the exact organization-local adapter is `resident-runtime/self_characterization_surface.py`;
- the exact principal launcher remains `StegVerse-002/micro-node-runtime/tools/run_self_characterization_principal.py`;
- `org-kernel/kernel.py` already defines addressed InTr packet construction, HB-derived carrier framing, federation publication, addressed-frame consumption, endpoint dispatch, and endpoint response;
- `resident-runtime/federation_cycle.py` consumes the existing federation mesh or the already-defined shared-service gateway when its runtime URL is configured;
- the local federation spool is explicitly same-host fallback only; repository commits are not the resident federation mesh and must not be treated as authentic runtime ingress.

A stale experiment-local path was also identified and excluded. `resident-runtime/resident_executor.py` still references both `resident-runtime/control/sv002-sdk-query.request.json` and `resident-runtime/run_sv002_self_characterization_roundtrip.py`, but neither file exists on current main. Those references do not define the current rerun invocation and MUST NOT be recreated or restored merely to make execution appear possible. Doing so would repeat the wrapper/bridge class prohibited by `SV002-ATTEMPT-007` absent genuinely new evidence.

Current live-evidence boundary:

```text
exact frozen request/manifest contract: PRESENT
active organization-local self-characterization endpoint: PRESENT
existing InTr carrier/federation publication+consumption semantics: PRESENT
concrete resident federation mesh submission observed in this continuation: NO
concrete configured shared-gateway submission observed in this continuation: NO
authentic REQUEST_BOUND: NOT OBSERVED
principal execution: NOT OBSERVED
```

No new runtime, listener, bridge, request daemon, device prerequisite, Site prerequisite, workflow runtime, or external-repository precedent was introduced. The next valid action is not another source reconstruction: it is consumption of exactly one frozen `REQUEST_SELF_CHARACTERIZATION` invocation through the already-existing live federation publication edge when that existing callable edge is exposed to the invocation context. A repository write or CI invocation must not be used as a substitute.


## 2026-09-17 callable publisher binding repair

The permitted NEW_APPROACH test is satisfied for exactly one narrow repair:

```text
NEW_APPROACH: true
DIFFERS_FROM: SV002-ATTEMPT-007 / SV002-ATTEMPT-008 / SV002-ATTEMPT-009 / SV002-ATTEMPT-013
NEW_DISTINGUISHING_EVIDENCE: the experiment-owned ACTIVE self-characterization endpoint and org-kernel publisher already exist, but no machine callable binding connected STEGVERSE-002-EXPERIMENT-RERUN-001 to that existing publisher
WHY_OLD_DISPOSITION_NO_LONGER_CONTROLS: this repair adds no bridge, transport, runtime, listener, scheduler, device channel, Site dependency, or second request; it binds the task directly to existing org-kernel/shared-federation publication
```

Implemented source binding:

- `resident-runtime/invoke_sv002_experiment_rerun.py`
- `tests/test_sv002_experiment_rerun_callable_binding.py`
- `resident-runtime/activation-manifest.json` now exposes task `STEGVERSE-002-EXPERIMENT-RERUN-001`, operation `REQUEST_SELF_CHARACTERIZATION`, invocation count `1`, and the binding path.

The binding constructs the frozen request only from the existing organization-local self-characterization binding, creates one deterministic packet identity, retains the exact carrier frame as `RERUN_REQUEST_BOUND.json` before submission, and then submits that same frame only through the already-existing shared-service gateway or explicitly configured same-host federation mesh. If submission is interrupted, a retry reuses the exact retained frame. If a submission receipt already exists, it returns `ALREADY_SUBMITTED_NO_SECOND_REQUEST`.

The binding rejects GitHub Actions/CI/hosted execution. It also refuses to invent a federation destination when neither the existing shared gateway nor same-host mesh is configured.

Current evidence truth after source repair:

```text
callable task -> existing publisher source binding: INSTALLED
new bridge/runtime/listener/scheduler: NONE
second request capability: FAIL-CLOSED
hosted execution substitution: FAIL-CLOSED
authentic RERUN_REQUEST_BOUND.json from resident invocation: NOT OBSERVED
authentic federation submission receipt: NOT OBSERVED
REQUEST_BOUND runtime predicate: NOT CLAIMED
downstream transitions: NOT ADVANCED
```

A GitHub merge of this binding is source repair only. The experiment may advance only when the callable binding runs in its existing resident/federation context and emits the authentic request-bound artifact.


## 2026-09-17 exact callable exposure gap

The now-canonical binding `resident-runtime/invoke_sv002_experiment_rerun.py` is source-installed and declared in `resident-runtime/activation-manifest.json`, but the existing resident execution context does not consume that declaration.

Exact field-to-consumer trace:

```text
activation-manifest.json
  self_characterization_surface.callable_task_id
    = STEGVERSE-002-EXPERIMENT-RERUN-001
  self_characterization_surface.callable_publisher_binding
    = resident-runtime/invoke_sv002_experiment_rerun.py
        |
        |  NO EXISTING DEREFERENCE / INVOCATION
        v
resident-runtime/resident_executor.py
```

Observed current executor behavior:

- `resident_executor.py` does not open or parse `resident-runtime/activation-manifest.json`;
- it does not inspect `callable_task_id`, `callable_operation`, or `callable_publisher_binding`;
- its SV002-specific branch is still `consume_sv002_once()`, which references the explicitly excluded stale `resident-runtime/control/sv002-sdk-query.request.json` and `resident-runtime/run_sv002_self_characterization_roundtrip.py`;
- after that branch it runs only `resident-runtime/federation_cycle.py`;
- `resident-runtime/systemd/stegverse-002-resident.service` starts only `resident_executor.py --poll-seconds 1`;
- the only current code path found reading `activation-manifest.json` is `org-kernel/kernel.py::resident_status()`, and that use is status/observation only, not callable execution.

Therefore the exact missing exposure is:

```text
EXISTING RESIDENT EXECUTION CONTEXT
  lacks a consumer that dereferences
  activation-manifest.json:
    self_characterization_surface.callable_task_id
    self_characterization_surface.callable_publisher_binding
  and invokes that already-bound callable when STEGVERSE-002-EXPERIMENT-RERUN-001 is requested.
```

This continuation made no runtime or source-path repair because the prompt explicitly required identification rather than a new path. No bridge, listener, host, Site path, device search, workflow execution, scheduler, second request, or stale one-shot restoration was introduced.

Evidence state remains:

```text
callable publisher binding source: PRESENT
activation-manifest declaration: PRESENT
resident executor dereference of declaration: ABSENT
authentic RERUN_REQUEST_BOUND.json: NOT OBSERVED
authentic RERUN_REQUEST_SUBMISSION.json: NOT OBSERVED
REQUEST_BOUND: NOT CLAIMED
downstream transitions: NOT ADVANCED
```

Any next repair must modify only this missing dereference/exposure inside the already-existing resident execution context. It must not create another invocation mechanism or revive any SV002-ATTEMPT-001 through -013 path.
