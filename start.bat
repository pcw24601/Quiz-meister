@echo off
REM Quiz-Meister launcher for Windows

cd /d "%~dp0"

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: uv is not installed or not found on PATH.
    echo Please install uv (https://docs.astral.sh/uv/):
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

uv run python start.py
pause
