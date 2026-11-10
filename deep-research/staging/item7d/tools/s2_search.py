"""s2_search.py - Semantic Scholar paper search for the item 7 router's "academic" tag (staged 10-29; installed 10-31).

Free: the official Graph API. The unauthenticated pool is shared and rate-limited, so one request at a time and at least
MIN_INTERVAL_S apart per process. Results point at the paper's DOI or arXiv page when it has one (pages the deep
strategy can read), else its Semantic Scholar page; the content is the abstract. Standard library only; never raises
(None when the request failed).

11-03 (staged with item 7d; Karl 11-02 - 7a was "NOT TESTED": 616 of 650 calls got HTTP 429 without a key, and this
module swallowed the error):
* An API key, when Karl has saved one in ~/.config/deep-research/semanticscholar.key (one line): read from the file only
  when a request is sent, sent as the x-api-key header, never printed, logged or put in the environment. Without the
  file the request goes out unauthenticated, as before.
* One line per call in ~/ai/deep-research/logs/s2-search.jsonl (S2_LOG): time (with UTC offset), UTC month, HTTP status
  or error type, result count, whether a key was used (true/false), seconds - never the key or the query text.
* last_status(): "sent", "error: HTTP 429", ... for this thread's last search() (the route log can show it).
Nothing in 7d uses S2 (routes 7d / 7dx have no free source); a later 7a rerun or a 7d-with-S2 arm needs Karl's OK.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = os.environ.get("S2_URL", "https://api.semanticscholar.org/graph/v1/paper/search")   # tests: a local mock
FIELDS = "title,url,abstract,year,venue,externalIds"
MIN_INTERVAL_S = float(os.environ.get("S2_MIN_INTERVAL_S", "1.1"))
TIMEOUT_S = 15.0
KEY_FILE = Path.home() / ".config" / "deep-research" / "semanticscholar.key"
LOG_FILE = Path(os.environ.get("S2_LOG", "/home/USER/ai/deep-research/logs/s2-search.jsonl"))
_lock = threading.Lock()
_last = [0.0]
_status = threading.local()


def available() -> bool:
    return True


def has_key() -> bool:
    """The key file is there (not read here)."""
    try:
        return KEY_FILE.is_file() and KEY_FILE.stat().st_size > 0
    except OSError:
        return False


def last_status() -> str:
    return getattr(_status, "s", "")


def _log(rec: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "month": time.strftime("%Y-%m", time.gmtime()),
                                **rec}) + "\n")
    except OSError:
        pass


def search(query: str, max_results: int = 10) -> list[dict] | None:
    query = (query or "").strip()
    _status.s = ""
    if not query:
        return None
    qs = urllib.parse.urlencode({"query": query[:300], "limit": max(1, min(20, int(max_results))), "fields": FIELDS})
    keyed = has_key()
    t0 = time.monotonic()
    try:
        with _lock:
            wait = _last[0] + MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.monotonic()
            headers = {"User-Agent": "deep-research-route"}
            if keyed:
                headers["x-api-key"] = KEY_FILE.read_text().strip()
            req = urllib.request.Request(f"{URL}?{qs}", headers=headers)
            del headers
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=TIMEOUT_S) as r:
                code = r.status
                data = json.loads(r.read(5_000_000))
        out = []
        for x in data.get("data") or []:
            if not isinstance(x, dict):
                continue
            ids = x.get("externalIds") if isinstance(x.get("externalIds"), dict) else {}
            url = (f"https://doi.org/{ids['DOI']}" if ids.get("DOI") else
                   f"https://arxiv.org/abs/{ids['ArXiv']}" if ids.get("ArXiv") else x.get("url"))
            if not url:
                continue
            venue = " ".join(str(v) for v in (x.get("venue"), x.get("year")) if v)
            out.append({"title": str(x.get("title") or ""), "url": str(url),
                        "content": (str(x.get("abstract") or "") or venue)[:2000], "score": None,
                        "published_date": str(x["year"]) if x.get("year") else None})
        _status.s = "sent"
        _log({"status": code, "results": len(out), "key": keyed, "s": round(time.monotonic() - t0, 2)})
        return out
    except urllib.error.HTTPError as e:
        _status.s = f"error: HTTP {e.code}"
        _log({"status": e.code, "error": f"HTTP {e.code}", "key": keyed, "s": round(time.monotonic() - t0, 2)})
    except Exception as e:  # noqa: BLE001 - SearXNG's results stand
        _status.s = f"error: {type(e).__name__}"
        _log({"error": type(e).__name__, "key": keyed, "s": round(time.monotonic() - t0, 2)})
    return None
