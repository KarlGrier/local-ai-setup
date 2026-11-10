"""The "tried / ruled out" list from the user's own files (phase 4 item 4; the round brief, the user 2026-10-23).

With LDR_DEEP_TRIED=1 and files on the job, a list of what the user's project has already tried, adopted, rejected or
ruled out (and what it planned but did not try) is extracted from those files ONCE per file set - one call per part of
the files, then one merge call - and cached by the files' contents (run/tried/<key>.json and .md, saved for the user
to check; a copy goes into the research's folder as tried-list.md). The lead agent's system prompt and the report
writer's outline, section and opening prompts then carry it, so known dead ends are not searched again and the report
separates what is new from what was already tried. Without the variable, or without files, nothing here runs.

tools/tried-list.py builds the list before a measured run (through strata-proxy), so its calls stay out of the run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Callable

from loguru import logger

CACHE = Path(os.environ.get("LDR_DEEP_TRIED_DIR") or "/home/USER/ai/deep-research/run/tried")
PART_CHARS = 60_000            # ~22K tokens a part (dense notes): room to think and list within the 131K context
MAP_MAX = 30                   # entries a part may list (10-23: uncapped, part 1 of o01's notes ran past 16K tokens)
MERGE_CHARS = 100_000          # the most entry text one merge call reads (~25K tokens); more is merged in batches
FINAL_MAX = 200                # entries the final merge keeps
BLOCK_CHARS = 36_000           # the most the prompts carry (~9K tokens); the full list stays in the .md
STATUS = ("tried_rejected", "ruled_out_without_trying", "tried_inconclusive", "adopted", "planned_not_tried")
LABEL = {"adopted": "adopted (in use)", "tried_rejected": "tried, rejected", "tried_inconclusive": "tried, inconclusive",
         "ruled_out_without_trying": "ruled out without trying", "planned_not_tried": "planned, not tried"}

MARK = "You are the claim-verification step of a research system."   # strata-proxy's one-shot class (deep/prompts.py)

MAP_PROMPT = MARK + """ Below is part {i} of {n} of the user's own project files ({names}). List every technique, \
method, setting, tool, library, model or idea that this text shows the project has already tried, measured, adopted, \
rejected or ruled out - and anything it lists as planned or proposed but not tried. One entry per idea (merge repeats \
within this part; fold small settings of one idea into that idea's entry), at most {max} entries - the most important \
first. Only what the text states; leave out general background, people and dates on their own. Keep it short.
For each entry:
- name: short and specific (at most 8 words), as a web search would name it (e.g. "speculative decoding with an MTP drafter")
- status: adopted | tried_rejected | tried_inconclusive | ruled_out_without_trying | planned_not_tried
- result: at most 25 words - the measured result or the reason, as the text gives it (numbers if it has them)
- where: the section, round or date in the text

<part>
{text}
</part>

Reply with JSON only: {{"entries": [{{"name": "...", "status": "...", "result": "...", "where": "..."}}]}}"""

MERGE_PROMPT = MARK + """ Below are entries extracted part by part from the user's own project files: what the \
project has already tried, adopted, rejected or ruled out, and what it planned. Merge them into one list: one entry per \
idea (entries that name the same idea become one; the later status wins - later rounds and dates over earlier ones - \
and the most informative result is kept). Drop entries that are not a technique, method, setting, tool, library, model \
or idea. At most {max} entries, the most important first. Keep names short (at most 8 words) and each result to at \
most 25 words.

<entries>
{entries}
</entries>

