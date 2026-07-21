# Wellbeing Measurement Scale Contract V1

## Contract identity

| Field | Value |
|-------|-------|
| Measurement contract | `wellbeing_measurements_v1` |
| Normalization | `canonical_0_100_v1` |
| Module | `domain_packs/life/measurement_scale.py` |

## Scales supported (closed enum)

| Token | Meaning | Valid range | Canonical map |
|-------|---------|-------------|----------------|
| `0_100` | Score 0–100 | `[0, 100]` | identity |
| `1_10` | Likert 1–10 | `[1, 10]` | `(raw - 1) / 9 * 100` (1→0, 10→100) |

Arbitrary scale strings are rejected (`MEASUREMENT_SCALE_UNKNOWN`).

## Payload shape (compatible extension)

Per-field scales on `life.daily_check_in.completed.v1` attributes:

```json
{
  "measurement_contract_version": "wellbeing_measurements_v1",
  "happiness": 5,
  "happiness_scale": "0_100",
  "stress": 4,
  "stress_scale": "1_10"
}
```

Mixed per-field scales are allowed and normalized independently.

## Score fields

`happiness`, `stress`, `energy`, `productivity`

Non-score (no score scale): `sleep_hours`, `weight`, money, gym boolean, task/meeting counts.

## Resolution precedence

1. Explicit `*_scale` field  
2. Known `measurement_contract_version` (requires per-field scales)  
3. Legacy adapter (event type + source URI / metadata)  
4. Error → field excluded (`AMBIGUOUS` / typed error)

**Never:** magnitude inference (`raw <= 10`).

## Typed errors

- `MEASUREMENT_SCALE_MISSING`
- `MEASUREMENT_SCALE_UNKNOWN`
- `MEASUREMENT_OUT_OF_RANGE`
- `MEASUREMENT_CONTRACT_UNSUPPORTED`
- `MEASUREMENT_SCALE_CONFLICT`

Invalid inputs are not silently clamped at the contract boundary.
