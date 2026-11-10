#!/usr/bin/env python3
"""harness_run.py - one harness on one task, recorded and graded (usability round, 2026-10-15).

    harness_run.py ARM TASK [--tag TAG]
      ARM:  opencode | codex | dsh-minimal | dsh-standard | dsh-ptc
      TASK: a1_inventory | a2_textstats | a3_cronlite | rt_effort

Each harness runs through its usability launcher (configs/usability/bin/*: offline except 127.0.0.1) with a measurement
copy of its config whose only change is the endpoint: 127.0.0.1:8090 (turnlog.py, a recording pass-through) instead of
Strata's 8080. Fresh repo per run (tasks.py), fresh harness home per run. Result: runs/<label>/result.json.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tasks  # noqa: E402
import turn_metrics  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
CFG = WS / "configs/usability"
U = WS / "tmp/usability"
RUNS = U / "runs"
TURNS = WS / "logs/usability/turns"
MEASURE = "http://127.0.0.1:8090/v1"


def main():
    arm, task = sys.argv[1], sys.argv[2]
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "r1"
    label = f"{arm}-{task}-{tag}"
    d = RUNS / label
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    if (TURNS / label).exists():
        shutil.rmtree(TURNS / label)
    repo = d / "repo"
    prompt = tasks.prepare(task, repo)
    (d / "prompt.txt").write_text(prompt)
    timeout = 3600 if task == "rt_effort" else 1800
    (TURNS / "LABEL").write_text(label)
    env = dict(os.environ, STRATA_NO_AUTOSTART="1")   # measured runs never start Strata (launchers, 2026-10-17)
    t0 = time.time()
    if arm == "opencode":
        conf = d / "opencode-measure.jsonc"
        conf.write_text((CFG / "opencode/opencode.jsonc").read_text().replace("http://127.0.0.1:8080/v1", MEASURE))
        env.update(OPENCODE_CONFIG=str(conf))
        cmd = [str(CFG / "bin/opencode-strata"), "run", "--auto", prompt]
    elif arm == "codex":
        home = d / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text((CFG / "codex/config.toml").read_text().replace("http://127.0.0.1:8080/v1",
                                                                                          MEASURE))
        env["CODEX_HOME_STRATA"] = str(home)
        cmd = [str(CFG / "bin/codex-strata"), "exec", "--skip-git-repo-check", "-c", 'approval_policy="never"',
               "-c", 'sandbox_mode="workspace-write"', prompt]
    elif arm.startswith("dsh-"):
        home = d / "dsh-home"
        (home / "profiles/web").mkdir(parents=True)
        (home / "profiles/web/cordis.patch.yml").write_text(
            (CFG / "dsh/web.cordis.patch.yml").read_text().replace("http://127.0.0.1:8080/v1", MEASURE))
        mode = {"dsh-minimal": "Minimal", "dsh-standard": "Standard", "dsh-ptc": "PTC"}[arm]
        cmd = [sys.executable, str(Path(__file__).parent / "dsh_drive.py"), "--repo", str(repo), "--mode", mode,
               "--prompt-file", str(d / "prompt.txt"), "--home", str(home), "--out", str(d / "ui"),
               "--turnlog", str(TURNS / label), "--timeout", str(timeout - 120)]
    else:
        raise SystemExit(f"unknown arm {arm}")
    with open(d / "stdout.txt", "w") as so, open(d / "stderr.txt", "w") as se:
        try:
            p = subprocess.run(cmd, cwd=repo, env=env, stdout=so, stderr=se, timeout=timeout)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    wall = round(time.time() - t0, 1)
    (TURNS / "LABEL").write_text("idle")
    g = tasks.grade(task, repo)
    summary, turns = turn_metrics.run_metrics(TURNS / label)
    diff = subprocess.run(["git", "-C", str(repo), "diff", "--stat"], capture_output=True, text=True).stdout
    res = {"label": label, "arm": arm, "task": task, "rc": rc, "wall_s": wall, "grade": g, "metrics": summary,
           "diffstat": diff[-1500:]}
    (d / "result.json").write_text(json.dumps(res, indent=1))
    (d / "turns.json").write_text(json.dumps(turns, indent=1))
    print(json.dumps({"label": label, "rc": rc, "wall_s": wall, "green": g["green"],
                      **{k: summary[k] for k in ("steps", "output_tokens", "reread_tokens", "unparsed_calls",
                                                 "bad_tool_args", "early_ends", "http_errors")}}))


if __name__ == "__main__":
    main()
