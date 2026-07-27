# Contextual Family Inference Artifact V1

## Schema

`IM_CONTEXT_FAMILY_EXECUTABLE_ARTIFACT_V1`

Per family:

- feature_order (locked)
- coef / intercept / means / stds
- missing-value policy
- threshold + semantics
- canonical_model_hash (IEEE hex serialization)
- frozen score percentile map + score_scale (ranking only; no retune)

## Inference rules

1. Load artifact; recompute package hash; fail-closed on mismatch.
2. Route by strategy/family ID.
3. Score → TAKE/SKIP/ABSTAIN with frozen thresholds.
4. Attach within-family percentile and normalized margin for ranking diagnostics.
5. Never accept outcome fields in the inference payload.
