"""Offline test of the staged research runner (10-29) against the C3 copy it was built from: start() and tick() run
in-process against a fake run dir; everything that would reach a service, the GPU, LDR, the jobs folder or a live run/
file is replaced by a stub. Run: nice -n 19 .venv/bin/python -I -B staging/runner-bench/tests/test_runner.py

1. Equivalence: start() on a grid of ldr.* stamp states (deep / quick job, key files yes / no) makes the same run_ldr
   calls and job updates in both runners whenever the model profile fits (no stamp, or the matching one).
2. Today's live stamps (copied, read-only) with today's model profile state: no restart that the C3 runner would not make.
3. Model profile: a different or edited profile restarts LDR (staged only), with the reason in the log.
4. paid-run.json: written before /api/start_research, removed when the start fails, kept by tick() while the job runs or
   is held, removed after; another writer's live file kept, a stale one removed; rewritten after a runner restart.
"""
import importlib.machinery
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

ST = Path("/home/USER/ai/deep-research/staging/runner-bench")
C3 = Path("/home/USER/ai/deep-research/staging/c3")
WS_LIVE = Path("/home/USER/ai/deep-research")
TMP = Path(tempfile.mkdtemp(prefix="runner-test-"))
FAILS: list[str] = []
N = [0]


def check(name: str, ok: bool, detail: str = "") -> None:
    N[0] += 1
    if not ok:
        FAILS.append(f"{name}: {detail}")
    print(f"{'ok  ' if ok else 'FAIL'} {name}{'' if ok else ' - ' + str(detail)[:600]}")


# the profile loader the runner takes from the installed package (C3, not installed yet): the staged C3 one
spec = importlib.util.spec_from_file_location("deep_modelprofile", C3 / "deep" / "modelprofile.py")
mpmod = importlib.util.module_from_spec(spec)
sys.modules["deep_modelprofile"] = mpmod
spec.loader.exec_module(mpmod)
sys.path.append(str(WS_LIVE / "tools"))      # research_common (import only); each runner puts its own folder first


