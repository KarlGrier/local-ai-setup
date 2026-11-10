#!/usr/bin/env python3
"""test_runner_steps.py [RUNNER_FILE] - Karl 11-04: "steps" for Jan's research, turned on by the same install as the
bench's (staging/post7d/install-ldr-fixes.sh). Offline: no LDR, runner, model or network; temp files in
staging/post7d/scratch. It checks, on RUNNER_FILE (default the installed tools/research-runner.py; install-ldr-fixes.sh
--check passes the expected file built in scratch):
  1 a Jan deep job's run-ldr.sh environment (the runner's own run_ldr(), with subprocess.run captured) carries
    LDR_DEEP_FIX=steps, plus the setup profile and the critic as before; a stray LDR_DEEP_FIX in the runner's own
    environment is replaced; a quick (baseline) job carries none;
  2 run-ldr.sh's REAL item-stamp block (cut from run-ldr.sh) turns that environment into run/ldr.items
    "setup critic fix:steps" (deep) / "off" (baseline);
  3 the runner's ldr_restart_reasons() accepts that stamp (no restart for a fitting LDR) and asks for a restart of an
    LDR stamped the old way ("setup critic") or the bench's way;
  4 in the LDR package, LDR_DEEP_FIX=steps switches "steps" on and none of the six fixes (checks.fix_on / fixes_on).
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
RUNNER = Path(sys.argv[1]) if len(sys.argv) > 1 else WS / "tools" / "research-runner.py"
SCRATCH = WS / "staging" / "post7d" / "scratch"
FAILS = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


def load_runner():
    tree = ast.parse(RUNNER.read_text())
    keep = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in ("run_ldr", "ldr_restart_reasons"):
            keep.append(n)
        elif isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("JOB_DEEP_FIX", "JOB_DEEP_ITEMS") for t in n.targets):
            keep.append(n)
    captured = {}

    class FakeSub:
        @staticmethod
        def run(cmd, **kw):
            captured["cmd"], captured["env"] = cmd, dict(kw.get("env") or {})
            return subprocess.CompletedProcess(cmd, 0, "", "")

    class RC:
        @staticmethod
        def settings():
            return {"verify_max_claims": 120}

    class RF:
        @staticmethod
        def modelprofile_mismatch(want, run_dir):
            return ""

    efforts = {"LDR_DEEP_REPORT_EFFORT": "medium", "LDR_DEEP_VERIFY_EFFORT": "xhigh"}
    ns = {"Path": Path, "os": os, "WS": WS, "RUN_DIR": WS / "run", "subprocess": FakeSub, "rc": RC, "rf": RF, "WANT_MODEL_PROFILE": "flash-next",
          "clean_env": lambda: {"HOME": os.environ.get("HOME", "/home/USER"), "PATH": "/usr/bin:/bin",
                                "LDR_DEEP_FIX": "all"},          # a stray value: the runner must set / pop its own
          "fallback_keys": lambda: False, "DEEP_LDR_EFFORTS": efforts,
          "DEEP_LDR_EFFORTS_FILE": "report=medium verify=xhigh"}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(RUNNER), "exec"), ns)
    return ns, captured


def stamp_block() -> str:
    lines = (WS / "run-ldr.sh").read_text().splitlines()
    a = next(i for i, l in enumerate(lines) if l.strip() == 'items=""')
    b = next(i for i, l in enumerate(lines) if l.strip().startswith('items=${items# }; echo "${items:-off}" > "$RUN/ldr.items"'))
    return "\n".join(lines[a:b + 1])


def stamp(env: dict, profile: str, run: Path) -> str:
    e = {k: v for k, v in env.items() if k.startswith("LDR_") or k in ("HOME", "PATH")}
    run.mkdir(parents=True, exist_ok=True)
    e.update({"PROFILE": profile, "RUN": str(run)})
    r = subprocess.run(["/bin/bash", "-c", stamp_block()], env=e, capture_output=True, text=True)
    check(r.returncode == 0, f"run-ldr.sh's item block ran ({profile}) {r.stderr.strip()[:200]}")
    return (run / "ldr.items").read_text().strip()


def fake_run_dir(base: Path, items: str, profile: str = "deep", quick: str = "off") -> Path:
    base.mkdir(parents=True, exist_ok=True)
    for name, val in (("ldr.profile", profile), ("ldr.fallback", "off"), ("ldr.s2", "on"), ("ldr.quicklimits", quick),
                      ("ldr.efforts", "report=medium verify=xhigh"), ("ldr.items", items)):
        (base / name).write_text(val + "\n")
    return base


def main() -> int:
    print(f"runner: {RUNNER}")
    ns, cap = load_runner()
    check("JOB_DEEP_FIX" in ns and "steps" in ns["JOB_DEEP_FIX"].split(","), "the runner defines JOB_DEEP_FIX with steps")
    tmp = Path(tempfile.mkdtemp(prefix="runner-steps-", dir=SCRATCH))
    # 1 + 2: a deep job
    ns["run_ldr"]("start", "deep")
    env = cap["env"]
    check(env.get("LDR_DEEP_FIX") == "steps", f"deep job: LDR_DEEP_FIX = {env.get('LDR_DEEP_FIX')!r} (want 'steps')")
    check(env.get("LDR_DEEP_CRITIC") == "1" and env.get("LDR_DEEP_SETUP_PROFILE", "").endswith("user-setup.md"),
          "deep job: setup profile + critic as before")
    check(env.get("LDR_PROFILE") == "deep", "deep job: LDR_PROFILE deep")
    st = stamp(env, "deep", tmp / "deep")
    check(st == "setup critic fix:steps", f"deep job: run/ldr.items {st!r} (want 'setup critic fix:steps')")
    # 3: the restart rule
    ok_dir = fake_run_dir(tmp / "fit", st)
    r = ns["ldr_restart_reasons"]("deep", False, ok_dir)
    check(r == [], f"an LDR started for a Jan deep job fits the next one (reasons: {r})")
    r = ns["ldr_restart_reasons"]("deep", False, fake_run_dir(tmp / "old", "setup critic"))
    check(any(x.startswith("items") for x in r), f"an LDR stamped 'setup critic' (before the install) is restarted ({r})")
    r = ns["ldr_restart_reasons"]("deep", False, fake_run_dir(tmp / "bench", "setup critic code fixes read claims fix:steps"))
    check(any(x.startswith("items") for x in r), f"the bench's LDR is restarted for a Jan job ({r})")
    # a quick job (baseline profile)
    ns["run_ldr"]("start", "baseline")
    benv = cap["env"]
    check("LDR_DEEP_FIX" not in benv, "quick job: no LDR_DEEP_FIX")
    bst = stamp(benv, "baseline", tmp / "base")
    check(bst == "off", f"quick job: run/ldr.items {bst!r} (want 'off')")
    r = ns["ldr_restart_reasons"]("baseline", True, fake_run_dir(tmp / "bfit", bst, profile="baseline", quick="on"))
    check(not any(x.startswith("items") for x in r), f"a quick job's LDR fits on items ({r})")
    # 4: the package's switch
    code = ("import os; from local_deep_research.deep import checks as c; "
            "print(int(c.fix_on('steps')), ','.join(c.fixes_on()) or '-', int(c.fix_on('read')), int(c.fix_on('claims')))")
    p = subprocess.run([str(WS / ".venv" / "bin" / "python"), "-I", "-B", "-c", code], capture_output=True, text=True,
                       env={"LDR_DEEP_FIX": "steps", "PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "/home/USER")})
    check(p.stdout.split() == ["1", "-", "0", "0"],
          f"LDR_DEEP_FIX=steps: steps on, no six fixes, no read / claims ({p.stdout.strip()} {p.stderr.strip()[-200:]})")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{'ALL OK' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
