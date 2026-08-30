# Convert Audio Files to WAV

`audio_converter.py` is a drag-and-drop desktop app (Tkinter + tkinterdnd2)
that extracts the audio track from one or more video/audio files (MP4 • M4A
• MOV • AAC • MP3 • WAV • MKV • FLAC • OGG) and re-encodes it as a mono,
48kHz, 16-bit PCM WAV file — a format that YouCut imports reliably.

## Setup

Run once to install Homebrew, Python, FFmpeg, Tcl/Tk, and create a virtual
environment (`.venv`) with the required Python packages (`tkinterdnd2`,
`pyinstaller`):

```bash
bash environment_setup.sh
```

## Build the app

Package `audio_converter.py` into a standalone `Audio_Converter.app` (via
PyInstaller) and install it into `/Applications`:

```bash
bash build_audio_converter_app.sh
```

## Usage

Either launch the built app (`/Applications/Audio_Converter.app`), or run the
script directly from the virtual environment:

```bash
source .venv/bin/activate
python audio_converter.py
```

Drag and drop files onto the window, then click **Convert**.

## Output

For each input file, an output file named `<original>_YouCut.wav` is created
next to it. If that name already exists, a numeric suffix (`_YouCut_1.wav`,
`_YouCut_2.wav`, ...) is used instead to avoid overwriting existing files.
