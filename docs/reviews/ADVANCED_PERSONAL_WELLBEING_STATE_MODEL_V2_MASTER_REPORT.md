# ADVANCED PERSONAL WELLBEING STATE MODEL V2 — MASTER REPORT

**Date:** 2026-07-20

---

## 1. Executive verdict

```text
ADVANCED_PERSONAL_WELLBEING_STATE_MODEL_V2_SHADOW_ONLY
```

V2 is fully implemented as **SHADOW** (`wellbeing_v2@2.0.0`). V1 remains **ACTIVE** production default. Historical V1 snapshots are preserved (additive migration `0007`). Promotion to ACTIVE requires live calibration labels and gate suite per validation protocol — not claimed here.

Also qualifies as `PASS_WITH_WARNINGS` on engineering completeness of the shadow pipeline (tests, docs, API, LifeOS adapter).

---

## 2. Estado previo encontrado

| Item | State |
|---|---|
| Engine HEAD at audit | `c432a51` (wellbeing_v1) |
| LifeOS HEAD at audit | `f4a9ef2` |
| V1 formula | ACTIVE, hierarchical-lite composites |
| Docs/wellbeing | absent → created |
| Shadow mode | absent → added |

---

## 3. Fórmula V1 auditada

`wellbeing_v1@1.0`: Happiness from reported happiness + energy + sleep; Stress from reported stress + alcohol/short sleep; Confidence ≈ data sufficiency. Happiness ≠ 100−Stress. No acute/chronic split, no MAD baselines, no multi-component confidence.

---

## 4. Problemas encontrados en V1

See `docs/reviews/WELLBEING_V2_PHASE0_AUDIT.md` (13 gaps). Primary: shallow Confidence, no accumulation, no sub-score hierarchy, no shadow lifecycle.

---

## 5. Arquitectura V2

Layered pipeline in `domain_packs/life/wellbeing_v2/`:

observations → features/baselines → happiness / stress / confidence → change detection → attribution → recommendations (ANALYZE/EXPLAIN) → snapshot.

Status: **SHADOW**. No LLM in score path.

---

## 6–8. Definiciones formales

Documented in:

- `docs/wellbeing/HAPPINESS_SCORE_V2_MODEL_CARD.md`
- `docs/wellbeing/STRESS_LOAD_V2_MODEL_CARD.md`
- `docs/wellbeing/CONFIDENCE_SCORE_V2_MODEL_CARD.md`
- `docs/wellbeing/WELLBEING_STATE_MODEL_V2_SPEC.md`

---

## 9. Catálogo de features

`docs/wellbeing/WELLBEING_FEATURE_REGISTRY_V2.md` + `registry.py` DECAYS. LifeOS-real sources only (check-ins, workouts, meetings attrs). Forbidden: HRV, cortisol, phone content, etc.

---

## 10–12. Pesos / interacciones / decays

Canonical in `wellbeing_v2/registry.py`. Happiness eustress interaction (high affect+vitality reduces friction penalty). Sleep×workload interaction capped. Feature half-lives in DECAYS.

---

## 13–16. Baselines / cold-start / missing / double-counting

Robust z + absolute blend when MAD low; maturity NO_BASELINE→STABLE. Cold-start caps scores and confidence. Missing domains listed; no silent mood imputation. Domain caps + physiological sleep cap + hierarchical sub-scores.

---

## 17–18. Uncertainty / Confidence calibration

Plausible ranges from confidence width. Calibration status **UNCALIBRATED** until ≥20 posterior labels (`CALIBRATION_MIN_LABELS`). Separate happiness_confidence / stress_confidence / overall.

---

## 19–21. Change detection / attribution / recommendations

`change_detection.py` states; contributors with effect_points; recommendations ANALYZE/EXPLAIN with urgency capped by confidence (no HIGH below threshold).

---

## 22–26. Simulaciones / baselines / temporal / leakage / ablation

Scenarios in `scenarios.py`; tests cover V1 compare, constant-50, leave-future-out leakage, subjective ablation. Expanding-window live backtest on user data = follow-up (warning).

---

## 27–28. Performance / Privacy

In-process deterministic compute over personal observation pages — suitable for Today refresh. Scores treated as private; UI language non-clinical.

---

## 29–30. API / Migrations

- `GET /api/v1/wellbeing/current?formula_id=wellbeing_v1|wellbeing_v2`
- `GET /api/v1/wellbeing/shadow/compare`
- Migration `0007_wellbeing_v2` additive columns on snapshots + formula status

---

## 31. Tests

| Suite | Result |
|---|---|
| V1 unit + integration | PASS |
| V2 unit scenarios | PASS |
| V2 validation (leakage/ablation) | PASS |
| Constitution verify | PASS |
| LifeOS npm contract | run at commit time |

---

## 32. Shadow results

Synthetic scenarios demonstrate: Happiness↑Stress↑ (deadline), Happiness↓Stress↓ (empty), recovery path, low confidence on sparse calendar. Live user shadow divergence table = next step with Engine+BFF running.

---

## 33. Promotion recommendation

**Do not activate V2** until: ≥20 feedback labels, confidence–error monotonicity check, live shadow MAE ≤ V1 on held-out weeks, false-alarm rate acceptable.

---

## 34. Warnings

1. Confidence calibration UNCALIBRATED (by design until labels).
2. Anticipatory load uses meetings proxy (no full calendar future graph in Engine observations).
3. Tasks/overdue not always present in Engine attrs — overdue_proxy weak.
4. Live multi-week personal backtest not run in this session.
5. V2 not promoted — SHADOW_ONLY verdict.

---

## 35. Next steps

1. Apply alembic `0007` on Postgres.
2. Run shadow/compare on synced personal data for 2–4 weeks.
3. Collect optional happiness/stress feedback labels with temporal cutoff.
4. Revisit promotion gates.

---

## 36–38. Commits / push / working tree

Recorded at end of sprint execution (see git log). Push to existing `origin` only.

---

## 39. Archivos modificados (Engine core)

```
docs/reviews/WELLBEING_V2_PHASE0_AUDIT.md
docs/reviews/ADVANCED_PERSONAL_WELLBEING_STATE_MODEL_V2_MASTER_REPORT.md
docs/wellbeing/* (7 specs)
docs/integrations/lifemaxxxing_compatibility_lock.json
migrations/versions/0007_wellbeing_v2_shadow.py
src/intelligence_maxxxing/domain_packs/life/wellbeing_v2/*
src/intelligence_maxxxing/application/use_cases/wellbeing.py
src/intelligence_maxxxing/api/routes/wellbeing.py
src/intelligence_maxxxing/contracts/api/wellbeing/*
src/intelligence_maxxxing/infrastructure/database/tables.py
sdk/python/intelligence_maxxxing_client/client.py
tests/unit/test_wellbeing_v2.py
tests/unit/test_wellbeing_v2_validation.py
tests/integration/test_wellbeing_api.py
```

LifeOS: BFF shadow route, formula_id, types/UI language, helpers.
