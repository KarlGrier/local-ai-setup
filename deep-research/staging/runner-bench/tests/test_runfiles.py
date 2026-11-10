"""Offline tests of tools/ldr_runfiles.py and the staged paid_budget.py reader (10-29). Temp folders only: no live run/,
no services, no keys. Run: nice -n 19 .venv/bin/python -I -B staging/runner-bench/tests/test_runfiles.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ST = Path("/home/USER/ai/deep-research/staging/runner-bench")
C3 = Path("/home/USER/ai/deep-research/staging/c3")
ITEM7 = Path("/home/USER/ai/deep-research/staging/item7/tools")
PY = "/home/USER/ai/deep-research/.venv/bin/python"
LIVE_RUN = Path("/home/USER/ai/deep-research/run")
TMP = Path(tempfile.mkdtemp(prefix="runfiles-test-"))
os.environ["PAID_SEARCH_RUN_NOW"] = str(TMP / "run" / "paid-run.json")   # the staged reader reads the temp run dir
sys.path.insert(0, str(ST / "tools"))
import ldr_runfiles as rf  # noqa: E402

FAILS: list[str] = []
N = [0]


def check(name: str, ok: bool, detail: str = "") -> None:
    N[0] += 1
    if not ok:
        FAILS.append(f"{name}: {detail}")
    print(f"{'ok  ' if ok else 'FAIL'} {name}{'' if ok else ' - ' + detail}")


run = TMP / "run"
prof = TMP / "profiles"
run.mkdir()
prof.mkdir()
shutil.copy(C3 / "profiles" / "flash-next.env", prof / "flash-next.env")
(prof / "other.env").write_text("LDR_PROFILE_STATUS=measured\n")

# ---- 1. the model profile stamp ------------------------------------------------------------------------------------
# run-ldr.sh's own stamp line (staged copy), run on the temp profile -> must equal stamp_for()
line = next(l for l in (ST / "run-ldr.sh").read_text().splitlines() if 'ldr.modelprofile"' in l and "sha256sum" in l)
for name in ("flash-next", "other"):
    pfile = str((prof / f"{name}.env").resolve())
    subprocess.run(["bash", "-c", line.strip()], env={"PATH": os.environ["PATH"], "P_FILE": pfile, "RUN": str(run)},
                   check=True)
    got = (run / "ldr.modelprofile").read_text().strip()
    check(f"stamp_for({name}) = run-ldr.sh's stamp line", rf.stamp_for(name, prof) == got, f"{rf.stamp_for(name, prof)} vs {got}")
check("stamp_for(path) = stamp_for(name)", rf.stamp_for(str(prof / "flash-next.env"), prof) == rf.stamp_for("flash-next", prof))
check("stamp_for(missing) is None", rf.stamp_for("nope", prof) is None)

(run / "ldr.modelprofile").unlink()
mm = lambda want, pd=prof: rf.modelprofile_mismatch(want, run, pd)  # noqa: E731
check("no stamp + flash-next: fits", mm("flash-next") == "")
check("no stamp + default (None): fits", mm(None) == "")
check("no stamp + flash-next, no profiles dir at all (today): fits", mm("flash-next", TMP / "nowhere") == "")
check("no stamp + other: restart", mm("other").startswith("model profile: LDR runs the built-in values"), mm("other"))
(run / "ldr.modelprofile").write_text(rf.stamp_for("flash-next", prof) + "\n")
check("stamp flash-next + flash-next: fits", mm("flash-next") == "")
check("stamp flash-next + path to it: fits", mm(str(prof / "flash-next.env")) == "")
check("stamp flash-next + other: restart", mm("other").startswith("model profile flash-next "), mm("other"))
check("stamp flash-next + missing profile: restart (run-ldr.sh then refuses)", "no file" in mm("ghost"), mm("ghost"))
old = (prof / "flash-next.env").read_text()
(prof / "flash-next.env").write_text(old + "\n# edited\n")
check("flash-next edited since LDR started: restart", "file changed since LDR started" in mm("flash-next"), mm("flash-next"))
(prof / "flash-next.env").write_text(old)
check("edit undone: fits again", mm("flash-next") == "")

cli = [PY, "-I", "-B", str(ST / "tools" / "ldr_runfiles.py")]
r = subprocess.run(cli + ["mp-check", "--run-dir", str(run), "--profiles-dir", str(prof), "--want", "flash-next"],
                   capture_output=True, text=True)
check("CLI mp-check fits: exit 0, no output", r.returncode == 0 and not r.stdout.strip(), f"{r.returncode} {r.stdout!r}")
r = subprocess.run(cli + ["mp-check", "--run-dir", str(run), "--profiles-dir", str(prof), "--want", "other"],
                   capture_output=True, text=True)
check("CLI mp-check differs: exit 1 + why", r.returncode == 1 and "model profile" in r.stdout, f"{r.returncode} {r.stdout!r}")
r = subprocess.run(cli + ["mp-check", "--run-dir", str(run), "--profiles-dir", str(prof)], capture_output=True, text=True,
                   env={**os.environ, "LDR_MODEL_PROFILE": "other"})
check("CLI mp-check default = $LDR_MODEL_PROFILE", r.returncode == 1, f"{r.returncode} {r.stdout!r}")

# ---- 2. run/paid-run.json ------------------------------------------------------------------------------------------
P = run / "paid-run.json"
me = os.getpid()
rec = rf.paid_run_write("research", "20261029-job", "research-runner", run)
d = json.loads(P.read_text())
check("write: kind/run/writer/pid/pid_start", d["kind"] == "research" and d["run"] == "20261029-job" and d["pid"] == me
      and d["pid_start"] == rf.pid_start(me) and d["writer"] == "research-runner" and "route" not in d and "cache" not in d, str(d))
check("write: no temp file left", sorted(p.name for p in run.iterdir() if p.name.startswith(".paid-run")) == [])
check("write: mode 644", oct(P.stat().st_mode & 0o777) == "0o644", oct(P.stat().st_mode))
check("live", rf.paid_run_live(run) == d)
m0 = P.stat().st_mtime_ns
time.sleep(0.02)
check("only_if_changed: identical -> not rewritten",
      rf.paid_run_write("research", "20261029-job", "research-runner", run, only_if_changed=True) is None
      and P.stat().st_mtime_ns == m0)
check("only_if_changed: other job -> rewritten",
      rf.paid_run_write("research", "20261029-job2", "research-runner", run, only_if_changed=True)["run"] == "20261029-job2")
rf.paid_run_write("test", "screen-deep-p7b/s01", "bench2", run, route="7b", cache=True)
d = json.loads(P.read_text())
check("test record: route + cache (JSON bool)", d["kind"] == "test" and d["route"] == "7b" and d["cache"] is True, str(d))
check("only_if_changed: route differs -> rewritten",
      rf.paid_run_write("test", "screen-deep-p7b/s01", "bench2", run, route="7c", cache=True, only_if_changed=True) is not None)
check("only_if_changed: cache key dropped -> rewritten",
      rf.paid_run_write("test", "screen-deep-p7b/s01", "bench2", run, route="7c", only_if_changed=True) is not None
      and "cache" not in json.loads(P.read_text()))
for bad, kw in (("bad kind", dict(kind="chat", run="x")), ("empty run", dict(kind="test", run=" "))):
    try:
        rf.paid_run_write(writer="t", run_dir=run, **kw)
        check(f"write refuses {bad}", False, "no error")
    except ValueError:
        check(f"write refuses {bad}", True)
dead = subprocess.Popen(["true"])
dead.wait()
try:
    rf.paid_run_write("test", "x/y", "t", run, pid=dead.pid)
    check("write refuses a dead pid", False, "no error")
except ValueError:
    check("write refuses a dead pid", True)

# a live other writer (a child process), then the same file once that writer is gone
child = subprocess.Popen(["sleep", "30"])
rf.paid_run_write("test", "hard-screen-deep-p7c/h01", "bench2", run, route="7c", pid=child.pid)
check("clear by another pid: live file kept", rf.paid_run_clear(run, pid=me).startswith("kept") and P.exists())
check("clear --stale-only: live file kept", rf.paid_run_clear(run, stale_only=True).startswith("kept") and P.exists())
child.kill()
for _ in range(200):                                    # the signal lands asynchronously: wait for state Z
    if Path(f"/proc/{child.pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
        break
    time.sleep(0.01)
check("writer died, not yet reaped (zombie): stale", rf.paid_run_live(run) is None)
child.wait()
check("writer gone: stale (readers ignore it)", rf.paid_run_live(run) is None)
check("paid-show says STALE", "STALE" in rf.paid_run_text(run), rf.paid_run_text(run))
check("clear by another pid removes a stale file", rf.paid_run_clear(run, pid=me) == "removed (stale)" and not P.exists())

rf.paid_run_write("research", "j", "research-runner", run)
check("clear own (pid) removes", rf.paid_run_clear(run, pid=me) == "removed (own)" and not P.exists())
rf.paid_run_write("research", "j", "research-runner", run)
check("clear --stale-only keeps our own live file", rf.paid_run_clear(run, pid=me, stale_only=True).startswith("kept"))
d = json.loads(P.read_text())
d["pid_start"] = "1"                                   # same pid, other start time = a reused pid
P.write_text(json.dumps(d))
check("pid reused (start time differs): stale", rf.paid_run_live(run) is None)
P.write_text(json.dumps({"kind": "test", "run": "by-hand/q1", "route": "7b"}))
check("no pid, fresh (by hand): live", rf.paid_run_live(run) is not None)
old_t = time.time() - 13 * 3600
os.utime(P, (old_t, old_t))
check("no pid, 13 h old: stale", rf.paid_run_live(run) is None)
check("clear removes the old pid-less file", rf.paid_run_clear(run, stale_only=True) == "removed (stale)")
P.write_text("{not json")
check("garbage: not live", rf.paid_run_live(run) is None)
check("clear removes garbage", rf.paid_run_clear(run, stale_only=True) == "removed (unreadable)" and not P.exists())
check("clear with no file: none", rf.paid_run_clear(run, pid=me) == "none")
r = subprocess.run(cli + ["paid-clear", "--run-dir", str(run)], capture_output=True, text=True)
check("CLI paid-clear needs --stale-only", r.returncode != 0)
child = subprocess.Popen(["sleep", "30"])
rf.paid_run_write("test", "a/b", "bench2", run, pid=child.pid)
r = subprocess.run(cli + ["paid-clear", "--stale-only", "--run-dir", str(run)], capture_output=True, text=True)
check("CLI paid-clear --stale-only: live kept", r.stdout.startswith("kept") and P.exists(), r.stdout)
child.kill()
child.wait()
r = subprocess.run(cli + ["paid-clear", "--stale-only", "--run-dir", str(run)], capture_output=True, text=True)
check("CLI paid-clear --stale-only: stale removed", r.stdout.strip() == "removed (stale)" and not P.exists(), r.stdout)

# ---- 3. the reader: staged paid_budget.py (item 7 + the stale check) -------------------------------------------------
sys.path.insert(0, str(ST / "item7" / "tools"))
import paid_budget as pb  # noqa: E402

check("paid_budget reads the temp run dir", pb.RUN_NOW_FILE == P, str(pb.RUN_NOW_FILE))
rf.paid_run_write("research", "20261029-jan", "research-runner", run)
check("reader: live research file -> kind research, run = job id",
      pb.kind("ldr") == "research" and pb.run_id("ldr") == "20261029-jan", f"{pb.kind('ldr')} {pb.run_id('ldr')}")
check("reader: chat client ignores the file", pb.kind("jan") == "chat" and pb.run_id("jan") == "")
child = subprocess.Popen(["sleep", "30"])
rf.paid_run_write("test", "screen-deep-p7b/s01", "bench2", run, route="7b", cache=True, pid=child.pid)
check("reader: live test file -> kind test, run id", pb.kind("ldr") == "test" and pb.run_id("ldr") == "screen-deep-p7b/s01")
sys.path.insert(1, str(ITEM7))
import search_route  # noqa: E402  (staged item 7, unchanged)

cfg, err = search_route.load_config()
check("route from the live run file: 7b", search_route.pick_profile(cfg, pb._run_now()) == ("7b", "run file"),
      str(search_route.pick_profile(cfg, pb._run_now())))
child.kill()
child.wait()
check("reader: writer died -> file ignored (research without run id = no paid search)",
      pb._run_now() == {} and pb.kind("ldr") == "research" and pb.run_id("ldr") == "")
check("route from a stale run file: today's fallback", search_route.pick_profile(cfg, pb._run_now())[0] == "fallback")
ok, why = pb.run_reserve("research", "ldr")
check("reader: stale file -> research refused (no run id)", not ok and "no PAID_SEARCH_RUN" in why, why)
P.write_text(json.dumps({"kind": "test", "run": "by-hand/q1"}))
check("reader: pid-less fresh file (item 7's tests) used", pb.run_id("ldr") == "by-hand/q1")
os.utime(P, (old_t, old_t))
check("reader: pid-less 13 h old file ignored", pb._run_now() == {})
P.unlink()
check("reader: writer and reader agree on stale (same /proc rule)", rf.pid_start(me) == pb._pid_start(me)
      and rf.pid_start(dead.pid) is None and pb._pid_start(dead.pid) is None)
r = subprocess.run([PY, "-I", "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2]); "
                    "import paid_budget, ldr_runfiles; print(paid_budget.RUN_NOW_FILE == ldr_runfiles.RUN_DIR / ldr_runfiles.PAID_FILE)",
                    str(ST / "item7" / "tools"), str(ST / "tools")],
                   capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "PAID_SEARCH_RUN_NOW"})
check("default paths: reader's file = writers' file (run/paid-run.json)", r.stdout.strip() == "True", r.stdout + r.stderr)

# ---- nothing live touched -----------------------------------------------------------------------------------------------
for f in ("paid-run.json", "paid-run.lock", "ldr.modelprofile"):
    check(f"live run/{f} not created", not (LIVE_RUN / f).exists())
shutil.rmtree(TMP)
print(f"\n{N[0] - len(FAILS)} / {N[0]} pass" + ("" if not FAILS else "\nFAILED:\n  " + "\n  ".join(FAILS)))
sys.exit(1 if FAILS else 0)
