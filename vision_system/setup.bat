@echo off
title NavHat PRO — Vision System Setup
echo ========================================================
echo   Setting up NavHat PRO v6.0 AI Vision Environment
echo ========================================================

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [1/3] Creating Python virtual environment (venv)...
if not exist "venv" (
    python -m venv venv
)

echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/3] Installing required packages from requirements.txt...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ========================================================
echo   Setup Complete! You can now run run.bat
echo ========================================================
pause
