"""The user's own files as research sources (workspace patch, 2026-10-17).

A job started from Jan can name files (or folders, expanded by the MCP server). The agents get one more tool,
``read_file(file, focus, part)``: it reads one piece of a file (up to LDR_DEEP_FETCH_MAX_CHARS characters, the same
cap as a web page), runs the same extraction step as fetch_content on it, registers the piece as a citable source
(file://<path>#part=<n>) and stores its full text in the evidence store - so the report cites the user's files with
[N] like web pages, and the citation check verifies those claims against the file's own text.

Text extraction: PDFs with pypdf, HTML stripped to text, everything else read as UTF-8.
"""

from __future__ import annotations

import html
import re
import threading
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from loguru import logger

from . import config

_texts: dict[str, str] = {}
_lock = threading.Lock()


def file_text(path: str) -> str:
    with _lock:
        if path in _texts:
            return _texts[path]
    p = Path(path)
    try:
        if p.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            r = PdfReader(str(p))
            text = "\n\n".join(f"[page {i + 1}]\n{(pg.extract_text() or '').strip()}" for i, pg in enumerate(r.pages))
        else:
            text = p.read_text(encoding="utf-8", errors="replace")
            if p.suffix.lower() in (".html", ".htm"):
                text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
                text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", text))
                text = re.sub(r"[ \t]+", " ", text)
                text = re.sub(r"\n\s*\n+", "\n\n", text)
    except Exception as e:  # noqa: BLE001
        text = f"(could not read {p.name}: {type(e).__name__}: {e})"
    with _lock:
        _texts[path] = text
    return text


def pieces(text: str, size: int) -> list[str]:
    """Cut at paragraph boundaries where possible, never longer than size."""
    out, i = [], 0
    while i < len(text):
        j = min(len(text), i + size)
        if j < len(text):
            k = text.rfind("\n\n", i + size // 2, j)
            if k > i:
                j = k
        out.append(text[i:j])
        i = j
    return out or [""]


def file_table(files: list[str]) -> list[dict[str, Any]]:
    size = config().fetch_max_chars
    rows = []
    for n, f in enumerate(files, 1):
        t = file_text(f)
        rows.append({"n": n, "path": f, "name": Path(f).name, "chars": len(t), "parts": len(pieces(t, size))})
    return rows


def files_addendum(files: list[str]) -> str:
    rows = file_table(files)
    lines = [f"  {r['n']}. {r['name']} ({r['chars']:,} characters, {r['parts']} part{'s' if r['parts'] > 1 else ''})"
             for r in rows]
    return ("\n\nTHE USER'S FILES (part of this research; read them with read_file before searching the web for "
            "what they already cover):\n" + "\n".join(lines) +
            "\nread_file(file, focus, part) returns the passages of one part that matter for `focus`; `file` is the "
            "number or the name above, parts start at 1. Cite what you take from a file by the [N] it returns, like a "
            "web page. Subagents can read the files too.")


def make_read_file_tool(files: list[str], collector: Any, model: Any, overall_query: str):
    """The agents' read_file tool for this research's files."""
    from ..advanced_search_system.tools.fetch import _register_in_collector
    from ..advanced_search_system.tools.fetch.prompts import SUMMARY_FOCUS_QUERY_PROMPT
    from .llm import invoke
    from .prompts import EXTRACT_LIMIT_NEW, EXTRACT_LIMIT_OLD

    cfg = config()
    rows = file_table(files)

    def resolve(ref: str) -> dict | None:
        ref = str(ref).strip()
        if ref.isdigit() and 1 <= int(ref) <= len(rows):
            return rows[int(ref) - 1]
        for r in rows:
            if ref in (r["name"], r["path"]) or Path(ref).name == r["name"]:
                return r
        hits = [r for r in rows if ref.lower() in r["name"].lower()]
        return hits[0] if len(hits) == 1 else None

    listing = "; ".join(f"{x['n']}. {x['name']} ({x['parts']} part{'s' if x['parts'] > 1 else ''})" for x in rows)

    @tool(description=(
        "Read one part of one of the user's own files and return the passages relevant to `focus`, quoted (like "
        "fetch_content for a web page; cite what you use by the [N] it returns). `file` is the file's number or "
        f"name, `part` starts at 1. The user's files: {listing}"))
    def read_file(file: str, focus: str, part: int = 1) -> str:
        """Description passed via ``@tool(description=...)`` above."""
        r = resolve(file)
        if r is None:
            return "Unknown file. The files are: " + "; ".join(f"{x['n']}. {x['name']}" for x in rows)
        text = file_text(r["path"])
        ps = pieces(text, cfg.fetch_max_chars)
        try:
            k = int(part or 1)
        except (TypeError, ValueError):
            k = 1
        if not 1 <= k <= len(ps):
            return f"{r['name']} has {len(ps)} part(s); ask for part 1 to {len(ps)}."
        piece = ps[k - 1]
        title = f"{r['name']} (your file, part {k} of {len(ps)})"
        url = f"file://{r['path']}#part={k}"
        prompt = SUMMARY_FOCUS_QUERY_PROMPT.format(focus=focus, title=title, url=url, content=piece,
                                                   overall_query=overall_query)
        prompt = prompt.replace(EXTRACT_LIMIT_OLD, EXTRACT_LIMIT_NEW.format(max_chars=cfg.extract_max_chars))
        summary, _info = invoke(model, prompt, cfg.extract_effort, what=f"file extraction {r['name']}#{k}")
        store = getattr(collector, "deep_store", None)
        more = f"\n\n({r['name']} has {len(ps)} parts; this was part {k}.)" if len(ps) > 1 else ""
        if not summary or summary.strip().upper().startswith("NOT RELEVANT"):
            if store is not None:
                store.add_fetch(None, url, title, focus, piece, "NOT RELEVANT")
            return f"NOT RELEVANT (nothing in {title} matched the focus){more}"
        idx = _register_in_collector(collector, url, title, summary)
        if store is not None:
            store.add_fetch(idx, url, title, focus, piece, summary)
        logger.info(f"deep: read_file {r['name']} part {k}/{len(ps)} -> [{idx}] ({len(summary)} chars)")
        return f"[{idx}] Title: {title}\nURL: {url}\n\n{summary}{more}"

    return read_file
