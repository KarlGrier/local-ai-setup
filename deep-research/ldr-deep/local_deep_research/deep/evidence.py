"""Evidence store: everything the agents gathered in one research, kept for the report and the verification pass.

Thread-safe (the lead, parallel subagents and LangGraph's parallel tool threads all write to it). Optionally
mirrored to ``<out_dir>/<research>/evidence.jsonl`` as it grows, so a crash or cancel still leaves the evidence.
Source indices are the strategy collector's citation indices (the [N] the agents cite and LDR's Sources list uses).
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from . import current_agent


@dataclass
class Fetch:
    idx: int
    url: str
    title: str
    focus: str
    extraction: str
    agent: str
    t: float


@dataclass
class Source:
    idx: int
    url: str
    title: str = ""
    snippets: list[str] = field(default_factory=list)
    page_text: str = ""          # the full fetched text (up to the fetch cap), if the page was read
    fetches: list[Fetch] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    # phase 4 items 5 + 6 (10-28): read by the background reader, the page's date, the cited page this primary source
    # was found from, primary sources found from this page, why it could not be read, the page's checked claims
    auto_read: bool = False
    date: str = ""
    via: int | None = None
    primaries: list[int] = field(default_factory=list)
    unreadable: str = ""
    claims: list[dict] = field(default_factory=list)


class EvidenceStore:
    def __init__(self, query: str, out_dir: Path | None = None):
        self.query = query
        self.t0 = time.time()
        self.lock = threading.RLock()
        self.sources: dict[int, Source] = {}
        self.url_to_idx: dict[str, int] = {}
        self.searches: list[dict[str, Any]] = []
        self.subagents: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.page_cache: dict[str, dict[str, Any]] = {}     # url -> fetch result (to avoid re-downloading)
        self.reader = None                                   # phase 4 item 6: deep/reading.py's Reader, when on
        self.out_dir = out_dir
        self._jsonl = None
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            self._jsonl = open(out_dir / "evidence.jsonl", "a", encoding="utf-8")
            self._write({"type": "start", "query": query})

    # -- persistence ------------------------------------------------------------------------------------------------
    def _write(self, rec: dict[str, Any]) -> None:
        if self._jsonl is None:
            return
        rec = {"t": round(time.time() - self.t0, 2), "agent": current_agent.get(), **rec}
        try:
            self._jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._jsonl.flush()
        except Exception:  # noqa: BLE001
            logger.exception("deep: evidence write failed")

    def close(self) -> None:
        with self.lock:
            if self._jsonl is not None:
                self._jsonl.close()
                self._jsonl = None

    # -- recording ----------------------------------------------------------------------------------------------------
    def _source(self, idx: int, url: str, title: str = "") -> Source:
        s = self.sources.get(idx)
        if s is None:
            s = Source(idx=idx, url=url, title=title)
            self.sources[idx] = s
            self.url_to_idx.setdefault(url, idx)
        elif title and not s.title:
            s.title = title
        return s

    def add_search(self, query: str, indexed_results: list[dict[str, Any]], engine: str = "") -> None:
        with self.lock:
            rows = []
            for r in indexed_results or []:
                if not isinstance(r, dict):
                    continue
                try:
                    idx = int(r.get("index"))
                except (TypeError, ValueError):
                    continue
                url = r.get("link") or r.get("url") or ""
                s = self._source(idx, url, r.get("title") or "")
                snip = (r.get("snippet") or r.get("body") or "").strip()
                if snip and snip not in s.snippets:
                    s.snippets.append(snip)
                if query not in s.queries:
                    s.queries.append(query)
                rows.append({"idx": idx, "url": url, "title": r.get("title") or "", "snippet": snip[:500]})
            self.searches.append({"query": query, "agent": current_agent.get(), "n": len(rows),
                                  "t": round(time.time() - self.t0, 1)})
            self._write({"type": "search", "query": query, "engine": engine, "results": rows})

    def add_fetch(self, idx: int | None, url: str, title: str, focus: str, page_text: str, extraction: str) -> None:
        with self.lock:
            if idx is None:
                idx = self.url_to_idx.get(url)
            rec = {"type": "fetch", "idx": idx, "url": url, "title": title, "focus": focus,
                   "page_chars": len(page_text or ""), "extraction": extraction}
            if idx is not None:
                s = self._source(idx, url, title)
                if page_text and len(page_text) > len(s.page_text):
                    s.page_text = page_text
                    rec["page_text"] = page_text
                s.fetches.append(Fetch(idx, url, title, focus, extraction, current_agent.get(), time.time() - self.t0))
                s.auto_read = False
                pdate = str((self.page_cache.get(url) or {}).get("published_date") or "")
                s.date = s.date or pdate
            self._write(rec)
            # phase 4 item 5 (10-28): the extraction's quotes become claims - checked against the page, dated
            if idx is not None and extraction and not extraction.startswith("NOT RELEVANT"):
                from .checks import fix_on
                if fix_on("claims"):
                    from . import claims as _claims
                    new = _claims.merge(s.claims, _claims.from_extraction(extraction, page_text or s.page_text, pdate,
                                                                          focus, current_agent.get()))
                    if new:
                        s.claims.extend(new)
                        self._write({"type": "claims", "idx": idx, "url": url, "claims": new})

    def cache_page(self, url: str, result: dict[str, Any]) -> None:
        with self.lock:
            if result.get("status") == "success" and (result.get("content") or "").strip():
                self.page_cache[url] = result

    def cached_page(self, url: str) -> dict[str, Any] | None:
        with self.lock:
            return self.page_cache.get(url)

    def add_subagent(self, topic: str, text: str, status: str, seconds: float, calls: int) -> None:
        with self.lock:
            self.subagents.append({"topic": topic, "text": text, "status": status, "seconds": round(seconds, 1),
                                   "calls": calls, "agent": current_agent.get()})
            self._write({"type": "subagent", "topic": topic, "status": status, "seconds": round(seconds, 1),
                         "calls": calls, "text": text})
        if self.reader is not None:
            self.reader.want(text)                           # item 6: read what these findings cite

    # -- phase 4 item 6 (10-28): pages read by the background reader ----------------------------------------------------
    def add_read(self, idx: int, url: str, title: str, page_text: str, date: str = "", via: int | None = None) -> None:
        with self.lock:
            s = self._source(idx, url, title)
            if page_text and len(page_text) > len(s.page_text):
                s.page_text = page_text
                s.auto_read = not s.fetches
            s.date = s.date or (date or "")
            if via is not None:
                s.via = via
            s.unreadable = ""
            self._write({"type": "read", "idx": idx, "url": url, "title": title, "date": date or "", "via": via,
                         "page_chars": len(page_text or ""), "page_text": page_text})

    def mark_unreadable(self, idx: int, why: str) -> None:
        with self.lock:
            s = self.sources.get(idx)
            if s is None or s.page_text:
                return
            s.unreadable = why[:200]
            self._write({"type": "unreadable", "idx": idx, "url": s.url, "why": s.unreadable})

    def link_primary(self, via: int, idx: int) -> None:
        with self.lock:
            s = self.sources.get(via)
            if s is not None and idx not in s.primaries and idx != via:
                s.primaries.append(idx)
                self._write({"type": "primary", "via": via, "idx": idx})

    def add_note(self, kind: str, **data: Any) -> None:
        with self.lock:
            self.notes.append({"kind": kind, **data})
            self._write({"type": "note", "kind": kind, **data})

    # -- views ------------------------------------------------------------------------------------------------------
    def fetched_sources(self) -> list[Source]:
        with self.lock:
            return sorted((s for s in self.sources.values() if s.fetches), key=lambda s: s.idx)

    def all_sources(self) -> list[Source]:
        with self.lock:
            return sorted(self.sources.values(), key=lambda s: s.idx)

    def source(self, idx: int) -> Source | None:
        with self.lock:
            return self.sources.get(idx)

    def source_list_text(self, max_items: int = 400) -> str:
        """Deterministic list of every source seen: '[N] title — url (read)'."""
        with self.lock:
            lines = []
            for s in sorted(self.sources.values(), key=lambda s: (not s.fetches, s.idx))[:max_items]:
                mark = " (read)" if s.fetches else ""
                lines.append(f"[{s.idx}] {s.title[:90]} — {s.url}{mark}")
            more = len(self.sources) - len(lines)
            if more > 0:
                lines.append(f"... and {more} more search results not listed")
            return "\n".join(lines)

    def queries_text(self, max_items: int = 300) -> str:
        with self.lock:
            seen, out = set(), []
            for s in self.searches:
                q = s["query"]
                if q not in seen:
                    seen.add(q)
                    out.append(q)
            if len(out) > max_items:
                out = out[:max_items] + [f"... and {len(out) - max_items} more"]
            return "; ".join(out)

    def stats(self) -> dict[str, Any]:
        with self.lock:
            out = {"searches": len(self.searches), "sources_seen": len(self.sources),
                   "pages_read": sum(1 for s in self.sources.values() if s.fetches),
                   "fetches": sum(len(s.fetches) for s in self.sources.values()),
                   "subagents": len(self.subagents), "elapsed_s": round(time.time() - self.t0, 1)}
            if self.reader is not None:
                out["pages_auto_read"] = sum(1 for s in self.sources.values() if s.auto_read)
                out["primary_sources"] = sum(1 for s in self.sources.values() if s.via is not None)
                out["unreadable"] = sum(1 for s in self.sources.values() if s.unreadable)
            return out


CITE_RE = re.compile(r"[\[【](\d+(?:\s*[,–-]\s*\d+)*)[\]】]")


def cited_indices(text: str) -> list[int]:
    """All [N] / [N, M] / [N-M] indices in text, in order of first appearance."""
    out: list[int] = []
    for m in CITE_RE.finditer(text or ""):
        for part in re.split(r"\s*,\s*", m.group(1)):
            if re.match(r"^\d+\s*[–-]\s*\d+$", part):
                a, b = (int(x) for x in re.split(r"\s*[–-]\s*", part))
                rng = range(a, b + 1) if 0 <= b - a <= 20 else [a, b]
                for n in rng:
                    if n not in out:
                        out.append(n)
            elif part.strip().isdigit():
                n = int(part)
                if n not in out:
                    out.append(n)
    return out
