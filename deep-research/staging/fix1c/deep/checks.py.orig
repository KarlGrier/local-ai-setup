"""Report checks of phase 4's six fixes (the user's 10-24 list, extended 10-27 after the code-tool grading).

Switched on per fix by ``LDR_DEEP_FIX`` (a comma list, or ``all``); without it nothing here changes a report:
  version   Fix 1: every flag / environment variable / build option the report names is looked up in the project's
            code at the user's version (the code tool's pinned clone, when the code tool is on) and in the research's
            sources; one recommended for the user's engine but found only in another engine, another version or
            another project gets "[Version check: ...]" where it is recommended and a line in a "Version check" section
  inline    Fix 2: the critic's "Check these" items are also marked on the lines they concern ("[Check: ...]"), and a
            claim the citation check finds unsupported carries the checker's note in its mark
  arith     Fix 3: the derived numbers of the report are recomputed in code (a restricted calculator: numbers, units,
            + - * / ^ and parentheses - nothing else is evaluated); a wrong one gets "[Arithmetic check: ...]". The
            agents also get a `calculate` tool with the same calculator.
  cite      Fix 4: every [N] must be a source of this research; others are taken out of the text, and a statement
            left without any citation is marked "[Citation check: ...]"
  baseline  Fix 5: the setup check (setup.py) also judges every recommendation against the user's current settings
            ("already set" is not a gain); its like-with-like gain notes were dropped 10-28 (the user: noise)
  budget    Fix 6: the time budget covers the whole run; the report stage's time is reserved from the start and the
            report stage plans its checks to finish by the budget (TimePlan below; the strategy sets the deadlines)
  consist   the consistency pass (10-27): statements in different parts of the report that contradict each other
            (the Answer or an action list against a detailed section) are found, and the one the report's own
            evidence does not support is marked with the correction ("[Consistency check: ...]"); 10-29: its focused
            step first evaluates each rule the report states about a recommended setting on the task's own numbers
            (arithmetic written out, recomputed in code), then compares the outcome with the claims about this setup
Marks never contain square brackets inside them, so tools/blind-open.py can strip every one with one pattern.
"""
from __future__ import annotations

import ast
import json
import math
import operator
import os
import re
import time
from typing import Any, Callable

from .prompts import VERIFY_MARK

FIXES = ("version", "inline", "arith", "cite", "baseline", "budget", "consist")


# phase 4 items 5 + 6 (Karl 10-27, bundled with the fixes): named on their own, never part of "all" - a run with
# LDR_DEEP_FIX=all keeps measuring the six fixes alone
ITEMS = ("read", "claims")


def fix_on(name: str) -> bool:
    v = {x.strip().lower() for x in os.environ.get("LDR_DEEP_FIX", "").split(",") if x.strip()}
    return name in v or ("all" in v and name not in ITEMS)


def fixes_on() -> list[str]:
    return [f for f in FIXES if fix_on(f)]


# ------------------------------------------------------------------------------------------------ marks and locating
MARK_NAMES = ("Setup check", "Fresh check", "Check", "Arithmetic check", "Version check", "Consistency check",
              "Citation check")
MARK_RE = re.compile(r"[ \t]*(?:\*{1,2})?\[(?:⚠[^\]\n]*|(?:" + "|".join(map(re.escape, MARK_NAMES))
                     + r")\b[^\]\n]*)\](?:\*{1,2})?")
CITE_RE = re.compile(r"\[\[\d+\]\]\([^)\s]*\)|\[\d+(?:\s*[,–-]\s*\d+)*\]")
_TRANS = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " ",
          "−": "-", "×": "x"}


def clean_mark(text: str, limit: int = 400) -> str:
    """Mark text: no square brackets (they would end the mark early), one line, cut at `limit`."""
    t = re.sub(r"\s+", " ", str(text or "")).strip().replace("[", "(").replace("]", ")")
    return t if len(t) <= limit else t[:limit - 3].rstrip() + "..."


def mark(name: str, text: str) -> str:
    return f" **[{name}: {clean_mark(text)}]**"


def _norm_map(s: str) -> tuple[str, list[int]]:
    """s lower-cased, without check marks, citations and Markdown emphasis, whitespace collapsed; with the index in
    s of every kept character."""
    skip = sorted([m.span() for m in MARK_RE.finditer(s)] + [m.span() for m in CITE_RE.finditer(s)])
    out, idx = [], []
    k, prev_space = 0, True
    i, n = 0, len(s)
    while i < n:
        while k < len(skip) and skip[k][1] <= i:
            k += 1
        if k < len(skip) and skip[k][0] <= i < skip[k][1]:
            i = skip[k][1]
            continue
        c = s[i]
        if c in "*`_":
            i += 1
            continue
        c = _TRANS.get(c, c)
        if c.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space = True
        else:
            out.append(c.lower())
            idx.append(i)
            prev_space = False
        i += 1
    return "".join(out), idx


class Locator:
    """Finds a quote in the report although the quote lost or changed its bold, code marks, citations, curly quotes
    or capitals (the setup check's known pitfall). Returns (start, end) in the original text."""

    def __init__(self, body: str):
        self.body = body
        self.norm, self.map = _norm_map(body)

    def find(self, quote: str) -> tuple[int, int] | None:
        q = _norm_map(quote or "")[0].strip().strip(".").strip()
        if len(q) < 12:
            return None
        p = self.norm.find(q)
        if p >= 0:
            return self.map[p], self.map[p + len(q) - 1] + 1
        words = q.split(" ")
        if len(words) >= 12:                       # the quote's last or first 10 words
            tail = " ".join(words[-10:])
            p = self.norm.find(tail)
            if p >= 0:
                return self.map[max(0, p - len(q) + len(tail))], self.map[p + len(tail) - 1] + 1
            head = " ".join(words[:10])
            p = self.norm.find(head)
            if p >= 0:
                end = min(len(self.map) - 1, p + len(q) - 1)
                return self.map[p], self.map[end] + 1
        return None


def insertion_point(body: str, end: int) -> int:
    """Where a mark goes for a statement ending at `end`: the end of its sentence (after its citations, before the
    full stop), or before the cell's closing '|' in a table row."""
    ls = body.rfind("\n", 0, end) + 1
    le = body.find("\n", end)
    le = len(body) if le < 0 else le
    if body[ls:le].lstrip().startswith("|"):
        bar = body.find("|", end, le)
        p = bar if bar >= 0 else le
        while p > end and body[p - 1] == " ":
            p -= 1
        return p
    m = re.compile(r"[.!?](?=\s|$|\*)").search(body, end, le)
    p = m.start() if m else le
    while p > end and body[p - 1] in " \t":
        p -= 1
    # a mark already there (another check's): after it
    m2 = MARK_RE.match(body, p)
    while m2 and m2.end() > p:
        p = m2.end()
        m2 = MARK_RE.match(body, p)
    return p


def insert_marks(body: str, items: list[tuple[str, str]]) -> tuple[str, list[bool]]:
    """items: (quote, mark text); each mark is put after the sentence holding its quote. Returns the new body and,
    per item, whether its quote was found. The same mark twice at one place is put once."""
    loc = Locator(body)
    at: list[tuple[int, int, str]] = []
    found = []
    for k, (q, mk) in enumerate(items):
        span = loc.find(q)
        found.append(span is not None)
        if span is not None:
            at.append((insertion_point(body, span[1]), k, mk))
    done: set[tuple[int, str]] = set()
    for p, _k, mk in sorted(at, key=lambda x: (-x[0], -x[1])):
        if (p, mk) in done:
            continue
        done.add((p, mk))
        body = body[:p] + mk + body[p:]
    return body, found


def strip_marks(body: str) -> str:
    return MARK_RE.sub("", body)


def _json(text: str, key: str):
    m = re.search(r"(?s)\{.*\}", text or "")
    if m:
        raw = m.group(0)
        for cand in (raw, re.sub(r",\s*([}\]])", r"\1", raw)):
            try:
                return json.loads(cand)[key]
            except (ValueError, KeyError, TypeError):
                continue
    return salvage_list(text, key)


def salvage_list(text: str, key: str) -> list | None:
    """The complete objects of a JSON list under `key` in a reply that was cut off (finish=length - Fix 6 caps outputs
    near the deadline): {"key": [{...}, {...}, {"cut...  ->  [{...}, {...}]. None when no complete item is there."""
    m = re.search(r'"' + re.escape(key) + r'"\s*:\s*\[', text or "")
    if not m:
        return None
    items, i, n = [], m.end(), len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] != "{":
            break
        depth, j, in_str, esc = 0, i, False, False
        while j < n:
            c = text[j]
            if in_str:
                esc = (c == "\\" and not esc)
                if c == '"' and not esc:
                    in_str = False
                elif c != "\\":
                    esc = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= n:
            break                                  # the cut item
        try:
            items.append(json.loads(text[i:j + 1]))
        except ValueError:
            break
        i = j + 1
    return items or None


def _jsonl(text: str) -> list[dict]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip().strip(",")
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


# ------------------------------------------------------------------------------------------------ Fix 4: citations
def _indices(group: str) -> list[int]:
    out = []
    for part in re.split(r"\s*,\s*", group.strip("[]")):
        if re.match(r"^\d+\s*[–-]\s*\d+$", part):
            a, b = (int(x) for x in re.split(r"\s*[–-]\s*", part))
            out += list(range(a, b + 1)) if 0 <= b - a <= 20 else [a, b]
        elif part.strip().isdigit():
            out.append(int(part))
    return out


def code_spans(text: str) -> list[tuple[int, int]]:
    """Fenced code blocks and `inline code`: a regex class such as [0-9] in them is not a citation."""
    spans = [m.span() for m in re.finditer(r"(?ms)^\s*```.*?^\s*```", text)]
    for m in re.finditer(r"`[^`\n]+`|\$[^$\n]+\$|\\\(.+?\\\)", text):     # `code`, $math$, \(math\)
        if not any(a <= m.start() < b for a, b in spans):
            spans.append(m.span())
    for m in re.finditer(r"\[0,\s*1\]", text):        # the unit interval ("bounded in [0, 1]"), not sources 0 and 1
        spans.append(m.span())
    return spans


def cite_guard(body: str, valid: Callable[[int], bool]) -> tuple[str, dict]:
    """Every [N] must be a source of this research. Invalid indices are taken out of their citation; a sentence left
    with no citation at all gets a mark. Code (fenced or `inline`) is left alone. Deterministic (no model call)."""
    removed: dict[int, int] = {}
    emptied: list[int] = []                       # positions (in the new text) of citations that disappeared
    out, last = [], 0
    new_len = 0
    code = code_spans(body)
    for m in re.finditer(r"\[\d+(?:\s*[,–-]\s*\d+)*\]", body):
        if any(a <= m.start() < b for a, b in code):
            continue
        g = m.group(0)
        idx = _indices(g)
        bad = [i for i in idx if not valid(i)]
        if not bad:
            continue
        for i in bad:
            removed[i] = removed.get(i, 0) + 1
        keep = [i for i in dict.fromkeys(idx) if valid(i)]
        rep = ("[" + ", ".join(map(str, keep)) + "]") if keep else ""
        seg = body[last:m.start()]
        if not keep:
            seg = seg.rstrip(" ")
        out.append(seg)
        new_len += len(seg)
        if not keep:
            emptied.append(new_len)
        out.append(rep)
        new_len += len(rep)
        last = m.end()
    out.append(body[last:])
    new = "".join(out)
    if not removed:
        return body, {"removed": {}, "marked": 0}
    # a sentence that lost its only citation(s): mark it once, at the sentence end
    marks = []
    for p in emptied:
        ls = max(new.rfind("\n", 0, p), max(new.rfind(". ", 0, p), new.rfind("? ", 0, p), new.rfind("! ", 0, p))) + 1
        le_m = re.compile(r"[.!?](?=\s|$)|\n").search(new, p)
        le = le_m.start() if le_m else len(new)
        if not re.search(r"\[\d+(?:\s*[,–-]\s*\d+)*\]", new[ls:le]):
            marks.append(insertion_point(new, max(ls, p - 1)))
    mk = mark("Citation check", "its citation pointed to no source of this research and was taken out; "
                                "this statement has no source")
    for p in sorted(set(marks), reverse=True):
        new = new[:p] + mk + new[p:]
    return new, {"removed": {str(k): v for k, v in sorted(removed.items())}, "marked": len(set(marks))}


def cite_section(res: dict) -> str:
    if not res or not res.get("removed"):
        return ""
    n = sum(res["removed"].values())
    lst = ", ".join(f"{k} ({v}x)" if v > 1 else k for k, v in res["removed"].items())
    return (f"Citations to sources that are not part of this research were taken out: {n} ({lst})"
            + (f"; {res['marked']} statement(s) were left without a source and are marked." if res.get("marked")
               else "."))


# ------------------------------------------------------------------------------------------------ Fix 3: arithmetic
UNITS = {"kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 2.0 ** 10, "mib": 2.0 ** 20, "gib": 2.0 ** 30,
         "tib": 2.0 ** 40, "thousand": 1e3, "million": 1e6, "billion": 1e9, "%": 0.01}
_NUM_UNIT = re.compile(r"(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(KiB|MiB|GiB|TiB|KB|MB|GB|TB|thousand|million|billion|%)(?![A-Za-z])",
                       re.I)
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow}


class CalcError(ValueError):
    pass


