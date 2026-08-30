#!/bin/bash

set -e

PROJECT_DIR="$HOME/Downloads/work/GIT-uri/Youtube_Shorts/scripts/convert_audiofile_to_wav"

cd "$PROJECT_DIR"

echo "=============================================="
echo "       Building Audio_Converter"
echo "=============================================="
echo ""

# Activate virtual environment
if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found."
    echo ""
    echo "Run environment_setup.sh first."
    exit 1
fi

source .venv/bin/activate

# Verify Python
echo "Python:"
python --version

# Verify tkinter
python -c "import tkinter; print('Tkinter OK')"

# Verify tkinterdnd2
python -c "import tkinterdnd2; print('tkinterdnd2 OK')"

# Verify PyInstaller
pyinstaller --version

# Verify FFmpeg
echo ""
echo "FFmpeg:"
which ffmpeg

# Clean previous build
echo ""
echo "Cleaning previous build..."

rm -rf build
rm -rf dist
rm -f "Audio_Converter.spec"

# Build
echo ""
echo "Building application..."

pyinstaller \
    --windowed \
    --clean \
    --noconfirm \
    --name "Audio_Converter" \
    --collect-all tkinterdnd2 \
    audio_converter.py

# Verify
if [ ! -d "dist/Audio_Converter.app" ]; then
    echo ""
    echo "ERROR: Application build failed."
    exit 1
fi

echo ""
echo "=============================================="
echo "        BUILD COMPLETED SUCCESSFULLY"
echo "=============================================="
echo ""
echo "Application:"
echo "$PROJECT_DIR/dist/Audio_Converter.app"
echo ""

# Install
echo "Installing into /Applications..."

rm -rf "/Applications/Audio_Converter.app"

cp -R \
    "dist/Audio_Converter.app" \
    "/Applications/"

echo ""
echo "Installed:"
echo "/Applications/Audio_Converter.app"

echo ""
echo "Launching application..."

open -a "Audio_Converter"