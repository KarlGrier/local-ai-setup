#!/bin/bash
# gap-mock-test.sh - runs gap-switch0213.sh --mock against stubs under work/r23/switch-gap/scratch/mock, and the starter
# switch-start.sh against a stub driver, and checks their outputs (gap-afetch's gap-mock-test.sh form). Every tool the
# driver calls is a stub there (with_server.sh, exact7.sh, kcheck.sh, guard.py, srv.sh, stopmon.sh, port_gap4.sh,
# abarm.sh, ctest, node, nvidia-smi, the server suite, basalt_fix_rules.py's br, port0211_rules.py's envcheck, sq.py's
# GPU-side subcommands, sq_client.py, the three clients); the driver's mock mode skips the real preflight, never kills a
# real process, never queries the GPU and writes no NOTES.md / alert / ntfy. switch_rules.py runs for real (its arms on
# the real configs, its ctestlist on a copy of build-switch's CTestTestfile.cmake, its armenv on the stubs' fake
# /proc readings, its decide on the stubs' synthetic outputs); sq.py derive / rule run for real into the mock's folder;
# afetch_rules.py priority runs for real on a mock state file. Nothing outside scratch/mock is written (the stored
# port-0211 screen, the configs, the spec and the trees are only read); nothing real runs. Exit 0 = every check passed.
#   scenarios: U a bad argument; A a full run (the real trees' paid path within a mock budget: C4 runs bounded, SWITCH
#   CHECKS PASS); A2 the same with a SearXNG-only tree; D C2 DIFFERS + C3 PASS (PASS); D2 C2 DIFFERS + C3 FAIL (FAIL C3); NR
#   B never reproducible (DIFFERS, flagged); E a GPU parity program fails (FAIL C1, the gap goes on); F / F2 / F3 the
#   server suite / node --check / a CPU test failing before the gap (C1 FAIL named, the gap still opens); PB / PD the
#   paid budget too low before the gap / drained before C4 (C4 NOT RUN); PS / PS2 the paid calls (the hard caps B 5 / P
#   10 in the servers emulated, the soft stop 5 per arm: judged on 2 / fewer than 2 per arm; the total never above 10);
#   PE the hard cap missing from P's server environment (C4 NOT RUN (env)); PF / PF2 a fatal line on P's / B's C4 start
#   (FAIL / NOT DECIDED); NJ build-switch stale (ninja -n: a hard refusal); KC a kernel error during the CPU tests (a
#   hard refusal); G the read-back mismatch (FAIL C1);
#   R the read-back not decided once (retried, PASS); H / H2 the priority hold before / during the gap; O the dated
#   override; I a second instance; J another gap; K the build unit active; HF another's hold; L the lost-answer line on
#   the screen (C5 1, named, recommended); M a short deadline (C3 skipped: INCOMPLETE); N engines left (exit 5); X2 8080's
#   stopping engine left (named, never killed); KE / KP a kernel error during a server run / during the parity programs
#   (stopped at once); KE2 + port_gap4.sh end failing; K2 port_gap4.sh end failing; V a test server left behind (void:
#   C2 NOT DECIDED); EV a start whose server lacks STRATA_DEBUG (armenv FAIL: C3 NOT DECIDED); FS a foreign GPU user
#   during X; T / T2 a signal during a server run / during port_gap4.sh end; W the watchdog;
#   the starter: S1 no .ready, S1b one sha missing, S2 waiting for the build unit then busy once then done, S3 the hold
#   is final, S4 busy past 6 h, S5 no result line, S6 an edited driver, S7 engines left, S8 another instance, S9 a
#   snapshot that is not the reviewed file.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; SG=$WS/work/r23/switch-gap; M=$SG/scratch/mock
P=$WS/.venv/bin/python; PY="$P -I -B"
REALBT=$WS/strata-r23p0213/build-switch
rm -rf $M; mkdir -p $M/bin $M/lib $M/kr $M/fr $M/ru $M/sq $M/clients $M/logs $M/slogs $M/prof $M/starter $M/tree/build-switch $M/webtree/serve
# ---------------------------------------------------------------- the stubs
cat > $M/bin/mockeng.py <<'EOF'
# mockeng.py (gap-mock-test.sh only): the stub server's records and log lines
import json, os, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
SRC = Path("/home/USER/ai-speed-testing/strata-compare/results/r23/port-0211/gap/speed")
def append(p, text):
    if p:
        with open(p, "a") as f:
            f.write(text)
def done_lines(n):
    return "".join(f"[strata] done: 512 tokens in 4 s (128.0 tok/s) (length, cancel=False)\n" for _ in range(n))
def eng_lines(n, fe=True):
    out = ""
    for _ in range(n):
        out += ("strata serve: prompt 38 tokens = 0 reused + 38 read in 120 ms (316.7 tok/s), 512 generated in 4000 ms "
                "(128.0 tok/s), drafts accepted 300 of 550, 0 checkpoints, 200 windows, 2.75 drafts per window\n")
        if fe:
            out += "strata serve: fetch: 250 admissions in 200 windows (1.25 per window)\n"
    return out
def prio_find():
    (M / "state.json").write_text(json.dumps({"repos": {"unsloth/Qwen4-Flash-GGUF": {"kind": "Flash", "access": {"private": False,
                                  "gated": False}, "weights": {"Qwen4-Flash-Q4_K_M.gguf": 1}, "first_seen": "mock"}}, "polls": 9,
                                  "last_poll": "mock"}))
cmd, a = sys.argv[1], sys.argv[2:]
slog, elog = os.environ.get("SLOG"), os.environ.get("ELOG")
if cmd == "prio":
    prio_find()
