#!/usr/bin/env python3
"""
auto_shorts.py
==============
Automated pipeline: from a vlog (YouTube or local file) -> multiple
YouTube Shorts.

Steps:
    1. Get the source video: either download it from YouTube (yt-dlp),
       or use a file already on disk (--local-video), skipping the
       download
    2. Extract audio and transcribe it with timestamps (Whisper)
    3. Pick the best segments for Shorts (start/end + reason),
       either automatically via Claude (Anthropic API), or from a JSON
       file you supply (generated manually, e.g. with a free AI)
    4. Cut each segment with ffmpeg and reframe it into vertical 9:16 format

Requirements (installation):
    pip install yt-dlp openai-whisper anthropic --break-system-packages
    # ffmpeg must be installed at the system level (sudo apt install ffmpeg)
    # "yt-dlp" is only needed if you download from YouTube (not needed if
    # you always use --local-video)
    # "anthropic" is only needed for automatic clip selection with Claude
    # (not needed if you use --clips-json)

Required environment variables (only for automatic selection with Claude):
    ANTHROPIC_API_KEY   -> your key from console.anthropic.com

Usage examples:

    # Full, automatic variant, from YouTube (Claude picks the clips):
    python auto_shorts.py "https://www.youtube.com/watch?v=XXXXXXXX" \
        --num-clips 3 --clip-length 45 --output-dir ./shorts_output

    # Same variant, but starting from a video file already on disk
    # (no url, no yt-dlp):
    python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" \
        --num-clips 3 --clip-length 45 --output-dir ./shorts_output

    # Variant without Claude API, in two steps (also works with --local-video):
    # 1) only transcribe, then stop
    python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" \
        --transcript-only
    # (take _auto_shorts_work/transcript.json, give it to a free AI,
    #  ask for clips in the format {start, end, title, reason}, save clips.json)
    # 2) cut + format, using the already-chosen clips
    python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" --clips-json clips.json --output-dir ./shorts_output
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


# ----------------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------------

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class ClipCandidate:
    start: float
    end: float
    title: str
    reason: str


# ----------------------------------------------------------------------------
# Step 1: Getting the video (YouTube download OR local file)
# ----------------------------------------------------------------------------

def run_subprocess(cmd: List[str]) -> None:
    """Run an external command (ffmpeg/yt-dlp) and, if it fails, print the
    actual stdout/stderr before re-raising the error.

    subprocess.run(..., capture_output=True) hides useful error messages
    unless we print them explicitly - without this, an ffmpeg error only
    shows up as "returned non-zero exit status N", with no detail.
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nERROR running command: {' '.join(cmd)}")
        if result.stdout:
            print("--- stdout ---")
            print(result.stdout)
        if result.stderr:
            print("--- stderr ---")
            print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)


def download_video(url: str, workdir: Path) -> Path:
    """Download the YouTube video using yt-dlp and return the local path.

    Only called when the user did NOT provide --local-video (i.e. wants to
    download from YouTube instead of using an existing file).
    """
    print(f"[1/4] Downloading video from: {url}")
    output_template = str(workdir / "source.%(ext)s")

    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url,
    ]
    run_subprocess(cmd)

    video_path = workdir / "source.mp4"
    if not video_path.exists():
        # yt-dlp may save with a different extension in some cases
        candidates = list(workdir.glob("source.*"))
        if not candidates:
            raise FileNotFoundError("yt-dlp did not produce any video file.")
        video_path = candidates[0]

    print(f"    -> Video saved to: {video_path}")
    return video_path


# ----------------------------------------------------------------------------
# Step 2: Audio extraction + transcription with Whisper
# ----------------------------------------------------------------------------

def extract_audio(video_path: Path, workdir: Path) -> Path:
    """Extract the audio track as mono 16kHz wav (ideal for Whisper)."""
    audio_path = workdir / "audio.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        str(audio_path),
    ]
    run_subprocess(cmd)
    return audio_path


def transcribe_audio(audio_path: Path, model_size: str = "base") -> List[TranscriptSegment]:
    """Transcribe audio with Whisper and return segments with timestamps."""
    print("[2/4] Transcribing audio with Whisper (may take a few minutes)...")
    import whisper  # local import, to avoid forcing installation if the user is just reading the script

    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio_path), verbose=False)

    segments = [
        TranscriptSegment(start=seg["start"], end=seg["end"], text=seg["text"].strip())
        for seg in result["segments"]
    ]
    print(f"    -> {len(segments)} segments transcribed.")
    return segments


