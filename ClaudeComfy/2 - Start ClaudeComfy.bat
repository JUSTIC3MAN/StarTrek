@echo off
title ClaudeComfy (MiniMax H3)
set "PYTHONUTF8=1"
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH="
if not exist "%~dp0venv\Scripts\python.exe" (
    echo Run "1 - Setup ClaudeComfy.bat" first.
    pause
    exit /b 1
)
cd /d "%~dp0ComfyUI"
echo Starting ClaudeComfy on http://127.0.0.1:8189 ...
"%~dp0venv\Scripts\python.exe" -s main.py --enable-manager --enable-manager-legacy-ui --listen 127.0.0.1 --port 8189 --auto-launch %*
pause
