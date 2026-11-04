@echo off
rem Opens the Star Trek interface (talk to the local AI, watch the overseer, see the latest edit). Starts Comfort first if it is not running.
curl -s -m 2 http://127.0.0.1:8790/api/state >nul 2>&1
if errorlevel 1 (
  start "" /min "%~dp0Comfort\Start Comfort.bat"
  timeout /t 8 /nobreak >nul
)
start "" http://127.0.0.1:8790/startrek
