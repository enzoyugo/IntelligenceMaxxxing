# Local Market Narrative Runtime V1

```powershell
$env:PYTHONPATH = "E:\IntelligenceMaxxxing\src"
python -m pytest tests/domain_packs/trading/market_narrative_v1 -q
```

Produce narratives by feeding a context snapshot dict into:

`intelligence_maxxxing.domain_packs.trading.market_narrative_v1.narrative_runtime_v1.run_narrative_runtime`

Do not attach outcomes. Do not call into FAMILY shadow decision paths.
