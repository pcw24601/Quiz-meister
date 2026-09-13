#!/bin/bash
# Quiz-Meister launcher for Linux/Mac

cd "$(dirname "$0")"

if command -v uv &>/dev/null; then
    uv run python start.py
else
    echo "Error: uv is not installed or not found on PATH."
    echo "Please install uv (https://docs.astral.sh/uv/):"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
