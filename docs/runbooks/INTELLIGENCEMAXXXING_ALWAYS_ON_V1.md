# IntelligenceMaxxxing Always-On V1

- Bind: `127.0.0.1:8100` only (not public)
- Health: `/health/live`, `/api/v1/research/health`
- Started via TMX `process_control_v1.start_im_api` / ecosystem watchdog
- Research-only; no broker execution
- Consumed by TMX bridge and LifeMaxxxing BFF server-side
