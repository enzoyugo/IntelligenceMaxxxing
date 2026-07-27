# Trading Contextual Family Executable Freeze V1

## Status

TMX shadow campaign: `SHADOW_PROTOCOL_ACTIVE_COLLECTING_EVIDENCE`

Candidate: `IM_CONTEXT_FAMILY` as **`VALID_CONTEXTUAL_NEAR_MISS`** only.

## Freeze

- Artifact: `IM_CONTEXT_FAMILY_EXECUTABLE_ARTIFACT_V1`
- Canonical serialization: IEEE-754 hex floats, sorted keys, no volatile timestamps
- Golden vectors: 100% pass (TMX)
- Cross-process hash: stable across 3 processes
- Policy IM **1.0.0** / M2 Bundle **1.0.0**: **unchanged**

## Protocol registration

Protocol hash and `shadow_start_utc` are registered in TMX  
`data/processed/research/trusted_contextual_family_multi_lane_shadow_v1/`.

This document records IM acknowledgment of the research-only freeze. No live assessment binding.

## Fail-closed

Model/registry/feature-order drift → FAMILY decisions ABSTAIN; do not promote; do not alter Policy.
