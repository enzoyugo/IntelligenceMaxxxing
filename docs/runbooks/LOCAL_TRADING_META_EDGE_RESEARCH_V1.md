# Local Trading Meta-Edge Research V1 Runbook

## Train

```powershell
cd E:\IntelligenceMaxxxing
$env:PYTHONPATH="src"
python -m intelligence_maxxxing.domain_packs.trading.meta_edge_v1 train `
  --training-jsonl data\trading_meta_edge_v1\outer_1\inbox\training_rows.jsonl `
  --artifact-dir data\trading_meta_edge_v1\outer_1\artifacts `
  --split-hash <split_hash> `
  --feature-registry-hash <feature_registry_hash>
```

## Infer

```powershell
python -m intelligence_maxxxing.domain_packs.trading.meta_edge_v1 infer `
  --observations-jsonl data\trading_meta_edge_v1\outer_1\inbox\observations.jsonl `
  --artifact-dir data\trading_meta_edge_v1\outer_1\artifacts `
  --out-assessments-jsonl data\trading_meta_edge_v1\outer_1\outbox\assessments.jsonl
```

## Full campaign (from TMX)

```powershell
cd E:\TradingMaxxxing_V2
$env:PYTHONPATH="src"
python -m tradingmaxxing_v2.research.im_meta_edge_discovery_v1.orchestrator_v1 --mode full
```

## Tests

```powershell
cd E:\IntelligenceMaxxxing
$env:PYTHONPATH="src"
python -m pytest tests\domain_packs\trading\meta_edge_v1 -q
```

## Safety

- Research-only; never enable execution.
- Do not point training at OOS/FORWARD origins.
- Do not edit `policy_v1.py` Policy 1.0.0 or live M2 bundle for this research.
