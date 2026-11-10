#!/usr/bin/env python3
"""make_staged.py - the engine-scope change as exact text edits, applied to a base copy of each file (10-29).

  .venv/bin/python -I -B staging/enginescope/make_staged.py [--base installed|c3|DIR] [--out DIR] [--check]

--base installed (default): the files as installed now -> staging/enginescope/{deep,fetch,strategies}/ (+ *.orig, *.diff)
--base c3: staging/c3's staged copies of report.py, codetool.py and the strategy (c3 installs first) ->
           staging/enginescope/c3-merged/ (+ *.c3.diff); the fetch tool is not in c3 (the installed one is used)
--check:   only say whether every edit applies (each old text found exactly once), write nothing.
Every edit is an exact (old, new) pair; one that does not match stops the run and names it, so a re-run at install time
(after other installs) shows at once whether the change still applies. deep/enginescope.py and deep/engines/strata.json are
new files (copied as they are).
"""
from __future__ import annotations

import argparse
import difflib
import shutil
import sys
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
PKG = WS / ".venv/lib/python3.12/site-packages/local_deep_research"
HERE = WS / "staging/enginescope"
C3 = WS / "staging/c3"

# staged name -> (path in the package, path in staging/c3 or None)
FILES = {
    "deep/codetool.py": ("deep/codetool.py", "deep/codetool.py"),
    "deep/report.py": ("deep/report.py", "deep/report.py"),
    "fetch/__init__.py": ("advanced_search_system/tools/fetch/__init__.py", None),
    "strategies/langgraph_agent_strategy.py": ("advanced_search_system/strategies/langgraph_agent_strategy.py",
                                               "strategies/langgraph_agent_strategy.py"),
}
NEW = ["deep/enginescope.py", "deep/engines/strata.json"]

EDITS: dict[str, list[tuple[str, str]]] = {}

