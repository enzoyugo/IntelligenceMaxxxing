# Local Trading Assessment Service V1

```powershell
cd E:\IntelligenceMaxxxing
$env:PYTHONPATH="src;sdk\python"
$env:ENGINE_ENV="development"
$env:IM_TRADING_BRIDGE_TOKEN="tmx-im-local-bridge-v1"
python -m uvicorn --factory intelligence_maxxxing.api.app:create_app --host 127.0.0.1 --port 8100
```

Smoke: `GET /api/v1/trading/health` with `X-Trading-Bridge-Token`.
