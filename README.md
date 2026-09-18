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
