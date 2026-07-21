# WELLBEING ISOLATED SMOKE INFRASTRUCTURE V1

## Old smoke target

Personal production Engine/BFF (`LIFEOS_BFF_URL` → Engine :8100)  
Observation retained: `obs_ab746ef9d6c64732990a6e7fc4aaea15`

## New smoke target

Temporary PostgreSQL database `intelligence_maxxxing_iso_smoke_<timestamp>`  
Engine on port **8117** (never 8100)  
TEST environment + SMOKE_TEST purpose + TEST_PROFILE subject_scope

## Scripts

| Script | Role |
|--------|------|
| `scripts/smoke/wellbeing_isolation_e2e.ps1` | Create DB → migrate → bootstrap identity → Engine → canary → destroy |
| `scripts/smoke/wellbeing_isolation_canary.py` | Reject PROD smoke; accept TEST smoke; assert exclusion counts |
| LifeOS `scripts/smoke/wellbeing_scale_contract_e2e.ps1` | Delegates to Engine isolated smoke; **refuses** non-isolated mode |

## Parameters

```powershell
.\scripts\smoke\wellbeing_scale_contract_e2e.ps1 -Isolated -KeepArtifacts:$false
```

`-KeepArtifacts` retains temp DB name + artifact JSON under `artifacts/isolation_smoke/`.

## Protections

- Abort if not Isolated  
- Abort if DATABASE_URL ends with production DB name without audit flag  
- Abort canary if URL contains port 8100  
- No personal subject reuse — generated `test-*` UUID  

## CI

Requires Docker PostgreSQL. If Docker unavailable: reproducible script remains; do **not** declare CI PASS for this job.

## Production ledger writes from new smoke

**None** (by design).
