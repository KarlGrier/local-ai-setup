"""paid_search.py - the one entry point for searches beside SearXNG (phase 4 item 7, staged 10-29; not installed).

    extra = paid_search.search(query, searxng_results, client="ldr")

route -> cache -> budget -> provider:
1. route (search_route.py + paid-route.json): tag the query, pick the profile (off by default = "fallback", today's
   patch 0005 behaviour), get the free / paid / fallback sources for the tag;
2. free sources (Semantic Scholar, s2_search.py) are asked directly - nothing to count or cache;
3. each paid source: a cache lookup first (paid_cache.py; a hit spends no credit and never reaches the budget, so it
   does not count against the run cap); on a miss the provider module (exa_fallback / tavily_fallback), which applies
   paid_budget's caps (run caps 30 / 100, the 25 % and 10 % month thresholds) inside its locked counter; an answer the
   provider actually sent is stored in the cache (refusals and failures never are);
4. one line per decision in ~/ai/deep-research/logs/paid-route.jsonl: tag and why, profile and where it came from,
   SearXNG's count, every source asked with its outcome (sent / cache hit / refused: ... / error: ... / off), and for a
   hit the credit it saved. No key, header or result text is logged.

Returns only results new to SearXNG's list (by URL), each {"title", "url", "content", "engine", "published_date"};
[] when nothing was added. Never raises. Standard library only (import path: the tools folder).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import exa_fallback
import paid_budget
import paid_cache
import s2_search
import search_route
import tavily_fallback

LOG_FILE = Path(os.environ.get("PAID_ROUTE_LOG", "/home/USER/ai/deep-research/logs/paid-route.jsonl"))
PAID = {"exa": exa_fallback, "tavily": tavily_fallback}
FREE = {"s2": s2_search}


def request_params(provider: str, max_results: int) -> dict:
    """The request parameters that change a provider's answer (part of the cache key)."""
    if provider == "exa":
        return {"type": exa_fallback.SEARCH_TYPE, "num": max(1, min(10, int(max_results))), "contents": "highlights"}
    return {"depth": "basic", "num": max(1, min(20, int(max_results))), "answer": False}


def est_cost(provider: str) -> float:
    """What one request costs in the provider's counter unit (Exa: dollars, Tavily: credits)."""
    if provider == "exa":
        return exa_fallback.PRICE_USD.get(exa_fallback.SEARCH_TYPE, 0.015)
    return 1.0


def _flag(name: str, run_now: dict, default: bool) -> bool:
    env = os.environ.get(name, "").strip()
    if env in ("0", "1"):
        return env == "1"
    if isinstance(run_now.get("cache"), bool):
        return run_now["cache"]
    return default


def cache_for(cfg: dict, run_now: dict | None = None) -> paid_cache.PaidCache | None:
    """The cache, or None when it is off (PAID_SEARCH_CACHE=0/1, else the run file's "cache", else the config)."""
    if not _flag("PAID_SEARCH_CACHE", run_now or {}, bool(cfg["cache"].get("enabled"))):
        return None
    folder = os.environ.get("PAID_SEARCH_CACHE_DIR") or cfg["cache"].get("dir") or "~/.cache/deep-research/paid-search"
    return paid_cache.PaidCache(folder, int(float(cfg["cache"].get("max_mb", 64)) * (1 << 20)))


def _norm_url(u) -> str:
    return str(u or "").strip().split("#", 1)[0].rstrip("/")


