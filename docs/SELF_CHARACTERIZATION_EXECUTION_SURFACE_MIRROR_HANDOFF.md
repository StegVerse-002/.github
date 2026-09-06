# Organization AI Self-Characterization Execution Surface Mirror Handoff

Status: ACTIVE
Updated: 2026-09-06
Organization: StegVerse-002
Repository: StegVerse-002/.github

## Source of truth

This handoff governs the organization-local self-characterization execution surface in this repository. The frozen StegVerse-002 experiment contract remains owned by `StegVerse-002/micro-node-runtime`.

## Ownership rule

A self-characterization execution surface is an organizational resident capability and belongs in the target entity's own `<ORG>/.github`.

Cross-organization communication arrives through the canonical organization boundaries:

```text
StegVerse-org/StegVerse-SDK
-> StegVerse-org/.github egress
-> StegVerse-002/.github ingress
-> stegverse-002.self-characterization
-> StegVerse-002/micro-node-runtime principal
-> StegVerse-002/.github egress
-> Master Records
```

The source organization may request self-characterization. It may not execute the target organization's principal.

## Reusable surface

Canonical reusable implementation:
- `resident-runtime/self_characterization_surface.py`
- per-entity bindings under `resident-runtime/self-characterization/*.json`

The historical/resident implementation remains valid source, but its Python/local-repository subprocess path is not the final `CURRENT_USER_IPHONE` execution path because the user-operated topology may not require another machine.

Invariant:
- execution owner = `<ENTITY_ORG>/.github`;
- principal repository organization = `<ENTITY_ORG>`;
- cross-org principal execution = prohibited;
- ingress/egress = organization Interlock/InTr boundary;
- Master Records custody/reconstruction = required;
- model output does not self-grant authority;
- applicable Transition Elements resolve effects.

## StegVerse-002 binding

`resident-runtime/self-characterization/stegverse-002.json` binds the reusable surface to:
- entity: `StegVerse-002`;
- service: `stegverse-002.self-characterization`;
- principal: `StegVerse-002/micro-node-runtime`;
- operation: `REQUEST_SELF_CHARACTERIZATION`.

The frozen principal objective, resource policy, runtime identity verification, and experiment artifacts remain defined by the micro-node-runtime experiment contract and launcher. This org surface does not rewrite them.

## Master Records observation rule

StegVerse-002 is the event source and receipt issuer. Master Records is the canonical custody/reconstruction surface. Other organizations may consume Master Records-derived evidence but must not maintain a competing privileged observation history of StegVerse-002 internal state.

## Boundary receipt custody binding — 2026-09-01

The organization boundary persists `ORG_BOUNDARY_RECEIPTS.json` into the same principal evidence root after the self-characterization endpoint returns. The bundle hash-binds the exact ingress packet, manifest hash, payload hash, and the five org-boundary transitions:

```text
INGRESS_ACCEPTED
-> DISPATCHED
-> CONSUMED
-> RESULT_BOUND
-> EGRESS_EMITTED
```

Master Records reconstruction is required to validate this bundle together with S0, principal transition receipts, and final artifacts.

## Federation ingress/return dispatch — 2026-09-01

The organization kernel and shared-Gateway cycle dispatch registered internal endpoint adapters. For self-characterization the operational route is:

```text
federation frame
-> StegVerse-002 org kernel
-> org-boundary process_boundary
-> stegverse-002.self-characterization
-> principal
-> org-boundary receipt bundle
-> exact endpoint response packet
-> originating SDK service
```

The response packet carries `response_to_packet_id` and therefore cannot trigger a response loop. A repeated identical request reaches the exactly-once guard and returns the preserved result without rerunning the principal.

## Live boundary progression correction — 2026-09-01

The organization boundary appends canonical boundary events at the time each boundary transition occurs:

```text
INGRESS_ACCEPTED
DISPATCHED
<principal executes>
CONSUMED
RESULT_BOUND
EGRESS_EMITTED
```

