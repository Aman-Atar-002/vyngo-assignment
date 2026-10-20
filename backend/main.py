import time

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pipeline import process_turn, sessions
from stt import transcribe
from understanding import new_slots

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/voice-search")
def voice_search(audio: UploadFile = File(...), session_id: str = Form("default")):
    start = time.perf_counter()
    transcript = transcribe(audio)
    stt_ms = round((time.perf_counter() - start) * 1000)

    if not transcript:
        raise HTTPException(status_code=422, detail="No speech detected")

    return process_turn(session_id, transcript, stt_ms)


@app.post("/text-search")  # for curl tests and the eval script
def text_search(session_id: str = Body(...), transcript: str = Body(...)):
    return process_turn(session_id, transcript)


@app.post("/reset")
def reset(session_id: str = Body(..., embed=True)):
    sessions.pop(session_id, None)
    return {"slots": new_slots()}