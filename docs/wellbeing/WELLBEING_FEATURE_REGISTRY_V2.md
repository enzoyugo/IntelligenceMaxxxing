# Wellbeing Feature Registry V2

| Field | Value |
|---|---|
| **Formula** | `wellbeing_v2@2.0.0` |
| **Registry module** | `domain_packs/life/wellbeing_v2/registry.py` → `DECAYS` |

## Scope

Only features derivable from **real LifeOS observations** ingested by the Engine. No speculative biometrics.

### Allowed sources

- `life.daily_check_in.completed.v1` context attributes
- Workout completion observations (LifeOS sync)
- Task/meeting counts when exposed via observation `context.attributes`
- Calendar density derived from explicit meeting observations (not phone screen time)

### Explicitly forbidden

- HRV, cortisol, blood glucose, SpO₂
- Phone unlock counts, app usage, screen time, keyboard activity
- Email/chat sentiment, social media activity
- GPS mobility patterns without explicit user-logged events
- Third-party wearable streams unless mapped 1:1 to a LifeOS observation type (none at v2.0.0)

## Missingness policy

| Policy | Meaning |
|---|---|
| `NO_IMPUTATION` | Absent → feature omitted; reduces coverage |
| `LAST_WITH_DECAY` | Most recent value carried forward with exponential decay by half-life |

`LAST_WITH_DECAY` is permitted only where noted; subjective booleans and 1–10 scales never use it.

## Feature table

| Feature ID | Source(s) | Direction | Half-life (h) | Domain | Missingness | Maps to sub-scores |
|---|---|---|---:|---|---|---|
| `checkin_happiness` | `daily_check_in.attributes.happiness` (1–10) | + happiness | 36 | affect | NO_IMPUTATION | positive_affect |
| `checkin_energy` | `daily_check_in.attributes.energy` (1–10) | + happiness / − stress | 24 | vitality | NO_IMPUTATION | vitality, physiological (inverse) |
| `checkin_stress` | `daily_check_in.attributes.stress` (1–10) | + stress | 24 | emotional | NO_IMPUTATION | emotional |
| `checkin_productivity` | `daily_check_in.attributes.productivity` (1–10) | + happiness / − friction | 48 | agency | NO_IMPUTATION | satisfaction, agency, persistent_friction (inverse) |
| `checkin_sleep_hours` | `daily_check_in.attributes.sleep_hours` (float) | + recovery / − stress if low | 72 | sleep | LAST_WITH_DECAY | recovery, physiological, recovery_deficit |
| `checkin_gym_done` | `daily_check_in.attributes.gym_done` (bool) | + happiness / − stress | 48 | movement | NO_IMPUTATION | enjoyment, protective_capacity |
| `checkin_social_activity` | `daily_check_in.attributes.social_activity` (bool) | + happiness / − stress | 72 | connection | NO_IMPUTATION | connection, protective_capacity |
| `checkin_alcohol` | `daily_check_in.attributes.alcohol` (bool) | + stress | 48 | contextual | NO_IMPUTATION | contextual |
| `checkin_meetings` | `daily_check_in.attributes.meetings` (int, optional) | + stress | 24 | cognitive | NO_IMPUTATION | cognitive |
| `workout_completed` | workout observation `completed=true` | + happiness / − stress | 72 | movement | NO_IMPUTATION | vitality, enjoyment, protective_capacity |
| `task_overdue_count` | task observation attrs `overdue_count` | + stress | 24 | cognitive | NO_IMPUTATION | cognitive, anticipatory |
| `task_completed_count` | task observation attrs `completed_count` | + happiness | 48 | agency | NO_IMPUTATION | agency |
| `meeting_density` | derived: meetings / free_minutes from calendar attrs | + stress | 12 | cognitive | LAST_WITH_DECAY | cognitive, contextual, anticipatory |
| `calendar_free_block_minutes` | calendar attrs `free_minutes` | − stress | 12 | cognitive | LAST_WITH_DECAY | protective_capacity, positive_anticipation |

## Normalization

For each feature at time `t`:

```text
robust_z = clamp((x - median_personal) / max(MAD_personal, ε), -3, 3)
```

Cold-start uses population anchors from V1 check-in schema (happiness 6.5, stress 4.5, energy 6.0, sleep 7.5h).

Decay for observation at age `Δh`:

```text
weight = exp(-ln(2) * Δh / half_life_hours)
```

## Domain cap reference

See `registry.py` → `DOMAIN_CAPS`. Features inherit domain tags above for cap aggregation.

## Extraction contract

Features are extracted from projected observations with:

- `domain_pack == "life"`
- `subject == "daily_check_in"` (check-in features) or pack-defined workout/task subjects
- `metadata.life_event_type == "life.daily_check_in.completed.v1"` for check-ins
- First-write-wins per calendar day by lowest `global_position` (same as V1)

## Version history

| Version | Change |
|---|---|
| 2.0.0 | Initial registry aligned to LifeOS check-in schema |
