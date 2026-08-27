#!/usr/bin/env python3
"""
auto_shorts.py
==============
Pipeline automatizat: dintr-un vlog (YouTube sau fisier local) -> mai multe
YouTube Shorts.

Etape:
    1. Obtine videoclipul sursa: fie il descarca de pe YouTube (yt-dlp),
       fie foloseste direct un fisier deja existent pe calculator
       (--local-video), sarind peste descarcare
    2. Extrage audio si il transcrie cu timestamp-uri (Whisper)
    3. Alege cele mai bune segmente pentru Shorts (inceput/sfarsit + motiv),
       fie automat prin Claude (Anthropic API), fie dintr-un fisier JSON
       furnizat de tine (generat manual, ex. cu un AI gratuit)
    4. Taie fiecare segment cu ffmpeg si il reincadreaza in format vertical 9:16

Cerinte (instalare):
    pip install yt-dlp openai-whisper anthropic --break-system-packages
    # ffmpeg trebuie sa fie instalat la nivel de sistem (sudo apt install ffmpeg)
    # "yt-dlp" e necesar DOAR daca descarci de pe YouTube (nu e nevoie daca
    # folosesti mereu --local-video)
    # "anthropic" e necesar DOAR daca folosesti alegerea automata cu Claude
    # (nu e nevoie daca folosesti --clips-json)

Variabile de mediu necesare (doar pentru alegerea automata cu Claude):
    ANTHROPIC_API_KEY   -> cheia ta de la console.anthropic.com

Exemple de utilizare:

    # Varianta completa, automata, de pe YouTube (Claude alege clipurile):
    python auto_shorts.py "https://www.youtube.com/watch?v=XXXXXXXX" \
        --num-clips 3 --clip-length 45 --output-dir ./shorts_output

    # Aceeasi varianta, dar pornind de la un fisier video deja pe disc
    # (fara url, fara yt-dlp):
    python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" \
        --num-clips 3 --clip-length 45 --output-dir ./shorts_output

    # Varianta fara API Claude, in doi pasi (functioneaza si cu --local-video):
    # 1) doar transcrie, apoi opreste-te
    python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" \
        --transcript-only
    # (iei _auto_shorts_work/transcript.json, il dai unui AI gratuit,
    #  ceri clipuri in formatul {start, end, title, reason}, salvezi clips.json)
    # 2) taiere + formatare, folosind clipurile deja alese
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
# Structuri de date
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
# Pasul 1: Obtinerea videoclipului (descarcare YouTube SAU fisier local)
# ----------------------------------------------------------------------------

def run_subprocess(cmd: List[str]) -> None:
    """Ruleaza o comanda externa (ffmpeg/yt-dlp) si, daca esueaza, afiseaza
    stdout/stderr-ul real inainte de a propaga eroarea.

    subprocess.run(..., capture_output=True) ascunde mesajele de eroare utile
    daca nu le afisam explicit - fara asta, o eroare ffmpeg apare doar ca
    "returned non-zero exit status N", fara niciun detaliu.
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nEROARE la rularea comenzii: {' '.join(cmd)}")
        if result.stdout:
            print("--- stdout ---")
            print(result.stdout)
        if result.stderr:
            print("--- stderr ---")
            print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)


def download_video(url: str, workdir: Path) -> Path:
    """Descarca videoclipul YouTube folosind yt-dlp si returneaza calea locala.

    Apelata doar cand utilizatorul NU a dat --local-video (adica vrea sa
    descarce de pe YouTube in loc sa foloseasca un fisier deja existent).
    """
    print(f"[1/4] Descarc videoclipul de la: {url}")
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
        # yt-dlp poate salva cu alta extensie in unele cazuri
        candidates = list(workdir.glob("source.*"))
        if not candidates:
            raise FileNotFoundError("yt-dlp nu a produs niciun fisier video.")
        video_path = candidates[0]

    print(f"    -> Video salvat la: {video_path}")
    return video_path


# ----------------------------------------------------------------------------
# Pasul 2: Extragere audio + transcriere cu Whisper
# ----------------------------------------------------------------------------

def extract_audio(video_path: Path, workdir: Path) -> Path:
    """Extrage pista audio in format wav mono 16kHz (ideal pentru Whisper)."""
    audio_path = workdir / "audio.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        str(audio_path),
    ]
    run_subprocess(cmd)
    return audio_path


