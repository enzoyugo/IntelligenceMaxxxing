# Wellbeing State Model V2 — Architecture Specification

| Field | Value |
|---|---|
| **Formula ID** | `wellbeing_v2` |
| **Version** | `2.0.0` |
| **Status** | `SHADOW` |
| **Production default** | `wellbeing_v1@1.0` remains **ACTIVE** |

## Purpose

V2 replaces the flat V1 composite with a layered, deterministic pipeline that estimates a latent wellbeing state vector **z(t)**, maps independent **Happiness** and **Stress Load** scores, and reports **Confidence** as evidence quality—not model certainty.

V2 is implemented in Engine only. LifeOS consumes snapshots via API; it must not recompute scores locally.

## Non-goals

- Clinical diagnosis, disorder screening, or treatment guidance
- Causal claims or behavior optimization (`RECOMMEND` / `EXECUTE` remain forbidden for the Life pack)
- LLM-driven score generation
- Ingestion of non-LifeOS signals (HRV, cortisol, phone content, passive sensing, third-party wearables without explicit LifeOS observation mapping)

## Architecture layers

```
L0  Observation ingest     life.daily_check_in.completed.v1, workouts, task/meeting attrs
L1  Feature extraction     registry-driven normalization, decay, baseline (median/MAD)
L2  Sub-score assembly     happiness + stress sub-scores with domain caps
L3  Latent state z(t)      acute / chronic / anticipatory temporal mix
L4  Score mapping          tanh → 0–100 Happiness; bounded accumulation → Stress
L5  Confidence             separate happiness / stress / overall evidence quality
L6  Policy outputs         early-warning states, contributors (ANALYZE / EXPLAIN only)
```

Each layer is versioned, deterministic, and auditable. Snapshots persist `formula_id`, `formula_version`, feature snapshot hash, and contributor breakdown.

## Latent state vector z(t)

At evaluation time `t`, the engine maintains a bounded latent vector:

```text
z(t) = [
  z_happiness_acute,
  z_happiness_chronic,
  z_happiness_anticipatory,
  z_stress_acute,
  z_stress_chronic,
  z_stress_anticipatory,
  z_confidence_happiness,
  z_confidence_stress,
]
```

Sub-scores (L2) feed L3 temporal mixing:

```text
z_happiness = 0.45 * acute + 0.40 * chronic + 0.15 * anticipatory
z_stress    = 0.45 * acute + 0.40 * chronic + 0.15 * anticipatory
```

Acute uses features with half-life ≤ 48h (decayed). Chronic uses EWMA / rolling median over 7–30d windows. Anticipatory uses forward-looking calendar/task density when observation attrs exist.

Constants are imported from `registry.py`: `ACUTE_CHRONIC_ANTICIPATORY = (0.45, 0.40, 0.15)`.

## Happiness and Stress independence

**Happiness is not defined as `100 - Stress`.** The scores share no algebraic inversion.

| Score | Latent construction | Output mapping |
|---|---|---|
| Happiness | Weighted sum of positive sub-scores minus capped `persistent_friction` penalty | `50 + 50 * tanh(z_h / T)`, `T = 1.2` |
| Stress Load | Weighted load sub-scores minus `protective_capacity`, plus accumulated load | `clamp(50 + 50 * tanh(z_s / T), 0, 100)` |

Shared features (e.g. sleep) may inform both sides after **domain caps** (see below); they are not mirrored.

## Confidence as evidence quality

Confidence measures **how well the available observations support the published scores**, not abstract epistemic certainty or LLM confidence.

Three published values:

- `happiness_confidence` — coverage/freshness/reliability of happiness-relevant features
- `stress_confidence` — same for stress-relevant features
- `confidence` (overall) — blend of the above plus cross-score agreement and global coverage

Calibration status is `UNCALIBRATED` until ≥ 20 user feedback labels exist (see calibration policy). Until then, the calibration component contributes its prior (neutral) weight only.

## Cold-start policy

| Days with eligible check-ins | Behavior |
|---|---|
| 0 | All scores `null`; `data_sufficiency = COLD_START`; `early_warning = INSUFFICIENT_DATA` |
| 1–2 | Sub-scores computed with population prior baselines; confidence capped at 35; happiness/stress may be emitted with `COLD_START` flag |
| 3–6 | Personal median/MAD baselines when feature-specific sample ≥ 3; confidence capped at 55 |
| ≥ 7 | Full pipeline; confidence uncapped subject to missingness penalties |

