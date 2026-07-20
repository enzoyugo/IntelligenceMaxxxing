# Wellbeing Validation Protocol V2

| Field | Value |
|---|---|
| **Formula** | `wellbeing_v2@2.0.0` |
| **Purpose** | Shadow evaluation and SHADOW → ACTIVE promotion |
| **Production default during validation** | `wellbeing_v1@1.0` ACTIVE |

## Evaluation objective

Demonstrate that V2 **predicts held-out user self-report** at least as well as baselines and V1, without temporal leakage, before replacing V1 as ACTIVE.

Primary metrics:

- MAE(happiness, label_happiness)
- MAE(stress, label_stress)
- Calibration MAE after personal fit (where n ≥ 20)

Secondary metrics:

- Early-warning precision/recall vs user-flagged `inaccurate` / `accurate` feedback
- Contributor stability (rank correlation day-over-day)
- Cold-start MAE (n < 7 days users)

## Baselines

Every evaluation run reports all baselines on identical folds:

| Baseline ID | Definition |
|---|---|
| `constant50` | Always predict 50 for happiness and stress |
| `last_report` | Yesterday's reported happiness/stress from check-in (1–10 → 0–100) |
| `MA7` | 7-day trailing mean of reported happiness/stress |
| `V1` | `compute_wellbeing_v1` output on same window |
| `sleep_only` | Happiness/stress inferred from sleep_hours alone via fixed piecewise map (audit sanity check) |

V2 must beat `V1` and `last_report` on pooled MAE to pass primary gate.

## Expanding-window protocol

For each user with ≥ 30 days of check-ins:

1. **Train/calibrate** on days `[1, t]` (calibration params only when gate permits)
2. **Predict** snapshot for day `t + 1`
3. **Score** against label at `t + 1` (reported happiness/stress)
4. Increment `t` and repeat (expanding window)

Minimum cohort: **5 users** or **500 user-days**, whichever is larger, synthetic fixtures excluded.

## Leakage rules

| ID | Rule |
|---|---|
| L1 | No feature with `occurred_at` after snapshot `period_end` |
| L2 | No label collected before snapshot `period_end + 24h` |
| L3 | Baseline median/MAD at t uses only `[t - 89, t]` inclusive |
| L4 | Accumulated load state resets in ablation runs; no cross-user state |
| L5 | Shadow snapshots excluded from LifeOS default API during evaluation |
| L6 | Feedback rows labeled `synthetic=true` excluded |

Automated test suite: `tests/unit/test_wellbeing_v2_leakage.py` (to be implemented with formula code).

## Ablation requirements

Before promotion, run ablations disabling one component at a time:

- Domain caps off
- Accumulation off (RETENTION = 0)
- Anticipatory horizon off
- Personal calibration off

Document MAE delta; no component removal may increase pooled MAE by > **5%** without documented justification.

## Promotion gates (SHADOW → ACTIVE)

All gates must pass on `main` CI within 30 days of promotion request:

| Gate | Threshold |
|---|---|
| G1 Pooled MAE | V2 happiness MAE ≤ V1 happiness MAE − **2%** relative |
| G2 Pooled MAE | V2 stress MAE ≤ V1 stress MAE − **2%** relative |
| G3 Cold-start | Users with n < 7: V2 MAE ≤ `last_report` MAE |
| G4 Leakage | 100% pass on L1–L6 automated tests |
| G5 Shadow period | ≥ **14 days** production shadow compute with zero formula errors |
| G6 Constitution | `verify_constitution.ps1` PASS; no constitutional doc edits |
| G7 Rollback plan | Documented revert to V1 ACTIVE via formula flag in ≤ 5 minutes |
| G8 API compatibility | LifeOS adapter tests pass with `formula=wellbeing_v2` opt-in |

## Demotion triggers (ACTIVE → SHADOW)

- Pooled MAE regression > **10%** vs validation benchmark over 7 days
- Leakage test failure in production audit
- Critical bug in contributor or confidence computation

Demotion sets `wellbeing_v1` ACTIVE; V2 snapshots retained for audit.

## Reporting

Each validation run emits:

```json
{
  "protocol_version": "2.0.0",
  "run_id": "...",
  "baselines": { "constant50": {}, "V1": {}, "...": {} },
  "v2": { "happiness_mae": 0, "stress_mae": 0 },
  "gates": { "G1": true, "...": true },
  "promotion_eligible": false
}
```

Stored under `docs/reviews/` or CI artifact; not served via public API.

## Version history

| Version | Change |
|---|---|
| 2.0.0 | Initial validation protocol for shadow promotion |
