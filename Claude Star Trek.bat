@echo off
title Claude - Star Trek
rem Opens Claude Code (the terminal version of Claude) in the Star Trek folder, so it reads CLAUDE.md and the manuals.
cd /d "%~dp0"
where claude >nul 2>&1 || set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where claude >nul 2>&1 || (echo. & echo   Claude Code is not installed. In PowerShell run:   irm https://claude.ai/install.ps1 ^| iex & echo. & pause & exit /b 1)
claude %*
