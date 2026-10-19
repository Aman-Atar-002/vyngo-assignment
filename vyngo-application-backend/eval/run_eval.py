import contextlib
import io
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BODY_GROUPS, LLM_MODEL
from pipeline import process_turn, sessions

FILTER_SLOTS = ["budget_max", "body_type", "fuel", "city", "make", "model"]  # purpose is not a filter
EVAL_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_latency_log.jsonl")
# "expect" = the filters that must be active after the LAST turn. Unlisted slots must be empty.
CASES = [
    {"name": "basic: diesel pickup, budget, city",
     "turns": ["diesel pickup under 5 lakh in Pune"],
     "expect": {"fuel": "diesel", "body_type": "pickup", "budget_max": 500000, "city": "Pune"}},
    {"name": "make + body type + city",
     "turns": ["I need a Tata truck in Mumbai"],
     "expect": {"make": "Tata", "body_type": "truck", "city": "Mumbai"}},
    {"name": "cng van with budget",
     "turns": ["show me CNG vans under 6 lakh"],
     "expect": {"fuel": "cng", "body_type": "van", "budget_max": 600000}},
    {"name": "mini truck with budget",
     "turns": ["mini truck under 4 lakh for city delivery"],
     "expect": {"body_type": "mini_truck", "budget_max": 400000}},
    {"name": "make + model + city",
     "turns": ["Mahindra Jeeto in Delhi"],
     "expect": {"make": "Mahindra", "model": "Jeeto", "city": "Delhi"}},
    {"name": "electric three wheeler",
     "turns": ["electric three wheeler under 4 lakh"],
     "expect": {"fuel": "electric", "body_type": "three_wheeler", "budget_max": 400000}},
    {"name": "two-word make",
     "turns": ["Ashok Leyland pickup under 8 lakh"],
     "expect": {"make": "Ashok Leyland", "body_type": "pickup", "budget_max": 800000}},
    {"name": "petrol trucks in a city",
     "turns": ["petrol trucks in Bengaluru"],
     "expect": {"fuel": "petrol", "body_type": "truck", "city": "Bengaluru"}},
    {"name": "hinglish 1",
     "turns": ["chhota truck chahiye, 5 lakh ke andar, city delivery ke liye"],
     "expect": {"body_type": "mini_truck", "budget_max": 500000}},
    {"name": "hinglish 2",
     "turns": ["Pune mein diesel pickup chahiye 8 lakh tak"],
     "expect": {"city": "Pune", "fuel": "diesel", "body_type": "pickup", "budget_max": 800000}},
    {"name": "correction: fuel only",
     "turns": ["diesel truck under 5 lakh in Pune", "no, make it CNG"],
     "expect": {"fuel": "cng", "body_type": "truck", "budget_max": 500000, "city": "Pune"}},
    {"name": "correction: budget only",
     "turns": ["Tata pickup under 8 lakh", "no, under 6 lakh"],
     "expect": {"make": "Tata", "body_type": "pickup", "budget_max": 600000}},
    {"name": "clear one slot",
     "turns": ["diesel truck in Chennai", "any city is fine"],
     "expect": {"fuel": "diesel", "body_type": "truck"}},
    {"name": "fresh request resets old slots",
     "turns": ["Tata vehicles in Mumbai", "show me petrol trucks in Hyderabad"],
     "expect": {"fuel": "petrol", "body_type": "truck", "city": "Hyderabad"}},
    {"name": "zero results + relaxation message",
     "turns": ["electric truck under 50,000 rupees"],
     "expect": {"fuel": "electric", "body_type": "truck", "budget_max": 50000},
     "zero": True},
    {"name": "follow-up: km of the first vehicle",
     "turns": ["diesel pickup under 10 lakh", "what is the km of the first one"],
     "expect": {"fuel": "diesel", "body_type": "pickup", "budget_max": 1000000},
     "action": "vehicle_question", "answer_km": True},
]


def norm(v):
    return v.lower().strip() if isinstance(v, str) else v


