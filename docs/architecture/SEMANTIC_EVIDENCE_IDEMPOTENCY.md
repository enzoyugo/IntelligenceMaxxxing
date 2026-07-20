# Semantic Evidence Idempotency (Stage 3.1)

HTTP `Idempotency-Key` alone is insufficient.

`evidence_fingerprint = sha256(tenant|owner|app|experiment|protocol|phase|cutoff_position|sorted unique source event ids|method|params)`

Unique constraint:

`(tenant_id, owner_id, application_id, experiment_id, phase, evidence_fingerprint)`

Replay with a different Idempotency-Key returns the same evidence/belief IDs with `replayed=true` and creates no new outcome/learning.