# ---------------------------------------------------------------------------------------------- deep/codetool.py
EDITS["deep/codetool.py"] = [
    ("    (50) and LDR_DEEP_CODE_SEARCH_MAX searches (30), and 10 core calls are always left for other programs.\n",
     "    (50) and LDR_DEEP_CODE_SEARCH_MAX searches (30), and 10 core calls are always left for other programs.\n"
     "\n"
     "10-29 (engine scope, deep/enginescope.py; LDR_DEEP_FIX version): when the task is about one engine of a multi-engine\n"
     "project (Strata's DeepSeek engine), a read of a file or doc part of another engine (Strata's Qwen engine) says so above\n"
     "its lines, and search hits in such files carry [OTHER ENGINE ...]. The evidence keeps the plain text.\n"),
    ('''def make_tools(collector: Any, rid: str, log_dir: str | Path | None = None, task: str = "",
               profile: str = "") -> list:
''', '''def _enginescope():
    """deep/enginescope.py (10-29 engine-scope labels): inside LDR's package, else from its file next to this one (this
    file is also loaded on its own by tools/code-mcp.py); None when it cannot be loaded."""
    try:
        from . import enginescope as es
        return es
    except ImportError:
        import importlib.util
        import sys
        es = sys.modules.get("deep_enginescope")
        if es is None:
            try:
                spec = importlib.util.spec_from_file_location("deep_enginescope",
                                                              Path(__file__).with_name("enginescope.py"))
                es = importlib.util.module_from_spec(spec)
                sys.modules["deep_enginescope"] = es        # (dataclasses need the module registered)
                spec.loader.exec_module(es)
            except (OSError, ImportError, AttributeError):
                sys.modules.pop("deep_enginescope", None)
                return None
        return es


def _file_text(r: Repo, rel: str) -> str | None:
    """A file of a clone as text (the engine-scope labels place a doc by all of it), or None."""
    try:
        p = r._path(rel)
        if not p.is_file() or p.stat().st_size > TEXT_MAX_BYTES:
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except (OSError, CodeToolError):
        return None


def make_tools(collector: Any, rid: str, log_dir: str | Path | None = None, task: str = "",
               profile: str = "") -> list:
'''),
    ('''            store.add_fetch(idx, url, title, focus, text, text)
        return idx
''', '''            store.add_fetch(idx, url, title, focus, text, text)
        return idx

    # 10-29 engine-scope labels (LDR_DEEP_FIX version): a file or doc part of another engine of the task's project
    es = _enginescope()
    verdicts: dict = {}

    def engine_of(r: Repo, rel: str):
        """The engine verdict of one file of a clone (by its path; a doc by all of its text), cached for the run."""
        store = getattr(collector, "deep_store", None)
        if es is None or not es.scopes_of(store):
            return None
        key = (str(r.root), rel)
        if key not in verdicts:
            folder = es.content_dir(None, rel)
            readme = _file_text(r, folder + "README.md") if folder and rel != folder + "README.md" else None
            if readme is not None:             # a config / script / note of a bench run: placed by the run's README
                v = es.classify(r.url(rel), "", readme, es.scopes_of(store), whole=readme, pins=es.pins_of(store))
                verdicts[key] = v if v is not None and v.engine else None
            else:
                whole = _file_text(r, rel) if es._is_doc(rel) or folder else None
                verdicts[key] = es.classify(r.url(rel), "", whole or "", es.scopes_of(store), whole=whole,
                                            pins=es.pins_of(store))
        return verdicts[key]

    def hit_lines(r: Repo, hits: list[dict]) -> tuple[list[str], str]:
        """The search hits as 'file:line: text' - a hit in another engine's file or doc part with [OTHER ENGINE ...] -
        and the legend line ('' when no hit is marked)."""
        out, first, n = [], None, 0
        for h in hits:
            try:
                v = engine_of(r, h["file"])
            except Exception:  # noqa: BLE001 - a label never breaks the search
                v = None
            tag = es.short(v) if v is not None and (v.engine or v.part_at(h["line"])) else ""
            if tag:
                first, n = first or v, n + 1
            out.append(f"{h['file']}:{h['line']}: {tag + ' ' if tag else ''}{h['text']}")
        if first is None:
            return out, ""
        proj, other, own = es._names(first)
        return out, (f"\\n({n} hit(s) marked [OTHER ENGINE: {proj}'s {other}] are in that engine's files or doc parts; "
                     f"the task is about its {own} - not evidence for the {own}'s flags or settings.)")
'''),
    ('''        lines = [f"{h['file']}:{h['line']}: {h['text']}" for h in g["hits"]]
''', '''        lines, legend = hit_lines(r, g["hits"])
'''),
    ('''        return f"{g['total']} hit(s) for /{pattern}/ in {r.label}:\\n" + "\\n".join(lines) + more
''', '''        return f"{g['total']} hit(s) for /{pattern}/ in {r.label}:\\n" + "\\n".join(lines) + more + legend
'''),
    ('''        return f"[{idx}] Title: {title}\\nURL: {d['url']}\\n\\n{d['text']}{rest}"
''', '''        text, label = d["text"], ""
        try:                                   # 10-29: another engine's file or doc part (the evidence keeps the text)
            v = engine_of(r, d["file"])
            n = es.note(v, (d["start"], d["end"])) if v is not None else ""
            if n:
                label, text = f"[{n}]\\n", es.mark_lines(text, v)
        except Exception:  # noqa: BLE001 - a label never breaks the read
            pass
        return f"[{idx}] Title: {title}\\nURL: {d['url']}\\n{label}\\n{text}{rest}"
'''),
    ('''                idx = cite(i["url"], title, text, query or title)
                return f"[{idx}] Title: {title}\\nURL: {i['url']}\\n\\n{text}"
''', '''                idx = cite(i["url"], title, text, query or title)
                label = ""
                try:                           # 10-29: an issue / PR about another engine of the task's project
                    v = es.for_source(getattr(collector, "deep_store", None), i["url"], title, text) if es else None
                    label = f"[{es.note(v)}]\\n" if v is not None and es.note(v) else ""
                except Exception:  # noqa: BLE001
                    label = ""
                return f"[{idx}] Title: {title}\\nURL: {i['url']}\\n{label}\\n{text}"
'''),
]

