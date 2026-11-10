"""Offline test of the staged bench queue (bench2-queue.sh + bench2.py, 10-29). Temp folders only; no LDR, no services.
Run: nice -n 19 .venv/bin/python -I -B staging/runner-bench/tests/test_queue.py

1. bash -n on the staged queue and run-ldr.sh.
2. The queue's restart decision: the staged block (ldr_restart_why, cut from the staged script) against the inline
   condition of the live queue (cut from bench2-queue.sh.orig), on a grid of stamp states and on today's stamps
   (copied read-only): the same decision whenever the model profile fits; plus the model profile and item 7 cases.
3. The queue's new column handling (cut from the staged script).
4. bench2.py (staged vs .orig, both loaded with WS / B pointed at a temp folder, ldr-client stubbed):
   next (old 7 columns unchanged; --wide adds route / cache / model profile), run's checks, and the item 7 run file
   around each question (written before, removed after - also when the client call fails).
"""
import importlib.machinery
import importlib.util
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import types
from contextlib import redirect_stdout
from pathlib import Path

ST = Path("/home/USER/ai/deep-research/staging/runner-bench")
C3 = Path("/home/USER/ai/deep-research/staging/c3")
WS_LIVE = Path("/home/USER/ai/deep-research")
PY = "/home/USER/ai/deep-research/.venv/bin/python"
TMP = Path(tempfile.mkdtemp(prefix="queue-test-"))
FAILS: list[str] = []
N = [0]


def check(name: str, ok: bool, detail: str = "") -> None:
    N[0] += 1
    if not ok:
        FAILS.append(f"{name}: {detail}")
    print(f"{'ok  ' if ok else 'FAIL'} {name}{'' if ok else ' - ' + str(detail)[:700]}")


# ---- 1. syntax --------------------------------------------------------------------------------------------------------
for f in (ST / "tools" / "bench2-queue.sh", ST / "run-ldr.sh"):
    r = subprocess.run(["bash", "-n", str(f)], capture_output=True, text=True)
    check(f"bash -n {f.name}", r.returncode == 0, r.stderr)

# ---- 2. the restart decision --------------------------------------------------------------------------------------------
staged = (ST / "tools" / "bench2-queue.sh").read_text()
block = staged[staged.index("# ---- 10-29: does the running LDR fit"):staged.index("# ---- end of the LDR fit block ----")]
orig = (ST / "tools" / "bench2-queue.sh.orig").read_text().splitlines()
i0 = next(i for i, l in enumerate(orig) if l.startswith('  if [ "$(cat run/ldr.profile'))
i1 = next(i for i in range(i0, i0 + 6) if "! curl -s -m 5" in orig[i])
cond = "\n".join(orig[i0:i1 + 1])
check("the live queue's condition found (4 lines, ends with the curl check)", i1 - i0 == 3 and cond.rstrip().endswith("then"), cond)
cond = cond.replace(" \\\n     || ! curl -s -m 5 -o /dev/null http://127.0.0.1:5000/auth/login; then", "; then")
cond = cond.replace("run/", "$d/")
check("... cut without the curl check, on $d", "curl" not in cond and "run/" not in cond and cond.count("$d/") == 6
      and cond.endswith("!= off ]; then"), cond)
old_fn = f'old_restart() {{\n  local d=$1 PROF=$2 WANT_EFF=$3 WANT_ITEMS=$4\n{cond}\n    echo yes; else echo no; fi\n}}\n'

prof = TMP / "profiles"
prof.mkdir()
shutil.copy(C3 / "profiles" / "flash-next.env", prof / "flash-next.env")
(prof / "other.env").write_text("LDR_PROFILE_STATUS=measured\n")
sys.path.insert(0, str(ST / "tools"))
import ldr_runfiles as rf  # noqa: E402

MP_OK, MP_OTHER = rf.stamp_for("flash-next", prof), rf.stamp_for("other", prof)
# the helper call inside the block, pointed at the staged helper and the temp profiles (the block itself is unchanged)
harness = (block + "\n" + old_fn +
           f'runfiles() {{ "{PY}" -I -B "{ST}/tools/ldr_runfiles.py" "$@" --profiles-dir "{prof}"; }}\n')
STAMPS = ("profile", "efforts", "items", "fallback", "s2", "quicklimits", "modelprofile")
GRID = {"profile": ["deep", "baseline", None], "efforts": ["report=medium verify=xhigh", "report=default verify=default", None],
        "items": ["critic setup", "setup critic", "claims code critic fixes read setup", "off", "", None],
        "fallback": ["off", "on", None], "s2": ["off", "on", None], "quicklimits": ["off", "on", None]}
