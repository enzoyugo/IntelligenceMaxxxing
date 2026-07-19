# Builds the standalone public client wheel and certifies it contains no Engine Core.
# Output: dist/sdk/intelligence_maxxxing_client-<version>-py3-none-any.whl
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

function Fail($Message) {
    Write-Host "SDK BUILD FAILED: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "==> Ensuring build tooling (build, setuptools, wheel)..."
python -m pip install --quiet build setuptools wheel
if ($LASTEXITCODE -ne 0) { Fail "could not install build tooling" }

$outDir = "dist/sdk"
if (Test-Path $outDir) { Get-ChildItem "$outDir/*.whl" -ErrorAction SilentlyContinue | Remove-Item -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "==> Building wheel from sdk/python (no build isolation)..."
python -m build --wheel --no-isolation --outdir $outDir sdk/python
if ($LASTEXITCODE -ne 0) { Fail "wheel build failed" }

$wheel = Get-ChildItem "$outDir/*.whl" | Select-Object -First 1
if (-not $wheel) { Fail "no wheel produced" }

Write-Host "==> Certifying wheel does not contain the Engine Core..."
$check = @"
import sys, zipfile, hashlib
w = r'$($wheel.FullName)'
z = zipfile.ZipFile(w)
names = z.namelist()
core = [n for n in names if n.startswith('intelligence_maxxxing/') or n.startswith('src/') or n.startswith('intelligence_maxxxing-')]
if core:
    print('CORE ENTRIES FOUND:', core); sys.exit(1)
pkgs = sorted({n.split('/')[0] for n in names if '/' in n and not n.endswith('.dist-info')})
print('packages:', pkgs)
print('sha256:', hashlib.sha256(open(w, 'rb').read()).hexdigest())
"@
python -c $check
if ($LASTEXITCODE -ne 0) { Fail "wheel contains Engine Core" }

Write-Host "SDK WHEEL BUILT AND CERTIFIED (no Core): $($wheel.Name)" -ForegroundColor Green
exit 0
