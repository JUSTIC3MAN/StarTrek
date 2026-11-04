@echo off
title ClaudeKrea setup
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "UV_LINK_MODE=copy"
echo === Installing Python packages for the Krea 2 node packs ===
"%~dp0tools\uv.exe" pip install --python "%~dp0venv\Scripts\python.exe" -c "%~dp0scripts\constraints.txt" --extra-index-url https://download.pytorch.org/whl/cu130 --index-strategy unsafe-best-match -r "%~dp0scripts\krea_requirements.txt"
if errorlevel 1 goto fail
echo.
echo === Downloading the uncensored Qwen3-VL-4B text encoder (4.8 GB) ===
"%~dp0venv\Scripts\python.exe" "%~dp0scripts\download_krea_models.py"
if errorlevel 1 goto fail
echo.
echo Done. Start ComfyUI with "2 - Start ClaudeComfy.bat" and open "Krea 2 RedCraft (ClaudeComfy)" from the Workflows sidebar.
pause
exit /b 0
:fail
echo.
echo Something failed - scroll up for the error, then run this file again.
pause
exit /b 1
