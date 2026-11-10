"""The "not yet" fresh check (phase 4 item 2; the user 2026-10-20, run inside deep research from 2026-10-23).

"Status claims ("not yet published/released/available/supported") get a fresh, dated search for anything newer than
the sources before they go in a report." With LDR_DEEP_NOTYET=1, after the citation and setup checks: one call finds
every "has not happened yet" statement in the report; up to LDR_DEEP_NOTYET_MAX (15) are checked, status claims first
(the report's own words say "not yet", "pending", "still open", "unreleased" or "not <...> yet"); each gets a new search
on LDR's own SearXNG (127.0.0.1:8889) with the first pages read around its subject, and a judge call: outdated / still
true / unclear, from those results only. Each outdated statement gets the dated update right after it, marked as the
fresh check's, and a short "Fresh check" section lists every checked claim with the date of the check. Nothing is
deleted or rewritten. When the searches mostly fail, the check stops and says so (no verdicts from the model alone).
The prompts are tools/notyet-check.py's (stage 1), so its results carry over.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Callable

import requests

SEARX = os.environ.get("LDR_DEEP_NOTYET_SEARX", "http://127.0.0.1:8889")
NOPROXY = {"http": None, "https": None}
MARK = "You are the claim-verification step of a research system."   # strata-proxy's verify class (deep/prompts.py)

FIND_PROMPT = MARK + """ Below is a research report written on {date}. List every statement in it that something \
had NOT happened yet as of its sources: not yet published, released, adopted, cited, listed, available, supported, \
merged, approved, decided or in force; pending or under review; expected, planned or announced for later; "no X exists \
yet". Leave out final past events (something was withdrawn or rejected) and general forecasts with no specific event.
For each one give the exact quote, the subject (what had not happened), the status the report claims, and one web \
search query that would show whether it has happened since (name the subject precisely; no dates in the query).

<report>
{report}
</report>

Reply with JSON only: {{"claims": [{{"quote": "<copied exactly>", "subject": "...", "status": "...", "query": "..."}}]}}"""

JUDGE_PROMPT = MARK + """ A research report written on {date} says: "{quote}"
Subject: {subject}. Status the report claims: {status}. Today is {today}.
Below are fresh web search results and page excerpts. Decide whether the claimed status still holds today:
- "outdated": a source below shows that it has happened (since the report, or already before it). Say what happened \
and on what date, and give that source's URL.
- "still_true": the sources show it still has not happened; give the newest dated evidence.
- "unclear": the results do not settle it.
Use only the results below, and give dates only where a source states them.

<results>
{results}
</results>

