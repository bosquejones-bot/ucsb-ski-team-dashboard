@echo off
title UCSB Ski & Snowboard Team Dashboard
echo ===================================================
echo   UCSB Ski ^& Snowboard Team Dashboard
echo ===================================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

if exist .venv\Scripts\activate.bat (
    echo Activating existing virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Creating .venv...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing dependencies from requirements.txt...
    pip install -r requirements.txt
)

echo Starting dashboard...
streamlit run app.py

pause