The live append-only surface is `ORG_BOUNDARY_RECEIPTS.live.jsonl`. The terminal `ORG_BOUNDARY_RECEIPTS.json` bundle is v0.2 and preserves per-event `observed_at` plus the endpoint application disposition. Exactly-once replay reuses the already-frozen bundle rather than reminting a second history.

Transport consumption and principal completion remain distinct fields. A returned fail-closed/partial endpoint result may be transported and bound without being promoted to successful experiment completion.

## Version-domain control — 2026-09-01

Canonical version-domain control is explicit in `docs/SV002_EXPERIMENT_VERSION_DOMAINS.md`.

```text
experiment condition: v0.3 FROZEN / OPERATIVE
implementation: evolving
external evaluation: separate revision stream
expanded protocol document: NON-OPERATIVE unless separately adopted
```

Implementation revisions may repair execution, reconstruction, custody routing, observer projection, viewer verification, fail-closed behavior, and physical-substrate portability without changing the experiment-condition version. Any change to the principal-visible objective, system interface, discovery/read surface, search semantics that alter the discovery condition, permitted actions, stopping semantics, subject-visible identity information, or frozen snapshot content requires a new experiment-condition version.

## Canonical Master Records custody binding — 2026-09-01

`resident-runtime/submit_sv002_self_characterization_to_master_records.py` requires the complete canonical v0.3 artifact set, validates experiment/run binding and completed principal state, binds exact artifact names/sizes/SHA-256 values/artifact-set hash/organization-ledger root, publishes the deterministic InTr/federation packet to `master-records.sv002-self-characterization-reconstruction`, writes `MASTER_RECORDS_CUSTODY_HANDOFF.json`, is exactly-once, and grants no authority.

Publication is not reconstruction success; Master Records must consume the packet, establish custody, and produce reconstruction PASS separately.

## Resident pre-T0 readiness evaluator — 2026-09-01

`resident-runtime/evaluate_sv002_pre_t0_readiness.py` remains a resident-only rehearsal/readiness evaluator. It never substitutes for authentic principal execution.

Runtime readiness requires:
- explicit `stegverse.resident-node-eligibility/v1` evidence with declared/eligible/StegVerse-owned-or-federated state;
- live runtime identity verification of the qualifying non-reference resident-loopback principal model/process;
- hosted-environment guards clear;
- empty canonical principal state root.

The readiness receipt declares `principal_executed=false` and `authority_effect=NONE`.

## v0.3 T0 snapshot release state

The frozen experiment condition is bound to `releases/SV002_SELF_CHARACTERIZATION_V0.3_T0_RELEASE_MANIFEST.json`. The ten snapshot tags/releases were reconciled to `EXPERIMENT_SNAPSHOT_RELEASE`; this is evidence identity only and is not a product release, principal-execution claim, `SYSTEM_AI_ACTIVE` claim, custody claim, reconstruction PASS, runtime activation, deployment, admissibility, or Guardian-enforcement claim.

## Native current-iPhone organization execution envelope v1 — released source / historical only

Issue #23 / PR #24 released `stegverse.sv002-native-org-execution-envelope/v1`, preserving `StegVerse-002/.github` as target principal execution owner.

```text
validated PR head: 44472f699fb820748336731bfd161a31f6f97276
merge: 94a14a67c1b7044aaac4381ea5be0762e505c617
release reconciliation: 1125ac9e75ab725df60ce8559dc6683e5f2ec6ac
Org Boundary Execution validation: 34014887434 SUCCESS
```

v1 remains retained for provenance. It binds the ingress packet/manifest, frozen experiment semantics, existing resident request/task, current-iPhone/native principal substrate, exact target model/package/resource identities, TV/TVC, WorkerCoordinator/InTr requirements, Master Records requirements, and no authority transfer. However, it does not cryptographically bind the target organization's live `INGRESS_ACCEPTED` receipt. No physical v1 envelope was materialized. v1 MUST NOT be selected for a new native execution.

## Native current-iPhone organization execution envelope v1.1 — issue #26

Issue #26 advances only the portable envelope implementation version; frozen experiment condition v0.3 is unchanged.

