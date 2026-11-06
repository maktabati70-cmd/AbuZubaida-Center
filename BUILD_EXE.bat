@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build AbuZubaida-Center.exe
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY goto nopy
%PY% build_exe.py
exit /b
:nopy
echo.
echo  Python is needed only once to build the exe.
echo  Download it from https://www.python.org/downloads/
echo  IMPORTANT: tick "Add python.exe to PATH" during setup, then run BUILD_EXE.bat again.
start "" https://www.python.org/downloads/
pause