WANTS = [("deep", "report=medium verify=xhigh", "critic setup"), ("deep", "report=default verify=default", "off"),
         ("baseline", "report=default verify=default", "off"),
         ("deep", "report=medium verify=xhigh", "claims code critic fixes read setup")]


def bash_cases(cases: list[tuple[dict, tuple, str, str]]) -> list[tuple[str, str]]:
    """Each case: stamps, (PROF, WANT_EFF, WANT_ITEMS), WANT_FB, MPROF -> (old yes/no, new reason) from one bash."""
    d = TMP / "run"
    lines = [harness, "set +e"]
    for st, (p, e, it), fb, mp in cases:
        for name in STAMPS:
            v = st.get(name)
            lines.append(f"rm -f '{d}/ldr.{name}'" if v is None else f"printf '%s\\n' '{v}' > '{d}/ldr.{name}'")
        lines.append(f"o=$(old_restart '{d}' '{p}' '{e}' '{it}'); n=$(ldr_restart_why '{d}' '{p}' '{e}' '{it}' '{fb}' '{mp}' 2>/dev/null)")
        lines.append('printf "%s\\t%s\\n" "$o" "$n"')
    d.mkdir(exist_ok=True)
    r = subprocess.run(["bash", "-s"], input="\n".join(lines), capture_output=True, text=True)
    out = [tuple((l + "\t").split("\t")[:2]) for l in r.stdout.splitlines()]
    assert len(out) == len(cases), (len(out), len(cases), r.stderr[-500:])
    return out


cases = []
for combo in itertools.product(*GRID.values()):
    st = dict(zip(GRID, combo))
    for want, mps in itertools.product(WANTS, [None, MP_OK]):
        cases.append(({**st, "modelprofile": mps}, want, "off", "flash-next"))
t0 = time.time()
res = bash_cases(cases)
bad = [(c, r) for c, r in zip(cases, res) if (r[0] == "yes") != bool(r[1])]
n_restart = sum(r[0] == "yes" for r in res)
check(f"queue: the same restart decision as the live queue in {len(cases)} stamp states (model profile fits)", not bad,
      bad[:3])
check("the grid exercises both decisions", 0 < n_restart < len(cases), n_restart)
print(f"     ({len(cases)} states in {time.time() - t0:.1f} s; {n_restart} restarts)")

live = {}
for name in STAMPS:
    p = WS_LIVE / "run" / f"ldr.{name}"
    live[name] = p.read_text().strip() if p.exists() else None
print(f"     today's stamps: {live}")
plan_wants = WANTS + [("deep", f"report={live['efforts'].split()[0].split('=')[1]} verify={live['efforts'].split()[1].split('=')[1]}"
                       if live.get("efforts") else "report=default verify=default",
                       " ".join(sorted((live.get("items") or "off").split())))]
res = bash_cases([(live, w, "off", "flash-next") for w in plan_wants])
check("today's stamps: the same decision as the live queue for every want (incl. the running setup)",
      all((r[0] == "yes") == bool(r[1]) for r in res), list(zip(plan_wants, res)))
check("today's stamps: no model-profile reason (no stamp yet = flash-next)", not any("model profile" in r[1] for r in res), res)
print(f"     today's stamps + the running setup's want: live queue {res[-1][0]}, staged: {res[-1][1] or 'fits'}"
      " (S2 on = an LDR the queue did not start; both restart it)")

fit = {"profile": "deep", "efforts": "report=medium verify=xhigh", "items": "critic setup", "fallback": "off", "s2": "off",
       "quicklimits": "off"}
W = WANTS[0]
r = dict(zip(["no stamp", "stamp ok", "other", "edited"],
             bash_cases([({**fit, "modelprofile": None}, W, "off", "flash-next"),
                         ({**fit, "modelprofile": MP_OK}, W, "off", "flash-next"),
                         ({**fit, "modelprofile": MP_OTHER}, W, "off", "flash-next"),
                         ({**fit, "modelprofile": "flash-next 000000000000"}, W, "off", "flash-next")])))
check("model profile: no stamp / matching stamp fit", r["no stamp"][1] == "" and r["stamp ok"][1] == "", r)
check("model profile: LDR on 'other' -> restart with the reason", r["other"][1].startswith("model profile other"), r["other"])
check("model profile: flash-next edited -> restart", "file changed since LDR started" in r["edited"][1], r["edited"])
r = bash_cases([({**fit, "modelprofile": MP_OK}, W, "off", "other"), ({**fit, "modelprofile": MP_OTHER}, W, "off", "other")])
check("step wants 'other': restart from flash-next, fits on 'other'", r[0][1].startswith("model profile flash-next") and r[1][1] == "", r)
r = bash_cases([({**fit, "fallback": "on"}, W, "on", "flash-next"), ({**fit, "fallback": "off"}, W, "on", "flash-next"),
                ({**fit, "fallback": None}, W, "on", "flash-next"), ({**fit, "fallback": "on"}, W, "off", "flash-next")])
