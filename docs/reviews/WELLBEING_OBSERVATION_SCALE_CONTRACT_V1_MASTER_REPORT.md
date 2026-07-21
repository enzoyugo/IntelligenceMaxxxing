# WELLBEING OBSERVATION SCALE CONTRACT V1 — Master Report

## Verdict

**WELLBEING_OBSERVATION_SCALE_CONTRACT_V1_PASS_WITH_WARNINGS**

## Contract summary

| Item | Value |
|------|-------|
| Old scale behavior | Magnitude heuristic `raw <= 10 → 1_10 else 0_100` in `wellbeing_v1@1.1` |
| New scale contract | Explicit per-field scale or known legacy adapter only |
| Event version | `life.daily_check_in.completed.v1` (compatible extension; no silent semantic change) |
| Measurement contract version | `wellbeing_measurements_v1` |
| Normalization version | `canonical_0_100_v1` |

### Fields covered

`happiness`, `stress`, `energy`, `productivity`

### Scales supported

`0_100`, `1_10` (closed enum)

### Resolution precedence

1. Explicit field → 2. Contract version → 3. Legacy adapter → 4. Error / AMBIGUOUS

### Legacy policies

- LifeOS Daily Flow URI / source_system → `1_10`
- Fixture tags → declared scale
- Ambiguous bare payloads → exclude + confidence penalty (no magnitude guess)

### Ambiguous-event policy

Do not guess; mark AMBIGUOUS; exclude from scores; cap confidence.

### Boundary values

| Input | Result |
|-------|--------|
| 5 / `0_100` | 5 (live E2E avg_h=5.0) |
| 10 / `0_100` | 10 (live E2E avg_s=10.0) |
| 5 / `1_10` | ≈44.444… |
| 10 / `1_10` | 100 |

### Formula versions

| | |
|--|--|
| V1 old | `1.1` |
| V1 new | `1.2` ACTIVE |
| V2 | `2.1.0` SHADOW (was `2.0.0`) |

### Historical preservation

Prior snapshots retained; new computes create new snapshot IDs with normalization metadata.

### Confidence impact

Legacy / ambiguous / invalid ratios penalize epistemic confidence; ambiguous → confidence ≤ 40.

### E2E observation

`obs_ab746ef9d6c64732990a6e7fc4aaea15` — SCALE_CONTRACT_SMOKE PASS

### Quality

| Gate | Result |
|------|--------|
| Engine pytest | PASS except pre-existing import-boundary failure |
| LifeOS backend pytest | 67 passed |
| LifeOS frontend npm test | 97 passed |
| TypeScript | pass |
| Lint | 0 errors (pre-existing warnings) |
| Live scale smoke | PASS |
| Magnitude inference productive | REMOVED (AST structural test) |

### Warnings

1. Pre-existing constitutional `test_application_layer_has_no_infrastructure_import` still fails (unchanged).
2. Authoritative LifeOS capture scale is **`1_10`** (ValueSlider), not `0_100` as assumed in an earlier sprint narrative — documented in Phase 0 + LifeOS scale report.
3. Full iPhone Daily Flow tap-through not re-run in this session; synthetic 0_100 + code-path emission verified. SDK client installed/reported as **0.4.0** after BFF restart.

### Related docs

- `WELLBEING_OBSERVATION_SCALE_CONTRACT_PHASE0_AUDIT.md`
- `WELLBEING_MEASUREMENT_SCALE_CONTRACT_V1.md`
- `WELLBEING_LEGACY_SCALE_RESOLUTION_AUDIT_V1.md`
- `WELLBEING_CANONICAL_NORMALIZATION_V1.md`
- LifeOS: `LIFEOS_DAILY_FLOW_SCALE_CONTRACT_V1.md`, `LIFEOS_SCALE_CONTRACT_LIVE_E2E_V1.md`
