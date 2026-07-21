# Wellbeing Legacy Scale Resolution Audit V1

## Policy

Historical events keep raw bytes and provenance. No silent mass rewrite.

## Classification (`scripts/audit/wellbeing_observation_scale_audit.py`)

| Class | Meaning |
|-------|---------|
| `EXPLICIT_SCALE` | Valid per-field `*_scale` |
| `KNOWN_LEGACY_CONTRACT` | No explicit scale; adapter resolves |
| `AMBIGUOUS` | No scale and no known policy — do not guess |
| `INVALID` | Unknown scale / out of range / non-numeric |

## Legacy adapters (authoritative)

| Match | Assumed scale |
|-------|---------------|
| `source_ids` starts with `lifemaxxxing://daily-check-ins/` | `1_10` |
| `metadata.source_system == lifeos` on check-in v1 | `1_10` |
| `metadata.legacy_scale` / `test_fixture_scale` tags | as declared |

## Demo run

```json
{
  "EXPLICIT_SCALE": 1,
  "KNOWN_LEGACY_CONTRACT": 1,
  "AMBIGUOUS": 1,
  "INVALID": 1
}
```

## Ambiguous-event policy

- Do not infer by magnitude.
- Exclude field from score features (`None`).
- Penalize Confidence (`ambiguous_scale_count`, cap ≤ 40 when any ambiguous).
- Preserve event for later review.

## Note on prior synthetic 0–100 smoke

Earlier activation smokes sent ~60–70 without scales while attaching LifeOS source URIs. Under the LifeOS legacy policy those values are **INVALID** for `1_10` and are excluded — not reinterpreted via `raw <= 10`.
