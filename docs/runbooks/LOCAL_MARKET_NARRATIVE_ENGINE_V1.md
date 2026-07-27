# Local Market Narrative Engine V1

## Prerequisites

- TMX foundation artifacts present under  
  `E:\TradingMaxxxing_V2\data\processed\research\professional_market_state_and_narrative_foundation_v1\`
- IM health: `http://127.0.0.1:8100/health/live` and research health endpoint
- Do not open OOS or use FORWARD for model fitting

## Schema locations

Read TMX campaign schemas:

- `market_narrative_schema_v1.json`
- `market_hypothesis_schema_v1.json`
- `episodic_memory_manifest.json`

## Operating rules

1. Only cite evidence object IDs present in TMX ledgers with `available_at <= decision_available_at`.
2. Structured JSON is primary; human text is secondary.
3. Unknown strategy identity → ABSTAIN/DQ (exact registry only).
4. Never mutate FAMILY shadow artifacts.

## Health

```powershell
Invoke-WebRequest http://127.0.0.1:8100/health/live
Invoke-WebRequest http://127.0.0.1:8100/api/v1/research/health
```
