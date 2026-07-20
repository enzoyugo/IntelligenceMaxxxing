# Life Domain Pack Charter

**Pack:** `life`  
**Version:** `0.1.0`  
**Status:** `EXPERIMENTAL` / `SHADOW`  
**Maximum autonomy:** `OBSERVE`, `ANALYZE`, `EXPLAIN` only

## Purpose

Teach the Core Engine how to evaluate N-of-1 observational associations between sleep and productivity for a single LifeMaxxxing subject, without issuing recommendations or claiming causality.

## Problem

Personal lifestyle telemetry exists in LifeMaxxxing, but governed hypothesis → experiment → evidence → belief → learning loops did not exist. Stage 3 admits the first shadow protocol.

## Intended users

- Private LifeMaxxxing operators (single-subject N-of-1)
- Engine operators reviewing shadow epistemic outputs

## Domain vocabulary

- Daily check-in, sleep hours, productivity score
- Sleep threshold (human-confirmed)
- Exposure groups: `SUFFICIENT` / `BELOW_THRESHOLD`
- Belief states: exploratory / prospective / insufficient / inconclusive

## Observable data

- `life.daily_check_in.completed.v1` observations already accepted by the Engine
- No direct database access from the pack; only public observation projections via Core ports

## Decisions supported

None. This pack never decides or recommends behavior.

## Measurable outcomes

- Belief state transitions under the pre-registered protocol
- Learning records describing what changed and what remains unknown

## Risks

- Confounding (observational association only)
- Small-N instability
- Data leakage across baseline / prospective cutoffs if protections fail

## Protected metrics

- Sleep threshold and MMD are human-confirmed and frozen at activation
- Calibration remains `UNCALIBRATED` until a later stage admits calibration

## Limitations

- Correlation only (`CORRELATION`)
- Never causal
- Never recommendations, execution, or behavior optimization
- Shadow / experimental; not an official Life product claim

## Cross-domain relationships

None in v0.1.0.

## Retirement conditions

- Protocol superseded by a later template version, or
- Constitutional Owner suspends / retires the pack