elif cmd == "screen":                   # screen R N: the stored port-0211 screen pass as N's
    r, n = Path(a[0]), a[1]
    k = n[-1]
    f = float(os.environ.get(f"MOCK_DEC_{n[:-1]}", "1.0"))
    total = 0
    for s in "nar":
        (r / f"{n}{s}.englog").write_text((SRC / f"B{k}{s}.englog").read_text())
        recs = [json.loads(x) for x in (SRC / f"B{k}{s}.jsonl").read_text().splitlines() if x.strip()]
        for x in recs:
            x["decode_tps"] = round(x["decode_tps"] * f, 2)
        (r / f"{n}{s}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs))
        total += len(recs)
    (r / f"{n}.startlog").write_text("mock\n")
    (r / f"{n}.wu.jsonl").write_text(json.dumps({"id": "warmup"}) + "\n")
    append(slog, done_lines(total + 1))
    append(elog, eng_lines(total + 1))
    if os.environ.get("MOCK_LOST_AT") and os.environ.get("MOCK_LOST_AT") in os.environ.get("MOCK_LABEL", ""):
        append(slog, "[strata] a request ended without an answer and without a finish reason; it is answered as an error\n")
elif cmd == "sqclient":                 # sqclient OUTDIR: the sampled arm's records and its start's logs
    out = Path(a[0]); arm = os.environ["SQ_ARM"]; out.mkdir(parents=True, exist_ok=True)
    n = {"R1": 32, "X": 32, "R2": 16, "VF": 8}[arm]
    append(elog, eng_lines(n))
    append(slog, done_lines(n))
    (out / "sampled.jsonl").write_text("".join(json.dumps({"name": f"{arm}-{i}", "finish": "length"}) + "\n" for i in range(n)))
    eb = int(os.environ.get("SQ_ELOG_BASE") or 0)
    with open(elog, "rb") as fi:
        fi.seek(eb)
        (out / "engine.out").write_bytes(fi.read())
    (out / "server.out").write_text(Path(slog).read_text() if slog else "mock\n")
    print(f"sampled {arm}: {n} of {n} requests answered")
elif cmd == "c2":                       # c2 OUTDIR PLAN: the served-output records (ids from the seed; MOCK_C2_* steer)
    out, plan = Path(a[0]), json.loads(Path(a[1]).read_text()); out.mkdir(parents=True, exist_ok=True)
    arm = out.name
    with open(out / "c2.jsonl", "w") as f:
        for i, r in enumerate(plan["requests"]):
            ids = [r["seed"] % 1000, i, 7, 8]
            if os.environ.get("MOCK_C2_DIFF") == "1" and arm == "P" and i == 0:
                ids = ids[:2] + [99]
            if os.environ.get("MOCK_C2_NOREP") == "1" and arm == "B2":
                ids = ids + [5]
            f.write(json.dumps({"name": r["name"], "prompt": r["prompt"], "seed": r["seed"], "prompt_tokens": 38, "ids": ids,
                                "completion_tokens": len(ids), "finish": "length", "continuation": r["thinking"]}) + "\n")
    append(slog, done_lines(len(plan["requests"])))
    append(elog, eng_lines(len(plan["requests"])))
    if os.environ.get("MOCK_PRIO_AT") == f"c2{arm}":
        prio_find()
    if os.environ.get("MOCK_PAID_DRAIN_AT") == f"c2{arm}":   # Jan chat spends meanwhile: Exa down to $2 left
        u = json.loads((M / "paidtools/u.json").read_text()); u["exa_usd"] = 8.0; (M / "paidtools/u.json").write_text(json.dumps(u))
    print(f"done: {len(plan['requests'])} of {len(plan['requests'])} requests (mock)")
elif cmd == "web":                      # web OUTDIR PLAN
    out, plan = Path(a[0]), json.loads(Path(a[1]).read_text()); out.mkdir(parents=True, exist_ok=True)
    with open(out / "web.jsonl", "w") as f:
        for i, r in enumerate(plan["requests"]):
            ok = not (os.environ.get("MOCK_C4_FAIL") == "1" and out.name == "P" and i == 0)
            f.write(json.dumps({"name": r["name"], "completed": ok, "finish": "stop" if ok else "error", "search_calls": 1,
                                "fetch_ok": ["python.org/downloads"], "cited_fetched": ["python.org/downloads"],
                                "cited_tool": ["python.org/downloads"], "errors": [] if ok else ["error chunk: mock"]}) + "\n")
    append(slog, done_lines(2 * len(plan["requests"])))
    print("web: mock")
elif cmd == "fx":                       # fx OUT PLAN
    out, plan = Path(a[0]), json.loads(Path(a[1]).read_text())
    with open(out, "w") as f:
        for r in plan["requests"]:
            f.write(json.dumps({"name": r["name"], "prompt_tokens": r.get("expect_prompt_tokens"), "expect_prompt_tokens":
                                r.get("expect_prompt_tokens"), "completion_tokens": r["max_tokens"], "finish": "length",
                                "decode_tps": 131.0}) + "\n")
    append(slog, done_lines(len(plan["requests"])))
    print("fixtures: mock")
EOF
cat > $M/lib/with_server.sh <<'EOF'
#!/bin/bash
# mock with_server.sh LABEL CFG -- CMD: the engine's start lines into the config's log, the fake /proc env, the server log,
# then CMD with $ELOG / $SLOG
M=$(dirname $(dirname $(readlink -f $0))); P=/home/USER/ai-speed-testing/strata-compare/.venv/bin/python
L=$1 CFG=$2; shift 3
export ELOG=$($P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" $CFG)
mkdir -p $(dirname $ELOG); touch $ELOG
export SLOG=$M/slogs/server_${L}_mock.log MOCK_LABEL=$L
env | grep '^PAID_SEARCH' | sort > $M/paid-env-$L.txt   # (what the test server would inherit)
if [ -n "${MOCK_PENV_BAD_AT:-}" ] && [[ $L == *"$MOCK_PENV_BAD_AT"* ]]; then env -u PAID_SEARCH_RUN_CAP -0 > $M/server-environ-$L
else env -0 > $M/server-environ-$L; fi   # (the server's /proc/PID/environ, for c4_web.py's env gate)
echo "# mock server log $L ($CFG)" > $SLOG
echo "=== mock $L start ($CFG)"
[ -n "${MOCK_FAIL_AT:-}" ] && [[ $L == *"$MOCK_FAIL_AT"* ]] && { echo "server exited (mock)"; exit 1; }
[ -n "${MOCK_FAIL_ONCE_AT:-}" ] && [[ $L == *"$MOCK_FAIL_ONCE_AT"* ]] && [ ! -e $M/failed-once ] && { touch $M/failed-once; echo "server exited (mock, once)"; exit 1; }
fake() { $M/engines/$1/swmock-eng 600 > /dev/null 2>&1 < /dev/null & echo $! >> $M/fake.pids; echo $!; }   # a fake engine (never named strata*)
$P -I -B - "$CFG" "$L" <<'PYEOF'
import json, os, sys
from pathlib import Path
cfg_path, lab = sys.argv[1], sys.argv[2]
M = Path(os.environ["SLOG"]).parents[1]
cfg = json.loads(Path(cfg_path).read_text())
env = dict(cfg.get("env", {}))
sha = "153ce47d3ef0" if "engine-r23afetch" in cfg["exe"] else "639dfb1b7042" if "engine-r23p0213" in cfg["exe"] else "?"
penv = dict(env)
bad = os.environ.get("MOCK_ENVBAD_AT")
if bad and bad in lab:
    penv.pop("STRATA_DEBUG", None)
(M / "engine-env.json").write_text(json.dumps({"procs": [{"pid": 4242, "env": env, "sha12": sha, "parent_env": penv,
    "parent_argv": ["python", cfg["server"], "--engine", "strata", "--config", os.path.abspath(cfg_path)]}]}))
with open(cfg["log"], "a") as f:
    f.write("strata generate: memory guard: mock\nstrata mtp: EXACT speculative sampling on (STRATA_SPEC_EXACT): mock\n"
            "strata serve: STRATA_ADAPT_FETCH=2: the PCIe share takes each layer's most-routed misses and admits those routed "
            ">= 2.00 and 0.50 more than a resident one; the tier own copies are off\n")
PYEOF
echo "server ready (mock: guard pid 1, server pid 2) load_time_s 1.0"
echo "engine pid 4242 pinned/locked: mock"
[ -n "${MOCK_SLEEP_AT:-}" ] && [[ $L == *"$MOCK_SLEEP_AT"* ]] && sleep ${MOCK_SLEEP_S:-4}
if [ -n "${MOCK_FOREIGN_AT:-}" ] && [[ $L == *"$MOCK_FOREIGN_AT"* ]] && [ ! -e $M/foreign-done ]; then   # a foreign GPU user during the run (once)
  touch $M/foreign-done; sleep 30 > /dev/null 2>&1 < /dev/null & echo $! > $M/foreign.pid; touch $M/foreign-on; sleep 1.2; rm -f $M/foreign-on; kill $(cat $M/foreign.pid)
fi
if [ -n "${MOCK_KERR_AT:-}" ] && [[ $L == *"$MOCK_KERR_AT"* ]]; then   # a kernel error during the run: kwatch's marker, an engine to kill
  fake engine-r23afetch > $M/kerr-engine.pid; echo "Xid 79 (mock): GPU has fallen off the bus" > $M/kernel_error; sleep 1.5
fi
bash -c "$*"
[ -n "${MOCK_LEFTOVER_AT:-}" ] && [[ $L == *"$MOCK_LEFTOVER_AT"* ]] && touch $M/leftover   # (its server "survives" the stop)
[ -n "${MOCK_FATAL_AT:-}" ] && [[ $L == *"$MOCK_FATAL_AT"* ]] && echo "[strata] the engine had stopped (exit code 139); it starts again" >> $SLOG
[ -n "${MOCK_ENGINE_LEFT_AT:-}" ] && [[ $L == *"$MOCK_ENGINE_LEFT_AT"* ]] && fake engine-r23p0213 > $M/left-engine.pid
echo "=== mock $L done"
EOF
cat > $M/lib/exact7.sh <<'EOF'
#!/bin/bash
# mock exact7.sh LABEL CFG (PIN_CACHE, REF): MOCK_E7 of 7 identical (default 3: bit-identity is not expected), slots MATCHED
L=$1
echo "exact7 $L: ${MOCK_E7:-3}/7 identical to ${REF:-?}"
echo "exact7-slots $L: 3238+3300 slots (5080 + 4060 Ti); ${REF:-?}: 3238+3300 -> MATCHED"
exit 0
EOF
cat > $M/lib/guard.py <<'EOF'
# mock guard.py LABEL -- CMD...: runs CMD
import subprocess, sys
a = sys.argv[1:]
sys.exit(subprocess.call(a[a.index("--") + 1:]))
EOF
for x in srv.sh stopmon.sh; do printf '#!/bin/bash\necho "mock %s $*"\nexit 0\n' $x > $M/lib/$x; done
cat > $M/lib/kcheck.sh <<'EOF2'
#!/bin/bash
# mock kcheck.sh LABEL: fails once the label contains MOCK_KFAIL_AT, or (as the real one) while kwatch's marker exists
M=$(dirname $(dirname $(readlink -f $0)))
[ -e $M/kernel_error ] && { echo "mock KCHECK FAIL $1: kernel error seen"; exit 1; }
[ -n "${MOCK_KFAIL_AT:-}" ] && [[ "$1" == *"$MOCK_KFAIL_AT"* ]] && { echo "mock KCHECK FAIL $1"; exit 1; }
echo "mock kcheck ok $1"; exit 0
EOF2
printf '#!/bin/bash\nexit 0\n' > $M/lib/ntfy-note.py
cat > $M/kr/port_gap4.sh <<'EOF'
#!/bin/bash
# mock port_gap4.sh begin WHAT | end: a lock holder (sleep), the hold file, a log line per call
M=$(dirname $(dirname $(readlink -f $0)))
case $1 in
  begin) echo "begin $2" >> $M/pg4.log; echo "phase 4 gap: $2 (since mock)" > $M/hold
         if [ "${MOCK_OLD_ENGINE:-0}" = 1 ]; then   # 8080's stop left its engine running (it has B's binary)
           $M/engines/engine-r23afetch/swmock-eng 600 > /dev/null 2>&1 < /dev/null & echo $! >> $M/fake.pids; echo $! > $M/old-engine.pid
         fi
         sleep 600 > /dev/null 2>&1 < /dev/null & echo $! > $M/lockpid; echo "mock port_gap4: gap open";;
  end) echo "end" >> $M/pg4.log; [ -n "${MOCK_END_SLEEP:-}" ] && sleep $MOCK_END_SLEEP
       [ "${MOCK_END_FAIL:-0}" = 1 ] && { echo "mock port_gap4: the daily did not start"; exit 1; }
       kill $(cat $M/lockpid) 2> /dev/null; rm -f $M/lockpid $M/hold; echo "mock port_gap4: served build back";;
