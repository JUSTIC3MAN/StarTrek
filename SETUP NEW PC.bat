@echo off
title Star Trek - new PC setup
rem One-time setup of Star Trek on a new Windows PC. Safe to run again (finished steps are skipped, downloads resume).
rem Read README.md first. Log: setup\setup_log.txt
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\setup_startrek.ps1" %*
echo.
pause
