# Convert Audio File to WAV

`Convert_For_Youcut.py` extracts the audio track from one or more video/audio
files and re-encodes it as a mono, 48kHz, 16-bit PCM WAV file — a format that
YouCut imports reliably.

## Requirements

- `ffmpeg` installed (e.g. `brew install ffmpeg`)

## Usage

```bash
python3 Convert_For_Youcut.py video1.mp4 video2.mov audio.mp3
```

Files are typically passed by dragging & dropping them onto this script.

## Output

For each input file, an output file named `<original>_YouCut.wav` is created
next to it. If that name already exists, a numeric suffix (`_YouCut_1.wav`,
`_YouCut_2.wav`, ...) is used instead to avoid overwriting existing files.
