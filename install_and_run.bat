@echo off
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0install_and_run.ps1"
if errorlevel 1 pause
