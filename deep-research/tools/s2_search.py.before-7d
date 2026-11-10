"""s2_search.py - Semantic Scholar paper search for the item 7 router's "academic" tag (staged 10-29; not installed).

Free: the official Graph API without a key (no key file, nothing to count). The unauthenticated pool is shared and
rate-limited, so one request at a time and at least MIN_INTERVAL_S apart per process. Results point at the paper's DOI
or arXiv page when it has one (pages the deep strategy can read), else its Semantic Scholar page; the content is the
abstract. Standard library only; never raises (None when the request failed).
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request

URL = os.environ.get("S2_URL", "https://api.semanticscholar.org/graph/v1/paper/search")   # tests: a local mock
FIELDS = "title,url,abstract,year,venue,externalIds"
MIN_INTERVAL_S = float(os.environ.get("S2_MIN_INTERVAL_S", "1.1"))
TIMEOUT_S = 15.0
_lock = threading.Lock()
_last = [0.0]


def available() -> bool:
    return True


def search(query: str, max_results: int = 10) -> list[dict] | None:
    query = (query or "").strip()
    if not query:
        return None
    qs = urllib.parse.urlencode({"query": query[:300], "limit": max(1, min(20, int(max_results))), "fields": FIELDS})
    try:
        with _lock:
            wait = _last[0] + MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.monotonic()
            req = urllib.request.Request(f"{URL}?{qs}", headers={"User-Agent": "deep-research-route"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=TIMEOUT_S) as r:
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
        return out
    except Exception:  # noqa: BLE001 - SearXNG's results stand
        return None
