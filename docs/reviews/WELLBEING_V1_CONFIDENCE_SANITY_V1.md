# Wellbeing V1 Confidence Sanity V1

## Problem

UI showed Confidence 98 with PARTIAL · 5 days — contradictory.

## V1.1 epistemic confidence

Components:

1. Day coverage (`sample / window_days`)
2. Domain coverage (happiness/stress/energy/productivity/sleep/gym)
3. Data-sufficiency factor (COLD_START/PARTIAL/ADEQUATE/RICH)
4. Calibration factor (uncalibrated → ×0.85)
5. Sample maturity cap:

| Days | Cap |
|---|---|
| 1–2 | 25 |
| 3–6 | 45 |
| 7–13 | 60 |
| 14–29 | 75 |
| 30+ | 100 |

6. Extreme-score low-evidence dampener (×0.7) when H/S ≤5 or ≥95 under thin data

## Display contract

- `confidence` field = epistemic score (what LifeOS shows)
- `features.agency_score` = productivity/energy/gym composite
- `features.calibration_status` = `uncalibrated` until feedback campaign matures

## Live result (5-day PARTIAL)

Confidence **45.0** (= maturity cap), band Low/Medium boundary — honest vs PARTIAL.
