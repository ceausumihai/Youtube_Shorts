# YouTube Shorts Toolkit

Scripts to turn a vlog into ready-to-upload YouTube Shorts, plus a helper to
prepare audio for YouCut.

## Scripts

- [`scripts/create_youtube_shorts/`](scripts/create_youtube_shorts/README.md) —
  `auto_shorts.py` takes a video (from YouTube or a local file), transcribes it
  with Whisper, picks the best moments (automatically with Claude or manually
  from a JSON file), and cuts/reframes them into vertical 9:16 clips.
- [`scripts/convert_audiofile_to_wav/`](scripts/convert_audiofile_to_wav/README.md) —
  `audio_converter.py` is a drag-and-drop desktop app that extracts audio from
  video/audio files and re-encodes it as a WAV file compatible with YouCut.

See each subfolder's README for installation, configuration, and usage details.
