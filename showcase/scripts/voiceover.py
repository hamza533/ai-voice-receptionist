"""Generate the showcase voiceover with Gemini TTS.

Two takes, for consistent tone and natural rhythm:
  - the whole narration in ONE request (one voice, one read),
  - the whole call as ONE two-speaker request (Ava + the caller),
then each take is split into lines at its longest pauses.

Writes public/vo/<id>.wav and src/voiceover.json (durations), which the Remotion
composition uses to time scenes, captions and the call transcript.
Free-tier friendly: 2 requests; existing takes are reused (delete public/vo/_*.wav to redo).
Send text only: TTS models read any style instruction out loud.

    GEMINI_API_KEY=... python scripts/voiceover.py
"""

from __future__ import annotations

import array
import itertools
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
    "gemini-2.5-pro-preview-tts",
    "gemini-3.8-flash-tts",
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
    "gemini-3.8-flash-lite-tts",
]

NARRATOR_VOICE = "Puck"  # upbeat
AVA_VOICE = "Aoede"  # the receptionist's voice in the product
CALLER_VOICE = "Leda"  # Ayesha, the caller

NARRATION: list[tuple[str, str]] = [
    ("n_intro", "Meet Receptly: the AI receptionist that never misses a call."),
    (
        "n_problem",
        "Busy with a client? Closed for the night? Every unanswered call is a booking you've lost.",
    ),
    (
        "n_landing",
        "Now Ava answers every call, on your phone line or right from your website. Listen.",
    ),
    ("n_booked", "It's in Google Calendar instantly, and the confirmation email is already sent."),
    ("n_overview", "Every call, every booking, every result, in one dashboard."),
    (
        "n_detail",
        "Open any call for the full transcript, every action Ava took, and an AI summary.",
    ),
    ("n_teach", "Teach Ava your prices, hours and FAQs in minutes. No code."),
    (
        "n_trust",
        "She only offers times that are really free, never double-books, and hands off to "
        "your team whenever a caller asks.",
    ),
    ("n_mobile", "Your front desk, in your pocket."),
    ("n_outro", "Receptly. Never miss a call again."),
]

DIALOGUE: list[tuple[str, str, str]] = [
    (
        "c1",
        "Ava",
        "Thank you for calling Luma Hair Studio, this is Ava. This call may be recorded "
        "and transcribed. How can I help you today?",
    ),
    ("c2", "Ayesha", "Hi! Can I get a haircut with Sara tomorrow afternoon?"),
    ("c3", "Ava", "Sara's free at 2:30 or 4 tomorrow. Which suits you best?"),
    ("c4", "Ayesha", "2:30, please."),
    (
        "c5",
        "Ava",
        "Perfect. A haircut with Sara, tomorrow at 2:30, for Ayesha Khan. Shall I book it?",
    ),
    ("c6", "Ayesha", "Yes, please!"),
    ("c7", "Ava", "Done! Your confirmation email is on its way. Anything else I can help with?"),
]


def request(client: genai.Client, contents: str, speech: types.SpeechConfig) -> bytes:
    last: Exception | None = None
    for model in MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"], speech_config=speech
                    ),
                )
                print(f"    via {model}")
                return resp.candidates[0].content.parts[0].inline_data.data
            except Exception as exc:
                last = exc
                msg = str(exc)
                if any(k in msg for k in ("per day", "404", "NOT_FOUND", "400 INVALID")):
                    print(f"    {model}: unavailable ({msg[:70]}), trying next model")
                    break
                print(f"    {model}: {msg[:70]} — retrying in {25 * (attempt + 1)}s")
                time.sleep(25 * (attempt + 1))
    raise RuntimeError(f"all TTS models failed: {last}")


def write(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)


def take(client: genai.Client, name: str, contents: str, speech: types.SpeechConfig) -> bytes:
    path = OUT / f"_{name}.wav"
    if path.exists():
        with wave.open(str(path), "rb") as w:
            return w.readframes(w.getnframes())
    print(f"  recording take '{name}'")
    pcm = request(client, contents, speech)
    write(path, pcm)
    return pcm


def split(pcm: bytes, parts: int, threshold: int = 700) -> list[bytes]:
    """Cut a take into `parts` lines at its parts-1 longest pauses."""
    s = array.array("h", pcm)
    win = RATE // 50  # 20 ms windows
    loud = [
        max((abs(v) for v in s[i : i + win]), default=0) >= threshold for i in range(0, len(s), win)
    ]
    gaps: list[tuple[int, int]] = []  # (length in windows, middle window)
    run = 0
    for i, is_loud in enumerate([*loud, True]):
        if not is_loud:
            run += 1
            continue
        if run and i - run > 0:  # ignore leading silence
            gaps.append((run, i - run // 2))
        run = 0
    cuts = sorted(mid * win for _, mid in sorted(gaps, reverse=True)[: parts - 1])
    bounds = [0, *cuts, len(s)]
    return [s[a:b].tobytes() for a, b in itertools.pairwise(bounds)]


def trim(pcm: bytes, threshold: int = 700) -> bytes:
    s = array.array("h", pcm)
    start = next((i for i, v in enumerate(s) if abs(v) > threshold), 0)
    end = next((i for i in range(len(s) - 1, -1, -1) if abs(s[i]) > threshold), len(s) - 1)
    pad = int(RATE * 0.04)
    return s[max(0, start - pad) : min(len(s), end + pad)].tobytes()


def voice(name: str) -> types.VoiceConfig:
    return types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=name))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1beta")
    )
    # Blank lines between lines give the reader a clear pause to split on.
    narration = take(
        client,
        "narration",
        "\n\n".join(t for _, t in NARRATION),
        types.SpeechConfig(voice_config=voice(NARRATOR_VOICE)),
    )
    dialogue = take(
        client,
        "dialogue",
        "\n".join(f"{who}: {t}" for _, who, t in DIALOGUE),
        types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    types.SpeakerVoiceConfig(speaker="Ava", voice_config=voice(AVA_VOICE)),
                    types.SpeakerVoiceConfig(speaker="Ayesha", voice_config=voice(CALLER_VOICE)),
                ]
            )
        ),
    )
    groups = [
        ([(i, t, NARRATOR_VOICE) for i, t in NARRATION], narration),
        (
            [(i, t, AVA_VOICE if w == "Ava" else CALLER_VOICE) for i, w, t in DIALOGUE],
            dialogue,
        ),
    ]
    manifest: dict[str, dict[str, object]] = {}
    for lines, pcm in groups:
        for (line_id, text, spk), seg in zip(lines, split(pcm, len(lines)), strict=True):
            seg = trim(seg)
            write(OUT / f"{line_id}.wav", seg)
            seconds = len(seg) / 2 / RATE
            manifest[line_id] = {
                "file": f"vo/{line_id}.wav",
                "seconds": round(seconds, 3),
                "text": text,
                "voice": spk,
            }
            per_word = seconds / max(1, len(text.split()))
            flag = "  <- check" if per_word > 0.6 or per_word < 0.15 else ""
            print(f"  {line_id:11} {seconds:5.1f}s  {text[:60]}{flag}")
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(float(str(v["seconds"])) for v in manifest.values())
    print(f"wrote {MANIFEST.name}: {len(manifest)} clips, {total:.1f}s of voice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