check("item 7 step: fallback on fits; off / missing -> restart; an ordinary step on a fallback LDR -> restart",
      r[0][1] == "" and r[1][1] == "search fallback off -> on" and r[2][1] == "search fallback off -> on"
      and r[3][1] == "search fallback on -> off", r)
# the helper failing (not installed, broken): LDR is left as it is, the reason goes to stderr
brk = harness.replace(f'"{ST}/tools/ldr_runfiles.py"', f'"{TMP}/missing.py"')
d = TMP / "run"
for name, v in fit.items():
    (d / f"ldr.{name}").write_text(v + "\n")
(d / "ldr.modelprofile").write_text(MP_OTHER + "\n")
rr = subprocess.run(["bash", "-c", brk + f"\nldr_restart_why '{d}' deep 'report=medium verify=xhigh' 'critic setup' off flash-next"],
                    capture_output=True, text=True)
check("helper missing: no restart, the failure on stderr", rr.stdout == "" and "model profile check failed" in rr.stderr,
      (rr.stdout, rr.stderr[-300:]))

# ---- 3. the queue's new columns ---------------------------------------------------------------------------------------
lines = [l for l in staged.splitlines() if l.lstrip().startswith(('[ "${ROUTE:--}"', 'WANT_FB=off; FBENV=""'))]
check("the column lines found", len(lines) == 2, lines)


def columns(next_line: str, env: dict | None = None) -> dict:
    sh = ('read -r SET PROF ID EFF LABEL VEFF ITEMS ROUTE PCACHE MPROF <<< "$NEXT"\n' + "\n".join(lines) +
          '\nprintf "%s|%s|%s|%s|%s|%s" "$ITEMS" "$ROUTE" "$PCACHE" "$MPROF" "$WANT_FB" "$FBENV"')
    out = subprocess.run(["bash", "-c", sh], capture_output=True, text=True, env={"PATH": os.environ["PATH"], "NEXT": next_line,
                                                                                  **(env or {})}).stdout
    return dict(zip(["items", "route", "cache", "mprof", "want_fb", "fbenv"], out.split("|")))


c = columns("screen deep s01 medium p4 xhigh setup,critic - - -")
check("ordinary step: no route, fallback off, flash-next", c == {"items": "setup,critic", "route": "", "cache": "", "mprof": "flash-next",
                                                                 "want_fb": "off", "fbenv": ""}, c)
c = columns("screen deep s01 medium p7b xhigh setup,critic 7b on -", {"LDR_MODEL_PROFILE": "other"})
check("item 7 step: route, cache, fallback on; model profile from LDR_MODEL_PROFILE",
      c == {"items": "setup,critic", "route": "7b", "cache": "on", "mprof": "other", "want_fb": "on",
            "fbenv": "LDR_SEARCH_FALLBACK=1"}, c)
c = columns("screen deep s01 - - - - - - sonnet-5-5")
check("a step's model_profile wins", c["mprof"] == "sonnet-5-5" and c["route"] == "", c)
check("the start lines unset the fallback first, then set it for item 7 (env -u ... $FBENV)",
      staged.count("$ITEMENV $FBENV LDR_MODEL_PROFILE=$MPROF") == 2 and staged.count("-u LDR_SEARCH_FALLBACK") == 2)
check("bench2.py gets --model-profile and the item 7 flags",
      "--model-profile $MPROF ${ROUTE:+--paid-route $ROUTE} ${PCACHE:+--paid-cache $PCACHE}" in staged)
check("the queue does not write paid-run.json itself (bench2.py owns it for each question)",
      "paid-run.json" not in staged.replace("bench2.py writes run/paid-run.json", ""))

# ---- 4. bench2.py --------------------------------------------------------------------------------------------------------
WS_T = TMP / "ws"
B = WS_T / "results" / "bench2"
(WS_T / "run").mkdir(parents=True)
(WS_T / "tools").mkdir()
shutil.copytree(prof, WS_T / "profiles")         # bench2.py reads WS/profiles (as the installed one will)
B.mkdir(parents=True)
(B / "questions-screen.jsonl").write_text(json.dumps({"id": "s01", "kind": "checkable", "question": "q1?"}) + "\n" +
                                          json.dumps({"id": "s02", "kind": "open", "question": "q2?"}) + "\n")
