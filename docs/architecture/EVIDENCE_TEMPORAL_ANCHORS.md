# Evidence Temporal Anchors (Stage 3.1)

Pre-registered experiments freeze activation anchors:

- `activation_event_id`
- `activation_global_position`
- `activation_recorded_at`
- `baseline_cutoff` / `prospective_start`

Each evidence evaluation freezes:

- `evidence_cutoff_global_position` (stream head at evaluation start)
- `evidence_cutoff_recorded_at`
- `evaluation_started_at`

## Baseline membership

Requires all of:

1. `occurred_at < baseline_cutoff`
2. `global_position < activation_global_position`
3. `recorded_at <= activation_recorded_at`

Otherwise backfilled rows are excluded as `BACKFILLED_AFTER_ACTIVATION`.

## Prospective membership

Requires post-activation ledger position/time, within evidence cutoff, and
`occurred_at <= evaluation_started_at + 5 minutes`. Future client timestamps are
`OCCURRED_AT_IN_FUTURE`.

## Clock

Runtime uses `SystemClock`. `ControlledTestClock` exists only when `ENGINE_ENV=test`.