def calc(expr: str) -> float:
    """Evaluate numbers (with the units above), + - * / ^ and parentheses. Nothing else: no names, no calls."""
    s = str(expr or "").strip()
    if not s or len(s) > 400:
        raise CalcError("give an expression of 1-400 characters")
    s = s.replace(",", "") if re.search(r"\d,\d{3}", s) else s
    s = s.translate(str.maketrans({"×": "*", "÷": "/", "−": "-", "–": "-"}))
    s = _NUM_UNIT.sub(lambda m: f"({m.group(1)}*{UNITS[m.group(2).lower()]!r})", s)
    s = s.replace("^", "**")
    if re.search(r"[A-Za-z_]", s.replace("e+", "").replace("e-", "").replace("e", "")):
        raise CalcError("only numbers, the units KB MB GB TB KiB MiB GiB TiB thousand million billion %, "
                        "+ - * / ^ and parentheses")
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as e:
        raise CalcError(f"not an arithmetic expression: {e.msg}")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 64 or abs(a) > 1e12):
                raise CalcError("power too large")
            if isinstance(n.op, ast.Div) and b == 0:
                raise CalcError("division by zero")
            v = _OPS[type(n.op)](a, b)
            if isinstance(v, complex) or not math.isfinite(v):
                raise CalcError("no finite result")
            return float(v)
        raise CalcError("only numbers and + - * / ^")
    return ev(tree)


def fmt_num(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.3g} billion"
    if a >= 1e6:
        return f"{v / 1e6:.3g} million"
    if a >= 1000:
        return f"{v:,.0f}"
    return f"{v:.3g}"


ARITH_PROMPT = VERIFY_MARK + """ Below is a research report. Find every CALCULATION in it: a number the \
report derives from other numbers - products, ratios, sums, differences, unit conversions, percentages and speed-ups, \
times from sizes and speeds, counts such as rows = size / row size, totals of a list. Skip numbers simply quoted from a \
source or measured.

For each, write the calculation as a formula that a program can recompute, with the input numbers exactly as the \
report gives them:
- only plain numbers, + - * / ^ and parentheses - no unit words;
- the formula's value must BE the report's result in the report's own unit: do every unit conversion yourself with an \
explicit factor (MB to GB: / 1000; GB at GB/s to ms: * 1000; a fraction to percent: * 100);
- "result_unit": the unit the report gives the result in, as text (for your reference only);
- "stated": the report's result as a plain number in that unit (for a range, one formula per end, or its middle);
- "bound": how the report states that result: "=" (exact or rounded), "~" (about, roughly, ~, ≈), "<=" (within, \
under, up to, at most, less than), ">=" (at least, over, more than) or "range" (then also "stated_low" and \
"stated_high").

<report>
{report}
</report>

Reply with JSON only: {{"calcs": [{{"quote": "<the words that give the result, copied exactly from the report>", \
"formula": "...", "result_unit": "...", "stated": <number>, "bound": "=", "what": "<what is computed, at most 12 \
words>"}}]}}"""


# 10-28 (bundle replays): a stated result can be a bound or a range ("within 2 %", "~2-3 MB"); checking it as an equality
# gave false alarms ("1.71 %, not 2 %"). The model says which ("bound"); the quote's own words decide when it does not.
_BOUND_WORDS = (("<=", re.compile(r"(?:within|under|below|up to|at most|less than|no more than|<|≤)\s*[~≈]?\s*$", re.I)),
                (">=", re.compile(r"(?:at least|over|above|more than|no less than|>|≥)\s*[~≈]?\s*$", re.I)),
                ("~", re.compile(r"(?:~|≈|about|approx\.?|approximately|around|roughly|some|nearly|almost)\s*$", re.I)))
_RANGE_RE = re.compile(r"(\d[\d,]*\.?\d*)\s*(?:-|–|—|to)\s*~?\s*(\d[\d,]*\.?\d*)")


def _stated_bound(quote: str, stated: float, c: dict) -> tuple[str, float, float]:
    """("=" | "~" | "<=" | ">=" | "range", low, high) for a model-listed result."""
    b = str(c.get("bound") or "").strip()
    try:
        lo, hi = float(str(c.get("stated_low")).replace(",", "")), float(str(c.get("stated_high")).replace(",", ""))
        if lo <= hi:
            return "range", lo, hi
    except (TypeError, ValueError):
        pass
    q = quote or ""
    for m in _RANGE_RE.finditer(q):
        try:
            a, z = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        if a < z and any(abs(x - stated) <= 0.005 * max(abs(stated), 1e-12) for x in (a, z, (a + z) / 2)):
            return "range", a, z
    for m in re.finditer(r"\d[\d,]*\.?\d*", q):
        try:
            x = float(m.group(0).replace(",", ""))
        except ValueError:
            continue
        if abs(x - stated) <= 0.005 * max(abs(stated), 1e-12):
            before = q[max(0, m.start() - 24):m.start()]
            for kind, rx in _BOUND_WORDS:
                if rx.search(before):
                    return kind, stated, stated
            break
    if b in ("<=", ">=", "~"):
        return b, stated, stated
    return "=", stated, stated


def _judge(v: float, stated: float, quote: str, c: dict, tolerance: float) -> tuple[bool, float, str]:
    """(ok, relative miss, bound kind): a bound passes when the value is on its side, a range when the value is in it
    (each with the tolerance), "~" with 15 %, "=" with the tolerance."""
    kind, lo, hi = _stated_bound(quote, stated, c)
    if kind == "range":
        ok = lo * (1 - tolerance) <= v <= hi * (1 + tolerance)
        rel = 0.0 if lo <= v <= hi else min(abs(v - lo), abs(v - hi)) / max(abs(lo), 1e-12)
    elif kind == "<=":
        rel = max(0.0, (v - stated) / abs(stated))
        ok = rel <= tolerance
    elif kind == ">=":
        rel = max(0.0, (stated - v) / abs(stated))
        ok = rel <= tolerance
    else:
        rel = abs(v - stated) / abs(stated)
        ok = rel <= (0.15 if kind == "~" else tolerance)
    return ok, rel, kind