def check_slots(actual, expected):
    errors = []
    for name in FILTER_SLOTS:
        want, got = expected.get(name), actual.get(name)
        if norm(got) != norm(want):
            errors.append(f"{name}: expected {want!r}, got {got!r}")
    return errors


def check_walls(results, expected):

    errors = []
    for v in results:
        who = f"{v['make']} {v['model']} (id {v['id']})"
        if "budget_max" in expected and v["price"] > expected["budget_max"]:
            errors.append(f"WALL BROKEN: {who} costs {v['price']}, budget {expected['budget_max']}")
        if "fuel" in expected and v["fuel"] != expected["fuel"]:
            errors.append(f"WALL BROKEN: {who} is {v['fuel']}, wanted {expected['fuel']}")
        if "city" in expected and v["city"].lower() != expected["city"].lower():
            errors.append(f"WALL BROKEN: {who} is in {v['city']}, wanted {expected['city']}")
        if "make" in expected and v["make"].lower() != expected["make"].lower():
            errors.append(f"WALL BROKEN: {who} is {v['make']}, wanted {expected['make']}")
        if "model" in expected and expected["model"].lower() not in v["model"].lower():
            errors.append(f"WALL BROKEN: {who} does not match model {expected['model']}")
        if "body_type" in expected:
            allowed = BODY_GROUPS.get(expected["body_type"], [expected["body_type"]])
            if v["body_type"] not in allowed:
                errors.append(f"WALL BROKEN: {who} is {v['body_type']}, wanted {expected['body_type']}")
    return errors


def run_case(case):
    sid = str(uuid.uuid4())
    llm_ms, search_ms, data = [], [], None
    with contextlib.redirect_stdout(io.StringIO()):          
        for text in case["turns"]:
            data = process_turn(sid, text, speak=False, log_file=EVAL_LOG)
            llm_ms.append(data["latency_ms"]["llm"])
            search_ms.append(data["latency_ms"]["search"])

    errors = check_slots(data["slots"], case["expect"])
    action = data["delta"]["action"]

    if "action" in case and action != case["action"]:
        errors.append(f"action: expected {case['action']!r}, got {action!r}")
    if action in ("search", "new_search"):
        errors += check_walls(data["results"], case["expect"])
    if case.get("zero"):
        if data["results"] or data["total_matches"]:
            errors.append(f"expected zero results, got {data['total_matches']}")
        if "could not find" not in data["answer_text"]:
            errors.append("zero-result message was not spoken")
    if case.get("answer_km"):
        shown = sessions[sid]["last_shown"]
        if not shown:
            errors.append("no vehicles were shown before the follow-up")
        elif f"{shown[0]['km_driven']:,}" not in data["answer_text"]:
            errors.append(f"answer does not contain the first vehicle's km ({shown[0]['km_driven']:,})")
    if errors:
        errors.append(f"slots were: {data['slots']}")
    return errors, llm_ms, search_ms


def main():
    if os.path.exists(EVAL_LOG):
        os.remove(EVAL_LOG)
    lines = []

    def emit(line=""):
        print(line)
        lines.append(line)

    emit(f"Eval run {time.strftime('%Y-%m-%d %H:%M')} | LLM {LLM_MODEL} | {len(CASES)} cases")
    emit()
    passed, llm_all, search_all = 0, [], []

    for i, case in enumerate(CASES, 1):
        try:
            errors, llm_ms, search_ms = run_case(case)
        except Exception as e:
            errors, llm_ms, search_ms = [f"CRASH: {e}"], [], []
        llm_all += llm_ms
        search_all += search_ms
        if not errors:
            passed += 1
        emit(f"{'PASS' if not errors else 'FAIL'}  {i:>2}. {case['name']}")
        for e in errors:
            emit(f"        - {e}")

    rate = round(100 * passed / len(CASES))
    emit()
    emit(f"Pass rate: {passed}/{len(CASES)} ({rate}%)")
    if llm_all:
        emit(f"Avg understanding (LLM) latency: {round(sum(llm_all) / len(llm_all))} ms | "
             f"avg search: {round(sum(search_all) / len(search_all), 1)} ms")

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()