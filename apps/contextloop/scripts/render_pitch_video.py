#!/usr/bin/env python3
"""Render the narrated ContextLoop pitch video (1920 x 1080, H.264 + AAC) with WebVTT captions and a poster frame.

The script lives in contextloop/ui/pitch/script.json, one voiced beat at a time. Each beat is voiced by a recorded take,
recordings/voiceover/<beat id>.wav (any format ffmpeg reads, also .m4a or .mp3), when one exists, otherwise by the best macOS voice
installed. The pitch stage (contextloop/ui/pitch/pitch.html) is then captured frame by frame in headless Chromium: every visual is a
function of time, so the video is deterministic and each highlight lands on its line of narration.

Usage:
  python scripts/render_pitch_video.py                 full render (about 10 minutes)
  python scripts/render_pitch_video.py --stills 5,arch-2a+4   PNG stills (seconds, or beat id + offset), for a quick look
  python scripts/render_pitch_video.py --draft         720p, 15 fps, fast
Options: --voice "Ava (Premium)" --rate 172 --scale 2 (supersample) --music bed.m4a
Neural voices: --tts google (Chirp 3 HD, default voice Orus; uses `gcloud auth login` and GOOGLE_TTS_PROJECT in .env), or
--tts elevenlabs / --tts openai with ELEVENLABS_API_KEY or OPENAI_API_KEY in .env (the script text is sent to
that service; the audio is cached in data/out/tts-cache, so re-renders don't pay again). Choose a voice with --voice.
Needs (on the host, not in Docker): macOS `say`, ffmpeg, and `pip install playwright` (uses Playwright's Chromium, else Google Chrome).
For a better synthetic voice, download a Premium voice (System Settings → Accessibility → Spoken Content → System voice → Manage
Voices, e.g. Ava, Zoe or Evan) and it is picked up automatically.
"""
from __future__ import annotations

import argparse
import array
import base64
import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "contextloop" / "ui"
SCRIPT = UI / "pitch" / "script.json"
VOICEOVER = ROOT / "recordings" / "voiceover"
OUT = UI / "assets" / "video"
NAME = "contextloop-pitch"
RATE = 48_000

VOICES = ["Ava (Premium)", "Zoe (Premium)", "Evan (Premium)", "Nathan (Premium)", "Noelle (Premium)", "Ava (Enhanced)", "Zoe (Enhanced)",
          "Evan (Enhanced)", "Allison (Enhanced)", "Samantha (Enhanced)", "Serena (Premium)", "Daniel (Enhanced)", "Samantha"]
# How the synthetic voice should say the terms it gets wrong (captions keep the written form).
SAY = {r"\bdbt\b": "D B T", r"\bSQL\b": "sequel", r"\bMCP\b": "M C P", r"\bSAP\b": "S A P", r"\bCOO's\b": "C O O's",
       r"\bETL\b": "E T L", r"\bDuckDB\b": "Duck D B", r"\bMetricFlow\b": "Metric Flow", r"\bTrino\b": "Treeno", r"\bAI\b": "A I",
       r"\b2\.7\b": "two point seven", r"\bPostgres\b": "Post-gress"}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def pick_voice(wanted: str | None) -> str:
    installed = {ln.split("  ")[0].strip() for ln in run(["say", "-v", "?"], text=True).stdout.splitlines()}
    if wanted:
        if wanted not in installed:
            sys.exit(f"voice {wanted!r} is not installed; `say -v ?` lists the voices")
        return wanted
    return next(v for v in VOICES if v in installed)


