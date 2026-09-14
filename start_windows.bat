@echo off
cd /d %~dp0
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Install Python 3.11 or newer from python.org and then double-click this file again.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
python run_dashboard.py
pause
