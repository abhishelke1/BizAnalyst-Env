#!/bin/bash
echo "========================================"
echo "  SCOUT AI - Autonomous Business Intelligence"
echo "========================================"
echo

# Kill any existing processes on port 7860
echo "Cleaning up old processes..."
lsof -ti:7860 | xargs kill -9 2>/dev/null
sleep 2

# Check for API key
if [ -z "$GROQ_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo
    echo "[ERROR] No API key found!"
    echo "Set one of these environment variables:"
    echo "  export GROQ_API_KEY=gsk_..."
    echo "  export OPENAI_API_KEY=sk-..."
    echo
    exit 1
fi

# Start the server
echo "Starting SCOUT AI server..."
echo
cd "$(dirname "$0")"
python scout_server.py
