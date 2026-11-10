"""Engine-scope labels (10-29, Karl: the second 10-24 rerun's wrong-engine settings).

When the task is about ONE engine of a multi-engine project - e.g. Strata's DeepSeek-V4.1 engine (strata-dsv41) - a
source or a section of a source that describes ANOTHER engine of that project (Strata's Qwen engine) is labelled where
the model reads it: in the fetch tool's output, in the code tool's read and search output, in search results and in
the writers' source labels, next to the version note. The run-full-bundle-verpin trace: --pcie-frac, --adapt-every,
--trim-stage-weights, --vram-reserve-mib, STRATA_IO_THREADS, STRATA_UNBUFFERED_LOAD and --layer-split 22 came into the
lead's answer from pages pinned at the RIGHT version (v0.2.4) that describe the Qwen engine (docs/MULTI_GPU.md, the
community RTX 5080 benchmark) - the version labels cannot catch those.

  * Which engine the task is about (task_scopes): per project of deep/engines/<project>.json that the task (or else the
    setup profile) names, the engine whose task markers the task names - from the task text; from the setup profile
    only when the task names none. No label when no engine or several are named.
  * Which engine a source is about (classify): a GitHub page of the project by its path (the table's engine folders and
    doc files, per version - folders_by_version, picked by the user's pinned version (the version labels' pins): the
    newest entry at or below it, else the conservative base map; shared folders - kernels, serve, the launcher, and
    core / platform where that version links them into the task's engine - are never another engine; other code
    files: no label); docs, bench results, release notes, issues and pages on other sites by marker counts (model names, engine
    names, setting prefixes) with a clear margin (another engine's >= 3 and >= 8x the task engine's). A page naming
    both engines is labelled per section (split on its markdown headings; a section with weak or no markers takes its
    parent heading's verdict). A bench run's config / script is placed by its run's README. Other projects: no label.
  * Off unless LDR_DEEP_FIX has "version" (the same switch as the version labels). Standard library only.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TABLE_DIR = Path(__file__).with_name("engines")      # one <project>.json per project

PAGE_MIN = 3            # another engine's markers on a page before the whole page is labelled
PAGE_RATIO = 8          # ... and at least this many times the task's engine's (else: per section)
SEC_MIN = 2             # the same for one section of a mixed page
SEC_RATIO = 3
PROJECT_MENTIONS = 3    # a page on another site is about the project: its name this often (title counts 3 times)
QUOTE_MIN = 20          # a quote shorter than this is not placed in the page

_TABLE: dict | None = None


def table() -> dict:
    """Project key -> its table (deep/engines/<project>.json), read once."""
    global _TABLE
    if _TABLE is None:
        _TABLE = {}
        for f in sorted(TABLE_DIR.glob("*.json")) if TABLE_DIR.is_dir() else []:
            try:
                _TABLE[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return _TABLE


def on() -> bool:
    """The version labels' switch: LDR_DEEP_FIX has "version" (or "all")."""
    try:
        from .checks import fix_on
        return fix_on("version")
    except ImportError:                       # loaded straight from its file (tests, tools)
        v = {x.strip().lower() for x in os.environ.get("LDR_DEEP_FIX", "").split(",") if x.strip()}
        return "version" in v or "all" in v


# ------------------------------------------------------------------------------------------------ markers
_RX: dict[tuple[str, str], list[re.Pattern]] = {}


def _rx(project: str, engine: str, kind: str = "markers") -> list[re.Pattern]:
    key = (project, engine + ":" + kind)
    if key not in _RX:
        e = table()[project]["engines"][engine]
        if kind == "task":
            _RX[key] = [re.compile(p, re.I) for p in e.get("task_markers", [])]
        else:
            _RX[key] = ([re.compile(p, re.I) for p in e.get("markers", [])]
                        + [re.compile(p) for p in e.get("markers_cs", [])])
    return _RX[key]


def counts(text: str, project: str) -> dict[str, int]:
    """Marker hits of each engine of the project in text."""
    return {eng: sum(len(rx.findall(text or "")) for rx in _rx(project, eng))
            for eng in table()[project]["engines"]}


def _named(text: str, project: str) -> list[str]:
    return [eng for eng in table()[project]["engines"]
            if any(rx.search(text or "") for rx in _rx(project, eng, "task"))]


