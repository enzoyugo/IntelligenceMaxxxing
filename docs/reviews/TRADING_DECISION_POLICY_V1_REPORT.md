# Trading Decision Policy V1 Report

**policy_id:** `IM_TRADING_DECISION_POLICY`  
**policy_version:** `1.0.0`  
**frozen_at:** `2026-07-20T22:00:00Z`  
**model_version:** null

Ordered gates: schema → temporal → identity → quote → cost → fidelity → evidence → context → portfolio → anomalies → rank → decision.

Decisions: TAKE | SKIP | UNKNOWN | DEFER_DATA_QUALITY.

V1 often abstains with `NO_TRUSTED_BASE_RATE` + `SAMPLE_TOO_SMALL` (by design). Overall confidence is not a win probability; UNKNOWN keeps `overall_confidence=null`.
