#!/bin/bash
set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh"
  exit 1
fi
brew install python ffmpeg tcl-tk 2>/dev/null || true
PYTHON="$(command -v python3)"
if ! "$PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
  echo "Tkinter is unavailable in $PYTHON. Install the matching Homebrew python-tk package, then rerun."
  exit 1
fi
"$PYTHON" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m tkinter >/dev/null 2>&1 || { echo "Tkinter test failed."; exit 1; }
python -c 'import tkinterdnd2; print("tkinterdnd2 OK")'
ffmpeg -version | head -1
