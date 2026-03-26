#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== ScreenMind Installer ==="
echo ""

# --- Check Python version (need 3.10+) ---
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

# Check /opt/homebrew/bin/ directly for Apple Silicon
if [ -z "$PYTHON" ]; then
    for candidate in /opt/homebrew/bin/python3.{14,13,12,11,10}; do
        if [ -x "$candidate" ]; then
            PYTHON="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ required but not found."
    echo "Install with: brew install python@3.13"
    exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Using Python $PY_VERSION ($PYTHON)"

# --- Check/install ffmpeg ---
if ! command -v ffmpeg &>/dev/null && ! [ -x /opt/homebrew/bin/ffmpeg ]; then
    echo "Installing ffmpeg..."
    brew install ffmpeg
else
    echo "ffmpeg: $(command -v ffmpeg || echo /opt/homebrew/bin/ffmpeg)"
fi

# --- Check/install tesseract (optional) ---
if ! command -v tesseract &>/dev/null && ! [ -x /opt/homebrew/bin/tesseract ]; then
    echo "Installing tesseract (for OCR)..."
    brew install tesseract || echo "WARNING: tesseract install failed — OCR will be unavailable"
else
    echo "tesseract: $(command -v tesseract || echo /opt/homebrew/bin/tesseract)"
fi

# --- Create venv ---
echo ""
echo "Creating virtual environment..."
"$PYTHON" -m venv "$VENV_DIR"

# --- Install dependencies ---
echo "Installing core dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo "Installing optional dependencies..."
"$VENV_DIR/bin/pip" install --quiet scikit-image pytesseract Pillow 2>/dev/null || \
    echo "WARNING: Some optional deps failed — SSIM dedup and/or OCR may be unavailable"

# --- Verify ---
echo ""
echo "Verifying server compiles..."
"$VENV_DIR/bin/python" -m py_compile "$SCRIPT_DIR/server.py"
echo "OK"

# --- Output registration command ---
VENV_PYTHON="$VENV_DIR/bin/python"
SERVER_PATH="$SCRIPT_DIR/server.py"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Register with Claude Code:"
echo ""
echo "  claude mcp add screenmind -- $VENV_PYTHON $SERVER_PATH"
echo ""
echo "=== macOS Screen Recording Permission ==="
echo ""
echo "For screenmind_record_start to capture your screen:"
echo "  1. System Settings → Privacy & Security → Screen Recording"
echo "  2. Click '+' and add: $(command -v ffmpeg || echo /opt/homebrew/bin/ffmpeg)"
echo "  3. Restart your terminal"
echo ""
echo "If recordings show a black screen, this permission is the cause."