def _numbers_in(s: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", s or "")


# Written-out equations, checked with no model (10-27 replay: the model's list missed 2 of 3 planted errors, and most of
# a report's arithmetic is written out, e.g. "1,357 × 9.4 MB = 12.8 GB", "(3÷2 + 1) × 356 = 2.5 × 356 = 890 B").
_EQ_UNITS = {"b": (1.0, "B"), "kb": (1e3, "B"), "mb": (1e6, "B"), "gb": (1e9, "B"), "tb": (1e12, "B"),
             "kib": (2.0 ** 10, "B"), "mib": (2.0 ** 20, "B"), "gib": (2.0 ** 30, "B"), "tib": (2.0 ** 40, "B"),
             "kb/s": (1e3, "B/s"), "mb/s": (1e6, "B/s"), "gb/s": (1e9, "B/s"), "tb/s": (1e12, "B/s"),
             "ns": (1e-9, "s"), "µs": (1e-6, "s"), "us": (1e-6, "s"), "ms": (1e-3, "s"), "s": (1.0, "s"),
             "%": (0.01, "%"), "bit": (0.125, "B"), "bits": (0.125, "B")}
_EQ_NUM = r"\d[\d,]*(?:\.\d+)?(?:[KM](?![A-Za-z]))?"
_EQ_UNIT = r"(?:\s?(?:KiB|MiB|GiB|TiB|KB/s|MB/s|GB/s|TB/s|KB|MB|GB|TB|bits|bit|ns|µs|us|ms|B|s|%)(?![A-Za-z/]))?"
_EQ_TERM = rf"\(*\s*{_EQ_NUM}{_EQ_UNIT}(?:\s+[a-z][a-z-]*){{0,2}}\s*\)*"   # "1,357 hot experts × 9.4 MB": up to 2 words
_EQ_OP = r"(?:\s*[×*÷/+−^]\s*|\s-\s|\sx\s)"         # 10-28: ^ too ("2048 × 2^20")
_EQ_EXPR = rf"{_EQ_TERM}(?:{_EQ_OP}{_EQ_TERM})*"
_EQ_CHAIN = re.compile(rf"(?<![\w.$/=–-])(?P<chain>{_EQ_EXPR}(?:\s+(?:=|≈|~=)\s+~?\s*{_EQ_EXPR})+)")
_EQ_TOK = re.compile(rf"(?P<num>{_EQ_NUM})(?P<unit>{_EQ_UNIT})")


def _eq_side(part: str) -> tuple[float, float, list[str]] | None:
    """(value with the units' scales, value of the bare numbers, unit families) of one side, or None."""
    fams: list[str] = []

    part = re.sub(r"(?<=[\dBst%])\s+(?!(?:bits?|ms|ns|us|s)\b)[a-z][a-z-]*(?:\s+[a-z][a-z-]*)?(?=\s*[)×*÷/+−x-]|\s*$)",
                  "", part)   # label words out (not the unit words)

    def num(m, scaled: bool) -> str:
        n, mult = m.group("num"), 1.0
        if n[-1] in "KM":
            n, mult = n[:-1], (1e3 if n[-1] == "K" else 1e6)
        v = float(n.replace(",", "")) * mult
        u = (m.group("unit") or "").strip().lower()
        if u and scaled:
            fams.append(_EQ_UNITS[u][1])
            v *= _EQ_UNITS[u][0]
        return f"({v!r})"
    ops = lambda s: s.replace("×", "*").replace("÷", "/").replace("−", "-").replace(" x ", " * ")
    try:
        base = calc(ops(_EQ_TOK.sub(lambda m: num(m, True), part)))
        raw = calc(ops(_EQ_TOK.sub(lambda m: num(m, False), part)))
    except CalcError:
        return None
    return base, raw, fams


def explicit_equations(body: str, tolerance: float = 0.10) -> list[dict]:
    """Every written-out calculation chain (numbers, units, + - × ÷, '=' or '≈' with spaces around) outside code spans,
    each pair of neighbouring sides compared. Units on both sides: compared in base units, when the result's unit
    family can come from the left's (B, B/s, s); a unit on one side only: the bare numbers (and x100 for a percent)."""
    text = list(body)
    for a, b in code_spans(body):                  # code blanked out, then Markdown emphasis taken out
        text[a:b] = " " * (b - a)
    text = re.sub(r"\*{1,2}|__", "", "".join(text))
    out = []
    for m in _EQ_CHAIN.finditer(text):
        chain = m.group("chain").strip()
        if re.match(r"\s?[–-]\s?\d", text[m.end():m.end() + 4]):
            continue                               # 10-28: "... = 18-25 MB" - a range, not one result (not checked)
        parts = [p.strip().lstrip("~").strip() for p in re.split(r"\s+(?:=|≈|~=)\s+", chain)]
        bare = re.sub(r"[KMGT]?B/s", " ", chain)     # the "/" of GB/s is not a division
        if len(parts) < 2 or not re.search(r"[×*÷+−]|/|\s-\s|\sx\s", bare) or len(re.findall(r"\d", chain)) < 2:
            continue
        approx = "≈" in chain or "~" in chain
        sides = [_eq_side(p) for p in parts]
        for k in range(len(parts) - 1):
            a, b = sides[k], sides[k + 1]
            if a is None or b is None:
                continue
            (ba, ra, fa), (bb, rb, fb) = a, b
            rec = {"quote": chain[:400], "formula": parts[k][:200], "stated": parts[k + 1][:80], "method": "explicit",
                   "what": "written-out calculation", "result_unit": ""}
            cands = []
            if fa and fb:
                fam = fb[-1]
                ok = fam in fa or (fam == "s" and {"B", "B/s"} <= set(fa)) or (fam == "B/s" and {"B", "s"} <= set(fa)) \
                    or (fam == "B" and {"B/s", "s"} <= set(fa)) or fam == "%"
                if not ok:
                    rec["status"] = "units unclear"
                    out.append(rec)
                    continue
                cands.append((ba, bb))
                scale = _EQ_UNITS[_EQ_TOK.search(parts[k + 1]).group("unit").strip().lower()][0] if _EQ_TOK.search(
                    parts[k + 1]) and (_EQ_TOK.search(parts[k + 1]).group("unit") or "").strip() else 1.0
            else:
                # 10-28 (the combined rerun: 11 false alarms): a unit on one side only - the bare numbers, the left's
                # unit-aware value (a ratio of two sizes, a percent factor: "75 GB / 11.4 MB = 6,579",
                # "x 75 % = 1,019") and, for a unit on the right only, the right in base units ("... = 168 MB")
                cands += [(ra, rb), (ba, rb)]
                if fb and not fa:
                    cands.append((ra, bb))
                if "%" in fb and not fa:
                    cands.append((ra * 100, rb))
                scale = 1.0
            # 10-28 (p4s6 o02: "138 + 110 = 248 GB / 1.8 GB/s ≈ 138 s"): a side that goes on calculating states the
            # previous step's result as its first number - that number is compared too
            nxt = parts[k + 1]
            first = _EQ_TOK.search(nxt)
            if first and first.start() <= 2 and re.search(r"[×*÷+−^]|/|\s-\s|\sx\s",
                                                          re.sub(r"[KMGT]?B/s", " ", nxt[first.end():])):
                fs = _eq_side(first.group(0))
                if fs:
                    cands += [(ra, fs[1]), (ba, fs[0])]
            tol = tolerance * 1.5 if approx else tolerance
            best = min(cands, key=lambda c: abs(c[0] - c[1]) / max(abs(c[1]), 1e-12))
            rel = abs(best[0] - best[1]) / max(abs(best[1]), 1e-12)
            rec["computed"] = best[0] / scale if fa and fb else best[0]
            rec["rel_diff"] = round(rel, 4)
            rec["status"] = "wrong" if rel > tol else "ok"
            if rec["status"] == "wrong" and not (fa and fb):
                # the result's unit is not written ("48 x 198 B = 9.5", the KB cut off; "1.63 ms / 800 = 2", us): a
                # match a power of 1,000 away means a missing unit, not a wrong sum - "units unclear", not marked;
                # 10-28 (p4s6 o02: "132.07 / 15,360 = 8.6 MB each", the GB cut off on the left): either side
                for f in (1e-12, 1e-9, 1e-6, 1e-3, 1e3, 1e6, 1e9, 1e12):
                    if any(abs(x * f - y) / max(abs(y), 1e-12) <= tol for x, y in cands):
                        rec["status"], rec["unit_step"] = "units unclear", f
                        break
            out.append(rec)
    return out


def arith_check(llm: Callable[[str], str], body: str, tolerance: float = 0.10) -> dict:
    """The written-out equations are checked with no model; then the model lists the other calculations as formulas
    and the program recomputes them. A formula whose input numbers do not all appear in the report is not trusted (a
    copying slip of the model, not the report's) and is only counted."""
    explicit = explicit_equations(body, tolerance)
    text = llm(ARITH_PROMPT.format(report=body))
    calcs = _json(text, "calcs")
    if calcs is None:
        return {"calcs": explicit or None, "raw": (text or "")[:4000]}
    seen = [_norm_map(e["quote"])[0] for e in explicit]
    calcs = [c for c in calcs if not (isinstance(c, dict) and any(
        q and (q in _norm_map(str(c.get("quote") or ""))[0] or _norm_map(str(c.get("quote") or ""))[0] in q)
        for q in seen))]
    plain = re.sub(r"(?<=\d),(?=\d{3})", "", body)
    report_nums = set(_numbers_in(plain))
    out = []
    for c in calcs:
        if not isinstance(c, dict):
            continue
        f, unit = str(c.get("formula") or ""), str(c.get("result_unit") or "").strip().lower()
        rec = {"quote": str(c.get("quote") or "")[:400], "formula": f[:300], "result_unit": unit,
               "stated": c.get("stated"), "what": str(c.get("what") or "")[:120]}
        try:
            stated = float(str(c.get("stated")).replace(",", ""))
            raw = calc(f)
            # 10-27 replay: the model mostly writes unit-free formulas already in the result's unit ("16+8" GB); a
            # formula with unit words is in base units (converted); a percent may come as a fraction or x100
            cands = {"as written": raw}
            if unit and unit in UNITS:
                if _NUM_UNIT.search(f):
                    cands["converted"] = raw / UNITS[unit]
                if unit == "%":
                    cands["x100"] = raw * 100
            read_as, v = min(cands.items(), key=lambda kv: abs(kv[1] - stated) / max(abs(stated), 1e-12))
            rec["read_as"] = read_as
        except (CalcError, ValueError, TypeError) as e:
            rec.update(status="not computable", error=str(e)[:120])
            out.append(rec)
            continue
        missing = [n for n in _numbers_in(f.replace(",", "")) if n not in report_nums
                   and n.rstrip("0").rstrip(".") not in report_nums]
        rec["computed"] = v
        if missing:
            rec.update(status="inputs not in the report", missing=missing[:5])
        elif stated == 0:
            rec["status"] = "ok" if abs(v) < 1e-9 else "wrong"
        else:
            ok, rel, kind = _judge(v, stated, rec["quote"], c, tolerance)
            rec["rel_diff"], rec["bound"] = round(rel, 4), kind
            rec["status"] = "ok" if ok else "wrong"
        out.append(rec)
    return {"calcs": explicit + out}


def arith_marks(res: dict) -> list[tuple[str, str]]:
    items = []
    for c in (res or {}).get("calcs") or []:
        if c.get("status") != "wrong" or not c.get("quote"):
            continue
        unit = c["result_unit"].upper() if c["result_unit"] in ("kb", "mb", "gb", "tb") else (
            {"kib": "KiB", "mib": "MiB", "gib": "GiB", "tib": "TiB", "%": "%"}.get(c["result_unit"], c["result_unit"]))
        got = fmt_num(c["computed"]) + (f" {unit}" if unit and unit not in ("thousand", "million", "billion") else "")
        if c["result_unit"] in ("thousand", "million", "billion"):
            got = fmt_num(c["computed"] * UNITS[c["result_unit"]])
        items.append((c["quote"], mark("Arithmetic check", f"{c['formula']} = {got}, not {c['stated']}"
                                                            f"{(' ' + unit) if unit else ''}")))
    return items


def arith_section(res: dict) -> str:
    cs = (res or {}).get("calcs")
    if cs is None:
        return "## Arithmetic check\n\nThe arithmetic check did not complete; the report's calculations were not recomputed."
    wrong = [c for c in cs if c.get("status") == "wrong"]
    ok = sum(1 for c in cs if c.get("status") == "ok")
    other = len(cs) - ok - len(wrong)
    if not wrong:
        return ""
    lines = ["## Arithmetic check", "",
             f"{len(cs)} calculations in this report were recomputed in code: {ok} agree, {len(wrong)} do not"
             + (f", {other} could not be recomputed" if other else "") + " (the corrections are also shown right after "
             "each one above):", ""]
    for c in wrong:
        lines.append(f"- {c['what'] or 'calculation'}: \"{clean_mark(c['quote'], 200)}\" - {clean_mark(c['formula'], 160)} "
                     f"= {fmt_num(c['computed'])}{(' ' + c['result_unit']) if c['result_unit'] else ''}, not {c['stated']}")
    return "\n".join(lines)


def make_calc_tool():
    """The agents' calculator (Fix 3): the same restricted evaluator."""
    from langchain_core.tools import tool

    @tool(description=(
        "Compute an arithmetic result exactly instead of in your head: numbers, + - * / ^ and parentheses, with the "
        "units KB MB GB TB KiB MiB GiB TiB, thousand / million / billion and %. Sizes come out in bytes, e.g. "
        "'110.6 GB / 9.4 KB' -> 11,765,957 (rows), '48 * 9.4 MB / 1 GB' -> 0.4512. Use it for every number you derive "
        "(capacities, row counts, transfer times = size / speed, speed-ups, percentages)."))
    def calculate(expression: str) -> str:
        """Description passed via ``@tool(description=...)`` above."""
        try:
            v = calc(expression)
        except CalcError as e:
            return f"CALCULATOR: {e}"
        return f"{expression} = {v:,.6g}" + (f" (= {fmt_num(v)})" if abs(v) >= 1e6 else "")

    return calculate


# ------------------------------------------------------------------------------------------------ Fix 1: versions
FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
ENV_RE = re.compile(r"(?<![\w-])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?![\w-])")
CMAKE_RE = re.compile(r"(?<![\w-])-D[A-Z][A-Z0-9_]{2,}")
# 10-28 (A8): JSON config keys in the report's code ("gpu": [0], "layer_split": "40") - kept with their quotes, and
# looked up in the code as the quoted string literal
CONFIG_RE = re.compile(r'"([a-z][a-z0-9_]{1,40})"\s*:')
GENERIC = {"CUDA_VISIBLE_DEVICES", "LD_LIBRARY_PATH", "OMP_NUM_THREADS", "CUDA_MODULE_LOADING", "PYTORCH_CUDA_ALLOC_CONF",
           "HF_HOME", "XDG_CACHE_HOME", "CMAKE_BUILD_TYPE", "CMAKE_CUDA_ARCHITECTURES", "TCP_NODELAY"}


def setting_names(body: str) -> list[str]:
    """Flags, environment variables and -D build options named in the report, in order of first use."""
    t = strip_marks(body)
    names: dict[str, None] = {}
    for rx in (FLAG_RE, ENV_RE, CMAKE_RE):
        for m in rx.finditer(t):
            n = m.group(0)
            if rx is ENV_RE and (len(n) < 5 or n in GENERIC or n.isdigit()):
                continue
            names.setdefault(n, None)
    for a, b in code_spans(t):                      # config keys only inside code (a JSON snippet, `"key": value`)
        for m in CONFIG_RE.finditer(t[a:b]):
            names.setdefault(f'"{m.group(1)}"', None)
    order = sorted(names, key=lambda n: t.find(n))
    return order


def _sentences_with(body: str, name: str, n: int = 2) -> list[str]:
    out = []
    for line in body.split("\n"):
        if name not in line or line.lstrip().startswith("#"):
            continue
        for sent in re.split(r"(?<=[.!?])\s+", line):
            if name in sent:
                out.append(clean_mark(strip_marks(sent), 300))
                break
        if len(out) >= n:
            break
    return out


ENGINE_DIRS_PROMPT = VERIFY_MARK + """ A research task is about one program, or one engine of a project. Below \
are the task and the folder layout of the project's source code at the user's version. Which folders hold the code of \
the program or engine the task is about - its own option parsing and implementation - and not the project's other \
engines, tools, apps, tests or docs? Be specific: when a folder (such as src/) holds several engines, list the \
engine's own subfolder(s), not the parent; when the project has one engine per model family, list only the one for \
the model the task is about; when the task is about the project as a whole or names no one model, list every engine's \
folders and the core folders they share. If the whole repository is that program, answer ".". List apart, as "shared", folders \
whose code parses or passes options for SEVERAL engines (a common launcher, CLI or server): accepting an option there \
does not mean the engine reads it.

<task>
{task}
</task>

<layout repo="{repo}">
{tree}
</layout>

Reply with JSON only: {{"dirs": ["<a folder path exactly as listed>"], "shared": ["<folder>"], "why": "<one sentence>"}}"""


def engine_dirs(llm: Callable[[str], str], task: str, repo: Any) -> dict:
    """The folders of the engine the task is about in this clone (one model call; checked to exist)."""
    import os as _os
    rows = []
    for root, ds, fs in _os.walk(repo.root):
        rel = _os.path.relpath(root, repo.root)
        depth = 0 if rel == "." else rel.count(_os.sep) + 1
        ds[:] = sorted(d for d in ds if d != ".git") if depth < 3 else []
        if rel != ".":
            rows.append(f"{rel}/  ({len(fs)} files)")
        if len(rows) >= 400:
            break
    out = llm(ENGINE_DIRS_PROMPT.format(task=task, repo=f"{repo.name}@{repo.ref}", tree="\n".join(rows)))
    got = _json(out, "dirs") or []
    shared_got = _json(out, "shared") or []
    ok, shared = [], []
    for d in got if isinstance(got, list) else []:
        d = str(d).strip().strip("/") or "."
        if d == "." or (repo.root / d).is_dir():
            # 10-28 (A8: --ple-io, --pcie-frac passed as DeepSeek options through strata_cli/launch): a launcher, CLI or
            # server folder is shared, whatever the answer says
            (shared if d != "." and SHARED_DIR_RE.search(d) else ok).append(d)
    for d in shared_got if isinstance(shared_got, list) else []:
        d = str(d).strip().strip("/")
        if d and d not in ok and d not in shared and (repo.root / d).is_dir():
            shared.append(d)
    return {"repo": f"{repo.name}@{repo.ref}", "dirs": ok, "shared": shared, "why": _json(out, "why"),
            "raw": None if got else (out or "")[:1000]}


SHARED_DIR_RE = re.compile(r"(^|/)(cli|launch|launcher|serve|server|apps?|tools|scripts|frontend)(/|$)|_cli(/|$)")


def _in_dirs(path: str, dirs: list[str]) -> bool:
    return any(d == "." or path == d or path.startswith(d + "/") for d in dirs)


# 10-29 (Fix 1b; the 10-28 judging of the DeepSeek replays' 68 marks against the v0.2.4 code: 11 false, all settings the
# shared launcher or server applies on the engine's path - "gpu" / "gpu_order", --model / --plan / --tune / --set,
# STRATA_DS4_AUTO_PIN - or names the search missed: SLOT_KEEP for STRATA_DS4_SLOT_KEEP, -DSTRATA_NATIVE_EXPERTS): a hit in
# the launcher / server's scripts is traced (the lines around it, the function it is in, where the value goes), a short
# name is judged by its long form, a -D option by its CMake lines, and a constant of the code that is no setting at all
# (a planner's SMALLEST_CARD_GB) is not sent to the model
SCRIPT_EXT = (".py", ".sh", ".bash", ".bat", ".cmd", ".ps1", ".js", ".mjs", ".cjs", ".ts")
CODE_EXT = (".py", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".cu", ".cuh", ".js", ".mjs", ".cjs", ".ts", ".rs",
            ".go", ".java", ".kt", ".swift", ".m", ".mm", ".metal")
TEST_PATH_RE = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*$|_tests?\.[A-Za-z]+$|(^|/)conftest\.py$")
# variables of the CUDA / ROCm runtimes, the OS, Python: what the server sets there is not looked for in the engine's code
RUNTIME_ENV_RE = re.compile(r"^(CUDA|HIP|ROCR|HSA|GPU|OMP|MKL|KMP|LD|DYLD|PYTHON|HF|TRANSFORMERS|TORCH|PYTORCH|NCCL|TF|XDG|VK|"
                            r"MESA|SYCL|ONEAPI|ZE)_|^(PATH|HOME|TMPDIR|TEMP|TMP|USER|LANG)$")
_PASSED_RE = re.compile(r"""["'](--[a-z][a-z0-9]*(?:-[a-z0-9]+)*)["']|\benv(?:iron)?\s*(?:\[|\.setdefault\(|\.get\(|"""
                        r"""\.pop\()\s*["']([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)["']""")
# a line on the engine's path: its arguments, its environment, its process (strong); the engine or its family named (weak)
_ENGINE_STRONG_RE = re.compile(r"\benv\s*\[|environ\s*\[|\b(?:args|argv|cmd)\s*(?:\+=|\.append|\.extend|\.insert)|\bargv\b|"
                               r"""\[\s*["'](?:args|argv|env|cmd)["']\s*\]|Popen|subprocess\.""")
_ENGINE_WEAK_RE = re.compile(r"engine|\bfamily\b|\barch\b", re.I)
TRACE_HITS, TRACE_CANDIDATES, TRACE_USES, TRACE_CHARS = 2, 16, 2, 3000
# a name read as a setting somewhere: quoted (getenv("X"), env["X"], "X": ...), a shell / CMake / preprocessor variable
_SETTING_USE = (r"""["'`]{e}["'`]""", r"\$\{{?{e}\b", r"\$env:{e}\b", r"%{e}%", r"(?<![\w.]){e}=\S", r"-D{e}\b",
                r"\boption\s*\(\s*{e}\b", r"\bif\s*\(\s*(?:NOT\s+)?{e}\b", r"#\s*(?:el)?if(?:n?def)?\b.*\b{e}\b",
                r"\bdefined\s*\(?\s*{e}\b", r"getenv|environ")


def _bare(n: str) -> str:
    """'"gpu"' -> 'gpu': a config key is listed with its quotes, the model answers without them."""
    return n[1:-1] if len(n) > 2 and n[0] == n[-1] == '"' else n


def _whole(s: str) -> re.Pattern:
    """s as a whole name, not a piece of a longer one (--set is not in --settings, SLOT_KEEP not in STRATA_DS4_SLOT_KEEP)."""
    if s.startswith("-"):
        return re.compile(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])")
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(s) + r"(?![A-Za-z0-9_])")


