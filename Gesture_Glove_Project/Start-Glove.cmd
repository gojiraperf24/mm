@echo off
setlocal
cd /d "%~dp0"
if exist "glove\release\GloveStudio\GloveStudio.exe" (
  start "" "glove\release\GloveStudio\GloveStudio.exe"
  exit /b 0
)
if exist "glove\.venv\Scripts\pythonw.exe" (
  start "" "glove\.venv\Scripts\pythonw.exe" "glove\app.py"
  exit /b 0
)
echo Run Setup-Glove.ps1 from PowerShell first.
pause
