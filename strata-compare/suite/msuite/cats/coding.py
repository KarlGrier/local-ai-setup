"""Coding: 25 Python problems with hidden unit tests.  Score = share of hidden tests passed (first answer only)."""
from __future__ import annotations

import json
import re
import uuid

from ..common import ITEMS, SUITE
from .. import sandbox

DIR = ITEMS / "coding"
RUNNER = (SUITE / "msuite" / "harness" / "coding_runner.py").read_text()
FORMAT = ("\n\nReply with your complete solution as one fenced ```python code block (standard library only). It must "
          "define `{entry}`. Do not read input or print anything when the module is imported.")
MARK = "# ==== HIDDEN TESTS ===="
FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+.-]*)[^\n]*\n(.*?)(?:```|\Z)", re.S)


def load() -> list[dict]:
    items = []
    for p in sorted(DIR.glob("c*.py")):
        src = p.read_text(encoding="utf-8")
        head, tests = src.split(MARK, 1)
        ns: dict = {}
        exec(compile(head, str(p), "exec"), ns)          # constants only: LEVEL, KIND, ENTRY, PROMPT, GOOD, BAD
        items.append({"id": f"coding/{p.stem}", "category": "coding", "level": ns["LEVEL"], "kind": ns["KIND"],
                      "entry": ns["ENTRY"], "prompt": ns["PROMPT"].strip() + FORMAT.format(entry=ns["ENTRY"]),
                      "good": ns["GOOD"], "bad": ns["BAD"], "tests_src": tests, "max_tokens": None})
    return items


def extract_code(text: str, entry: str):
    """The last fenced python block that defines `entry`; else the last python block; else None."""
    blocks = [(lang.lower(), body) for lang, body in FENCE.findall(text or "")]
    py = [b for lang, b in blocks if lang in ("python", "py", "python3", "")]
    pat = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+%s\b" % re.escape(entry), re.M)
    hits = [b for b in py if pat.search(b)]
    if hits:
        return hits[-1]
    return py[-1] if py else None


def run_tests(code: str, tests_src: str, per_test_s: float = 10.0, wall_s: float = 150) -> dict:
    nonce = "@@" + uuid.uuid4().hex + "@@"
    d = sandbox.new_workdir("code")
    try:
        (d / "solution.py").write_text(code, encoding="utf-8")
        (d / "hidden_test.py").write_text(tests_src, encoding="utf-8")
        (d / "runner.py").write_text(RUNNER, encoding="utf-8")
        res = sandbox.run([sandbox.PYTHON, "-I", "runner.py", nonce, str(per_test_s)], d, timeout_s=wall_s,
                          mem_mb=3072)
    finally:
        sandbox.remove_workdir(d)
    total, results, import_error = None, [], None
    for line in res["stdout"].splitlines():
        if not line.startswith(nonce):
            continue
        try:
            ev = json.loads(line[len(nonce):])
        except ValueError:
            continue
        if "total" in ev:
            total = ev["total"]
        elif "import_error" in ev:
            import_error = ev["import_error"]
        elif "test" in ev:
            results.append(ev)
    if total is None:
        total = tests_src.count("\ndef test_")
    passed = sum(1 for r in results if r["ok"])
    return {"passed": passed, "total": total, "import_error": import_error, "timed_out": res["timed_out"],
            "failures": [f"{r['test']}: {r['msg']}" for r in results if not r["ok"]][:10],
            "stderr_tail": res["stderr"][-600:] if (import_error or res["timed_out"] or total != len(results)) else ""}


def grade(item: dict, rec: dict) -> dict:
    text = (rec.get("response") or {}).get("content") or ""
    code = extract_code(text, item["entry"])
    if code is None:
        return {"score": 0.0, "solved": False, "detail": "no fenced python code block in the answer"}
    r = run_tests(code, item["tests_src"])
    score = r["passed"] / r["total"] if r["total"] else 0.0
    return {"score": score, "solved": r["passed"] == r["total"] and r["total"] > 0,
            "detail": f"{r['passed']}/{r['total']} hidden tests" + (f"; import error: {r['import_error']}"
                                                                    if r["import_error"] else ""),
            "tests": r}


def selftest() -> list[tuple[str, bool, str]]:
    out = []
    for it in load():
        g = run_tests(it["good"], it["tests_src"])
        out.append((f"{it['id']} known-good passes all", g["passed"] == g["total"] and g["total"] > 0,
                    f"{g['passed']}/{g['total']} {g['failures'][:2]} {g['stderr_tail'][-200:]}"))
        b = run_tests(it["bad"], it["tests_src"])
        out.append((f"{it['id']} known-bad fails some", b["passed"] < b["total"], f"{b['passed']}/{b['total']}"))
        # the grader end to end: answer text with prose around the block
        ans = {"response": {"content": "Here you go:\n\n```python\n" + it["good"] + "\n```\n\nExample:\n```python\n"
                            "print(1)\n```"}}
        gg = grade(it, ans)
        out.append((f"{it['id']} grader extracts the right block", gg["solved"], gg["detail"]))
    none = grade({"entry": "f", "tests_src": ""}, {"response": {"content": "def f(): pass"}})
    out.append(("coding: answer without a fenced block scores 0", none["score"] == 0, none["detail"]))
    return out