Current consumable schema:

```text
stegverse.sv002-native-org-execution-envelope/v1.1
```

Implementation surfaces:

```text
schemas/sv002-native-org-execution-envelope-v1.1.schema.json
resident-runtime/validate_sv002_native_org_execution_envelope_v1_1.py
tests/test_sv002_native_org_execution_envelope_v1_1.py
```

v1.1 adds exact target-org ingress-admission binding before any physical consumer may accept the envelope. `org-boundary/runtime/process_boundary.py` emits `INGRESS_ACCEPTED` before dispatch using this canonical receipt subject:

```text
{
  packet_id,
  service_id: stegverse-002.self-characterization,
  payload_hash,
  kind: INGRESS_ACCEPTED,
  previous_receipt_id: null
}
```

The target boundary computes:

```text
evidence_hash = sha256(canonical(receipt subject))
receipt_id = ingress_accepted- + first 24 hex characters of evidence_hash
```

v1.1 therefore requires:
- `ingress.payload_sha256`;
- `ingress_admission.kind=INGRESS_ACCEPTED`;
- the exact deterministic `receipt_id`;
- the exact deterministic `evidence_hash`;
- `subject=stegverse-002.self-characterization`;
- `previous_receipt_id=null`.

The v1.1 binder accepts a supplied live target-org ingress receipt and verifies these values, including a non-empty `observed_at`. It does not mint or infer an admission receipt merely from ingress fields. Any packet/service/payload-hash or receipt identity drift fails closed.

All v1 execution boundaries remain unchanged:

```text
resident request: RESIDENT-EXEC-SV002-ORG-RUNTIME-ACTIVATION-001
task: SHWP-SV002-ORG-RUNTIME-ACTIVATION-001
execution owner: StegVerse-002/.github
physical substrate: CURRENT_USER_IPHONE
principal substrate: RESIDENT_LOOPBACK_NATIVE_IOS
principal owner: StegVerse-002/micro-node-runtime
credential authority: TV/TVC
GitHub runtime authority: NONE
second machine required: false
hosted runtime allowed: false
runtime network resource fetch allowed: false
WorkerCoordinator required: true
InTr admission required: true
Master Records required: true
authority transfer: false
authority effect: NONE_EXECUTION_REQUEST_ONLY
```

The exact materialized resource-bundle SHA-256 remains a required late binding and MUST NOT be invented before the frozen TT/RTG/GTG/AE + organization-capability bundle bytes actually exist.

## README completeness — issue #26

Material execution-admission semantics changed. README is updated in the same change to mark v1 historical-only and v1.1 current-consumable. The canonical Org Boundary Execution workflow is also extended to run the v1.1 tests while retaining all pre-existing boundary/reconstruction tests.

## Current runtime truth

```text
native envelope v1 source: COMPLETE / RELEASED / HISTORICAL_ONLY
native envelope v1.1 ingress-bound source: IMPLEMENTED / VALIDATION PENDING
real frozen resource bundle bytes: NOT OBSERVED
native v1.1 execution envelope with real bundle SHA: NOT MATERIALIZED
native envelope delivered to current iPhone: NOT OBSERVED
physical native model/package/bundle installed: NOT OBSERVED
WorkerCoordinator checkout for this task: NOT OBSERVED IN THIS SESSION
live runtime identity: NOT OBSERVED
resident request consumed: NOT OBSERVED
principal execution: NOT OBSERVED
org-boundary downstream terminal result: NOT OBSERVED
Master Records reconstruction PASS: NOT OBSERVED
SYSTEM_AI_ACTIVE: false
```

Source installation, CI, merge, release, heartbeat progression, or static envelope validation does not establish any runtime predicate.

## Next action

Validate and release issue #26. Only then implement the matching StegOS consumer against v1.1, requiring the real resource-bundle SHA and existing WorkerCoordinator authority evidence without creating a second runtime, listener, request, principal identity, scheduler, WorkerCoordinator, credential path, or synthetic target-org admission.