def _project_named(text: str, p: dict) -> bool:
    t = text or ""
    if re.search(p.get("name_re") or r"$^", t, re.I):         # a task may write "strata"
        return True
    low = t.lower()
    return any(r.lower() in low for r in p.get("repos", []))


# ------------------------------------------------------------------------------------------------ the task's engine
def task_scopes(task: str, profile: str = "") -> dict[str, str]:
    """Project key -> the engine the task is about, for each known project the task (or else the profile) names. The
    engine comes from the task; from the profile only when the task names none of the project's engines. None or
    several named: no entry (no labels for that project)."""
    out: dict[str, str] = {}
    for key, p in table().items():
        if not (_project_named(task, p) or _project_named(profile, p)):
            continue
        engs = _named(task, key)
        if not engs and profile:
            engs = _named(profile, key)
        if len(engs) == 1:
            out[key] = engs[0]
    return out


def _profile_text() -> str:
    try:
        from .setup import profile_path, setup_facts
        path = profile_path()
        return setup_facts(path) if path else ""
    except Exception:  # noqa: BLE001 - outside the package, or no profile
        return ""


def _derive_pins(task: str, profile: str) -> dict[str, str]:
    """The version labels' pins (codetool.derive_pins: the task's versions, else the profile's single one)."""
    try:
        from .codetool import derive_pins
    except ImportError:                       # loaded on its own (tests, tools): no pins, the conservative folder map
        return {}
    try:
        return derive_pins(task or "", profile or "")
    except Exception:  # noqa: BLE001
        return {}


def scopes_of(store: Any, task: str | None = None) -> dict[str, str]:
    """The task's engines for one research, computed once (from `task`, else the store's task, and the setup profile)
    and kept on the store, with the pinned versions that pick the folder map (pins_of); {} when the switch is off."""
    if store is None or not on():
        return {}
    sc = getattr(store, "engine_scopes", None)
    if sc is None:
        t, prof = task if task is not None else (getattr(store, "query", "") or ""), _profile_text()
        sc = task_scopes(t, prof)
        try:
            store.engine_scopes = sc
            if getattr(store, "engine_pins", None) is None:
                store.engine_pins = _derive_pins(t, prof)
        except AttributeError:
            pass
    return sc


def pins_of(store: Any) -> dict[str, str]:
    """Project name (lower case) -> the version the user runs: the version labels' pins on the store (the code tool /
    the replay set them), else the same derive_pins on the task and the profile."""
    pins = getattr(store, "pins", None)
    if pins:
        return pins
    pins = getattr(store, "engine_pins", None)
    if pins is None:
        pins = _derive_pins(getattr(store, "query", "") or "", _profile_text())
        try:
            store.engine_pins = pins
        except AttributeError:
            pass
    return pins or {}


# ------------------------------------------------------------------------------------------------ where a page is
GH_RE = re.compile(r"https?://(?:www\.)?(github\.com|raw\.githubusercontent\.com)/([A-Za-z0-9][A-Za-z0-9-]{0,38})/"
                   r"([A-Za-z0-9._-]{1,100})(?:/([^?#]*))?", re.I)


def gh_parse(url: str) -> tuple[str, str, str] | None:
    """(repo name lower case, kind, path inside the repo) of a GitHub URL; kind 'file' (blob / raw / blame), 'tree',
    'other' (issues, releases, the repo root, ...); None for other sites."""
    m = GH_RE.match(url or "")
    if not m:
        return None
    name = m.group(3).removesuffix(".git").lower()
    parts = [p for p in (m.group(4) or "").split("/") if p]
    if m.group(1).lower().startswith("raw."):
        return name, "file", "/".join(parts[1:])
    if len(parts) > 2 and parts[0] in ("blob", "raw", "blame"):
        return name, "file", "/".join(parts[2:])
    if len(parts) > 1 and parts[0] == "tree":
        return name, "tree", "/".join(parts[2:])
    return name, "other", "/".join(parts)


