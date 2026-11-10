"""Dollar estimate for a Claude run, from the last local run's token counts and the published prices.

Assumptions (printed with every estimate): the Claude tokenizer counts about as many tokens as the local model's;
Claude writes as many output tokens (thinking + answer) as the local model did; single-turn items cost the Batch
API's half price; each long-context document is written to the cache once (1.25x) and read by the other questions
(0.1x); agentic turns re-read the conversation from the cache (0.1x) and write only the new part (1.25x).  The
"high" figure doubles every output token (Claude at its highest effort can think longer than the local model).
"""
from __future__ import annotations

import statistics

from .common import RESULTS, read_json
from .backend_anthropic import BATCH, CACHE_READ, CACHE_WRITE_5M, price_of


def _base_label(explicit=None):
    if explicit:
        return explicit
    best = None
    for m in RESULTS.glob("*/meta.json"):
        try:
            meta = read_json(m)
        except ValueError:
            continue
        if (meta.get("backend") or {}).get("kind") != "openai" or meta.get("status") != "complete":
            continue
        key = meta.get("finished") or ""
        if best is None or key > best[0]:
            best = (key, meta["label"])
    return best[1] if best else None


def _tokens_by_item(label):
    out = {}
    for p in (RESULTS / label / "answers").rglob("*.json"):
        r = read_json(p)
        e = out.setdefault(r["item"], {"prompt": [], "completion": [], "steps": []})
        t = r.get("tokens") or {}
        if t.get("prompt") is not None:
            e["prompt"].append(t["prompt"])
        if t.get("completion") is not None:
            e["completion"].append(t["completion"])
        if r.get("steps"):
            e["steps"].append([((s.get("tokens") or {}).get("prompt") or 0, (s.get("tokens") or {}).get("completion") or 0)
                               for s in r["steps"]])
    return out


def estimate(model: str, items: list[dict], runs: int, log=print, base_label=None) -> dict:
    pin, pout = (x / 1e6 for x in price_of(model))
    base = _base_label(base_label)
    tok = _tokens_by_item(base) if base else {}
    per_cat_comp, per_cat_prompt = {}, {}
    for it in items:
        e = tok.get(it["id"])
        if e and e["completion"]:
            per_cat_comp.setdefault(it["category"], []).append(statistics.mean(e["completion"]))
            per_cat_prompt.setdefault(it["category"], []).append(statistics.mean(e["prompt"]) if e["prompt"] else 0)
    default_comp = {"coding": 8000, "math": 10000, "instruct": 3000, "tools": 1500, "honesty": 2500, "freshness": 2000,
                    "visual": 15000, "longctx": 6000, "agentic": 3000, "research": 20000}
    cats, seen_docs = {}, set()
    for it in items:
        e = tok.get(it["id"])
        cat = it["category"]
        comp = statistics.mean(e["completion"]) if e and e["completion"] else (
            statistics.median(per_cat_comp[cat]) if per_cat_comp.get(cat) else default_comp[cat])
        prompt = statistics.mean(e["prompt"]) if e and e["prompt"] else (
            statistics.median(per_cat_prompt[cat]) if per_cat_prompt.get(cat) else len(it.get("prompt", "")) / 3.5)
        c_lo = c_hi = 0.0
        for r in range(runs):
            if it.get("agentic") or it.get("research"):
                steps = e["steps"][0] if e and e["steps"] else [(4000 + 6000 * k, comp / 6) for k in range(6)]
                prev = 0
                for p_k, c_k in steps:
                    base_in = (max(0, p_k - prev) * CACHE_WRITE_5M + prev * CACHE_READ) * pin
                    c_lo += base_in + c_k * pout
                    c_hi += base_in + 2 * c_k * pout
                    prev = p_k + c_k
            elif it.get("long"):
                key = (it["doc"], r)
                mult = CACHE_READ if key in seen_docs else CACHE_WRITE_5M
                seen_docs.add(key)
                c_lo += prompt * mult * pin + comp * pout
                c_hi += prompt * mult * pin + 2 * comp * pout
            else:
                c_lo += (prompt * pin + comp * pout) * BATCH
                c_hi += (prompt * pin + 2 * comp * pout) * BATCH
        a = cats.setdefault(cat, [0.0, 0.0])
        a[0] += c_lo
        a[1] += c_hi
    point = sum(v[0] for v in cats.values())
    high = sum(v[1] for v in cats.values())
    log(f"cost estimate for {model} ({runs} run(s) per item), from local run '{base or 'none: defaults'}':")
    for c, (lo, hi) in cats.items():
        log(f"   {c:10s} ${lo:7.2f}   (if Claude writes 2x the tokens: ${hi:7.2f})")
    log(f"   {'total':10s} ${point:7.2f}   (2x output: ${high:.2f})")
    return {"point": round(point, 2), "high_2x_output": round(high, 2), "base_label": base,
            "by_category": {c: round(v[0], 2) for c, v in cats.items()}, "prices_per_mtok": price_of(model)}
