# TradingMaxxxing Adapter Boundary V1

TradingMaxxxing is an **external client**. IntelligenceMaxxxing never imports TMX packages, never reads TMX files, and never issues broker commands.

## Surface

- `POST /api/v1/trading/assessments`
- `GET /api/v1/trading/assessments/{id}`
- `GET /api/v1/trading/policies/active`
- `GET /api/v1/trading/health`

Auth for local bridge: header `X-Trading-Bridge-Token` (shared secret env `IM_TRADING_BRIDGE_TOKEN`).

## Storage

IM-owned append-only JSONL under `data/trading_bridge_v1/` (or `IM_TRADING_STORE_DIR`).
