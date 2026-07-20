# Evidence Data Quality Incidents

## Duplicate logical source conflict

Symptom: `critical_data_quality_failure=true`, exclusion `DUPLICATE_SOURCE_CONFLICT`.

Cause: same `lifemaxxxing://daily-check-ins/{id}` with conflicting sleep/productivity/occurred_at.

Action: do not treat as `PROSPECTIVE_SUPPORTED`. Investigate Life outbox dual-submit or edit/replay.

## Future timestamps

Exclusion: `OCCURRED_AT_IN_FUTURE`. Wait for a later evaluation cutoff; do not force-count.

## Backfill after activation

Exclusion: `BACKFILLED_AFTER_ACTIVATION`. Offline sync with old `occurred_at` cannot rewrite baseline.
