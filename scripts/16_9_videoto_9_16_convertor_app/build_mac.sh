#!/bin/bash
set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
source .venv/bin/activate
rm -rf build dist "Auto Shorts 9:16.spec"
pyinstaller \
  --windowed \
  --clean \
  --noconfirm \
  --name "Auto Shorts 9:16" \
  --collect-all tkinterdnd2 \
  AutoShorts9x16App.py
printf '\nBuilt: %s\n' "$PROJECT_DIR/dist/Auto Shorts 9:16.app"
