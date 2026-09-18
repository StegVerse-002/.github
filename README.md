# StegVerse-002 Organization Control Plane

This repository owns StegVerse-002 organization-local discovery, ingress, egress, resident dispatch, organization-ledger, and cross-organization execution-boundary semantics. It does **not** own the frozen principal model/runtime/resource contract, which remains in `StegVerse-002/micro-node-runtime`, and GitHub Actions has no runtime authority.

## Self-characterization execution ownership

For `STEGVERSE-002-SELF-CHARACTERIZATION-001`, organization execution ownership remains:

```text
external requester
-> InTr / organization ingress
-> StegVerse-002/.github
-> StegVerse-002-owned principal
-> organization egress
-> Master Records custody/reconstruction
```

A source organization may request self-characterization but may not execute the StegVerse-002 principal. TV/TVC remains credential authority; WorkerCoordinator remains claim/fence authority; InTr/Interlock remains transition authority; Master Records remains observed-reality/custody/reconstruction authority.

The historical/resident implementation in `resident-runtime/self_characterization_surface.py` is Python/local-repository coupled. It remains valid historical source but is not an acceptable final implementation when the physical execution requirement is `CURRENT_USER_IPHONE` with no second user-operated machine.

## Native current-iPhone execution envelope

The first released envelope revision, `stegverse.sv002-native-org-execution-envelope/v1`, bound the target ingress packet/manifest and all execution/authority constraints but did not cryptographically bind the target organization's canonical `INGRESS_ACCEPTED` receipt. Because no physical native envelope had yet been materialized, v1 is retained as historical/provenance source and MUST NOT be consumed for a new native execution.

The current consumable revision is:

```text
stegverse.sv002-native-org-execution-envelope/v1.1
```

Implementation:

```text
schemas/sv002-native-org-execution-envelope-v1.1.schema.json
resident-runtime/validate_sv002_native_org_execution_envelope_v1_1.py
tests/test_sv002_native_org_execution_envelope_v1_1.py
```

v1.1 reuses the existing request and task exactly:

```text
request: RESIDENT-EXEC-SV002-ORG-RUNTIME-ACTIVATION-001
task: SHWP-SV002-ORG-RUNTIME-ACTIVATION-001
```

It binds the frozen ingress packet/manifest plus the exact canonical payload SHA-256 and the target-org `INGRESS_ACCEPTED` receipt identity. The canonical target-boundary receipt is derived from:

```text
{
  packet_id,
  service_id: stegverse-002.self-characterization,
  payload_hash,
  kind: INGRESS_ACCEPTED,
  previous_receipt_id: null
}
```

The envelope must carry the exact deterministic `receipt_id`, `evidence_hash`, service subject, and null predecessor. The v1.1 binder consumes a supplied target-org receipt and verifies that identity; it does not synthesize admission evidence from packet fields alone.

The envelope also binds the frozen objective/knowledge policy, target-org execution ownership, `CURRENT_USER_IPHONE`, `RESIDENT_LOOPBACK_NATIVE_IOS`, the released target model/package identity, the exact materialized frozen-resource-bundle SHA-256, TV/TVC credentials, required WorkerCoordinator/InTr admission, and required Master Records reconstruction.

It fails closed on target-ingress-receipt drift, request/task substitution, ownership drift, frozen-contract drift, reference-model substitution, hosted or second-machine fallback, runtime network resource fetch, non-TV/TVC credentials, GitHub runtime authority, disabled Master Records requirements, or authority transfer. The envelope has `authority_effect=NONE_EXECUTION_REQUEST_ONLY`; its existence alone grants no execution authority.

The real frozen resource-bundle SHA-256 is intentionally not predeclared in source because the real bundle bytes have not yet been materialized. A consumable v1.1 envelope can only be finalized after those exact bytes exist and are hash-bound.

Source/schema/test success does not prove WorkerCoordinator checkout, delivery to the physical iPhone, live runtime identity, resident-request consumption, principal execution, downstream organization-boundary transitions, Master Records reconstruction, or `SYSTEM_AI_ACTIVE`.

## Universal action-transition evidence invariant

Every StegVerse action is canonically complete only when every required governed state transition is authentically emitted, retained, same-execution correlated, and reconstructable through canonical Master Records custody. This is an ecosystem-wide invariant, not a special condition of the StegVerse-002 experiment.

