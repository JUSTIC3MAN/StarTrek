@echo off
setlocal
title Subtitle Studio - Lyrics inbox
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo.
    echo    Subtitle Studio isn't set up yet. Run Start.bat once first.
    echo.
    pause
    exit /b 1
)

venv\Scripts\python lyrics.py %*

echo.
echo    Lyrics inbox stopped.
pause
