@echo off
title Krea 2 Identity Edit setup
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH="
if not exist "%~dp0venv\Scripts\python.exe" (
    echo Run "1 - Setup ClaudeComfy.bat" first.
    pause
    exit /b 1
)
echo === Downloading Krea 2 Identity Edit files (about 20 GB, resumes if interrupted) ===
echo.
"%~dp0venv\Scripts\python.exe" -s "%~dp0scripts\download_krea_edit_models.py"
if errorlevel 1 goto fail
echo.
echo Done. Start ComfyUI with "2 - Start ClaudeComfy.bat" and open "Krea 2 Identity Edit (ClaudeComfy)" from the Workflows sidebar.
pause
exit /b 0
:fail
echo.
echo Something failed - scroll up for the error, then run this file again. It picks up where it stopped.
pause
exit /b 1