Population priors use conservative 1–10 → robust-z anchors (happiness 6.5, stress 4.5, energy 6.0, sleep 7.5h) documented in the feature registry.

## Missingness

- Default: **`NO_IMPUTATION`** — absent features contribute zero to numerators and reduce coverage denominators.
- **`LAST_WITH_DECAY`** allowed only for slow-moving signals (`sleep_hours`, `meeting_density`) where stale carry-forward is justified; decay uses registry half-life.
- Missingness never imputes subjective mood/stress/boolean flags.
- Confidence `missingness` component penalizes proportion of required features absent in the evaluation window.

## Double-counting and hierarchical domain caps

Features are tagged with a **domain** (sleep, movement, affect, cognitive, …). Multiple sub-scores may consume the same domain; hierarchical caps limit total absolute contribution:

```text
effective_contribution(domain) = min(raw_sum, DOMAIN_CAPS[domain].max_total_contribution)
```

Caps apply after sub-score weighting, before latent mixing. See `registry.py` → `DOMAIN_CAPS`.

Example: `sleep_hours` feeds happiness `recovery`, stress `physiological`, and stress `recovery_deficit`. Combined sleep-domain stress contribution is capped at 0.30; happiness recovery cap at 0.20.

## Temporal model: acute, chronic, anticipatory

| Horizon | Window | Role |
|---|---|---|
| Acute | 0–48h (half-life decay) | Same-day / recent deviations |
| Chronic | 7–30d rolling robust baseline | Sustained elevation or deficit |
| Anticipatory | Next 24–72h from calendar/task attrs | Forward load / positive expectation |

Stress accumulation (chronic component):

```text
load_t = clamp(0.72 * load_{t-1} + new_load - recovery, 0, 100)
```

`ACCUMULATION_RETENTION = 0.72`. Recovery credits derive from sleep adequacy, gym, social activity, and explicit rest signals.

## Shadow vs active policy

| Status | Meaning |
|---|---|
| **ACTIVE** (`wellbeing_v1@1.0`) | Default API `/current`, LifeOS dashboard, persisted snapshots served to clients |
| **SHADOW** (`wellbeing_v2@2.0.0`) | Computed in parallel, stored in shadow snapshots or internal audit tables; **not** returned as default unless `?formula=wellbeing_v2` or operator flag |

Promotion **SHADOW → ACTIVE** requires passing `WELLBEING_VALIDATION_PROTOCOL_V2.md` gates. Demotion or rollback restores V1 as ACTIVE without deleting historical V2 snapshots.

## Output contract (conceptual)

```json
{
  "formula_id": "wellbeing_v2",
  "formula_version": "2.0.0",
  "formula_status": "SHADOW",
  "happiness": 62.4,
  "stress": 71.1,
  "happiness_confidence": 48.2,
  "stress_confidence": 52.0,
  "confidence": 50.1,
  "calibration_status": "UNCALIBRATED",
  "data_sufficiency": "ADEQUATE",
  "early_warning": "WATCH",
  "latent": { "z_happiness": 0.31, "z_stress": 0.58 },
  "sub_scores": { "...": "..." },
  "contributors": [],
  "features": {},
  "explanation": {}
}
```

## Related documents

| Document | Scope |
|---|---|
| `HAPPINESS_SCORE_V2_MODEL_CARD.md` | Happiness sub-scores and mapping |
| `STRESS_LOAD_V2_MODEL_CARD.md` | Stress sub-scores and accumulation |
| `CONFIDENCE_SCORE_V2_MODEL_CARD.md` | Confidence components |
| `WELLBEING_FEATURE_REGISTRY_V2.md` | Feature IDs, sources, decay |
| `WELLBEING_CALIBRATION_POLICY_V2.md` | Personal calibration gates |
| `WELLBEING_VALIDATION_PROTOCOL_V2.md` | Evaluation and promotion |
| `src/intelligence_maxxxing/domain_packs/life/wellbeing_v2/registry.py` | Canonical numeric constants |

## Implementation note

V2 code lives under `domain_packs/life/wellbeing_v2/`. All weights and decays **must** be imported from `registry.py`; documentation and code share a single source of truth.