def project_of(url: str, title: str = "", text: str = "") -> str | None:
    """The known project a page is about: a GitHub URL by its repo name (another repo: None, even when it names the
    project - a fork or a related project is not labelled); another site by the project's repo path in the URL or the
    project's name on the page."""
    gh = gh_parse(url)
    if gh is None and re.match(r"https?://(?:www\.)?github\.com(?:/|$)", url or "", re.I):
        return None                        # github.com search, topics, an account: lists of repos, not a project page
    for key, p in table().items():
        names = {n.lower() for n in p.get("repo_names", [])}
        if gh is not None:
            if gh[0] in names:
                return key
            continue
        low = (url or "").lower()
        if any(r.lower() in low for r in p.get("repos", [])):
            return key
        rx = re.compile(p.get("name_re") or r"$^")
        if 3 * len(rx.findall(title or "")) + len(rx.findall(text or "")) >= PROJECT_MENTIONS:
            return key
    return None


def _under(path: str, f: str) -> bool:
    return (path.startswith(f) or path == f.rstrip("/")) if f.endswith("/") else path == f


def _ver(v: str | None) -> tuple | None:
    m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?$", (v or "").strip())
    return tuple(int(x or 0) for x in m.groups()) if m else None


def version_entry(project: str, version: str | None) -> tuple[str, dict] | None:
    """(tag, entry) of the table's folders_by_version for the user's version: the newest entry at or below it. None for
    no pin, an unparseable one or one below every entry - the base map (the conservative one) applies."""
    want = _ver(version)
    if want is None:
        return None
    entries = [(_ver(k), k, e) for k, e in (table()[project].get("folders_by_version") or {}).items()
               if not k.startswith("_") and _ver(k) is not None]
    below = [x for x in entries if x[0] <= want]
    if not below:
        return None
    _v, tag, entry = max(below, key=lambda x: x[0])
    return tag, entry


def project_version(project: str, pins: dict[str, str] | None) -> str | None:
    p = table()[project]
    for n in [project] + list(p.get("repo_names", [])):
        if pins and pins.get(n.lower()):
            return pins[n.lower()]
    return None


def path_engine(project: str, path: str, version: str | None = None) -> str | None:
    """'<engine>' for a path in an engine's folders or doc files, 'shared' for a shared folder or file, None otherwise;
    the longest matching entry wins (tools/dsv41/ over tools/). The folder map is the one for the user's version
    (version_entry: its folders replace the same base entries); without one, the base (conservative) map."""
    p = table()[project]
    path = (path or "").lstrip("/")
    ve = version_entry(project, version)
    moved = set()
    extra: list[tuple[str, str]] = []
    if ve is not None:
        for eng, folders in ve[1].items():
            if eng in p["engines"] or eng == "shared":
                extra += [(f, eng) for f in folders]
                moved |= set(folders)
    cands = [(f, eng) for eng, e in p["engines"].items() for f in e.get("folders", []) + e.get("docs", [])
             if f not in moved]
    cands += [(f, "shared") for f in p.get("shared", []) if f not in moved]
    cands += extra
    hits = [(len(f), eng) for f, eng in cands if _under(path, f)]
    return max(hits)[1] if hits else None


DOC_EXT = (".md", ".markdown", ".rst", ".txt", ".adoc")


def content_dir(project: str | None, path: str) -> str | None:
    """The folder (e.g. 'bench/results/<run>/') when `path` is in one of the table's content_dirs - every text file there
    is placed by its words, by the folder's README.md when the caller has it; None otherwise. project None: any
    project's table."""
    path = (path or "").lstrip("/")
    for key, p in table().items():
        if project is not None and key != project:
            continue
        for pat in p.get("content_dirs", []):
            rx = "^" + re.escape(pat.rstrip("/")).replace(r"\*", "[^/]+") + "/"
            m = re.match(rx, path)
            if m:
                return m.group(0)
    return None


def _is_doc(path: str) -> bool:
    low = (path or "").lower().rstrip("/")
    return low.endswith(DOC_EXT) or low.rsplit("/", 1)[-1] in ("readme", "changelog", "news")