def load(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(m)
    return m


new = load(ST / "tools" / "research-runner.py", "runner_new")
old = load(ST / "tools" / "research-runner.py.c3", "runner_c3")
rc = new.rc
rf = new.rf
check("both runners share research_common; the staged one uses the staged ldr_runfiles",
      old.rc is rc and Path(rf.__file__).parent == ST / "tools", rf.__file__)

# ---- stubs: nothing live -----------------------------------------------------------------------------------------------
WS_T = TMP / "ws"
RUN = WS_T / "run"
PROF = WS_T / "profiles"
RUN.mkdir(parents=True)
PROF.mkdir()
shutil.copy(C3 / "profiles" / "flash-next.env", PROF / "flash-next.env")
(PROF / "other.env").write_text("LDR_PROFILE_STATUS=measured\n")
rf.RUN_DIR, rf.PROFILES_DIR = RUN, PROF
rc.searxng_problems = lambda: {}
rc.NEXT_FILE = TMP / "next-research.json"
rc.CALL_LOG = TMP / "no-llm-calls.jsonl"
rc.paused_total = lambda *a, **k: 0.0
rc.CONTROL_FILE = TMP / "research-control.json"
rc.RUN = TMP
rc.is_night = lambda *a, **k: False
rc.bench_running = lambda: False
rc.test_lock_held = lambda: None
KEYS = [False]
LOGS = {"new": [], "old": []}
for m, tag in ((new, "new"), (old, "old")):
    m.WS = WS_T
    m.ENSURE = Path("/bin/true")
    m.MODE_FILE = TMP / "proxy-mode.json"
    m.avail_gb = lambda: 64.0
    m.log = LOGS[tag].append
    m.notify = lambda *a, **k: None
    m.ldr_up = lambda: True
    m.ldr_pid = lambda: 4242
    m.time = types.SimpleNamespace(time=time.time, sleep=lambda s: None)
    m.fallback_keys = lambda: KEYS[0]
new.RUN_DIR = RUN
check("the stubs point every runner path at the temp folder",
      new.RUN_DIR == RUN and old.WS == WS_T and new.MODE_FILE.parent == TMP and rc.CONTROL_FILE.parent == TMP)
DEEP_FILE = new.DEEP_LDR_EFFORTS_FILE
check("both runners: same efforts stamp", DEEP_FILE == old.DEEP_LDR_EFFORTS_FILE, f"{DEEP_FILE} / {old.DEEP_LDR_EFFORTS_FILE}")


def write_stamps(st: dict) -> None:
    for name in ("profile", "fallback", "s2", "quicklimits", "efforts", "items", "modelprofile"):
        p = RUN / f"ldr.{name}"
        if st.get(name) is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(st[name] + "\n")


def fake_run_ldr(calls: list):
    """What run-ldr.sh does for the runner's environment: stamps for that LDR start (as the staged C3 script writes them)."""
    def f(cmd: str, profile: str = "deep"):
        calls.append((cmd, profile))
        if cmd == "start":
            write_stamps({"profile": profile, "fallback": "on" if KEYS[0] else "off", "s2": "on",
                          "quicklimits": "on" if profile == "baseline" else "off",
                          "efforts": DEEP_FILE if profile == "deep" else "report=default verify=default",
                          "items": "setup critic" if profile == "deep" else "off",
                          "modelprofile": rf.stamp_for(os.environ.get("LDR_MODEL_PROFILE") or "flash-next")})
        return 0, "ok"
    return f


class Resp:
    def __init__(self, code: int):
        self.status_code, self.text = code, ""

    def json(self):
        return {"research_id": 77}


def run_start(m, stamps: dict, quick: bool, code: int = 200, boom: bool = False):
    """start() of runner m on these stamps -> (run_ldr calls, job updates, paid file at start_research, error)"""
    write_stamps(stamps)
    (RUN / "paid-run.json").unlink(missing_ok=True)
    calls, updates, seen = [], [], []
    m.run_ldr = fake_run_ldr(calls)
    r = m.Runner()
    job = {"id": "20261029-120000-test", "question": "q?", "mode": "quick" if quick else "deep", "budget_minutes": 30}

    def update(jid, **ch):
        updates.append({k: v for k, v in ch.items() if k not in ("runs", "started")})
        job.update(ch)
        return job

    def api(method, path, **kw):
        seen.append(rf.paid_run_live(RUN))
        if boom:
            raise RuntimeError("LDR login failed: HTTP 500")
        return Resp(code)
    r.update = update
    r.ldr.api = api
    err = None
    try:
        r.start(job, {"default_budget_minutes": 180.0})
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    return calls, updates, seen, err


# ---- 1. equivalence on a grid ------------------------------------------------------------------------------------------
GRID = {"profile": ["deep", "baseline", None], "fallback": ["on", "off", None], "s2": ["on", "off"],
        "quicklimits": ["on", "off", None], "efforts": [DEEP_FILE, "report=default verify=default", None],
        "items": ["setup critic", "critic  setup", "off", "setup critic code fixes read claims", None]}
mp_ok = rf.stamp_for("flash-next")
n = same = restarts = 0
diffs = []
t0 = time.time()
for combo in itertools.product(*GRID.values()):
    st = dict(zip(GRID, combo))
    for mps, quick, keys in itertools.product([None, mp_ok], [False, True], [False, True]):
        KEYS[0] = keys
        st["modelprofile"] = mps
        a = run_start(old, st, quick)
        b = run_start(new, st, quick)
        n += 1
        ok = a[0] == b[0] and a[1] == b[1] and (a[3] is None) == (b[3] is None)
        same += ok
        restarts += ("stop", "deep") in a[0]
        if not ok and len(diffs) < 5:
            diffs.append((st, quick, keys, a[:2], b[:2], a[3], b[3]))
check(f"start(): the same run_ldr calls and job updates in {n} stamp states (model profile fits)", same == n,
      f"{n - same} differ, e.g. {diffs[:2]}")
check("the grid exercises both paths (restart and no restart)", 0 < restarts < n, f"{restarts} restarts of {n}")
print(f"     ({n} states x 2 runners in {time.time() - t0:.1f} s; {restarts} restarts)")

# ---- 2. today's live stamps (copied read-only; the model profile as today: no stamp, no profiles/ yet) ------------------
live = {}
for name in ("profile", "fallback", "s2", "quicklimits", "efforts", "items", "modelprofile"):
    p = WS_LIVE / "run" / f"ldr.{name}"
    live[name] = p.read_text().strip() if p.exists() else None
print(f"     today's stamps: {live}")
rf.PROFILES_DIR = TMP / "no-profiles-yet"            # profiles/ does not exist before C3 is installed
for quick, keys in itertools.product([False, True], [False, True]):
    KEYS[0] = keys
    a = run_start(old, live, quick)
    b = run_start(new, live, quick)
    check(f"today's stamps ({'quick' if quick else 'deep'} job, keys {keys}): same decision as the C3 runner",
          a[0] == b[0] and a[1] == b[1], f"{a[:2]} / {b[:2]}")
    check(f"today's stamps ({'quick' if quick else 'deep'} job, keys {keys}): no model-profile reason",
          not any("model profile" in x for x in new.ldr_restart_reasons("baseline" if quick else "deep", quick, RUN)),
          new.ldr_restart_reasons("baseline" if quick else "deep", quick, RUN))
rf.PROFILES_DIR = PROF
fit = {"profile": "deep", "fallback": "off", "s2": "on", "quicklimits": "off", "efforts": DEEP_FILE, "items": "setup critic"}
KEYS[0] = False
check("a fitting LDR from before C3 (no stamp): no restart",
      run_start(new, {**fit, "modelprofile": None}, False)[0] == [] and new.ldr_restart_reasons("deep", False, RUN) == [])

# ---- 3. model profile changes -------------------------------------------------------------------------------------------
LOGS["new"].clear()
calls = run_start(new, {**fit, "modelprofile": rf.stamp_for("other")}, False)[0]
check("LDR on another profile: stop + start", calls == [("stop", "deep"), ("start", "deep")], calls)
check("... logged with the reason", any("model profile other" in l and "restarted in the deep profile" in l for l in LOGS["new"]),
      LOGS["new"][-3:])
check("... the C3 runner would not have restarted", run_start(old, {**fit, "modelprofile": rf.stamp_for("other")}, False)[0] == [])
(PROF / "flash-next.env").write_text((PROF / "flash-next.env").read_text() + "\n# edited\n")
check("flash-next.env edited since LDR started: restart",
      run_start(new, {**fit, "modelprofile": mp_ok}, False)[0] == [("stop", "deep"), ("start", "deep")])
check("... after the restart the new stamp fits", new.ldr_restart_reasons("deep", False, RUN) == [])
shutil.copy(C3 / "profiles" / "flash-next.env", PROF / "flash-next.env")
os.environ["LDR_MODEL_PROFILE"] = "other"
check("runner's WANT_MODEL_PROFILE comes from LDR_MODEL_PROFILE at start (here: flash-next)", new.WANT_MODEL_PROFILE == "flash-next")
new.WANT_MODEL_PROFILE = "other"
check("want 'other', no stamp: restart", run_start(new, {**fit, "modelprofile": None}, False)[0] == [("stop", "deep"), ("start", "deep")])
check("want 'other', its stamp: no restart", run_start(new, {**fit, "modelprofile": rf.stamp_for("other")}, False)[0] == [])
new.WANT_MODEL_PROFILE = "flash-next"
del os.environ["LDR_MODEL_PROFILE"]

# ---- 4. paid-run.json in start() ---------------------------------------------------------------------------------------
me = os.getpid()
for quick in (False, True):
    KEYS[0] = True
    st = {**fit, "fallback": "on", "modelprofile": mp_ok} if not quick else \
        {"profile": "baseline", "fallback": "on", "s2": "on", "quicklimits": "on", "items": "off", "modelprofile": mp_ok}
    calls, updates, seen, err = run_start(new, st, quick)
    s0 = seen[0] or {}
    check(f"start ({'quick' if quick else 'deep'}): run file live at /api/start_research = research + job id + our pid",
          s0.get("kind") == "research" and s0.get("run") == "20261029-120000-test" and s0.get("pid") == me
          and "route" not in s0 and "cache" not in s0, s0)
    check(f"start ({'quick' if quick else 'deep'}): kept after a good start (job running)",
          rf.paid_run_live(RUN) is not None and updates[-1].get("state") == "running" and err is None, (updates[-1:], err))
calls, updates, seen, err = run_start(new, {**fit, "modelprofile": mp_ok}, False, code=500)
check("start refused (HTTP 500): file written, then removed; job queued",
      seen[0] is not None and not (RUN / "paid-run.json").exists() and updates[-1].get("state") == "queued", updates[-1:])
calls, updates, seen, err = run_start(new, {**fit, "modelprofile": mp_ok}, False, boom=True)
check("start raised: file removed, the error goes on to tick() as before",
      seen[0] is not None and not (RUN / "paid-run.json").exists() and err and "LDR login failed" in err, err)
a = run_start(old, {**fit, "modelprofile": mp_ok}, False, boom=True)
check("... the C3 runner raised the same way", a[3] == err, a[3])

# ---- 5. tick(): the file follows the job -----------------------------------------------------------------------------
JOBS: list = []
rc.all_jobs = lambda: JOBS
rc.settings = lambda: {"yield_minutes": 5.0, "ldr_idle_stop_minutes": 15.0, "night_pause": "off"}
new.ldr_pid = lambda: None                           # no idle stop
watched, started = [], []
R = new.Runner()
R.watch = lambda job, s: watched.append(job["id"])
R.start = lambda job, s: started.append(job["id"])
P = RUN / "paid-run.json"
P.unlink(missing_ok=True)


def tick_with(state: str | None):
    JOBS[:] = [] if state is None else [{"id": "J1", "state": state, "question": "q", "mode": "deep"}]
    R.tick()
    return rf.paid_run_live(RUN)


rec = tick_with("running")
check("tick, job running: file = research J1, our pid", rec and rec["run"] == "J1" and rec["pid"] == me, rec)
m0 = P.stat().st_mtime_ns
time.sleep(0.02)
tick_with("running")
check("tick again: not rewritten (unchanged)", P.stat().st_mtime_ns == m0)
check("tick, job held (paused: night / you): kept", (tick_with("paused") or {}).get("run") == "J1")
check("tick, job 'starting' (start() failed half-way): removed", tick_with("starting") is None and not P.exists())
tick_with("running")
check("tick, job finished: removed", tick_with("finished") is None and not P.exists())
tick_with("running")
check("tick, job cancelled: removed", tick_with("cancelled") is None and not P.exists())
tick_with("running")
check("tick, no jobs: removed", tick_with(None) is None and not P.exists())
check("tick, job queued: nothing written (start() writes it)", tick_with("queued") is None and started[-1:] == ["J1"])
child = subprocess.Popen(["sleep", "30"])
rf.paid_run_write("test", "screen-deep-p7b/s01", "bench2", RUN, route="7b", pid=child.pid)
tick_with(None)
check("tick, a measurement's live file: kept", (rf.paid_run_live(RUN) or {}).get("writer") == "bench2")
child.kill()
child.wait()
tick_with(None)
check("tick, that file after its writer died: removed", not P.exists())
dead = subprocess.Popen(["true"])
dead.wait()
P.write_text(json.dumps({"kind": "research", "run": "J1", "writer": "research-runner", "pid": dead.pid, "pid_start": "1"}))
rec = tick_with("running")
check("runner restarted mid-job (old runner pid dead): rewritten with this pid", rec and rec["pid"] == me, rec)
tick_with(None)
os.chmod(RUN, 0o555)                                   # an unwritable run dir: logged once, the tick goes on
try:
    LOGS["new"].clear()
    tick_with("running")
    tick_with("running")
    errs = [l for l in LOGS["new"] if "paid-run.json" in l]
    check("write error: tick goes on, logged once", len(errs) == 1 and watched[-1] == "J1", LOGS["new"])
finally:
    os.chmod(RUN, 0o755)

# ---- nothing live touched -----------------------------------------------------------------------------------------------
for f in ("paid-run.json", "paid-run.lock", "ldr.modelprofile"):
    check(f"live run/{f} not created", not (WS_LIVE / "run" / f).exists())
shutil.rmtree(TMP)
print(f"\n{N[0] - len(FAILS)} / {N[0]} pass" + ("" if not FAILS else "\nFAILED:\n  " + "\n  ".join(FAILS)))
sys.exit(1 if FAILS else 0)