Reply with JSON only: {{"entries": [{{"name": "...", "status": "...", "result": "...", "where": "..."}}]}}"""

LEAD_INTRO = ("What the user's own files show their project has ALREADY done (extracted from those files; the user can "
              "check this list). Plan with it: do not spend searches re-establishing what is listed here; look for "
              "what is new relative to it - newer versions, implementations, results, or ideas not on the list. When a "
              "finding matches an entry, say that the project already tried, adopted or ruled it out, and what, if "
              "anything, is new about it.")
REPORT_NOTE = ("Separate what is new from what <tried_list> shows the user's project has already tried, adopted or "
               "ruled out: mark such items as already tried, with the project's own result, and lead with what is new.")


def enabled() -> bool:
    return os.environ.get("LDR_DEEP_TRIED", "").strip().lower() in ("1", "true", "yes", "on")


def key(files: list[str]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(Path(f).name.encode() + b"\0" + hashlib.sha256(Path(f).read_bytes()).digest())
    return h.hexdigest()[:16]


def _entries(text: str) -> list[dict] | None:
    m = re.search(r"(?s)\{.*\}", text or "")
    if not m:
        return None
    for t in (m.group(0), re.sub(r",\s*([}\]])", r"\1", m.group(0))):
        try:
            e = json.loads(t).get("entries")
            return [x for x in e if isinstance(x, dict) and (x.get("name") or "").strip()] if isinstance(e, list) else None
        except (ValueError, AttributeError):
            continue
    return None


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _dedupe(entries: list[dict]) -> list[dict]:
    """The fallback merge: one entry per normalised name, the later one (files are read in order) winning."""
    by: dict[str, dict] = {}
    for e in entries:
        by[_norm(e["name"])] = e
    return list(by.values())


def _lines(entries: list[dict]) -> list[str]:
    return [json.dumps({k: e.get(k, "") for k in ("name", "status", "result", "where")}, ensure_ascii=False)
            for e in entries]


def _merge(llm, entries: list[dict], final_max: int) -> tuple[list[dict], str]:
    """One merge call when the entries fit MERGE_CHARS, else batches merged first and those results merged again."""
    lines = _lines(entries)
    if sum(len(x) + 1 for x in lines) <= MERGE_CHARS:
        out, finish = llm(MERGE_PROMPT.format(entries="\n".join(lines), max=final_max), 32768, "medium")
        got = _entries(out)
        if got is None or finish == "length":
            return _dedupe(entries)[:final_max * 2], "dedupe (a merge call gave no complete list)"
        return got, "merge"
    batches, cur, n = [], [], 0
    for e, x in zip(entries, lines):
        if cur and n + len(x) > MERGE_CHARS:
            batches.append(cur); cur, n = [], 0
        cur.append(e); n += len(x) + 1
    batches.append(cur)
    merged, modes = [], []
    for b in batches:
        got, mode = _merge(llm, b, final_max)
        merged += got; modes.append(mode)
    if len(batches) == 1:          # one batch that still did not fit (very long lines): stop splitting
        return _dedupe(merged)[:final_max * 2], "dedupe (entries too long to merge)"
    final, mode = _merge(llm, _dedupe(merged), final_max)
    return final, f"merge in {len(batches)} batches, then " + mode


def build(llm: Callable[[str, int, str], tuple[str, str | None]], files: list[str]) -> dict:
    """llm(prompt, max_tokens, effort) -> (text, finish). One low-effort call per part of the files (at most MAP_MAX
    entries each), a dedupe by name, then medium-effort merge calls (batched above MERGE_CHARS)."""
    from .files import file_text, pieces

    t0 = time.time()
    parts = [(Path(f).name, p) for f in files for p in pieces(file_text(f), PART_CHARS)]
    names = ", ".join(Path(f).name for f in files)
    raw: list[dict] = []
    failed = 0
    for i, (fname, text) in enumerate(parts, 1):
        out, finish = llm(MAP_PROMPT.format(i=i, n=len(parts), names=names, text=text, max=MAP_MAX), 32768, "low")
        got = _entries(out)
        if got is None:
            failed += 1
            logger.warning(f"deep tried: part {i}/{len(parts)} ({fname}) gave no list (finish {finish})")
            continue
        raw += [{**e, "file": fname} for e in got]
    merged, mode = None, "none"
    if raw:
        merged, mode = _merge(llm, _dedupe(raw), FINAL_MAX)
    entries = [e for e in (merged or []) if e.get("status") in STATUS] + \
              [{**e, "status": "tried_inconclusive"} for e in (merged or []) if e.get("status") not in STATUS]
    return {"files": [str(f) for f in files], "parts": len(parts), "parts_failed": failed, "raw_entries": len(raw),
            "mode": mode, "entries": entries, "seconds": round(time.time() - t0, 1),
            "built": time.strftime("%Y-%m-%d %H:%M")}


def markdown(res: dict) -> str:
    lines = [f"# Tried / ruled out - from your files ({res['built']})", "",
             "Extracted from: " + ", ".join(Path(f).name for f in res["files"]) +
             f". {len(res['entries'])} entries from {res['parts']} parts. Check it: the research used this list to "
             "separate new ideas from ones your project already tried.", ""]
    for st in STATUS:
        group = [e for e in res["entries"] if e.get("status") == st]
        if group:
            lines += [f"## {LABEL[st].capitalize()} ({len(group)})", ""]
            lines += [f"- **{e['name'].strip()}** - {(e.get('result') or '').strip()}"
                      + (f" ({e['where'].strip()})" if (e.get("where") or "").strip() else "") for e in group]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def get(files: list[str], llm: Callable[[str, int, str], tuple[str, str | None]] | None) -> dict | None:
    """The cached list for this file set, or a new one when llm is given (else None)."""
    k = key(files)
    p = CACHE / f"{k}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    if llm is None:
        return None
    res = build(llm, files)
    if not res["entries"]:
        logger.warning("deep tried: no entries extracted; nothing cached")
        return res
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    (CACHE / f"{k}.md").write_text(markdown(res), encoding="utf-8")
    logger.info(f"deep tried: {len(res['entries'])} entries from {res['parts']} parts in {res['seconds']} s -> {p}")
    return res


def block(res: dict) -> str:
    """<tried_list> for the prompts. Tried-and-rejected, ruled-out and inconclusive entries with their results (the
    reasons matter); adopted and planned ones as compact name lists (that they exist matters). Results are shortened
    until the whole block fits BLOCK_CHARS. (10-23: the first form cut at 24K in status order and dropped most adopted
    and all planned entries of o01's list - the ones that say what is not new.)"""
    names = {st: [e["name"].strip() for e in res["entries"] if e.get("status") == st] for st in STATUS}
    lists = "".join(f"{LABEL[st].capitalize()}: " + "; ".join(names[st]) + "\n"
                    for st in ("adopted", "planned_not_tried") if names[st])
    for width in (160, 100, 60, 0):
        rows = [f"- {e['name'].strip()} [{LABEL[st]}]" + (f": {(e.get('result') or '').strip()[:width]}" if width else "")
                for st in ("tried_rejected", "ruled_out_without_trying", "tried_inconclusive")
                for e in res["entries"] if e.get("status") == st]
        text = "<tried_list>\n" + LEAD_INTRO + "\n" + "\n".join(rows) + "\n" + lists + "</tried_list>"
        if len(text) <= BLOCK_CHARS:
            return text
    return text[:BLOCK_CHARS - 60] + "\n... (the rest in the user's tried-list file)\n</tried_list>"


def with_tried(prompt: str, blk: str) -> str:
    """A report prompt (a str.format template) with the list and note right after </task>."""
    assert "</task>" in prompt
    b = blk.replace("{", "{{").replace("}", "}}")
    return prompt.replace("</task>", "</task>\n\n" + b + "\n" + REPORT_NOTE, 1)
