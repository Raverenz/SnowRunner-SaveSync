@echo off
cd /d "%~dp0"
py -3 host_packer_app.py
if errorlevel 1 pause
