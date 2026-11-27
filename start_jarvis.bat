@echo off
title J.A.R.V.I.S. HUD Core
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_jarvis.py
) else if exist "C:\Users\Gaurav Rajput\AppData\Local\Python\bin\python.exe" (
    "C:\Users\Gaurav Rajput\AppData\Local\Python\bin\python.exe" run_jarvis.py
) else (
    python run_jarvis.py
)
pause
