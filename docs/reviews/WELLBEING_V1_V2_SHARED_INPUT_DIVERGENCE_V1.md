# Wellbeing V1/V2 Shared Input Divergence V1

## Shared cutoff

Both formulas use the same observation scan + trailing window in `WellbeingService.compare_shadow` / `get_current`.

## Post V1.1 live compare (window=14)

| | V1.1 ACTIVE | V2 SHADOW |
|---|---|---|
| Happiness | 69.45 | 66.83 |
| Stress | 38.0 | ~63.5 |
| Confidence | 45.0 | 55.56 |
| Δ H | -2.62 | |
| Δ S | +25.5 | |
| Δ C | +10.56 | |

## Likely drivers

- V1.1 single-pass 0–100 normalize + simple composite vs V2 hierarchical load
- V2 includes schedule domain (missing → reported in missing_data)
- Confidence definitions differ (epistemic maturity vs multi-component)

High |Δ Stress| ≥ 25 → Shadow Lab warning shown in LifeOS. V2 not promoted.
