# StegVerse-002 Self-Characterization Version Domains

Status: ACTIVE PRE-T0 CONTROL
Experiment: STEGVERSE-002-SELF-CHARACTERIZATION-001

## Version domains

The experiment condition and its implementation/evaluation surfaces use separate version domains.

```text
experiment condition: v0.3 — FROZEN / OPERATIVE FOR T0
implementation: v0.8 — EVOLVING PRE-T0
external evaluation: independent revision stream
expanded protocol document: non-operative unless separately adopted
```

The frozen v0.3 condition controls the subject-visible experiment. Implementation revisions may improve execution correctness, receipt capture, reconstruction, custody routing, observation projection, verification, and fail-closed behavior without creating a new experiment-condition version.

A new experiment-condition version is required if an implementation change alters any principal-visible treatment variable, including:
- initial objective or system interface;
- discoverable/readable resource content or reachability;
- search semantics or ordering in a way that changes the discovery condition;
- permitted action vocabulary or reachable external action;
- stopping semantics;
- subject identity information exposed to the principal;
- frozen capability-snapshot content;
- other subject-visible knowledge-policy constraints.

Implementation changes that remain outside the principal-visible condition include:
- worker version compatibility;
- exact verifier pin/execution semantics;
- receipt materialization/routing;
- replay/reconstruction integrity checks;
- hierarchical ledger aggregation;
- public-observer projection completeness;
- viewer-side verification metadata;
- CI and fail-closed validation.

## Operative declaration

For STEGVERSE-002-SELF-CHARACTERIZATION-001 at T0:

```text
operative experiment condition = v0.3
frozen condition mutated by implementation revisions = false
v0.5 expanded protocol document operative as scoring rubric = false unless separately declared
implementation may advance beyond v0.3 = true
```

Implementation revision labels do not supersede or rewrite the frozen v0.3 experiment artifacts.

## Claim discipline

Source/implementation readiness is distinct from:
- resident runtime identity observed;
- authentic principal execution;
- Master Records reconstruction/custody;
- public observation readiness;
- viewer-verifiable fidelity;
- release/activation.

Authority effect: NONE.


## v0.8 implementation note — 2026-09-01

Implementation v0.8 adds only evidence/custody plumbing outside the frozen principal-visible v0.3 condition:
- canonical self-characterization artifact-set publication to Master Records;
- dedicated Master Records custody/reconstruction intake;
- explicit Master Records custody receipt sourcing for public observation;
- frozen v0.3 contract binding correction in the org execution surface.

No principal-visible input, resource, search behavior, action vocabulary, or stopping condition is changed.