# ---------------------------------------------------------------------------------------------- deep/report.py
EDITS["deep/report.py"] = [
    ('''        for fix, rule in FIX_OPENING_RULES:
            if checks.fix_on(fix):
                self.p_opening += "\\n" + rule
''', '''        for fix, rule in FIX_OPENING_RULES:
            if checks.fix_on(fix):
                self.p_opening += "\\n" + rule
        # 10-29 engine scope (with the version labels): the task is about one engine of a multi-engine project - its
        # sources about another engine are marked [OTHER ENGINE ...] and the sections get one rule line
        if checks.fix_on("version"):
            from . import enginescope
            if enginescope.scopes_of(store, query):
                self.p_section += "\\n" + enginescope.SECTION_RULE
'''),
    ('''    def _extractions(self, s: Source) -> str:
        if checks.fix_on("claims") and getattr(s, "claims", None):
''', '''    def _extractions(self, s: Source) -> str:
        return self._engine_quotes(s, self._extractions_plain(s))

    def _extractions_plain(self, s: Source) -> str:
        if checks.fix_on("claims") and getattr(s, "claims", None):
'''),
    ('''    def _label(self, s: Source) -> str:
        """'[N] title (url)', with the page's date and, for a primary source, the page it was found from (item 6)."""
        extra = (f", dated {s.date}" if getattr(s, "date", "") else "") + (
            f"; primary source behind [{s.via}]" if getattr(s, "via", None) is not None else "")
        note = self._version_note(s)
        return f"[{s.idx}] {'[' + note + '] ' if note else ''}{s.title[:100]} ({s.url}{extra})"
''', '''    def _engine_note(self, s: Source) -> str:
        """10-29 (engine scope, with the version labels): a source about another engine of the task's project - by its
        path, or by its words (a mixed page: the parts that are) - says so, next to the version note."""
        if not checks.fix_on("version"):
            return ""
        from .enginescope import writer_note
        return writer_note(self.store, s)

    def _engine_quotes(self, s: Source, text: str, paragraphs: bool = False) -> str:
        """Quotes (or, with paragraphs, passages) from another engine's part of a mixed page, marked."""
        if not text or not checks.fix_on("version"):
            return text
        from .enginescope import writer_quotes
        return writer_quotes(self.store, s, text, paragraphs=paragraphs)

    def _label(self, s: Source) -> str:
        """'[N] title (url)', with the page's date and, for a primary source, the page it was found from (item 6)."""
        extra = (f", dated {s.date}" if getattr(s, "date", "") else "") + (
            f"; primary source behind [{s.via}]" if getattr(s, "via", None) is not None else "")
        note = self._version_note(s)
        eng = self._engine_note(s)
        return (f"[{s.idx}] {'[' + note + '] ' if note else ''}{'[' + eng + '] ' if eng else ''}{s.title[:100]} "
                f"({s.url}{extra})")
'''),
    ('''                extra = relevant_passages(s.page_text, qw, per)
''', '''                extra = self._engine_quotes(s, relevant_passages(s.page_text, qw, per), paragraphs=True)
'''),
    ('''                note = self._version_note(s)
                label += f"; {note}" if note else ""
''', '''                note = self._version_note(s)
                label += f"; {note}" if note else ""
                eng = self._engine_note(s)
                label += f"; {eng}" if eng else ""
'''),
]

# ---------------------------------------------------------------------------------------------- the fetch tool
EDITS["fetch/__init__.py"] = [
    ('''def _scrub_tool_error(message: str) -> str:
''', '''def _engine_output(collector: Any, idx: Any, url: str, title: str, page: str, body: str, full: bool = False):
    """10-29 engine-scope labels (deep/enginescope.py, LDR_DEEP_FIX version): the answer with [OTHER ENGINE ...] when
    the page - or parts of it - describe another engine of the task's project; None otherwise (the caller's own
    answer stands). The evidence keeps the plain page and extraction."""
    store = getattr(collector, "deep_store", None)
    if store is None:
        return None
    try:
        from ....deep import enginescope as _es

        return _es.fetch_output(store, idx, url, title, page, body, full=full)
    except Exception:  # noqa: BLE001 - a label never breaks a fetch
        logger.exception("deep: engine-scope label failed")
        return None


def _scrub_tool_error(message: str) -> str:
'''),
    ('''                cite_idx = _register_in_collector(
                    collector, url, title, content
                )
                return f"[{cite_idx}] Title: {title}\\nURL: {url}\\n\\n{content}"
''', '''                cite_idx = _register_in_collector(
                    collector, url, title, content
                )
                return _engine_output(collector, cite_idx, url, title, content, content, full=True) or (
                    f"[{cite_idx}] Title: {title}\\nURL: {url}\\n\\n{content}")
'''),
    ('''            if _store is not None:
                _store.add_fetch(cite_idx, url, title, focus, content, summary)
            return f"[{cite_idx}] Title: {title}\\nURL: {url}\\n\\n{summary}"
''', '''            if _store is not None:
                _store.add_fetch(cite_idx, url, title, focus, content, summary)
            return _engine_output(collector, cite_idx, url, title, content, summary) or (
                f"[{cite_idx}] Title: {title}\\nURL: {url}\\n\\n{summary}")
'''),
]

