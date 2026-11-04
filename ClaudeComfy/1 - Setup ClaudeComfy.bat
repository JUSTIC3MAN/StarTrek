@echo off
title ClaudeComfy setup
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_claudecomfy.ps1"
echo.
pause