def _cut(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n - 3].rstrip() + "..."


def _search_name(n: str) -> str:
    """What the code is searched for: a -D build option without the -D (CMake and the code say STRATA_X, not -DSTRATA_X)."""
    return n[2:] if CMAKE_RE.fullmatch(n) else n


def _not_a_setting(hits: list[dict], name: str) -> str | None:
    """'file:line' where the code defines `name` as a constant, when no hit reads it as a setting (no environment read,
    no quoted key, no shell / CMake / preprocessor variable, no flag) - a planner's SMALLEST_CARD_GB = 8.0; else None."""
    e = re.escape(name)
    whole = _whole(name)
    use = re.compile("|".join(p.format(e=e) for p in _SETTING_USE))
    define = re.compile(rf"^\s*(?:[\w:<>,*&\s]*\s)?{e}\s*(?::[^=]*)?(?:=(?!=)|\{{)|^\s*#\s*define\s+{e}\b")
    defs = []
    for h in hits:
        t = h.get("text") or ""
        if not whole.search(t):
            continue
        if use.search(t):
            return None
        if h["file"].endswith(CODE_EXT) and define.search(t):
            if re.search(r"""=\s*["'][A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+["']""", t):
                return None                 # SH_STREAM = "STRATA_SH_STREAM": it holds a variable's name - a setting
            defs.append(h)
    return f"{defs[0]['file']}:{defs[0]['line']}" if defs else None


def _long_forms(name: str, hits: list[dict], names: list[str]) -> list[str]:
    """Longer names that end with this one (SLOT_KEEP -> STRATA_DS4_SLOT_KEEP): those in the code's hits first (the
    report's own before the others, then by count), then those only the report names."""
    rx = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z0-9]\w*?_" + re.escape(name) + r")(?![A-Za-z0-9_])")
    seen: dict[str, int] = {}
    for h in hits:
        for m in rx.finditer(h.get("text") or ""):
            seen[m.group(1)] = seen.get(m.group(1), 0) + 1
    rep = [m for m in names if m != name and m.endswith("_" + name) and ENV_RE.fullmatch(m)]
    code = sorted(seen, key=lambda k: (k not in rep, -seen[k], k))
    return code + [m for m in rep if m not in code]


class _Src:
    """The shared launcher / server's files of one clone for the traces, read once per version check: their lines and,
    for the Python files (parsed when first needed), the function and statement spans."""

    def __init__(self, root: Any, dirs: list[str]):
        self.root, self.dirs = str(root), list(dirs)
        self._lines: dict[str, list[str]] = {}
        self._text: dict[str, str] = {}
        self._py: list[str] | None = None
        self._spans: dict[str, tuple[list, list]] = {}
        self._ns: set[str] | None = None

    def namespaces(self) -> set[str]:
        """The names the launcher / server keeps parsed command lines in: `a: argparse.Namespace` parameters and
        `a = parser.parse_args(...)` (an attribute read on them is a flag's value)."""
        if self._ns is None:
            rx = re.compile(r"\b(\w+)\s*:\s*(?:argparse\.)?Namespace\b|^\s*(\w+)(?:\s*,\s*\w+)?\s*=\s*[\w.()]*?"
                            r"\.parse_(?:known_)?(?:intermixed_)?args\(", re.M)
            ns: set[str] = set()
            for rel in self.py_files():
                if rel not in self._text:
                    self._text[rel] = "\n".join(self.lines(rel))
                if "Namespace" in self._text[rel] or "parse_" in self._text[rel]:
                    ns |= {m.group(1) or m.group(2) for m in rx.finditer(self._text[rel])}
            self._ns = {x for x in ns if x and x not in ("self", "cls")}
        return self._ns

    def lines(self, rel: str) -> list[str]:
        if rel not in self._lines:
            p = os.path.join(self.root, rel)
            try:
                ok = os.path.isfile(p) and not os.path.islink(p) and os.path.getsize(p) <= 2 * 1024 * 1024
                if ok:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        self._lines[rel] = fh.read().splitlines()
                else:
                    self._lines[rel] = []
            except OSError:
                self._lines[rel] = []
        return self._lines[rel]

    def py_files(self) -> list[str]:
        """The shared folders' Python files, tests left out (at most 800)."""
        if self._py is None:
            out: list[str] = []
            for d in self.dirs:
                for r, ds, fs in os.walk(os.path.join(self.root, d)):
                    ds[:] = sorted(x for x in ds if not x.startswith(".") and x != "__pycache__")
                    for f in sorted(fs):
                        rel = os.path.relpath(os.path.join(r, f), self.root)
                        if f.endswith(".py") and rel not in out and not TEST_PATH_RE.search(rel):
                            out.append(rel)
                    if len(out) >= 800:
                        break
            self._py = out
        return self._py

    def spans(self, rel: str) -> tuple[list, list]:
        """([(start, end, qualified name, first docstring line)], [(start, end, statement)]) of a Python file."""
        if rel not in self._spans:
            funcs: list = []
            stmts: list = []
            try:
                tree = ast.parse("\n".join(self.lines(rel))) if rel.endswith(".py") else None
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                tree = None

            def walk(node, prefix):
                for ch in ast.iter_child_nodes(node):
                    if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if not isinstance(ch, ast.ClassDef):
                            doc = (ast.get_docstring(ch) or "").strip().split("\n")[0]
                            funcs.append((ch.lineno, ch.end_lineno or ch.lineno, prefix + ch.name, doc))
                        walk(ch, prefix + ch.name + ".")
                    else:
                        if isinstance(ch, ast.stmt):
                            stmts.append((ch.lineno, ch.end_lineno or ch.lineno, ch))
                        walk(ch, prefix)
            if tree is not None:
                try:
                    walk(tree, "")
                except RecursionError:
                    pass
            self._spans[rel] = (funcs, stmts)
        return self._spans[rel]

    def func_at(self, rel: str, line: int):
        inner = [f for f in self.spans(rel)[0] if f[0] <= line <= f[1]]
        return max(inner, key=lambda f: f[0]) if inner else None

    def stmt_at(self, rel: str, line: int):
        inner = [s for s in self.spans(rel)[1] if s[0] <= line <= s[1]]
        return min(inner, key=lambda s: (s[1] - s[0], -s[0]))[2] if inner else None

    def find(self, rx: re.Pattern, skip: set = frozenset(), near: str | None = None, span: tuple | None = None,
             limit: int = 12) -> list[tuple[str, int]]:
        """Code lines matching rx in the shared Python files (not comments, def lines or docstrings), the file `near`
        first; with span=(file, start, end) only there."""
        files = [span[0]] if span else self.py_files()
        if near in files:
            files = [near] + [f for f in files if f != near]
        out = []
        for rel in files:
            if rel not in self._text:
                self._text[rel] = "\n".join(self.lines(rel))
            if not rx.search(self._text[rel]):          # most files do not have it: one search each
                continue
            ls = self.lines(rel)
            lo, hi = (span[1], span[2]) if span else (1, len(ls))
            for i in range(lo, min(hi, len(ls)) + 1):
                if (rel, i) in skip or not rx.search(ls[i - 1]):
                    continue
                s = ls[i - 1].lstrip()
                if s.startswith(("#", "def ", "async def ", "class ", "@")):
                    continue
                st = self.stmt_at(rel, i)
                if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant):
                    continue
                out.append((rel, i))
                if len(out) >= limit:
                    return out
        return out

    def where(self, rel: str, line: int) -> str:
        f = self.func_at(rel, line) if rel.endswith(".py") else None
        if not f:
            return f"{rel}:{line}"
        return f"{rel}:{line} in {f[2]}()" + (f' ("{_cut(f[3], 80)}")' if f[3] else "")

    def context(self, rel: str, line: int, before: int = 1, after: int = 2, width: int = 130) -> str:
        """The code lines around a line (inside its function), comments and blank lines left out."""
        ls = self.lines(rel)
        f = self.func_at(rel, line) if rel.endswith(".py") else None
        lo, hi = max(1, line - before, f[0] + 1 if f else 1), min(len(ls), line + after, f[1] if f else len(ls))
        py = rel.endswith(".py")
        out = [_cut(re.sub(r"\s{2,}#\s.*$", "", ls[i - 1]) if py else ls[i - 1], width) for i in range(lo, hi + 1)
               if ls[i - 1].strip() and not ls[i - 1].lstrip().startswith(("#", "//"))]
        return " | ".join(out)

    def engine_path(self, rel: str, line: int) -> int:
        """0: the lines around reach the engine's arguments, environment or process; 1: they name the engine or its
        family; 2: neither."""
        t = self.where(rel, line) + " " + self.context(rel, line, before=1, after=2)
        return 0 if _ENGINE_STRONG_RE.search(t) else 1 if _ENGINE_WEAK_RE.search(t) else 2

    def best(self, uses: list[tuple[str, int]], n: int = TRACE_USES) -> list[tuple[str, int]]:
        """The uses on the engine's path first, then a plain test of the value (`if a.plan:` - its body is shown)."""
        plain = re.compile(r"^\s*(?:el)?if\s+(?:not\s+)?[\w.]+(?:\([^()]*\))?\s*:")
        return sorted(uses, key=lambda u: (self.engine_path(*u), not plain.search(self.lines(u[0])[u[1] - 1]),
                                           uses.index(u)))[:n]


def _stored_in(st, needle: re.Pattern, src: _Src, rel: str, line: int, prefer: str | None = None):
    """When `st` assigns a value that contains the needle: (label, pattern of its reads, span) of where it goes - a local
    variable (read in the same function), an attribute (.extra) or a key (["args"]); else None."""
    if not isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)) or st.value is None:
        return None
    v = st.value                        # a condition (x = a.yes or not a.plan, bool(...)) does not keep the value
    if isinstance(v, (ast.BoolOp, ast.Compare, ast.UnaryOp)) or (
            isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "bool"):
        return None
    try:
        if not needle.search(ast.unparse(st.value)):
            return None
    except Exception:  # noqa: BLE001
        return None
    targets = st.targets if isinstance(st, ast.Assign) else [st.target]
    flat = []
    for t in targets:
        flat += list(t.elts) if isinstance(t, (ast.Tuple, ast.List)) else [t]
    # several targets ("s.family, s.model = resolve(a.model, ...)"): the one named like the needle, else the first
    t = (next((x for x in flat if isinstance(x, ast.Attribute) and x.attr == prefer), None)
         or next((x for x in flat if isinstance(x, ast.Attribute) and needle.search("." + x.attr)), flat[0] if flat else None))
    if isinstance(t, ast.Name):
        f = src.func_at(rel, line)
        return (t.id, re.compile(rf"(?<![\w.]){re.escape(t.id)}\b(?!\s*=[^=])"), (rel, line + 1, f[1]) if f else None)
    if isinstance(t, ast.Attribute):
        return ("." + t.attr, re.compile(rf"\.{re.escape(t.attr)}\b(?!\s*\()(?!\s*=[^=])"), None)
    if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str):
        k = re.escape(t.slice.value)
        return (f'["{t.slice.value}"]', re.compile(rf"""\[\s*["']{k}["']\s*\](?!\s*=[^=])|\.get\(\s*["']{k}["']"""), None)
    return None


