#!/usr/bin/env python3
"""
Stream-Clipper: findet Highlights in einem Stream-VOD und schneidet fertige
Hochformat-Clips (9:16) mit Untertiteln und Hook-Text.

Ablauf:
  1. Metadaten + Audio des VODs laden (yt-dlp)          – oder lokale Datei
  2. Lautstärke pro Sekunde messen (ffmpeg)
  3. Chat-Replay laden und Nachrichten/Sekunde zählen    – optional
  4. Highlight-Score berechnen, beste Momente wählen
  5. Kandidaten transkribieren (faster-whisper)          – optional
  6. Claude wählt die besten Clips + schreibt Hooks       – optional (ANTHROPIC_API_KEY)
  7. Nur die nötigen Videoabschnitte laden und rendern

Nur für Streams verwenden, deren Rechteinhaber das Clippen erlaubt
(z. B. offizielle Clipping-Kampagnen).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Wörter/Emotes im Chat, die auf einen lustigen oder krassen Moment hindeuten.
HYPE_TOKENS = [
    "kekw", "lul", "lol", "omegalul", "lmao", "xd", "pog", "poggers", "pogchamp",
    "w", "ww", "www", "clip", "clipit", "clip it", "monkas", "pepelaugh",
    "sadge", "o7", "😂", "🤣", "💀", "😭", "🔥", "?", "??", "???", "wtf", "omg",
    "hahaha", "haha", "digga", "bruder", "krass", "brutal",
]
HYPE_RE = re.compile(
    r"(?i)(?<![\w])(" + "|".join(re.escape(t) for t in HYPE_TOKENS) + r")(?![\w])"
)

W, H = 1080, 1920


# ---------------------------------------------------------------- helpers

def log(msg: str) -> None:
    print(f"[clipper] {msg}", flush=True)


def run(cmd: list[str], capture: bool = False) -> str:
    res = subprocess.run(cmd, check=True, text=True,
                         stdout=subprocess.PIPE if capture else None,
                         stderr=subprocess.PIPE if capture else None)
    return res.stdout if capture else ""


def zscores(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [0.0] * len(values)
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values) or 1.0
    return [(v - mean) / sd for v in values]


def smooth(values: list[float], window: int) -> list[float]:
    if window <= 1:
        return values[:]
    half = window // 2
    prefix = [0.0]
    for v in values:
        prefix.append(prefix[-1] + v)
    out = []
    n = len(values)
    for i in range(n):
        a, b = max(0, i - half), min(n, i + half + 1)
        out.append((prefix[b] - prefix[a]) / (b - a))
    return out


def fmt_ts(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 3600:d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


# ---------------------------------------------------------------- 1. Quelle

def fetch_info(url: str) -> dict:
    out = run(["yt-dlp", "-J", "--no-warnings", url], capture=True)
    return json.loads(out)


def download_audio(url: str, workdir: Path) -> Path:
    target = workdir / "audio.%(ext)s"
    run(["yt-dlp", "-q", "--no-warnings", "-f", "ba/b", "-o", str(target), url])
    files = list(workdir.glob("audio.*"))
    if not files:
        sys.exit("Audio-Download fehlgeschlagen.")
    return files[0]


def media_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)], capture=True)
    return float(out.strip())


# ---------------------------------------------------------------- 2. Lautstärke

def loudness_per_second(audio: Path) -> list[float]:
    """RMS-Pegel in dB pro Sekunde."""
    log("Messe Lautstärke …")
    cmd = ["ffmpeg", "-v", "error", "-i", str(audio), "-vn", "-ac", "1",
           "-af", "aresample=8000,asetnsamples=n=8000:p=0,"
                  "astats=metadata=1:reset=1,"
                  "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
           "-f", "null", "-"]
    out = run(cmd, capture=True)
    levels = []
    for line in out.splitlines():
        if "RMS_level=" in line:
            val = line.split("=", 1)[1]
            try:
                f = float(val)
                levels.append(f if math.isfinite(f) else -90.0)
            except ValueError:
                levels.append(-90.0)
    return levels


# ---------------------------------------------------------------- 3. Chat

def chat_per_second(url: str, duration: int) -> tuple[list[float], list[float]]:
    """(Nachrichten pro Sekunde, Hype-Treffer pro Sekunde). Leer, wenn nicht verfügbar."""
    try:
        from chat_downloader import ChatDownloader
    except ImportError:
        return [], []
    log("Lade Chat-Replay (kann bei langen Streams dauern) …")
    rate = [0.0] * (duration + 1)
    hype = [0.0] * (duration + 1)
    try:
        chat = ChatDownloader().get_chat(url, message_groups=["messages"])
        for msg in chat:
            t = msg.get("time_in_seconds")
            if t is None or t < 0 or t > duration:
                continue
            i = int(t)
            rate[i] += 1
            text = msg.get("message") or ""
            hits = len(HYPE_RE.findall(text))
            # Emotes kommen bei Twitch oft als Text-Namen, bei YouTube als Emojis.
            for em in msg.get("emotes", []) or []:
                name = (em.get("name") or "").lower().strip(":")
                if HYPE_RE.fullmatch(name or "-"):
                    hits += 1
            hype[i] += min(hits, 3)
    except Exception as exc:  # Chat ist optional
        log(f"Chat nicht verfügbar ({exc.__class__.__name__}) – nutze nur Audio.")
        return [], []
    total = int(sum(rate))
    log(f"{total} Chat-Nachrichten gelesen.")
    if total < 50:
        return [], []
    return rate, hype


# ---------------------------------------------------------------- 4. Score

@dataclass
class Candidate:
    peak: float
    start: float
    end: float
    score: float
    transcript: str = ""
    words: list = field(default_factory=list)
    title: str = ""
    hook: str = ""
    caption: str = ""
    hashtags: list = field(default_factory=list)


def find_candidates(loud: list[float], chat_rate: list[float], chat_hype: list[float],
                    duration: float, n: int, length: int, chat_delay: int) -> list[Candidate]:
    secs = min(len(loud), int(duration)) if loud else int(duration)
    loud = (loud + [-90.0] * secs)[:secs]
    score = [0.0] * secs
    lz = zscores(smooth(loud, 4))
    for i in range(secs):
        score[i] += lz[i]
    if chat_rate:
        # Der Chat reagiert einige Sekunden NACH dem Moment → nach vorne verschieben.
        def shifted(arr):
            arr = (arr + [0.0] * secs)[:secs]
            return arr[chat_delay:] + [0.0] * chat_delay
        cz = zscores(smooth(shifted(chat_rate), 8))
        hz = zscores(smooth(shifted(chat_hype), 8))
        for i in range(secs):
            score[i] += 1.5 * cz[i] + 1.0 * hz[i]

    order = sorted(range(secs), key=lambda i: score[i], reverse=True)
    picked: list[int] = []
    min_gap = length * 1.2
    for i in order:
        if all(abs(i - p) >= min_gap for p in picked):
            picked.append(i)
        if len(picked) >= n:
            break

    cands = []
    pre = int(length * 0.6)  # Aufbau vor dem Höhepunkt
    for p in picked:
        start = max(0, p - pre)
        end = min(duration, start + length)
        start = max(0, end - length)
        cands.append(Candidate(peak=p, start=start, end=end, score=round(score[p], 2)))
    return cands


# ---------------------------------------------------------------- 5. Transkript

_whisper = None


def transcribe(audio: Path, cand: Candidate, model_size: str, lang: str | None,
               workdir: Path) -> None:
    global _whisper
    from faster_whisper import WhisperModel
    if _whisper is None:
        log(f"Lade Whisper-Modell '{model_size}' …")
        _whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
    seg_path = workdir / f"seg_{int(cand.start)}.wav"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(cand.start), "-t",
         str(cand.end - cand.start), "-i", str(audio), "-ac", "1", "-ar", "16000",
         str(seg_path)])
    segments, _ = _whisper.transcribe(str(seg_path), language=lang, word_timestamps=True,
                                      vad_filter=True)
    words, text = [], []
    for s in segments:
        text.append(s.text.strip())
        for w in s.words or []:
            words.append({"start": round(w.start, 2), "end": round(w.end, 2),
                          "word": w.word.strip()})
    cand.transcript = " ".join(text)
    cand.words = words
    seg_path.unlink(missing_ok=True)


# ---------------------------------------------------------------- 6. Claude

def rank_with_claude(cands: list[Candidate], n: int, streamer: str, lang_name: str,
                     length: int) -> list[Candidate]:
    import anthropic
    client = anthropic.Anthropic()
    payload = [{"id": i, "start_in_vod": fmt_ts(c.start), "score": c.score,
                "transcript": c.transcript[:2500]} for i, c in enumerate(cands)]
    schema = {
        "type": "object",
        "properties": {
            "clips": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "trim_start": {"type": "number"},
                        "trim_end": {"type": "number"},
                        "title": {"type": "string"},
                        "hook": {"type": "string"},
                        "caption": {"type": "string"},
                        "hashtags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "trim_start", "trim_end", "title", "hook",
                                 "caption", "hashtags"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["clips"],
        "additionalProperties": False,
    }
    prompt = (
        f"Du bist Editor für Kurzvideo-Clips des Streamers {streamer or 'unbekannt'}.\n"
        f"Hier sind {len(cands)} Kandidaten-Ausschnitte (je ca. {length} s) mit Transkript "
        f"und einem automatischen Highlight-Score aus Lautstärke und Chat-Aktivität.\n"
        f"Wähle die {n} Ausschnitte, die als TikTok/YouTube-Shorts-Clip am besten funktionieren "
        "(lustig, überraschend, emotional, Streit, krasse Spielszene, starkes Zitat). "
        "Lass Ausschnitte weg, die ohne Kontext unverständlich sind, den Streamer bloßstellen, "
        "beleidigend sind oder private Daten zeigen.\n"
        "Für jeden gewählten Clip:\n"
        "- trim_start / trim_end: Sekunden relativ zum Ausschnitt-Anfang, so dass der Clip "
        "direkt mit Action beginnt und nach der Pointe endet (mindestens 12 s).\n"
        f"- title: Titel auf {lang_name}, max. 60 Zeichen, neugierig machend, kein Clickbait-Lügen.\n"
        f"- hook: Text-Overlay für die ersten Sekunden auf {lang_name}, max. 7 Wörter.\n"
        f"- caption: 1 Satz auf {lang_name} + Aufforderung zum Kommentieren.\n"
        "- hashtags: 3–5 passende Hashtags ohne #.\n\n"
        f"Kandidaten (JSON):\n{json.dumps(payload, ensure_ascii=False)}"
    )
    log("Claude wählt die besten Clips …")
    resp = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low",
                       "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Anfrage abgelehnt")
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    chosen = []
    for item in data["clips"][:n]:
        i = item["id"]
        if not (0 <= i < len(cands)):
            continue
        c = cands[i]
        span = c.end - c.start
        ts = max(0.0, min(float(item["trim_start"]), span - 5))
        te = max(ts + 8, min(float(item["trim_end"]), span))
        c.words = [{**w, "start": w["start"] - ts, "end": w["end"] - ts}
                   for w in c.words if w["start"] >= ts and w["end"] <= te]
        c.start, c.end = c.start + ts, c.start + te
        c.title, c.hook, c.caption = item["title"], item["hook"], item["caption"]
        c.hashtags = [h.lstrip("#") for h in item["hashtags"]]
        chosen.append(c)
    return chosen


def fallback_texts(c: Candidate, streamer: str) -> None:
    words = c.transcript.split()
    snippet = " ".join(words[:8]) if words else "Krasser Moment"
    c.title = c.title or (f"{streamer}: " if streamer else "") + snippet[:50]
    c.hook = c.hook or "Warte bis zum Ende ..."
    c.caption = c.caption or "Was sagt ihr dazu? 👇"
    c.hashtags = c.hashtags or ["clips", "stream", "fyp"] + (
        [re.sub(r"\W", "", streamer.lower())] if streamer else [])


# ---------------------------------------------------------------- 7. Render

def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000:d}:{cs % 360000 // 6000:02d}:{cs % 6000 // 100:02d}.{cs % 100:02d}"


def ass_escape(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(c: Candidate, path: Path, words_per_line: int, sub_y: int) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,DejaVu Sans,82,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,{H - sub_y},1
Style: Hook,DejaVu Sans,74,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,80,80,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    dur = c.end - c.start
    if c.hook:
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(min(3.5, dur))},Hook,,0,0,0,,"
                     f"{ass_escape(c.hook)}")
    words = c.words
    for i in range(0, len(words), words_per_line):
        chunk = words[i:i + words_per_line]
        start = chunk[0]["start"]
        end = words[i + words_per_line]["start"] if i + words_per_line < len(words) \
            else chunk[-1]["end"] + 0.3
        end = max(end, start + 0.3)
        # aktuelles Wort gelb hervorheben (Karaoke-Effekt)
        parts = []
        for w in chunk:
            k = max(1, int(round((w["end"] - w["start"]) * 100)))
            parts.append(f"{{\\k{k}}}{ass_escape(w['word']).upper()}")
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,"
                     + " ".join(parts))
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def download_section(url: str, c: Candidate, workdir: Path, idx: int) -> Path:
    out = workdir / f"raw_{idx:02d}.%(ext)s"
    run(["yt-dlp", "-q", "--no-warnings",
         "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
         "--download-sections", f"*{c.start:.2f}-{c.end:.2f}",
         "--force-keyframes-at-cuts", "--merge-output-format", "mp4",
         "-o", str(out), url])
    files = sorted(workdir.glob(f"raw_{idx:02d}.*"))
    if not files:
        raise RuntimeError("Download des Abschnitts fehlgeschlagen")
    return files[0]


def render(src: Path, c: Candidate, ass: Path, dst: Path, layout: str,
           cam: str | None, is_full_vod: bool) -> None:
    ass_arg = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    if layout == "facecam" and cam:
        x, y, w, h = cam.split(":")
        vf = (
            f"[0:v]split=2[a][b];"
            f"[a]crop={w}:{h}:{x}:{y},scale={W}:{int(H * 0.36)}:force_original_aspect_ratio=increase,"
            f"crop={W}:{int(H * 0.36)}[cam];"
            f"[b]scale=-2:{int(H * 0.64)},crop={W}:{int(H * 0.64)}[game];"
            f"[cam][game]vstack,setsar=1,fps=30,ass='{ass_arg}'[v]"
        )
    else:  # "blur": ganzes Bild in der Mitte, unscharfer Hintergrund
        vf = (
            f"[0:v]split=2[a][b];"
            f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=24:2,eq=brightness=-0.08[bg];"
            f"[b]scale={W}:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,ass='{ass_arg}'[v]"
        )
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if is_full_vod:
        cmd += ["-ss", f"{c.start:.2f}", "-t", f"{c.end - c.start:.2f}"]
    cmd += ["-i", str(src), "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-movflags", "+faststart", "-shortest", str(dst)]
    run(cmd)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description="Highlights aus Stream-VODs als 9:16-Clips")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="VOD-URL (Twitch, YouTube, Kick …)")
    src.add_argument("--file", help="lokale Videodatei statt URL")
    ap.add_argument("--clips", type=int, default=6, help="Anzahl fertiger Clips")
    ap.add_argument("--length", type=int, default=45, help="Länge der Kandidaten in Sekunden")
    ap.add_argument("--layout", choices=["blur", "facecam"], default="blur")
    ap.add_argument("--cam", help="Facecam-Bereich im Original: x:y:breite:höhe (für --layout facecam)")
    ap.add_argument("--lang", default="de", help="Sprache des Streams (de, en …) oder 'auto'")
    ap.add_argument("--whisper", default="small", help="Whisper-Modell: tiny, base, small, medium")
    ap.add_argument("--no-transcribe", action="store_true", help="keine Untertitel/Transkripte")
    ap.add_argument("--no-chat", action="store_true", help="Chat-Replay nicht verwenden")
    ap.add_argument("--no-ai", action="store_true", help="Claude nicht verwenden")
    ap.add_argument("--chat-delay", type=int, default=5, help="Sekunden, die der Chat hinterherhinkt")
    ap.add_argument("--streamer", default="", help="Name des Streamers (für Titel/Hashtags)")
    ap.add_argument("--out", default="clips", help="Ausgabeordner")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe") + (("yt-dlp",) if args.url else ()):
        if not shutil.which(tool):
            sys.exit(f"'{tool}' ist nicht installiert.")
    if args.layout == "facecam" and not args.cam:
        sys.exit("--layout facecam braucht --cam x:y:breite:höhe")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="clipper_"))
    lang = None if args.lang == "auto" else args.lang
    lang_name = {"de": "Deutsch", "en": "Englisch"}.get(args.lang, "der Sprache des Streams")

    try:
        if args.url:
            info = fetch_info(args.url)
            duration = float(info.get("duration") or 0)
            streamer = args.streamer or info.get("uploader") or info.get("channel") or ""
            log(f"VOD: {info.get('title')} ({fmt_ts(duration)})")
            audio = download_audio(args.url, workdir)
            if not duration:
                duration = media_duration(audio)
        else:
            audio = Path(args.file)
            duration = media_duration(audio)
            streamer = args.streamer
            log(f"Datei: {audio.name} ({fmt_ts(duration)})")

        loud = loudness_per_second(audio)
        rate, hype = ([], [])
        if args.url and not args.no_chat:
            rate, hype = chat_per_second(args.url, int(duration))

        n_cand = args.clips if args.no_ai else args.clips * 2
        cands = find_candidates(loud, rate, hype, duration, n_cand, args.length,
                                args.chat_delay)
        log(f"{len(cands)} Kandidaten gefunden.")

        if not args.no_transcribe:
            for c in cands:
                log(f"Transkribiere {fmt_ts(c.start)} …")
                transcribe(audio, c, args.whisper, lang, workdir)
        # Wort-Zeiten relativ zum Clip-Anfang sind schon relativ (Segment beginnt bei 0).

        chosen = cands[:args.clips]
        if not args.no_ai and os.environ.get("ANTHROPIC_API_KEY") and not args.no_transcribe:
            try:
                chosen = rank_with_claude(cands, args.clips, streamer, lang_name, args.length) \
                    or chosen
            except Exception as exc:
                log(f"Claude-Auswahl fehlgeschlagen ({exc}) – nutze automatischen Score.")
                chosen = cands[:args.clips]
        elif not args.no_ai:
            log("Kein ANTHROPIC_API_KEY gesetzt – nutze automatischen Score und Standard-Hooks.")

        summary = []
        for idx, c in enumerate(sorted(chosen, key=lambda c: c.start), 1):
            fallback_texts(c, streamer)
            log(f"Rendere Clip {idx}: {fmt_ts(c.start)}–{fmt_ts(c.end)} „{c.title}“")
            ass = workdir / f"clip_{idx:02d}.ass"
            build_ass(c, ass, words_per_line=3,
                      sub_y=int(H * 0.36) + 140 if args.layout == "facecam" else int(H * 0.78))
            if args.url:
                src_path = download_section(args.url, c, workdir, idx)
                full = False
            else:
                src_path, full = audio, True
            dst = out_dir / f"clip_{idx:02d}.mp4"
            render(src_path, c, ass, dst, args.layout, args.cam, full)
            text = (f"TITEL: {c.title}\n\nCAPTION:\n{c.caption}\n"
                    + " ".join("#" + h for h in c.hashtags)
                    + f"\n\nQUELLE: {args.url or args.file} @ {fmt_ts(c.start)}\n")
            (out_dir / f"clip_{idx:02d}.txt").write_text(text, encoding="utf-8")
            d = asdict(c)
            d.pop("words")
            d["file"] = dst.name
            summary.append(d)
        (out_dir / "clips.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
        log(f"Fertig: {len(summary)} Clips in '{out_dir}/'")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
