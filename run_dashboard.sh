#!/bin/bash
cd "$(dirname "$0")"

if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Python 3 is required but not installed."
    exit 1
fi

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

streamlit run app.py

