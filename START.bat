@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Abu Zubaida OSINT Center
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY goto nopy
%PY% start.py
if errorlevel 1 pause
exit /b
:nopy
echo.
echo  Python is not installed on this computer.
echo  Download it from https://www.python.org/downloads/
echo  IMPORTANT: during setup tick "Add python.exe to PATH".
echo  Then run START.bat again.
echo.
start "" https://www.python.org/downloads/
pause
