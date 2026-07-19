# Verifies the SHA-256 constitutional manifest. Exits non-zero on any mismatch.
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

Write-Host "== Constitutional manifest verification ==" -ForegroundColor Cyan

python -c @"
import sys
from pathlib import Path
from intelligence_maxxxing.governance import verify_manifest

result = verify_manifest(Path('docs/constitutional'))
for path in result.matched:
    print(f'  OK        {path}')
for path in result.mismatched:
    print(f'  MISMATCH  {path}')
for path in result.missing_files:
    print(f'  MISSING   {path}')
for path in result.unlisted_files:
    print(f'  UNLISTED  {path}')

if result.ok:
    print(f'Manifest verified: {len(result.matched)} constitutional files intact.')
    sys.exit(0)
print('CONSTITUTIONAL MANIFEST VERIFICATION FAILED', file=sys.stderr)
sys.exit(1)
"@
if ($LASTEXITCODE -ne 0) {
    Write-Error "Constitutional manifest verification failed."
}
Write-Host "Constitution intact." -ForegroundColor Green