esac
EOF
cat > $M/kr/abarm.sh <<'EOF'
#!/bin/bash
# mock abarm.sh URL OFF0 OUTDIR NAME SPEC...: the stored port-0211 screen pass as NAME's
M=$(dirname $(dirname $(readlink -f $0)))
/home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B $M/bin/mockeng.py screen $3 $4
echo "mock abarm $4: 9 workloads"
EOF
cat > $M/fr/basalt_fix_rules.py <<'EOF'
# mock basalt_fix_rules.py br envcli | e7gate (gates in basalt_rules' form)
import os, re, sys, time
from pathlib import Path
a = sys.argv[2:]
def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d
def gate(st, det):
    if opt("--gates") and opt("--gate"):
        with open(opt("--gates"), "a") as f:
            f.write(f"{opt('--gate')} {st} {det}\n")
def alive(pid):
    try:
        os.kill(pid, 0)
        return Path(f"/proc/{pid}").exists() and "zombie" not in Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return False
if a[0] == "envcli":
    job = int(opt("--job"))
    while alive(job):
        time.sleep(0.1)
    print(f"ENV CHECK OK: 1 engine start(s) ({opt('--mode')}), mock"); gate("PASS", "mock envcli"); sys.exit(0)
if a[0] == "e7gate":
    s, lab = Path(a[1]).read_text(), a[2]
    m = re.findall(rf"^exact7 {re.escape(lab)}: (\d)/7 identical", s, re.M)
    n = int(m[-1]) if m else None
    print(f"exact7 {lab}: {n}/7, slots MATCHED -> {'PASS' if n == 7 else 'FAIL'}")
    gate("PASS" if n == 7 else ("FAIL" if n is not None else "MISSING"), f"exact7 {lab}: {n}/7, slots MATCHED"); sys.exit(0)
sys.exit(2)
EOF
cat > $M/ru/port0211_rules.py <<'EOF'
# mock port0211_rules.py envcheck EXE CFG ...: the config's env = the fake engine's (engine-env.json)
import json, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
a = sys.argv[1:]
def opt(k):
    return a[a.index(k) + 1] if k in a else None
cfg = json.loads(Path(a[2]).read_text())
env = json.loads((M / "engine-env.json").read_text())["procs"][0]["env"]
ok = env == cfg.get("env", {})
print("engine pid 4242: mock; " + ("ENV CHECK OK" if ok else "ENV CHECK FAILED"))
if opt("--gates") and opt("--gate"):
    open(opt("--gates"), "a").write(f"{opt('--gate')} {'PASS' if ok else 'FAIL'} mock envcheck\n")
sys.exit(0 if ok else 1)
EOF
cat > $M/sq/sq.py <<'EOF'
# mock sq.py: derive / rule = the real sq.py (into the mock's folder); selftests, envcheck, verify, ids, score, envwatch, decide stubbed
import json, os, subprocess, sys, time
from pathlib import Path
REAL = "/home/USER/ai-speed-testing/strata-compare/work/r23/sampled-qwen/sq.py"
a = sys.argv[1:]
cmd = a[0]
if cmd in ("derive", "rule"):
    sys.exit(subprocess.call([sys.executable, "-I", "-B", REAL] + a))
if cmd == "selftest":
    print("mock\nSELFTEST OK"); sys.exit(0)
if cmd == "selftest-real":
    print("mock\nSELFTEST-REAL OK"); sys.exit(0)
if cmd == "envcheck":
    Path(a[1], f"envcheck-{a[2]}.txt").write_text("engine pid 4242: mock\nENV CHECK OK\n"); print("ENV CHECK OK"); sys.exit(0)
if cmd == "verify":
    o, arm = Path(a[1]), a[2]
    mode = os.environ.get("MOCK_VF", "PASS")
    if mode == "ONCE" and not (o / "vf-once").exists():
        (o / "vf-once").write_text("x"); mode = "ND"
    if mode == "ND" or not (o / arm / "engine.out").exists():
        v = {"verdict": "NOT DECIDED", "why": "no read-back summary (mock)"}
        (o / f"verify-{arm}.json").write_text(json.dumps(v)); print(f"read-back {arm}: NOT DECIDED"); sys.exit(2)
    bad = mode == "FAIL"
    v = {"verdict": "FAIL" if bad else "PASS", "why": "read-back mismatch: 3 mismatch line(s)" if bad else
         "412 admitted slots read back, 0 differ, no mismatch line", "read_back": 412, "differ": 3 if bad else 0,
         "mismatch_lines": 3 if bad else 0}
    (o / f"verify-{arm}.json").write_text(json.dumps(v)); print(f"read-back {arm}: {v['verdict']} - {v['why']}")
    sys.exit(1 if bad else 0)
if cmd == "ids":
    for arm in a[2:]:
        print(f"ids {arm}: 32 of 32 samples valid (mock)")
    sys.exit(0)
if cmd == "score":
    print("scorer engine: mock\nscored 80 of 80 samples (46720 positions) in 1 s"); sys.exit(0)
if cmd == "envwatch":
    job = int(a[1])
    while Path(f"/proc/{job}").exists() and "zombie" not in Path(f"/proc/{job}/status").read_text():
        time.sleep(0.1)
    print("engine pid 4243 -> ENV OK\nENV CHECK OK: 1 scorer engine start(s)"); sys.exit(0)
if cmd == "decide":
    o = Path(a[1])
    have = all((o / x / "sampled.jsonl").exists() for x in ("R1", "X", "R2"))
    v = os.environ.get("MOCK_SQ_X", "PASS") if have else "NOT DECIDED"
    res = {"spec": "mock", "verdict": v, "candidates": {"X": {"verdict": v, "why": "D2 3.1 <= band 11.345 (mock)" if v == "PASS" else "D2 40.2 > band 11.345 (mock)" if v == "FAIL" else "R1 missing", "d2_x_ref": 3.1, "band": 11.345}},
           "overall": {"X": {"verdict": v}}, "flags": []}
    (o / "decision.json").write_text(json.dumps(res)); (o / "decision.txt").write_text(json.dumps(res) + "\n")
    print(f"decision {v}: X {v}"); sys.exit({"PASS": 0, "FAIL": 1}.get(v, 2))
sys.exit(2)
EOF
cat > $M/sq/sq_client.py <<'EOF'
# mock sq_client.py URL OUTDIR (SQ_SPEC SQ_ARM SQ_LABEL SQ_ELOG_BASE SQ_BUDGET_S, ELOG)
import subprocess, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
if sys.argv[1] == "selftest":
    print("mock\nCLIENT SELFTEST OK"); sys.exit(0)
sys.exit(subprocess.call([sys.executable, "-I", "-B", str(M / "bin/mockeng.py"), "sqclient", sys.argv[2]]))
EOF
cat > $M/clients/c4_web.py <<'EOF'
# mock c4_web.py URL OUT --plan PLAN [--paid-base F --paid-tools D --paid-stop N]: the REAL client's run() (its paid-call
# stop) against c4_web.py's own fake strata_web stream; MOCK_PAID_PER_REQ paid calls per request move the fake counters
import json, os, sys, urllib.request
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r23/switch-gap")
import c4_web
if sys.argv[1] == "selftest":
    print("mock\nC4 WEB SELFTEST OK"); sys.exit(0)
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
plan = json.load(open(opt("--plan")))
c4_web.SETTLE_S = 0
tools = opt("--paid-tools")
M = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
environ = f"{M}/server-environ-{os.environ['MOCK_LABEL']}"
cap = c4_web.read_environ(environ).get("PAID_SEARCH_RUN_CAP")   # (the server's paid_budget.py run cap: the hard limit, emulated)
fake = c4_web.Fake(os.environ["SLOG"], ["good"] * len(plan["requests"]), counter=f"{tools}/u.json" if tools else None,
                   paid_per=int(os.environ.get("MOCK_PAID_PER_REQ", "0")), run_cap=cap)
