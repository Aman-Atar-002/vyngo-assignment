import re

from config import SLOT_LABELS
from search import best_relaxation


def lakh(price):
    return f"{price / 100000:.2f}"        


def facts(v):
    
    nums = {lakh(v["price"]), str(v["km_driven"]), str(v["year"]),
            str(v["payload_kg"]), str(v["gvw_kg"])}
    nums |= set(re.findall(r"\d+", v["model"]))   # digits inside the catalog model name
    return nums


def reasons_for(v, top):
    reasons = []
    if len(top) > 1:
        if v["price"] == min(x["price"] for x in top):
            reasons.append("it is the lowest priced of these")
        if v["km_driven"] == min(x["km_driven"] for x in top):
            reasons.append("it has the fewest kilometres driven")
        if v["year"] == max(x["year"] for x in top):
            reasons.append("it is the newest")
    if v["papers_verified"]:
        reasons.append("its papers are verified")
    return reasons[:2] or ["it matches all your filters"]


def describe(v, top, ordinal):
    return (f"{ordinal}: {v['make']} {v['model']}, {v['year']}, "
            f"{lakh(v['price'])} lakh rupees, {v['km_driven']:,} kilometres, "
            f"{v['fuel']}, in {v['city']}. "
            f"I picked it because {' and '.join(reasons_for(v, top))}.")


def build_answer(action, results, total, slots):
    
    if action not in ("search", "new_search"):
        return "", set()

    if not results:
        text = "I could not find any vehicles matching all your filters."
        extra = set()
        best = best_relaxation(slots)
        if best:
            text += f" If you drop the {SLOT_LABELS[best[0]]}, I found {best[1]} matches."
            extra.add(str(best[1]))
        else:
            text += " Try changing more than one requirement."
        return text, extra

    ordinals = ["First", "Second", "Third"]
    parts = [f"Here are the top {len(results)}."]
    parts += [describe(v, results, ordinals[i]) for i, v in enumerate(results)]
    return " ".join(parts), {str(total), str(len(results))}


def invalid_numbers(text, results, extra):
    
    allowed = {n.replace(",", "") for v in results for n in facts(v)}
    allowed |= extra
    spoken = [n.replace(",", "") for n in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)]
    return [n for n in spoken if n not in allowed]



def attribute_sentence(v, attr):
    name = f"{v['make']} {v['model']}"
    if attr == "price":
        return f"The {name} costs {lakh(v['price'])} lakh rupees."
    if attr == "km":
        return f"The {name} has run {v['km_driven']:,} kilometres."
    if attr == "year":
        return f"The {name} is a {v['year']} model."
    if attr == "payload":
        return f"The {name} can carry a payload of {v['payload_kg']} kilograms."
    if attr == "gvw":
        return f"The {name} has a gross vehicle weight of {v['gvw_kg']} kilograms."
    if attr == "fuel":
        return f"The {name} runs on {v['fuel']}."
    if attr == "city":
        return f"The {name} is located in {v['city']}."
    if attr == "papers":
        if v["papers_verified"]:
            return f"The {name} has verified papers."
        return f"The {name} does not have verified papers."
    return f"The {name} is a {v['body_type'].replace('_', ' ')}."


def build_followup(question, last_shown, focus):

    if not last_shown:
        return "I have not shown any vehicles yet. Tell me what you are looking for.", None, None

    pos = question["vehicle"] or focus
    if pos is None and len(last_shown) == 1:
        pos = 1
    if pos is None or not 1 <= pos <= len(last_shown):
        return "Which vehicle do you mean, the first, second or third?", None, None

    v = last_shown[pos - 1]
    if question["attribute"] is None:
        name = f"{v['make']} {v['model']}"
        return (f"What would you like to know about the {name}? I can tell you its price, "
                f"kilometres, year, payload, fuel, city or papers status."), v, pos
    return attribute_sentence(v, question["attribute"]), v, pos