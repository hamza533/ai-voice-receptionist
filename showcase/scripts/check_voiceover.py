"""Transcribe every voiceover clip and compare it with the script.

Catches TTS mistakes (extra words, instructions read aloud, missing phrases) before render.
Exit code 1 lists clips to delete and regenerate.

    GEMINI_API_KEY=... python scripts/check_voiceover.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash"]


def words(text: str) -> list[str]:
    text = text.lower().replace("2:30", "two thirty").replace("4:00", "four")
    return re.findall(r"[a-z]+", text)


def transcribe(client: genai.Client, data: bytes) -> str:
    for model in MODELS:
        for _ in range(2):
            try:
                r = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=data, mime_type="audio/wav"),
                        "Transcribe this audio exactly. Output only the spoken words.",
                    ],
                )
                return (r.text or "").strip()
            except Exception:
                time.sleep(4)
    raise RuntimeError("no transcription model available")


def main() -> int:
    manifest = json.loads((ROOT / "src" / "voiceover.json").read_text(encoding="utf-8"))
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1beta")
    )
    bad = []
    for clip_id, info in manifest.items():
        heard = transcribe(client, (ROOT / "public" / info["file"]).read_bytes())
        want, got = words(info["text"]), words(heard)
        extra = len(got) - len(want)
        missing = [w for w in want if w not in got]
        ok = extra <= 2 and len(missing) <= max(1, len(want) // 10)
        print(f"{'OK ' if ok else 'BAD'} {clip_id:11} {info['seconds']:5.1f}s  {heard[:90]}")
        if not ok:
            bad.append(clip_id)
    if bad:
        print("regenerate:", " ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
