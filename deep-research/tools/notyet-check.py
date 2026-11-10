#!/usr/bin/env python3
"""notyet-check.py - phase 4 item 2 (the user, 10-20): "Status claims ("not yet published/released/available/
supported") get a fresh, dated search for anything newer than the sources before they go in a report."
Stage 1: run directly on saved reports (test case: o03's EN 18286, published in the Official Journal on 14 October 2026;
false-alarm check: the o01, o02 and o07 reports). Through strata-proxy (8090), holding run/bench.lock.

  notyet-check.py REPORT.md [...] [--date YYYY-MM-DD] [--n 1] [--effort medium] [--max-claims 15] [--label L]
    1. find   every "has not happened yet" statement in the report (not yet published / released / cited / available
              / supported / merged / in force, pending, expected later, no X yet), with a search query for each;
              up to --max-claims are checked, status claims first (the user, 10-22: the report's own words say "not
              yet", "pending", "still open", "unreleased" or "not <...> yet"), then the rest in the find step's order
    2. search LDR's own SearXNG (127.0.0.1:8889, the deep runs' search) with that query; the top results' titles,
              snippets and dates, and the text of the first 3 pages around the subject's words (trafilatura)
    3. judge  per claim: outdated (it has happened: what, when, where) / still true / unclear, from those results only
  -> <--out or the report's folder>/<folder>-<report stem>.notyet-<label><k>.json and one summary line per run
--date: the report's date (default: the file's modification date)."""
from __future__ import annotations

import argparse
import sys
import fcntl
import json
import re
import time
from datetime import date, datetime
from pathlib import Path

import requests

WS = Path("/home/USER/ai/deep-research")
PROXY = "http://127.0.0.1:8090"
SEARX = "http://127.0.0.1:8889"
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


def stream_call(messages: list, effort: str, max_tokens: int = 30000) -> dict:
    body = {"model": "strata", "messages": messages, "stream": True, "temperature": 1.0, "max_tokens": max_tokens,
            "reasoning_effort": effort, "stream_options": {"include_usage": True}}
    t0 = time.time()
    text, usage, finish = [], None, None
    with requests.post(PROXY + "/v1/chat/completions", json=body, stream=True, timeout=3600, proxies=NOPROXY) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: ") or line == b"data: [DONE]":
                continue
            d = json.loads(line[6:])
            if d.get("error"):
                raise RuntimeError(str(d["error"])[:300])
            usage = d.get("usage") or usage
            for ch in d.get("choices") or []:
                text.append((ch.get("delta") or {}).get("content") or "")
                finish = ch.get("finish_reason") or finish
    return {"text": "".join(text).strip(), "usage": usage, "finish": finish, "seconds": round(time.time() - t0, 1)}


def json_of(text: str):
    m = re.search(r"(?s)\{.*\}", text)
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


# 10-22 (the user): status claims first, then the rest up to the cap. Matched on the quote (the report's own words) -
# the find step's "status" line says "not yet" for nearly every claim. Stage 1's miss: o03's medium replay listed 39
# claims and checked the first 15; its EN 18286 sentence ("its OJ citation remains pending") was not among them.
STATUS_WORDS = re.compile(r"\bnot\s+yet\b|\bnot\s+(?:\w+\s+){1,2}yet\b|\bpending\b|\bstill\s+open\b|\bunreleased\b", re.I)


def pick(claims: list, max_claims: int) -> list:
    first = [bool(STATUS_WORDS.search(c.get("quote") or "")) for c in claims]
    order = sorted(range(len(claims)), key=lambda i: (not first[i], i))
    return [{**claims[i], "found_index": i, "status_first": first[i]} for i in order[:max_claims]]


def run_one(report: Path, rdate: str, effort: str, max_claims: int) -> dict:
    body = report.read_text(encoding="utf-8")
    body = re.split(r"(?m)^#{1,3} (Citation check|Sources|References)\s*$", body)[0]
    t0 = time.time()
    f = stream_call([{"role": "user", "content": FIND_PROMPT.format(date=rdate, report=body)}], effort)
    claims = (json_of(f["text"]) or {}).get("claims")
    if claims is None:
        return {"error": "find: no JSON", "raw": f["text"][:2000], "seconds": round(time.time() - t0, 1)}
    checked = []
    tried = failed = 0
    errs = []
    for c in pick(claims, max_claims):
        try:
            results = search(c.get("query") or c.get("subject") or "", c.get("subject") or "")
        except Exception as e:  # noqa: BLE001
            results = f"(search failed: {type(e).__name__})"
            errs.append(type(e).__name__)
        tried += 1
        if results.startswith("(search failed") or results == "(no results)":
            failed += 1
        # 10-21 (the user): searches mostly failing -> FAILED with the reason, no verdicts from the model's own
        # knowledge (stage 1's first run judged every claim with SearXNG 8889 down)
        if tried >= 3 and failed * 2 > tried:
            return {"claims_found": len(claims), "checked": [], "search_failed": True,
                    "error": f"FAILED: {failed} of {tried} web searches failed ({max(set(errs), key=errs.count) if errs else 'no results'}) - stopped, no verdicts",
                    "find_seconds": f["seconds"], "seconds": round(time.time() - t0, 1)}
        j = stream_call([{"role": "user", "content": JUDGE_PROMPT.format(
            date=rdate, today=date.today().isoformat(), quote=c.get("quote", ""), subject=c.get("subject", ""),
            status=c.get("status", ""), results=results)}], effort)
        checked.append({**c, "judge": json_of(j["text"]) or {"raw": j["text"][:1500]}, "judge_seconds": j["seconds"]})
    return {"claims_found": len(claims), "status_first": sum(1 for c in checked if c["status_first"]), "checked": checked,
            "found": claims, "find_seconds": f["seconds"], "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="+")
    ap.add_argument("--date")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--max-claims", type=int, default=15)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", help="folder for the results (default: next to each report)")
    a = ap.parse_args()
    sys.path.insert(0, str(WS / "tools"))
    import research_common as rc
    probs = rc.searxng_problems((8889,))
    if probs:
        raise SystemExit(f"FAILED before the start: {probs[8889]} - nothing checked")
    lock = open(WS / "run" / "bench.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    failed_runs = 0
    for rp in map(Path, a.reports):
        rdate = a.date or datetime.fromtimestamp(rp.stat().st_mtime).date().isoformat()
        for k in range(1, a.n + 1):
            res = {"report": str(rp), "report_date": rdate, "effort": a.effort, "k": k, **run_one(rp, rdate, a.effort,
                                                                                                    a.max_claims)}
            out = Path(a.out) if a.out else rp.parent
            out.mkdir(parents=True, exist_ok=True)
            dst = out / f"{rp.parent.name}-{rp.stem}.notyet-{a.label}{k}.json"
            dst.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
            v = [((c.get("judge") or {}).get("verdict")) for c in res.get("checked", [])]
            print(f"notyet {rp.parent.name}/{rp.name} {a.label}{k}: {res.get('claims_found')} claims, "
                  f"outdated {v.count('outdated')}, still true {v.count('still_true')}, unclear {v.count('unclear')}, "
                  f"{res.get('seconds')} s{(' ' + res['error']) if res.get('error') else ''}", flush=True)
            failed_runs += bool(res.get("search_failed"))
    lock.close()
    if failed_runs:
        raise SystemExit(f"{failed_runs} run(s) FAILED: web searches failing")


if __name__ == "__main__":
    main()