urllib.request.urlopen = fake
penv = ({"run": opt("--paid-env-run"), "cap": opt("--paid-env-cap"), "environ": environ, "gate": opt("--paid-env-gate"),
         "gates": opt("--paid-env-gates")} if opt("--paid-env-run") else None)
sys.exit(c4_web.run(a[0], a[1], plan, os.environ["SLOG"], os.environ.get("ELOG"), int(opt("--elog-base", "0")),
                    opt("--paid-base"), tools or c4_web.PAID_TOOLS, int(opt("--paid-stop", "10")), int(opt("--paid-arm-stop", "5")),
                    penv))
EOF
mkdir -p $M/paidtools
cat > $M/paidtools/exa_fallback.py <<'EOF'
# mock exa_fallback.py: the counter code's shape (usage(), available(); no key file)
import json, os
U = os.path.join(os.path.dirname(os.path.abspath(__file__)), "u.json")
MONTH_CREDIT_USD = 10.0; PRICE_USD = {"lite": 0.004}; SEARCH_TYPE = "lite"; CAP_USD = 9.0
def available():
    return json.load(open(U))["exa_av"]
def usage():
    u = json.load(open(U))
    return {"month": "2026-11", "usd": u["exa_usd"] if u.get("exa_usd") is not None else 0.004 * u["exa"], "searches": u["exa"],
            "closed": False, "cap_usd": CAP_USD}
EOF
cat > $M/paidtools/tavily_fallback.py <<'EOF'
# mock tavily_fallback.py
import json, os
U = os.path.join(os.path.dirname(os.path.abspath(__file__)), "u.json")
MONTH_CREDITS = 1000; CAP = 900
def available():
    return json.load(open(U))["tav_av"]
def usage():
    return {"month": "2026-11", "count": json.load(open(U))["tav"], "cap": CAP}
EOF
for c in c2_client.py:C2_CLIENT_SELFTEST_OK:c2 fixtures_client.py:FIXTURES_CLIENT_SELFTEST_OK:fx; do
  IFS=: read -r f ok sub <<< "$c"
  cat > $M/clients/$f <<EOF
# mock $f URL OUT --plan PLAN ...: records in the real client's format (mockeng.py $sub)
import subprocess, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
if sys.argv[1] == "selftest":
    print("mock\n${ok//_/ }"); sys.exit(0)
