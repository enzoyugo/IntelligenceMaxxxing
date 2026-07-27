# Local Contextual Family Shadow Inference V1

## Preconditions

- IM live/research health 200
- TMX shadow start manifest present
- Policy/M2 unchanged

## Role of IM

Research documentation and future optional assessment provenance only.  
Live Policy IM must **not** consume FAMILY shadow decisions for control.

## Verify freeze (TMX)

```powershell
cd E:\TradingMaxxxing_V2
$env:PYTHONPATH='src'
python -c "import json; from pathlib import Path; p=Path('data/processed/research/trusted_contextual_family_multi_lane_shadow_v1/candidate_executable_freeze_manifest.json'); print(json.loads(p.read_text())['freeze_gate_pass'])"
```
