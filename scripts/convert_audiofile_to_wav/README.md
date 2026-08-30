# Convert Audio Files to WAV

`audio_converter.py` extracts the audio track from one or more video/audio
files in these formats (MP4 • M4A • MOV • AAC • MP3 • WAV) and re-encodes it as a mono, 48kHz, 16-bit PCM WAV file

## Requirements

- Setup the development environment. Execute: setup_youcut_converter.sh
- Build the Audio Convertor APP. Execute: build_audio_converter_app.sh

## Usage

```bash
python audio_converter.py 
```

Files are typically passed by dragging & dropping them onto the UI.

## Output

For each input file, an output file named `<original>_YouCut.wav` is created
next to it. If that name already exists, a numeric suffix (`_YouCut_1.wav`,
`_YouCut_2.wav`, ...) is used instead to avoid overwriting existing files.
