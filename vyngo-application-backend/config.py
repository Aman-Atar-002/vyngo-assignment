import os
import sqlite3

from groq import Groq


groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

LLM_MODEL = "openai/gpt-oss-120b"
STT_MODEL = "whisper-large-v3"
TTS_VOICE = "en-IN-NeerjaNeural"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.db")

SLOT_NAMES = ["budget_max", "body_type", "fuel", "city", "purpose", "make", "model"]
ACTIONS = ["search", "new_search", "vehicle_question", "other"]
ALLOWED = {
    "body_type": ["mini_truck", "pickup", "truck", "three_wheeler", "van", "car"],
    "fuel": ["diesel", "petrol", "cng", "electric"],
}

# a search for the key also matches these body types
BODY_GROUPS = {"truck": ["truck", "mini_truck"]}

# ranking weights (add up to 1.0)
WEIGHTS = {"price": 0.30, "km": 0.30, "year": 0.25, "papers": 0.15}

SLOT_LABELS = {"budget_max": "budget", "body_type": "body type", "fuel": "fuel type",
               "city": "city", "make": "make", "model": "model"}


QUESTION_ATTRIBUTES = ["price", "km", "year", "payload", "gvw", "fuel", "city", "papers", "body_type"]

STT_PROMPT = (
    "Used commercial vehicle search. Hinglish: chhota truck chahiye, 5 lakh ke andar, "
    "Pune mein diesel pickup dikhao. "
    "Truck, mini truck, pickup, car, diesel, CNG, petrol, lakh. "
    "Makes: Tata, Mahindra, Maruti, Ashok Leyland, Eicher, Piaggio, Bajaj. "
    "Models: Ace, Jeeto, Super Carry, Dost, Bolero Pickup, Yodha, Partner, Ape, Eeco. "
    "Cities: Pune, Mumbai, Delhi, Bengaluru, Chennai, Hyderabad, Ahmedabad."
)


def load_catalog_values():
    conn = sqlite3.connect(DB_PATH)
    makes = [r[0] for r in conn.execute("SELECT DISTINCT make FROM vehicles ORDER BY make")]
    models = [r[0] for r in conn.execute("SELECT DISTINCT model FROM vehicles ORDER BY model")]
    conn.close()
    return makes, models


CATALOG_MAKES, CATALOG_MODELS = load_catalog_values()