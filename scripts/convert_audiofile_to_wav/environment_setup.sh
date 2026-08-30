#!/bin/bash

set -e

echo "=============================================="
echo "     YouCut Converter - Environment Setup"
echo "=============================================="
echo ""

# --------------------------------------------------
# 1. Install Homebrew
# --------------------------------------------------

if ! command -v brew >/dev/null 2>&1; then
    echo "Installing Homebrew..."

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Configure Homebrew for Apple Silicon
if [ -x "/opt/homebrew/bin/brew" ]; then
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

echo ""
echo "Homebrew:"
brew --version | head -1


# --------------------------------------------------
# 2. Install latest Homebrew Python + dependencies
# --------------------------------------------------

echo ""
echo "Installing Python, FFmpeg and Tcl/Tk..."

brew update
brew install python ffmpeg tcl-tk || echo "Some formulas may already be installed, continuing..."


# --------------------------------------------------
# 3. Find Python
# --------------------------------------------------

PYTHON="$(command -v python3)"

if [ -z "$PYTHON" ]; then
    echo ""
    echo "ERROR: python3 was not found."
    exit 1
fi

echo ""
echo "Python found:"
echo "$PYTHON"

echo ""
echo "Python version:"
"$PYTHON" --version


# --------------------------------------------------
# 4. Check Tkinter
# --------------------------------------------------

echo ""
echo "Checking Tkinter..."

if "$PYTHON" -c "import tkinter" >/dev/null 2>&1; then

    echo "Tkinter: OK"

else

    echo ""
    echo "ERROR: Tkinter is not available in this Python."
    echo ""
    echo "Python:"
    echo "$PYTHON"
    echo ""
    echo "This usually means the Python distribution does not"
    echo "contain a usable Tk framework."
    echo ""
    echo "Tcl/Tk installed at:"
    brew --prefix tcl-tk
    echo ""
    echo "Please check your Python/Tk installation."
    exit 1

fi


# --------------------------------------------------
# 5. Locate project
# --------------------------------------------------

PROJECT_DIR="$HOME/Downloads/work/GIT-uri/Youtube_Shorts/scripts/convert_audiofile_to_wav"

echo ""
echo "Project directory:"
echo "$PROJECT_DIR"

if [ ! -d "$PROJECT_DIR" ]; then

    echo ""
    echo "ERROR: Project directory does not exist."
    echo ""
    echo "Create/clone the project first, or modify:"
    echo ""
    echo "$PROJECT_DIR"

    exit 1
fi

cd "$PROJECT_DIR"


# --------------------------------------------------
# 6. Create virtual environment
# --------------------------------------------------

echo ""
echo "Creating Python virtual environment..."

if [ ! -d ".venv" ]; then

    "$PYTHON" -m venv .venv

else

    echo ".venv already exists."

fi


# --------------------------------------------------
# 7. Activate virtual environment
# --------------------------------------------------

source .venv/bin/activate


# --------------------------------------------------
# 8. Upgrade pip
# --------------------------------------------------

echo ""
echo "Updating pip..."

python -m pip install --upgrade pip


# --------------------------------------------------
# 9. Install Python dependencies
# --------------------------------------------------

echo ""
echo "Installing Python packages..."

python -m pip install \
    tkinterdnd2 \
    pyinstaller || echo "Some packages may already be installed, continuing..."


# --------------------------------------------------
# 10. Verify dependencies
# --------------------------------------------------

echo ""
echo "=============================================="
echo "Checking dependencies"
echo "=============================================="

echo ""
echo "Python:"
python --version

echo ""
echo "Tkinter:"
python -c "import tkinter; print('OK')"

echo ""
echo "tkinterdnd2:"
python -c "import tkinterdnd2; print('OK')"

echo ""
echo "PyInstaller:"
pyinstaller --version

echo ""
echo "FFmpeg:"
which ffmpeg
ffmpeg -version | head -1


# --------------------------------------------------
# 11. Test application
# --------------------------------------------------

echo ""
echo "=============================================="
echo "Testing application"
echo "=============================================="
echo ""

if [ ! -f "Audio_Converter.py" ]; then

    echo "ERROR: Audio_Converter.py was not found."
    exit 1

fi

echo "Starting application..."
echo ""

python Audio_Converter.py