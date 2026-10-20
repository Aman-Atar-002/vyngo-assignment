import sqlite3
import time

from config import BODY_GROUPS, DB_PATH, SLOT_LABELS, WEIGHTS


def build_query(slots):

    where, params = [], []
    if slots["budget_max"] is not None:
        where.append("price <= ?")
        params.append(slots["budget_max"])
    if slots["body_type"]:
        options = BODY_GROUPS.get(slots["body_type"], [slots["body_type"]])
        where.append("body_type IN (" + ",".join("?" * len(options)) + ")")
        params.extend(options)
    if slots["fuel"]:
        where.append("fuel = ?")
        params.append(slots["fuel"])
    if slots["city"]:
        where.append("LOWER(city) = LOWER(?)")
        params.append(slots["city"])
    if slots["make"]:
        where.append("LOWER(make) = LOWER(?)")
        params.append(slots["make"])
    if slots["model"]:
        where.append("LOWER(model) LIKE ?")
        params.append(f"%{slots['model'].lower()}%")

    sql = "SELECT * FROM vehicles"
    if where:
        sql += " WHERE " + " AND ".join(where)
    return sql, params, where


def normalize(value, low, high, lower_is_better):
    if high == low:
        return 1.0
    score = (value - low) / (high - low)
    return 1 - score if lower_is_better else score


def rank(rows):
    
    if not rows:
        return []
    p = [r["price"] for r in rows]
    k = [r["km_driven"] for r in rows]
    y = [r["year"] for r in rows]
    for r in rows:
        parts = {
            "price": round(WEIGHTS["price"] * normalize(r["price"], min(p), max(p), True), 3),
            "km": round(WEIGHTS["km"] * normalize(r["km_driven"], min(k), max(k), True), 3),
            "year": round(WEIGHTS["year"] * normalize(r["year"], min(y), max(y), False), 3),
            "papers": round(WEIGHTS["papers"] * r["papers_verified"], 3),
        }
        r["score_parts"] = parts
        r["score"] = round(sum(parts.values()), 3)
    return sorted(rows, key=lambda r: r["score"], reverse=True)


def search(slots):
  
    start = time.perf_counter()
    sql, params, where = build_query(slots)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()

    ranked = rank(rows)
    filter_text = " AND ".join(where).replace("?", "{}").format(*params) if where else "none"
    search_ms = round((time.perf_counter() - start) * 1000, 1)
    print("FILTER:", filter_text, "| matches:", len(ranked))
    return ranked[:3], len(ranked), filter_text, search_ms


def best_relaxation(slots):
    
    best = None
    for name in SLOT_LABELS:
        if slots.get(name) is None:
            continue
        trial = dict(slots)
        trial[name] = None
        _, total, _, _ = search(trial)
        if total > 0 and (best is None or total > best[1]):
            best = (name, total)
    return best