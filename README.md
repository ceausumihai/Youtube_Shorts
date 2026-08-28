# Auto Shorts — vlog (YouTube sau fisier local) -> Shorts, automat cu AI

Script Python care ia un videoclip — de pe YouTube SAU deja de pe calculatorul
tău — și produce automat 2-5 clipuri scurte (9:16, fără subtitrări). Alegerea
clipurilor se poate face fie automat prin Claude, fie manual, dându-i
scriptului un fișier JSON produs de tine (ex. cu ajutorul unui AI gratuit).

## Instalare (o singură dată)

```bash
# 1. ffmpeg (dacă nu îl ai deja)
sudo apt install ffmpeg        # Linux
brew install ffmpeg            # Mac

# 2. pachetele Python
pip install yt-dlp openai-whisper anthropic --break-system-packages
# "yt-dlp" e necesar DOAR daca descarci de pe YouTube
# (nu e nevoie daca folosesti mereu --local-video)
# "anthropic" e necesar DOAR daca folosesti alegerea automata cu Claude
# (nu e nevoie daca folosesti mereu --clips-json)
```

## Configurare (doar pentru alegerea automată cu Claude)

Ai nevoie de o cheie API de la https://console.anthropic.com/ (diferită de un
abonament claude.ai — API-ul se plătește separat, per token folosit).

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Dacă alegi mereu clipurile manual (`--clips-json`), poți sări peste acest pas
— scriptul nu va apela deloc Claude.

## Sursa videoclipului: YouTube sau fișier local

Dă **fie** un link YouTube, **fie** `--local-video <cale>` — niciodată
amândouă:

```bash
# De pe YouTube (descarca automat cu yt-dlp)
python auto_shorts.py "https://www.youtube.com/watch?v=XXXXXXXX" ...

# Dintr-un fisier deja pe calculator (sare peste descarcare)
python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" ...
```

Toate exemplele de mai jos funcționează identic cu ambele surse — înlocuiește
pur și simplu `<sursa-video>` cu link-ul YouTube sau cu `--local-video <cale>`.

## Rulare

### Varianta 1 — complet automată (Claude alege clipurile)

```bash
python auto_shorts.py <sursa-video> \
    --num-clips 3 \
    --clip-length 45 \
    --whisper-model base \
    --output-dir ./shorts_output
```

Exemplu concret cu fișier local:

```bash
python auto_shorts.py --local-video "/home/user/Videos/vlog.mp4" \
    --num-clips 3 --clip-length 45 --output-dir ./shorts_output
```

### Varianta 2 — fără costuri API, alegi clipurile tu (cu un AI gratuit)

**Pasul 1** — doar (descarcă dacă e nevoie și) transcrie, apoi oprește-te:

```bash
python auto_shorts.py <sursa-video> --transcript-only
```

Rezultă `_auto_shorts_work/transcript.json` — un transcript complet cu
timestamp-uri. Dai acest fișier unui AI gratuit (ChatGPT, Gemini, etc.) și îi
ceri să aleagă cele mai bune momente pentru Shorts, în acest format:

```json
[
  {
    "start": 125.0,
    "end": 168.5,
    "title": "Titlu scurt pentru Short",
    "reason": "De ce functioneaza acest moment (optional)"
  }
]
```

Salvezi răspunsul ca `clips.json`.

**Pasul 2** — taiere + formatare, folosind clipurile deja alese:

```bash
python auto_shorts.py <sursa-video> \
    --clips-json clips.json \
    --output-dir ./shorts_output
```

> Notă: dacă sursa e un link YouTube, la Pasul 2 scriptul redescarcă
> videoclipul (nu are cache) — deci va dura la fel de mult ca prima rulare
> pentru descărcare. Transcrierea insă e complet sărită la Pasul 2 (nu mai e
> nevoie de segmente cu `--clips-json`), iar dacă folosești `--local-video`,
> pasul e și mai rapid, pentru că fișierul e deja pe disc.

Rezultat (ambele variante): în `./shorts_output/` apar fișiere `.mp4` gata de
urcat pe YouTube Shorts, cu titlul afișat și în consolă, alături de motivul
alegerii.

## Parametri utili

| Parametru | Ce face |
|---|---|
| `url` (poziţional) | link-ul YouTube; omite-l dacă folosești `--local-video` |
| `--local-video` | cale către un fișier video deja pe calculator; sare peste descărcarea YouTube |
| `--num-clips` | câte shorts vrei să genereze (doar pentru alegerea automată cu Claude) |
| `--clip-length` | lungimea țintă (secunde) a fiecărui clip (doar pentru alegerea automată) |
| `--whisper-model` | `tiny`/`base` = rapid, `small`/`medium`/`large` = mai precis dar mai lent |
| `--clips-json` | cale către un fișier JSON cu clipurile deja alese; sare peste apelul Claude |
| `--transcript-only` | doar obține transcriptul, apoi se oprește (util pentru a genera manual `clips.json`) |
| `--anthropic-api-key` | cheia API, dacă nu vrei să o pui în variabila de mediu |

## Cum funcționează (pe scurt)

1. **Sursa video**: fie **yt-dlp** descarcă videoclipul de pe YouTube, fie
   scriptul folosește direct fișierul dat cu `--local-video`.
2. **Whisper** transcrie audio cu timestamp-uri (`_auto_shorts_work/transcript.json`) —
   dar doar dacă e nevoie de segmente: la `--transcript-only`, la alegerea
   automată cu Claude, sau dacă `transcript.json` nu există deja. Cu
   `--clips-json`, transcrierea e sărită complet (clipurile sunt deja alese).
3. Alegerea segmentelor pentru Shorts:
   - automat, prin **Claude** (analizează transcriptul și alege hook + poveste + încheiere), SAU
   - manual, din fișierul JSON pe care i-l dai (`--clips-json`).
4. **ffmpeg** taie fiecare segment și îl reîncadrează pe verticală (fundal
   blurat + video centrat), fără subtitrări.

## Note

- Prima rulare cu Whisper descarcă modelul (câteva sute MB, în funcție de
  `--whisper-model`) — durează puțin mai mult prima dată.
- Dacă vlogul are voci suprapuse/zgomot de fundal, `--whisper-model small`
  sau `medium` dă transcrieri mult mai bune decât `base`.
- Dacă `_auto_shorts_work/transcript.json` există deja, scriptul îl
  refolosește în loc să retranscrie audio — șterge-l manual dacă vrei o
  retranscriere (ex. cu alt `--whisper-model`).
- Scriptul șterge fișierele temporare din timpul tăierii, dar păstrează
  `transcript.json` în `_auto_shorts_work/` pentru depanare, re-generare sau
  pentru a-l folosi cu un AI gratuit la alegerea clipurilor.
- Cu `--local-video`, nu ai nevoie deloc de `yt-dlp` instalat — doar de
  ffmpeg, Whisper și (opțional) `anthropic`.

## Bonus: conversie audio pentru YouCut

Scriptul `scripts/Convert_For_Youcut.py` (și wrapper-ul dublu-click pentru
Mac, `scripts/Convert_For_YouCut.command`) extrag pista audio dintr-unul sau
mai multe fișiere video/audio și o reîncodează ca WAV mono, 48kHz, 16-bit PCM
— un format pe care YouCut îl importă fără probleme.

```bash
python3 scripts/Convert_For_Youcut.py video1.mp4 video2.mov audio.mp3
```

Pe Mac poți trage și fișierele direct peste `Convert_For_YouCut.command`
pentru a le converti fără linia de comandă. Rezultatul apare lângă fișierul
original, cu sufixul `_YouCut.wav`. Necesită `ffmpeg` instalat.