# ----------------------------------------------------------------------------
# Step 3: Picking the best clips with Claude
# ----------------------------------------------------------------------------

def pick_best_clips(
    segments: List[TranscriptSegment],
    num_clips: int,
    clip_length: int,
    api_key: Optional[str] = None,
) -> List[ClipCandidate]:
    """Send the transcript to Claude and get back the best segments."""
    print(f"[3/4] Picking the best {num_clips} segments with Claude...")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)  # uses ANTHROPIC_API_KEY if api_key=None

    # Build a numbered transcript with timestamps, so Claude can reference
    # the exact segments it chooses.
    transcript_text = "\n".join(
        f"[{seg.start:.1f}s -> {seg.end:.1f}s] {seg.text}" for seg in segments
    )

    system_prompt = (
        "You are an expert viral content editor for YouTube Shorts/TikTok. "
        "You receive the full transcript of a vlog, with timestamps. "
        "Your task is to pick the best moments for short clips "
        "(shorts), each with a complete story: a strong hook at the start, "
        "a climax, and a clear ending. "
        f"Each clip must be between {max(15, clip_length - 15)} and "
        f"{clip_length + 15} seconds long. "
        "Respond STRICTLY in JSON format (no extra text, no ``` ), "
        "as a list of objects with the fields: start (number, seconds), "
        "end (number, seconds), title (short catchy title for the Short), "
        "reason (why this moment works as a Short)."
    )

    user_prompt = (
        f"Pick exactly {num_clips} segments for Shorts from the following transcript:\n\n"
        f"{transcript_text}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    raw_text = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print("WARNING: Claude's response was not valid JSON. Raw response:")
        print(raw_text)
        raise e

    clips = [
        ClipCandidate(
            start=float(item["start"]),
            end=float(item["end"]),
            title=item.get("title", "short"),
            reason=item.get("reason", ""),
        )
        for item in parsed
    ]

    print("    -> Clips chosen:")
    for c in clips:
        print(f"       * {c.start:.1f}s - {c.end:.1f}s : {c.title}")

    return clips


def load_clips_from_json(json_path: Path) -> List[ClipCandidate]:
    """Load the chosen clips from a manually produced JSON file (e.g. with a free AI).

    Expected format (list of objects, the same format normally produced by
    Claude in pick_best_clips):

        [
          {
            "start": 125.0,
            "end": 168.5,
            "title": "Short title for the clip",
            "reason": "Why this moment works (optional)"
          },
          ...
        ]

    The "start" and "end" fields are in seconds, relative to the original
    video (same timestamps as in transcript.json).
    """
    print(f"[3/4] Loading clips from JSON file: {json_path}")

    if not json_path.exists():
        raise FileNotFoundError(f"File {json_path} does not exist.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("The JSON file must contain a non-empty list of clips.")

    clips = []
    for i, item in enumerate(data):
        if "start" not in item or "end" not in item:
            raise ValueError(f"Item {i} in the JSON is missing 'start'/'end'.")
        clips.append(
            ClipCandidate(
                start=float(item["start"]),
                end=float(item["end"]),
                title=item.get("title", f"clip_{i+1}"),
                reason=item.get("reason", ""),
            )
        )

    print("    -> Clips loaded:")
    for c in clips:
        print(f"       * {c.start:.1f}s - {c.end:.1f}s : {c.title}")

    return clips


# ----------------------------------------------------------------------------
# Step 4: Cutting + reframing to 9:16
# ----------------------------------------------------------------------------


def slugify(text: str) -> str:
    keep = [c if c.isalnum() else "_" for c in text.lower()]
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:50] or "clip"


def cut_and_format_clip(
    video_path: Path,
    clip: ClipCandidate,
    output_dir: Path,
) -> Path:
    """Cut the segment and reframe it vertically (9:16)."""
    duration = clip.end - clip.start
    slug = slugify(clip.title)
    raw_cut = output_dir / f"_tmp_{slug}.mp4"
    final_path = output_dir / f"{slug}.mp4"

    # 1) Cut the raw segment (no full re-encoding, just seek + copy when possible)
    run_subprocess(
        [
            "ffmpeg", "-y",
            "-ss", str(clip.start), "-i", str(video_path),
            "-t", str(duration),
            "-c:v", "libx264", "-c:a", "aac",
            str(raw_cut),
        ]
    )

    # 2) Reframe to 9:16 (centered crop + blurred background).
    #    Filter: scale the original to fill width 1080, center it on a
    #    blurred 1080x1920 background - a common style for Shorts/Reels.
    vf_filter = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=20:5[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )

    run_subprocess(
        [
            "ffmpeg", "-y",
            "-i", str(raw_cut),
            "-filter_complex", vf_filter,
            "-c:v", "libx264", "-c:a", "aac",
            "-preset", "medium", "-crf", "20",
            str(final_path),
        ]
    )

    raw_cut.unlink(missing_ok=True)

    return final_path


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Automatically generate YouTube Shorts from a vlog.")
    parser.add_argument("url", nargs="?", default=None,
                         help="Link to the source YouTube video (omit if using --local-video)")
    parser.add_argument("--local-video", default=None,
                         help="Path to a video file already on disk (skips the YouTube download). "
                              "Use EITHER url OR --local-video, never both.")
    parser.add_argument("--num-clips", type=int, default=3, help="How many shorts to generate")
    parser.add_argument("--clip-length", type=int, default=45, help="Target length of each clip (seconds)")
    parser.add_argument("--whisper-model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                         help="Whisper model size (larger = more accurate, but slower)")
    parser.add_argument("--output-dir", default="./shorts_output", help="Folder where results are saved")
    parser.add_argument("--anthropic-api-key", default=None, help="Anthropic API key (default: ANTHROPIC_API_KEY env var)")
    parser.add_argument("--clips-json", default=None,
                         help="Path to a JSON file with already-chosen clips (skips the Claude call in Step 3). "
                              "Format: list of {start, end, title, reason}.")
    parser.add_argument("--transcript-only", action="store_true",
                         help="Only download+transcribe and stop (useful when you want to generate clips.json manually).")
    args = parser.parse_args()

    if not args.url and not args.local_video:
        sys.exit("ERROR: provide either a YouTube link (url), or --local-video <path to file>.")
    if args.url and args.local_video:
        sys.exit("ERROR: use only one of url or --local-video, not both.")

    workdir = Path("./_auto_shorts_work")
    workdir.mkdir(exist_ok=True)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.local_video:
        # The video is already on disk -> skip yt-dlp entirely
        video_path = Path(args.local_video)
        if not video_path.exists():
            sys.exit(f"ERROR: video file {video_path} does not exist.")
        print(f"[1/4] Using local video: {video_path}")
    else:
        video_path = download_video(args.url, workdir)

    # Transcription is only needed if we want just the transcript, or if
    # we need to pick clips with Claude (which needs segments).
    # With --clips-json, the clips are already chosen, so we skip it.
    transcript_path = workdir / "transcript.json"
    segments: List[TranscriptSegment] = []
    if args.transcript_only or not args.clips_json:
        if transcript_path.exists():
            print(f"[2/4] Reusing existing transcript: {transcript_path}")
            segments = [
                TranscriptSegment(**item)
                for item in json.loads(transcript_path.read_text(encoding="utf-8"))
            ]
        else:
            audio_path = extract_audio(video_path, workdir)
            segments = transcribe_audio(audio_path, model_size=args.whisper_model)
            transcript_path.write_text(
                json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    else:
        print("[2/4] --clips-json provided, skipping transcription (segments not needed).")

    if args.transcript_only:
        print(f"\nTranscript saved to: {transcript_path}")
        print("Generate the clips file (format: list of start/end/title/reason) "
              "and run the script again with --clips-json <file>.")
        return

    if args.clips_json:
        clips = load_clips_from_json(Path(args.clips_json))
    else:
        api_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            sys.exit("ERROR: set the ANTHROPIC_API_KEY environment variable or use --anthropic-api-key "
                      "(or use --clips-json to avoid calling Claude)")
        clips = pick_best_clips(segments, args.num_clips, args.clip_length, api_key=api_key)

    print("[4/4] Cutting and reframing to 9:16 for each clip...")
    results = []
    for clip in clips:
        final_path = cut_and_format_clip(video_path, clip, output_dir)
        results.append((clip, final_path))
        print(f"    -> Generated: {final_path}")

    print("\n=== DONE ===")
    for clip, path in results:
        print(f"- {path.name}: {clip.title}\n    Reason: {clip.reason}")


if __name__ == "__main__":
    main()