def _trace(src: _Src, rel: str, line: int, q: str) -> str:
    """One launcher / server hit: where it is (file, function and its docstring's first line), the lines around it, and
    where the value goes - what the parsed flag or the value read is stored in and where that is read, and the callers
    of the function that reads it (the ones on the engine's path first)."""
    st, fn = (src.stmt_at(rel, line), src.func_at(rel, line)) if rel.endswith(".py") else (None, None)
    if st is not None and 0 <= line - st.lineno <= 2:   # the statement itself (an add_argument call, an assignment, an
        a = st.lineno                                   # if and the first lines of its body), not its neighbours
        b = max(line, min(getattr(st, "end_lineno", None) or a, a + 2))
        out = f"{src.where(rel, line)}: {src.context(rel, a, before=0, after=b - a)}"
    else:
        out = f"{src.where(rel, line)}: {src.context(rel, line)}"
    if not rel.endswith(".py"):
        return out
    needle = re.compile(r"""["']""" + re.escape(_bare(q)) + r"""["']""")
    steps: list[tuple[str, list]] = []
    call = st.value if isinstance(st, ast.Expr) else None
    if (isinstance(call, ast.Call) and getattr(call.func, "attr", "") == "add_argument" and q.startswith("-")
            and any(isinstance(a, ast.Constant) and a.value == q for a in call.args)):
        dest = next((k.value.value for k in call.keywords if k.arg == "dest" and isinstance(k.value, ast.Constant)), None)
        if not isinstance(dest, str):
            flags = [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            dest = next((f for f in flags if f.startswith("--")), q).lstrip("-").replace("-", "_")
        # its reads on the parsed command line (a.tune, args.set - the launcher's Namespace names), else any .dest read
        own = rf"\.{re.escape(dest)}\b(?!\s*\()(?!\s*=[^=])"
        ns = sorted(src.namespaces())
        rd = re.compile(rf"(?<![\w.])(?:{'|'.join(map(re.escape, ns))}){own}") if ns else re.compile(own)
        uses = src.find(rd, skip={(rel, line)}, near=rel)
        if not uses and ns:
            rd = re.compile(own)
            uses = src.find(rd, skip={(rel, line)}, near=rel)
        store = None                             # where the launcher keeps it: s.tune = a.tune, s.extra = {.., a.set}
        for r2, l2 in uses:
            tgt = _stored_in(src.stmt_at(r2, l2), rd, src, r2, l2, prefer=dest)
            if tgt:
                store = (r2, l2, tgt)
                break
        first = [(store[0], store[1])] if store else []
        steps.append((f"parsed into .{dest}, read at", (first + [u for u in src.best(uses, len(uses))
                                                                  if u not in first])[:TRACE_USES]))
        if store:
            r2, l2, tgt = store
            kept = [u for u in src.find(tgt[1], skip={(r2, l2)} | set(uses), span=tgt[2], limit=24)
                    if not rd.search(src.lines(u[0])[u[1] - 1])]
            steps.append((f"kept in {tgt[0]}, read at", src.best(kept)))
    else:
        tgt = _stored_in(st, needle, src, rel, line)
        if tgt:
            steps.append((f"stored in {tgt[0]}, read at", src.best(src.find(tgt[1], skip={(rel, line)}, near=rel,
                                                                             span=tgt[2]))))
        short = fn[2].split(".")[-1] if fn else ""
        method = fn is not None and "." in fn[2]
        if short and not short.startswith("__") and len(short) > 3 and (not method or "_" in short or len(short) >= 8):
            name = re.escape(short)
            callers = src.find(re.compile(rf"(?<![\w.]){name}\s*\(|\.{name}\s*\("), skip={(rel, line)}, near=rel)
            steps.append((f"{'returned by' if isinstance(st, ast.Return) else 'used in'} {short}(), which is called at",
                          src.best(callers)))
    for label, uses in steps:
        out += f"\n    {label}: " + ("; ".join(f"{src.where(r, n)}: {src.context(r, n, before=1, after=2, width=90)}"
                                          for r, n in uses) or "nowhere else in the launcher / server")
    return out


def _passed_on(text: str, q: str, repo: Any, ed: list[str]) -> str:
    """The flags and engine variables in the traced lines, with their hits in the engine's own folders (a flag the
    server adds that the engine never parses is not passed on to any effect)."""
    found: list[str] = []
    for m in _PASSED_RE.finditer(text):
        x = m.group(1) or m.group(2)
        if x and x not in found and x != _bare(q) and x not in GENERIC and not RUNTIME_ENV_RE.search(x):
            found.append(x)
    rows = []
    for x in found[:3]:
        hits: list[dict] = []
        for d in ed:
            try:
                hits += [h for h in repo.grep(x, d, fixed=True, max_hits=20)["hits"] if _whole(x).search(h["text"])]
            except Exception:  # noqa: BLE001
                pass
        rows.append(f"`{x}`: " + (f"{len(hits)} hit(s): " + "; ".join(f"{h['file']}:{h['line']}: {_cut(h['text'], 120)}"
                                                                       for h in hits[:1]) if hits else "no hits"))
    return ("    Flags / variables in these lines, in the engine's own folders: " + " | ".join(rows)) if rows else ""


def _engine_level(text: str) -> int:
    """0: on the engine's path (its arguments, environment or process) and about the engine; 1: on such a path; 2: about
    the engine or its family only; 3: neither."""
    strong, weak = bool(_ENGINE_STRONG_RE.search(text)), bool(_ENGINE_WEAK_RE.search(text))
    return 0 if strong and weak else 1 if strong else 2 if weak else 3


def _command_words(sentences: list[str], q: str, project: str = "") -> set[str]:
    """The command the report gives the flag with ("strata launch --model x --plan" -> {"launch"}): picks the parser."""
    out: set[str] = set()
    if not q.startswith("-"):
        return out
    rx = re.compile(r"([a-z][\w.-]*)\s+([a-z][\w.-]*)\s+(?:-{1,2}[\w-]+(?:[ =](?!-)\S+)?\s+)*" + re.escape(q) + r"(?![\w-])")
    for s in sentences:
        for m in rx.finditer(s):
            out |= {w.lower() for w in m.groups()}
    return {w for w in out if w != project.lower() and len(w) > 2}


def _argparse_def(src: _Src, rel: str, line: int, q: str) -> tuple[str, str] | None:
    """(the parser or group it is added to, its help) when the line adds the flag to an argparse parser."""
    if not rel.endswith(".py"):
        return None
    st = src.stmt_at(rel, line)
    call = st.value if isinstance(st, ast.Expr) else None
    if not (isinstance(call, ast.Call) and getattr(call.func, "attr", "") == "add_argument"
            and any(isinstance(a, ast.Constant) and a.value == q for a in call.args)):
        return None
    recv = call.func.value.id if isinstance(call.func.value, ast.Name) else ""
    hlp = next((k.value for k in call.keywords if k.arg == "help"), None)
    try:
        h = hlp.value if isinstance(hlp, ast.Constant) else ast.unparse(hlp) if hlp is not None else ""
    except Exception:  # noqa: BLE001
        h = ""
    return recv, str(h)


def _launcher_use(repo: Any, src: _Src, q: str, sd: list[str], ed: list[str], inside_whole: int,
                  inside_read: int = 0, sentences: list[str] | None = None) -> str:
    """'Launcher / server use' of a name the shared launcher / server scripts have: a flag's parsers (with their help),
    and up to TRACE_HITS of its places traced - for a flag the parser of the command the report gives it with first, then
    the places whose value reaches the engine's arguments, environment or process, then those that read it."""
    hits: list[dict] = []
    for d in sd:
        try:
            hits += [h for h in repo.grep(q, d, fixed=True, max_hits=400)["hits"] if h not in hits]
        except Exception:  # noqa: BLE001
            pass
    whole = _whole(q)
    hits = [h for h in hits if h["file"].endswith(SCRIPT_EXT) and not TEST_PATH_RE.search(h["file"])
            and whole.search(h.get("text") or "")]

    if q.startswith('"'):          # a config key read at the top of a config (cfg.get("gpu"), not cfg["vision"].get("gpu"))
        k = re.escape(_bare(q))
        reads = re.compile(rf"""(?<![\w\])])\w+\s*(?:\.get\(\s*["']{k}["']|\[\s*["']{k}["']\s*\](?!\s*=[^=]))""")
    else:
        reads = re.compile(r"add_argument|getenv|environ|\.get\(|\[")

    def code_text(h) -> str:                        # a Python line without its inline comment
        t = h.get("text") or ""
        return re.sub(r"\s{2,}#\s.*$", "", t) if h["file"].endswith(".py") else t

    def is_code(h) -> bool:                         # the name in code, not in a comment or a docstring
        t = code_text(h)
        if not whole.search(t) or t.lstrip().startswith(("#", "//", "*", "/*")):
            return False
        st = src.stmt_at(h["file"], h["line"]) if h["file"].endswith(".py") else None
        return not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant))
    best: dict[tuple, tuple] = {}                   # one place per function (per parser for a flag): its best line
    for h in hits:
        py = h["file"].endswith(".py")
        key = (h["file"], (src.func_at(h["file"], h["line"]) or (0,))[0]) if py else (h["file"],)
        adef = _argparse_def(src, h["file"], h["line"], q) if py and q.startswith("-") else None
        if adef:
            key = (h["file"], h["line"])                # each parser's own flag (launch, serve, tune ...)
        c = (h, adef, is_code(h))
        p = best.get(key)
        if p is None or (not c[2], not reads.search(code_text(h)), h["line"]) < \
                (not p[2], not reads.search(code_text(p[0])), p[0]["line"]):
            best[key] = c
    places = sorted(best.values(), key=lambda c: (not c[0]["file"].endswith(".py"), not c[2], c[0]["file"],
                                                  c[0]["line"]))[:60]
    if not places:
        return ""
    words = _command_words(sentences or [], q, repo.name.split("/")[-1])

    def fit(h, adef) -> int:                        # the parser of the report's own command ("strata launch")
        if not adef or not words:
            return 0
        toks = set(re.split(r"[/_.\-]+", h["file"].lower())) | set(adef[0].lower().split("_"))
        return len(toks & words)
    alone = re.compile(r"""["']""" + re.escape(q) + r"(?![\w-])") if not q.startswith('"') else re.compile(re.escape(q))
    lvl = [_engine_level(src.where(h["file"], h["line"]) + " " + src.context(h["file"], h["line"])) for h, _, _ in places]

    def rank(i):
        h, adef, code = places[i]
        return (not code, not alone.search(code_text(h)), -fit(h, adef), not reads.search(code_text(h)))
    pre = sorted(range(len(places)), key=lambda i: (*rank(i), lvl[i], i))[:TRACE_CANDIDATES]
    traced = []
    for i in pre:
        h, adef, code = places[i]
        try:
            t = _trace(src, h["file"], h["line"], q)
        except Exception as e:  # noqa: BLE001
            t = f"{h['file']}:{h['line']}: {_cut(h.get('text'), 130)} (not traced: {type(e).__name__})"
        traced.append((*rank(i), min(lvl[i], _engine_level(t)), lvl[i], i, t))
    traced.sort(key=lambda x: x[:-1])                                   # the best places first
    pick = traced[:TRACE_HITS] if traced[0][4] <= 1 else traced[:1]   # a second one only when on the engine's path
    text = "\n".join("  - " + t for *_, t in pick)
    if len(text) > TRACE_CHARS:
        text = text[:TRACE_CHARS - 4].rstrip() + " ..."
    lines = []
    defs = [(h, a) for h, a, _ in places if a]
    if defs:
        lines.append(f"Parsed as a command-line option at ({len(defs)}): " + "; ".join(
            f"{h['file']}:{h['line']} ({a[0] or '?'}.add_argument: \"{_cut(a[1], 70)}\")" for h, a in defs[:4])
            + (f"; ... ({len(defs) - 4} more)" if len(defs) > 4 else ""))
    more = "+" if len(places) >= 60 else ""
    lines += [f"Launcher / server use ({len(places)}{more} place(s) in its scripts, {len(pick)} traced: the lines around "
              "the hit, then where the value goes):", text]
    passed = _passed_on(text, q, repo, ed) if ed else ""
    if passed:
        lines.append(passed)
    if ed and not q.startswith('"'):
        if not inside_whole:
            lines.append(f"    `{q}` itself has no hit in the engine's own folders: the engine's code does not parse or "
                         "read it under this name.")
        elif not inside_read:
            lines.append(f"    `{q}` is in the engine's own folders only in text (no \"{q}\" the code parses or reads).")
    return "\n".join(lines)


def _cmake_lines(repo: Any, src: _Src, q: str, ed: list[str]) -> str:
    """A -D build option's CMake lines: its option() line, then the lines that switch something for the engine (the
    engine folder's name nearby) - each with the two lines after it."""
    hits: list[dict] = []
    for glob in ("CMakeLists.txt", "*.cmake"):
        try:
            hits += [h for h in repo.grep(q, ".", glob=glob, fixed=True, max_hits=80)["hits"] if h not in hits]
        except Exception:  # noqa: BLE001
            pass
    if not hits:
        return f"Build files (CMake): no `{q}`"
    keys = {d.rstrip("/").split("/")[-1] for d in ed if d not in (".", "")}

    def near_engine(h) -> bool:
        ls = src.lines(h["file"])
        return any(k and k in " ".join(ls[max(0, h["line"] - 2):h["line"] + 3]) for k in keys)
    opt = re.compile(r"\boption\s*\(\s*" + re.escape(q) + r"\b")
    depth = lambda h: (h["file"].count("/"), h["file"], h["line"])     # noqa: E731 - the top CMakeLists.txt first
    options = sorted((h for h in hits if opt.search(h["text"])), key=depth)[:1]
    pick = options + sorted((h for h in hits if not opt.search(h["text"])),
                            key=lambda h: (not near_engine(h), *depth(h)))[:3 - len(options)]
    return (f"Build files (CMake), {len(hits)} line(s) with `{q}`: "
            + "; ".join(f"{h['file']}:{h['line']}: {src.context(h['file'], h['line'], before=0, after=2, width=120)}"
                        for h in pick))


VERSION_PROMPT = VERIFY_MARK + """ A research report for the task below names the settings listed after it \
(command-line flags, environment variables, build options, config keys). Decide for each one, from the evidence given \
with it - the project's source code AT THE USER'S VERSION and the research's sources that mention it - what it is:
- "this-version": a setting of the program or engine the task is about, at the user's version: the code in that \
engine's folders handles it; or the shared launcher / server code applies it when it runs that engine - for every \
engine or for this one - as its "Launcher / server use" lines show: it passes the value on to that engine (in its \
arguments, its environment or a request) and the engine's own code reads what is passed, or the launcher / server acts \
on it itself (it picks the cards or the model, sets the engine's arguments or environment, runs a tuner, prints a plan);
- "other-engine": it exists in the same project at that version, but only outside the engine's folders (another \
engine, a tool, an app, the docs) - not an option of the engine the task is about;
- "launcher-only": only the shared launcher or server code (or code several engines share) has it, and the code shown \
neither passes it on to this engine nor acts on it when this engine runs: it is only parsed or stored, it is another \
engine's option the launcher also handles, or the engine's own code ignores, rejects or never parses what is passed on;
- "other-version": it appears only in another version's code or docs (newer or older), not at the user's version;
- "other-project": it belongs to another program (llama.cpp, vLLM, a fork, ...);
- "not-found": no evidence has it;
- "generic": not specific to any program (an operating-system, driver or general build setting).
Then say how the report presents it ("use"): "recommended" - as a setting to use or try with the program the task \
is about, at the user's version; "described" - as part of that program, without recommending it (its default, \
"leave it off", "do not add", how the program works); "attributed" - clearly as another program's, engine's or \
version's, not this program's. A quoted name such as "gpu" is a key of a JSON config file. A short name the evidence \
gives as the end of a longer one (SLOT_KEEP of STRATA_DS4_SLOT_KEEP) is judged by the longer name; a -D build option by \
its CMake lines and the code it switches. Code evidence outranks web pages and docs; a source marked OTHER VERSION is \
not evidence for the user's version.

<task>
{task}
</task>
{versions}
<settings>
{items}
</settings>

For each setting output one line of JSON (JSON Lines, nothing else):
{{"name": "<as listed>", "kind": "this-version|other-engine|launcher-only|other-version|other-project|not-found|generic", \
"use": "recommended|described|attributed", "note": "<at most 20 words: where it really belongs, or what the user's \
version has instead>"}}"""


