# Auto Shorts — vlog (YouTube or local file) -> Shorts, automatically with AI

`auto_shorts.py` takes a video — either from YouTube or already on your
computer — and automatically produces 2-5 short clips (9:16, no subtitles).
Clip selection can be done either automatically by Claude, or manually by
giving the script a JSON file you produced yourself (e.g. with the help of a
free AI).

## Pipeline

1. Get the source video: either download it from YouTube (`yt-dlp`), or use
   a file already on disk (`--local-video`), skipping the download.
2. Extract the audio track and transcribe it with timestamps (Whisper).
3. Pick the best segments for Shorts (start/end + reason), either
   automatically via Claude (Anthropic API), or from a JSON file you supply
   (`--clips-json`).
4. Cut each segment with `ffmpeg` and reframe it into vertical 9:16 format.

## Installation (one time)

```bash
# 1. ffmpeg (if you don't already have it)
sudo apt install ffmpeg        # Linux
brew install ffmpeg            # Mac

# 2. Python packages
pip install yt-dlp openai-whisper anthropic --break-system-packages
# "yt-dlp" is only needed if you download from YouTube
# (not needed if you always use --local-video)
# "anthropic" is only needed for automatic clip selection with Claude
# (not needed if you always use --clips-json)
```

## Configuration (only for automatic selection with Claude)

You need an API key from https://console.anthropic.com/ (different from a
claude.ai subscription — the API is billed separately, per token used).

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

If you always pick clips manually (`--clips-json`), you can skip this step —
the script will never call Claude.

## Video source: YouTube or local file

Provide **either** a YouTube link, **or** `--local-video <path>` — never
both:

```bash
# From YouTube (downloads automatically with yt-dlp)
python auto_shorts.py "https://www.youtube.com/watch?v=XXXXXXXX" ...

# From a file already on disk (skips download)
python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" ...
```

All examples below work identically with either source — just replace
`<video-source>` with the YouTube link or with `--local-video <path>`.

## Running

### Option 1 — fully automatic (Claude picks the clips)

```bash
python auto_shorts.py <video-source> \
    --num-clips 3 \
    --clip-length 45 \
    --whisper-model base \
    --output-dir ./shorts_output
```

Concrete example with a local file:

```bash
python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" \
    --num-clips 3 --clip-length 45 --output-dir ./shorts_output
```

### Option 2 — no API costs, you pick the clips (with a free AI)

**Step 1** — only (download if needed and) transcribe, then stop:

```bash
python auto_shorts.py <video-source> --transcript-only
```

This produces `_auto_shorts_work/transcript.json` — a full transcript with
timestamps. Give this file to a free AI (ChatGPT, Gemini, etc.) and ask it to
pick the best moments for Shorts, in this format:

```json
[
  {
    "start": 125.0,
    "end": 168.5,
    "title": "Short title for the clip",
    "reason": "Why this moment works (optional)"
  }
]
```

Save the response as `clips.json`.

**Step 2** — cut + format, using the already-chosen clips:

```bash
python auto_shorts.py <video-source> \
    --clips-json clips.json \
    --output-dir ./shorts_output
```

> Note: if the source is a YouTube link, Step 2 re-downloads the video (no
> cache) — so it will take as long as the first run to download. Transcription
> however is fully skipped in Step 2 (no longer needed with `--clips-json`),
> and if you use `--local-video`, the step is even faster since the file is
> already on disk.

Result (both options): `.mp4` files ready to upload to YouTube Shorts appear
in `./shorts_output/`, with the title shown in the console too, along with
the reason for the choice.

## Useful parameters

| Parameter | What it does |
|---|---|
| `url` (positional) | YouTube link; omit it if using `--local-video` |
| `--local-video` | path to a video file already on disk; skips the YouTube download |
| `--num-clips` | how many shorts to generate (only for automatic selection with Claude) |
| `--clip-length` | target length (seconds) of each clip (only for automatic selection) |
| `--whisper-model` | `tiny`/`base` = fast, `small`/`medium`/`large` = more accurate but slower |
| `--clips-json` | path to a JSON file with already-chosen clips; skips the Claude call |
| `--transcript-only` | only get the transcript, then stop (useful for manually generating `clips.json`) |
| `--anthropic-api-key` | API key, if you don't want to put it in the environment variable |

## Notes

- The first run with Whisper downloads the model (a few hundred MB,
  depending on `--whisper-model`) — it takes a bit longer the first time.
- If the vlog has overlapping voices/background noise, `--whisper-model
  small` or `medium` gives much better transcripts than `base`.
- If `_auto_shorts_work/transcript.json` already exists, the script reuses it
  instead of re-transcribing the audio — delete it manually if you want a
  fresh transcription (e.g. with a different `--whisper-model`).
- The script deletes temporary files created during cutting, but keeps
  `transcript.json` in `_auto_shorts_work/` for debugging, regeneration, or
  to use with a free AI for clip selection.
- With `--local-video`, you don't need `yt-dlp` installed at all — just
  ffmpeg, Whisper, and (optionally) `anthropic`.
