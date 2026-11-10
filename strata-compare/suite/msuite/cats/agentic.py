"""Agentic coding: 3 small repos with failing tests, fixed through a simple tool loop (read_file, write_file,
run_tests), at most 15 steps (model turns), the same loop and wording for every model.

Score per repo: 1 when the repo is green at the end, judged on a fresh copy of the model's files with the original
tests restored plus hidden tests of the same behaviour; also recorded: steps, tokens, whether the visible suite alone
was green.  The repo lives in a throwaway folder under tmp/suite; tests run in the sandbox (no network, time limit).
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from ..common import ITEMS
from .. import sandbox

DIR = ITEMS / "agentic"
MAX_STEPS = 15
# Output tokens per step, every model.  65,536 since 2026-10-13 (the user's call); 32,768 before, which only
# Sonnet 5.5 reached (2 of 3 repos, thinking before the first write; its agentic items were re-run).
STEP_MAX_TOKENS = 65536
READ_CAP = 20000
OUT_CAP = 6000
TEST_CMD = [sandbox.PYTHON, "-E", "-s", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"]

TOOLS = [
    {"name": "read_file", "description": "Read a text file of the repository.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path relative to the repository root"}},
                    "required": ["path"], "additionalProperties": False}},
    {"name": "write_file", "description": "Write (create or completely replace) a text file of the repository.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path relative to the repository root"},
                                                     "content": {"type": "string", "description": "The complete new file content"}},
                    "required": ["path", "content"], "additionalProperties": False}},
    {"name": "run_tests", "description": "Run the repository's test suite (python -m unittest) and return its output.",
     "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
]

TASK = """You are working in a small Python repository whose test suite currently fails. Change the code so that the whole test suite passes.

Rules:
- Use the tools: read_file(path), write_file(path, content) (it replaces the whole file) and run_tests().
- Do not change the tests: they are restored before grading, and hidden tests check the same behaviour, so fix the code properly (no special-casing of test inputs).
- You have at most {max_steps} steps; each of your replies counts as one step. Several tool calls in one reply are allowed.
- When the tests pass, reply with a one-paragraph summary of what you changed and make no tool call.

{readme}
Files in the repository:
{files}"""


def _files(root: Path) -> list[str]:
    """Regular files under root; symlinks (files or directories) are neither listed nor followed."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [n for n in dirnames if n != "__pycache__" and not os.path.islink(os.path.join(dirpath, n))]
        for n in filenames:
            full = os.path.join(dirpath, n)
            if not os.path.islink(full) and os.path.isfile(full):
                out.append(os.path.relpath(full, root))
    return sorted(out)


def load() -> list[dict]:
    out = []
    for d in sorted(p for p in DIR.iterdir() if p.is_dir()):
        readme = (d / "task.md").read_text(encoding="utf-8").strip() + "\n" if (d / "task.md").exists() else ""
        files = _files(d / "repo")
        prompt = TASK.format(max_steps=MAX_STEPS, readme=readme, files="\n".join("- " + f for f in files))
        out.append({"id": f"agentic/{d.name}", "category": "agentic", "prompt": prompt, "dir": str(d),
                    "tools": TOOLS, "agentic": True})
    return out


# ------------------------------------------------------------------------------------------------- the tools
def _safe_path(root: Path, rel) -> Path:
    if not isinstance(rel, str) or not rel or rel.startswith("/") or "\x00" in rel:
        raise ValueError("path must be a relative path inside the repository")
    p = root / rel
    cur = root
    for part in Path(rel).parts:                 # no component may be a symlink (the sandbox could have made one)
        cur = cur / part
        if cur.is_symlink():
            raise ValueError("symlinks are not allowed")
    rp = p.resolve()
    if rp != root.resolve() and root.resolve() not in rp.parents:
        raise ValueError("path is outside the repository")
    return p


def run_suite(root: Path, timeout_s=90) -> dict:
    r = sandbox.run(TEST_CMD, root, timeout_s=timeout_s, mem_mb=2048)
    text = (r["stdout"] + r["stderr"])
    green = r["rc"] == 0 and not r["timed_out"] and ("\nOK" in text or text.rstrip().endswith("OK"))
    return {"green": green, "rc": r["rc"], "timed_out": r["timed_out"], "output": text}


def call_tool(root: Path, name: str, args_json) -> str:
    try:
        args = json.loads(args_json) if isinstance(args_json, str) and args_json.strip() else (args_json or {})
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
    except ValueError as e:
        return f"ERROR: arguments are not valid JSON ({e})"
    try:
        if name == "read_file":
            p = _safe_path(root, args.get("path"))
            if not p.is_file():
                return f"ERROR: no such file: {args.get('path')}"
            t = p.read_text(encoding="utf-8", errors="replace")
            return t if len(t) <= READ_CAP else t[:READ_CAP] + f"\n... [truncated at {READ_CAP} characters]"
        if name == "write_file":
            p = _safe_path(root, args.get("path"))
            content = args.get("content")
            if not isinstance(content, str):
                return "ERROR: content must be a string"
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists() and (p.is_symlink() or not p.is_file()):
                return "ERROR: not a regular file"
            p.write_text(content, encoding="utf-8")
            return f"wrote {len(content)} characters to {args.get('path')}"
        if name == "run_tests":
            r = run_suite(root)
            out = r["output"]
            if len(out) > OUT_CAP:
                out = "... [earlier output cut]\n" + out[-OUT_CAP:]
            return (f"exit code {r['rc']}" + (" (timed out)" if r["timed_out"] else "") + "\n" + out)
        return f"ERROR: unknown tool {name!r}"
    except ValueError as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------------------------- loop + grade
