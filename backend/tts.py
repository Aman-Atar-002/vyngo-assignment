import asyncio
import base64
import re
import time

import edge_tts

from config import TTS_VOICE


async def synth_one(text):
    audio = b""
    async for chunk in edge_tts.Communicate(text, TTS_VOICE).stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return audio


async def synth_all(parts):
    return await asyncio.gather(*(synth_one(p) for p in parts))   # keeps the order


def synthesize(text):
    start = time.perf_counter()
    # intro, First, Second, Third become separate chunks; a short answer stays one chunk
    parts = [p for p in re.split(r"\s(?=(?:First|Second|Third):)", text) if p.strip()]
    audio = b"".join(asyncio.run(synth_all(parts)))
    return base64.b64encode(audio).decode(), round((time.perf_counter() - start) * 1000)