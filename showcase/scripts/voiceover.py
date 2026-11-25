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

NARRATOR_VOICE = "Sulafat"  # warm
AVA_VOICE = "Aoede"  # the receptionist's voice in the product
CALLER_VOICE = "Leda"  # Ayesha, the caller

# Problem first, then the answer. Plain words only: no product internals.
NARRATION: list[tuple[str, str]] = [
    (
        "n_hook",
        "It's Saturday morning. Every chair is full, your hands are busy, "
        "and the phone keeps ringing.",
    ),
    (
        "n_cost",
        "Each call you can't answer is a customer who quietly books somewhere else.",
    ),
    (
        "n_intro",
        "Meet Ava, your receptionist from Receptly. She answers every call, day and night, "
        "in a warm, natural voice.",
    ),
    (
        "n_confirm",
        "The booking goes straight into your calendar, and your customer gets a "
        "confirmation text right away.",
    ),
    (
        "n_waitlist",
        "A reminder goes out the day before. If someone can't make it, the time is offered "
        "to the next person on your waitlist, so your chairs stay full.",
    ),
    (
        "n_team",
        "Ava knows who is working and when, including days off and lunch breaks, "
        "so she only offers times that really work.",
    ),
    (
        "n_value",
        "At a glance, you can see every call, and how much business Ava brought in, "
        "even while you were closed.",
    ),
    (
        "n_trust",
        "She never double-books, never guesses, and passes callers to your team "
        "whenever they ask for a person.",
    ),
    (
        "n_setup",
        "Getting started takes minutes. Add your hours, your team and your services, "
        "and Ava is ready.",
    ),
    ("n_outro", "Receptly. Never miss a call, or a customer, again."),
]

DIALOGUE: list[tuple[str, str, str]] = [
    (
        "c1",
        "Ava",
        "Thank you for calling Luma Hair Studio, this is Ava. This call may be recorded "
        "and transcribed. How can I help you today?",
    ),
    ("c2", "Ayesha", "Hi! Could I book a haircut with Sara tomorrow afternoon?"),
    (
        "c3",
        "Ava",
        "Of course. Sara has two thirty or four o'clock tomorrow. Which would you prefer?",
    ),
    ("c4", "Ayesha", "Two thirty would be perfect."),
    (
        "c5",
        "Ava",
        "Lovely. That's a haircut with Sara, tomorrow at two thirty, for Ayesha Khan. "
        "Shall I confirm it?",
    ),
    ("c6", "Ayesha", "Yes, please."),
    (
        "c7",
        "Ava",
        "You're all set! I've sent you a confirmation text. "
        "Is there anything else I can help with?",
    ),
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


def split(pcm: bytes, texts: list[str], threshold: int = 700) -> list[bytes]:
    """Cut a take into one clip per line.

    Chooses all cuts together (dynamic programming over the pauses): each clip's length
    should match its share of the text, and cuts prefer longer pauses. Picking the N
    longest pauses alone fails when a line has a long pause of its own (after a full
    stop), and the pace drifts too much for fixed positions.
    """
    s = array.array("h", pcm)
    win = RATE // 50  # 20 ms windows
    loud = [
        max((abs(v) for v in s[i : i + win]), default=0) >= threshold for i in range(0, len(s), win)
    ]
    speech = [i for i, x in enumerate(loud) if x]
    n = len(texts)
    if not speech or n < 2:
        return [pcm]
    first, last = speech[0], speech[-1]
    pauses: list[tuple[int, int]] = []  # (middle window, length in windows) inside the speech
    run = 0
    for i, is_loud in enumerate(loud):
        if not is_loud:
            run += 1
            continue
        if run >= 8 and first < i - run and i <= last:  # >= 160 ms
            pauses.append((i - run // 2, run))
        run = 0
    points = [(first, 0), *pauses, (last, 0)]
    chars = [max(1, len(t)) for t in texts]
    per_char = (last - first) / sum(chars)
    inf = float("inf")
    m = len(points)
    # best[k][j]: lowest cost for the first k lines ending at point j
    best = [[inf] * m for _ in range(n + 1)]
    back = [[0] * m for _ in range(n + 1)]
    best[0][0] = 0.0
    for k in range(1, n + 1):
        want = chars[k - 1] * per_char
        for j in range(1, m):
            if k == n and j != m - 1:
                continue
            for a in range(j):
                if best[k - 1][a] == inf:
                    continue
                dur = points[j][0] - points[a][0]
                cost = ((dur - want) / want) ** 2 - 0.02 * points[j][1]
                if best[k - 1][a] + cost < best[k][j]:
                    best[k][j], back[k][j] = best[k - 1][a] + cost, a
    cuts = []
    j = m - 1
    for k in range(n, 1, -1):
        j = back[k][j]
        cuts.append(points[j][0])
    bounds = [0, *(c * win for c in reversed(cuts)), len(s)]
    return [s[a:b].tobytes() for a, b in itertools.pairwise(bounds)]


def trim(pcm: bytes, threshold: int = 700) -> bytes:
    s = array.array("h", pcm)
    start = next((i for i, v in enumerate(s) if abs(v) > threshold), 0)
    end = next((i for i in range(len(s) - 1, -1, -1) if abs(s[i]) > threshold), len(s) - 1)
    pad = int(RATE * 0.04)
    return s[max(0, start - pad) : min(len(s), end + pad)].tobytes()


def on_screen(text: str) -> str:
    """Times are spelled out for the voice, shown as numbers on screen."""
    return (
        text.replace("two thirty", "2:30")
        .replace("Two thirty", "2:30")
        .replace("four o'clock", "4:00")
    )


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
        segments = split(pcm, [t for _, t, _ in lines])
        for (line_id, text, spk), seg in zip(lines, segments, strict=True):
            seg = trim(seg)
            write(OUT / f"{line_id}.wav", seg)
            seconds = len(seg) / 2 / RATE
            manifest[line_id] = {
                "file": f"vo/{line_id}.wav",
                "seconds": round(seconds, 3),
                "text": on_screen(text),
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
