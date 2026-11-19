@echo off
cd /d "%~dp0"
py -3 savesync.py
if errorlevel 1 pause
