@echo off
cd /d "%~dp0"
echo Starting python backend...
python run.py
if errorlevel 1 pause