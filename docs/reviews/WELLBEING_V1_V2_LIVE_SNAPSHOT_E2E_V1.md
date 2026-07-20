# Wellbeing V1/V2 Live Snapshot E2E V1

**Date:** 2026-07-20  
**Engine HEAD (entry):** `6cbc5a4`  
**Marker:** `E2E_WELLBEING_ACTIVATION_2026`

## Observations (sample)

| Day | Observation ID | Global position |
|---|---|---|
| 2026-07-16 | `obs_96513771816344a495e4544dc1683500` | 10 |
| 2026-07-17 | `obs_b337648580e0467ca981158cc145a12d` | 11 |
| 2026-07-18 | `obs_8c9957ca48404158a3c03706b9514dd5` | 12 |
| 2026-07-19 | `obs_4276e5fe55a9490a9535f48e40953273` | 13 |
| 2026-07-20 | `obs_0b9f539f77b5465f8def0bb27cef8542` | 14 |

Idempotent replay of last key: `replayed=true`, same `observation_id`.

## V1 ACTIVE

- Snapshot (smoke): `wbs_3f12c3be74644594a606ddee24ff2424`
- Formula: `wellbeing_v1@1.0`
- Status: **ACTIVE**
- Sample live scores: happiness/stress/confidence returned with `data_sufficiency=PARTIAL`

## V2 SHADOW

- Snapshot (smoke): `wbs_8d940cd96d6141d7a5d9117409d7e642`
- Formula: `wellbeing_v2@2.0.0`
- Status: **SHADOW**
- Input fingerprint: `a65ccf2773d2a2d22c3181bb1f56624c`

## Shadow compare

Returns `v1`, `v2`, `divergences` (happiness/stress/confidence deltas). V2 not promoted.

## Reproducibility

Same cutoff + formula yields stable fingerprints for V2; new snapshot rows are append-only (new IDs on recompute, originals retained).

## Cleanup

Ledger observations retained (no silent delete). Marker used only in local ids / idempotency keys.
