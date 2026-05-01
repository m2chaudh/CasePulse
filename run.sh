#!/bin/bash
# CasePulse - Launch Script
# Usage: ./run.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Setting up..."
    python3.11 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    echo "Setup complete!"
fi

# Create data directories if needed
mkdir -p data/{tokens,attachments,db,chroma}

# Launch Streamlit
echo "Starting CasePulse..."
streamlit run Home.py --server.port 8501 --browser.gatherUsageStats false
