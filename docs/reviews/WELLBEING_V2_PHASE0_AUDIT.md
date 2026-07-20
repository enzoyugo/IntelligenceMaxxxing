# Wellbeing V2 Phase 0 Audit

**Date:** 2026-07-20  
**Engine HEAD:** `c432a51`  
**LifeOS HEAD:** `f4a9ef2`  
**Constitution:** PASS  

## V1 found (implemented)

| Component | Location | Status |
|---|---|---|
| Formula | `domain_packs/life/wellbeing_v1.py` | ACTIVE `wellbeing_v1@1.0` |
| API | `/api/v1/wellbeing/*` | current/history/explanation/formula/feedback |
| Tables | migration `0006_wellbeing_v1` | snapshots, baselines, feedback, formula versions |
| LifeOS adapter | `features/wellbeing/*` | BFF proxy, cache, strip — no local formula |
| Tests | unit + integration wellbeing; LifeOS contract | PASS |

## V1 gaps vs V2 prompt

1. Happiness ≈ composite of happiness/energy/sleep — not hierarchical sub-scores (affect, agency, connection, …).
2. Stress ≈ reported stress + alcohol/sleep amp — no acute/chronic/anticipatory accumulation model.
3. Confidence ≈ data sufficiency enum proxy — not multi-component calibrated confidence.
4. No separate happiness_confidence / stress_confidence.
5. No robust personal baseline (median/MAD) normalization.
6. No per-feature decay / half-life registry.
7. No double-counting controls beyond informal weighting.
8. No change-detection states / lead-time eval harness.
9. No shadow mode or formula registry lifecycle.
10. No model cards / feature registry docs.
11. No plausible ranges / uncertainty.
12. No temporal validation / ablation / leakage suites.
13. No recalculation audit path for historical snapshots.

## Decision

Keep V1 as **ACTIVE** production default. Implement `wellbeing_v2@2.0.0` as **SHADOW** with full layered pipeline; promote only via explicit gates.
