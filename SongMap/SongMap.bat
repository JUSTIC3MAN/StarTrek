@echo off
title SongMap
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    call setup.bat
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
if not "%~1"=="" venv\Scripts\python.exe songmap.py --add %*
venv\Scripts\python.exe songmap.py
echo.
echo    SongMap stopped.
pause
