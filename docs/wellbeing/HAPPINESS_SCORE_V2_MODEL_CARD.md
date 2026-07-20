# Happiness Score V2 — Model Card

| Field | Value |
|---|---|
| **Formula** | `wellbeing_v2@2.0.0` |
| **Score** | `happiness` (0–100, higher is better) |
| **Status** | SHADOW |

## Purpose

Estimate **subjective wellbeing and positive functioning** from LifeOS observations using a transparent weighted latent model. Intended for personal longitudinal tracking, dashboard display, and ANALYZE/EXPLAIN outputs.

## Non-purpose

- Not a clinical depression/anxiety instrument (PHQ-9, GAD-7, etc.)
- Not a substitute for professional mental-health assessment
- Not a ranking or comparison score across users
- Not derived from `100 - stress`
- Not inferred from phone content, HRV, cortisol, or passive biometrics

## Sub-scores

Each sub-score is a robust-z aggregate of registry features in [-1, 1] before weighting. Weights are imported from `registry.py` → `HAPPINESS_WEIGHTS`.

| Sub-score | Weight | Primary signals |
|---|---:|---|
| `positive_affect` | **0.22** | `checkin_happiness` |
| `vitality` | **0.14** | `checkin_energy`, `workout_completed` |
| `satisfaction` | **0.10** | `checkin_productivity` |
| `agency` | **0.08** | `checkin_productivity`, `task_completed_count` |
| `connection` | **0.12** | `checkin_social_activity` |
| `enjoyment` | **0.08** | `checkin_gym_done`, `workout_completed` |
| `recovery` | **0.14** | `checkin_sleep_hours` (adequacy vs personal baseline) |
| `positive_anticipation` | **0.06** | low forward meeting density, upcoming positive calendar gaps |
| `persistent_friction` | **0.06** (penalty) | sustained low energy + low sleep + low productivity composite |

### Latent happiness (pre-mapping)

```text
h_latent_raw = Σ (w_i * sub_score_i)  for i ≠ persistent_friction
h_latent     = h_latent_raw - w_friction * clamp(persistent_friction, 0, 1)
```

`persistent_friction` activates only when ≥ 3 of {energy, sleep, productivity} are below personal p25 for 5+ days (chronic horizon).

Weights sum to **1.00** including the friction penalty slot.

## Output mapping

```text
happiness = 50 + 50 * tanh(h_latent / T)
```

| Constant | Value | Source |
|---|---:|---|
| `T` (tanh temperature) | **1.2** | `registry.TANH_TEMPERATURE` |

Properties:

- Centered at 50 when latent = 0 (at personal baseline)
- Saturates smoothly; no hard clip except final `clamp(0, 100)` for numerical safety
- Outliers in input features are limited upstream by robust-z clamp [-3, 3]

## Guardrails

1. **Independence**: happiness computation never reads the stress output score.
2. **Domain caps**: movement domain (vitality + enjoyment) combined cap **0.22**; sleep domain (recovery) cap **0.20**.
3. **Cold-start**: if `positive_affect` is missing, happiness is `null` regardless of secondary features.
4. **Minimum evidence**: at least one of {positive_affect, vitality} must be present to emit a numeric score.
5. **Friction ceiling**: penalty removes at most **6** mapped points at latent saturation.

## Limitations

- Self-report bias on happiness/energy/productivity
- Sparse check-ins reduce reliability; see `happiness_confidence`
- `positive_anticipation` is weak until calendar/task observations are consistently synced
- Population priors during cold-start may mis-rank individuals with atypical baselines
- Does not detect acute safety crises; not designed for emergency triage

## Calibration interaction

Personal offset/scale adjustments (when label count permits) apply to `h_latent` before tanh mapping. Global sub-score weights remain fixed until ≥ 50 labels (see calibration policy).

## Version history

| Version | Change |
|---|---|
| 2.0.0 | Initial SHADOW hierarchical happiness model |