For the frozen v0.3 rerun, the current successor coordination task is `SHWP-SV002-ACTION-TRANSITION-EVIDENCE-001` under COSV `50000000107000`. It reuses the already-validated event-ephemeral path:

```text
registered StegVerseNode
-> Interlock
-> Universal InTr materialization
-> bounded invocation lease
-> EVENT_EPHEMERAL runtime
-> execution-time runtime identity
-> WorkerCoordinator claim/fence
-> authentic governed ingress
-> frozen v0.3 execution
-> governed egress
-> Master Records custody/reconstruction
```

Zero connected devices is not a runtime blocker for this path. No standing runtime, external host, second request, second scheduler, second WorkerCoordinator, alternate credential path, or second user-operated device may be introduced merely to make the rerun executable.

Missing required transition evidence means the action is not proven complete. Source state, CI, discovery metadata, scheduling metadata, or partial receipts cannot substitute for the complete transition chain.


## Current original rerun task

The current canonical rerun identity is `STEGVERSE-002-EXPERIMENT-RERUN-001` with COSV `50000000107000`. It uses the existing registered StegVerseNode -> Interlock/InTr -> bounded EVENT_EPHEMERAL execution path and does not depend on `SHWP-SV002-FROZEN-CORPUS-MATERIALIZATION-001` as a prerequisite.


## StegVerse-002 experiment attempt reference

`docs/STEGVERSE_002_EXPERIMENT_ATTEMPT_REFERENCE.md` is the mandatory preflight history for `STEGVERSE-002-EXPERIMENT-RERUN-001`. It assigns stable IDs to already-tried, non-working, non-conforming, or mis-scoped approaches and defines a duplicate-attempt gate. Before another rerun action is taken, the proposed action must be checked against that map; matching `DO_NOT_REPEAT` entries are not retried without genuinely new distinguishing evidence.

The reference also enforces the current scope rule: other repositories/implementations are not precedent for the StegVerse-002 experiment and may be consulted only for a deliberately new approach after experiment-local evidence establishes a new failure.


## Current SV002 rerun invocation truth

For `STEGVERSE-002-EXPERIMENT-RERUN-001`, the experiment-owned current ingress is the ACTIVE `stegverse-002.self-characterization` service plus the existing organization-kernel InTr carrier/federation publication and consumption path. Repository commits and GitHub Actions are not that federation mesh and do not prove runtime ingress.

The legacy `resident_executor.py` references to `resident-runtime/control/sv002-sdk-query.request.json` and `resident-runtime/run_sv002_self_characterization_roundtrip.py` are stale on current main because both referenced files are absent. They must not be restored as a substitute invocation path without genuinely new experiment-local evidence. The mandatory duplicate-attempt rules remain in `docs/STEGVERSE_002_EXPERIMENT_ATTEMPT_REFERENCE.md`.

Authentic `REQUEST_BOUND`, principal execution, and same-execution reconstruction remain unobserved until the frozen request is consumed through the existing live federation edge.


## Rerun callable publisher binding

`resident-runtime/invoke_sv002_experiment_rerun.py` is the machine binding for `STEGVERSE-002-EXPERIMENT-RERUN-001`. It does not implement a new transport or runtime. It binds the frozen `REQUEST_SELF_CHARACTERIZATION` request to the existing organization-kernel carrier/federation publisher and fails closed outside an already-configured shared gateway or same-host federation mesh.

The binding is exactly-once: one deterministic packet is bound to one retained carrier frame, and retries reuse that same frame. GitHub/CI execution is prohibited and cannot establish `REQUEST_BOUND`.


## SV002 rerun resident-evidence observation boundary — 2026-09-18

For `STEGVERSE-002-EXPERIMENT-RERUN-001` / COSV `50000000107000`, the callable/executor repair remains source-complete, but runtime progress is not promoted from source state. The rerun binding writes `RERUN_REQUEST_BOUND.json` and `RERUN_REQUEST_SUBMISSION.json` under the resident self-characterization state root, while the resident executor writes `resident-runtime/state/resident-executor.latest.json`.

A bounded reconciliation on 2026-09-18 found no existing experiment-owned authoritative read surface available to this conversation that exposes those resident-local artifacts. Standing-device/remote-device rediscovery was not used because it is prohibited by the experiment attempt map. Repository absence is not interpreted as resident-local absence or execution failure. `REQUEST_BOUND` and every downstream runtime predicate therefore remain unclaimed until the authentic resident bytes are observed and same-execution correlated.


