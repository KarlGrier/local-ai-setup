"""Advisory checks after the report (phase 4 item 3, stage 2; the user, 2026-10-21).

"Keep the critic as an advisory pass that adds a short 'check these' list to the report. Don't let the two-source
verifier delete or rewrite claims, especially prices and specs on product questions (~50 % false alarms on o02). If it
goes to stage 2, run it flag-only."
  LDR_DEEP_CRITIC=1      a fresh-context critic reads the finished report (tools/level-replay.py critic's prompt)
  LDR_DEEP_VERIFY2=flag  the two-source verifier (level-replay.py verify2's method): key claims against the passages of
                         the sources they cite and of others the research read; disagreements are only listed
Both only add the "Check these" list (at most CHECK_MAX lines, the most important first); the report text is never
changed. Without the variables nothing here runs.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

CHECK_MAX = 8
VERIFY2_MAX_CLAIMS = 40
VERIFY2_OTHERS = 4

CRITIC_PROMPT = """You are the claim-verification step of a research system. Below are a research task and the final \
report written for it. Review the report as a critical expert reading it for the first time, for the person who \
asked. List the problems that matter:
- "reasoning": a conclusion that does not follow, a wrong calculation or comparison, a figure applied to the wrong \
item (another product's or model's specification), something technically impossible;
- "unsupported": a key claim with no citation, cited to something that is not a source, or resting on a single source \
where it matters;
- "contradiction": two statements of the report that disagree, or sources it reports as disagreeing without settling it;
- "stale": a status claim ("not yet", "pending", "expected", "the latest") that may have changed since its sources;
- "gap": a part of the task the report does not answer.
For each give the exact quote (for a gap: the part of the task), why it is a problem, and the action: "fix" with the \
corrected text where the report's own content is enough, or "research" with one web search query that would settle it.
At most 20, the most important first. Do not list matters of style.

<task>
{task}
</task>

<report>
{report}
</report>

Reply with JSON only: {{"issues": [{{"type": "reasoning|unsupported|contradiction|stale|gap", "quote": "...", "why": \
"...", "action": "fix|research", "fix": "<corrected text or empty>", "query": "<search query or empty>"}}]}}"""

VERIFY2_PROMPT = """You are the claim-verification step of a research system. Below are sentences from a research \
report, each followed by passages of several sources the research read: the ones the sentence cites and others that \
may bear on it. For each claim, say which sources state it, which contradict it, and which say nothing about it. Judge \
from the passages only, not from your own knowledge. A source supports a claim when it states the claim's facts \
(paraphrase is fine; figures, dates and names must match); it contradicts it when it states different facts.

{items}

