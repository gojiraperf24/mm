$ErrorActionPreference = 'Stop'
$gloveRoot = Join-Path $PSScriptRoot 'glove'
$pythonPath = Join-Path $gloveRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & py -3.12 -m venv (Join-Path $gloveRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Install 64-bit Python 3.12 and try again.' }
}
& $pythonPath -m pip install -r (Join-Path $gloveRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
Write-Host 'Setup complete. Double-click Start-Glove.cmd.'
