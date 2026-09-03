@echo off
title NavHat PRO v6.0 — Vision System
echo ========================================================
echo   Launching NavHat PRO v6.0 Vision System
echo ========================================================

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python navhat_vision.py
pause
