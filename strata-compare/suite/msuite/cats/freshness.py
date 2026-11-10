"""Knowledge freshness: recorded separately, never scored and never in the totals."""
from __future__ import annotations

import re

from ..common import ITEMS, read_json

DIR = ITEMS / "freshness"


# moved into the scored research category (with web search) on 2026-10-12: kept here only to grade older answers
RETIRED = {"f01_best_gpu", "f02_best_model_for_my_pc"}


def load() -> list[dict]:
    hw = (DIR / "hardware.txt").read_text(encoding="utf-8").strip()
    data = read_json(DIR / "items.json")
    return [{"id": f"freshness/{i['id']}", "category": "freshness", "prompt": i["prompt"].replace("{hardware}", hw),
             "retired": i["id"] in RETIRED} for i in data["items"]]


def grade(item: dict, rec: dict) -> dict:
    text = (rec.get("response") or {}).get("content") or ""
    detail = text.strip().splitlines()[-1][:200] if text.strip() else "(empty)"
    if item["id"].endswith("training_cutoff"):
        m = re.findall(r"CUTOFF:\s*\**\s*(\d{4}-\d{2})", text)
        detail = f"stated cutoff {m[-1]}" if m else "no CUTOFF line"
    return {"score": None, "solved": None, "detail": detail}


def selftest():
    it = [i for i in load() if i["id"].endswith("training_cutoff")][0]
    g = grade(it, {"response": {"content": "My knowledge...\nCUTOFF: 2025-08"}})
    hw = [i for i in load() if "{hardware}" in i["prompt"]]
    return [("freshness: cutoff parsed, hardware filled in", g["detail"] == "stated cutoff 2025-08" and not hw,
             g["detail"])]
