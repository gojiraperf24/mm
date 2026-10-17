param(
    [ValidateSet('esp32-direct','esp32-usb','esp32-bluetooth','esp32-two-hands','esp32-audio','nano-usb','nano-bluetooth')]
    [string[]]$Environment = @('esp32-direct'),
    [string]$UploadPort
)
$ErrorActionPreference = 'Stop'
# Espressif's GCC installation cannot reliably locate its subprograms when its
# own directory contains spaces. A temporary drive alias avoids changing files.
$driveName = @('Z','Y','X','W','V','U','T','S','R') | Where-Object { -not (Test-Path ($_.ToString() + ':\')) } | Select-Object -First 1
if (-not $driveName) { throw 'No free drive letter for the temporary compiler path alias.' }
$driveRoot = $driveName + ':\'
$priorCoreDir = $env:PLATFORMIO_CORE_DIR
& subst.exe ($driveName + ':') $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Could not create temporary compiler path alias.' }
try {
    $env:PLATFORMIO_CORE_DIR = $driveRoot + '.platformio'
    $firmwareArgs = @('run','--project-dir',($driveRoot + 'firmware'))
    foreach ($targetEnvironment in $Environment) { $firmwareArgs += @('-e',$targetEnvironment) }
    if ($UploadPort) { $firmwareArgs += @('-t','upload','--upload-port',$UploadPort) }
    & ($driveRoot + '.venv\Scripts\python.exe') ($driveRoot + 'tools\pio.py') @firmwareArgs
    if ($LASTEXITCODE -ne 0) { throw 'Firmware build/upload failed. See the first compiler error above.' }
} finally {
    & subst.exe ($driveName + ':') /D
    $env:PLATFORMIO_CORE_DIR = $priorCoreDir
}
