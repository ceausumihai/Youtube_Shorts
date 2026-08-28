#!/usr/bin/env python3
"""Convert video/audio files into WAV files compatible with YouCut.

Extracts the audio track from each input file and re-encodes it to a mono,
48kHz, 16-bit PCM WAV file (named "<original>_YouCut.wav"), which YouCut can
import reliably. Requires ffmpeg to be installed (e.g. `brew install ffmpeg`).

Usage:
    python3 Convert_For_Youcut.py video1.mp4 video2.mov audio.mp3

Files are typically passed by dragging & dropping them onto this script
(see Convert_For_YouCut.command for a double-clickable macOS wrapper).
"""

import sys
import subprocess
from pathlib import Path


SAMPLE_RATE = "48000"
CHANNELS = "1"
CODEC = "pcm_s16le"


def convert_file(input_file: Path):
    output_file = input_file.with_name(
        f"{input_file.stem}_YouCut.wav"
    )

    # Avoid overwriting existing files
    counter = 1
    while output_file.exists():
        output_file = input_file.with_name(
            f"{input_file.stem}_YouCut_{counter}.wav"
        )
        counter += 1

    print()
    print("=" * 60)
    print(f"Input : {input_file}")
    print(f"Output: {output_file}")
    print("=" * 60)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-i", str(input_file),
        "-vn",
        "-map", "0:a:0",
        "-c:a", CODEC,
        "-ar", SAMPLE_RATE,
        "-ac", CHANNELS,
        str(output_file),
    ]

    try:
        subprocess.run(command, check=True)

        print()
        print("✅ Conversie reușită!")
        print(f"   {output_file}")

        return True

    except subprocess.CalledProcessError:
        print()
        print("❌ Conversia a eșuat!")
        return False


def main():
    print()
    print("=" * 60)
    print("          YouCut Audio Converter")
    print("=" * 60)

    # Check if FFmpeg exists
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print()
        print("❌ FFmpeg nu este instalat.")
        print()
        print("Instalează-l cu:")
        print()
        print("    brew install ffmpeg")
        print()
        input("Apasă ENTER pentru a închide...")
        sys.exit(1)

    # Files received through drag & drop
    files = sys.argv[1:]

    if not files:
        print()
        print("❌ Nu ai selectat niciun fișier.")
        print()
        input("Apasă ENTER pentru a închide...")
        sys.exit(1)

    success = 0
    failed = 0

    for file in files:

        input_file = Path(file)

        if not input_file.exists():
            print(f"❌ Fișierul nu există: {input_file}")
            failed += 1
            continue

        if not input_file.is_file():
            print(f"❌ Nu este fișier: {input_file}")
            failed += 1
            continue

        if convert_file(input_file):
            success += 1
        else:
            failed += 1

    print()
    print("=" * 60)
    print("FINAL")
    print("=" * 60)
    print(f"✅ Reușite : {success}")
    print(f"❌ Eșuate  : {failed}")
    print()

    input("Apasă ENTER pentru a închide...")


if __name__ == "__main__":
    main()