# ------------------------------------------------------------------------------------------------ sections
NUM_RE = re.compile(r"^(\d+): ?(.*)$")
HEAD_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(\S.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")


def numbered(text: str) -> bool:
    """The code tool's numbered lines ("123: ...")?"""
    nonempty = [ln for ln in (text or "").splitlines() if ln.strip()]
    return bool(nonempty) and sum(1 for ln in nonempty if NUM_RE.match(ln)) >= 0.8 * len(nonempty)


def lines_of(text: str) -> list[tuple[int, str]]:
    """(line number, text) of every line; the code tool's numbered lines keep their numbers (a line without one gets
    the number before it)."""
    num = numbered(text)
    out: list[tuple[int, str]] = []
    for i, ln in enumerate((text or "").splitlines(), 1):
        m = NUM_RE.match(ln) if num else None
        if m:
            out.append((int(m.group(1)), m.group(2)))
        else:
            out.append((out[-1][0] if (num and out) else i, ln))
    return out


def line_range(text: str) -> tuple[int, int] | None:
    """(first, last) line number of the code tool's numbered lines; None for other text."""
    if not numbered(text):
        return None
    ls = lines_of(text)
    return (ls[0][0], ls[-1][0]) if ls else None


@dataclass
class Section:
    start: int                    # first line number
    end: int                      # last line number
    heading: str                  # "" for the lines before the first heading
    level: int                    # 1-6; 0 before the first heading
    counts: dict[str, int] = field(default_factory=dict)
    engine: str | None = None     # the engine it is about (by its own markers or its parent's), or None


def sections(text: str, project: str) -> list[Section]:
    """Markdown sections (headings outside code fences), each with its marker counts (heading included)."""
    secs: list[Section] = []
    cur = Section(0, 0, "", 0)
    body: list[str] = []
    fence = False
    lines = lines_of(text)
    for num, ln in lines:
        if FENCE_RE.match(ln):
            fence = not fence
        m = None if fence else HEAD_RE.match(ln)
        if m:
            if body or cur.heading:
                cur.counts = counts("\n".join(body), project)
                secs.append(cur)
            cur = Section(num, num, ("#" * len(m.group(1))) + " " + m.group(2)[:80], len(m.group(1)))
            body = [ln]
        else:
            if not body and not cur.heading:
                cur.start = num
            body.append(ln)
        cur.end = num
    if body or cur.heading:
        cur.counts = counts("\n".join(body), project)
        secs.append(cur)
    return secs


def _verdict(c: dict[str, int], task_eng: str, mn: int, ratio: int) -> str | None:
    """The engine a block of text is about: another engine (at least `mn` of its markers and `ratio` times the task
    engine's), the task's engine (the same margin the other way, or only its markers), or None (mixed / too few)."""
    own = c.get(task_eng, 0)
    others = sorted(((n, e) for e, n in c.items() if e != task_eng), reverse=True)
    top, eng = others[0] if others else (0, None)
    if top >= mn and top >= ratio * own:
        return eng
    if (own >= mn and own >= ratio * top) or (own and not top):
        return task_eng
    return None


# ------------------------------------------------------------------------------------------------ the verdict
@dataclass
class Verdict:
    project: str
    task_engine: str
    engine: str | None = None             # the other engine, when the whole page / file is about it
    how: str = ""                         # "folder", "doc file", "content", "sections"
    path: str = ""
    parts: list[Section] = field(default_factory=list)   # mixed page: its sections about another engine
    at: str = ""                          # the folder map's version, when it (not the base map) placed the file

    @property
    def labelled(self) -> bool:
        return bool(self.engine or self.parts)

    def other_engine(self) -> str:
        return self.engine or (self.parts[0].engine if self.parts else "")

    def part_at(self, line: int) -> Section | None:
        for s in self.parts:
            if s.start <= line <= s.end:
                return s
        return None


def classify(url: str, title: str = "", text: str = "", scopes: dict[str, str] | None = None,
             whole: str | None = None, pins: dict[str, str] | None = None) -> Verdict | None:
    """Which engine a source describes, when the task is about another engine of the same project; None otherwise.
    `text` is what was read (a page, an extraction's page, the code tool's numbered lines); `whole` the whole file when
    the code tool has it (it decides the page and its sections; the line numbers then match the code tool's); `pins`
    the user's versions (the folder map of that version; none: the conservative map)."""
    if not scopes:
        return None
    proj = project_of(url, title, text or whole or "")
    if proj is None or proj not in scopes:
        return None
    task_eng = scopes[proj]
    gh = gh_parse(url)
    if gh is not None and gh[2] and gh[1] in ("file", "tree"):
        version = project_version(proj, pins)
        where = path_engine(proj, gh[2], version)
        if where == "shared":
            return None
        if where is not None:
            if where == task_eng:
                return None
            how = "doc file" if gh[2] in table()[proj]["engines"][where].get("docs", []) else "folder"
            ve = version_entry(proj, version)
            at = ve[0] if ve is not None and path_engine(proj, gh[2], None) != where else ""
            return Verdict(proj, task_eng, engine=where, how=how, path=gh[2], at=at)
        if gh[1] == "tree" or not (_is_doc(gh[2]) or content_dir(proj, gh[2])):
            return None                   # code outside the engine folders: not placed by its words
    body = whole if whole is not None else text
    flat = "\n".join(t for _, t in lines_of(body))
    page = _verdict(counts((title or "") + "\n" + flat, proj), task_eng, PAGE_MIN, PAGE_RATIO)
    if page is not None and page != task_eng:
        return Verdict(proj, task_eng, engine=page, how="content", path=gh[2] if gh else "")
    c = counts(flat, proj)
    if page == task_eng or not c.get(task_eng) or not any(n for e, n in c.items() if e != task_eng):
        return None                       # the task's engine's page, or too few markers: no label
    secs = sections(body, proj)           # mixed (both engines named): per section
    if len(secs) < 2:
        return None
    # a page with one top heading (its title) is not one section about an engine: its verdict is not inherited
    title_head = [s for s in secs if s.level == 1]
    title_head = title_head[0] if len(title_head) == 1 and title_head[0] is next(
        (s for s in secs if s.level > 0), None) else None
    stack: list[Section] = []
    parts = []
    for s in secs:
        while stack and stack[-1].level >= s.level and s.level > 0:
            stack.pop()
        own = _verdict(s.counts, task_eng, SEC_MIN, SEC_RATIO)
        if own is None and not s.counts.get(task_eng):
            own = next((p.engine for p in reversed(stack) if p.engine and p is not title_head), None)  # the parent's
        s.engine = own
        if s.level > 0:
            stack.append(s)
        if own is not None and own != task_eng:
            parts.append(s)
    if not parts:
        return None
    return Verdict(proj, task_eng, how="sections", path=gh[2] if gh else "", parts=parts)


# ------------------------------------------------------------------------------------------------ the labels
def _names(v: Verdict) -> tuple[str, str, str]:
    p = table()[v.project]
    other = p["engines"][v.other_engine()]["label"]
    own = p["engines"][v.task_engine]["label"]
    return p.get("name") or v.project, other, own


def note(v: Verdict | None, lines: tuple[int, int] | None = None) -> str:
    """The label's text (without brackets). `lines`: the line range that was read - a mixed page then names only the
    sections in that range (none there: '')."""
    if v is None or not v.labelled:
        return ""
    proj, other, own = _names(v)
    tail = (f"the task is about its {own} - its flags, settings and numbers are not the {own}'s unless that engine's "
            f"code shows them")
    if v.engine:
        what = "file is part of" if v.how == "folder" else "page describes"
        return f"OTHER ENGINE: this {what} {proj}'s {other}{' at ' + v.at if v.at else ''}; {tail}"
    parts = v.parts
    if lines is not None:
        parts = [s for s in parts if s.start <= lines[1] and s.end >= lines[0]]
        if not parts:
            return ""
    shown = ", ".join(f'"{s.heading}"' + (f" (lines {s.start}-{s.end})" if lines is not None else "")
                      if s.heading else f"lines {s.start}-{s.end}" for s in parts[:6])
    more = f" and {len(parts) - 6} more" if len(parts) > 6 else ""
    return (f"PARTLY OTHER ENGINE: the parts {shown}{more} of this page describe {proj}'s {other}; the task is about "
            f"its {own} - flags, settings and numbers from those parts are not the {own}'s unless that engine's code "
            f"shows them; quotes from them are marked [OTHER ENGINE]")


def short(v: Verdict | None) -> str:
    """A short mark for one line (a search hit, a quote): '[OTHER ENGINE: Strata's Qwen engine]'."""
    if v is None or not v.labelled:
        return ""
    proj, other, _own = _names(v)
    return f"[OTHER ENGINE: {proj}'s {other}]"


def _norm(s: str) -> tuple[str, list[int]]:
    """Lower case, whitespace and markdown marks collapsed; with the map back to positions in s."""
    out, pos = [], []
    sp = True
    for i, ch in enumerate(s or ""):
        if ch.isspace() or ch in "*`_>|#":
            if not sp:
                out.append(" ")
                pos.append(i)
                sp = True
            continue
        out.append(ch.lower())
        pos.append(i)
        sp = False
    return "".join(out), pos


def _strip_numbers(text: str) -> str:
    return "\n".join(t for _, t in lines_of(text))


def locate(quote: str, page: str, _cache: dict | None = None) -> int | None:
    """The line number (as lines_of numbers it) of the page line where a quote starts, or None."""
    q = re.sub(r"^\s*(?:[-*•>]\s*)?(?:\d+:\s*)?", "", quote or "").strip().strip("\"“”'").strip()
    q = re.sub(r"\s+\((?:\d{4}-\d\d(?:-\d\d)?|undated)[^)]*\)\s*$", "", q).strip().strip("\"“”'")
    qn = _norm(_strip_numbers(q))[0].strip(" .")
    if len(qn) < QUOTE_MIN:
        return None
    key = id(page)
    if _cache is not None and key in _cache:
        flat, starts, nums, norm, pos = _cache[key]
    else:
        ls = lines_of(page)
        flat_parts, starts, nums, off = [], [], [], 0
        for num, t in ls:
            starts.append(off)
            nums.append(num)
            flat_parts.append(t)
            off += len(t) + 1
        flat = "\n".join(flat_parts)
        norm, pos = _norm(flat)
        if _cache is not None:
            _cache[key] = (flat, starts, nums, norm, pos)
    p = norm.find(qn)
    if p < 0:
        words = qn.split(" ")
        if len(words) < 8:
            return None
        p = norm.find(" ".join(words[:5]))
        if p < 0:
            p = norm.find(" ".join(words[-5:]))
        if p < 0:
            return None
    at = pos[p]
    lo, hi = 0, len(starts) - 1
    while lo < hi:                       # the last line starting at or before `at`
        mid = (lo + hi + 1) // 2
        if starts[mid] <= at:
            lo = mid
        else:
            hi = mid - 1
    return nums[lo]


def mark_quotes(body: str, page: str, v: Verdict | None, paragraphs: bool = False) -> str:
    """An extraction / quote list with [OTHER ENGINE ...] on each line that comes from a marked part of a mixed page;
    with `paragraphs` (page passages) on the first line of each paragraph that does."""
    if v is None or not v.parts or not body:
        return body
    tag = short(v) + " "
    cache: dict = {}
    if paragraphs:
        chunks = re.split(r"(\n\s*\n)", body)          # paragraphs at even places, their separators kept between
        for k in range(0, len(chunks), 2):
            n = next((x for x in (locate(ln, page, cache) for ln in chunks[k].splitlines() if ln.strip())
                      if x is not None), None)
            if n is not None and v.part_at(n):
                chunks[k] = tag + chunks[k]
        return "".join(chunks)
    out = []
    for ln in body.splitlines():
        n = locate(ln, page, cache) if ln.strip() else None
        sec = v.part_at(n) if n is not None else None
        if sec is not None:
            m = re.match(r"^(\s*(?:[-*•]\s+)?)", ln)
            ln = ln[:m.end()] + tag + ln[m.end():]
        out.append(ln)
    return "\n".join(out)


def mark_lines(text: str, v: Verdict | None) -> str:
    """The code tool's numbered lines (or a page's text) with a line before each marked part and after its end."""
    if v is None or not v.parts or not text:
        return text
    out = []
    inside = None
    for num, ln in zip((n for n, _ in lines_of(text)), text.splitlines()):
        sec = v.part_at(num)
        if sec is not None and sec is not inside:
            proj, other, _own = _names(v)
            out.append(f"[OTHER ENGINE from here (line {num}, part {sec.heading or 'before the first heading'}): "
                       f"{proj}'s {other}]")
        elif sec is None and inside is not None:
            out.append("[end of the OTHER ENGINE part]")
        inside = sec
        out.append(ln)
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ the call sites
def for_source(store: Any, url: str, title: str = "", text: str = "", whole: str | None = None) -> Verdict | None:
    """classify() with the store's task engines; cached per (url, text) on the store (the writers label every source
    in every prompt)."""
    sc = scopes_of(store)
    if not sc:
        return None
    src = whole if whole is not None else text
    key = (url, title, len(src or ""), (src or "")[:120], whole is not None)
    cache = getattr(store, "_engine_cache", None)
    if cache is None:
        cache = {}
        try:
            store._engine_cache = cache
        except AttributeError:
            pass
    if key not in cache:
        cache[key] = classify(url, title, text, sc, whole=whole, pins=pins_of(store))
    return cache[key]


def fetch_output(store: Any, idx: Any, url: str, title: str, page: str, body: str, full: bool = False) -> str | None:
    """The fetch tool's answer with its labels, or None when there is none (the caller's own string stands). `full`:
    the body is the page itself (full mode), else an extraction from it."""
    v = for_source(store, url, title, page)
    n = note(v)
    if not n:
        return None
    body = mark_lines(body, v) if full else mark_quotes(body, page, v)
    return f"[{idx}] Title: {title}\nURL: {url}\n[{n}]\n\n{body}"


def file_text(store: Any, url: str) -> str | None:
    """A code-tool file as far as the research read it: every range of that file in the evidence, merged by line
    number (numbered lines). The writers place a range by the whole of what was read of its file - the same in a live
    run and a replay (no clone is opened or read here). None for other links or a single range."""
    base = (url or "").split("#", 1)[0]
    if "/blob/" not in base or getattr(store, "sources", None) is None:
        return None
    idx = getattr(store, "_engine_files", None)
    n = len(store.sources)
    if idx is None or idx[0] != n:
        files: dict[str, list] = {}
        for src in list(store.sources.values()):
            u = (getattr(src, "url", "") or "").split("#", 1)[0]
            if "/blob/" in u and numbered(getattr(src, "page_text", "") or ""):
                files.setdefault(u, []).append(src.page_text)
        idx = (n, files)
        try:
            store._engine_files = idx
        except AttributeError:
            pass
    texts = idx[1].get(base) or []
    if len(texts) < 2:
        return None
    merged: dict[int, str] = {}
    for t in texts:
        for num, ln in lines_of(t):
            merged.setdefault(num, ln)
    return "\n".join(f"{k}: {merged[k]}" for k in sorted(merged))


def writer_note(store: Any, s: Any) -> str:
    """The writers' label of a source (ahead of its title, next to the version note); '' when none."""
    page = getattr(s, "page_text", "") or ""
    v = for_source(store, s.url, getattr(s, "title", ""), page, whole=file_text(store, s.url))
    return note(v, line_range(page)) if v is not None else ""


def writer_quotes(store: Any, s: Any, body: str, paragraphs: bool = False) -> str:
    """A source's extraction / checked quotes (or, with paragraphs, page passages) with [OTHER ENGINE ...] on what
    comes from the marked parts of a mixed page."""
    page = getattr(s, "page_text", "") or ""
    if not body or not page:
        return body
    v = for_source(store, s.url, getattr(s, "title", ""), page, whole=file_text(store, s.url))
    if v is None or not v.parts:
        return body
    return mark_quotes(body, page, v, paragraphs=paragraphs)


def search_title(store: Any, url: str, title: str, snippet: str) -> str:
    """A search result's title with the short mark ahead when its page is placed in another engine (path, or a snippet
    with clear markers)."""
    v = for_source(store, url, title, snippet)
    if v is None or not v.engine:
        return title
    return f"{short(v)} {title}"


def prompt_rule(store: Any) -> str:
    """One rule line for the lead's and the subagents' prompts; '' without an engine scope."""
    sc = scopes_of(store)
    if not sc:
        return ""
    out = []
    for proj, eng in sc.items():
        p = table()[proj]
        own = p["engines"][eng]["label"]
        others = ", ".join("its " + e["label"] for k, e in p["engines"].items() if k != eng)
        out.append(f"\n\nENGINE SCOPE: the task is about {p.get('name') or proj}'s {own}. Tool results mark pages, files, "
                   f"search hits and quoted parts that describe another engine of {p.get('name') or proj} ({others}) "
                   f"with [OTHER ENGINE ...] or [PARTLY OTHER ENGINE ...]: their flags, environment variables, "
                   f"defaults and measured numbers are not the {own}'s - do not report them as the {own}'s options "
                   f"unless the {own}'s own code or docs show them, and say which engine they belong to when you "
                   f"mention them.")
    return "".join(out)


SECTION_RULE = ("- A source marked [OTHER ENGINE ...], or a quote marked [OTHER ENGINE ...] from a page marked [PARTLY "
                "OTHER ENGINE ...], describes another engine of the same project than the one the task is about: "
                "never present its flags, settings, defaults, files or numbers as the task's engine's - say which "
                "engine it is about, and keep it out of the steps you recommend unless a source about the task's "
                "engine confirms it.")
