param([Parameter(Mandatory=$true)][string]$Port, [ValidateSet('esp32-direct','esp32-usb','esp32-bluetooth','esp32-two-hands','esp32-audio')][string]$Environment='esp32-direct')
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Invoke-Firmware.ps1') -Environment @($Environment) -UploadPort $Port
