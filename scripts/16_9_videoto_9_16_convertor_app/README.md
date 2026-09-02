# Auto Shorts 9:16 — macOS App

A macOS GUI for the existing `auto_shorts.py` pipeline.

## Features

- Drag and drop one or more 16:9 source videos into the window.
- Enter **Start time (seconds)** and **Short duration (seconds)**.
- Validates that the source is approximately 16:9.
- Validates that the requested segment fits within the source duration.
- Uses the existing `auto_shorts.py` clip JSON format (`start` / `end`).
- Calls the existing `auto_shorts.py` 9:16 reframing function.
- Saves the output beside the source as `OriginalName_9_16.mp4`.
- Does not overwrite an existing output; it creates `_9_16_1`, `_9_16_2`, etc.
- Shows the actual FFmpeg / Python output in an in-app **Conversion log**.
- Saves a `.auto_shorts_9_16.log` beside the first source video for troubleshooting.
- Includes **Open Output Folder** and **Open log file** buttons.
- Works when launched from Finder because the GUI discovers an absolute FFmpeg path and passes it into `auto_shorts.py`.
- The GUI imports `auto_shorts.py` directly instead of spawning `python3`, avoiding interpreter/venv mismatches.

## Setup on a new Mac

Run:

```bash
./setup_mac.sh
```

Activate the venv and test:

```bash
source .venv/bin/activate
python AutoShorts9x16App.py
```

Build the app:

```bash
./build_mac.sh
```

The app will be created at:

```text
dist/Auto Shorts 9:16.app
```

## Expected input/output

Example source:

```text
/Users/me/Videos/Vacation.mp4
```

With:

```text
Start time: 125
Duration: 45
```

the app produces:

```text
/Users/me/Videos/Vacation_9_16.mp4
```

The existing `auto_shorts.py` reframing style is preserved: 1080x1920 output with a blurred background and centered foreground video.