For each claim output one line of JSON (JSON Lines, nothing else):
{{"claim": <number>, "supporting": [<source indices>], "contradicting": [<source indices>], "note": "<for a \
contradiction: what differs, at most 25 words>"}}"""


def critic_on() -> bool:
    return os.environ.get("LDR_DEEP_CRITIC", "").strip().lower() in ("1", "true", "yes", "on")


def verify2_on() -> bool:
    return os.environ.get("LDR_DEEP_VERIFY2", "").strip().lower() == "flag"


def _json(text: str, key: str):
    m = re.search(r"(?s)\{.*\}", text or "")
    try:
        return json.loads(m.group(0))[key] if m else None
    except (ValueError, KeyError, TypeError):
        return None


def domain(url: str) -> str:
    d = urlparse(url or "").netloc.lower()
    return d[4:] if d.startswith("www.") else d


def critic(llm, task: str, body: str) -> dict:
    text = llm(CRITIC_PROMPT.format(task=task, report=body))
    issues = _json(text, "issues")
    if issues is None:
        # phase 4 fixes (10-27): a reply cut off at the output cap keeps its complete issues (only with LDR_DEEP_FIX)
        from .checks import fixes_on, salvage_list
        if fixes_on():
            issues = salvage_list(text, "issues")
            if issues is not None:
                return {"issues": issues, "raw": None, "salvaged": True}
    return {"issues": issues, "raw": None if issues is not None else (text or "")[:4000]}


def verify2(writer, body: str, words, passages, count_text) -> list[dict]:
    """Key claims against their cited sources' passages and up to VERIFY2_OTHERS others that share words with them."""
    store = writer.store
    claims = writer.select_key_claims(writer.split_claims(body), VERIFY2_MAX_CLAIMS)
    stext = {s.idx: (s.page_text or "\n".join(s.snippets[:3] + [f.extraction for f in s.fetches if f.extraction]))
             for s in store.all_sources()}
    swords = {i: words(t[:200000]) for i, t in stext.items()}
    items = []
    for c in claims:
        plain = re.sub(r"\s*\[\d+(?:\s*[,\u2013-]\s*\d+)*\]", "", c["text"])
        cw = words(plain)
        others = sorted((i for i in swords if i not in c["sources"]), key=lambda i: -len(swords[i] & cw))
        others = [i for i in others[:VERIFY2_OTHERS] if len(swords[i] & cw) >= 3]
        blocks = []
        for i in list(c["sources"]) + others:
            s = store.source(i)
            if s is None or i not in stext:
                continue
            tag = "cited" if i in c["sources"] else "not cited"
            blocks.append(f"Source [{i}] ({tag}) {s.title[:100]} - {domain(s.url)}:\n{passages(stext[i], cw, 900)}")
        items.append({"claim": c, "plain": plain, "body": "\n\n".join(blocks)})
    batches, cur, tok = [], [], 0
    for it in items:
        n = count_text(it["body"]) + 60
        if cur and (len(cur) >= 6 or tok + n > 36000):
            batches.append(cur)
            cur, tok = [], 0
        cur.append(it)
        tok += n
    if cur:
        batches.append(cur)
    for b in batches:
        listing = "\n\n".join(f"### Claim {j + 1}\n{it['plain']}\nCited: {it['claim']['sources']}\n{it['body']}"
                              for j, it in enumerate(b))
        outp = writer._llm("verify", VERIFY2_PROMPT.format(items=listing))
        got = {}
        for line in outp.splitlines():
            line = line.strip().strip(",")
            if line.startswith("{"):
                try:
                    d = json.loads(line)
                    got[int(d.get("claim"))] = d
                except (ValueError, TypeError):
                    continue
        for j, it in enumerate(b):
            d = got.get(j + 1) or {}
            it["result"] = {"supporting": [x for x in (d.get("supporting") or []) if isinstance(x, int)],
                            "contradicting": [x for x in (d.get("contradicting") or []) if isinstance(x, int)],
                            "note": str(d.get("note", ""))[:300], "answered": bool(d)}
    return [{"text": it["plain"], "cited": it["claim"]["sources"], **it.get("result", {})} for it in items]


PRIORITY = {"reasoning": 0, "contradiction": 1, "disagree": 1, "stale": 2, "unsupported": 3, "gap": 4}


def check_these(crit: dict | None, v2: list[dict] | None) -> str:
    """The short advisory list: critic issues and the claims whose sources disagree, the most important first."""
    rows = []
    for i in (crit or {}).get("issues") or []:
        q = (i.get("quote") or "").strip()
        if not q:
            continue
        hint = (i.get("fix") or "").strip() if i.get("action") == "fix" else (
            f"a search that would settle it: {i.get('query')}" if i.get("query") else "")
        rows.append((PRIORITY.get(i.get("type"), 5), f"- **{i.get('type', 'check')}**: \"{q[:240]}\" - {(i.get('why') or '').strip()}"
                     + (f" ({hint})" if hint else "")))
    for c in v2 or []:
        if c.get("contradicting"):
            srcs = ", ".join(f"[{x}]" for x in c["contradicting"])
            rows.append((PRIORITY["disagree"], f"- **sources disagree**: \"{c['text'][:240]}\" - {srcs} "
                         f"{'say(s) otherwise: ' + c['note'] if c.get('note') else 'say(s) otherwise'}"))
    if not rows:
        return ""
    rows.sort(key=lambda r: r[0])
    shown = rows[:CHECK_MAX]
    head = ["## Check these", "",
            "An automatic second reading flagged these points. They are suggestions to check, not corrections: the "
            "report above is unchanged" + (f" ({len(rows) - CHECK_MAX} more in advisory.json)." if len(rows) > CHECK_MAX else "."), ""]
    return "\n".join(head + [r[1] for r in shown])
