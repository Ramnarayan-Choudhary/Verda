#!/bin/bash
# Setup script for IRIS service within VREDA
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Setting up IRIS Ideation Service ==="

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -q flask flask-socketio litellm openai loguru pymupdf anyascii pyyaml \
    numpy requests tqdm pandas fastapi nora-lib python-json-logger \
    langsmith tenacity retry

echo "=== IRIS setup complete ==="
echo ""
echo "To start the server:"
echo "  cd $SCRIPT_DIR"
echo "  source .venv/bin/activate"
echo "  GEMINI_API_KEY=your-key python server_wrapper.py"
echo ""
echo "Or with .env:"
echo "  cp .env.example .env  # then fill in GEMINI_API_KEY"
echo "  python server_wrapper.py"
