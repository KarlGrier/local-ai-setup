#!/usr/bin/env python3
"""tasks.py - the four harness tasks of the usability round: prepare a fresh repo, grade it.

    a1_inventory, a2_textstats, a3_cronlite   the suite's agentic repos (failing tests; graded as the suite grades them:
                                              the model's files, the original tests restored + the hidden tests, green)
    rt_effort                                 a real bug in a public repo: Strata v0.1.44's serve/ (exported without git
                                              history, so the fix in v0.1.44.1 cannot be looked up); graded by upstream's
                                              own test for the fix (serve/test_effort_paths.py of v0.1.44.1, copied in as
                                              a hidden file) plus the whole serve suite, with the original tests restored
"""
import json
import shutil
import subprocess
import sys
import tarfile
import io
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
SUITE = WS / "suite"
STRATA = WS / "strata"
VENV_RT = WS / "tmp/usability/venv-rt"
AGENTIC = ["a1_inventory", "a2_textstats", "a3_cronlite"]

AGENTIC_PROMPT = """This is a small Python repository whose test suite currently fails. Change the code so that the whole test suite passes.

Run the tests with: python3 -m unittest discover -s tests -t . -v

Rules:
- Do not change the tests: they are restored before grading, and hidden tests check the same behaviour, so fix the code properly (no special-casing of test inputs).
- No network access is available.
- When the tests pass, reply with a one-paragraph summary of what you changed."""

RT_PROMPT = """Bug report for this repository (Strata's server, the Python package in serve/):

1. The run config's "reasoning_effort" key (for example "low") is honoured by POST /v1/chat/completions and POST /v1/messages for requests that name no level, but POST /v1/responses (the OpenAI Responses API that Codex uses) ignores it: such requests always think at the default level.
2. A chat completions request with "reasoning_effort": false should turn thinking off (the same as "none"), but the server treats it as if no level had been sent.

Fix both. Every API should give a request that names no level the same default: the Chat settings shared with apps first, then the config's "reasoning_effort". Keep everything else as it is, and add tests in serve/ for the fix.

Testing: use the virtual environment in .venv (it has the packages the tests need), for example
  .venv/bin/python -m unittest serve.test_responses -v
The whole serve suite (.venv/bin/python -m unittest discover -s serve -t . -p 'test_*.py') takes about 5 minutes and must still pass. No network access is available.

When you are done, reply with a one-paragraph summary of what you changed."""


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@localhost", "GIT_COMMITTER_NAME": "test",
                        "GIT_COMMITTER_EMAIL": "test@localhost", "PATH": "/usr/bin:/bin", "HOME": "/tmp"})


def prepare(task: str, dest: Path) -> str:
    """A fresh repo for `task` at `dest` (a git repo with one commit); returns the prompt."""
    if dest.exists():
        shutil.rmtree(dest)
    if task in AGENTIC:
        shutil.copytree(SUITE / "items/agentic" / task / "repo", dest)
        prompt = AGENTIC_PROMPT
    elif task == "rt_effort":
        dest.mkdir(parents=True)
        tar = subprocess.run(["git", "-C", str(STRATA), "archive", "v0.1.44"], check=True, capture_output=True).stdout
        tarfile.open(fileobj=io.BytesIO(tar)).extractall(dest)
        (dest / ".venv").symlink_to(VENV_RT)
        prompt = RT_PROMPT
    else:
        raise SystemExit(f"unknown task {task}")
    (dest / ".gitignore").write_text(".venv\n__pycache__/\n")
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "initial")
    return prompt


def grade(task: str, repo: Path) -> dict:
    """Green or not, judged on a copy of the model's files with the original tests restored and the hidden tests in."""
    if task in AGENTIC:
        sys.path.insert(0, str(SUITE))
        from msuite.cats import agentic
        item = {"dir": str(SUITE / "items/agentic" / task)}
        r = agentic.final_check(item, repo)
        changed_tests = _tests_changed(task, repo)
        return {"green": r["green"], "visible_green": r["visible_green"], "tests_changed": changed_tests,
                "tail": r["output_tail"][-600:]}
    # rt_effort
    check = repo.parent / "grade-copy"
    if check.exists():
        shutil.rmtree(check)
    shutil.copytree(repo, check, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    tar = subprocess.run(["git", "-C", str(STRATA), "archive", "v0.1.44", "serve"], check=True, capture_output=True).stdout
    orig = {m.name: m for m in tarfile.open(fileobj=io.BytesIO(tar)).getmembers()}
    t = tarfile.open(fileobj=io.BytesIO(tar))
    restored = 0
    for name, m in orig.items():                       # the original serve/test_*.py back (the model's own new ones stay)
        if Path(name).name.startswith("test_") and name.endswith(".py"):
            (check / name).write_bytes(t.extractfile(m).read())
            restored += 1
    hidden = subprocess.run(["git", "-C", str(STRATA), "show", "v0.1.44.1:serve/test_effort_paths.py"], check=True,
                            capture_output=True).stdout
    (check / "serve/test_zz_hidden_effort_paths.py").write_bytes(hidden)
    py = str(VENV_RT / "bin/python")
    h = subprocess.run([py, "-m", "unittest", "serve.test_zz_hidden_effort_paths"], cwd=check, capture_output=True,
                       text=True, timeout=600)
    full = subprocess.run([py, "-m", "unittest", "discover", "-s", "serve", "-t", ".", "-p", "test_*.py"], cwd=check,
                          capture_output=True, text=True, timeout=1800)
    hid_ok = h.returncode == 0
    full_ok = full.returncode == 0
    shutil.rmtree(check, ignore_errors=True)
    return {"green": hid_ok and full_ok, "hidden_green": hid_ok, "suite_green": full_ok, "restored_tests": restored,
            "hidden_tail": h.stderr[-900:], "suite_tail": full.stderr[-900:]}


def _tests_changed(task, repo):
    orig = SUITE / "items/agentic" / task / "repo/tests"
    out = []
    for f in orig.rglob("*.py"):
        mine = repo / "tests" / f.relative_to(orig)
        if not mine.exists() or mine.read_bytes() != f.read_bytes():
            out.append(str(f.relative_to(orig)))
    return out


if __name__ == "__main__":
    cmd, task, path = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    if cmd == "prepare":
        print(prepare(task, path))
    elif cmd == "grade":
        print(json.dumps(grade(task, path), indent=1))
