"""paid_cache.py - a disk cache of paid search results across runs (phase 4 item 7, staged 10-29; not installed).

* Key: sha256 of (provider, normalised query, the request parameters that change the answer). One JSON file per entry
  in the cache folder (default ~/.cache/deep-research/paid-search, outside every run folder; created on the first
  store, never on a lookup).
* An entry holds the provider, the normalised query, the parameters, the tag, when it was stored and when it expires,
  and the results reduced to title / url / content / score / published_date - never a key, header or caller.
* TTL per query tag (search_route's ttl_hours: news short); expired entries are removed when looked up or pruned.
* Size cap (bytes): after a store that takes the folder over the cap, expired entries go first, then the least recently
  used (file mtime, refreshed on every hit) until it is under 90 % of the cap. File-locked; writes are atomic.
* A hit spends no credit and never reaches paid_budget, so it does not count against a run's cap.
Standard library only.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from search_route import normalise

VERSION = 1
RESULT_FIELDS = ("title", "url", "content", "score", "published_date")


def _clean(results: list) -> list[dict]:
    out = []
    for x in results or []:
        if not isinstance(x, dict):
            continue
        out.append({k: (x.get(k) if isinstance(x.get(k), (int, float)) or x.get(k) is None else str(x.get(k)))
                    for k in RESULT_FIELDS})
    return out


class PaidCache:
    def __init__(self, folder: str | Path, max_bytes: int = 64 << 20):
        self.dir = Path(os.path.expanduser(str(folder)))
        self.max_bytes = int(max_bytes)

    @staticmethod
    def key(provider: str, query: str, params: dict | None = None) -> str:
        blob = json.dumps({"v": VERSION, "p": provider, "q": normalise(query), "params": params or {}},
                          sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def _path(self, provider: str, k: str) -> Path:
        return self.dir / f"{provider}-{k[:40]}.json"

    def lookup(self, provider: str, query: str, params: dict | None = None,
               now: float | None = None) -> tuple[list[dict] | None, str]:
        """(results, "hit") or (None, "miss" | "expired"). Never raises, never creates the folder."""
        now = time.time() if now is None else now
        k = self.key(provider, query, params)
        p = self._path(provider, k)
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            return None, "miss"
        if not isinstance(d, dict) or d.get("key") != k or not isinstance(d.get("results"), list):
            return None, "miss"
        if float(d.get("expires", 0)) <= now:
            try:
                p.unlink()
            except OSError:
                pass
            return None, "expired"
        try:
            os.utime(p)                              # least recently used goes first
        except OSError:
            pass
        return d["results"], "hit"

    def store(self, provider: str, query: str, params: dict | None, results: list, ttl_s: int, tag: str = "",
              now: float | None = None) -> bool:
        """Store one provider answer (a list, possibly empty). False when it could not be written. Never raises."""
        now = time.time() if now is None else now
        k = self.key(provider, query, params)
        rec = {"v": VERSION, "key": k, "provider": provider, "query": normalise(query), "params": params or {},
               "tag": tag, "stored": now, "expires": now + max(0, int(ttl_s)), "results": _clean(results)}
        try:
            self.dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            p = self._path(provider, k)
            tmp = self.dir / f".{p.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            tmp.write_text(json.dumps(rec, ensure_ascii=False))
            os.replace(tmp, p)
            self.prune(now)
            return True
        except OSError:
            return False

    def _entries(self) -> list[tuple[Path, os.stat_result]]:
        out = []
        try:
            for p in self.dir.glob("*.json"):
                try:
                    out.append((p, p.stat()))
                except OSError:
                    pass
        except OSError:
            pass
        return out

    def prune(self, now: float | None = None, force: bool = False) -> int:
        """Keep the folder under its cap; returns the number of entries removed."""
        now = time.time() if now is None else now
        ents = self._entries()
        total = sum(st.st_size for _, st in ents)
        if total <= self.max_bytes and not force:
            return 0
        removed = 0
        with open(self.dir / ".lock", "a") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            ents = self._entries()
            total = sum(st.st_size for _, st in ents)
            keep = []
            for p, st in ents:                       # expired first
                try:
                    exp = float(json.loads(p.read_text()).get("expires", 0))
                except (OSError, ValueError, AttributeError):
                    exp = 0.0
                if exp <= now:
                    try:
                        p.unlink(); total -= st.st_size; removed += 1
                    except OSError:
                        pass
                else:
                    keep.append((p, st))
            target = int(self.max_bytes * 0.9)
            for p, st in sorted(keep, key=lambda e: e[1].st_mtime):
                if total <= target:
                    break
                try:
                    p.unlink(); total -= st.st_size; removed += 1
                except OSError:
                    pass
        return removed

    def stats(self) -> dict:
        ents = self._entries()
        return {"entries": len(ents), "bytes": sum(st.st_size for _, st in ents), "max_bytes": self.max_bytes}