def _settle_dirs(e1: dict, e2: dict) -> dict:
    """Two engine_dirs answers -> the engine's folders (both name them), the shared ones, the disputed ones."""
    # two independent answers, only the folders both name (round 3: one answer took in the Qwen engine's
    # src/program, the other did not); no overlap -> the first answer
    both = [d for d in e1["dirs"] if d in e2["dirs"]]
    keep = both or e1["dirs"]
    # 10-28 (p4s6 o01, a whole-project question: one answer took only the DeepSeek engine, the other every
    # engine and src/core, kernels, prefill; the overlap made src/core's --kv-resident "another engine"): the
    # folders only one answer names are disputed, and a name found there is not flagged
    # 10-29 (p4s6 o02, Fix 1b): also when the other answer calls that folder shared - src/program (the Qwen engine) was
    # one answer's engine folder and the other's "shared", so its STRATA_SPLIT_UNIFORM read as launcher-only
    disputed = [d for d in dict.fromkeys(e1["dirs"] + e2["dirs"]) if d not in keep]
    shared = [d for d in dict.fromkeys(e1.get("shared", []) + e2.get("shared", [])) if d not in keep and d not in disputed]
    return {**e1, "dirs": keep, "shared": shared, "disputed": disputed, "answers": [e1["dirs"], e2["dirs"]]}


def _code_parts(repo: Any, q: str, e: dict, src: "_Src | None",
                sentences: list[str] | None = None) -> tuple[list[str], bool]:
    """The code evidence of one name, searched as q, in one clone: its hits in the engine's own folders, in the shared
    launcher / server folders (with the launcher / server use traced), in disputed folders and elsewhere; a -D build
    option's CMake lines. -> (lines, found in a disputed folder)"""
    parts: list[str] = []
    try:
        g = repo.grep(q, ".", fixed=True, max_hits=400)      # a config key: its quoted string literal
    except Exception as ex:  # noqa: BLE001
        return [f"Code at {repo.name}@{repo.ref}: search failed ({ex})"], False
    ed = e.get("dirs") or []
    sd = e.get("shared") or []
    dd = e.get("disputed") or []
    where = f"the engine's own folders ({', '.join(ed)})" if ed else "the repository"
    if not g["total"]:
        return [f"Code at {repo.name}@{repo.ref} (the user's version): no hits anywhere"], False
    hits = g["hits"]
    if ed and g["more"]:
        # 10-28 (p4s6 o01): the repository-wide search keeps its first 400 hits, and the project's bench results
        # filled them (--expert-cache: 380 files under bench/results), so src/program's hit was lost and the
        # engine's own option read as "another engine" - its own, the shared and the disputed folders are
        # searched on their own
        for d in ed + sd + dd:
            try:
                hits = hits + [h for h in repo.grep(q, d, fixed=True, max_hits=50)["hits"] if h not in hits]
            except Exception:  # noqa: BLE001
                pass
    inside = [h for h in hits if not ed or _in_dirs(h["file"], ed)]
    shared_hits = [h for h in hits if ed and sd and not _in_dirs(h["file"], ed) and _in_dirs(h["file"], sd)]
    disputed_hits = [h for h in hits if ed and dd and not _in_dirs(h["file"], ed + sd) and _in_dirs(h["file"], dd)]
    outside = [h for h in hits if ed and not _in_dirs(h["file"], ed) and h not in shared_hits and h not in disputed_hits]
    if shared_hits:
        parts.append(f"Shared launcher / server code ({', '.join(sd)}), which parses options for several engines: "
                     f"{len(shared_hits)} hit(s): " + "; ".join(f"{h['file']}:{h['line']}: {h['text'][:100]}"
                                                             for h in shared_hits[:3]))
        # 10-29 (Fix 1b): whether the launcher / server passes it on to this engine or acts on it - traced, unless the
        # engine's own code reads the name itself ("--x" / "X" as a string it parses or reads: this version's anyway; a
        # mention in a message or a comment is not that); a config key is always traced (the engine never reads the
        # config file)
        inside_whole = len([h for h in inside if _whole(q).search(h["text"])]) if ed else 0
        quoted = re.compile(r"""["']""" + re.escape(_bare(q)) + r"""["']""")
        inside_read = len([h for h in inside if quoted.search(h["text"])]) if ed else 0
        if src is not None and ed and (q.startswith('"') or not inside_read):
            use = _launcher_use(repo, src, q, sd, ed, inside_whole, inside_read, sentences)
            if use:
                parts.append(use)
    disputed = bool(disputed_hits)
    if disputed_hits:
        parts.append(f"Folders that may also be the engine's ({', '.join(dd)}): {len(disputed_hits)} hit(s): "
                     + "; ".join(f"{h['file']}:{h['line']}: {h['text'][:100]}" for h in disputed_hits[:3]))
    dirs: dict[str, int] = {}
    for h in outside:
        top = "/".join(h["file"].split("/")[:2])
        dirs[top] = dirs.get(top, 0) + 1
    more = "+" if g["more"] else ""
    line_in = "; ".join(f"{h['file']}:{h['line']}: {h['text'][:100]}" for h in inside[:3])
    line_out = "; ".join(f"{h['file']}:{h['line']}: {h['text'][:100]}" for h in outside[:3])
    parts.append(f"Code at {repo.name}@{repo.ref} (the user's version) - in {where}: {len(inside)}{more} hit(s)"
                 + (f": {line_in}" if line_in else "")
                 + (f" | elsewhere: {len(outside)}{more} hit(s) ("
                    + ", ".join(f"{k} {v}" for k, v in sorted(dirs.items(), key=lambda x: -x[1])[:5]) + ")"
                    + (f": {line_out}" if line_out else "") if ed else ""))
    return parts, disputed


def version_evidence(names: list[str], body: str, store: Any, code: Any, eng: dict) -> dict:
    """The evidence version_check sends for each name (no model call): {"items": [text per name sent], "sent": [names],
    "unsettled": {names found in a disputed folder}, "constants": {name: where it is defined}, "long": {short: long}}."""
    srcs = [(s.idx, s.title or "", s.url or "", (s.page_text or "") + "\n" + "\n".join(s.snippets[:3]))
            for s in (store.all_sources() if store is not None else [])]
    code = list(code or [])
    src_of = {}
    for repo in code:
        e = eng.get(repo.name, {})
        src_of[repo.name] = _Src(repo.root, e.get("shared") or []) if getattr(repo, "root", None) else None
    items, sent, unsettled, constants, longs = [], [], set(), {}, {}
    for n in names:
        q = _search_name(n)
        # 10-29 (Fix 1b): the whole-name hits of an environment-style name - a constant of the code that nothing reads
        # as a setting is not sent; a short name that never occurs on its own is judged by its long form
        long = None
        if ENV_RE.fullmatch(n) and code:
            consts, alone, sub = [], False, []
            for repo in code:
                try:
                    g = repo.grep(n, ".", fixed=True, max_hits=400)
                except Exception:  # noqa: BLE001
                    consts.append(None)
                    alone = True
                    continue
                sub += g["hits"]
                w = [h for h in g["hits"] if _whole(n).search(h["text"])]
                if not w and g["more"]:
                    try:
                        w = repo.grep(r"(^|[^A-Za-z0-9_])" + n + r"([^A-Za-z0-9_]|$)", ".", max_hits=50)["hits"]
                    except Exception:  # noqa: BLE001
                        w = [{"file": "?", "line": 0, "text": n}]
                alone = alone or bool(w)
                if w:
                    consts.append(None if g["more"] else _not_a_setting(w, n))
            if consts and all(consts):
                constants[n] = consts[0]
                continue
            if sub and not alone:
                # a long form the report names too, or one in the engine's, shared or disputed folders (not one only
                # in vendored code: AVX512_BF16 is not GGML_AVX512_BF16)
                where = [d for e in eng.values() for k in ("dirs", "shared", "disputed") for d in e.get(k) or []]
                forms = [f for f in _long_forms(n, sub, names) if f in names or any(
                    _in_dirs(h["file"], where) and _whole(f).search(h["text"]) for h in sub)]
                long = forms[0] if forms else None
                if long:
                    longs[n] = long
        parts = [f"### {n}"]
        if q != n:
            parts.append(f"Build option: searched without the -D, as `{q}` (the name CMake and the code use)")
        if long:
            others = forms[1:3]
            parts.append(f"Short form: `{n}` does not occur on its own in the code at the user's version; it is the end of "
                         f"`{long}`{' (named in the report too)' if long in names else ''}"
                         + (f" (also of {', '.join('`' + o + '`' for o in others)})" if others else "")
                         + f" - judge it by `{long}`. The code evidence below is for `{long}`:")
            q = long
        disputed = False
        for repo in code:
            e = eng.get(repo.name, {})
            p, d = _code_parts(repo, q, e, src_of.get(repo.name), _sentences_with(body, n, 4))
            parts += p
            disputed = disputed or d
            if q != n and CMAKE_RE.fullmatch(n) and src_of.get(repo.name) is not None:
                parts.append(_cmake_lines(repo, src_of[repo.name], q, e.get("dirs") or []))
        if disputed:
            unsettled.add(n)
        mention = [(i, t, u) for i, t, u, txt in srcs if n in txt or n in t][:5]
        if mention:
            parts.append("Sources mentioning it: " + "; ".join(f"[{i}] {t[:90]} ({u[:110]})" for i, t, u in mention))
        else:
            parts.append("Sources mentioning it: none of the research's sources")
        parts += [f"Report: \"{s}\"" for s in _sentences_with(body, n)]
        items.append("\n".join(parts))
        sent.append(n)
    return {"items": items, "sent": sent, "unsettled": unsettled, "constants": constants, "long": longs}


def version_check(llm: Callable[[str], str], task: str, body: str, store: Any, code: Any = None,
                  pins: dict | None = None, max_names: int = 120) -> dict:
    """code: (repo object with .grep) list for the pinned clones; store: the evidence store (sources mentioning a
    name). One or more model calls (about 40 names each)."""
    names = setting_names(body)[:max_names]
    if not names:
        return {"names": [], "results": []}
    # 10-27 replay: without knowing which folder is the engine, another engine's flags (same project) read as "this
    # version" - so first the engine's folders, then every name's hits inside and outside them
    eng = {}
    for repo in code or []:
        try:
            eng[repo.name] = _settle_dirs(engine_dirs(llm, task, repo), engine_dirs(llm, task, repo))
        except Exception as e:  # noqa: BLE001
            eng[repo.name] = {"dirs": [], "error": str(e)[:200]}
    ev = version_evidence(names, body, store, code, eng)
    items, unsettled = ev["items"], {_bare(n) for n in ev["unsettled"]}
    versions = ""
    if pins:
        versions = "\nThe user's versions (from the task or the setup profile): " + ", ".join(
            f"{k} {v}" for k, v in pins.items()) + "\n"
    results, raw = [], []
    for start in range(0, len(items), 40):
        out = llm(VERSION_PROMPT.format(task=task, versions=versions, items="\n\n".join(items[start:start + 40])))
        got = _jsonl(out)
        if not got:
            raw.append((out or "")[:2000])
        results += [d for d in got if isinstance(d, dict) and d.get("name")]
    for r in results:
        if r.get("kind") in ("other-engine", "launcher-only") and _bare(str(r["name"])) in unsettled:
            r["kind"], r["was"] = "unsure", r.get("kind")      # found in a disputed folder: not flagged
    if not any(e.get("dirs") for e in eng.values()):
        # 10-28 (bundle write replays, no clone): with no engine folders read from the code the model took "docs only,
        # no engine code shown" for another engine - neither kind can be told without the code, so neither is flagged
        for r in results:
            if r.get("kind") in ("other-engine", "launcher-only"):
                r["kind"], r["was"] = "unsure", r.get("kind")
    # 10-29 (Fix 1b): constants of the code (no setting at all) were not sent; they are listed, never flagged
    results += [{"name": n, "kind": "not-a-setting", "use": "described",
                 "note": f"a constant of the code ({w}), not a flag, variable or config key"}
                for n, w in ev["constants"].items()]
    return {"names": names, "results": results, "raw": raw or None, "engine_dirs": eng,
            "long_forms": ev["long"] or None}


BAD_KINDS = {"other-engine": "another engine of the same project", "other-version": "another version",
             "other-project": "another program", "not-found": "no source of this research",
             "launcher-only": "accepted by the shared launcher, but not read by this engine's code"}


def _use(r: dict) -> str:
    u = str(r.get("use") or "").lower()
    if u in ("recommended", "described", "attributed"):
        return u
    return "recommended" if r.get("recommended") is True else "attributed"   # the 10-27 output format


