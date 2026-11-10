"""Tool calls: 10 prompts with real tool definitions.  Right tool, schema-valid arguments that match the request,
and no call when no tool fits.  Only the first response is judged (no tool results are sent back)."""
from __future__ import annotations

import importlib.util
import json

import jsonschema

from ..common import ITEMS

DIR = ITEMS / "tools"


def _mod():
    spec = importlib.util.spec_from_file_location("tools_items", DIR / "items.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load() -> list[dict]:
    return [{"id": f"tools/{it['id']}", "category": "tools", "prompt": it["prompt"], "tools": it["tools"],
             "expect": it["expect"], "good": it["good"], "bad": it["bad"]} for it in _mod().ITEMS]


def _norm(v):
    return v.strip().lower() if isinstance(v, str) else v


def _match(spec: dict, v) -> bool:
    (kind, want), = spec.items()
    if kind == "eq":
        return v == want
    if kind == "ci":
        return isinstance(v, str) and _norm(v) == _norm(want)
    if kind == "contains":
        return isinstance(v, str) and want.lower() in v.lower()
    if kind == "startswith":
        return isinstance(v, str) and v.startswith(want)
    if kind == "in":
        return any((_norm(v) == _norm(w)) for w in want)
    if kind == "num":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v - want) < 1e-9
    if kind == "set":
        return isinstance(v, list) and sorted(_norm(x) for x in v) == sorted(_norm(x) for x in want)
    if kind == "obj":
        return isinstance(v, dict) and all(k in v and _match(s, v[k]) for k, s in want.items())
    raise ValueError(f"unknown matcher {kind}")


def grade(item: dict, rec: dict) -> dict:
    resp = rec.get("response") or {}
    calls = resp.get("tool_calls") or []
    exp = item["expect"]
    if exp is None:
        ok = not calls and bool((resp.get("content") or "").strip())
        return {"score": 1.0 if ok else 0.0, "solved": ok,
                "detail": "no call, answered in text" if ok else
                (f"called {[c['name'] for c in calls]} although no tool fits" if calls else "no call but empty answer")}
    if len(calls) != len(exp):
        return {"score": 0.0, "solved": False,
                "detail": f"{len(calls)} calls ({[c['name'] for c in calls]}), expected {len(exp)} ({[e['name'] for e in exp]})"}
    schemas = {t["name"]: t["parameters"] for t in item["tools"]}
    remaining = list(calls)
    for e in exp:
        found = None
        problems = []
        for c in remaining:
            if c["name"] != e["name"]:
                problems.append(f"wrong tool {c['name']}")
                continue
            try:
                args = json.loads(c["arguments"]) if isinstance(c["arguments"], str) else c["arguments"]
            except ValueError:
                problems.append("arguments are not valid JSON")
                continue
            try:
                jsonschema.validate(args, schemas[c["name"]])
            except jsonschema.ValidationError as err:
                problems.append(f"schema: {err.message[:100]}")
                continue
            bad = [k for k, s in e["args"].items() if k not in args or not _match(s, args[k])]
            if bad:
                problems.append(f"wrong values for {bad}: {json.dumps({k: args.get(k) for k in bad})[:160]}")
                continue
            found = c
            break
        if found is None:
            return {"score": 0.0, "solved": False, "detail": "; ".join(problems) or f"no {e['name']} call"}
        remaining.remove(found)
    return {"score": 1.0, "solved": True, "detail": "right tool, valid matching arguments"}


def selftest():
    out = []
    for it in load():
        g = grade(it, {"response": {"content": "Here." if it["expect"] is None else "", "tool_calls": it["good"]}})
        b = grade(it, {"response": {"content": "", "tool_calls": it["bad"]}})
        out.append((f"{it['id']} accepts the right call, rejects the wrong one", g["solved"] and not b["solved"],
                    f"good: {g['detail']} | bad: {b['detail']}"))
    return out
