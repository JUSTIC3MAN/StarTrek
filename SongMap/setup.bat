@echo off
setlocal enabledelayedexpansion
title SongMap - setup
cd /d "%~dp0"
if not exist logs mkdir logs

set "CUDA=%~1"
if "%CUDA%"=="" set "CUDA=cu128"

echo.
echo    SongMap - first-time setup
echo    ==================================================
echo    Installs PyTorch (%CUDA%) and the music models' code into a private
echo    "venv" folder here, then downloads SongFormer (about 2.8 GB) and Beat This!.
echo    Lyrics use Subtitle Studio's models, so nothing is downloaded twice.
echo    Expect 5-20 minutes, once.
echo.

rem ---- find Python 3.12 (3.11 / 3.13 also work) ----------------------------
set "PY="
py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if not defined PY if exist "C:\Program Files\Python312\python.exe" set "PY="C:\Program Files\Python312\python.exe""
if not defined PY py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
if not defined PY py -3.13 -c "import sys" >nul 2>&1 && set "PY=py -3.13"
if not defined PY (
    echo    Python 3.12 was not found. Install it from https://www.python.org/downloads/release/python-3129/
    goto :fail
)
echo    Using: %PY%

if not exist "venv\Scripts\python.exe" (
    echo.
    echo    Creating the private Python environment...
    %PY% -m venv venv || goto :fail
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet

echo.
echo    [1/4] PyTorch with CUDA (%CUDA%) - about 3 GB (instant if Subtitle Studio's copy is in pip's cache)...
pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/%CUDA% --log logs\setup_pip.log
if errorlevel 1 (
    echo    Pinned PyTorch not available - installing the newest CUDA build instead...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/%CUDA% --log logs\setup_pip.log || goto :fail
)
python -c "import torch;print('          torch', torch.__version__, '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"
pip freeze | findstr /b /i "torch" > constraints.txt

echo.
echo    [2/4] SongFormer, Beat This! and the analysis packages...
pip install -r requirements.txt -c constraints.txt --log logs\setup_pip.log || goto :fail

echo.
echo    [3/4] Downloading the models...
python tools\fetch_models.py || goto :fail

echo.
echo    [4/4] Checking everything on the GPU...
python tools\check.py
if errorlevel 1 (
    echo.
    echo    Setup finished, but a check failed - see setup_check.txt. SongMap still runs;
    echo    the failed part falls back to a simpler method and the sheet says so.
    exit /b 0
)
echo.
echo    Setup finished.
exit /b 0

:fail
echo.
echo    Setup stopped - the reason is in the lines above (and logs\setup_pip.log).
echo    Run setup.bat again after fixing it; finished steps are skipped.
echo.
exit /b 1
