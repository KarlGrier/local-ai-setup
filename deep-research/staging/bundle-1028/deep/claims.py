"""Claims with quote, URL and date (phase 4 item 5, Karl 10-27; with LDR_DEEP_FIX including "claims").

The page extractor already answers with verbatim quotes, one per line (tools/fetch/prompts.py: "Output ONLY verbatim
quotes from the page"). Each line becomes a claim of its source, made in code, no model call:
  * checked word for word against the page text it came from: "exact", "close" (start and end found in order - a
    changed middle), or "not on the page" (the extractor paraphrased; such lines stay out of the writer's evidence);
  * dated: a date inside the quote, else the nearest date before it on the page (within 800 characters - a dateline,
    a changelog heading), else the page's own published date;
  * kept on the source (Source.claims) and in evidence.jsonl ("claims" records).
The report writer then gives each section its sources' checked, dated quotes first (report.py).
"""

from __future__ import annotations

import re
from typing import Any

from .checks import _norm_map

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
     "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
_MON = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun" \
       r"|jul|aug|sept|sep|oct|nov|dec)\.?"
DATE_RES = [
    ("iso", re.compile(r"\b((?:19|20)\d\d)-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?\b")),
    ("dmy", re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r",?\s+((?:19|20)\d\d)\b", re.I)),
    ("mdy", re.compile(r"\b" + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+((?:19|20)\d\d)\b", re.I)),
    ("my", re.compile(r"\b" + _MON + r"\s+((?:19|20)\d\d)\b", re.I)),
]
MIN_QUOTE_CHARS = 25
NEAR_CHARS = 800


def _iso(kind: str, m: re.Match) -> str:
    g = m.groups()
    if kind == "iso":
        return f"{g[0]}-{g[1]}" + (f"-{g[2]}" if g[2] else "")
    if kind == "dmy":
        return f"{g[2]}-{MONTHS[g[1].lower().rstrip('.')]:02d}-{int(g[0]):02d}"
    if kind == "mdy":
        return f"{g[2]}-{MONTHS[g[0].lower().rstrip('.')]:02d}-{int(g[1]):02d}"
    return f"{g[1]}-{MONTHS[g[0].lower().rstrip('.')]:02d}"


def dates_in(text: str) -> list[tuple[int, str]]:
    """(position, ISO date) of every date in text; a day-precise match wins over a month-only one at the same place."""
    found: dict[int, str] = {}
    taken: list[tuple[int, int]] = []
    for kind, rx in DATE_RES:
        for m in rx.finditer(text or ""):
            if any(a <= m.start() < b for a, b in taken):
                continue
            try:
                found[m.start()] = _iso(kind, m)
            except (KeyError, ValueError):
                continue
            taken.append(m.span())
    return sorted(found.items())


def quote_lines(extraction: str) -> list[str]:
    out = []
    for line in (extraction or "").splitlines():
        q = line.strip().strip("-•*> ").strip()
        q = q[1:-1].strip() if len(q) > 2 and q[0] in "\"“'" and q[-1] in "\"”'" else q
        if len(q) >= MIN_QUOTE_CHARS and not q.upper().startswith("NOT RELEVANT"):
            out.append(q)
    return out


class PageIndex:
    """One page's normalised text, for checking many quotes against it."""

    def __init__(self, page_text: str):
        self.text = page_text or ""
        self.norm, self.map = _norm_map(self.text)

    def find(self, quote: str) -> tuple[str, int | None]:
        q = _norm_map(quote)[0].strip().strip(".").strip()
        if len(q) < 12:
            return "not on the page", None
        p = self.norm.find(q)
        if p >= 0:
            return "exact", self.map[p]
        words = q.split(" ")
        if len(words) >= 10:
            head, tail = " ".join(words[:5]), " ".join(words[-5:])
            p = self.norm.find(head)
            while p >= 0:
                t = self.norm.find(tail, p + len(head))
                if t >= 0 and t - p <= 1.5 * len(q):
                    return "close", self.map[p]
                p = self.norm.find(head, p + 1)
        return "not on the page", None


def from_extraction(extraction: str, page_text: str, page_date: str = "", focus: str = "",
                    agent: str = "") -> list[dict[str, Any]]:
    """The claims of one extraction: each quote line checked against the page and dated."""
    if not page_text:
        return []
    idx = PageIndex(page_text)
    page_dates = dates_in(page_text)
    out = []
    for q in quote_lines(extraction):
        found, pos = idx.find(q)
        date, how = "", ""
        inq = dates_in(q)
        if inq:
            date, how = inq[-1][1], "in the quote"
        elif pos is not None:
            before = [d for p, d in page_dates if pos - NEAR_CHARS <= p <= pos]
            if before:
                date, how = before[-1], "on the page before the quote"
        if not date and page_date:
            date, how = str(page_date)[:10], "the page's date"
        out.append({"quote": q[:1200], "found": found, "date": date, "date_how": how, "focus": focus[:200],
                    "agent": agent})
    return out


def merge(existing: list[dict], new: list[dict]) -> list[dict]:
    """New claims not already kept (by their normalised quote)."""
    seen = {_norm_map(c["quote"])[0] for c in existing}
    add = []
    for c in new:
        k = _norm_map(c["quote"])[0]
        if k not in seen:
            seen.add(k)
            add.append(c)
    return add


def evidence_block(claims: list[dict], max_items: int = 40) -> str:
    """The writer's view: the checked quotes, dated."""
    lines = []
    for c in claims:
        if c.get("found") == "not on the page":
            continue
        d = f" ({c['date']}, {c['date_how']})" if c.get("date") else " (undated)"
        lines.append(f'- "{c["quote"]}"{d}')
        if len(lines) >= max_items:
            break
    return ("Checked quotes from this page (verbatim, with dates):\n" + "\n".join(lines)) if lines else ""


def stats(sources: list[Any]) -> dict[str, Any]:
    cs = [c for s in sources for c in (getattr(s, "claims", None) or [])]
    n = len(cs)
    return {"claims": n, "exact": sum(c["found"] == "exact" for c in cs),
            "close": sum(c["found"] == "close" for c in cs),
            "not_on_page": sum(c["found"] == "not on the page" for c in cs),
            "dated": sum(bool(c.get("date")) for c in cs),
            "sources_with_claims": sum(1 for s in sources if getattr(s, "claims", None))}