PLAN = [{"set": "screen", "profile": "deep", "effort": "medium", "label": "p4", "verify_effort": "xhigh",
         "items": ["setup", "critic"]},
        {"set": "screen", "profile": "deep", "effort": "medium", "label": "p7b", "verify_effort": "xhigh",
         "items": ["setup", "critic"], "paid_route": "7b", "paid_cache": True, "model_profile": "flash-next"}]
(B / "plan.json").write_text(json.dumps(PLAN))
os.environ["BENCH2_PLAN"] = "plan.json"
os.environ.pop("LDR_MODEL_PROFILE", None)
shutil.copy(Path("/home/USER/ai/deep-research/staging/item7/tools/paid-route.json"), WS_T / "tools" / "paid-route.json")
rf.RUN_DIR, rf.PROFILES_DIR = WS_T / "run", prof


def load(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(m)
    m.WS, m.B, m.NIGHT_OK = WS_T, B, TMP / "night-ok-yes"
    return m


(TMP / "night-ok-yes").touch()
b_new = load(ST / "tools" / "bench2.py", "bench2_new")
b_old = load(ST / "tools" / "bench2.py.orig", "bench2_old")
check("bench2 (staged) uses the staged helper", Path(b_new.runfiles().__file__).parent == ST / "tools")


def out_of(fn, a) -> tuple[str, str | None]:
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            fn(a)
        return buf.getvalue().strip(), None
    except SystemExit as e:
        return buf.getvalue().strip(), str(e)


o_old, _ = out_of(b_old.cmd_next, types.SimpleNamespace())
o_new, _ = out_of(b_new.cmd_next, types.SimpleNamespace(wide=False))
check("next: the old 7 columns, unchanged", o_old == o_new == "screen deep s02 medium p4 xhigh setup,critic", (o_old, o_new))
o_wide, _ = out_of(b_new.cmd_next, types.SimpleNamespace(wide=True))
check("next --wide: + route cache model profile ('-' for none)", o_wide == o_old + " - - -", o_wide)
for q in ("s01", "s02"):
    (B / "runs" / "screen-deep-p4" / q).mkdir(parents=True, exist_ok=True)
    (B / "runs" / "screen-deep-p4" / q / "bench.json").write_text("{}")
o_wide, _ = out_of(b_new.cmd_next, types.SimpleNamespace(wide=True))
check("next --wide on an item 7 step", o_wide == "screen deep s02 medium p7b xhigh setup,critic 7b on flash-next", o_wide)
(B / "plan.json").write_text(json.dumps([{**PLAN[1], "model_profile": "two words"}]))
o_wide, err = out_of(b_new.cmd_next, types.SimpleNamespace(wide=True))
check("next --wide refuses a value with spaces (it would shift the queue's columns)", err and "spaces" in err, (o_wide, err))
(B / "plan.json").write_text(json.dumps(PLAN))

CLIENT = []


def fake_run(cmd, **kw):
    out = Path(cmd[cmd.index("--capture-dir") + 1]).parent
    CLIENT.append(rf.paid_run_live(WS_T / "run"))
    if CLIENT_BOOM[0]:
        raise KeyboardInterrupt("client stopped")
    (out / "summary.json").write_text("{}")
    return types.SimpleNamespace(returncode=0)


CLIENT_BOOM = [False]
for m in (b_new, b_old):
    m.subprocess = types.SimpleNamespace(run=fake_run, STDOUT=subprocess.STDOUT)


def stamps(**kw) -> None:
    base = {"profile": "deep", "efforts": "report=medium verify=xhigh", "items": "setup critic", "fallback": "off",
            "s2": "off", "quicklimits": "off", "modelprofile": None}
    base.update(kw)
    for k, v in base.items():
        p = WS_T / "run" / f"ldr.{k}"
        p.unlink(missing_ok=True) if v is None else p.write_text(v + "\n")


def run_args(**kw):
    a = dict(set="screen", profile="deep", ids="s01", checkable_min=30, open_min=120, effort_agent=None,
             effort_extract=None, effort_all="medium", effort_verify="xhigh", label="t", items="setup,critic",
             model_profile=None, paid_route=None, paid_cache=None)
    a.update(kw)
    return types.SimpleNamespace(**a)


def bench_run(m, **kw):
    shutil.rmtree(B / "runs" / f"screen-deep-{kw.get('label', 't')}", ignore_errors=True)
    CLIENT.clear()
    _, err = out_of(m.cmd_run, run_args(**kw))
    return err


for label, st, kw, refuse in [
        ("ordinary run, LDR fits, no model-profile stamp", {}, {}, None),
        ("ordinary run, matching stamp", {"modelprofile": MP_OK}, {}, None),
        ("fallback on, no item 7", {"fallback": "on"}, {}, "fallback on"),
        ("efforts differ", {"efforts": "report=default verify=default"}, {}, "LDR started with"),
        ("items differ", {"items": "off"}, {}, "phase 4 items")]:
    stamps(**st)
    e_old = bench_run(b_old, **{k: v for k, v in kw.items() if k not in ("model_profile", "paid_route", "paid_cache")})
    n_old = len(CLIENT)
    e_new = bench_run(b_new, **kw)
    check(f"bench2 run: {label}: as before", (e_old is None) == (e_new is None) and n_old == len(CLIENT)
          and (refuse is None or (refuse in (e_new or "") and refuse in (e_old or ""))), (e_old, e_new))
stamps(modelprofile=MP_OTHER)
check("bench2 run: LDR on another model profile -> refused", "model profile" in (bench_run(b_new) or ""))
check("bench2 run: --model-profile other on 'other' -> runs", bench_run(b_new, model_profile="other") is None and len(CLIENT) == 1)
stamps(modelprofile=MP_OK)
check("bench2 run: --paid-cache without a route -> refused", "--paid-cache needs --paid-route" in (bench_run(b_new, paid_cache="on") or ""))
check("bench2 run: item 7 on an LDR without the fallback -> refused",
      "LDR_SEARCH_FALLBACK=1" in (bench_run(b_new, paid_route="7b") or ""))
stamps(modelprofile=MP_OK, fallback="on")
check("bench2 run: unknown route -> refused", "not a profile" in (bench_run(b_new, paid_route="7z") or ""))
(WS_T / "tools" / "paid-route.json").rename(WS_T / "tools" / "paid-route.off")
check("bench2 run: item 7 tools not installed -> refused", "not installed" in (bench_run(b_new, paid_route="7b") or ""))
(WS_T / "tools" / "paid-route.off").rename(WS_T / "tools" / "paid-route.json")

err = bench_run(b_new, paid_route="7b", paid_cache="on", label="p7b", ids="s01,s02")
seen = list(CLIENT)
check("item 7 run: both questions ran", err is None and len(seen) == 2, (err, seen))
check("item 7 run: the run file during each question = test, <runs folder>/<qid>, route, cache, bench2's pid",
      [(s or {}).get("run") for s in seen] == ["screen-deep-p7b/s02", "screen-deep-p7b/s01"]
      and all(s and s["kind"] == "test" and s["route"] == "7b" and s["cache"] is True and s["writer"] == "bench2"
              and s["pid"] == os.getpid() for s in seen), seen)
check("item 7 run: removed after the run", not (WS_T / "run" / "paid-run.json").exists())
bj = json.loads((B / "runs" / "screen-deep-p7b" / "s01" / "bench.json").read_text())
check("item 7 run: bench.json records the paid run",
      bj.get("paid_run") == {"kind": "test", "run": "screen-deep-p7b/s01", "route": "7b", "cache": True}, bj.get("paid_run"))
stamps(modelprofile=MP_OK)
bench_run(b_new)
bj = json.loads((B / "runs" / "screen-deep-t" / "s01" / "bench.json").read_text())
check("ordinary run: no paid_run in bench.json, no run file", "paid_run" not in bj and CLIENT == [None])
stamps(modelprofile=MP_OK, fallback="on")
CLIENT_BOOM[0] = True
try:
    bench_run(b_new, paid_route="7c", label="p7c")
    check("client call interrupted: the error goes on", False, "no error")
except KeyboardInterrupt:
    check("client call interrupted: the error goes on", True)
CLIENT_BOOM[0] = False
check("... the run file was live during the call and is removed (finally)",
      CLIENT and CLIENT[0]["route"] == "7c" and not (WS_T / "run" / "paid-run.json").exists())

# ---- nothing live touched -----------------------------------------------------------------------------------------------
for f in ("paid-run.json", "paid-run.lock", "ldr.modelprofile"):
    check(f"live run/{f} not created", not (WS_LIVE / "run" / f).exists())
shutil.rmtree(TMP)
print(f"\n{N[0] - len(FAILS)} / {N[0]} pass" + ("" if not FAILS else "\nFAILED:\n  " + "\n  ".join(FAILS)))
sys.exit(1 if FAILS else 0)
