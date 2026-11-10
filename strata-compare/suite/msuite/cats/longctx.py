"""Long context beyond needles: two ~95K-token documents (items/longctx/gen.py), three questions each: several needles
at once (partial credit per needle), counting mentions, and tracking a value that changes through the text."""
from __future__ import annotations

import json
import re

from ..common import ITEMS, last_line_answer, parse_int, read_json

DIR = ITEMS / "longctx"
INTRO = "Below is a long document. Read it carefully and answer the question that follows it.\n\n<document>\n"


def doc_block(doc_rel: str) -> str:
    return INTRO + (DIR / doc_rel).read_text(encoding="utf-8") + "\n</document>\n\n"


def load() -> list[dict]:
    out = []
    for q in read_json(DIR / "questions.json"):
        out.append({"id": f"longctx/{q['id']}", "category": "longctx", "doc": q["doc"], "type": q["type"],
                    "question": "Question: " + q["question"], "answer": q["answer"], "long": True})
    return out


def _norm(v) -> str:
    s = str(v).strip().lower()
    s = re.sub(r"\s*mhz$", "", s)
    s = s.replace(",", "").replace("'", "").replace('"', "").replace("’", "")
    return re.sub(r"\s+", " ", s).strip(" .")


def _json_obj(text: str):
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", text or "", re.S))):
        try:
            v = json.loads(m.group(0))
            if isinstance(v, dict):
                return v
        except ValueError:
            continue
    return None


def grade(item: dict, rec: dict) -> dict:
    text = (rec.get("response") or {}).get("content") or ""
    if item["type"] == "needles":
        obj = _json_obj(text)
        if obj is None:
            return {"score": 0.0, "solved": False, "detail": "no JSON object in the answer"}
        right = [k for k, v in item["answer"].items() if k in obj and _norm(obj[k]) == _norm(v)]
        wrong = {k: obj.get(k) for k in item["answer"] if k not in right}
        n = len(item["answer"])
        return {"score": len(right) / n, "solved": len(right) == n,
                "detail": f"{len(right)}/{n} needles" + (f"; wrong: {json.dumps(wrong)[:200]}" if wrong else "")}
    raw = last_line_answer(text)
    got = parse_int(raw)
    ok = got == item["answer"]
    return {"score": 1.0 if ok else 0.0, "solved": ok,
            "detail": f"answered {raw!r}" + ("" if ok else f", expected {item['answer']}")}


# ----------------------------------------------------------------------------------------- independent re-derivation
def _rederive_a(text):
    main = None
    for line in text.splitlines():
        m = re.search(r"main fuel tank held ([\d,]+) L", line)
        if m:
            main = int(m.group(1).replace(",", ""))
        for pat, sign in ((r"drew ([\d,]+) L from the main tank", -1), (r"([\d,]+) L transferred from the main tank", -1),
                          (r"pumped ([\d,]+) L into the main tank", 1)):
            m = re.search(pat, line)
            if m:
                main += sign * int(m.group(1).replace(",", ""))
        m = re.search(r"main tank gauge recalibrated; the corrected reading is ([\d,]+) L", line)
        if m:
            main = int(m.group(1).replace(",", ""))
    count = sum(1 for line in text.splitlines() if re.search(r"\bsnow petrels?\b", line))
    return count, main


def _rederive_b(text):
    t = None
    for m in re.finditer(r"treasury held ([\d,]+) crowns|brought ([\d,]+) crowns into the city treasury|spent ([\d,]+) "
                         r"crowns from the city treasury|took ([\d,]+) crowns from the city treasury|city treasury held "
                         r"exactly ([\d,]+) crowns", text):
        g = [x and int(x.replace(",", "")) for x in m.groups()]
        if g[0] is not None or g[4] is not None:
            t = g[0] if g[0] is not None else g[4]
        elif g[1] is not None:
            t += g[1]
        else:
            t -= g[2] if g[2] is not None else g[3]
    return len(re.findall(r"Marrow Bridge", text)), t


def selftest():
    out = []
    items = {i["id"]: i for i in load()}
    ta = (DIR / "docs/doc_a.txt").read_text(encoding="utf-8")
    tb = (DIR / "docs/doc_b.txt").read_text(encoding="utf-8")
    ca, fa = _rederive_a(ta)
    cb, fb = _rederive_b(tb)
    out.append(("longctx A: count and fuel re-derived from the text = stored answers",
                ca == items["longctx/la_count"]["answer"] and fa == items["longctx/la_track"]["answer"],
                f"count {ca} vs {items['longctx/la_count']['answer']}, fuel {fa} vs {items['longctx/la_track']['answer']}"))
    out.append(("longctx B: count and treasury re-derived from the text = stored answers",
                cb == items["longctx/lb_count"]["answer"] and fb == items["longctx/lb_track"]["answer"],
                f"count {cb} vs {items['longctx/lb_count']['answer']}, treasury {fb} vs {items['longctx/lb_track']['answer']}"))
    for key, text in (("la", ta), ("lb", tb)):
        nd = items[f"longctx/{key}_needles"]["answer"]
        missing = [v for v in nd.values() if v.replace("4312", "4,312") not in text and v not in text]
        out.append((f"longctx {key}: every needle value occurs in the document", not missing, f"missing {missing}"))
    for it in items.values():
        if it["type"] == "needles":
            good = "```json\n" + json.dumps(it["answer"]) + "\n```"
            half = dict(it["answer"])
            k0 = next(iter(half))
            half[k0] = "wrong"
            g, b = grade(it, {"response": {"content": good}}), grade(it, {"response": {"content": json.dumps(half)}})
            ok = g["score"] == 1.0 and abs(b["score"] - 0.8) < 1e-9
        else:
            g = grade(it, {"response": {"content": f"...\nANSWER: {it['answer']}"}})
            b = grade(it, {"response": {"content": f"ANSWER: {it['answer'] - 1}"}})
            ok = g["solved"] and not b["solved"]
        out.append((f"{it['id']} grader", ok, f"{g['detail']} | {b['detail']}"))
    return out
