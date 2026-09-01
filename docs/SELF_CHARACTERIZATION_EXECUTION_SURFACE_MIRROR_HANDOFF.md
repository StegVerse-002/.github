# Organization AI Self-Characterization Execution Surface Mirror Handoff

Status: ACTIVE
Updated: 2026-09-01
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

The implementation is intended to be vendored into any organization `.github` and rebound to an AI entity owned by that organization.

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

## Remaining runtime evidence

Source installation does not establish a live request, principal execution, egress, custody, or reconstruction. Those remain evidence transitions.


## Boundary receipt custody binding — 2026-09-01

The organization boundary now persists `ORG_BOUNDARY_RECEIPTS.json` into the same principal evidence root after the self-characterization endpoint returns. The bundle hash-binds the exact ingress packet, manifest hash, payload hash, and the five org-boundary transitions:

```text
INGRESS_ACCEPTED
-> DISPATCHED
-> CONSUMED
-> RESULT_BOUND
-> EGRESS_EMITTED
```

Master Records reconstruction is required to validate this bundle together with S0, principal transition receipts, and final artifacts. This closes the boundary-history gap between the external SDK packet and the principal evidence chain.
