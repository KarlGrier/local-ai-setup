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

Item 7d (staged 11-03): a profile with "_select" (paid-route.json; 7d / 7dx) asks its paid and fallback sources only
for the searches search_route.select_step() picks - the run's follow-up searches (see search_route.py). What it needs:
* the agent of the search: LDR deep mode's ContextVar local_deep_research.deep.current_agent, read from sys.modules
  (never imported here; the hook runs in the web_search tool's thread, where it holds the same label the evidence
  store writes); a caller can pass agent= instead;
* the run's state: ~/.config/deep-research/paid-route-state.json (PAID_ROUTE_STATE; file-locked), one entry per run id
  + the run file's "written" stamp (a rerun under the same run id starts afresh), dropped 7 days after its last search.
  Not keyed by month (the 10-31 month-change bug of paid-runs.json cannot happen here).
The route log line then carries "select": {n, agent, picked, why, follow_at}. Profiles without "_select" (fallback,
types, 7a / 7b / 7c) behave exactly as before.
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import time
from pathlib import Path

import exa_fallback
import paid_budget
import paid_cache
import s2_search
import search_route
import tavily_fallback

LOG_FILE = Path(os.environ.get("PAID_ROUTE_LOG", "/home/USER/ai/deep-research/logs/paid-route.jsonl"))
STATE_FILE = Path(os.environ.get("PAID_ROUTE_STATE",
                                 str(Path.home() / ".config" / "deep-research" / "paid-route-state.json")))
STATE_KEEP_S = 7 * 86400
PAID = {"exa": exa_fallback, "tavily": tavily_fallback}
FREE = {"s2": s2_search}


def ldr_agent() -> str | None:
    """The deep-mode agent running this search ("lead", "sub3", ...), or None outside LDR's deep mode."""
    mod = sys.modules.get("local_deep_research.deep")
    cv = getattr(mod, "current_agent", None) if mod is not None else None
    if cv is None:
        return None
    try:
        return str(cv.get())
    except Exception:  # noqa: BLE001 - no label: the rule's no-agent branch
        return None


def run_key(client: str, run_now: dict) -> str:
    """The selection state's key: the run id + the run file's stamp ("" when there is no run id)."""
    run = paid_budget.run_id(client)
    if not run:
        return ""
    stamp = run_now.get("written") or run_now.get("pid_start") or ""
    return f"{run}@{stamp}" if stamp else run


def select_update(key: str, agent, sel: dict, now: float | None = None) -> tuple[bool, dict]:
    """One search of run `key` through the 7d rule under the state file's lock: (picked, log record)."""
    now = time.time() if now is None else float(now)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE.with_suffix(".lock"), "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            d = json.loads(STATE_FILE.read_text())
            if not isinstance(d, dict) or not isinstance(d.get("runs"), dict):
                raise ValueError
        except (OSError, ValueError):
            d = {"runs": {}}
        runs = {k: v for k, v in d["runs"].items()
                if isinstance(v, dict) and now - float(v.get("t", 0)) <= STATE_KEEP_S}
        st = runs.get(key) or search_route.new_state(now)
        picked, why = search_route.select_step(st, agent, sel, now)
        st["t"] = now
        runs[key] = st
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"runs": runs}))
        os.replace(tmp, STATE_FILE)
    return picked, {"n": st["n"], "agent": search_route.agent_name(agent), "picked": picked, "why": why,
                    "follow_at": st.get("follow_at")}


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


def _search(query: str, searxng_results, client: str, max_results: int, reason: str, agent=None) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    cfg, cfg_err = search_route.load_config()
    run_now = paid_budget._run_now() if client == "ldr" else {}
    profile, psrc = search_route.pick_profile(cfg, run_now)
    dec = search_route.decide(q, cfg, profile)
    sel = search_route.select_config(cfg, profile)
    sel_rec = None
    if sel is not None:                     # 7d: only the run's follow-up searches ask the paid / fallback sources
        want = bool(dec["paid"] or dec["fallback"])
        key = run_key(client, run_now)
        if not key:
            picked, sel_rec = False, {"picked": False, "why": "no run id"}
        else:
            if agent is None and client == "ldr":
                agent = ldr_agent()
            try:
                picked, sel_rec = select_update(key, agent, sel if want else {**sel, "per_sub": 0, "per_lead": 0,
                                                                                "skip_unknown": 10 ** 9})
            except OSError as e:            # no state, no paid search (nothing is spent on a guess)
                picked, sel_rec = False, {"picked": False, "why": f"state file: {type(e).__name__}"}
            if not want:
                sel_rec["why"] = "no paid source for this tag"
        if not picked:
            dec = {**dec, "paid": [], "fallback": []}
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
        why_not = (getattr(FREE[src], "last_status", lambda: "")() or "failed") if got is None else "sent"
        actions.append({"source": src, "step": "free", "outcome": why_not,      # 11-03: e.g. "error: HTTP 429"
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
        if sel_rec is not None:
            rec["select"] = sel_rec
        if cfg_err:
            rec["config_error"] = cfg_err
        _log(rec)
    return extra


def search(query: str, searxng_results=None, client: str = "ldr", max_results: int = 10, reason: str = "",
           agent=None) -> list[dict]:
    """Results to add beside SearXNG's (see the module text). agent: the deep-mode agent label (7d), else read from
    LDR's ContextVar. Never raises."""
    try:
        return _search(query, searxng_results, client, max_results, reason, agent)
    except Exception as e:  # noqa: BLE001 - SearXNG's results stand
        _log({"client": client, "query": (query or "")[:300], "error": type(e).__name__})
        return []
