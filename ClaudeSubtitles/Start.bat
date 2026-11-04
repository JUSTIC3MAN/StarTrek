@echo off
setlocal
title Subtitle Animator
cd /d "%~dp0"

rem --- find a Python we can use -------------------------------------------
set PY=
where py >nul 2>nul && set PY=py
if not defined PY (where python >nul 2>nul && set PY=python)
if not defined PY (where python3 >nul 2>nul && set PY=python3)

if not defined PY (
  echo.
  echo   Python isn't installed, or isn't on your PATH.
  echo.
  echo   Install it from https://www.python.org/downloads/
  echo   and tick "Add python.exe to PATH" during setup.
  echo.
  pause
  exit /b 1
)

rem --- ffmpeg is optional but needed for .mov output ----------------------
where ffmpeg >nul 2>nul
if errorlevel 1 (
  if not exist "%~dp0bin\ffmpeg.exe" (
    echo.
    echo   Heads up: ffmpeg wasn't found, so .mov export is disabled.
    echo   PNG sequence export still works and imports fine into After Effects.
    echo.
    echo   To enable .mov:  winget install Gyan.FFmpeg
    echo   ...then close and reopen this window.
    echo.
  )
)

%PY% server.py %*

echo.
echo   Server stopped.
pause