def version_flagged(res: dict, uses: tuple = ("recommended", "described")) -> list[dict]:
    """10-28 (A8): names presented as this program's - recommended, or described as its own - not only recommended."""
    return [r for r in (res or {}).get("results") or [] if _use(r) in uses and r.get("kind") in BAD_KINDS]


def version_marks(body: str, res: dict, versions: str = "") -> list[tuple[str, str]]:
    """The first recommending sentence per section for each flagged name."""
    items = []
    for r in version_flagged(res):
        n = r["name"]
        txt = (f"`{n}` - {BAD_KINDS[r['kind']]}{' (' + clean_mark(r.get('note'), 160) + ')' if r.get('note') else ''}; "
               + (f"unverified for {versions or 'your version'}" if _use(r) == "recommended"
                  else f"not an option of {versions or 'your version'} as far as the code shows"))
        section = None
        for line in strip_marks(body).split("\n"):
            if line.startswith("## "):
                section = line
                continue
            if n in line and not line.lstrip().startswith("#") and section != "done:" + str(section):
                sent = next((s for s in re.split(r"(?<=[.!?])\s+", line) if n in s), line)
                items.append((sent, mark("Version check", txt)))
                section = "done:" + str(section)
    return items


def version_section(res: dict, versions: str = "") -> str:
    if res is None:
        return "## Version check\n\nThe version check did not complete; the settings named in this report were not checked."
    bad = version_flagged(res)
    if not bad:
        return ""
    rec = [r for r in bad if _use(r) == "recommended"]
    desc = [r for r in bad if _use(r) == "described"]
    lines = ["## Version check", "",
             f"{len(bad)} setting{'s' if len(bad) != 1 else ''} this report presents as part of {versions or 'your version'} "
             f"{'are' if len(bad) != 1 else 'is'} not {'options' if len(bad) != 1 else 'an option'} of it as far as the "
             "code and the sources show (marked where they first appear in each section above):", ""]
    for head, group in (("Recommended:", rec), ("Described as its own:", desc)):
        if group:
            lines.append(head)
            for r in group:
                lines.append(f"- `{r['name']}`: {BAD_KINDS[r['kind']]}"
                             + (f" - {clean_mark(r.get('note'), 200)}" if r.get("note") else ""))
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ consistency pass
CONSIST_PROMPT = VERIFY_MARK + """ Below are a research task and the report written for it. Find statements in \
different parts of the report that CONTRADICT each other - above all between the Answer, the Key findings or an \
action list and the detailed sections (one place recommends a setting that another explains has no effect on this \
setup; two different defaults, figures or limits for the same thing; a step called lossless in one place and \
approximate in another). Also a RULE stated in one place - a default that depends on the hardware, a threshold, a \
guard that needs one GPU, a size cap - that, applied to this setup (the task and the setup facts below, and the \
report's own figures), gives another outcome than a claim about this setup elsewhere: work out what the rule gives \
here. Ignore different wording, and statements about different conditions that are both right - but only when the \
condition really is different on this setup.

For each contradiction quote both statements exactly, decide which one the report's own evidence supports (the code \
quote, the measured figure, the more specific source, the detailed explanation) - "a", "b", or "unclear" - and give \
the correction for the other one.

<task>
{task}
</task>
{facts}
<report>
{report}
</report>

Reply with JSON only: {{"contradictions": [{{"quote_a": "...", "quote_b": "...", "right": "a|b|unclear", "why": \
"<one sentence>", "fix": "<the corrected statement for the wrong one, or empty>"}}]}}"""

# 10-28 (A8 (3), K4 missed: the DSpark section's rule "not loaded when the experts exceed 1.5x the VRAM" against the
# action list's "auto loads the drafter" - a rule against a claim about this PC, 300 lines apart): per setting the
# Answer / action list recommends, every sentence of the report about it in one small prompt
# 10-29 (K4 still missed after A8, replay b-f5c-full: the --dspark prompt held the 1.5x rule, the "auto loads the 8 GB
# drafter" claim and the task's 138 GB / 16 + 8 GB, and the model still did not apply the rule): rule first, and the
# evaluation is part of the reply - per setting the model lists each rule / threshold / condition the sentences state,
# evaluates it on the task's own numbers with the arithmetic written out, and only then compares the outcome with each
# claim about this setup. Sentences carry ids (S1, S2, ...), so the quotes come back exact and the reply stays short.
CONSIST_FOCUS_PROMPT = VERIFY_MARK + """ A research report recommends the settings below for the user's setup. For \
each, every sentence of the report about it is listed with an id (S1, S2, ...) and the section it is in. Check \
whether these sentences agree about what the setting does ON THIS SETUP: the setup the task describes (its hardware, \
versions, settings and measured numbers come first), then the setup facts below for what the task does not say.

For each setting, work in this order (the reply has a field for each step):
1. RULES. List each rule the sentences state about the setting: a default that depends on the hardware, a \
threshold, a condition (only when, unless, if ... exceeds ...), a guard (one GPU only), a cap or limit. Evaluate it \
on this setup: name each input with its number and where the number comes from (the task, the setup facts, or a \
sentence id), write the arithmetic out with the numbers (for example "1.5 x 20 GB = 30 GB; 100 GB > 30 GB"), say \
whether the condition holds here (yes, no, or unknown when no number for it is given anywhere) and what the rule \
therefore gives on this setup.
2. CLAIMS. Only then compare that outcome with each sentence that claims what the setting does on this setup, what \
the user has now, or what changing it gains here. A claim that disagrees with the outcome is a conflict even when \
neither sentence mentions the other: such a conflict often shows only once the rule is applied to the user's \
numbers. A test the task says the user tried once is not the current state unless the task says so. Decide which \
one the report's own evidence supports (the code quote, the measured figure, the more specific source).
3. OTHER CONFLICTS. Also list two sentences whose claims about this setup contradict each other directly.
Different wording is not a conflict, nor are statements about different conditions that are both right - but a \
condition is different only when it does not hold on this setup.

<task>
{task}
</task>
{facts}
<settings>
{items}
</settings>

Reply with JSON only. Use the sentence ids; at most 3 rules per setting ("rules": [] when it states none); a claim \
that agrees needs only its id and "agrees": "yes".
{{"settings": [{{"setting": "...", "rules": [{{"rule": "S<id>", "condition": "<the rule in a few words>", "inputs": \
"<each number and its source>", "arithmetic": "<the calculation, written out>", "holds": "yes|no|unknown", \
"outcome": "<what the rule gives on this setup>", "claims": [{{"claim": "S<id>", "agrees": "yes|no", "right": \
"rule|claim|unclear", "why": "<one sentence>", "fix": "<the corrected claim, or empty>"}}]}}], "conflicts": \
[{{"quote_a": "S<id>", "quote_b": "S<id>", "right": "a|b|unclear", "why": "<one sentence>", "fix": "<the corrected \
statement for the wrong one, or empty>"}}]}}]}}"""
FOCUS_PER_CALL = 5            # settings per focused call (10 settings at most -> 2 calls, as before)
ACTION_HEAD_RE = re.compile(r"(?i)answer|key findings|action|plan|tier a|tonight|recommend|try first|summary|ranked")


def _name_variants(name: str) -> list[str]:
    """'--dspark' -> dspark; 'DS4_LAYER_MAJOR' -> layer major / layer-major / layer_major (prefixes dropped)."""
    n = name.strip('"').lstrip("-")
    n = re.sub(r"^(?:DS4|STRATA|GGML|LLAMA|CUDA)_", "", n)
    words = [w for w in re.split(r"[_-]+", n.lower()) if w]
    out = {name.lower(), n.lower()}
    if len(words) > 1:
        out |= {" ".join(words), "-".join(words), "_".join(words)}
    return sorted((v for v in out if len(v) >= 4), key=len, reverse=True)


def action_settings(body: str, max_n: int = 10) -> list[str]:
    """The settings named in the Answer, Key findings and action-list sections, in order."""
    secs = re.split(r"(?m)^(?=## )", strip_marks(body))
    picked = "\n".join(s for s in secs if ACTION_HEAD_RE.search(s.split("\n", 1)[0]))
    return setting_names(picked)[:max_n]


COMMON_WORDS = {"experts", "expert", "split", "cache", "threads", "thread", "layers", "layer", "chunk", "prefill", "store",
                "context", "batch", "model", "size", "mode", "memory", "prompt", "decode", "draft", "drafter", "plan",
                "tune", "set", "auto", "verbose", "port", "host", "gpus", "devices", "device", "slots", "slot", "ahead",
                "vision", "spec", "quant", "engine", "server", "serve", "stream", "pcie"}
RULE_STRONG_RE = re.compile(r"(?i)\b(exceeds?|threshold|not loaded|ignored|single[- ]device|one gpu|only on|only when|"
                            r"disabl\w*|guard\w*|capped|refuses?)\b|×|\d\s*x\b|>|<")
RULE_CUE_RE = re.compile(r"(?i)\b(only|when|if|unless|above|below|default|auto|cap|requires?|single|never|always)\b")


def sentences_about(body: str, name: str, max_n: int = 16, per_section: int = 3, rows: bool = False) -> list:
    """The report's sentences about a setting, spread over its sections (2 each at most): the action sections' first,
    then sentences that state a rule (a threshold, a guard; then a condition or default), then the rest. A one-word form of the name
    ('dspark') counts unless it is a common word of these reports ('experts', 'split', 'cache'). rows=True: (the
    shown line, the sentence as the report has it) pairs, so a reply's sentence id maps back to an exact quote."""
    text = strip_marks(body)
    vs = [v for v in _name_variants(name) if " " in v or "-" in v or "_" in v or v not in COMMON_WORDS]
    cands, sec = [], ""
    for line in text.split("\n"):
        if line.startswith("## "):
            sec = line[3:80]
            continue
        if line.lstrip().startswith("#"):
            continue                               # subheadings are not statements
        for sent in re.split(r"(?<=[.!?])\s+", line):
            low = sent.lower()
            if len(sent) > 20 and any(v in low for v in vs):
                prio = (0 if ACTION_HEAD_RE.search(sec) else 1 if RULE_STRONG_RE.search(sent)
                        else 2 if RULE_CUE_RE.search(sent) else 3)
                cands.append((prio, len(cands), sec, sent))
    out, per = [], {}
    for prio, k, sec, sent in sorted(cands):
        if per.get(sec, 0) >= per_section:
            continue
        per[sec] = per.get(sec, 0) + 1
        out.append((k, f"[{sec}] {clean_mark(sent, 400)}", sent))
        if len(out) >= max_n:
            break
    return [(t, s) if rows else t for _, t, s in sorted(out)]


def consistency_check(llm: Callable[[str], str], task: str, body: str, facts: str = "", focus: bool = True) -> dict:
    fb = f"\n<user_setup>\n{facts}\n</user_setup>\n" if facts else ""
    text = llm(CONSIST_PROMPT.format(task=task, report=body, facts=fb))
    items = _json(text, "contradictions")
    res = {"contradictions": items, "raw": None if items is not None else (text or "")[:4000]}
    if not focus:
        return res
    names = [n for n in action_settings(body) if len(sentences_about(body, n)) >= 2]
    found, rule_checks, unparsed = [], [], 0
    for start in range(0, len(names), FOCUS_PER_CALL):
        block, ids = focus_block(body, names[start:start + FOCUS_PER_CALL])
        got, rc = focus_reply(llm(CONSIST_FOCUS_PROMPT.format(task=task, facts=fb, items=block)), ids)
        if got is None:
            unparsed += 1
            continue
        found += got
        rule_checks += rc
    seen = {(_norm_map(str(c.get("quote_a") or ""))[0], _norm_map(str(c.get("quote_b") or ""))[0])
            for c in (items or []) if isinstance(c, dict)}
    for c in found:
        k = (_norm_map(str(c.get("quote_a") or ""))[0], _norm_map(str(c.get("quote_b") or ""))[0])
        if k not in seen and (k[1], k[0]) not in seen:
            seen.add(k)
            c.setdefault("step", "focused")
            res["contradictions"] = (res["contradictions"] or []) + [c]
    res["focused_settings"] = names
    res["rule_checks"] = rule_checks           # every rule evaluated, with or without a conflict (for the reader)
    if unparsed:
        res["focused_unparsed"] = unparsed
    return res


def focus_block(body: str, names: list[str]) -> tuple[str, dict[str, str]]:
    """The <settings> block of one focused call: per setting its sentences, each with an id (S1, S2, ...; a sentence
    listed under two settings keeps one id) -> (block, {id: the sentence as the report has it})."""
    ids: dict[str, str] = {}
    by_raw: dict[str, str] = {}
    parts = []
    for n in names:
        lines = []
        for shown, raw in sentences_about(body, n, rows=True):
            sid = by_raw.get(raw)
            if sid is None:
                sid = by_raw[raw] = f"S{len(by_raw) + 1}"
                ids[sid] = raw
            lines.append(f"- {sid} {shown}")
        parts.append(f"### {n}\n" + "\n".join(lines))
    return "\n\n".join(parts), ids


_SID_RE = re.compile(r"\W*S(\d+)\b")


def _sentence(v: Any, ids: dict[str, str]) -> str:
    """A reply's 'S12' (or '[S12]', 'S12: ...') -> that sentence of the report ('' for an unknown id); any other text
    is taken as a quote."""
    s = str(v or "").strip()
    m = _SID_RE.match(s)
    return ids.get(f"S{m.group(1)}", "") if m else s


def _yes(v: Any) -> bool:
    return v is True or str(v).strip().lower() in ("yes", "true", "holds")


def _no(v: Any) -> bool:
    return v is False or str(v).strip().lower() in ("no", "false", "disagrees")


