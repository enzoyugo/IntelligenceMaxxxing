# M2 AGENT RUN CONTRACT TRUTH V1

Generated: 2026-07-24T01:13Z (approx)  
Repo: IntelligenceMaxxxing @ `f21254d` (no code change)

## Verdict

Neither pure discrete-`agent_runs` nor assessment-only aggregation.

**Official:** typed parallel artifacts inside frozen `IM_M2_AGENT_BUNDLE@1.0.0`, with `agent_runs.jsonl` as an **optional/auxiliary** ledger.

## For FORWARD IB enroll (TMX bridge → Policy assessment)

| Expectation | Required? |
|-------------|-----------|
| Policy / IM advisory assessment row | **Yes** |
| HorizonNoise sidecar assessment | Optional observational |
| Discrete Context/Anomaly/Critic `agent_runs` | **No** |
| Typed Context/Anomaly/Critic JSONL | Only if `/agent-bundle/runs` invoked |

Missing Context/Anomaly/Critic `agent_runs` for `ES_94055f6c1b606314b76ffcfd` is **not a failure** of the live enroll path.

Verifier mode: `POLICY_ADVISORY_AGGREGATED_PLUS_OPTIONAL_M2_TYPED_ARTIFACTS`  
Status: `AGGREGATED_POLICY_TRACE_COMPLETE`

## Frozen versions

- `IM_TRADING_DECISION_POLICY@1.0.0`
- `IM_M2_AGENT_BUNDLE@1.0.0`
- `HorizonNoiseAgentV1@1.0.0` (outside frozen M2 bundle)

## IM code change

**None.** Contract documentation only; no prospective agent-trace repair required.
