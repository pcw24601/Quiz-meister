@echo off
REM Quiz-Meister launcher for Windows

cd /d "%~dp0"

python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

python start.py
pause
