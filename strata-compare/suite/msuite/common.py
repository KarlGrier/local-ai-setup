"""Shared paths, constants and small helpers for the model test suite."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]          # suite/
WS = SUITE.parent                                     # the workspace (strata-compare)
ITEMS = SUITE / "items"
RESULTS = SUITE / "results"
VENDOR = SUITE / "vendor"
TMP = WS / "tmp" / "suite"                            # throwaway folders (sandboxes, browser profiles)
KEY_FILE = Path.home() / ".config" / "model-suite" / "anthropic.key"

# The user's local sampling (every local request sends these explicitly).
LOCAL_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
LOCAL_EFFORT = "xhigh"
RUNS = {"quick": 1, "full": 3}

CATEGORIES = ["coding", "agentic", "math", "instruct", "tools", "longctx", "honesty", "freshness", "visual", "research"]
SCORED = ["coding", "agentic", "math", "instruct", "tools", "longctx", "honesty", "research"]   # in the totals
CAT_TITLES = {"coding": "Coding (hidden tests)", "agentic": "Agentic coding (repos green)", "math": "Math",
              "instruct": "Instruction following", "tools": "Tool calls", "longctx": "Long context",
              "honesty": "Honesty (balanced)", "freshness": "Knowledge freshness (not scored)",
              "visual": "Visual (judged by you)", "research": "Research with web search (key)"}


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj, indent=1):
    """Atomic write (temp file + rename) so a crash never leaves half an answer on disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def items_fingerprint() -> str:
    """One hash over every prompt and checker file of categories 1-9: two runs with the same fingerprint used the same
    tests.  The research category (added later) has its own fingerprint, so older runs stay comparable."""
    h = hashlib.sha256()
    for p in sorted(ITEMS.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.relative_to(ITEMS).parts[0] != "research":
            h.update(str(p.relative_to(ITEMS)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,80}$")


def check_label(label: str) -> str:
    if not SAFE_LABEL.match(label):
        raise SystemExit(f"label {label!r}: use letters, digits, '.', '_', '+', '-' only")
    return label


def label_dir(label: str) -> Path:
    return RESULTS / check_label(label)


def answer_path(label: str, item_id: str, run: int) -> Path:
    cat, name = item_id.split("/", 1)
    return label_dir(label) / "answers" / cat / f"{name}.r{run}.json"


def last_line_answer(text: str):
    """The value of the last 'ANSWER: ...' line (markdown emphasis and backticks stripped), or None."""
    if not text:
        return None
    found = None
    for line in text.splitlines():
        s = line.strip().strip("*_`> ").strip()
        m = re.match(r"(?i)^answer\s*[:：]\s*(.+?)\s*$", s)
        if m:
            found = m.group(1).strip().strip("*_`").strip()
    return found


def parse_int(s):
    if s is None:
        return None
    s = s.replace(",", "").replace(" ", "").replace(" ", "").strip().rstrip(".")
    s = re.sub(r"^\$|\\boxed\{(.*)\}$", r"\1", s)
    try:
        return int(s)
    except ValueError:
        try:
            f = float(s)
            return int(f) if f == int(f) else None
        except (ValueError, OverflowError):
            return None


def research_fingerprint() -> str:
    """The research questions only (the key is read at grading time and may be edited)."""
    p = ITEMS / "research" / "questions.json"
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else "-"
