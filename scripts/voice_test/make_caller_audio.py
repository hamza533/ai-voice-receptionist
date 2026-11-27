"""Generate a spoken caller script with Gemini TTS for automated voice tests.

The WAV is used as Chrome's fake microphone (--use-file-for-fake-audio-capture), so a real
web call can be placed against the running agent without a human. Several caller turns
are separated by "||" and spaced GAP_S seconds apart (start of each turn).

    python scripts/voice_test/make_caller_audio.py out.wav "Hi, can I book a haircut?||Yes please."
"""

from __future__ import annotations

import array
import os
import sys
import time
import wave

from google import genai
from google.genai import types

RATE = 48000  # Chrome's fake capture device expects 48 kHz
LEAD_SILENCE_S = float(os.environ.get("LEAD_S", "24"))  # dispatch + connect + greeting
GAP_S = float(os.environ.get("GAP_S", "16"))  # from one caller turn to the next
TAIL_SILENCE_S = 40.0  # time for Ava to answer before Chrome loops the file


def tts(client: genai.Client, text: str, voice: str) -> bytes:
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts"),
                contents=text,  # text only: TTS models read style instructions aloud
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                        )
                    ),
                ),
            )
            pcm24 = resp.candidates[0].content.parts[0].inline_data.data  # 24 kHz mono
            samples = array.array("h", pcm24)
            return array.array("h", (s for s in samples for _ in (0, 1))).tobytes()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(40)  # free tier: 3 TTS requests per minute
    return b""


def main() -> None:
    out, script = sys.argv[1], sys.argv[2]
    voice = os.environ.get("CALLER_VOICE", "Puck")
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1beta")
    )
    audio = b""
    cursor = LEAD_SILENCE_S
    for i, line in enumerate(t.strip() for t in script.split("||")):
        if i:
            time.sleep(21)  # stay under the free-tier TTS rate limit
        speech = tts(client, line, voice)
        start = LEAD_SILENCE_S + i * GAP_S
        audio += b"\x00\x00" * int(RATE * max(0.0, start - cursor)) + speech
        cursor = start + len(speech) / 2 / RATE
        print(f"turn {i + 1} at {start:.0f}s ({len(speech) / 2 / RATE:.1f}s): {line}")
    audio += b"\x00\x00" * int(RATE * TAIL_SILENCE_S)
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio)
    print(f"wrote {out}: {len(audio) / 2 / RATE:.0f}s")


if __name__ == "__main__":
    main()
