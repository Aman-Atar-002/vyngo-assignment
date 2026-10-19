import json
import os
import time

from response import build_answer, build_followup, invalid_numbers
from search import search
from tts import synthesize
from understanding import apply_delta, extract_delta, new_slots

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latency_log.jsonl")

# one entry per browser session
sessions = {}


def process_turn(session_id, transcript, stt_ms=0, speak=True,log_file=LOG_PATH):
    session = sessions.setdefault(
        session_id, {"slots": new_slots(), "last_shown": [], "focus": None}
    )
    delta, llm_ms = extract_delta(transcript, session["slots"], session["last_shown"])
    apply_delta(session["slots"], delta)

    print("TRANSCRIPT:", transcript)
    print("DELTA:", delta)
    print("SLOTS:", session["slots"])

    results, total, filter_text, search_ms = [], 0, "none", 0
    answer_text, extra, grounded = "", set(), []

    if delta["action"] in ("search", "new_search"):
        results, total, filter_text, search_ms = search(session["slots"])
        session["last_shown"] = results
        session["focus"] = None
        answer_text, extra = build_answer(delta["action"], results, total, session["slots"])
        grounded = results
    elif delta["action"] == "vehicle_question":
        answer_text, vehicle, pos = build_followup(
            delta["question"], session["last_shown"], session["focus"]
        )
        if pos is not None:
            session["focus"] = pos
        grounded = [vehicle] if vehicle else []

    bad = invalid_numbers(answer_text, grounded, extra)
    if bad:
        print("VALIDATOR BLOCKED, unknown numbers:", bad)
        answer_text = "Sorry, I could not prepare a reliable answer. Please try again."

    audio_b64, tts_ms = "", 0
    if answer_text and speak:
        audio_b64, tts_ms = synthesize(answer_text)
    print("ANSWER:", answer_text)

    latency = {"stt": stt_ms, "llm": llm_ms, "search": search_ms, "tts": tts_ms}
    with open(log_file, "a") as f:
        f.write(json.dumps({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "transcript": transcript,
            "action": delta["action"],
            "spoken": speak,
            "latency_ms": latency,
            "server_total_ms": round(sum(latency.values())),
        }) + "\n")

    return {
        "transcript": transcript,
        "delta": delta,
        "slots": session["slots"],
        "filter": filter_text,
        "total_matches": total,
        "results": results,
        "answer_text": answer_text,
        "audio_b64": audio_b64,
        "latency_ms": latency,
    }