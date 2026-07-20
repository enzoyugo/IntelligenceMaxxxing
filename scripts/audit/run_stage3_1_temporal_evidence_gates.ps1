# Stage 3.1 temporal + evidence hardening gates (real PostgreSQL when available).
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))

Write-Host "== Stage 3.1 unit suites =="
$env:ENGINE_ENV = "test"
python -m pytest -q `
  tests/unit/test_temporal_eligibility.py `
  tests/unit/test_source_identity.py `
  tests/unit/test_terminal_state_machine.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Stage 3.1 canary scan (no future-dated hacks) =="
python -c @"
from pathlib import Path
text = Path('scripts/audit/stage3_epistemic_e2e_canaries.py').read_text(encoding='utf-8')
forbidden = ['datetime.now(UTC) + timedelta(days=', 'now + timedelta(days=']
hits = [f for f in forbidden if f in text]
if hits:
    raise SystemExit(f'STAGE3_CANARIES_CONTAIN_NO_FUTURE_DATED_OBSERVATION_HACK failed: {hits}')
print('STAGE3_CANARIES_CONTAIN_NO_FUTURE_DATED_OBSERVATION_HACK ok')
"@
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== ControlledTestClock production guard =="
python -c @"
import os
os.environ['ENGINE_ENV'] = 'production'
from intelligence_maxxxing.infrastructure.clock.controlled_test_clock import ControlledTestClock
try:
    ControlledTestClock()
    raise SystemExit('PRODUCTION_RUNTIME_CANNOT_USE_CONTROLLED_TEST_CLOCK failed')
except RuntimeError as exc:
    assert 'ENGINE_ENV=test' in str(exc)
print('PRODUCTION_RUNTIME_CANNOT_USE_CONTROLLED_TEST_CLOCK ok')
"@
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Epistemic smoke =="
python -m pytest -q tests/integration/test_epistemic_smoke.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Stage 3.1 temporal evidence gates PASSED"
exit 0