## SV002 established-native resident read-capability result — 2026-09-18

A bounded check of the already-established StegVerse-002 native architecture found no authoritative reader for the rerun's resident-local evidence files. The existing `sv002-self-characterization` Universal InTr profile is request/materialization transport, while `sv002-public-observe` is a separate Site/public-observation projection and is not used for this continuation. The native StegOS host source contains no binding to `RERUN_REQUEST_BOUND.json`, `RERUN_REQUEST_SUBMISSION.json`, or `resident-executor.latest.json`.

No new read endpoint, bridge, listener, wrapper, device dependency, Site path, workflow runtime, or second request was created. `REQUEST_BOUND` remains unclaimed because the authentic resident bytes remain unobserved; repository/source absence is not treated as resident-local absence.


## SV002 no-new-evidence checkpoint — 2026-09-18

After the established resident-read observation boundary was merged, the repositories already participating in the rerun path were checked only for newer changes capable of exposing an authoritative resident-state surface. None exists: StegVerse-002/.github remains at the observation-boundary main, micro-node-runtime has no newer rerun change, and current StegOS head predates that boundary.

Accordingly the prior result remains controlling without another discovery sweep. Authentic `RERUN_REQUEST_BOUND.json`, `RERUN_REQUEST_SUBMISSION.json`, and the same-execution resident-executor result remain unobserved; `REQUEST_BOUND` and all downstream transitions remain unclaimed. No runtime absence is inferred.


## SV002 Master Records receipt-tail result — 2026-09-18

Direct review of Master Records SV002 receipt/custody surfaces confirms that the current rerun has not reached Master Records at all. There is no current Goal/COSV receipt, no current-rerun `SV002-RUN-*`, no custody intake, and no reconstruction receipt. The Master Records endpoint only accepts the complete canonical principal artifact set after a qualifying run exists.

The exact current-rerun failure/observation boundary is therefore `REQUEST_BOUND`: the source-level callable/executor binding exists, but no authentic `RERUN_REQUEST_BOUND.json` runtime receipt has been retained/observed. Master Records reconstruction is not failing; it has not been entered. Historical browser/infrastructure receipts remain separate and non-admissible for this rerun.


## SV002 REQUEST_BOUND evidence-loss repair — 2026-09-18

The existing rerun callable writes `RERUN_REQUEST_BOUND.json` before federation publication, but a later publication failure previously caused the callable to report `request_bound_claimed=false`, and the resident executor then discarded that structured nonzero child result. This could erase the distinction between “callable never bound the request” and “request was bound but publication failed.”

The bounded repair preserves validated request-bound identity in the existing callable result and existing `resident-executor.latest.json` heartbeat without creating another request, runtime, transport, listener, scheduler, reader, Site path, device prerequisite, or authority surface. Authentic runtime evidence is still required before `REQUEST_BOUND` can be promoted.


## SV002 REQUEST_BOUND canonical Master Records custody — 2026-09-18

Receipt-chain review identified a concrete post-binding evidence defect for `STEGVERSE-002-EXPERIMENT-RERUN-001`. The deterministic rerun packet is `SV002-RERUN-C796D0BFD181CEC5D99E4C23` with manifest SHA-256 `29222a589eb4c2958d2787743e266f067ee07e1373c51f60b553f1f359789828`. Neither identity appears in canonical Master Records custody.

The ecosystem-wide custody invariant requires every observed governed state transition to emit a canonical state receipt and submit it to Master Records. The rerun callable previously persisted `RERUN_REQUEST_BOUND.json` locally but did not submit that `REQUEST_BOUND` transition through the existing canonical state-transition custody client.

The callable now reuses `StegVerse-Labs/.github/workers/canonical_state_transition_custody.py`, writes the exact canonical REQUEST_BOUND state receipt once, requires Master Records `RECORDED` plus `reconstruction_status=PASS`, retains the returned custody identity, and only then proceeds to the existing federation publication edge. If the canonical custody client or authoritative Master Records surface is unavailable, the rerun fails closed before federation submission. No second request, runtime, scheduler, listener, bridge, Site path, custody store, transition authority, or execution authority is introduced.
