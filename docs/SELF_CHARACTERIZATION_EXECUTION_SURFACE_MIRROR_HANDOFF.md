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


## Federation ingress/return dispatch — 2026-09-01

The organization kernel and shared-Gateway cycle now dispatch registered internal endpoint adapters rather than rejecting them as non-control services. For the self-characterization lane this makes the operational route:

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

The organization boundary no longer synthesizes the complete self-characterization boundary chain only after the endpoint returns.

For the principal lane it now appends canonical boundary events at the time each boundary transition occurs:

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
