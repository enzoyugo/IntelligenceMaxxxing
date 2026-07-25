# IM Trading Meta-Edge Research Boundary V1

## Hard rules

- No `tradingmaxxing` imports.
- No broker/MT5 imports.
- No reads of TMX repository storage.
- Accept only contract payloads copied into IM-local `data/trading_meta_edge_v1/`.
- Prospective assessment paths must continue to reject outcomes (research observation contract enforces this).

## Layers

Domain pack: `intelligence_maxxxing.domain_packs.trading.meta_edge_v1`

CLI: `python -m intelligence_maxxxing.domain_packs.trading.meta_edge_v1 train|infer`

## Relation to M2 Bundle 1.0.0

Frozen M2 bundle remains authoritative for live advisory agents. Meta-edge bundle is research-parallel and non-authoritative for `IM_ADVISORY`.
