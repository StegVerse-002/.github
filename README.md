# StegVerse-002 Organization Control Plane

This repository owns StegVerse-002 organization-local discovery, ingress, egress, resident dispatch, organization-ledger, and cross-organization execution-boundary semantics. It does **not** own the frozen principal model/runtime contract, which remains in `StegVerse-002/micro-node-runtime`, and it does not make GitHub Actions an execution authority.

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

`schemas/sv002-native-org-execution-envelope.schema.json` and `resident-runtime/validate_sv002_native_org_execution_envelope.py` define the organization-owned source contract for carrying an already-admitted frozen-v0.3 self-characterization request into the existing native current-iPhone execution seam.

The envelope reuses the existing request and task exactly:

```text
request: RESIDENT-EXEC-SV002-ORG-RUNTIME-ACTIVATION-001
task: SHWP-SV002-ORG-RUNTIME-ACTIVATION-001
```

It binds the admitted ingress packet/manifest, frozen objective and knowledge policy, target-org execution ownership, `CURRENT_USER_IPHONE`, `RESIDENT_LOOPBACK_NATIVE_IOS`, the released target model/package identity, the exact materialized frozen-resource-bundle SHA-256, TV/TVC credentials, required WorkerCoordinator/InTr admission, and required Master Records reconstruction.

It fails closed on request/task substitution, ownership drift, frozen-contract drift, reference-model substitution, hosted or second-machine fallback, runtime network resource fetch, non-TV/TVC credentials, GitHub runtime authority, disabled Master Records requirements, or authority transfer. The envelope has `authority_effect=NONE_EXECUTION_REQUEST_ONLY`; its existence alone grants no execution authority.

The real frozen resource-bundle SHA-256 is intentionally not predeclared in source because the real bundle bytes have not yet been materialized. A valid envelope can only be finalized after those exact bytes exist and are hash-bound.

Source/schema/test success does not prove delivery to the physical iPhone, live runtime identity, resident-request consumption, principal execution, an InTr transition, Master Records reconstruction, or `SYSTEM_AI_ACTIVE`.
