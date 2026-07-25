# Trading Meta-Edge Research Policy V1 Report

## Purpose

Parallel research policy for historical selective TAKE/SKIP/ABSTAIN, **not** a mutation of frozen `IM_TRADING_DECISION_POLICY@1.0.0`.

## Identifiers

| Field | Value |
|-------|-------|
| Policy | `IM_TRADING_META_EDGE_RESEARCH_POLICY@1.0.0` |
| Bundle | `IM_TRADING_META_EDGE_AGENT_BUNDLE@1.0.0` |
| `promotion_eligible` | `false` |
| `live_policy_influence` | `false` |

## Mechanism

1. Hierarchical base-rate store on `label_trusted_net_R` (train folds only).
2. Sample gates (min n).
3. Thresholds: TAKE if E[net R] ≥ +0.05; SKIP if ≤ −0.05; else ABSTAIN.
4. Ridge expectancy model stored as diagnostic artifact (does not alone authorize TAKE).
5. Observation contract rejects outcome fields and OOS/FORWARD origins.

## Storage

`data/trading_meta_edge_v1/{fold_id}/` — inbox, artifacts, outbox.

## Frozen live surface

`domain_packs/trading/policy_v1.py` unchanged by this pack (research modules live under `meta_edge_v1/`).

## Campaign outcome (TMX-evaluated)

Joined evaluation under `IM_DECISION_LAYER_META_EDGE_DISCOVERY_V1` produced **NEAR_MISS_DIAGNOSTIC_ONLY** — incremental vs RAW on nested folds, failed TMX_NATIVE parity gate and symbol-concentration gate. No live promotion.
