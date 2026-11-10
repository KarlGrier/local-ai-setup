"""tavily_fallback.py - a Tavily search when SearXNG fails or returns too few results (2026-10-19, the user's request).

Used by LDR (patch 0005, only when LDR was started with LDR_SEARCH_FALLBACK=1, which the Jan research runner does and
the measurement queue does not) and by the Strata chat page's web_search (serve/websearch.py). Standard library only,
so every Python here can import it.

* Dormant until the key file exists: ~/.config/deep-research/tavily.key (one line). The key is read only when a
  request is sent, and is never printed, logged or put in the environment.
* A monthly counter shared by every client (~/.config/deep-research/tavily-usage.json, file-locked): at most
  TAVILY_MONTHLY_CAP searches per calendar month (UTC; default 950 of Tavily's 1,000 free credits; a basic search is
  1 credit). A request that fails still counts. Over the cap: no request, the caller keeps SearXNG's results.
* Every use is one line in ~/ai/deep-research/logs/tavily-fallback.jsonl (time, client, reason, query, result count,
  month count; errors by type and HTTP status only).
"""
from __future__ import annotations

import fcntl
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

KEY_FILE = Path.home() / ".config" / "deep-research" / "tavily.key"
USAGE_FILE = Path.home() / ".config" / "deep-research" / "tavily-usage.json"
LOG_FILE = Path("/home/USER/ai/deep-research/logs/tavily-fallback.jsonl")
URL = os.environ.get("TAVILY_URL", "https://api.tavily.com/search")   # tests point this at a local mock
CAP = int(os.environ.get("TAVILY_MONTHLY_CAP", "850"))   # Karl 10-27: about 850 a month (paid_policy.py: the rule)
TIMEOUT_S = 20.0


def available() -> bool:
    """The key file is there (not read here)."""
    try:
        return KEY_FILE.is_file() and KEY_FILE.stat().st_size > 0
    except OSError:
        return False


def _month() -> str:
    return time.strftime("%Y-%m", time.gmtime())


def usage() -> dict:
    try:
        d = json.loads(USAGE_FILE.read_text())
    except (OSError, ValueError):
        d = {}
    if d.get("month") != _month():
        d = {"month": _month(), "count": 0, "runs": {}}
    d.setdefault("runs", {})
    d["cap"] = CAP
    return d


def _reserve(client: str = "?") -> tuple[bool, int, str]:
    """Count one search (file-locked) if Karl's rule allows it for this caller (paid_policy.py: 10 % / 25 % of the
    month kept, per-run caps); (ok, month count, why not)."""
    import paid_policy
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock = USAGE_FILE.with_suffix(".lock")
    with open(lock, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        d = usage()
        ok, why = paid_policy.check(d["count"], 1, CAP, client, d["runs"])
        if not ok:
            return False, d["count"], why
        d["count"] += 1
        paid_policy.count_run(d, client)
        tmp = USAGE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"month": d["month"], "count": d["count"], "runs": d["runs"]}))
        os.replace(tmp, USAGE_FILE)
        return True, d["count"], ""


def _log(rec: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def search(query: str, max_results: int = 10, client: str = "?", reason: str = "") -> list[dict] | None:
    """Tavily results as [{"title", "url", "content", "score", "published_date"}], or None (no key, over the cap,
    or the request failed). Never raises."""
    query = (query or "").strip()
    if not query or not available():
        return None
    ok, n, why = _reserve(client)
    rec = {"client": client, "reason": reason, "query": query[:300], "month_count": n}
    if not ok:
        _log({**rec, "skipped": why})
        return None
    try:
        key = KEY_FILE.read_text().strip()
        body = json.dumps({"query": query, "max_results": max(1, min(20, int(max_results))),
                           "search_depth": "basic", "include_answer": False}).encode()
        req = urllib.request.Request(URL, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}",
                                              "User-Agent": "deep-research-fallback"})
        del key
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=TIMEOUT_S) as r:
            data = json.loads(r.read(5_000_000))
        out = [{"title": str(x.get("title") or ""), "url": str(x.get("url") or ""),
                "content": str(x.get("content") or ""), "score": x.get("score"),
                "published_date": x.get("published_date")}
               for x in (data.get("results") or []) if isinstance(x, dict) and x.get("url")]
        _log({**rec, "results": len(out)})
        return out
    except urllib.error.HTTPError as e:
        _log({**rec, "error": f"HTTP {e.code}"})
    except Exception as e:  # noqa: BLE001 - the caller keeps SearXNG's results
        _log({**rec, "error": type(e).__name__})
    return None