_CMP_RE = re.compile(rf"(?<![\w.$/=–-])(?P<l>{_EQ_EXPR})\s*(?P<op>>=|<=|≥|≤|>|<)\s*~?\s*(?P<r>{_EQ_EXPR})"
                     r"(?!\s*[-×*÷/+−^x]\s*[\d(])")         # the right side whole ("1.5 x (24 GB - 5.9 GB)")


def recheck_evaluation(text: str) -> dict:
    """The written-out arithmetic of a rule's evaluation recomputed in code (no model): its equations (as Fix 3 checks
    a report's) and its comparisons ("138 GB > 1.5 x 18 GB"). Returns the counts and the steps that do not hold."""
    text = str(text or "")
    eqs = explicit_equations(text)
    wrong = [f"{e['formula']} = {e['stated']} (recomputed {fmt_num(e['computed'])})"
             for e in eqs if e.get("status") == "wrong"]
    n_eq = len(eqs)
    n_cmp = 0
    for m in _CMP_RE.finditer(text):
        a, b = _eq_side(m.group("l")), _eq_side(m.group("r"))
        if a is None or b is None:
            continue
        n_cmp += 1
        x, y = (a[0], b[0]) if a[2] and b[2] else (a[1], b[1])
        op = {"≥": ">=", "≤": "<="}.get(m.group("op"), m.group("op"))
        ok = {">": x > y, "<": x < y, ">=": x >= y, "<=": x <= y}[op]
        if not ok:
            wrong.append(f"{m.group(0).strip()} does not hold")
    return {"equations": n_eq, "comparisons": n_cmp, "wrong": wrong}


def focus_reply(text: str, ids: dict[str, str]) -> tuple[list[dict] | None, list[dict]]:
    """One focused reply -> (contradictions, rule checks); (None, []) when it holds no usable JSON.
    A rule against a claim: quote_a = the claim, quote_b = the rule, step "rule", with the rule's evaluation; dropped
    when the model could not evaluate the rule here (holds "unknown"); not settled when the evaluation's own arithmetic
    does not recompute. Two sentences against each other: step "focused". A reply in the old shape (a plain
    "contradictions" list) is taken as conflicts."""
    sets = _json(text, "settings")
    if not isinstance(sets, list):
        old = _json(text, "contradictions")
        if not isinstance(old, list):
            return None, []
        sets = [{"setting": "", "conflicts": old}]
    found, checks = [], []
    for s in sets:
        if not isinstance(s, dict):
            continue
        name = str(s.get("setting") or "")
        for r in s.get("rules") if isinstance(s.get("rules"), list) else []:
            rule = _sentence(r.get("rule"), ids) if isinstance(r, dict) else ""
            if not rule:
                continue
            ev = {k: clean_mark(r.get(k), 400) for k in ("condition", "inputs", "arithmetic", "outcome")}
            holds = "yes" if _yes(r.get("holds")) else "no" if _no(r.get("holds")) else "unknown"
            ev["holds"] = holds
            rech = recheck_evaluation(ev["arithmetic"])
            rec = {"setting": name, "rule": rule, **ev, "recheck": rech, "claims": []}
            for c in r.get("claims") if isinstance(r.get("claims"), list) else []:
                claim = _sentence(c.get("claim"), ids) if isinstance(c, dict) else ""
                if not claim or claim == rule:
                    continue
                agrees = "no" if _no(c.get("agrees")) else "yes" if _yes(c.get("agrees")) else "unclear"
                rec["claims"].append({"claim": claim, "agrees": agrees, "why": clean_mark(c.get("why"), 300)})
                if agrees != "no" or holds == "unknown":
                    continue
                right = {"rule": "b", "claim": "a"}.get(str(c.get("right") or "").strip().lower(), "unclear")
                why = str(c.get("why") or "").strip()
                if rech["wrong"]:
                    right = "unclear"
                    why = (why + " " if why else "") + ("(the evaluation's arithmetic does not recompute: "
                                                         + "; ".join(rech["wrong"][:2]) + ")")
                found.append({"setting": name, "quote_a": claim, "quote_b": rule, "right": right, "why": why,
                              "fix": str(c.get("fix") or "").strip(), "step": "rule", "evaluation": ev})
            checks.append(rec)
        for c in s.get("conflicts") if isinstance(s.get("conflicts"), list) else []:
            if not isinstance(c, dict):
                continue
            a, b = _sentence(c.get("quote_a"), ids), _sentence(c.get("quote_b"), ids)
            if a and b and a != b:
                found.append({**c, "setting": str(c.get("setting") or name), "quote_a": a, "quote_b": b,
                              "step": "focused"})
    return found, checks


def consistency_marks(res: dict) -> list[tuple[str, str]]:
    items = []
    for c in (res or {}).get("contradictions") or []:
        if not isinstance(c, dict):
            continue
        if c.get("step") == "rule" and isinstance(c.get("evaluation"), dict):
            items += _rule_marks(c)
            continue
        a, b = str(c.get("quote_a") or ""), str(c.get("quote_b") or "")
        right = str(c.get("right") or "unclear").lower()
        why, fix = clean_mark(c.get("why"), 220), clean_mark(c.get("fix"), 220)
        if right in ("a", "b"):
            wrong, other = (b, a) if right == "a" else (a, b)
            items.append((wrong, mark("Consistency check", f"contradicts \"{clean_mark(other, 120)}\" elsewhere in this "
                                                           f"report, which the evidence supports" + (f"; {fix}" if fix else (f"; {why}" if why else "")))))
        else:
            for q, o in ((a, b), (b, a)):
                items.append((q, mark("Consistency check", f"contradicts \"{clean_mark(o, 120)}\" elsewhere in this "
                                                           f"report; not settled" + (f" ({why})" if why else ""))))
    return items


def _rule_marks(c: dict) -> list[tuple[str, str]]:
    """The marks of a rule-step pair (quote_a = the claim, quote_b = the rule): the claim's mark names the rule by its
    condition (a rule sentence's first words often do not show it) and ends with the evaluation's deciding step
    ("... 138 GB > 27.15 GB"); the whole evaluation is in the section."""
    ev = c["evaluation"]
    claim, rule = str(c.get("quote_a") or ""), str(c.get("quote_b") or "")
    right = str(c.get("right") or "unclear").lower()
    why, fix = clean_mark(c.get("why"), 180), clean_mark(c.get("fix"), 160)
    cond = clean_mark(ev.get("condition"), 90)
    as_rule = (f"the rule elsewhere in this report ({cond})" if cond
               else f"\"{clean_mark(rule, 120)}\" elsewhere in this report")
    as_claim = f"\"{clean_mark(claim, 120)}\" elsewhere in this report"
    arith = clean_mark(ev.get("arithmetic"), 1000)
    if len(arith) > 90:
        arith = "... " + clean_mark(re.split(r";\s*", arith.rstrip("; "))[-1], 86)
    applied = f"; applied to this setup: {arith}" if arith else ""
    said = f"; {fix.rstrip('.')}" if fix else (f"; {why.rstrip('.')}" if why else "")
    if right == "b":
        return [(claim, mark("Consistency check", f"contradicts {as_rule}, which the evidence supports{said}{applied}"))]
    if right == "a":
        return [(rule, mark("Consistency check", f"contradicts {as_claim}, which the evidence supports{said}{applied}"))]
    unsettled = "; not settled" + (f" ({why})" if why else "")
    return [(claim, mark("Consistency check", f"contradicts {as_rule}{unsettled}{applied}")),
            (rule, mark("Consistency check", f"contradicts {as_claim}{unsettled}{applied}"))]


def consistency_section(res: dict) -> str:
    cs = (res or {}).get("contradictions")
    if cs is None:
        return "## Consistency check\n\nThe consistency check did not complete."
    cs = [c for c in cs if isinstance(c, dict)]
    if not cs:
        return ""
    lines = ["## Consistency check", "",
             f"{len(cs)} pair{'s' if len(cs) != 1 else ''} of statements in this report contradict each other (each is "
             "marked above where it stands):", ""]
    for c in cs:
        right = str(c.get("right") or "unclear").lower()
        verdict = {"a": "the first holds", "b": "the second holds"}.get(right, "not settled")
        lines.append(f"- \"{clean_mark(c.get('quote_a'), 160)}\" vs \"{clean_mark(c.get('quote_b'), 160)}\": {verdict}"
                     + (f" - {clean_mark(c.get('why'), 200)}" if c.get("why") else ""))
        ev = c.get("evaluation") if c.get("step") == "rule" else None
        if isinstance(ev, dict):           # the second statement is a rule: how it was applied, for the reader to check
            lines.append("  - The rule applied to this setup: " + "; ".join(
                f"{k} {clean_mark(ev.get(k), 300)}" for k in ("condition", "inputs", "arithmetic", "holds", "outcome")
                if ev.get(k)) + ".")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ Fix 2: critic inline
def critic_marks(crit: dict | None, rows_max: int = 8) -> list[tuple[str, str]]:
    from .advisory import PRIORITY

    issues = [i for i in (crit or {}).get("issues") or [] if isinstance(i, dict) and (i.get("quote") or "").strip()
              and i.get("type") != "gap"]
    issues.sort(key=lambda i: PRIORITY.get(i.get("type"), 5))
    items = []
    for i in issues[:rows_max]:
        hint = (i.get("fix") or "").strip() if i.get("action") == "fix" else (
            f"a search that would settle it: {i.get('query')}" if i.get("query") else "")
        items.append((i["quote"], mark("Check", f"{i.get('type', 'check')}: {(i.get('why') or '').strip()}"
                                                + (f" ({hint})" if hint else ""))))
    return items


def verify_flags(claims: list[dict]) -> dict:
    """The citation check's marks with the checker's note (Fix 2), keyed by verdict for ReportWriter.annotate."""
    return {"unsupported": lambda c: f" **[⚠ not supported by the cited source: {clean_mark(c.get('note'), 200)}]**"
            if c.get("note") else " **[⚠ not supported by the cited source]**",
            "partial": lambda c: f" *[⚠ only partly supported by the cited source: {clean_mark(c.get('note'), 200)}]*"
            if c.get("note") else " *[⚠ only partly supported by the cited source]*"}


# ------------------------------------------------------------------------------------------------ Fix 6: time plan
# measured report-stage times (10-27 rerun, xhigh checks on a 4 h report): outline 196 s (2 calls), a section ~50 s,
# opening 43 s, citation check 12.4 s a claim, setup check 338 s, critic 193 s; the new checks are estimated alike
# (10-27 replays: setup 328-430 s, version 4 calls 275-431 s, arith 262-320 s, consistency 165-347 s, critic 76-193 s,
# a checked claim 9.7 s)
# 10-29 (K4): "consist" 480 -> 900 - the pass with its focused step measured 729 / 747 s on the 10-28 replays b-f5c-full
# / b-f5c-fixes (1 + 2 calls; ~800 s at scale 1.0), and the rule-first focused replies are longer (re-measure)
EST = {"outline": 200, "section": 55, "opening": 60, "cite": 1, "setup": 420, "version": 450, "arith": 330,
       "consist": 900, "critic": 200, "notyet": 300, "claim": 12.5, "files": 60}


def reserve_s(budget_s: float) -> float:
    """The report stage's share of a whole-run budget (Fix 6): 25 %, at least 10 min, at most 75 min, never more than
    40 % (LDR_DEEP_REPORT_RESERVE_S overrides)."""
    v = os.environ.get("LDR_DEEP_REPORT_RESERVE_S", "").strip()
    if v:
        try:
            return max(0.0, float(v))
        except ValueError:
            pass
    return min(max(0.25 * budget_s, 600.0), 4500.0, 0.40 * budget_s)


def wrapup_s(budget_s: float) -> float:
    """Time for the lead's final answer after the research deadline (measured 5.6 min on 10-27)."""
    v = os.environ.get("LDR_DEEP_WRAPUP_S", "").strip()
    try:
        return max(0.0, float(v)) if v else min(480.0, 0.10 * budget_s)
    except ValueError:
        return min(480.0, 0.10 * budget_s)


class TimePlan:
    """The report stage's clock against the run's deadline (the research clock: pauses held by the proxy gate do not
    count). Without a deadline every step runs as before."""

    SCALED = ("setup", "version", "arith", "consist", "critic", "notyet")   # report-reading checks: ~ report length

    def __init__(self, deadline: float | None, clock: Callable[[], float]):
        self.deadline, self.clock = deadline, clock
        self.skipped: list[str] = []
        self.notes: list[str] = []
        self.scale = 1.0          # report length / the ~45K-token reports the estimates were measured on (10-27 smoke)

    def est(self, step: str) -> float:
        return EST.get(step, 120) * (self.scale if step in self.SCALED else 1.0)

    def left(self) -> float:
        return float("inf") if self.deadline is None else self.deadline - self.clock()

    def fits(self, step: str, after: float = 0.0) -> bool:
        """True when `step` (an EST key) still fits, keeping `after` seconds for the steps that must follow."""
        ok = self.left() - EST["files"] - after >= self.est(step)
        if not ok:
            self.skipped.append(step)
        return ok

    def max_sections(self, after: float) -> int | None:
        if self.deadline is None:
            return None
        room = self.left() - EST["opening"] - EST["files"] - after      # (called after the outline is written)
        return max(2, int(room // EST["section"]))

    def claims(self, after: float, wanted: int) -> int:
        if self.deadline is None:
            return wanted
        room = self.left() - EST["files"] - after
        n = int(max(0.0, room) // EST["claim"])
        return min(wanted, n) if wanted else n

    def max_tokens(self, prompt_tokens: int, wanted: int) -> int:
        """Cap a call's output so it can end before the deadline (prompt at ~1,200 tok/s, output at ~35 tok/s)."""
        if self.deadline is None:
            return wanted
        room = self.left() - EST["files"] - prompt_tokens / 1200.0
        return max(4096, min(wanted, int(room * 35)))
