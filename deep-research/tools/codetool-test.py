#!/usr/bin/env python3
"""codetool-test.py - phase 4, the read-only code tool's test (the user, 10-24; go 10-27): rerun the user's 10-24 DeepSeek
speed-ideas question with the code tool on, on the same pipeline as that Jan job - deep profile, setup profile + setup
check + critic, Semantic Scholar on, agent / extraction / report medium, citation check xhigh, 240 min budget. The only
differences: LDR_DEEP_CODE=1, and no paid search fallback (measurements use SearXNG only; it only steps in when SearXNG
fails).

  codetool-test.py smoke   a short question about Strata v0.2.4 (8 min budget): do the agents call the tools, and cite?
  codetool-test.py full    the 10-24 question (read from its job file; the user allowed it for this test)

Output: results/bench2/codetool/run-<mode>/ (client.out, report.md, the deep folder with code-tool.jsonl, run.json).
Holds run/bench.lock for the whole run (the research runner leaves LDR alone; Jan jobs wait), starts LDR for the run and
stops it after (the runner starts it again in its own profile for the next job). Kernel log checked after the run.
Run it with the LDR venv: .venv/bin/python tools/codetool-test.py smoke
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
sys.path.insert(0, str(WS / "tools"))
import research_common as rc  # noqa: E402

OUT = WS / "results" / "bench2" / "codetool"
JOB = WS / "jobs" / "20261024-085829-goal-produce-a-ranked-evidence-checked-l" / "job.json"
KCHECK = Path("/home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh")
ENSURE = rc.SC / "configs" / "usability" / "bin" / "strata-ensure.sh"
SMOKE_Q = ("In the Strata project on GitHub (Niko1221/Strata) at version v0.2.4: does the DeepSeek-V4.1 engine's "
           "layer-major prompt pass (lm_begin) run when the model's layers are split across two GPUs, and what decides "
           "it? Give the source file and line.")


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


FIXES = "--fixes" in sys.argv          # 10-27: the six fixes' combined rerun (LDR_DEEP_FIX=all), own output folder
BUNDLE = "--bundle" in sys.argv        # 10-28: the items 5 + 6 bundle's combined rerun (LDR_DEEP_FIX=all,read,claims)
# 10-29: --suffix=NAME - another run of the same arm in its own folder (run-full-bundle-NAME)
SUFFIX = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--suffix=")), "")


def ldr_env() -> dict:
    """The research runner's deep-profile environment (research-runner.py run_ldr) + the code tool, without the paid
    search fallback; with --fixes also LDR_DEEP_FIX=all, with --bundle LDR_DEEP_FIX=all,read,claims."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("LDR_")}
    env.update({"LDR_PROFILE": "deep", "LDR_RESEARCH_S2": "1", "LDR_DEEP_REPORT_EFFORT": "medium",
                "LDR_DEEP_VERIFY_EFFORT": "xhigh",
                "LDR_DEEP_VERIFY_MAX_CLAIMS": str(int(rc.settings()["verify_max_claims"])),
                "LDR_DEEP_SETUP_PROFILE": str(WS / "user-setup.md"), "LDR_DEEP_CRITIC": "1", "LDR_DEEP_CODE": "1"})
    if BUNDLE:
        env["LDR_DEEP_FIX"] = "all,read,claims"
    elif FIXES:
        env["LDR_DEEP_FIX"] = "all"
    return env