def wav_seconds(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


TRIM = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse," \
       "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse"


# ---- neural voices (ElevenLabs, OpenAI) ---------------------------------------------------------------------------------
# Spelled out so a neural voice reads the acronyms as letters; captions keep the written form.
NEURAL_SAY = {r"\bdbt\b": "D-B-T", r"\bMCP\b": "M-C-P", r"\bSAP\b": "S-A-P", r"\bCOO's\b": "C-O-O's", r"\bETL\b": "E-T-L",
              r"\bDuckDB\b": "Duck D-B", r"\bSQL\b": "sequel", r"\bMetricFlow\b": "Metric Flow"}
TONE = ("Speak as a warm, confident solutions engineer briefing a customer's leadership team: natural, conversational pace, "
        "clear diction, short natural pauses at commas, light emphasis on the key numbers. Not salesy, not rushed.")
DEFAULT_VOICE = {"elevenlabs": "21m00Tcm4TlvDq8ikWAM", "openai": "coral", "google": "en-US-Chirp3-HD-Orus"}
KEY_VAR = {"elevenlabs": "ELEVENLABS_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_TTS_API_KEY"}
CACHE = ROOT / "data" / "out" / "tts-cache"  # generated audio is cached (git-ignored), so re-renders don't pay twice


def env_value(var: str) -> str:
    if os.environ.get(var):
        return os.environ[var]
    env = ROOT / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        k, _, v = line.partition("=")
        if k.strip() == var and v.strip():
            return v.strip().strip('"').strip("'")
    return ""


def api_key(provider: str) -> str:
    """The provider's credential. Google can also use your gcloud login: `gcloud auth login` plus GOOGLE_TTS_PROJECT in .env."""
    key = env_value(KEY_VAR[provider])
    if key:
        return key
    if provider == "google" and shutil.which("gcloud"):
        if not env_value("GOOGLE_TTS_PROJECT"):
            sys.exit("--tts google: set GOOGLE_TTS_PROJECT in .env to a Google Cloud project with the Text-to-Speech API enabled "
                     "(or set GOOGLE_TTS_API_KEY)")
        return "gcloud:" + subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
    sys.exit(f"--tts {provider} needs {KEY_VAR[provider]}: add it to {(ROOT / '.env').relative_to(ROOT)} (never commit it)")


def _post(url: str, headers: dict, body: dict) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            sys.exit(f"TTS request failed ({e.code}): {e.read().decode(errors='replace')[:300]}")
    raise RuntimeError("unreachable")


def neural_tts(provider: str, voice: str, text: str, prev: str, nxt: str, key: str) -> Path:
    """One beat from a neural voice, cached by its inputs. The neighbouring lines are passed where the API supports it, so the
    intonation flows from one line into the next."""
    for pat, rep in NEURAL_SAY.items():
        text, prev, nxt = (re.sub(pat, rep, s) for s in (text, prev, nxt))
    model = {"elevenlabs": "eleven_multilingual_v2", "openai": "gpt-4o-mini-tts", "google": "chirp3-hd"}[provider]
    digest = hashlib.sha256("|".join([provider, model, voice, text, prev, nxt, TONE]).encode()).hexdigest()[:20]
    dst = CACHE / provider / f"{digest}.mp3"
    if dst.exists():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    if provider == "elevenlabs":
        audio = _post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128", {"xi-api-key": key},
                      {"text": text, "model_id": model, "previous_text": prev, "next_text": nxt,
                       "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}})
    elif provider == "google":  # Chirp 3 HD: plain text in, MP3 out
        if key.startswith("gcloud:"):
            url, headers = "https://texttospeech.googleapis.com/v1/text:synthesize", {
                "Authorization": f"Bearer {key[7:]}", "x-goog-user-project": env_value("GOOGLE_TTS_PROJECT")}
        else:
            url, headers = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}", {}
        body = _post(url, headers, {"input": {"text": text}, "voice": {"languageCode": voice[:5], "name": voice},
                                    "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0, "sampleRateHertz": 48000}})
        audio = base64.b64decode(json.loads(body)["audioContent"])
    else:
        audio = _post("https://api.openai.com/v1/audio/speech", {"Authorization": f"Bearer {key}"},
                      {"model": model, "voice": voice, "input": text, "instructions": TONE, "response_format": "mp3"})
    dst.write_bytes(audio)
    return dst


def voice_beats(beats: list[dict], voice: str, rate: int, work: Path, tts: str = "say") -> dict[str, Path]:
    """One 48 kHz mono WAV per beat, silence trimmed at both ends. A recorded take always wins over a synthetic voice."""
    out = {}
    key = api_key(tts) if tts != "say" else ""
    for i, b in enumerate(beats):
        dst = work / f"{b['id']}.wav"
        take = next((p for p in sorted(VOICEOVER.glob(f"{b['id']}.*")) if p.suffix.lower() in {".wav", ".m4a", ".mp3", ".aiff", ".flac"}), None)
        if take:
            src, label = take, f"take {take.name}"
        elif tts != "say":
            prev = beats[i - 1]["text"] if i else ""
            nxt = beats[i + 1]["text"] if i + 1 < len(beats) else ""
            src, label = neural_tts(tts, voice, b["text"], prev, nxt, key), f"{tts} · {voice}"
        else:
            spoken = b["text"]
            for pat, rep in SAY.items():
                spoken = re.sub(pat, rep, spoken)
            src, label = work / f"{b['id']}.aiff", voice
            run(["say", "-v", voice, "-r", str(rate), "-o", str(src), spoken])
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", TRIM, "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", str(dst)])
        out[b["id"]] = dst
        print(f"  {b['id']:<10} {wav_seconds(dst):5.1f}s  {label}")
    return out


def mix(timeline: dict, wavs: dict[str, Path], dst: Path) -> None:
    total = int(timeline["total"] * RATE) + RATE
    buf = array.array("h", bytes(2 * total))
    for bid, p in wavs.items():
        start = int(timeline["beats"][bid]["start"] * RATE)
        with wave.open(str(p)) as w:
            s = array.array("h", w.readframes(w.getnframes()))
        n = min(len(s), total - start)
        buf[start:start + n] = s[:n]
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(buf.tobytes())


def vtt_time(s: float) -> str:
    h, rem = divmod(max(0.0, s), 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}"


def captions(timeline: dict, dst: Path, max_chars: int = 84) -> None:
    """WebVTT: each beat split at sentence and clause breaks into chunks of at most two short lines, timed by character share."""
    lines = ["WEBVTT", ""]
    n = 0
    for b in sorted(timeline["beats"].values(), key=lambda x: x["start"]):
        parts, cur = [], ""
        for piece in re.split(r"(?<=[.,:;?])\s+", b["text"]):
            if cur and len(cur) + 1 + len(piece) > max_chars:
                parts.append(cur)
                cur = piece
            else:
                cur = f"{cur} {piece}".strip()
        parts.append(cur)
        total_chars = sum(len(p) for p in parts)
        t = b["start"]
        for p in parts:
            d = b["dur"] * len(p) / total_chars
            n += 1
            lines += [str(n), f"{vtt_time(t)} --> {vtt_time(t + d)}", p, ""]
            t += d
    dst.write_text("\n".join(lines))


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D401
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def launch(p, scale: float, w: int = 1920, h: int = 1080):
    try:
        browser = p.chromium.launch()
    except Exception:  # noqa: BLE001  Playwright's Chromium not installed: use Google Chrome
        browser = p.chromium.launch(channel="chrome")
    page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    return browser, page


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tts", choices=["say", "google", "elevenlabs", "openai"], default="say",
                    help="narration voice: macOS say (default, offline), or a neural voice: google (Chirp 3 HD, uses your gcloud "
                         "login and GOOGLE_TTS_PROJECT), elevenlabs or openai (API key in .env)")
    ap.add_argument("--voice", help="voice: a macOS voice, a Google voice (default en-US-Chirp3-HD-Orus), an ElevenLabs voice ID, "
                                    "or an OpenAI voice (coral, ash, sage)")
    ap.add_argument("--rate", type=int, default=172, help="speaking rate for the synthetic voice, words per minute")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--scale", type=float, default=1.0, help="device scale factor; 2 supersamples (sharper, about 3x slower)")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--draft", action="store_true", help="720p at 15 fps, for checking timing")
    ap.add_argument("--stills", help="comma-separated seconds: write PNG stills instead of a video")
    ap.add_argument("--music", help="optional music bed, mixed under the voice at -24 dB")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    for tool in ("ffmpeg",) + (("say",) if a.tts == "say" else ()):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found (the video is rendered on a Mac host)")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(SCRIPT.read_text())
    beats = [b for sc in script["scenes"] for b in sc["beats"]]
    voice = pick_voice(a.voice) if a.tts == "say" else (a.voice or DEFAULT_VOICE[a.tts])
    work = Path(tempfile.mkdtemp(prefix="pitch-"))
    print(f"Voicing {len(beats)} beats (voice: {voice}; takes in {VOICEOVER.relative_to(ROOT)} win)")
    wavs = voice_beats(beats, voice, a.rate, work, a.tts)
    durations = {k: wav_seconds(v) for k, v in wavs.items()}

    srv, port = serve(UI)
    with sync_playwright() as p:
        browser, page = launch(p, a.scale)
        page.goto(f"http://127.0.0.1:{port}/pitch/pitch.html")
        tl = page.evaluate("d => window.__init(d)", durations)
        total = tl["total"]
        print(f"Timeline: {total:.1f}s, {len(tl['scenes'])} scenes")
        if a.stills:
            for tok in a.stills.split(","):  # seconds, or a beat id with an optional offset: arch-2a+4
                bid, _, off = tok.partition("+")
                s = tl["beats"][bid]["start"] + float(off or 0) if bid in tl["beats"] else float(tok)
                for k in range(30, -1, -1):  # play the second before it, so transitions are where they would be in the video
                    page.evaluate("t => window.__render(t)", max(0.0, s - k / 30))
                dst = work / f"still-{s:06.1f}.png"
                page.screenshot(path=str(dst))
                print(f"  {dst}")
            browser.close()
            return

        mix(tl, wavs, work / "voice.wav")
        captions(tl, out / f"{NAME}.vtt")
        fps = 15 if a.draft else a.fps
        size = "1280:720" if a.draft else "1920:1080"
        audio_in = ["-i", str(work / "voice.wav")]
        afilter = "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]"
        if a.music:
            audio_in += ["-stream_loop", "-1", "-i", a.music]
            afilter = ("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[v];[2:a]volume=-24dB,aresample=48000,"
                       f"afade=t=out:st={total - 3:.2f}:d=3[m];[v][m]amix=inputs=2:duration=first:normalize=0[a]")
        dst = out / (f"{NAME}-draft.mp4" if a.draft else f"{NAME}.mp4")
        enc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-", *audio_in,
             "-filter_complex", f"[0:v]scale={size}:flags=lanczos,format=yuv420p[v];{afilter}", "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast" if a.draft else "slow", "-crf", str(a.crf + (6 if a.draft else 0)),
             "-profile:v", "high", "-r", str(fps), "-g", str(fps * 2), "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-t", f"{total:.3f}",
             "-movflags", "+faststart", "-metadata", "title=ContextLoop: your AI agent is only as good as your data", str(dst)],
            stdin=subprocess.PIPE)
        frames = int(total * fps)
        t0 = time.time()
        for f in range(frames):
            page.evaluate("t => window.__render(t)", f / fps)
            enc.stdin.write(page.screenshot(type="jpeg", quality=95))
            if f % (fps * 10) == 0:
                done = (f + 1) / frames
                eta = (time.time() - t0) / done * (1 - done)
                print(f"  frame {f:>5}/{frames} · {f / fps:6.1f}s · eta {eta / 60:4.1f} min", flush=True)
        enc.stdin.close()
        if enc.wait():
            sys.exit("ffmpeg failed")
        if not a.draft:
            poster_t = tl["beats"]["open-2"]["start"] + tl["beats"]["open-2"]["dur"]
            page.evaluate("t => window.__render(t)", poster_t)
            page.screenshot(path=str(work / "poster.png"))
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "poster.png"), "-vf", "scale=1920:1080:flags=lanczos", "-q:v", "3",
                 str(out / f"{NAME}-poster.jpg")])
        browser.close()
    srv.shutdown()
    mb = dst.stat().st_size / 1e6
    show = lambda x: x.relative_to(ROOT) if x.is_relative_to(ROOT) else x  # noqa: E731
    print(f"Wrote {show(dst)} ({total / 60:.1f} min, {mb:.1f} MB), captions and poster in {show(out)}")


if __name__ == "__main__":
    main()
