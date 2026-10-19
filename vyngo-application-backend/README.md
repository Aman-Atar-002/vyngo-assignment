# Voice-Based Vehicle Search

A voice-first assistant for finding a used commercial vehicle. The buyer speaks, the system understands, searches a catalog with hard filters, and speaks back the top 3 results, each with a reason taken from catalog data.

```
voice -> STT -> slots -> hard SQL filters -> ranked top 3 -> validated answer -> TTS -> voice
```

Example: *"chhota truck chahiye, 5 lakh ke andar, city delivery ke liye"* (English and Hinglish both work).

---

## Quick start (about 10 minutes)

**You need:** Python 3.10+ (tested on 3.13), Node 18+, Chrome, and a free Groq API key from https://console.groq.com.

### 1) Backend

```bash
cd backend
pip install -r requirements.txt
```

Set your key (never commit it):

```powershell
# Windows PowerShell
$env:GROQ_API_KEY="your_key_here"
```
```bash
# Mac / Linux
export GROQ_API_KEY="your_key_here"
```

Start the server:

```bash
uvicorn main:app --reload or 

-- temrinal
python -m uvicorn main:app --reload --port 8000

The catalog (`backend/catalog.db`, 150 synthetic listings) is already in the repo. To rebuild it: `python generate_catalog.py` (seeded, so the data is identical every time).

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000, allow the microphone, tap the mic, speak, tap again to stop.

### 3) Run the eval (no server or browser needed)

```bash
cd backend
python eval/run_eval.py
```

---

## Demo script

| Turn | Say | What to check |
|---|---|---|
| 1. Search | "Diesel pickup under 10 lakh" | 3 cards, every price at most 10 lakh, spoken answer |
| 2. Correction | "No, make it CNG" | Only the **Fuel** box changes, the rest stay |
| 3. Zero result | "Electric truck under 50,000 rupees" | Red "No vehicles match" box and a spoken suggestion |
| 4. Follow-up | "What is the km of the second one?" | Answer read from row 2, cards stay on screen |
| Hinglish | "chhota truck chahiye, 5 lakh ke andar" | Body type = mini truck, Budget = 5,00,000 |

The **Applied filters** panel shows what the system understood after every turn. The backend terminal prints `DELTA`, `SLOTS`, `FILTER` and `ANSWER` for each turn.

---

## Architecture

```
Browser (Next.js)
   | audio + session_id
   v
FastAPI backend (one process)
   STT            Groq Whisper large-v3                 stt.py
   Understanding  LLM returns slot CHANGES only         understanding.py
   Session state  slots + last shown vehicles           pipeline.py
   Search         SQLite hard filters + weighted rank   search.py
   Response       templates from DB rows + validator    response.py
   TTS            edge-tts                              tts.py
   |
   v  transcript, slots, filter, results, answer, audio (base64), latency
Browser (shows filters, cards, plays audio)

Eval harness (eval/run_eval.py) and latency log (latency_log.jsonl)
call or sit beside the same pipeline.
```



## Eval

`backend/eval/run_eval.py` runs 16 test cases through the real pipeline (LLM, filters, search, answer, validator). It skips only the microphone and TTS. For each case it checks:
- the executed slots against the expected slots,
- every returned vehicle against the expected filters (the "walls"),
- for specific cases: the zero-result message, the action type, and that a follow-up answer contains the vehicle's real km.

Cases cover English, Hinglish, two-word makes, make + model, corrections (fuel only, budget only), clearing a slot, a fresh request that resets old slots, zero results, and a follow-up.


Notes:
- It calls the real Groq LLM, so it needs `GROQ_API_KEY`. On the free tier, rate limits can make a case show `CRASH`. Wait a minute and rerun.
- The eval types the sentences in, so it does not test the mic or Whisper. Test voice and Hinglish by speaking.
- The average LLM latency printed by the eval is inflated by rapid back-to-back calls. Use the live latency log for latency numbers.


## API

| Endpoint | Input | Use |
|---|---|---|
| `POST /voice-search` | form: `audio` file, `session_id` | The voice loop |
| `POST /text-search` | JSON: `session_id`, `transcript` | Typed input, curl tests |
| `POST /reset` | JSON: `session_id` | Clear the conversation |

```bash
curl -X POST localhost:8000/text-search -H "Content-Type: application/json" \
  -d '{"session_id":"t1","transcript":"diesel pickup under 5 lakh in Pune"}'
```

The response includes `slots`, `delta`, `filter` (the executed SQL conditions), `results` (with `score_parts`), `answer_text`, `audio_b64` and `latency_ms`.

---

## Known limits

- **Mishearing that lands on a valid value** (for example "5 lakh" heard as "50 lakh") runs the wrong filter silently. The transcript and Applied filters are on screen so the user can notice it.
- **`purpose` is not a filter**, because the catalog has no purpose column.
- **Follow-ups answer one attribute of one vehicle.** Comparisons ("which is cheaper?") are not handled.
- **No vendor fallback.** If Groq or edge-tts is down, the turn fails with an error message. Slot memory survives, so retrying works.
- **Sessions are in memory** in one process. They are lost on restart and would not be shared across workers (production: Redis).
- **edge-tts uses an unofficial endpoint.** It is free but not a production TTS.
- **Hinglish is best-effort.** Speech is auto-detected and understood, but the spoken answer is in English.
- **The catalog is synthetic.** Models and specs are realistic but approximate.

---

## Project layout

```
backend/
  config.py            constants, Groq client, catalog values, weights
  stt.py               speech to text
  understanding.py     LLM slot extraction, cleaning, merging
  search.py            filter builder, ranking, relaxation suggestion
  response.py          answer from rows, follow-ups, number validator
  tts.py               text to speech
  pipeline.py          sessions + one full turn + latency log
  main.py              FastAPI endpoints
  generate_catalog.py  builds catalog.db (150 listings)
  catalog.db           the catalog
  eval/run_eval.py     eval harness
  eval/results.txt     last eval report
  requirements.txt
frontend/              Next.js page (mic, filters panel, result cards, audio)
```

---

## Credits and AI use

- **Groq** hosted `whisper-large-v3` (STT) and `openai/gpt-oss-120b` (slot extraction).
- **edge-tts** (https://github.com/rany2/edge-tts) for speech synthesis.
- **FastAPI**, **Next.js**, **Tailwind CSS**, **shadcn/ui** and **lucide-react**. The initial page layout was generated with v0 and then rewritten.
- AI coding assistants (Claude) were used while building. I have reviewed the code and can explain it.
