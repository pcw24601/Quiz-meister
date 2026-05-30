#!/bin/bash
# Quiz-Meister launcher for Linux/Mac

cd "$(dirname "$0")"

# Install dependencies if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "Installing dependencies..."
  pip3 install -r requirements.txt
fi

python3 start.py
