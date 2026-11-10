#!/usr/bin/env python3
"""coderefs-check.py - the code-tool test's grading step 3 (the user, 10-24): every code reference in a report (file,
function, flag, environment variable, line) checked against a project's source at one tag.

Each reference is looked up with git grep in a local checkout of that tag and classed:
  engine     found in the engine the question is about (--engine-dir, default src/dsv41: the DeepSeek-V4.1 engine) -
             it exists there (whether it does what the report says is the answer key's job)
  elsewhere  found in Strata's code but not in that engine (the Qwen engine under src/, the server, the apps): a real
             Strata flag / variable, but not this engine's - advice to use it with this engine is wrong unless the
             server passes it on (the "where" field lists the top folders)
  docs       found only in docs / READMEs / tests / bench results
  missing    not in the repo at that tag: another project's (llama.cpp, vLLM, ...) or made up - the context line is kept
             so the grader can tell which
Line references (file:N, #LN) are checked for the file and the line count; GitHub blob links for the path.

  coderefs-check.py --repo DIR --tag v0.2.4 --out OUT.json REPORT.md [REPORT2.md ...]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, OrderedDict
from pathlib import Path

PATS = OrderedDict([
    ("blob", r"https://github\.com/[\w.-]+/[\w.-]+/blob/[\w./-]+?/([\w./-]+\.\w+)(?:#L(\d+)(?:-L\d+)?)?"),
    ("path", r"(?<![\w/.-])((?:src|serve|include|apps|cmake|tests|tools|scripts|docs|strata_\w+|metal|bench)/[\w./-]+\.\w+)(?::(\d+))?"),
    ("file", r"(?<![\w/.-])([\w-]+\.(?:cu|cuh|cpp|cc|hpp|h|py|cmake))(?::(\d+))?\b"),
    ("func", r"(?<![\w.])([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)\(\)"),     # snake_case() names only
    ("flag", r"(?<![\w-])(--[a-z][a-z0-9]+(?:-[a-z0-9]+)*)"),
    ("env", r"\b((?:DS4|STRATA|MAYA|GGML|LLAMA|CUDA|DSPARK|ENGRAM)_[A-Z0-9_]{2,})\b"),
])
NOT_CODE_FILES = {"llama.cpp", "ik_llama.cpp", "whisper.cpp", "node.js"}
DOC_HINT = re.compile(r"(^docs/|README|\.md$|^tests?/|/tests?/|test_|^packaging/|CHANGELOG|^bench/)")


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout


def classify(files: list[str], engine_dir: str) -> str:
    if not files:
        return "missing"
    if any(f.startswith(engine_dir) for f in files):
        return "engine"
    if [f for f in files if not DOC_HINT.search(f)]:
        return "elsewhere"
    return "docs"


def top_dirs(files: list[str]) -> list[str]:
    """Where a reference was found, code first: 'src/<part>' or the top folder, e.g. ['src/kernels', 'serve']."""
    out = []
    for f in sorted(files, key=lambda f: (bool(DOC_HINT.search(f)), f)):
        parts = f.split("/")
        d = "/".join(parts[:2]) if parts[0] == "src" and len(parts) > 2 else parts[0] if len(parts) > 1 else f
        if d not in out:
            out.append(d)
    return out[:6]


def where(repo: Path, kind: str, name: str) -> list[str]:
    """The files of the checkout that mention the reference (as code: a flag as a whole token, a function called or
    defined, a variable as a word)."""
    if kind == "flag":
        out = git(repo, "grep", "-l", "-I", "-E", "-e", f"{name}([^-A-Za-z0-9_]|$)", "--", ".")   # not --x inside --x-y
    elif kind == "func":
        out = git(repo, "grep", "-l", "-I", "-E", "-e", rf"\b{re.escape(name)}\s*\(", "--", ".")
    elif kind == "env":
        out = git(repo, "grep", "-l", "-I", "-w", "-F", "-e", name, "--", ".")
    else:
        return []
    return [f for f in out.splitlines() if f]


def path_hit(repo: Path, tracked: list[str], name: str, line: str | None) -> tuple[str, list[str], str]:
    """(class, files, note) for a file or path reference (+ a line)."""
    exact = [f for f in tracked if f == name or f.endswith("/" + name)]
    if not exact:
        return "missing", [], ""
    note = ""
    if line:
        f = exact[0]
        n = sum(1 for _ in open(repo / f, encoding="utf-8", errors="replace"))
        note = f"line {line} of {n}" + ("" if int(line) <= n else " - PAST THE END")
    return "file", exact[:5], note


def context(text: str, start: int, end: int) -> str:
    a = max(text.rfind("\n", 0, start), text.rfind(". ", 0, start) + 1, start - 220)
    b = min([x for x in (text.find("\n", end), text.find(". ", end), end + 220) if x != -1])
    return re.sub(r"\s+", " ", text[a:b]).strip()[:320]


def check(report: Path, repo: Path, engine_dir: str) -> dict:
    text = report.read_text(encoding="utf-8", errors="replace")
    tracked = git(repo, "ls-files").splitlines()
    refs: "OrderedDict[tuple[str, str], dict]" = OrderedDict()
    for kind, pat in PATS.items():
        for m in re.finditer(pat, text):
            name = m.group(1)
            line = m.group(2) if m.re.groups >= 2 else None
            if kind == "file" and name in NOT_CODE_FILES:
                continue
            if kind in ("file", "path", "blob"):
                kind2 = "file"
            else:
                kind2 = kind
            key = (kind2, name + (f":{line}" if line else ""))
            if key in refs:
                refs[key]["count"] += 1
                continue
            refs[key] = {"kind": kind2, "ref": key[1], "name": name, "line": line, "count": 1,
                         "context": context(text, m.start(), m.end())}
    for r in refs.values():
        if r["kind"] == "file":
            cls, files, note = path_hit(repo, tracked, r["name"], r["line"])
            r.update({"class": cls, "files": files, "note": note})
        else:
            files = where(repo, r["kind"], r["name"])
            r.update({"class": classify(files, engine_dir), "where": top_dirs(files), "n_files": len(files)})
    by = Counter((r["kind"], r["class"]) for r in refs.values())
    summary = {k: dict(sorted((c, n) for (kk, c), n in by.items() if kk == k)) for k in ("file", "func", "flag", "env")}
    return {"report": str(report), "refs": list(refs.values()), "summary": summary, "total": len(refs)}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("reports", nargs="+")
    p.add_argument("--repo", required=True, help="a git checkout of the project at --tag")
    p.add_argument("--tag", required=True)
    p.add_argument("--engine-dir", default="src/dsv41/")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    repo = Path(a.repo)
    head = git(repo, "describe", "--tags", "--exact-match").strip()
    if head != a.tag:
        raise SystemExit(f"{repo} is at {head or 'no tag'}, not {a.tag}")
    res = {"repo": str(repo), "tag": a.tag, "engine_dir": a.engine_dir,
           "reports": [check(Path(r), repo, a.engine_dir) for r in a.reports]}
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for r in res["reports"]:
        print(f"{Path(r['report']).name}: {r['total']} references - {json.dumps(r['summary'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
