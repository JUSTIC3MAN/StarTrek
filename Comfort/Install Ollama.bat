@echo off
setlocal
title Comfort - installing Ollama + qwen3.6:27b
cd /d "%~dp0"
set "LOG=%~dp0install_ollama.log"
set "OLL=%LOCALAPPDATA%\Programs\Ollama"
echo [%date% %time%] start> "%LOG%"
if exist "%OLL%\ollama.exe" goto installed
echo Downloading OllamaSetup.exe (1.6 GB) from github.com/ollama/ollama ...
echo downloading installer>> "%LOG%"
curl.exe -L --fail -o "%TEMP%\OllamaSetup.exe" https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe
if errorlevel 1 (echo DOWNLOAD FAILED>> "%LOG%" & goto fail)
echo Installing Ollama (silent) ...
echo installing>> "%LOG%"
"%TEMP%\OllamaSetup.exe" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
if not exist "%OLL%\ollama.exe" (echo INSTALL FAILED>> "%LOG%" & goto fail)
:installed
echo installed>> "%LOG%"
curl.exe -s http://127.0.0.1:11434/api/version >nul 2>&1 || start "" "%OLL%\ollama app.exe"
set /a n=0
:wait
curl.exe -s http://127.0.0.1:11434/api/version >nul 2>&1 && goto up
set /a n+=1
if %n% gtr 60 (echo SERVER DID NOT START>> "%LOG%" & goto fail)
timeout /t 2 /nobreak >nul
goto wait
:up
echo server up>> "%LOG%"
echo Downloading qwen3.6:27b (about 18-19 GB) - progress is in pull_progress.log ...
echo pulling qwen3.6:27b>> "%LOG%"
"%OLL%\ollama.exe" pull qwen3.6:27b > "%~dp0pull_progress.log" 2>&1
if errorlevel 1 (echo PULL FAILED>> "%LOG%" & goto fail)
echo pulled>> "%LOG%"
echo Testing speed, image input and tool calling ...
curl.exe -s http://127.0.0.1:11434/api/chat -H "Content-Type: application/json" -d @ollama_test_request.json -o ollama_test_result.json
"%OLL%\ollama.exe" list>> "%LOG%" 2>&1
echo READY>> "%LOG%"
echo.
echo Ollama and qwen3.6:27b are ready. You can close this window.
pause
exit /b 0
:fail
echo Something failed - see install_ollama.log
pause
exit /b 1
