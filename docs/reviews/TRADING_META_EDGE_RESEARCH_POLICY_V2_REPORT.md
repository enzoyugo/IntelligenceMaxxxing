# Trading Meta-Edge Research Policy V2 Report

## Identity

| Field | Value |
|-------|-------|
| Policy | `IM_TRADING_META_EDGE_RESEARCH_POLICY_V2@1.0.0` |
| Bundle | `IM_TRADING_META_EDGE_AGENT_BUNDLE_V2@1.0.0` |
| promotion_eligible | false |
| live_policy_influence | false |

## Relationship to V1 thin policy

Thresholds and hierarchical base-rate logic are **semantically identical** to the V1 thin research policy (TAKE ≥ +0.05R, SKIP ≤ −0.05R, min n=30). No opportunistic recalibration after seeing canonical V2 results.

Frozen live `IM_TRADING_DECISION_POLICY@1.0.0` and M2 Bundle 1.0.0 are untouched.

## Campaign outcome (TMX-evaluated on canonical V2)

Thin replication on ECONOMIC_VALID labels: **collapse** — IM selective mean ≈ −0.10R (not an edge). V1 +0.78R invalidated as label contamination.
