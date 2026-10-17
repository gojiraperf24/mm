param([switch]$Firmware)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run Setup-Glove.ps1 first.' }
Push-Location $projectRoot
try {
    & $pythonPath -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    & $pythonPath tools\demo_check.py
    if ($LASTEXITCODE -ne 0) { throw 'Integration check failed' }
    & $pythonPath app.py --smoke-test artifacts\gui
    if ($LASTEXITCODE -ne 0) { throw 'GUI check failed' }
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot 'build\pyinstaller-cache'
    $vocabAsset = Join-Path $projectRoot 'vocabulary.json'
    $speechAsset = Join-Path $projectRoot 'speech_worker.ps1'
    $voiceAsset = Join-Path $projectRoot 'vendor\espeak-ng'
    & $pythonPath -m PyInstaller --noconfirm --clean --onedir --windowed --name GloveStudio --distpath release --workpath build --specpath build --add-data "$vocabAsset;." --add-data "$speechAsset;." --add-data "$voiceAsset;vendor\espeak-ng" --hidden-import training --hidden-import transport --hidden-import sklearn.ensemble._forest --collect-submodules scipy._external.array_api_compat --collect-submodules scipy._external.array_api_extra --collect-submodules sklearn.externals.array_api_compat app.py
    if ($LASTEXITCODE -ne 0) { throw 'Application packaging failed' }
    Copy-Item -LiteralPath 'vocabulary.json' -Destination 'release\GloveStudio\vocabulary.json' -Force
    if ($Firmware) {
        & (Join-Path $projectRoot 'Invoke-Firmware.ps1')
    }
} finally { Pop-Location }
