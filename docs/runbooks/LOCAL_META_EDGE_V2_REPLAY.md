# Local Meta-Edge V2 Replay Runbook

## Full campaign (TMX orchestrator)

```powershell
cd E:\TradingMaxxxing_V2
$env:PYTHONPATH="src"
python -m tradingmaxxing_v2.research.meta_edge_canonical_replay_v2.orchestrator_v2 --mode full
```

## Guards

- Must not point economic builders at `trade_memory_train_validation_v1.jsonl`.
- Canonical source: `pre_oos_canonical_ledger_rebuild_v1/ledgers_v2/canonical_pre_oos_combined_ledger_v2.jsonl`.

## Todo validation

```powershell
python scripts/research/validate_meta_edge_v2_todo.py
```

## Tests

```powershell
python -m pytest tests/research/meta_edge_canonical_replay_v2 -q
```
