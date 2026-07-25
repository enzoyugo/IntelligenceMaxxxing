# Local Family Candidate Adjudication V1 — Runbook

## Preconditions

- TMX health `http://127.0.0.1:8000/api/health` → 200
- IM live `http://127.0.0.1:8100/health/live` → 200
- IM research `http://127.0.0.1:8100/api/v1/research/health` → 200
- PIT V1 artifacts present under TMX  
  `data/processed/research/pit_market_intelligence_and_real_decision_layer_v1/`
- OOS closed; do not point research loaders at forward paper for training

## Run (TMX)

```powershell
cd E:\TradingMaxxxing_V2
$env:PYTHONPATH = "src"
python -m tradingmaxxing_v2.research.contextual_family_adjudication_v1.orchestrator_v1
```

## Expected outputs

Root: `data/processed/research/contextual_family_edge_adjudication_v1/`

Critical:

- `candidate_decision_determinism_report.json` (`reproducible=true`)
- `candidate_repeated_random_placebo_results.json` (`n_policies>=2000`)
- `candidate_survivor_gate_matrix.json`
- `candidate_final_classifications.json`
- `run_manifest.json`

## Safety

- Do not modify Policy IM / M2
- Do not open TEST_OOS
- Do not use FORWARD for train/calibrate/select/adjudicate
- Keep Scheduled Tasks / headless workers running
