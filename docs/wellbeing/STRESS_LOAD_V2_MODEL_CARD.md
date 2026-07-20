# Stress Load V2 — Model Card

| Field | Value |
|---|---|
| **Formula** | `wellbeing_v2@2.0.0` |
| **Score** | `stress` (0–100, higher is worse) |
| **Status** | SHADOW |

## Purpose

Estimate **experienced and accumulated load** from cognitive, emotional, physiological, and contextual LifeOS signals. Supports early-warning detection and contributor explanation.

## Non-purpose

- Not a clinical burnout or PTSD diagnostic
- Not a measure of cortisol, HRV, or autonomic nervous system state
- Not derived from inverted happiness
- Not actionable medical advice

## Sub-scores

Weights from `registry.py` → `STRESS_WEIGHTS`.

| Sub-score | Weight | Primary signals |
|---|---:|---|
| `cognitive` | **0.18** | `checkin_meetings`, `meeting_density`, `task_overdue_count` |
| `emotional` | **0.20** | `checkin_stress` |
| `physiological` | **0.18** | `checkin_sleep_hours` (deficit), `checkin_energy` (inverse) |
| `contextual` | **0.12** | `checkin_alcohol`, routine disruption proxies |
| `anticipatory` | **0.10** | forward meeting/task density (next 48h) |
| `accumulated` | **0.12** | recursive load state (see accumulation) |
| `recovery_deficit` | **0.15** | chronic under-sleep, low gym/social, multi-day friction |
| `protective_capacity` | **0.05** (credit) | gym, social, adequate sleep, free calendar blocks |

### Latent stress (pre-mapping)

```text
load_subtotal = Σ (w_i * sub_score_i)  for load dimensions
stress_latent = load_subtotal - w_protect * clamp(protective_capacity, 0, 1)
```

Load dimensions exclude `protective_capacity`, which subtracts.

## Accumulation model

Chronic stress carries forward with decay:

```text
load_t = clamp(RETENTION * load_{t-1} + new_load - recovery, 0, 100)
```

| Constant | Value |
|---|---:|
| `RETENTION` | **0.72** (`registry.ACCUMULATION_RETENTION`) |

- `new_load`: weighted acute components (cognitive + emotional + physiological + contextual) at time t
- `recovery`: credit from sleep ≥ personal median, gym, social, and low meeting density (bounded 0–25 per day)
- Initial `load_0 = 0` for new users

The `accumulated` sub-score is `load_t / 100` mapped to [-1, 1] robust scale.

## Temporal mix (acute / chronic / anticipatory)

Before accumulation and output mapping, sub-scores are mixed per horizon:

```text
mix = 0.45 * acute + 0.40 * chronic + 0.15 * anticipatory
```

Constants: `registry.ACUTE_CHRONIC_ANTICIPATORY = (0.45, 0.40, 0.15)`.

| Horizon | Stress interpretation |
|---|---|
| Acute | Same-day reported stress, last-night sleep, today's meeting count |
| Chronic | 7–14d alcohol rate, sleep debt trend, accumulated load |
| Anticipatory | Tomorrow's meeting density, overdue task backlog growth |

## Output mapping

```text
stress = clamp(50 + 50 * tanh(stress_latent / T), 0, 100)
```

`T = 1.2` (`registry.TANH_TEMPERATURE`).

## Guardrails

1. **Independence**: never computed as `100 - happiness`.
2. **Domain caps**: sleep-domain contributions (physiological + recovery_deficit) capped at **0.30** combined; cognitive (cognitive + anticipatory meeting overlap) capped at **0.28**.
3. **Required signal**: `emotional` (reported stress) must be present for non-null stress unless `accumulated > 0.5` with ≥ 7d history.
4. **Protective floor**: protective credit cannot reduce mapped stress by more than **8** points/day.
5. **Alcohol amplifier**: contextual alcohol contribution capped at **0.08** latent units regardless of frequency spikes.

## Limitations

- Self-reported stress dominates emotional sub-score; low reporting cadence creates blind spots
- Meeting/task features depend on LifeOS sync completeness
- Accumulation can lag sudden recovery (by design—models sustained load)
- No physiological biomarker validation

## Version history

| Version | Change |
|---|---|
| 2.0.0 | Initial SHADOW accumulation-based stress model |