def final_check(item: dict, work: Path) -> dict:
    """Fresh copy of the model's files, original tests restored, hidden tests added; run in the sandbox."""
    d = Path(item["dir"])
    check = sandbox.new_workdir("agentic-check")
    try:
        shutil.copytree(work, check, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
        shutil.copytree(d / "repo" / "tests", check / "tests", dirs_exist_ok=True)
        visible = run_suite(check)
        for h in (d / "hidden").glob("*.py"):
            shutil.copy(h, check / "tests" / h.name)
        full = run_suite(check)
        return {"visible_green": visible["green"], "green": full["green"], "output_tail": full["output"][-1500:]}
    finally:
        sandbox.remove_workdir(check)


def run_item(item: dict, backend, log=print) -> dict:
    """The tool loop.  Returns one record with every step, total tokens and the final check."""
    d = Path(item["dir"])
    work = sandbox.new_workdir("agentic")
    shutil.copytree(d / "repo", work, dirs_exist_ok=True)
    messages = [{"role": "user", "content": item["prompt"]}]
    steps, t0 = [], time.monotonic()
    finished, stop = False, None
    try:
        for step in range(1, MAX_STEPS + 1):
            rec = backend.chat(messages, tools=item["tools"], max_tokens=STEP_MAX_TOKENS,
                               prompt_tokens_est=sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) // 3)
            r = rec["response"]
            calls = r.get("tool_calls") or []
            steps.append({"step": step, "tokens": rec["tokens"], "timing": rec["timing"],
                          "finish_reason": r.get("finish_reason"), "cut_off": rec.get("cut_off"),
                          "content": r.get("content"), "reasoning_chars": len(r.get("reasoning") or ""),
                          "tool_calls": calls, "cost_usd": rec.get("cost_usd"),
                          "provider": (r.get("meta") or {}).get("provider")})
            log(f"    step {step}: {len(calls)} tool call(s) {[c['name'] for c in calls]}, "
                f"{rec['tokens'].get('completion')} tokens")
            if not calls:
                finished = True
                stop = "no tool call (model says done)" if not rec.get("cut_off") else "cut off"
                break
            messages.append(backend.assistant_message(rec))
            results = []
            for c in calls:
                out = call_tool(work, c["name"], c["arguments"])
                results.append((c["id"], out))
                steps[-1].setdefault("tool_results", []).append(out[:2000])
            messages += backend.tool_result_messages(results)
        else:
            stop = f"step limit ({MAX_STEPS})"
        check = final_check(item, work)
        files = {f: (work / f).read_text(encoding="utf-8", errors="replace")[:20000] for f in _files(work)
                 if not f.startswith("tests/") and f.endswith(".py") and not (work / f).is_symlink()}
    finally:
        sandbox.remove_workdir(work)
    tok = lambda k: sum((s["tokens"].get(k) or 0) for s in steps)
    return {
        "response": {"content": steps[-1]["content"] if steps else "", "reasoning": "", "tool_calls": [],
                     "finish_reason": stop,
                     "meta": {"provider": ", ".join(sorted({s["provider"] for s in steps if s.get("provider")})) or None}},
        "cut_off": any(s.get("cut_off") for s in steps),
        "steps": steps, "n_steps": len(steps), "step_max_tokens": STEP_MAX_TOKENS, "finished": finished, "stop": stop, "final_files": files,
        "check": check,
        "tokens": {"prompt": tok("prompt"), "completion": tok("completion"), "reasoning": tok("reasoning"),
                   "answer": tok("answer"), "method": steps[0]["tokens"].get("method") if steps else None,
                   "cached_prompt": tok("cached_prompt")},
        "timing": {"wall_s": round(time.monotonic() - t0, 2), "ttft_s": None,
                   "e2e_tps": None, "decode_tps": None, "server_decode_tps": None},
        "cost_usd": round(sum(s.get("cost_usd") or 0 for s in steps), 5) if any(s.get("cost_usd") for s in steps) else None,
    }


def grade(item: dict, rec: dict) -> dict:
    c = rec.get("check") or {}
    ok = bool(c.get("green"))
    return {"score": 1.0 if ok else 0.0, "solved": ok,
            "detail": (f"{'GREEN' if ok else 'not green'} (visible suite {'green' if c.get('visible_green') else 'red'}), "
                       f"{rec.get('n_steps')} steps, stop: {rec.get('stop')}")}


def selftest():
    out = []
    for it in load():
        d = Path(it["dir"])
        work = sandbox.new_workdir("agentic-selftest")
        try:
            shutil.copytree(d / "repo", work, dirs_exist_ok=True)
            pristine = final_check(it, work)
            shutil.copytree(d / "fix", work, dirs_exist_ok=True)
            fixed = final_check(it, work)
            # the tools: path escapes are refused, a symlink made inside the sandbox is not followed
            esc = call_tool(work, "read_file", json.dumps({"path": "../../etc/passwd"}))
            (work / "link.txt").symlink_to("/etc/hostname")
            sym = call_tool(work, "read_file", json.dumps({"path": "link.txt"}))
            wr = call_tool(work, "write_file", json.dumps({"path": "/tmp/x", "content": "x"}))
        finally:
            sandbox.remove_workdir(work)
        out.append((f"{it['id']} pristine repo is red", not pristine["visible_green"] and not pristine["green"], ""))
        out.append((f"{it['id']} known-good fix is green (visible + hidden)", fixed["visible_green"] and fixed["green"],
                    fixed["output_tail"][-400:]))
        out.append((f"{it['id']} tools refuse escapes and symlinks", all(x.startswith("ERROR") for x in (esc, sym, wr)),
                    f"{esc[:60]} | {sym[:60]} | {wr[:60]}"))
    return out