Reply with JSON only: {{"verdict": "outdated|still_true|unclear", "update": "<one sentence, with the date>", \
"event_date": "<YYYY-MM-DD or empty>", "source": "<url or empty>"}}"""

STATUS_WORDS = re.compile(r"\bnot\s+yet\b|\bnot\s+(?:\w+\s+){1,2}yet\b|\bpending\b|\bstill\s+open\b|\bunreleased\b", re.I)


def enabled() -> bool:
    return os.environ.get("LDR_DEEP_NOTYET", "").strip().lower() in ("1", "true", "yes", "on")


def max_claims() -> int:
    try:
        return max(1, int(os.environ.get("LDR_DEEP_NOTYET_MAX", "15")))
    except ValueError:
        return 15


def json_of(text: str):
    m = re.search(r"(?s)\{.*\}", text or "")
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-/]+", s) if len(w) > 2]


def page_excerpt(url: str, keys: list[str], max_chars: int = 3000) -> str:
    import trafilatura

    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}, proxies=NOPROXY)
        text = trafilatura.extract(r.text, include_comments=False) or ""
    except Exception as e:  # noqa: BLE001
        return f"(not read: {type(e).__name__})"
    paras = [p for p in text.split("\n") if p.strip()]
    hit = [p for p in paras if any(k.lower() in p.lower() for k in keys)] or paras[:5]
    return "\n".join(hit)[:max_chars]


def search(query: str, subject: str) -> str:
    r = requests.get(SEARX + "/search", params={"q": query, "format": "json"}, timeout=30, proxies=NOPROXY)
    res = (r.json().get("results") or [])[:8]
    keys = words(subject)[:6]
    out = []
    for i, x in enumerate(res):
        out.append(f"[{i + 1}] {x.get('title', '')}\n{x.get('url', '')}\ndate: {x.get('publishedDate') or 'not given'}\n"
                   f"{(x.get('content') or '')[:400]}")
        if i < 3:
            out.append("page excerpt:\n" + page_excerpt(x.get("url", ""), keys))
    return "\n\n".join(out) or "(no results)"


def pick(claims: list, n: int) -> list:
    first = [bool(STATUS_WORDS.search(c.get("quote") or "")) for c in claims]
    order = sorted(range(len(claims)), key=lambda i: (not first[i], i))
    return [{**claims[i], "found_index": i, "status_first": first[i]} for i in order[:n]]


def check(llm: Callable[[str], str], body: str, search_fn: Callable[[str, str], str] = search,
          today: str | None = None) -> dict:
    """llm(prompt) -> text. The report body (before its sections) is checked as written today."""
    today = today or date.today().isoformat()
    f = llm(FIND_PROMPT.format(date=today, report=body))
    claims = (json_of(f) or {}).get("claims")
    if not isinstance(claims, list):
        return {"error": "find: no JSON", "raw": (f or "")[:2000], "date": today}
    checked, errs = [], []
    tried = failed = 0
    for c in pick([c for c in claims if isinstance(c, dict)], max_claims()):
        try:
            results = search_fn(c.get("query") or c.get("subject") or "", c.get("subject") or "")
        except Exception as e:  # noqa: BLE001
            results = f"(search failed: {type(e).__name__})"
            errs.append(type(e).__name__)
        tried += 1
        if results.startswith("(search failed") or results == "(no results)":
            failed += 1
        if tried >= 3 and failed * 2 > tried:
            return {"claims_found": len(claims), "checked": [], "search_failed": True, "date": today,
                    "error": f"{failed} of {tried} web searches failed - stopped, no verdicts"}
        j = llm(JUDGE_PROMPT.format(date=today, today=today, quote=c.get("quote", ""), subject=c.get("subject", ""),
                                    status=c.get("status", ""), results=results))
        checked.append({**c, "judge": json_of(j) or {"raw": (j or "")[:1500]}})
    if tried and failed * 2 > tried:      # fewer than 3 claims, searches mostly failed: no verdicts either
        return {"claims_found": len(claims), "checked": [], "search_failed": True, "date": today,
                "error": f"{failed} of {tried} web searches failed - no verdicts"}
    return {"claims_found": len(claims), "checked": checked, "found": claims, "date": today}


def annotate(body: str, res: dict) -> tuple[str, str]:
    """(body with each outdated statement followed by the dated update, the "Fresh check" section)."""
    today = res.get("date") or date.today().isoformat()
    if res.get("error"):
        return body, (f"## Fresh check\n\nThe fresh check of \"not yet\" statements did not complete ({res['error']}); "
                      "those statements were not re-checked.")
    rows = res.get("checked") or []
    if not rows:
        return body, ""
    lines = ["## Fresh check", "",
             f"Statements that something had not happened yet, checked with a new search on {today} "
             f"({len(rows)} of {res.get('claims_found', len(rows))} found):", ""]
    for c in rows:
        j = c.get("judge") or {}
        v = j.get("verdict") or "unclear"
        upd = (j.get("update") or "").strip()
        src = (j.get("source") or "").strip()
        q = (c.get("quote") or "").strip()
        if v == "outdated" and q:
            mark = f" **[Fresh check {today}: {upd or 'this has happened since'}{(' (' + src + ')') if src else ''}]**"
            at = body.find(q)
            if at >= 0:
                m = re.compile(r"[.!?](?=\s|$)|\n").search(body, at + len(q))
                end = m.start() if m else len(body)
                while end > at + len(q) and body[end - 1] == "]" and "[" in body[at + len(q):end]:
                    end = body.rfind("[", at + len(q), end)
                    while end > at + len(q) and body[end - 1] == " ":
                        end -= 1
                body = body[:end] + mark + body[end:]
        label = {"outdated": "OUTDATED", "still_true": "still true", "unclear": "unclear"}.get(v, v)
        lines.append(f"- \"{q[:300]}\" -> {label}{(': ' + upd) if upd else ''}{(' (' + src + ')') if src else ''}")
    return body, "\n".join(lines)
