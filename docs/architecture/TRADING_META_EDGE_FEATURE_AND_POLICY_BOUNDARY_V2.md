# IM Meta-Edge Feature & Policy Boundary V2

- No `tradingmaxxing` imports.
- No broker/MT5 access.
- Ingest only contract JSONL copied into `data/trading_meta_edge_v1/` (handoff).
- Observation contract rejects outcomes and OOS/FORWARD origins.
- Feature missingness must remain explicit (`UNKNOWN` / null + reason).
- Policy V2 is research-parallel; never mutates Policy 1.0.0.
