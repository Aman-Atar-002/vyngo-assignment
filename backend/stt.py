from fastapi import UploadFile

from config import STT_MODEL, STT_PROMPT, groq_client


def transcribe(audio: UploadFile) -> str:
    result = groq_client.audio.transcriptions.create(
        file=(audio.filename or "audio.webm", audio.file.read()),
        model=STT_MODEL,
        # language="en",
        prompt=STT_PROMPT,
        temperature=0,
    )
    return result.text.strip()