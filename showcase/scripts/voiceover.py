"""Generate the showcase voiceover with Gemini TTS.

Writes public/vo/<id>.wav for every line and src/voiceover.json with durations, which the
Remotion composition uses to time scenes, captions and the call transcript.

Free-tier friendly: lines already on disk are reused, requests are paced (3/min), and on a
quota error the next TTS model is tried (each model has its own daily quota).

    GEMINI_API_KEY=... python scripts/voiceover.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import wave
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "vo"
MANIFEST = ROOT / "src" / "voiceover.json"
RATE = 24000
MODELS = [
    "gemini-3.8-flash-tts",
    "gemini-3.1-flash-tts-preview",
    "gemini-3.8-flash-lite-tts",
    "gemini-2.5-pro-preview-tts",
]

NARRATOR = ("Charon", "Read this as a warm, confident, unhurried product-video narrator:")
AVA = ("Aoede", "Say this as Ava, a friendly, upbeat hair-salon receptionist on the phone:")
CALLER = ("Puck", "Say this as a relaxed, friendly customer calling a hair salon:")

LINES: list[tuple[str, tuple[str, str], str]] = [
    ("n_intro", NARRATOR, "Meet Receptly — the AI receptionist that never misses a call."),
    (
        "n_problem",
        NARRATOR,
        "When you're busy with a client, or the salon is closed, calls go unanswered. "
        "And every missed call is a lost booking.",
    ),
    (
        "n_landing",
        NARRATOR,
        "With Receptly, Ava answers every call — on your phone line, or right from your website.",
    ),
    (
        "c1",
        AVA,
        "Thank you for calling Luma Hair Studio, this is Ava. This call may be recorded "
        "and transcribed. How can I help you today?",
    ),
    ("c2", CALLER, "Hi! Can I get a haircut with Sara tomorrow afternoon?"),
    ("c3", AVA, "Sara has 2:30 PM or 4:00 PM tomorrow. Which works best for you?"),
    ("c4", CALLER, "2:30, please."),
    (
        "c5",
        AVA,
        "Lovely — a haircut with Sara tomorrow at 2:30 PM, for Ayesha Khan. Shall I book it?",
    ),
    ("c6", CALLER, "Yes, please!"),
    (
        "c7",
        AVA,
        "You're all set! A confirmation email is on its way. Anything else I can help with?",
    ),
    (
        "n_booked",
        NARRATOR,
        "The appointment lands straight in Google Calendar, and the customer gets a "
        "confirmation email, instantly.",
    ),
    (
        "n_overview",
        NARRATOR,
        "Your dashboard shows every call, every booking, and how your receptionist is doing.",
    ),
    (
        "n_detail",
        NARRATOR,
        "Open any call to see the full transcript, every action Ava took, and an AI summary "
        "for your team.",
    ),
    (
        "n_teach",
        NARRATOR,
        "Teach Ava your services, prices, opening hours and FAQs in minutes. No code needed.",
    ),
    (
        "n_trust",
        NARRATOR,
        "And it's built to be trusted. Ava only offers times that are really free, never "
        "double-books, and hands off to a person whenever a caller asks.",
    ),
    ("n_mobile", NARRATOR, "Your front desk, in your pocket."),
    ("n_outro", NARRATOR, "Receptly. Never miss a call again."),
]


def synth(client: genai.Client, voice: str, style: str, text: str) -> bytes:
    last: Exception | None = None
    for model in MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    # Text only: TTS models read any style instruction out loud.
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                            )
                        ),
                    ),
                )
                data = resp.candidates[0].content.parts[0].inline_data.data
                print(f"    via {model}")
                return data
            except Exception as exc:  # 429 per-minute / per-day, 404 unknown model, 5xx
                last = exc
                msg = str(exc)
                if "per day" in msg or "404" in msg or "NOT_FOUND" in msg:
                    print(f"    {model}: unavailable ({msg[:60]}), trying next model")
                    break
                wait = 25 * (attempt + 1)
                print(f"    {model}: {msg[:60]} — retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"all TTS models failed: {last}")


def trim(pcm: bytes, threshold: int = 900) -> bytes:
    """Strip leading/trailing near-silence so clips sit tightly on the timeline."""
    import array

    s = array.array("h", pcm)
    start = next((i for i, v in enumerate(s) if abs(v) > threshold), 0)
    end = next((i for i in range(len(s) - 1, -1, -1) if abs(s[i]) > threshold), len(s) - 1)
    pad = int(RATE * 0.05)
    return s[max(0, start - pad) : min(len(s), end + pad)].tobytes()


def tighten(
    pcm: bytes, threshold: int = 1500, max_gap_s: float = 0.6, keep_s: float = 0.4
) -> bytes:
    """Shorten long pauses inside a clip (TTS sometimes leaves 1-2 s mid-sentence)."""
    import array

    s = array.array("h", pcm)
    win = RATE // 50  # 20 ms
    out = array.array("h")
    quiet: list[array.array] = []
    for i in range(0, len(s), win):
        chunk = s[i : i + win]
        if max((abs(v) for v in chunk), default=0) < threshold:
            quiet.append(chunk)
            continue
        if quiet:
            if len(quiet) * win > RATE * max_gap_s:
                quiet = quiet[: int(keep_s * RATE / win)]
            for q in quiet:
                out.extend(q)
            quiet = []
        out.extend(chunk)
    return out.tobytes()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1beta")
    )
    manifest: dict[str, dict[str, object]] = {}
    made = 0
    for line_id, (voice, style), text in LINES:
        path = OUT / f"{line_id}.wav"
        if not path.exists():
            if made:
                time.sleep(21)  # free tier: 3 TTS requests per minute
            print(f"  {line_id} ({voice}): {text[:60]}")
            pcm = trim(synth(client, voice, style, text))
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(pcm)
            made += 1
        with wave.open(str(path), "rb") as w:
            pcm = w.readframes(w.getnframes())
        tight = tighten(pcm)
        if len(tight) < len(pcm):  # idempotent: only rewrites clips with long pauses
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(tight)
        seconds = len(tight) / 2 / RATE
        manifest[line_id] = {
            "file": f"vo/{line_id}.wav",
            "seconds": round(seconds, 3),
            "text": text,
            "voice": voice,
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(float(str(v["seconds"])) for v in manifest.values())
    print(f"wrote {MANIFEST.name}: {len(manifest)} clips, {total:.1f}s of voice ({made} new)")


if __name__ == "__main__":
    sys.exit(main())