a = sys.argv[1:]
sys.exit(subprocess.call([sys.executable, "-I", "-B", str(M / "bin/mockeng.py"), "$sub", a[1], a[a.index("--plan") + 1]]))
EOF
done
cat > $M/bin/nvidia-smi <<'EOF'
#!/bin/bash
# mock nvidia-smi: no compute process; a foreign one while foreign-on exists
M=$(dirname $(dirname $(readlink -f $0))); n=$(( $(cat $M/nvsmi.count 2> /dev/null || echo 0) + 1 )); echo $n > $M/nvsmi.count
[ -e $M/foreign-on ] && echo "$(cat $M/foreign.pid), 1000"
exit 0
EOF
cat > $M/bin/ctest <<'EOF'
#!/bin/bash
# mock ctest --test-dir B -R '^(a|b)$' ... --output-junit J: every named entry passes (MOCK_PAR_FAIL: that one fails;
# MOCK_KERR_PAR=1: a kernel error while a parity program of the build runs - the driver must kill it)
M=$(dirname $(dirname $(readlink -f $0)))
re=""; junit=""
while [ $# -gt 0 ]; do case $1 in -R) re=$2; shift;; --output-junit) junit=$2; shift;; esac; shift; done
names=$(echo "$re" | sed -E 's/^\^\(//; s/\)\$$//' | tr '|' ' ')
if [ "${MOCK_KERR_PAR:-0}" = 1 ] && [ -n "${CUDA_VISIBLE_DEVICES:-}" ]; then   # (the GPU run only)
  $M/tree/build-switch/swmock-par 600 > /dev/null 2>&1 < /dev/null & echo $! > $M/par-prog.pid
  echo "Xid 79 (mock): during the parity run" > $M/kernel_error; sleep 2
fi
if [ "${MOCK_KERR_CPU:-0}" = 1 ] && [ -z "${CUDA_VISIBLE_DEVICES:-}" ]; then echo "Xid 13 (mock): during the CPU tests" > $M/kernel_error; fi
i=0; n=$(echo $names | wc -w); x='<testsuite>'
for t in $names; do
  i=$((i + 1))
  if [ "$t" = "${MOCK_PAR_FAIL:-}" ]; then echo "$i/$n Test #$i: $t ...***Failed    0.10 sec"; x="$x<testcase name=\"$t\" status=\"fail\" time=\"0.1\"><failure message=\"Failed\"/></testcase>"
  else echo "$i/$n Test #$i: $t .........   Passed    0.10 sec"; x="$x<testcase name=\"$t\" status=\"run\" time=\"0.1\"/>"; fi
done
echo "$x</testsuite>" > $junit
echo "100% tests passed, 0 tests failed out of $n"
EOF
cat > $M/bin/ninja <<'EOF'
#!/bin/bash
# mock ninja -C B -n TARGETS: nothing to do (MOCK_NINJA_STALE=1: a step left)
[ "${MOCK_NINJA_STALE:-0}" = 1 ] && { echo "[1/1] Building CXX object CMakeFiles/gr_parity.dir/x.cpp.o"; exit 0; }
echo "ninja: no work to do."
EOF
cat > $M/bin/node <<'EOF'
#!/bin/bash
# mock node --check FILE
[ "${MOCK_NODE_RC:-0}" = 0 ] || echo "SyntaxError (mock)"
exit ${MOCK_NODE_RC:-0}
EOF
cat > $M/bin/servetests <<'EOF'
#!/bin/bash
# mock server suite (unittest -v form): a node test ran; MOCK_SERVE_FAIL=1 -> a new failure
echo "test_history (serve.test_web_history.WebHistoryTests.test_history) ... ok"
echo "test_math (serve.test_web_math.MathTests.test_math) ... ok"
echo "test_hip_ordinal (serve.test_gpu_roles_server.T.test_hip_ordinal) ... FAIL"
[ "${MOCK_SERVE_FAIL:-0}" = 1 ] && echo "ERROR: test_new_thing (serve.test_server.T.test_new_thing)"
echo "FAIL: test_hip_ordinal (serve.test_gpu_roles_server.T.test_hip_ordinal)"
echo "----------------------------------------------------------------------"
echo "Ran 3 tests in 1.0s"; echo; echo "FAILED (failures=1)"
EOF
chmod +x $M/lib/* $M/kr/*.sh $M/bin/nvidia-smi $M/bin/ctest $M/bin/node $M/bin/servetests $M/bin/ninja
mkdir -p $M/engines/engine-r23afetch $M/engines/engine-r23p0213 $M/engines/engine-r22p028x   # the fake engines: copies of sleep
for d in engine-r23afetch engine-r23p0213 engine-r22p028x; do cp /bin/sleep $M/engines/$d/swmock-eng; done
cp /bin/sleep $M/tree/build-switch/swmock-par
for t in $($PY $SG/switch_rules.py targets); do   # the fake parity programs (MOCK_DIRECT_FAIL: that one fails)
  printf '#!/bin/bash\n[ "${MOCK_DIRECT_FAIL:-}" = "%s" ] && exit 1\nexit 0\n' $t > $M/tree/build-switch/$t; chmod +x $M/tree/build-switch/$t
done
sed "s|$REALBT|$M/tree/build-switch|g" $REALBT/CTestTestfile.cmake > $M/tree/build-switch/CTestTestfile.cmake
printf 'def search(q):\n    return get("http://127.0.0.1:8888/search?q=" + q)\n' > $M/webtree/serve/websearch.py
echo "switchtests: build rc 0 in $M/tree/build-switch at 6dd81ecd194864d443d9568c17300fc4d4f98b9c; nvcc: mock" > $M/build-switch.log
$PY $SG/switch_rules.py fixtures $M/fixtures-plan.json > /dev/null   # (CPU, read only: P's tree + the GGUF's vocabulary)
CLEAR='{"repos": {"Qwen/Qwen4-Flash": {"kind": "Flash", "access": {"private": false, "gated": "manual"}, "weights": {"model-00001.safetensors": 1}}}, "polls": 3, "last_poll": "mock"}'

# ---------------------------------------------------------------- the driver scenarios
F=0; NCHK=0
chk() { NCHK=$((NCHK + 1)); if eval "$2"; then echo "  ok   $1"; else echo "  FAIL $1"; F=1; fi; }
O=$M/out
setup() {   # a clean mock state (the watch state CLEAR, no gap open, no hold, no hooks left)
  [ -s $M/lockpid ] && kill $(cat $M/lockpid) 2> /dev/null
  for fp in $(cat $M/fake.pids 2> /dev/null); do kill $fp 2> /dev/null; done
  [ -s $M/par-prog.pid ] && kill $(cat $M/par-prog.pid) 2> /dev/null
  rm -f $M/pg4.log $M/lockpid $M/hold $M/engine-env.json $M/leftover $M/nvsmi.count $M/wdg.log $M/switch0213-priority-done $M/driver.pid
  rm -f $M/fake.pids $M/*-engine.pid $M/par-prog.pid $M/kernel_error $M/failed-once $M/foreign-on $M/foreign.pid $M/foreign-done
  rm -rf $M/logs $M/slogs $M/rb-cache $O; mkdir -p $M/logs $M/slogs
  echo "$CLEAR" > $M/state.json
  echo '{"exa": 292, "tav": 365, "run": 0, "exa_usd": null, "exa_av": true, "tav_av": true}' > $M/paidtools/u.json; rm -f $M/paid-env-*.txt $M/server-environ-*
}
run() {   # run NAME [VAR=VALUE ...]: the driver in mock mode -> $M/NAME.out, rc in RC
  local n=$1; shift
  env "$@" timeout 900 bash $SG/gap-switch0213.sh --mock > $M/$n.out 2>&1; RC=$?
  rm -rf $M/out-$n; cp -r $O $M/out-$n 2> /dev/null
  echo "--- scenario $n: driver rc $RC"
}
bgrun() {   # bgrun NAME WAITFILE PATTERN [VAR=VALUE ...]: the driver in the background; TERM once PATTERN shows in WAITFILE
  local n=$1 wf=$2 pat=$3 i; shift 3
  env "$@" bash $SG/gap-switch0213.sh --mock > $M/$n.out 2>&1 & local dp=$!
  for i in $(seq 900); do grep -qE "$pat" $wf 2> /dev/null && break; sleep 0.1; done
  grep -qE "$pat" $wf 2> /dev/null || { echo "  FAIL $n: /$pat/ never showed in 90 s (the TERM is sent anyway)"; F=1; }
  kill -TERM $dp; wait $dp; RC=$?
  rm -rf $M/out-$n; cp -r $O $M/out-$n 2> /dev/null
  echo "--- scenario $n: driver rc $RC (TERM sent once /$pat/ was in $(basename $wf))"
}
alive() { [ -s "$1" ] && kill -0 "$(cat $1)" 2> /dev/null; }
nbeg() { local n; n=$(grep -c '^begin' $M/pg4.log 2> /dev/null); echo ${n:-0}; }
nend() { local n; n=$(grep -c '^end' $M/pg4.log 2> /dev/null); echo ${n:-0}; }
line_of() { grep -n -- "$2" $1 | head -1 | cut -d: -f1; }
V() { cat $O/verdict.txt 2> /dev/null; }

# U: an unknown argument runs nothing - the check itself and its place (the first command)
sed -n '1,/^case \${1:-} in/p' $SG/gap-switch0213.sh > $M/argcheck.sh; echo 'echo PAST-THE-CHECK' >> $M/argcheck.sh
chk "U --bogus: exit 2, nothing after the check" "bash $M/argcheck.sh --bogus > $M/U.out 2>&1; [ \$? = 2 ] && ! grep -q PAST $M/U.out && grep -q 'nothing run' $M/U.out"
chk "U --mock / --dry-run / no argument pass the check" "bash $M/argcheck.sh --mock | grep -q PAST && bash $M/argcheck.sh --dry-run | grep -q PAST && bash $M/argcheck.sh | grep -q PAST"
chk "U the check is the driver's first command (only set / exec / WS= before it)" "[ -z \"\$(sed -n '1,/^case \${1:-} in/p' $SG/gap-switch0213.sh | grep -vE '^#|^\$|^set -u -o pipefail\$|^exec 8>&- 9>&-|^WS=|^case ')\" ]"

setup; sleep 0 & wait $!; echo $! > $M/driver.pid   # (a stale pid file: a dead pid)
run A MOCK_SELFTEST=1
chk "A exit 0, result DONE, a stale pid file taken over and gone at the exit" "[ $RC = 0 ] && grep -q '^DONE (measurements only, nothing switched' $O/result.txt && [ ! -e $M/driver.pid ]"
chk "A the verdict: SWITCH CHECKS PASS - the real trees' paid path within the (mock) budget: C4 ran bounded" "[ \"\$(V)\" = 'SWITCH CHECKS PASS' ] && grep -q '^webpath PAID WEB PATH CAN REACH A PAID API, WITHIN THE BUDGET' $O/gates.txt && grep -q '^c4budget PASS PAID BUDGET OK' $O/gates.txt && grep -q '^C4 web search end to end: PASS' $O/decision.txt"
chk "A C4's test servers got PAID_SEARCH_KIND=test, the gap's run id and the hard caps (B 5, P 10), checked in their environment (penv gates); every other start KIND=test with no run id (0 paid)" "grep -qx 'PAID_SEARCH_KIND=test' \$(ls $M/paid-env-r23sw*-webP.txt) && grep -qx 'PAID_SEARCH_RUN_CAP=10' \$(ls $M/paid-env-r23sw*-webP.txt) && grep -q 'PAID_SEARCH_RUN=switch0213/r23sw' \$(ls $M/paid-env-r23sw*-webB.txt) && grep -qx 'PAID_SEARCH_KIND=test' \$(ls $M/paid-env-r23sw*-c2P.txt) && ! grep -q 'PAID_SEARCH_RUN' \$(ls $M/paid-env-r23sw*-c2P.txt) && grep -qx 'PAID_SEARCH_RUN_CAP=5' \$(ls $M/paid-env-r23sw*-webB.txt) && grep -q '^penv_webB PASS PAID ENV OK' $O/gates.txt && grep -q '^penv_webP PASS PAID ENV OK' $O/gates.txt"
chk "A the paid count in the decision (0), the counters before / after C4 recorded" "grep -q 'paid searches during C4: 0 (B 0, P 0; the stop at 10); the counters moved exa +0, tavily +0' $O/decision.txt && [ -s $O/c4/paid-start.json ] && [ -s $O/c4/paid-end.json ]"
chk "A C1 PASS (cpu, servetests with the known failure, node, gpu, read-back), C2 EXACT, C3 PASS" "grep -q '^C1 parity / unit tests + the read-back: PASS' $O/decision.txt && grep -q '^C2 served outputs against the daily: EXACT' $O/decision.txt && grep -q '^C3 the sampled test .*: PASS' $O/decision.txt && grep -q '  servetests: PASS - 3 tests, 1 failed or erred (known: test_hip_ordinal)' $O/decision.txt"
chk "A port_gap4 begin once, end once; the gap closed" "[ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && [ ! -e $M/lockpid ] && [ ! -e $M/hold ]"
chk "A the rules' selftest ran; the switches frozen; rules.txt has the files' shas" "grep -q 'switch_rules selftest: 0 failure(s)' $O/summary.txt && grep -q 'CITE_FORM = tool-url' $O/rules.txt && grep -q 'work/r23/switch-gap/gap-switch0213.sh ' $O/rules.txt && grep -q 'work/r23/sampled-qwen/sq.py ' $O/rules.txt"
chk "A sampled rule.txt and rules.txt written, and C1's CPU parts run, before the gap opened" "[ -s $O/sampled/rule.txt ] && [ \$(line_of $O/summary.txt 'the sampled rule frozen') -lt \$(line_of $O/summary.txt 'mock port_gap4: gap open') ] && [ \$(line_of $O/summary.txt 'ctest cpu rc') -lt \$(line_of $O/summary.txt 'mock port_gap4: gap open') ] && [ \$(line_of $O/summary.txt 'rules frozen') -lt \$(line_of $O/summary.txt 'mock port_gap4: gap open') ]"
chk "A the real sq.py derive wrote R1 / X / R2 / VF configs = the gap's debug arms (cfg_sampled PASS)" "[ -s $O/sampled/cfg/X.json ] && grep -q '^cfg_sampled PASS' $O/gates.txt && grep -q 'engine-r23p0213' $O/sampled/cfg/X.json"
chk "A the order: the GPU parity before any server; VF; C2 B1 B2 P; C3 R1 X R2; screen P, fixtures, screen B; exact7" "grep -oE 'C1 the GPU parity programs|server r23sw[0-9]+-(sqVF|c2B1|c2B2|c2P|sqR1|sqX|sqR2|scrP1|bpP|scrB1) |INFO exact7 r23sw' $O/summary.txt | sed -E 's/server r23sw[0-9]+-//; s/ \$//' | tr '\n' ',' | grep -qx 'C1 the GPU parity programs,sqVF,c2B1,c2B2,c2P,sqR1,sqX,sqR2,scrP1,bpP,scrB1,INFO exact7 r23sw,'"
chk "A every start's env (the engine + its server.py), armenv, start-line gates PASS (10 starts), no void, no foreign" "[ \$(grep -cE '^(env|fenv|line)_(sqVF|c2B1|c2B2|c2P|sqR1|sqX|sqR2|scrP1|bpP|scrB1) PASS' $O/gates.txt) = 30 ] && ! grep -qE '^(void|foreign)_' $O/gates.txt"
chk "A the parity: 89 GPU entries passed + 2 direct; 7 CPU entries + patch_guard_test" "grep -q 'gpu: 91 pass / 0 skip / 0 fail of 91' $O/summary.txt && grep -q 'cpu: 8 pass / 0 skip / 0 fail of 8' $O/summary.txt"
chk "A C5: 0 firings over the P starts' requests (VF, C2 P, X, the screen, the fixtures), no-patch recommendation" "grep -q '^C5 (information): the lost-answer guard fired 0 time(s) over 64 client requests' $O/decision.txt && grep -q 'no switch patch needed now' $O/decision.txt"
chk "A INFO: the screen speed P vs B, the fixtures, exact7 3/7 (not expected bitwise)" "grep -q '^INFO screen speed (one pass each' $O/decision.txt && grep -q '^INFO fixtures on P (standard sampling): conv 1200 tokens' $O/decision.txt && grep -q '^INFO exact7 P .*: FAIL exact7 r23sw[0-9]*-P: 3/7' $O/decision.txt"
chk "A the lock sweep before port_gap4.sh end; nothing to NOTES.md / ntfy (mock)" "[ \$(line_of $O/summary.txt 'lock sweep before the end') -lt \$(line_of $O/summary.txt 'port_gap4.sh end: the daily back') ] && grep -q 'mock: would add to NOTES.md' $O/summary.txt"
chk "A the engine logs went to scratch/mock/logs and the sampled folder only" "[ -s $M/logs/engine-r23sw-P.log ] && [ ! -e $WS/logs/engine-r23sw-P.log ] && [ -s $O/sampled/logs/engine-X.log ]"
chk "A the GPU watch ran (the mock's nvidia-smi was asked)" "[ \$(cat $M/nvsmi.count) -gt 20 ]"

setup; run A2 MOCK_WEB_LOCAL=1
chk "A2 a SearXNG-only tree: C4 runs on B then P, PASS; SWITCH CHECKS PASS" "[ $RC = 0 ] && [ \"\$(V)\" = 'SWITCH CHECKS PASS' ] && grep -q '^C4 web search end to end: PASS' $O/decision.txt && [ \$(line_of $O/summary.txt 'server r23sw[0-9]*-webB ') -lt \$(line_of $O/summary.txt 'server r23sw[0-9]*-webP ') ]"
chk "A2 C5 counts the web P start too (64 requests)" "grep -q 'fired 0 time(s) over 64 client requests' $O/decision.txt"
setup; run D MOCK_WEB_LOCAL=1 MOCK_C2_DIFF=1
chk "D C2 DIFFERS (think-s1 differs on P) with C3 PASS -> SWITCH CHECKS PASS" "[ \"\$(V)\" = 'SWITCH CHECKS PASS' ] && grep -q '^C2 served outputs against the daily: DIFFERS' $O/decision.txt && grep -q '  think-s1: DIFFERS (ids differ from position 2' $O/decision.txt"
setup; run D2 MOCK_WEB_LOCAL=1 MOCK_C2_DIFF=1 MOCK_SQ_X=FAIL
chk "D2 C2 DIFFERS and C3 FAIL -> SWITCH CHECKS FAIL (C3)" "[ \"\$(V)\" = 'SWITCH CHECKS FAIL (C3)' ]"
setup; run NR MOCK_WEB_LOCAL=1 MOCK_C2_NOREP=1
chk "NR B never reproducible: C2 DIFFERS (C2_NOREF_FORM differs, flagged); C3 decides: PASS" "[ \"\$(V)\" = 'SWITCH CHECKS PASS' ] && grep -q '^FLAG (C2) no request was B-reproducible' $O/decision.txt"
setup; run E MOCK_PAR_FAIL=gr_parity
chk "E a GPU parity program fails: FAIL (C1) - the gap went on (C2, C3, C5 ran)" "[ $RC = 0 ] && [[ \"\$(V)\" == 'SWITCH CHECKS FAIL (C1)'* ]] && grep -q '  gpu: FAIL - gpu: 90 pass / 0 skip / 1 fail of 91: gr_parity' $O/decision.txt && grep -q 'server r23sw[0-9]*-scrB1 ' $O/summary.txt"
setup; run EP MOCK_DIRECT_FAIL=prefill_fused_iq_test
chk "EP the --edge direct run fails: FAIL (C1), named" "[[ \"\$(V)\" == 'SWITCH CHECKS FAIL (C1)'* ]] && grep -q 'prefill_fused_iq_test_edge (FAIL' $O/decision.txt"
setup; run F MOCK_SERVE_FAIL=1
chk "F a new server-suite failure before the gap: the gap STILL opens (exit 0, begin 1), FAIL (C1) with the test named, the rest measured" "[ $RC = 0 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && [ \"\$(V)\" = 'SWITCH CHECKS FAIL (C1)' ] && grep -q '^C1 BEFORE THE GAP: servetests: .*NEW: test_new_thing' $O/decision.txt && grep -q '^C3 the sampled test .*: PASS' $O/decision.txt && grep -q '^C4 web search end to end: PASS' $O/decision.txt"
setup; run F2 MOCK_NODE_RC=1
chk "F2 node --check fails: the gap opens, FAIL (C1) naming node" "[ $RC = 0 ] && [ \$(nbeg) = 1 ] && [ \"\$(V)\" = 'SWITCH CHECKS FAIL (C1)' ] && grep -q '  node: FAIL' $O/decision.txt && grep -q '^C1 BEFORE THE GAP: node: ' $O/decision.txt"
setup; run F3 MOCK_DIRECT_FAIL=patch_guard_test
chk "F3 patch_guard_test fails before the gap: the gap opens, FAIL (C1) naming patch_guard_test" "[ $RC = 0 ] && [ \$(nbeg) = 1 ] && grep -q '  cpu: FAIL - cpu: 7 pass / 0 skip / 1 fail of 8: patch_guard_test' $O/decision.txt && [ \"\$(V)\" = 'SWITCH CHECKS FAIL (C1)' ]"
setup; sed -i 's/"exa_usd": null/"exa_usd": 8.0/' $M/paidtools/u.json; run PB
chk "PB the paid budget too low before the gap (Exa \$2 left < 25 % + 10 calls): C4 NOT RUN: paid budget, INCOMPLETE (C4 NOT RUN), the rest ran" "[ $RC = 0 ] && grep -q '^webpath REFUSED C4 NOT RUN: paid budget - exa: 8 of 10 USD used' $O/gates.txt && [ \"\$(V)\" = 'INCOMPLETE (C4 NOT RUN)' ] && ! grep -q 'server r23sw[0-9]*-webB ' $O/summary.txt && grep -q 'server r23sw[0-9]*-scrB1 ' $O/summary.txt"
setup; run PD MOCK_PAID_DRAIN_AT=c2P
chk "PD the budget drained during the gap (by Jan chat): refused right before C4, INCOMPLETE (C4 NOT RUN)" "[ $RC = 0 ] && grep -q '^webpath PAID' $O/gates.txt && grep -q '^c4budget REFUSED C4 NOT RUN: paid budget' $O/gates.txt && [ \"\$(V)\" = 'INCOMPLETE (C4 NOT RUN)' ] && ! grep -q 'server r23sw[0-9]*-webB ' $O/summary.txt"
setup; run PS MOCK_PAID_PER_REQ=4
chk "PS 4 paid calls a request: B sends 2 (4 + 1: B's hard cap 5), P sends 2 (4 + 1: the hard total 10), each 3rd not run (the soft 5 per arm); judged on 2: PASS; the hard cap holds the total at 10 or below" "[ $RC = 0 ] && [ \"\$(V)\" = 'SWITCH CHECKS PASS' ] && grep -q 'paid searches during C4: 10 (B 5, P 5' $O/decision.txt && [ \$(python3 -c \"import json; print(json.load(open('$M/paidtools/u.json'))['run'])\") -le 10 ] && grep -q '  searxng: NOT RUN (the paid-call stop (soft): 5 of the arm' $O/decision.txt"
setup; run PS2 MOCK_PAID_PER_REQ=6
chk "PS2 6 paid calls a request: B 1 request (5, capped), P 1 (5, the total 10 capped), the rest not run -> fewer than 2 per arm: INCOMPLETE (C4 NOT DECIDED); the hard cap holds the total at 10" "[ $RC = 0 ] && [ \"\$(V)\" = 'INCOMPLETE (C4 NOT DECIDED)' ] && grep -q 'paid searches during C4: 10 (B 5, P 5' $O/decision.txt && [ \$(python3 -c \"import json; print(json.load(open('$M/paidtools/u.json'))['run'])\") = 10 ]"
setup; run PE MOCK_PENV_BAD_AT=webP
chk "PE (S1) P's test server lacks PAID_SEARCH_RUN_CAP: penv_webP FAIL, nothing sent on P, C4 NOT RUN (env) -> INCOMPLETE (C4 NOT RUN)" "[ $RC = 0 ] && grep -q '^penv_webP FAIL C4 NOT RUN (env)' $O/gates.txt && [ \$(grep -c '\"not_run\": true' $O/c4/P/web.jsonl) = 3 ] && grep -q '^C4 web search end to end: NOT RUN - C4 NOT RUN (env)' $O/decision.txt && [ \"\$(V)\" = 'INCOMPLETE (C4 NOT RUN)' ]"
setup; run PF MOCK_FATAL_AT=webP
chk "PF (S2) an engine-stopped line on P's C4 start: C4 FAIL (not NOT DECIDED) -> SWITCH CHECKS FAIL (C4)" "[ $RC = 0 ] && grep -q '^fatal_webP FAIL' $O/gates.txt && [ \"\$(V)\" = 'SWITCH CHECKS FAIL (C4)' ] && grep -q \"P's C4 start: \" $O/decision.txt"
setup; run PF2 MOCK_FATAL_AT=webB
chk "PF2 the same line on B's C4 start still voids: C4 NOT DECIDED" "grep -q '^C4 web search end to end: NOT DECIDED' $O/decision.txt"
setup; run NJ MOCK_NINJA_STALE=1
chk "NJ (S3) build-switch not up to date (ninja -n has a step): a hard refusal, exit 6, no begin, no CPU test" "[ $RC = 6 ] && [ \$(nbeg) = 0 ] && grep -q 'build-switch is not up to date with the tree (ninja -n: \[1/1\]' $O/result.txt && ! grep -q 'ctest cpu' $O/summary.txt"
setup; run KC MOCK_KERR_CPU=1
chk "KC (M2) a kernel error during the CPU ctest entries: a hard refusal at once (exit 6, an alert), no begin, no server suite" "[ $RC = 6 ] && [ \$(nbeg) = 0 ] && grep -q 'a kernel error was recorded during C1.s CPU parts (after the CPU ctest entries' $O/result.txt && grep -q 'would alert: v0.2.13 switch checks not started' $O/summary.txt && [ ! -s $O/c1/servetests.txt ]"
setup; run G MOCK_VF=FAIL
chk "G the read-back mismatches: FAIL (C1), readback FAIL; the rest ran" "[[ \"\$(V)\" == 'SWITCH CHECKS FAIL (C1)'* ]] && grep -q '  readback: FAIL - FAIL: read-back mismatch' $O/decision.txt && grep -q 'server r23sw[0-9]*-sqR2 ' $O/summary.txt"
setup; run R MOCK_VF=ONCE
chk "R the read-back not decided on try 1: tried once more after C2 (try 2 PASS), the first try's folder kept" "grep -q 'read-back VF (try 2): PASS' $O/summary.txt && [ \$(line_of $O/summary.txt 'server r23sw[0-9]*-c2P ') -lt \$(line_of $O/summary.txt 'read-back VF (try 2)') ] && ls -d $O/sampled/void-VF-try1-* > /dev/null 2>&1 && grep -q '  readback: PASS' $O/decision.txt"

FIND='{"repos": {"unsloth/Qwen4-Flash-GGUF": {"kind": "Flash", "access": {"private": false, "gated": false}, "weights": {"a.gguf": 1}}}}'
setup; echo "$FIND" > $M/state.json; run H
chk "H the priority hold before the gap: exit 8, no begin, no CPU test" "[ $RC = 8 ] && [ \$(nbeg) = 0 ] && grep -q '^HELD by the priority rule' $O/result.txt && ! grep -q 'ctest cpu' $O/summary.txt"
setup; echo "$FIND" > $M/state.json; echo "2026-11-14: Karl: the Qwen4 day-one work is done" > $M/switch0213-priority-done; run O_ MOCK_WEB_LOCAL=1
chk "O the dated override: the gap runs, named in the summary and the decision, and (M3) not flagged as an unreadable watch state" "[ $RC = 0 ] && grep -q 'THE PRIORITY HOLD IS OVERRIDDEN' $O/summary.txt && grep -q '^PRIORITY OVERRIDE: ' $O/decision.txt && ! grep -q 'could not read the watch state' $O/decision.txt"
setup; run H2 MOCK_PRIO_AT=c2B2
chk "H2 a find during the gap (after C2 B2): exit 8, no later start, the gap ended cleanly, the decision lists the stop" "[ $RC = 8 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && ! grep -q 'server r23sw[0-9]*-c2P ' $O/summary.txt && grep -q '^STOPPED: the priority rule stopped the gap' $O/decision.txt && grep -q '^STOPPED by the priority rule' $O/result.txt"

setup; mkdir -p $O; echo keep > $O/marker; bash -c 'exec -a gap-switch0213-fake sleep 600' > /dev/null 2>&1 < /dev/null & FP=$!; sleep 0.3; echo $FP > $M/driver.pid
run I; kill $FP 2> /dev/null
chk "I a second instance exits 9 and touches nothing" "[ $RC = 9 ] && [ -s $M/out-I/marker ] && [ \"\$(cat $M/driver.pid)\" = $FP ] && [ \$(nbeg) = 0 ] && grep -q 'another gap-switch0213.sh (pid $FP) is running' $M/I.out"
rm -f $M/driver.pid
setup; sleep 600 > /dev/null 2>&1 < /dev/null & SP=$!; echo $SP > $M/lockpid; run J; kill $SP 2> /dev/null; rm -f $M/lockpid
chk "J another gap holds the lock: exit 1 (busy), no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'another gap holds the test lock' $O/result.txt"
setup; run K MOCK_BUILD_ACTIVE=1
chk "K the build unit active: exit 1 (busy), no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'build unit .* is still active' $O/result.txt"
setup; echo "phase 4 gap: another gap's work (since now)" > $M/hold; run HF
chk "HF the research queue held by someone else: busy, no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'research queue is held by someone else' $O/result.txt"

setup; run L MOCK_LOST_AT=scrP1
chk "L the lost-answer line on the P screen: C5 1 firing over the workload, named, a recommendation; the verdict unchanged" "grep -q 'fired 1 time(s) over 64 client requests' $O/decision.txt && grep -q '  FIRING scrP1: server_r23sw[0-9]*-scrP1_mock.log line' $O/decision.txt && grep -q 'RECOMMENDATION (for Karl): 1 firing(s)' $O/decision.txt && [ \"\$(V)\" = 'SWITCH CHECKS PASS' ]"
setup; run M_ SW_MAX_MIN=32
chk "M a 32-min deadline: the sampled part (33 min) does not fit after parity / VF / C2 -> INCOMPLETE (C3 NOT RUN)" "[ $RC = 0 ] && grep -q '^skip_sampled INFO the deadline' $O/gates.txt && [[ \"\$(V)\" == *'C3 NOT RUN'* ]]"
setup; run N MOCK_ENGINES_LEFT=1
chk "N engines left after 8080 stopped: exit 5, the gap closed, nothing measured" "[ $RC = 5 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && grep -q '^not run: engines still running after 8080 stopped' $O/result.txt && ! grep -q 'C1 the GPU parity programs' $O/summary.txt"
setup; run X2 MOCK_OLD_ENGINE=1
chk "X2 8080's stopping engine left running (B's binary): exit 5, named as from before the gap, NEVER killed" "[ $RC = 5 ] && alive $M/old-engine.pid && grep -q 'from before the gap, left alone: [0-9]*(swmock-eng' $O/result.txt && grep -q 'running since before the gap - left alone' $O/summary.txt"
setup; run KE MOCK_KERR_AT=c2B2
chk "KE a kernel error during C2 B2: the engine killed at once, exit 3, no later start, the daily back, the marker kept" "[ $RC = 3 ] && ! alive $M/kerr-engine.pid && [ -e $M/out-KE/kerr.seen ] && ! grep -q 'server r23sw[0-9]*-c2P ' $O/summary.txt && [ \$(nend) = 1 ] && [ -s $M/kernel_error ] && grep -q '^KERNEL ERROR during the gap - stopped at once, the daily back on 8080; kwatch not cleared' $O/result.txt"
setup; run KP MOCK_KERR_PAR=1
chk "KP a kernel error during the parity programs: the parity program killed at once, exit 3, no server started" "[ $RC = 3 ] && ! alive $M/par-prog.pid && ! grep -q 'server r23sw[0-9]*-sqVF ' $O/summary.txt && [ \$(nend) = 1 ]"
setup; run KE2 MOCK_KERR_AT=c2B1 MOCK_END_FAIL=1
chk "KE2 a kernel error and port_gap4.sh end failing: exit 3, '8080 NOT back', its alert" "[ $RC = 3 ] && grep -q '^KERNEL ERROR during the gap - stopped at once, 8080 NOT back' $O/result.txt && grep -q 'would alert: v0.2.13 switch checks: kernel error, 8080 not back' $O/summary.txt"
setup; run K2 MOCK_END_FAIL=1
chk "K2 port_gap4.sh end fails: exit 4, an alert, the decision written" "[ $RC = 4 ] && grep -q '^port_gap4.sh end FAILED' $O/result.txt && [ -s $O/decision.txt ]"
setup; run V_ MOCK_LEFTOVER_AT=c2P
chk "V a C2 P run that left its test server behind: void, C2 NOT DECIDED -> INCOMPLETE (C2 named)" "grep -q '^void_c2P FAIL the run left' $O/gates.txt && grep -q '^C2 served outputs against the daily: NOT DECIDED' $O/decision.txt && [[ \"\$(V)\" == *'C2 NOT DECIDED'* ]]"
setup; run EV MOCK_ENVBAD_AT=sqX
chk "EV the X start's server.py lacks STRATA_DEBUG: armenv FAIL, the client not run, C3 NOT DECIDED" "grep -q '^fenv_sqX FAIL ARM ENV FAILED (P)' $O/gates.txt && [ ! -s $O/sampled/X/sampled.jsonl ] && grep -q '^C3 the sampled test .*: NOT DECIDED' $O/decision.txt"
setup; run FS MOCK_FOREIGN_AT=sqX
chk "FS a foreign GPU user during X: foreign_sqX FAIL, sq.py's PASS does not stand (C3 NOT DECIDED)" "grep -q '^foreign_sqX FAIL seen during sqX' $O/gates.txt && grep -q '^C3 the sampled test .*: NOT DECIDED - sq.py gave PASS' $O/decision.txt"
setup; run W MOCK_WDG_S=1 MOCK_SLEEP_AT=c2B1 MOCK_SLEEP_S=3
chk "W the watchdog fires once while the gap is still open past its time (mock: seconds)" "[ $RC = 0 ] && [ \$(grep -c 'mock watchdog' $M/wdg.log 2> /dev/null) = 1 ]"
setup; bgrun T $O/summary.txt 'server r23sw[0-9]+-c2B1 ' MOCK_SLEEP_AT=c2B1 MOCK_SLEEP_S=4
chk "T a signal during a server run: exit 7, INTERRUPTED, the gap may still be open, no end, 8080's state in the alert (M1)" "[ $RC = 7 ] && grep -q '^INTERRUPTED: the gap may still be open (tmp/port-gap.lockpid): close it with work/r22/port_gap4.sh end; 8080 is' $O/result.txt && [ \$(nend) = 0 ] && [ ! -e $M/driver.pid ] && grep -qE 'would alert: v0.2.13 switch checks interrupted - the driver was stopped; the gap may still be open; 8080 is (NOT )?listening' $O/summary.txt"
setup; bgrun T2 $M/pg4.log '^end' MOCK_END_SLEEP=3
chk "T2 a signal during port_gap4.sh end: exit 7, no second end suggested" "[ $RC = 7 ] && grep -q '^INTERRUPTED: the driver was stopped while port_gap4.sh end was running: do NOT run end a second time blindly' $O/result.txt && [ \$(nend) = 1 ]"
setup

# ---------------------------------------------------------------- the starter against a stub driver
ST=$M/starter
cat > $ST/drv.sh <<'EOF'
#!/bin/bash
# stub driver: MODE busy1 (busy once, then done), hold, busy, noresult, engines, other
ST=__ST__
n=$(( $(cat $ST/count 2> /dev/null || echo 0) + 1 )); echo $n > $ST/count
case $(cat $ST/mode) in
  busy1) if [ $n = 1 ]; then echo "not started (busy): mock" > $ST/result.txt; exit 1; fi; echo "DONE mock" > $ST/result.txt; exit 0;;
  hold) echo "HELD by the priority rule (mock)" > $ST/result.txt; exit 8;;
  busy) echo "not started (busy): mock" > $ST/result.txt; exit 1;;
  noresult) exit 1;;
  engines) echo "not run: engines still running after 8080 stopped (mock)" > $ST/result.txt; exit 5;;
  other) exit 9;;
esac
EOF
sed -i "s|__ST__|$ST|" $ST/drv.sh
printf '#!/bin/bash\necho "$*" >> %s/notify.log\n' $ST > $ST/notify.sh; chmod +x $ST/drv.sh $ST/notify.sh
sha() { sha256sum "$1" | cut -c1-12; }
srun() {   # srun NAME MODE [VAR=VALUE ...]: the starter with its test overrides -> rc in RC
  local n=$1 mode=$2; shift 2
  rm -f $ST/count $ST/result.txt $ST/notify.log $ST/starter.log; echo $mode > $ST/mode; rm -rf $ST/copies
  env SWS_DRIVER=$ST/drv.sh SWS_BUILD_UNIT=switch-mock-no-such-unit SWS_LOCKPID=$M/lockpid SWS_LOG=$ST/starter.log \
      SWS_COPIES=$ST/copies SWS_RESULT=$ST/result.txt SWS_POLL_S=1 SWS_RETRY_S=1 SWS_SETTLE_S=0 SWS_NOTIFY=$ST/notify.sh \
      "$@" timeout 120 bash $SG/switch-start.sh > $ST/$n.out 2>&1; RC=$?
  cp $ST/starter.log $ST/$n.log 2> /dev/null
  echo "--- starter $n: rc $RC"
}
ready() { echo "reviewed by mock: sha256 $(sha $ST/drv.sh), rules $(sha $SG/switch_rules.py), c2 $(sha $SG/c2_client.py), c4 $(sha $SG/c4_web.py), fx $(sha $SG/fixtures_client.py), spec $(sha $SG/spec-port0213.json), sq $(sha $WS/work/r23/sampled-qwen/sq.py), client $(sha $WS/work/r23/sampled-qwen/sq_client.py), stat $(sha $WS/work/r23/sampled-qwen/sq_stat.py), starter $(sha $SG/switch-start.sh)" > $ST/drv.sh.ready; }
setup; rm -f $ST/drv.sh.ready; srun S1 busy1
chk "S1 no .ready -> exit 6, an alert, no try" "[ $RC = 6 ] && grep -q 'v0.2.13 switch checks not started' $ST/notify.log && [ ! -e $ST/count ]"
setup; ready; sed -i 's/, sq [0-9a-f]*//' $ST/drv.sh.ready; srun S1b busy1
chk "S1b a .ready without sq.py's sha -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup; ready; sed -i 's/, starter [0-9a-f]*//' $ST/drv.sh.ready; srun S1c busy1
chk "S1c (M8) a .ready without the starter's own sha -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup; ready; sed -i 's/, stat [0-9a-f]*//' $ST/drv.sh.ready; srun S1d busy1
chk "S1d (M8) a .ready without sq_stat.py's sha -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup; ready; sleep 600 > /dev/null 2>&1 < /dev/null & SP=$!; echo $SP > $M/lockpid; ( sleep 3; kill $SP; rm -f $M/lockpid ) & srun S2 busy1
chk "S2 waited for the open gap to close, busy once, then done: 2 tries, exit 0" "[ $RC = 0 ] && [ \$(cat $ST/count) = 2 ] && grep -q 'a gap open: yes' $ST/S2.log && [ \$(ls $ST/copies | wc -l) = 2 ]"
setup; ready; srun S3 hold
chk "S3 the priority hold is final: 1 try, exit 8" "[ $RC = 8 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'priority rule (final' $ST/S3.log"
setup; ready; srun S4 busy SWS_RETRY_FOR_S=4
chk "S4 busy past the retry window: exit 1, an alert, more than 1 try" "[ $RC = 1 ] && [ \$(cat $ST/count) -ge 2 ] && grep -q 'stayed busy' $ST/notify.log"
setup; ready; srun S5 noresult
chk "S5 the driver ended without a result line: exit 3, an alert, no retry" "[ $RC = 3 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'without a result' $ST/notify.log"
setup; ready; srun S7 engines
chk "S7 engines left after 8080 stopped (exit 5): an alert, no retry" "[ $RC = 5 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'v0.2.13 switch checks not run' $ST/notify.log"
setup; ready; srun S8 other
chk "S8 another driver instance (exit 9): an alert, no retry" "[ $RC = 9 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'another switch-check driver is running' $ST/notify.log"
setup; ready; srun S9 busy1 SWS_TEST_CORRUPT_SNAPSHOT=1
chk "S9 a snapshot that is not the reviewed file: exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ] && grep -q 'snapshot is not the reviewed file' $ST/notify.log"
setup; ready; echo "edited" >> $ST/drv.sh; srun S6 busy1
chk "S6 a driver edited after its review -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup

echo "--- A decision.txt (first 16 lines, cut)"; head -16 $M/out-A/decision.txt | cut -c1-240
echo "--- A result.txt"; cut -c1-400 $M/out-A/result.txt
echo "gap-mock-test: $NCHK checks, $([ $F = 0 ] && echo 'ALL CHECKS PASSED' || echo 'FAILED')"
exit $F
