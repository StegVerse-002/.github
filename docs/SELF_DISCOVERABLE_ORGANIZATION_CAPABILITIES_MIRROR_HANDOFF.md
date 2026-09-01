# StegVerse-002 Self-Discoverable Organization Capabilities Mirror Handoff

Status: SOURCE_INSTALLED_VALIDATION_PENDING_HOSTED_OBSERVATION
Updated: 2026-09-01

## Goal

Expose the capabilities developed across the StegVerse-002 organization to the StegVerse-002 principal as discoverable organization-local resources without prescribing that any capability constitutes entity identity, is relevant to self-characterization, or must be used.

## Canonical topology

```text
StegVerse-002/micro-node-runtime
        ↕
StegVerse-002/.github
        ↕
organization capability discovery
        ↕
repo-owned capabilities
```

The principal runtime does not hard-code sibling repositories as constitutive components.

## Repository-owned descriptors

All nine StegVerse-002 repositories own:

`.stegverse/capability/descriptor.json`

Descriptors state capability role and authority boundaries only. They explicitly do not prescribe identity constitution or self-characterization relevance.

## Organization discovery

Canonical registry/projection:

- `org-boundary/registry/capabilities.json`
- `org-boundary/registry/capability-descriptors.snapshot.json`

Discovery endpoint:

`stegverse-002.capability-discovery`

Operations:

- `LIST_CAPABILITIES`
- `SEARCH_CAPABILITIES`
- `READ_CAPABILITY_DESCRIPTOR`

Authority effect: `NONE_DISCOVERY_ONLY`.

## Self-characterization experiment

The principal experiment has not executed. v0.1/v0.2 artifacts remain historical and immutable.

Current pre-execution revision:

- `EXPERIMENT_CONTRACT.v0.3.json`
- `ENVIRONMENT_AVAILABILITY_MANIFEST.v0.2.json`
- `EXPERIMENT_MANIFEST.v0.3.json`
- `ORGANIZATION_CAPABILITY_SNAPSHOT.v0.1.json`

Organization-local capability resources are `AVAILABLE_NOT_INJECTED`.

The initial objective contains no sibling list and no prescribed ontology. The model may independently surface the organization capability snapshot through ordinary search/read actions.

Evidence discipline:

```text
AVAILABLE != DISCOVERABLE != ACCESSED != REFERENCED != USED != DERIVED
```

## Relationship to Admissible-Existence

This does not inject Admissible-Existence doctrine or AID into the principal. The existing construction provenance remains separately available. TT/RTG/GTG/AE remain pinned formal resources under their existing availability semantics.

A principal may independently discover organization-local capabilities, construction provenance, and available formal resources and determine what—if anything—those facts imply for its self-characterization.

## Documentation authority

This handoff plus the current repo-owned capability descriptors supersede conflicting historical topology/lifecycle prose in older documents for purposes of current organization capability relationships.

Historical receipts, provenance, experiment artifacts, and prior architecture documents remain evidence and are not rewritten merely to erase history.

## Validation state

Focused tests are installed in:

- `StegVerse-002/.github/tests/test_capability_discovery_surface.py`
- `StegVerse-002/micro-node-runtime/tests/test_organization_capability_discovery.py`

Validation workflows are installed, but hosted workflow execution has not been observed through the available GitHub run/status surfaces as of this update. Source installation must not be represented as authentic resident runtime discovery or principal experiment execution.

## Runtime nonclaims

Not established by this source integration:

- authentic resident capability-discovery request;
- principal access/use of any sibling capability;
- principal conclusion that any sibling capability constitutes itself;
- principal discovery/use of Admissible-Existence as a result of sibling discovery;
- authentic self-characterization execution;
- Master Records reconstruction of such an execution.
