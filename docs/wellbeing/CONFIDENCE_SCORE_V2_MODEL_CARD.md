# Confidence Score V2 — Model Card

| Field | Value |
|---|---|
| **Formula** | `wellbeing_v2@2.0.0` |
| **Scores** | `happiness_confidence`, `stress_confidence`, `confidence` (overall) |
| **Status** | SHADOW |

## Purpose

Quantify **evidence quality** supporting the published Happiness and Stress scores. Answers: *"How much should I trust this number given what was observed, when, and how completely?"*

## Non-purpose

- **Not** abstract model certainty or Bayesian posterior confidence
- **Not** LLM self-reported confidence
- **Not** a quality score for the user as a person
- **Not** interchangeable with happiness or stress magnitude
- **Not** a license for clinical decisions

## Components

Each component is normalized to [0, 1] before weighting. Weights from `registry.py` → `CONFIDENCE_WEIGHTS`.

| Component | Weight | Definition |
|---|---:|---|
| `coverage` | **0.18** | Fraction of registry features applicable to this score that are present in window |
| `freshness` | **0.14** | Mean decay-weighted recency; 1.0 if all features observed within half-life |
| `reliability` | **0.12** | Source-type quality (direct check-in > inferred calendar > stale carry-forward) |
| `baseline_maturity` | **0.14** | Personal baseline sample depth (0 until ≥ 3 points, ramps to 1 at 14 days) |
| `agreement` | **0.10** | Consistency among correlated features (e.g. low energy + low sleep co-directional) |
| `stability` | **0.10** | Low day-to-day variance in primary self-report (inverse variance penalty) |
| `calibration` | **0.08** | Personal label fit when calibrated; fixed **0.5** prior when `UNCALIBRATED` |
| `missingness` | **0.08** | `1 - missing_rate` for required features |
| `inference` | **0.04** | Penalty for features using `LAST_WITH_DECAY` or calendar inference |
| `ood` | **0.02** | Penalty when robust-z exceeds 2.5 on ≥ 2 features (out-of-personal-distribution) |

Weights sum to **1.00**.

## Separate happiness and stress confidence

Feature sets differ:

| Score | Required features (minimum set) |
|---|---|
| `happiness_confidence` | `checkin_happiness`, `checkin_energy`, `checkin_sleep_hours` |
| `stress_confidence` | `checkin_stress`, `checkin_sleep_hours`, `checkin_alcohol` |

Each score computes its component vector over its applicable registry subset, then:

```text
happiness_confidence = 100 * clamp(Σ w_c * component_c, 0, 1)
stress_confidence    = 100 * clamp(Σ w_c * component_c, 0, 1)
```

## Overall confidence

```text
confidence = clamp(
    0.35 * happiness_confidence
  + 0.35 * stress_confidence
  + 0.15 * cross_agreement
  + 0.15 * global_coverage,
  0, 100
)
```

- `cross_agreement`: 1.0 when happiness and stress latent directions are not contradictory (e.g. high happiness latent + extreme stress latent without supporting features reduces agreement)
- `global_coverage`: union coverage across all wellbeing features

## Calibration status

| Labels (feedback pairs) | Status | `calibration` component |
|---|---|---|
| 0–19 | `UNCALIBRATED` | fixed prior 0.5 |
| ≥ 20 | `CALIBRATED_OFFSET` or higher | MAE-based fit quality in [0, 1] |

Calibration measures **label fit**, not parametric uncertainty. See `WELLBEING_CALIBRATION_POLICY_V2.md`.

## Cold-start caps

| Condition | Max confidence |
|---|---:|
| `< 3` check-in days | 35 |
| `3–6` days | 55 |
| `≥ 7` days, adequate coverage | 100 (subject to component penalties) |

## Guardrails

1. Low confidence **must not** block score emission; it accompanies scores as metadata.
2. Early-warning severity escalation requires `confidence ≥ 40` unless `COMPOUND_RISK` safety rule fires with ≥ 2 independent load signals.
3. `inference` and `ood` components only reduce confidence; they never increase it.
4. Confidence is recomputed on every snapshot; no smoothing across days.

## Interpretation bands

| Range | Label |
|---|---|
| 0–24 | Very low |
| 25–49 | Low |
| 50–69 | Moderate |
| 70–84 | High |
| 85–100 | Very high |

## Limitations

- High confidence with wrong self-report remains possible (garbage in, confident out)
- Calendar inference inflates apparent coverage while lowering reliability—inference penalty mitigates but does not eliminate
- Uncalibrated users cap calibration component artificially

## Version history

| Version | Change |
|---|---|
| 2.0.0 | Initial multi-component evidence-quality confidence |
