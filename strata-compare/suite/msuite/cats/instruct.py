"""Instruction following: 20 prompts with script-checkable rules (items/instruct/items.py)."""
from __future__ import annotations

import importlib.util

from ..common import ITEMS

DIR = ITEMS / "instruct"


def _mod():
    spec = importlib.util.spec_from_file_location("instruct_items", DIR / "items.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load() -> list[dict]:
    return [{"id": f"instruct/{it['id']}", "category": "instruct", "prompt": it["prompt"], "_check": it["check"],
             "good": it["good"], "bad": it["bad"]} for it in _mod().ITEMS]


def grade(item: dict, rec: dict) -> dict:
    text = (rec.get("response") or {}).get("content") or ""
    try:
        ok, detail = item["_check"](text)
    except Exception as e:                                  # a checker must never crash the run
        ok, detail = False, f"checker error: {type(e).__name__}: {e}"
    return {"score": 1.0 if ok else 0.0, "solved": bool(ok), "detail": detail}


def selftest():
    out = []
    for it in load():
        g = grade(it, {"response": {"content": it["good"]}})
        b = grade(it, {"response": {"content": it["bad"]}})
        out.append((f"{it['id']} accepts known-good, rejects known-bad", g["solved"] and not b["solved"],
                    f"good: {g['detail']} | bad: {b['detail']}"))
    return out