def stamp(name: str) -> str:
    p = WS / "run" / f"ldr.{name}"
    return p.read_text().strip() if p.exists() else ""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("smoke", "full"):
        print(__doc__)
        return 2
    if mode == "full":
        job = json.loads(JOB.read_text())
        question, budget_s = job["question"], int(job["budget_minutes"] * 60)
    else:
        question, budget_s = SMOKE_Q, 8 * 60
    out = OUT / ((f"run-{mode}-bundle" if BUNDLE else f"run-{mode}-fixes" if FIXES else f"run-{mode}")
                 + (f"-{SUFFIX}" if SUFFIX else ""))
    if (out / "run.json").exists():
        log(f"{out} has a finished run already - move it away to run again")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    while True:                                   # never start over the user's own research
        active = [j for j in rc.all_jobs() if j.get("state") in rc.ACTIVE]
        if not active:
            lock = open(WS / "run" / "bench.lock", "w")
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not [j for j in rc.all_jobs() if j.get("state") in rc.ACTIVE]:
                break
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
        log("a Jan research job is running - waiting")
        time.sleep(60)
    env = ldr_env()
    e = subprocess.run([str(ENSURE), "Deep research"], env=env, capture_output=True, text=True, timeout=600)
    if e.returncode != 0:                          # Strata on 8080 (the on-demand launcher), as the runner starts it
        log(f"Strata did not start: {(e.stdout + e.stderr)[-300:]}")
        return 1
    log("bench lock taken, Strata up; restarting LDR in the deep profile with setup + critic + code")
    subprocess.run([str(WS / "run-ldr.sh"), "stop"], cwd=WS, env=env, capture_output=True, text=True, timeout=300)
    r = subprocess.run([str(WS / "run-ldr.sh"), "start"], cwd=WS, env=env, capture_output=True, text=True, timeout=300)
    items = sorted(stamp("items").split())
    want = {"profile": "deep", "s2": "on", "fallback": "off", "efforts": "report=medium verify=xhigh"}
    got = {k: stamp(k) for k in want}
    if r.returncode != 0 or items != sorted(["code", "critic", "setup"] + (["fixes", "read", "claims"] if BUNDLE else ["fixes"] if FIXES else [])) or got != want:
        log(f"LDR did not start as wanted (rc {r.returncode}, items {items}, {got}): {(r.stdout + r.stderr)[-300:]}")
        return 1
    tag = f"codetool-{mode}{'-fixes' if FIXES else ''}-{datetime.now():%m%d-%H%M}"
    cmd = [str(WS / ".venv" / "bin" / "python"), str(WS / "tools" / "ldr-client.py"), "research", tag, question,
           "--capture-dir", str(out / "capture"), "--max-minutes", str(budget_s // 60 + 150), "--budget-s", str(budget_s),
           "--effort-agent", "medium", "--effort-extract", "medium"]
    log(f"{tag}: research starts ({budget_s // 60} min budget)")
    t0 = time.time()
    rr = subprocess.run(cmd, cwd=WS, env={**env, "LDR_DEEP_TIME_BUDGET_S": str(budget_s)},
                        stdout=open(out / "client.out", "w"), stderr=subprocess.STDOUT)
    wall = time.time() - t0
    res = WS / "results" / tag
    if res.exists():
        for f in res.iterdir():
            if not (out / f.name).exists():
                f.rename(out / f.name)
        try:
            res.rmdir()
        except OSError:
            pass
    log(f"{tag}: client exit {rr.returncode} after {wall / 60:.1f} min; stopping LDR")
    subprocess.run([str(WS / "run-ldr.sh"), "stop"], cwd=WS, env=env, capture_output=True, text=True, timeout=300)
    k = subprocess.run(["bash", str(KCHECK), f"codetool-{mode}"], capture_output=True, text=True)
    meta = {"mode": mode, "tag": tag, "rc": rr.returncode, "wall_s": round(wall, 1), "budget_s": budget_s,
            "ended": datetime.now().isoformat(), "kernel_check_rc": k.returncode,
            "pipeline": "deep; setup + critic + code; S2 on; fallback off; agent/extract/report medium, verify xhigh"}
    (out / "run.json").write_text(json.dumps(meta, indent=1))
    fcntl.flock(lock, fcntl.LOCK_UN)
    log(f"done: {meta}")
    return 0 if rr.returncode == 0 and k.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