# ---------------------------------------------------------------------------------------------- the strategy
EDITS["strategies/langgraph_agent_strategy.py"] = [
    ('''def _make_web_search_tool(
''', '''def _deep_engine_titles(store: Any, results: list) -> list:
    """10-29 engine-scope labels (deep/enginescope.py, LDR_DEEP_FIX version): search results whose page is placed in
    another engine of the task's project (a GitHub path, or a snippet with clear markers) get [OTHER ENGINE ...] ahead
    of their title - copies only; the collector and the evidence keep the plain titles."""
    try:
        from ...deep import enginescope as _es

        if not _es.scopes_of(store):
            return results
        out = []
        for r in results:
            if isinstance(r, dict):
                t = r.get("title", "No title")
                t2 = _es.search_title(store, r.get("link", r.get("url", "")), t, r.get("snippet", r.get("body", "")) or "")
                r = dict(r, title=t2) if t2 != t else r
            out.append(r)
        return out
    except Exception:  # noqa: BLE001 - a label never breaks a search
        logger.exception("deep: engine-scope search labels failed")
        return results


def _make_web_search_tool(
'''),
    ('''            if _store is not None:
                _store.add_search(query, indexed, engine=search_engine_name)
            return _format_results(indexed, start)
''', '''            if _store is not None:
                _store.add_search(query, indexed, engine=search_engine_name)
                indexed = _deep_engine_titles(_store, indexed)
            return _format_results(indexed, start)
'''),
    ('''            subagent_prompt = _DEEP_SUBAGENT_PROMPT.format(date=current_date)
''', '''            from ...deep.enginescope import prompt_rule as _deep_engine_rule

            # 10-29: one engine-scope rule line when the task is about one engine of a multi-engine project
            subagent_prompt = _DEEP_SUBAGENT_PROMPT.format(date=current_date) + _deep_engine_rule(
                getattr(collector, "deep_store", None))
'''),
    ('''            if getattr(self, "deep_seed", None) is not None:
                from ...deep.seed import lead_addendum
''', '''            # 10-29: the engine scope (LDR_DEEP_FIX version) - one rule line when the task is about one engine of a
            # multi-engine project (Strata's DeepSeek engine); tool results mark the other engine's sources
            from ...deep.enginescope import prompt_rule as _deep_engine_rule

            system_prompt += _deep_engine_rule(self.deep_store)
            if getattr(self, "deep_seed", None) is not None:
                from ...deep.seed import lead_addendum
'''),
]


def apply(text: str, edits: list[tuple[str, str]], name: str) -> str:
    for k, (old, new) in enumerate(edits, 1):
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"{name}: edit {k} matches {n} times (needs exactly 1): {old.strip()[:90]!r}")
        text = text.replace(old, new)
    return text


def udiff(a: str, b: str, fa: str, fb: str) -> str:
    return "".join(difflib.unified_diff(a.splitlines(keepends=True), b.splitlines(keepends=True), fa, fb, n=3))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="installed")
    ap.add_argument("--out", default="")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    out = Path(a.out) if a.out else (HERE if a.base == "installed" else HERE / f"{a.base}-merged")
    for name, (pkg_rel, c3_rel) in FILES.items():
        if a.base == "installed":
            base = PKG / pkg_rel
        elif a.base == "c3":
            base = C3 / c3_rel if c3_rel else PKG / pkg_rel
        else:
            base = Path(a.base) / name
        old = base.read_text(encoding="utf-8")
        new = apply(old, EDITS[name], f"{name} ({base})")
        print(f"{name}: {len(EDITS[name])} edits apply to {base}")
        if a.check:
            continue
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base, dest.with_name(dest.name + ".orig"))
        dest.write_text(new, encoding="utf-8")
        tag = "" if a.base == "installed" else f".{a.base}"
        (out / (name + tag + ".diff")).write_text(udiff(old, new, f"a/local_deep_research/{pkg_rel}", f"b/local_deep_research/{pkg_rel}"), encoding="utf-8")
    if not a.check and out != HERE:
        for n in NEW:
            (out / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / n, out / n)
    if not a.check:
        for n in NEW:                      # the new files' diff against nothing (for the record)
            src = (HERE / n).read_text(encoding="utf-8")
            (HERE / (n + ".diff")).write_text(udiff("", src, "/dev/null", f"b/local_deep_research/{n}"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
