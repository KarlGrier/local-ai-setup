"""Math: 20 competition-style problems with integer answers (answers recomputed by items/math/verify.py)."""
from __future__ import annotations

import importlib.util

from ..common import ITEMS, last_line_answer, parse_int, read_json

DIR = ITEMS / "math"
FORMAT = ("\n\nGive the final answer as the last line of your reply, in exactly this form:\nANSWER: <integer>")


def load() -> list[dict]:
    return [{"id": f"math/{p['id']}", "category": "math", "prompt": p["prompt"] + FORMAT, "answer": p["answer"]}
            for p in read_json(DIR / "problems.json")]


def grade(item: dict, rec: dict) -> dict:
    text = (rec.get("response") or {}).get("content") or ""
    raw = last_line_answer(text)
    got = parse_int(raw)
    ok = got is not None and got == item["answer"]
    return {"score": 1.0 if ok else 0.0, "solved": ok,
            "detail": f"answered {raw!r}" + ("" if ok else f", expected {item['answer']}")}


def selftest():
    out = []
    spec = importlib.util.spec_from_file_location("math_verify", DIR / "verify.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    for it in load():
        key = it["id"].split("/")[1]
        out.append((f"{it['id']} stored answer = brute-force answer", v.ALL[key]() == it["answer"],
                    f"{it['answer']} vs {v.ALL[key]()}"))
        good = grade(it, {"response": {"content": f"Reasoning...\n\n**ANSWER: {it['answer']:,}**"}})
        bad = grade(it, {"response": {"content": f"ANSWER: {it['answer'] + 1}"}})
        miss = grade(it, {"response": {"content": f"The answer is {it['answer']}."}})
        out.append((f"{it['id']} grader: right / off-by-one / no ANSWER line",
                    good["solved"] and not bad["solved"] and not miss["solved"], f"{good['detail']} | {bad['detail']}"))
    return out
