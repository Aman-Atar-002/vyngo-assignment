import json
import time
from config import QUESTION_ATTRIBUTES 

from config import (ACTIONS, ALLOWED, CATALOG_MAKES, CATALOG_MODELS, LLM_MODEL,
                    SLOT_NAMES, groq_client)

EXAMPLE = json.dumps({
    "action": "search",
    "slots": {"budget_max": 500000, "body_type": "truck", "fuel": "cng",
              "city": None, "purpose": None, "make": "Tata", "model": None},
    "clear_slots": [],
    "question": {"vehicle": None, "attribute": None},
})

SYSTEM_PROMPT = f"""You extract search filters for a used commercial vehicle marketplace.
Return ONLY a JSON object shaped like this example:
{EXAMPLE}

Rules:
- Fill a slot ONLY if the user mentioned it in THIS message. Otherwise null.
- budget_max is an integer in rupees. 1 lakh = 100000. "under 5 lakh" -> 500000.
- body_type must be one of {ALLOWED["body_type"]}. Plain "truck" -> "truck". Use "mini_truck" only if the user says "mini", "small", "chhota" or "Ace-type".
- fuel must be one of {ALLOWED["fuel"]}.
- city is a city name. purpose is a short phrase like "city delivery".
- make must be one of {CATALOG_MAKES}. "Tata truck" -> make "Tata" AND body_type "truck".
- model is a model name (or part of one) from {CATALOG_MODELS}, e.g. "Ace" or "Jeeto".
- Words like "truck", "pickup", "van", "car" are body types, never a make or model. Do not clear body_type when one of them is said.
- Generic words like "vehicle", "vehicles", "any type", "anything" mean ANY body type: put "body_type" in clear_slots.
- Likewise "any fuel" -> clear "fuel", "any city" or "anywhere" -> clear "city", "any budget" or "no budget limit" -> clear "budget_max", "any make" -> clear "make".
- action: "search" if the user states or changes requirements (including corrections like "no, CNG");
  "new_search" if the user starts a completely different request;
  "vehicle_question" if the user asks about a vehicle already shown;
  "other" for anything else.
- If the user states a complete fresh request (for example "show me petrol trucks in Mumbai") that mentions 2 or more slots and is NOT a correction or refinement (no words like "no", "nahi", "instead", "also", "same", "but", "only"), use action "new_search" and fill every slot they mention.
- clear_slots: slot names the user wants removed.
- For action "vehicle_question", leave all slots null and fill "question":
  "vehicle" is the position number (1, 2 or 3) from "Vehicles last shown": "first"/"pehla" = 1, "second"/"doosra" = 2, "third"/"teesra" = 3, "the Tata one" = the matching position, "the cheapest" = the lowest price position. Use null if the user only says "it", "uska" or "that one".
  "attribute" is one of {QUESTION_ATTRIBUTES}: "price" for cost/kimat/daam, "km" for kilometres driven, "year", "payload" for load capacity, "gvw", "fuel", "city" for location, "papers" for verified papers/documents, "body_type".
- Use "vehicle_question" ONLY when the user asks for a fact (km, price, year, payload, city, papers) about a vehicle already shown. If the user mentions a fuel, budget, city, make or body type, it is a "search".
- For every other action, "question" values are null.
You are given the current slots only for context. Do not repeat them unless mentioned again."""


def new_slots():
    return {name: None for name in SLOT_NAMES}


def clean_delta(raw):

    slots_in = raw.get("slots") or {}
    slots = {}
    for name in SLOT_NAMES:
        value = slots_in.get(name)
        if value is None:
            continue

        if name == "make":
            match = next((m for m in CATALOG_MAKES if m.lower() == str(value).lower()), None)
            if not match:
                print(f"DROPPED invalid make: {value!r}")
                continue
            value = match
        elif name == "model":
            v = str(value).strip().lower()
            if not v or not any(v in m.lower() for m in CATALOG_MODELS):
                print(f"DROPPED invalid model: {value!r}")
                continue
            value = str(value).strip()
        elif name in ALLOWED and value not in ALLOWED[name]:
            print(f"DROPPED invalid {name}: {value!r}")
            continue
        elif name == "budget_max":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue

        slots[name] = value

    action = raw.get("action")
    if action not in ACTIONS:
        action = "search"
    clear = [s for s in (raw.get("clear_slots") or []) if s in SLOT_NAMES]

    q_in = raw.get("question") or {}
    try:
        vehicle = int(q_in.get("vehicle"))
    except (TypeError, ValueError):
        vehicle = None
    attribute = q_in.get("attribute")
    if attribute not in QUESTION_ATTRIBUTES:
        attribute = None
    question = {"vehicle": vehicle, "attribute": attribute}

    if action == "vehicle_question":
        slots, clear = {}, []   

    return {"action": action, "slots": slots, "clear_slots": clear,"question": question}


def shown_summary(last_shown):

    if not last_shown:
        return "none"
    return "; ".join(
        f"{i}. {v['make']} {v['model']} {v['year']}, price {v['price']}, {v['km_driven']} km"
        for i, v in enumerate(last_shown, 1)
    )

def extract_delta(transcript, current_slots, last_shown):

    start = time.perf_counter()
    resp = groq_client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                f"Current slots: {json.dumps(current_slots)}\n"
                f"Vehicles last shown: {shown_summary(last_shown)}\n"
                f"User said: {transcript}"},
        ],
    )
    llm_ms = round((time.perf_counter() - start) * 1000)
    try:
        raw = json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        raw = {}
    return clean_delta(raw), llm_ms


def apply_delta(slots, delta):

    if delta["action"] == "new_search":
        for name in SLOT_NAMES:
            slots[name] = None
    for name in delta["clear_slots"]:
        slots[name] = None
    for name, value in delta["slots"].items():
        slots[name] = value