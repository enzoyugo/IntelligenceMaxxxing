# Trading M2 Agents Boundary V1

## Endpoints

- `POST/GET /api/v1/trading/context-assessments`
- `POST/GET /api/v1/trading/anomaly-findings`
- `POST/GET /api/v1/trading/critic-reviews`
- `POST/GET /api/v1/trading/shadow-adjudications`
- `POST /api/v1/trading/agent-bundle/runs`
- `GET /api/v1/trading/agents/health`
- `GET /api/v1/trading/agent-bundles/active`

Existing M1 assessment routes unchanged. Policy 1.0.0 frozen.

## Storage (IM-owned JSONL)

`trading_context_assessments`, `trading_anomaly_findings`, `trading_critic_reviews`, `trading_shadow_adjudications`, `agent_runs`, …

## Authority

Shadow adjudication never replaces `IM_ADVISORY`. Live Paper unaffected.