def transcribe_audio(audio_path: Path, model_size: str = "base") -> List[TranscriptSegment]:
    """Transcrie audio cu Whisper si returneaza segmente cu timestamp-uri."""
    print("[2/4] Transcriu audio cu Whisper (poate dura cateva minute)...")
    import whisper  # import local, pentru a nu forta instalarea daca userul doar citeste scriptul

    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio_path), verbose=False)

    segments = [
        TranscriptSegment(start=seg["start"], end=seg["end"], text=seg["text"].strip())
        for seg in result["segments"]
    ]
    print(f"    -> {len(segments)} segmente transcrise.")
    return segments


# ----------------------------------------------------------------------------
# Pasul 3: Alegerea celor mai bune clipuri cu Claude
# ----------------------------------------------------------------------------

def pick_best_clips(
    segments: List[TranscriptSegment],
    num_clips: int,
    clip_length: int,
    api_key: Optional[str] = None,
) -> List[ClipCandidate]:
    """Trimite transcriptul catre Claude si primeste inapoi cele mai bune segmente."""
    print(f"[3/4] Aleg cele mai bune {num_clips} segmente cu ajutorul Claude...")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)  # foloseste ANTHROPIC_API_KEY daca api_key=None

    # Construim un transcript numerotat, cu timestamp-uri, ca sa poata Claude
    # sa refere exact segmentele alese.
    transcript_text = "\n".join(
        f"[{seg.start:.1f}s -> {seg.end:.1f}s] {seg.text}" for seg in segments
    )

    system_prompt = (
        "Esti un editor expert de continut viral pentru YouTube Shorts/TikTok. "
        "Primesti transcriptul complet al unui vlog, cu timestamp-uri. "
        "Sarcina ta este sa alegi cele mai bune momente pentru clipuri scurte "
        "(shorts), fiecare avand o poveste completa: un hook puternic la inceput, "
        "un punct culminant si o incheiere clara. "
        f"Fiecare clip trebuie sa aiba intre {max(15, clip_length - 15)} si "
        f"{clip_length + 15} secunde. "
        "Raspunde STRICT in format JSON (fara text suplimentar, fara ``` ), "
        "ca o lista de obiecte cu campurile: start (numar, secunde), "
        "end (numar, secunde), title (titlu scurt atragator pentru Short), "
        "reason (de ce acest moment functioneaza ca Short)."
    )

    user_prompt = (
        f"Alege exact {num_clips} segmente pentru Shorts din urmatorul transcript:\n\n"
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
        print("ATENTIE: raspunsul Claude nu a fost JSON valid. Raspuns brut:")
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

    print("    -> Clipuri alese:")
    for c in clips:
        print(f"       * {c.start:.1f}s - {c.end:.1f}s : {c.title}")

    return clips


def load_clips_from_json(json_path: Path) -> List[ClipCandidate]:
    """Incarca clipurile alese dintr-un fisier JSON produs manual (ex: cu un AI gratuit).

    Format asteptat (lista de obiecte, acelasi format pe care il produce
    normal Claude in pick_best_clips):

        [
          {
            "start": 125.0,
            "end": 168.5,
            "title": "Titlu scurt pentru Short",
            "reason": "De ce functioneaza acest moment (optional)"
          },
          ...
        ]

    Campurile "start" si "end" sunt in secunde, relative la videoclipul
    original (aceleasi timestamp-uri ca in transcript.json).
    """
    print(f"[3/4] Incarc clipurile din fisierul JSON: {json_path}")

    if not json_path.exists():
        raise FileNotFoundError(f"Fisierul {json_path} nu exista.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Fisierul JSON trebuie sa contina o lista nevida de clipuri.")

    clips = []
    for i, item in enumerate(data):
        if "start" not in item or "end" not in item:
            raise ValueError(f"Elementul {i} din JSON nu are 'start'/'end'.")
        clips.append(
            ClipCandidate(
                start=float(item["start"]),
                end=float(item["end"]),
                title=item.get("title", f"clip_{i+1}"),
                reason=item.get("reason", ""),
            )
        )

    print("    -> Clipuri incarcate:")
    for c in clips:
        print(f"       * {c.start:.1f}s - {c.end:.1f}s : {c.title}")

    return clips


# ----------------------------------------------------------------------------
# Pasul 4: Taiere + reincadrare 9:16
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
    """Taie segmentul si il reincadreaza vertical (9:16)."""
    duration = clip.end - clip.start
    slug = slugify(clip.title)
    raw_cut = output_dir / f"_tmp_{slug}.mp4"
    final_path = output_dir / f"{slug}.mp4"

    # 1) Taiem segmentul brut (fara re-encodare completa, doar seek + copy cand se poate)
    run_subprocess(
        [
            "ffmpeg", "-y",
            "-ss", str(clip.start), "-i", str(video_path),
            "-t", str(duration),
            "-c:v", "libx264", "-c:a", "aac",
            str(raw_cut),
        ]
    )

    # 2) Reincadram 9:16 (crop centrat + blur pe fundal).
    #    Filtrul: scalam originalul sa umple latimea 1080, il centram pe un
    #    fundal blurat de 1080x1920 - un stil comun pentru Shorts/Reels.
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
# Orchestrare
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Genereaza automat YouTube Shorts dintr-un vlog.")
    parser.add_argument("url", nargs="?", default=None,
                         help="Link-ul catre videoclipul YouTube sursa (omite-l daca folosesti --local-video)")
    parser.add_argument("--local-video", default=None,
                         help="Cale catre un fisier video deja existent pe calculator (sare peste descarcarea de pe YouTube). "
                              "Foloseste OR url, OR --local-video, niciodata amandoua.")
    parser.add_argument("--num-clips", type=int, default=3, help="Cate shorts sa genereze")
    parser.add_argument("--clip-length", type=int, default=45, help="Lungimea tinta a fiecarui clip (secunde)")
    parser.add_argument("--whisper-model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                         help="Marimea modelului Whisper (mai mare = mai precis, dar mai lent)")
    parser.add_argument("--output-dir", default="./shorts_output", help="Folderul unde se salveaza rezultatele")
    parser.add_argument("--anthropic-api-key", default=None, help="Cheia API Anthropic (implicit: variabila ANTHROPIC_API_KEY)")
    parser.add_argument("--clips-json", default=None,
                         help="Cale catre un fisier JSON cu clipurile deja alese (sare peste apelul Claude la Pasul 3). "
                              "Format: lista de {start, end, title, reason}.")
    parser.add_argument("--transcript-only", action="store_true",
                         help="Doar descarca+transcrie si opreste-te (util cand vrei sa generezi tu clips.json manual).")
    args = parser.parse_args()

    if not args.url and not args.local_video:
        sys.exit("EROARE: da fie un link YouTube (url), fie --local-video <cale catre fisier>.")
    if args.url and args.local_video:
        sys.exit("EROARE: foloseste doar unul dintre url sau --local-video, nu amandoua.")

    workdir = Path("./_auto_shorts_work")
    workdir.mkdir(exist_ok=True)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.local_video:
        # Videoclipul e deja pe disc -> sarim peste yt-dlp complet
        video_path = Path(args.local_video)
        if not video_path.exists():
            sys.exit(f"EROARE: fisierul video {video_path} nu exista.")
        print(f"[1/4] Folosesc videoclipul local: {video_path}")
    else:
        video_path = download_video(args.url, workdir)

    # Transcrierea e necesara doar daca vrem doar transcriptul, sau daca
    # trebuie sa alegem clipurile cu Claude (are nevoie de segmente).
    # Cu --clips-json, clipurile sunt deja alese, deci sarim peste ea.
    transcript_path = workdir / "transcript.json"
    segments: List[TranscriptSegment] = []
    if args.transcript_only or not args.clips_json:
        if transcript_path.exists():
            print(f"[2/4] Refolosesc transcriptul existent: {transcript_path}")
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
        print("[2/4] --clips-json furnizat, sar peste transcriere (nu mai e nevoie de segmente).")

    if args.transcript_only:
        print(f"\nTranscript salvat la: {transcript_path}")
        print("Genereaza fisierul cu clipuri (format: lista de start/end/title/reason) "
              "si ruleaza din nou scriptul cu --clips-json <fisier>.")
        return

    if args.clips_json:
        clips = load_clips_from_json(Path(args.clips_json))
    else:
        api_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            sys.exit("EROARE: seteaza variabila de mediu ANTHROPIC_API_KEY sau foloseste --anthropic-api-key "
                      "(sau foloseste --clips-json pentru a evita apelul catre Claude)")
        clips = pick_best_clips(segments, args.num_clips, args.clip_length, api_key=api_key)

    print("[4/4] Taiere si reincadrare 9:16 pentru fiecare clip...")
    results = []
    for clip in clips:
        final_path = cut_and_format_clip(video_path, clip, output_dir)
        results.append((clip, final_path))
        print(f"    -> Generat: {final_path}")

    print("\n=== GATA ===")
    for clip, path in results:
        print(f"- {path.name}: {clip.title}\n    Motiv: {clip.reason}")


if __name__ == "__main__":
    main()