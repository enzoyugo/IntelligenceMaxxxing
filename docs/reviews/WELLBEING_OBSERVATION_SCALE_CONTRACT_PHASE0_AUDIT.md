# WELLBEING OBSERVATION SCALE CONTRACT — PHASE 0 AUDIT

**Date:** 2026-07-20  
**LifeOS HEAD:** `22b4b94`  
**Engine HEAD:** `a678983`

## Critical correction vs prior sprint

Prior sprint assumed LifeOS stores **0–100**. Code audit shows Daily Flow `ValueSlider` defaults to **min=1, max=10** (Likert). Defaults: happiness=7, stress=4.

Values ~62–70 in the Engine DB came from **synthetic E2E BFF payloads**, not from the iPhone capture control.

**Authoritative LifeOS capture scale: `1_10`.**

## Field matrix

| Field | Source | Current range | Assumed by V1.1 | Normalizer | Ambiguity | Target |
|---|---|---|---|---|---|---|
| happiness | Daily Flow ValueSlider | 1–10 | magnitude heuristic | `_to_score_100` | 5 ambiguous | explicit `1_10` |
| stress | Daily Flow ValueSlider | 1–10 | magnitude heuristic | `_to_score_100` | 10→100 risk | explicit `1_10` |
| energy | Daily Flow ValueSlider | 1–10 | magnitude heuristic | `_to_score_100` | same | explicit `1_10` |
| productivity | Daily Flow ValueSlider | 1–10 | magnitude heuristic | `_to_score_100` | same | explicit `1_10` |
| sleep_hours | Stepper/input | hours | none (hours) | identity | none | hours (no score scale) |
| gym_done etc. | boolean | bool | bool | bool | none | boolean |

## Heuristic sites (productive — must remove)

| Location | Behavior |
|---|---|
| `wellbeing_v1.py` `_to_score_100` | `raw <= 10 → 1_10 else 0_100` |
| `wellbeing_v2/math_utils.scale_1_10` | assumes 1–10 always (wrong for 0–100 contamination) |

## Event contract

`life.daily_check_in.completed.v1` — BFF minimization allow-lists numeric fields; **unknown keys dropped**. Scale fields must be allow-listed (Option A compatible extension) or emit `completed.v2`.

**Decision:** Option A — extend v1 payload with `*_scale` enum fields + `measurement_contract_version`. Semántica de valores no cambia (sigue siendo Likert 1–10 desde UI).

## Target versions

| Artifact | Version |
|---|---|
| Measurement contract | `wellbeing_measurements_v1` |
| Normalization | `canonical_0_100_v1` |
| V1 formula | `wellbeing_v1@1.2` (ACTIVE) — no magnitude heuristic |
| V2 formula | `wellbeing_v2@2.1.0` (SHADOW) — consumes canonical 0–100 |
| SDK | `0.4.0` (pass-through attrs; pin bump) |

## Legacy policies (no magnitude)

| Key | Scale |
|---|---|
| `(life.daily_check_in.completed.v1, lifeos)` | `1_10` |
| Unit-test fixtures without scales | `1_10` via test helper / legacy fixture tag |
| Synthetic E2E 0–100 without scale | AMBIGUOUS / OUT_OF_RANGE under 1_10 → excluded + confidence penalty |