def _log(rec: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "month": time.strftime("%Y-%m", time.gmtime()),
                                **rec}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def paid_call(provider: str, query: str, tag: str, max_results: int, client: str, reason: str, cfg: dict,
              cache: paid_cache.PaidCache | None) -> tuple[list[dict] | None, dict]:
    """cache -> budget -> provider for one paid source: (results or None, the logged action)."""
    mod = PAID[provider]
    act: dict = {"source": provider}
    if not mod.available():
        act.update(outcome="off", n=0)                     # no key file: dormant, as today (no cache hits either)
        return None, act
    params = request_params(provider, max_results)
    if cache is not None:
        got, st = cache.lookup(provider, query, params)
        if got is not None:
            act.update(outcome="cache hit", n=len(got), saved=est_cost(provider))
            return got, act
        act["cache"] = st
    got = mod.search(query, max_results=max_results, client=client, reason=reason)
    status = mod.last_status() if hasattr(mod, "last_status") else ("sent" if got is not None else "")
    if got is None:
        act.update(outcome=status or "none", n=0)
        return None, act
    if cache is not None and status == "sent":
        act["stored"] = cache.store(provider, query, params, got,
                                    search_route.ttl_seconds(cfg, tag, empty=not got), tag=tag)
    act.update(outcome="sent", n=len(got))
    return got, act


def _search(query: str, searxng_results, client: str, max_results: int, reason: str) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    cfg, cfg_err = search_route.load_config()
    run_now = paid_budget._run_now() if client == "ldr" else {}
    profile, psrc = search_route.pick_profile(cfg, run_now)
    dec = search_route.decide(q, cfg, profile)
    cache = cache_for(cfg, run_now)
    base = [r for r in (searxng_results or []) if isinstance(r, dict)]
    seen = {_norm_url(r.get("url") or r.get("link")) for r in base} - {""}
    n_sx = len(base)
    extra: list[dict] = []
    actions: list[dict] = []

    def add(got, engine: str) -> int:
        new = 0
        for x in got or []:
            u = _norm_url(x.get("url")) if isinstance(x, dict) else ""
            if not u or u in seen:
                continue
            seen.add(u)
            extra.append({"title": str(x.get("title") or ""), "url": str(x["url"]), "content": str(x.get("content") or ""),
                          "engine": engine, "published_date": x.get("published_date")})
            new += 1
        return new

    for src in dec["free"]:
        got = FREE[src].search(q, max_results=max_results)
        actions.append({"source": src, "step": "free", "outcome": "sent" if got is not None else "failed",
                        "n": len(got or []), "new": add(got, src)})
    asked = set()
    for src in dec["paid"]:
        asked.add(src)
        got, act = paid_call(src, q, dec["tag"], max_results, client,
                             reason or f"route {profile}/{dec['tag']}: every search", cfg, cache)
        actions.append({**act, "step": "paid", "new": add(got, src)})
        if got:
            break
    have = n_sx + len(extra)
    if dec["fallback"] and have < dec["fallback_below"]:
        why = reason or (f"searxng returned {n_sx}" if profile == "fallback"
                         else f"route {profile}/{dec['tag']}: {have} results < {dec['fallback_below']}")
        for src in dec["fallback"]:
            if src in asked:
                continue
            asked.add(src)
            got, act = paid_call(src, q, dec["tag"], max_results, client, why, cfg, cache)
            actions.append({**act, "step": "fallback", "new": add(got, src)})
            if got:
                break
            why = f"{why}; {src}: {'none' if got == [] else 'unavailable'}"
    if actions or profile != "fallback" or cfg_err:
        rec = {"client": client, "kind": paid_budget.kind(client), "run": paid_budget.run_id(client) or None,
               "profile": profile, "profile_from": psrc, "tag": dec["tag"], "why": dec["why"], "query": q[:300],
               "searxng": n_sx, "actions": actions, "added": len(extra), "cache": cache is not None}
        if cfg_err:
            rec["config_error"] = cfg_err
        _log(rec)
    return extra


def search(query: str, searxng_results=None, client: str = "ldr", max_results: int = 10, reason: str = "") -> list[dict]:
    """Results to add beside SearXNG's (see the module text). Never raises."""
    try:
        return _search(query, searxng_results, client, max_results, reason)
    except Exception as e:  # noqa: BLE001 - SearXNG's results stand
        _log({"client": client, "query": (query or "")[:300], "error": type(e).__name__})
        return []
