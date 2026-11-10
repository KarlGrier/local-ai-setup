#!/bin/bash
# gap-mock-test.sh - runs gap-gate0213.sh --mock against stubs under work/r23/gate-0213/scratch/mock, and the starter
# gate-start.sh against a stub driver, and checks their outputs (work/r23/switch-gap/gap-mock-test.sh's form). Every tool
# the driver calls is a stub there (with_server.sh, exact7.sh, kcheck.sh, guard.py, srv.sh, stopmon.sh, port_gap4.sh,
# abarm.sh, pf_yardstick.py, kernel_rule2.py / kernel_rule3.py, gap9_verdicts.py, bp90_client.py, bp90_report.py,
# abreport.py, patchtest.sh, nvidia-smi, basalt_fix_rules.py's br envcli, port0211_rules.py's envcheck, fixtures_client.py);
# the driver's mock mode skips the real preflight / file / engine / tree checks, never kills a real process, never queries
# the GPU and writes no NOTES.md / alert / ntfy. The rules run for real: gate0213_rules.py (switchref on a copy of the
# switch gap's result files, pins on the real configs, decide on the stubs' outputs: the screen records and engine logs
# and Basalt's records are the v0.2.11 gate's stored ones), make_configs0213.py (into the mock's folder, --no-sha),
# switch_rules.py armenv (on the stubs' fake /proc readings) and startline, port0211_rules.py startlines / lost / pcie /
# e7gate / e7cmp, afetch_rules.py priority (on a mock state file). Fake engines are copies of sleep named g13mock-eng
# (never strata*), stopped by the test. Nothing outside scratch/mock is written (the configs, the stored results and the
# trees are only read). Exit 0 = every check passed. (11-10 review fixes: the swap rule SW / SWE, the kernel stop's fatal line
# KF, Basalt's short passes BS1 / BS2, fence4 in A, the INFO pair off by default in AF.)
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; GD=$WS/work/r23/gate-0213; M=$GD/scratch/mock
P=$WS/.venv/bin/python; PY="$P -I -B"
SRC=$WS/results/r23/port-0211/gap; SWREAL=$WS/results/r23/port-0213/switch-gap
rm -rf $M; mkdir -p $M/bin $M/lib $M/kr $M/b90 $M/ba/scripts $M/fr $M/ru $M/clients $M/logs $M/slogs $M/prof $M/starter \
  $M/swref/configs $M/y8 $M/y16/x28h $M/y11/p211
# ---------------------------------------------------------------- the stubs
cat > $M/bin/mockeng.py <<'EOF'
# mockeng.py (gap-mock-test.sh only): the stub server's records and log lines
import json, os, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
SRC = Path("/home/USER/ai-speed-testing/strata-compare/results/r23/port-0211/gap")
def append(p, text):
    if p:
        with open(p, "a") as f:
            f.write(text)
def done_lines(n):
    return "".join("[strata] done: 512 tokens in 4 s (128.0 tok/s) (length, cancel=False)\n" for _ in range(n))
def prio_find():
    (M / "state.json").write_text(json.dumps({"repos": {"unsloth/Qwen4-Flash-GGUF": {"kind": "Flash", "access": {"private": False,
                                  "gated": False}, "weights": {"Qwen4-Flash-Q4_K_M.gguf": 1}, "first_seen": "mock"}}, "polls": 9,
                                  "last_poll": "mock"}))
cmd, a = sys.argv[1], sys.argv[2:]
slog, elog, lab = os.environ.get("SLOG"), os.environ.get("ELOG"), os.environ.get("MOCK_LABEL", "")
if os.environ.get("MOCK_PRIO_AT") and lab.endswith(os.environ["MOCK_PRIO_AT"]):
    prio_find()
if cmd == "screen":                     # screen R N OFF0: the v0.2.11 gate's stored B pass k as N's (MOCK_DEC_<arm>[k] scale decode)
    r, n, off0 = Path(a[0]), a[1], int(a[2])
    k = n[-1]
    f = float(os.environ.get(f"MOCK_DEC_{n}", os.environ.get(f"MOCK_DEC_{n[:-1]}", "1.0")))
    total = 0
    with open(elog, "rb") as fi:
        fi.seek(off0)
        (r / f"{n}.startlog").write_bytes(fi.read())
    for s in "nar":
        (r / f"{n}{s}.englog").write_text((SRC / "speed" / f"B{k}{s}.englog").read_text())
        recs = [json.loads(x) for x in (SRC / "speed" / f"B{k}{s}.jsonl").read_text().splitlines() if x.strip()]
        for x in recs:
            x["decode_tps"] = round(x["decode_tps"] * f, 2)
        (r / f"{n}{s}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs))
        total += len(recs)
    (r / f"{n}.wu.jsonl").write_text(json.dumps({"id": "warmup"}) + "\n")
    append(slog, done_lines(total + 1))
    if os.environ.get("MOCK_LOST_AT") and lab.endswith(os.environ["MOCK_LOST_AT"]):
        append(slog, "[strata] a request ended without an answer and without a finish reason; it is answered as an error\n")
    print(f"mock screen {n}: {total} requests, decode x {f}")
elif cmd == "bp":                       # bp LABEL SETS PASS OUT: the v0.2.11 gate's stored Basalt records (M or H) of that pass
    lab_, sets, k, out = a[0], a[1], int(a[2]), a[3]
    b = "M" if "-bpM-" in lab_ else "H"
    tests = {"decode": ("conv", "struct", "prose"), "pp16k": ("pp16k",), "pp64k": ("pp64k",)}[sets]
    f = float(os.environ.get("MOCK_BP_H", "1.0")) if b == "H" else 1.0
    if os.environ.get("MOCK_BP_RC_AT") and lab_.endswith(os.environ["MOCK_BP_RC_AT"]):
        print(f"mock bp90 {lab_}: the client failed (rc 1, no records)")
        sys.exit(1)
    drop = os.environ.get("MOCK_BP_DROP_AT") and lab_.endswith(os.environ["MOCK_BP_DROP_AT"])
    recs = [json.loads(x) for x in (SRC / "bp90" / f"cold-{b}.jsonl").read_text().splitlines() if x.strip()]
    with open(out, "a") as fo:
        for x in recs:
            if drop and x["test"] == "struct":
                continue
            if x["test"] in tests and x["pass"] == k:
                x["label"] = lab_
                if x.get("decode_tps"):
                    x["decode_tps"] = round(x["decode_tps"] * f, 2)
                    x["predicted_ms"] = round(x["predicted_ms"] / f, 1)
                fo.write(json.dumps(x) + "\n")
    append(slog, done_lines(len(tests)))
    print(f"mock bp90 {lab_}: pass {k} {sets}")
elif cmd == "fx":                       # fx OUT PLAN: the single-card start's records
    out, plan = Path(a[0]), json.loads(Path(a[1]).read_text())
    with open(out, "w") as f:
        for r in plan["requests"]:
            f.write(json.dumps({"name": r["name"], "prompt_tokens": r.get("expect_prompt_tokens"), "expect_prompt_tokens":
                                r.get("expect_prompt_tokens"), "completion_tokens": r["max_tokens"], "finish": "length",
                                "decode_tps": 95.0}) + "\n")
            print(f"fixture {r['name']}: {r['max_tokens']} tokens (length), 95.0 tok/s")
    append(slog, done_lines(len(plan["requests"])))
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
echo "# mock server log $L ($CFG)" > $SLOG
echo "=== mock $L start ($CFG)"
[ -n "${MOCK_FAIL_AT:-}" ] && [[ $L == *"$MOCK_FAIL_AT" ]] && { echo "server exited (mock)"; exit 1; }
fake() { $M/engines/$1/g13mock-eng 600 > /dev/null 2>&1 < /dev/null & echo $! >> $M/fake.pids; echo $!; }   # a fake engine (never named strata*)
$P -I -B - "$CFG" "$L" <<'PYEOF'
import json, os, sys
from pathlib import Path
cfg_path, lab = sys.argv[1], sys.argv[2]
M = Path(os.environ["SLOG"]).parents[1]
cfg = json.loads(Path(cfg_path).read_text())
env = dict(cfg.get("env", {}))
sha = "153ce47d3ef0" if "engine-r23afetch" in cfg["exe"] else "639dfb1b7042" if "engine-r23p0213" in cfg["exe"] else "?"
(M / "engine-env.json").write_text(json.dumps({"procs": [{"pid": 4242, "env": env, "sha12": sha, "parent_env": dict(env),
    "parent_argv": ["python", cfg["server"], "--engine", "strata", "--config", os.path.abspath(cfg_path)]}]}))
with open(cfg["log"], "a") as f:
    f.write("strata generate: the doorbell writes the CPU pool's Q8_K rows (mock)\nstrata mtp: EXACT speculative sampling on (mock)\n"
            "strata mtp: cumulative draft length ON (mock)\nstrata mtp: the cost gate prices draft steps (mock)\n"
            "strata prefill: prompt experts: v2 kernels (mock)\n")
    if env.get("STRATA_ADAPT_FETCH") == "2":
        f.write("strata serve: STRATA_ADAPT_FETCH=2: the PCIe share takes each layer's most-routed misses (mock)\n")
PYEOF
echo "server ready (mock: guard pid 1, server pid 2) load_time_s 1.0"
echo "engine pid 4242 pinned/locked: mock"
[ -n "${MOCK_SLEEP_AT:-}" ] && [[ $L == *"$MOCK_SLEEP_AT" ]] && sleep ${MOCK_SLEEP_S:-4}
if [ -n "${MOCK_FOREIGN_AT:-}" ] && [[ $L == *"$MOCK_FOREIGN_AT" ]] && [ ! -e $M/foreign-done ]; then   # a foreign GPU user during the run (once)
  touch $M/foreign-done; sleep 30 > /dev/null 2>&1 < /dev/null & echo $! > $M/foreign.pid; touch $M/foreign-on; sleep 1.2; rm -f $M/foreign-on; kill $(cat $M/foreign.pid)
fi
if [ -n "${MOCK_SWAP_AT:-}" ] && [[ $L == *"$MOCK_SWAP_AT" ]]; then   # an engine of the gap with VmSwap 2048 kB for 1.5 s
  fp=$(fake engine-r23p0213); echo 2048 > $M/vmswap.kB; sleep 1.5; rm -f $M/vmswap.kB; kill $fp 2> /dev/null; wait $fp 2> /dev/null
fi
if [ -n "${MOCK_KERR_AT:-}" ] && [[ $L == *"$MOCK_KERR_AT" ]]; then   # a kernel error during the run: kwatch's marker, an engine to kill
  [ "${MOCK_KERR_FATAL:-0}" = 1 ] && echo "[strata] the engine had stopped (exit code 137); it starts again" >> $SLOG   # (the kill's trace)
  fake engine-r23p0213 > $M/kerr-engine.pid; echo "Xid 79 (mock): GPU has fallen off the bus" > $M/kernel_error; sleep 1.5
fi
bash -c "$*"
[ -n "${MOCK_LEFTOVER_AT:-}" ] && [[ $L == *"$MOCK_LEFTOVER_AT" ]] && touch $M/leftover   # (its server "survives" the stop)
[ -n "${MOCK_FATAL_AT:-}" ] && [[ $L == *"$MOCK_FATAL_AT" ]] && echo "[strata] the engine had stopped (exit code 139); it starts again" >> $SLOG
echo "=== mock $L done"
EOF
cat > $M/lib/exact7.sh <<'EOF'
#!/bin/bash
# mock exact7.sh LABEL CFG (PIN_CACHE, REF): MOCK_E7_<name> of 7 identical (default 7), slots MATCHED; the prof files the
# driver reads (x-math with the patch-guard line, x-112k); MOCK_KERR_E7=<name>: a kernel error with a fake engine running
M=$(dirname $(dirname $(readlink -f $0)))
L=$1; n=${L##*-}; v=MOCK_E7_$n; k=${!v:-7}
if [ "${MOCK_KERR_E7:-}" = "$n" ]; then
  $M/engines/engine-r23p0213/g13mock-eng 600 > /dev/null 2>&1 < /dev/null & echo $! >> $M/fake.pids; echo $! > $M/kerr-engine.pid
  echo "Xid 79 (mock): during exact7 $n" > $M/kernel_error; sleep 3
fi
if [ "${MOCK_SWAP_E7:-}" = "$n" ]; then   # an engine of this run with VmSwap 2048 kB for 1.5 s
  $M/engines/engine-r23p0213/g13mock-eng 600 > /dev/null 2>&1 < /dev/null & fp=$!; echo $fp >> $M/fake.pids
  echo 2048 > $M/vmswap.kB; sleep 1.5; rm -f $M/vmswap.kB; kill $fp 2> /dev/null; wait $fp 2> /dev/null
fi
g="strata patch guards: 7 checked, 0 off [spec_exact side_mixer router_q8k qsa_split_attn gr_fork draft_cum prefill_v2]"
[ "${MOCK_GUARDS_OFF:-0}" = 1 ] && g="strata patch guards: 7 checked, 1 off [gr_fork: off]"
echo "$g" > $M/prof/$L-x-math.out; echo "output : 1 2 3" > $M/prof/$L-x-112k.out
echo "$L-x-math out abcd1234 (${REF:-C*13} abcd1234) =  ms/round 10.00  prompt ms 100"
echo "exact7 $L: $k/7 identical to ${REF:-C*13}"
echo "exact7-slots $L: 3238+3300 slots (5080 + 4060 Ti); ${REF:-C*13}: 3238+3300 -> MATCHED"
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
cat > $M/lib/patchtest.sh <<'EOF'
#!/bin/bash
# mock patchtest.sh lossless (CFG, ELOG): the cfg row's PASS line (MOCK_LOSSY=1: a lossy line in the log)
[ "${MOCK_LOSSY:-0}" = 1 ] && { echo "lossless cfg: FAIL PASS (mock); 1 lossy line(s) in $ELOG"; exit 0; }
echo "lossless cfg: PASS (tail skip 0, mock); log clean"
EOF
cat > $M/kr/port_gap4.sh <<'EOF'
#!/bin/bash
# mock port_gap4.sh begin WHAT | end: a lock holder (sleep), the hold file, a log line per call
M=$(dirname $(dirname $(readlink -f $0)))
case $1 in
  begin) echo "begin $2" >> $M/pg4.log; echo "phase 4 gap: $2 (since mock)" > $M/hold
         sleep 600 > /dev/null 2>&1 < /dev/null & echo $! > $M/lockpid; echo "mock port_gap4: gap open";;
  end) echo "end" >> $M/pg4.log; [ -n "${MOCK_END_SLEEP:-}" ] && sleep $MOCK_END_SLEEP
       [ "${MOCK_END_FAIL:-0}" = 1 ] && { echo "mock port_gap4: the daily did not start"; exit 1; }
       kill $(cat $M/lockpid) 2> /dev/null; rm -f $M/lockpid $M/hold; echo "mock port_gap4: served build back";;
esac
EOF
cat > $M/kr/abarm.sh <<'EOF'
#!/bin/bash
# mock abarm.sh URL OFF0 OUTDIR NAME SPEC...: the v0.2.11 gate's stored screen pass as NAME's
M=$(dirname $(dirname $(readlink -f $0)))
/home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B $M/bin/mockeng.py screen $3 $4 $2
EOF
cat > $M/kr/pf_yardstick.py <<'EOF'
# mock pf_yardstick.py run CFG OUT --set long40: 40 first-token logit files (the mock references hold the same bytes)
import json, sys
from pathlib import Path
out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
for i in range(40):
    (out / f"first.{i}").write_bytes(b"mock logits %d\n" % i)
(out / "index.json").write_text(json.dumps({"prompts": 40}))
print("pf_yardstick: 40 prompts (mock)")
EOF
cat > $M/kr/kernel_rule2.py <<'EOF'
import os, sys
print("p213   top-1 agreement 40/40, changed picks 0 (mock) -> " + os.environ.get("MOCK_KL2", "PASS"))
EOF
cat > $M/kr/kernel_rule3.py <<'EOF'
import os, sys
print("p213   KL mean 0.0001 p90 0.0002 (mock) -> " + os.environ.get("MOCK_KL3", "PASS"))
EOF
cat > $M/kr/gap9_verdicts.py <<'EOF'
import os
print("continuations: " + ("5 hits, 1 misses" if os.environ.get("MOCK_CONT_MISS") == "1" else "6 hits, 0 misses"))
EOF
cat > $M/b90/bp90_client.py <<'EOF'
# mock bp90_client.py URL --label L --sets SET --passes 1 --first-pass K --tree T --out OUT
import subprocess, sys
from pathlib import Path
a = sys.argv[1:]
o = lambda k: a[a.index(k) + 1]
M = Path(__file__).resolve().parents[1]
sys.exit(subprocess.call([sys.executable, "-I", "-B", str(M / "bin/mockeng.py"), "bp", o("--label"), o("--sets"), o("--first-pass"), o("--out")]))
EOF
printf 'import sys\nprint("mock Basalt report")\n' > $M/b90/bp90_report.py
printf 'import sys\nprint("mock speed table")\n' > $M/ba/scripts/abreport.py
cat > $M/fr/basalt_fix_rules.py <<'EOF'
# mock basalt_fix_rules.py br envcli EXE CFG --job J ...: waits for the job; MOCK_ENVCLI_BAD=<config file name> -> FAIL
import os, sys, time
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
    if os.environ.get("MOCK_ENVCLI_BAD") == Path(a[2]).name:
        print("ENV CHECK FAILED - the arm is void: mock"); gate("FAIL", "mock envcli mismatch"); sys.exit(1)
    print(f"ENV CHECK OK: 7 engine start(s) ({opt('--mode')}), mock"); gate("PASS", "mock envcli"); sys.exit(0)
sys.exit(2)
EOF
cat > $M/ru/port0211_rules.py <<'EOF'
# mock port0211_rules.py envcheck EXE CFG --ngpu N ...: the config's env = the fake engine's (engine-env.json), N GPUs
import json, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
a = sys.argv[1:]
def opt(k):
    return a[a.index(k) + 1] if k in a else None
cfg = json.loads(Path(a[2]).read_text())
env = json.loads((M / "engine-env.json").read_text())["procs"][0]["env"]
ng = len([x for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
ok = env == cfg.get("env", {}) and str(ng) == (opt("--ngpu") or "2")
print(f"engine pid 4242: mock, {ng} GPU(s); " + ("ENV CHECK OK" if ok else "ENV CHECK FAILED"))
if opt("--gates") and opt("--gate"):
    open(opt("--gates"), "a").write(f"{opt('--gate')} {'PASS' if ok else 'FAIL'} mock envcheck ({ng} GPU)\n")
sys.exit(0 if ok else 1)
EOF
cat > $M/clients/fixtures_client.py <<'EOF'
# mock fixtures_client.py URL OUT --plan PLAN ...: records in the real client's format (mockeng.py fx)
import subprocess, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
a = sys.argv[1:]
sys.exit(subprocess.call([sys.executable, "-I", "-B", str(M / "bin/mockeng.py"), "fx", a[1], a[a.index("--plan") + 1]]))
EOF
cat > $M/bin/nvidia-smi <<'EOF'
#!/bin/bash
# mock nvidia-smi: no compute process; a foreign one while foreign-on exists
M=$(dirname $(dirname $(readlink -f $0))); n=$(( $(cat $M/nvsmi.count 2> /dev/null || echo 0) + 1 )); echo $n > $M/nvsmi.count
[ -e $M/foreign-on ] && echo "$(cat $M/foreign.pid), 1000"
exit 0
EOF
chmod +x $M/lib/* $M/kr/*.sh $M/bin/nvidia-smi
for d in engine-r23afetch engine-r23p0213 engine-r22p028x engine-v0213stock engine-r22s028t; do   # the fake engines: copies of sleep
  mkdir -p $M/engines/$d; cp /bin/sleep $M/engines/$d/g13mock-eng
done
for x in ref unfused cpushare; do mkdir -p $M/y8/$x; echo '{}' > $M/y8/$x/index.json; done
for i in $(seq 0 39); do printf 'mock logits %d\n' $i > $M/y16/x28h/first.$i; printf 'mock logits %d\n' $i > $M/y11/p211/first.$i; done
echo '{}' > $M/y16/x28h/index.json; echo '{}' > $M/y11/p211/index.json
for f in verdict.txt result.txt summary.txt decision.txt result-line.txt rules.txt; do cp $SWREAL/$f $M/swref/$f; done
cp $SWREAL/configs/manifest.json $M/swref/configs/manifest.json
$P -I -c "
import json
std = {'temperature': 1.0, 'top_p': 0.95, 'top_k': 20, 'min_p': 0.05, 'presence_penalty': 0.0, 'frequency_penalty': 0.0, 'repetition_penalty': 1.0}
reqs = [{'name': n, 'messages': [{'role': 'user', 'content': n}], 'max_tokens': m, 'thinking': False, 'seed': 7300001 + i, 'expect_prompt_tokens': 38}
        for i, (n, m) in enumerate((('conv', 1200), ('struct', 8192), ('prose', 1200)))]
open('$M/fixtures-plan.json', 'w').write(json.dumps({'plan': 'C5 fixtures', 'fields': std, 'requests': reqs}))"
CLEAR='{"repos": {"Qwen/Qwen4-Flash": {"kind": "Flash", "access": {"private": false, "gated": "manual"}, "weights": {"model-00001.safetensors": 1}}}, "polls": 3, "last_poll": "mock"}'
HEADREAL=$(git -C $WS/strata-r23p0213 rev-parse HEAD)

# ---------------------------------------------------------------- the driver scenarios
F=0; NCHK=0
chk() { NCHK=$((NCHK + 1)); if eval "$2"; then echo "  ok   $1"; else echo "  FAIL $1"; F=1; fi; }
O=$M/out
setup() {   # a clean mock state (the watch state CLEAR, no gap open, no hold, no hooks left)
  [ -s $M/lockpid ] && kill $(cat $M/lockpid) 2> /dev/null
  for fp in $(cat $M/fake.pids 2> /dev/null); do kill $fp 2> /dev/null; done
  rm -f $M/pg4.log $M/lockpid $M/hold $M/engine-env.json $M/leftover $M/nvsmi.count $M/wdg.log $M/gate0213-priority-done $M/driver.pid
  rm -f $M/fake.pids $M/*-engine.pid $M/kernel_error $M/vmswap.kB $M/foreign-on $M/foreign.pid $M/foreign-done $M/paid-env-*.txt
  rm -rf $M/logs $M/slogs $M/prof $M/rb-cache $O; mkdir -p $M/logs $M/slogs $M/prof
  echo "$CLEAR" > $M/state.json
  cp $SWREAL/verdict.txt $M/swref/verdict.txt
}
run() {   # run NAME [VAR=VALUE ...]: the driver in mock mode -> $M/NAME.out, rc in RC
  local n=$1; shift
  env "$@" timeout 900 bash $GD/gap-gate0213.sh --mock > $M/$n.out 2>&1; RC=$?
  rm -rf $M/out-$n; cp -r $O $M/out-$n 2> /dev/null
  echo "--- scenario $n: driver rc $RC"
}
bgrun() {   # bgrun NAME WAITFILE PATTERN [VAR=VALUE ...]: the driver in the background; TERM once PATTERN shows in WAITFILE
  local n=$1 wf=$2 pat=$3 i; shift 3
  env "$@" bash $GD/gap-gate0213.sh --mock > $M/$n.out 2>&1 & local dp=$!
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
V() { head -1 $O/verdict.txt 2> /dev/null; }
V2() { sed -n 2p $O/verdict.txt 2> /dev/null; }

# U: an unknown argument runs nothing - the check itself and its place (the first command)
sed -n '1,/^case \${1:-} in/p' $GD/gap-gate0213.sh > $M/argcheck.sh; echo 'echo PAST-THE-CHECK' >> $M/argcheck.sh
chk "U --bogus: exit 2, nothing after the check" "bash $M/argcheck.sh --bogus > $M/U.out 2>&1; [ \$? = 2 ] && ! grep -q PAST $M/U.out && grep -q 'nothing run' $M/U.out"
chk "U --mock / --dry-run / no argument pass the check" "bash $M/argcheck.sh --mock | grep -q PAST && bash $M/argcheck.sh --dry-run | grep -q PAST && bash $M/argcheck.sh | grep -q PAST"
chk "U the check is the driver's first command (only set / exec / WS= before it)" "[ -z \"\$(sed -n '1,/^case \${1:-} in/p' $GD/gap-gate0213.sh | grep -vE '^#|^\$|^set -u -o pipefail\$|^exec 8>&- 9>&-|^WS=|^case ')\" ]"

setup; sleep 0 & wait $!; echo $! > $M/driver.pid   # (a stale pid file: a dead pid)
run A MOCK_SELFTEST=1 P0213G_AF2_E7=1
chk "A exit 0, result DONE, a stale pid file taken over and gone at the exit" "[ $RC = 0 ] && grep -q '^DONE (measurements only, nothing switched' $O/result.txt && [ ! -e $M/driver.pid ]"
chk "A BASELINE PASS, DECODE WITHIN NOISE (B = P: the stored v0.2.11 screen as both), under the 11-07 amendment" "[ \"\$(V)\" = 'BASELINE PASS' ] && [[ \"\$(V2)\" == 'DECODE WITHIN NOISE (P +0.00 % vs B'* ]] && grep -q 'AMENDMENT 2026-11-07' $O/decision.txt && grep -q 'chat-cache save \[11-07 amendment\]' $O/decision.txt"
chk "A switchref PASS on the copy of the switch gap; the rules' selftest ran; the configs checked; the pins (19) in P0213x.json and PH; fence4 PASS before the gap" "grep -q '^fence4 PASS four-backtick fence' $O/gates.txt && [ \$(line_of $O/summary.txt 'four-backtick fence with a three-backtick example') -lt \$(line_of $O/summary.txt 'mock port_gap4: gap open') ] && grep -q '^switchref PASS' $O/gates.txt && grep -q 'gate0213 selftest: [0-9]* checks, 0 failure(s)' $O/summary.txt && grep -q '^cfg PASS CONFIG CHECK OK' $O/gates.txt && grep -q '^pins PASS P0213x.json: all 19 pins' $O/gates.txt && grep -q '^pins_h PASS PH.json: all 19 pins' $O/gates.txt"
chk "A rules.txt frozen and the single-card plan made before the gap opened" "[ -s $O/rules.txt ] && [ \$(line_of $O/summary.txt 'rules frozen') -lt \$(line_of $O/summary.txt 'mock port_gap4: gap open') ] && grep -q '\"max_tokens\": 512' $O/single/single-plan.json"
chk "A port_gap4 begin once, end once; the gap closed" "[ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && [ ! -e $M/lockpid ] && [ ! -e $M/hold ]"
chk "A the order: exact7 s213 p213off x28h p213a p213b nov2 da2 pa2; long40; screen B1 P1 P2 B2 B3 P3; Basalt M H / H M / M H; the single card" "grep -oE 'exact7 g13[0-9]+-[a-z0-9]+ \(|3 KL: pf_yardstick|server g13[0-9]+-[A-Za-z0-9-]+ ' $O/summary.txt | sed -E 's/^exact7 g13[0-9]+-([a-z0-9]+) \(/\1/; s/^server g13[0-9]+-//; s/ \$//; s/^3 KL.*/pfy/' | tr '\n' ',' | grep -qx 's213,p213off,x28h,p213a,p213b,nov2,da2,pa2,pfy,B1,P1,P2,B2,B3,P3,bpM-decode-1,bpM-pp16k-1,bpM-pp64k-1,bpH-decode-1,bpH-pp16k-1,bpH-pp64k-1,bpH-decode-2,bpH-pp16k-2,bpH-pp64k-2,bpM-decode-2,bpM-pp16k-2,bpM-pp64k-2,bpM-decode-3,bpM-pp16k-3,bpM-pp64k-3,bpH-decode-3,bpH-pp16k-3,bpH-pp64k-3,SG,'"
chk "A exactness: e7_release, e7_vs_p028x, guards, e7_repeat, e7_v2 PASS; every exact7 item's env checked (6 required + 2 INFO); e7_af2 INFO; no s028 (7/7)" "for k in e7_release e7_vs_p028x guards e7_repeat e7_v2; do grep -q \"^\$k PASS\" $O/gates.txt || exit 1; done; [ \$(grep -cE '^env_(s213|p213off|x28h|p213a|p213b|nov2)_e7 PASS' $O/gates.txt) = 6 ] && [ \$(grep -cE '^infoenv_(da2|pa2)_e7 PASS' $O/gates.txt) = 2 ] && grep -q '^e7_af2 INFO exact7 g13[0-9]*-pa2: 7/7, slots MATCHED' $O/gates.txt && ! grep -q 's028' $O/summary.txt"
chk "A KL: env_pfy, kl2_p213, kl3_p213 PASS; logits INFO (0 of 40 vs x28h and p211)" "grep -q '^env_pfy PASS' $O/gates.txt && grep -q '^kl2_p213 PASS' $O/gates.txt && grep -q '^kl3_p213 PASS' $O/gates.txt && grep -q '^logits_vs_p028x INFO 0 of 40' $O/gates.txt && grep -q '^logits_vs_p0211 INFO 0 of 40' $O/gates.txt"
chk "A every server start's env (engine + server.py), armenv and fetch start line PASS: 6 screen + 18 Basalt starts = 72 gates; no void / foreign / fatal" "[ \$(grep -cE '^(env|fenv|line)_(B[123]|P[123]|bp[MH]-(decode|pp16k|pp64k)-[123]) PASS' $O/gates.txt) = 72 ] && ! grep -qE '^(void|foreign|fatal|rc|swap)_' $O/gates.txt"
chk "A after the gap: lossless, lost_answers, startlines_P (v0.2.13's wanted lines), cont_P PASS; the speed lines and Basalt PASS" "for k in lossless lost_answers startlines_P cont_P; do grep -q \"^\$k PASS\" $O/gates.txt || exit 1; done; grep -q 'speed screen decode: P +0.00 % vs B' $O/decision.txt && grep -q 'Basalt struct decode: P .* -> PASS' $O/decision.txt && [ \$(line_of $O/summary.txt 'port_gap4.sh end: the daily back') -lt \$(line_of $O/summary.txt 'gate lossless PASS') ]"
chk "A Basalt: 3 passes of M and of H in cold-M / cold-H (15 records each: decode 3 + pp16k + pp64k per pass)" "[ \$(grep -c . $O/bp90/cold-M.jsonl) = 15 ] && [ \$(grep -c . $O/bp90/cold-H.jsonl) = 15 ]"
chk "A the single card (INFO): its start checked with ONE GPU (env_SG / fenv_SG PASS, no fetch line asked), 3 requests at 512 tokens, decode listed in the decision" "grep -q '^env_SG PASS mock envcheck (1 GPU)' $O/gates.txt && grep -q '^fenv_SG PASS' $O/gates.txt && ! grep -q '^line_SG' $O/gates.txt && grep -q '^single_SG INFO the single-card start .*3 of 3 requests answered' $O/gates.txt && grep -q 'THE SINGLE-CARD FALLBACK' $O/decision.txt && grep -q '^lines_SG PASS' $O/gates.txt && grep -q '^lossless_SG INFO' $O/gates.txt"
chk "A every test server got PAID_SEARCH_KIND=test and no run id (0 paid searches)" "for f in $M/paid-env-g13*.txt; do grep -qx 'PAID_SEARCH_KIND=test' \$f && ! grep -q 'PAID_SEARCH_RUN' \$f || exit 1; done; [ \$(ls $M/paid-env-g13*.txt | wc -l) = 25 ]"
chk "A the lock sweep before port_gap4.sh end; nothing to NOTES.md / ntfy / alert (mock); the engine logs only in scratch/mock" "[ \$(line_of $O/summary.txt 'lock sweep before the end') -lt \$(line_of $O/summary.txt 'port_gap4.sh end: the daily back') ] && grep -q 'mock: would add to NOTES.md' $O/summary.txt && [ -s $M/logs/engine-g0213-P.log ] && [ ! -e $WS/logs/r23/gate0213/engine-g0213-P.log ]"
chk "A the GPU watch ran (the mock's nvidia-smi was asked)" "[ \$(cat $M/nvsmi.count) -gt 30 ]"

setup; run D MOCK_DEC_P=0.94
chk "D P's decode -6 % in every pass: DECODE REAL LOSS, BASELINE FAIL (speed screen), the NEXT (desk hunt) line" "[ $RC = 0 ] && [[ \"\$(V)\" == 'BASELINE FAIL (speed screen'* ]] && [[ \"\$(V2)\" == 'DECODE REAL LOSS (P -6.00 % vs B'* ]] && grep -q 'NEXT (Karl 11-10): find the cause desk-first' $O/decision.txt"
setup; run BL MOCK_DEC_P1=0.95 MOCK_DEC_P2=0.99 MOCK_DEC_P3=0.99
chk "BL one P pass -5 %, two -1 %: DECODE WITHIN NOISE (the pass spread covers it); g16's decode BORDERLINE" "[ $RC = 0 ] && [[ \"\$(V2)\" == 'DECODE WITHIN NOISE (P -2.35 % vs B'* ]] && grep -q 'speed screen decode: P -2.35 % vs B .* -> BORDERLINE' $O/decision.txt && [[ \"\$(V)\" == 'BASELINE BORDERLINE' || \"\$(V)\" == 'BASELINE FAIL (speed screen)' ]]"
setup; run E7 MOCK_E7_p213a=5 MOCK_E7_s028=7
chk "E7 PH 5/7 vs x28h, stock 0.2.8 = stock v0.2.13 (7/7): s028 ran after the repeat; FAIL (e7_vs_p028x) 'our port changed bits'" "[ \"\$(V)\" = 'BASELINE FAIL (e7_vs_p028x)' ] && grep -q 'our port changed bits' $O/decision.txt && [ \$(line_of $O/summary.txt 'exact7 g13[0-9]*-p213b (') -lt \$(line_of $O/summary.txt 'exact7 g13[0-9]*-s028 (') ] && grep -q '^e7_upstream PASS' $O/gates.txt"
setup; run E7B MOCK_E7_p213a=5 MOCK_E7_s028=4
chk "E7B PH 5/7, upstream moved too (s028 4/7): the cross-version INFO line, BASELINE PASS (the KL rules decide)" "[ \"\$(V)\" = 'BASELINE PASS' ] && grep -q 'upstream itself moved from 0.2.8 to 0.2.13' $O/decision.txt"
setup; run RL MOCK_E7_p213off=6
chk "RL every switch off is 6/7 against stock v0.2.13: FAIL (e7_release)" "[ \"\$(V)\" = 'BASELINE FAIL (e7_release)' ]"
setup; run GU MOCK_GUARDS_OFF=1 MOCK_KL2=FAIL
chk "GU a patch guard off and kernel_rule2 FAIL: FAIL (guards, kl2_p213)" "[ \"\$(V)\" = 'BASELINE FAIL (guards, kl2_p213)' ]"
setup; run EV MOCK_ENVCLI_BAD=PH.json
chk "EV PH's CLI engines not as configured (envcli FAIL): p213a / p213b / nov2 / pfy not judged on it, FAIL naming env_p213a_e7 and env_pfy" "[[ \"\$(V)\" == 'BASELINE FAIL ('* ]] && [[ \"\$(V)\" == *'env_p213a_e7'* ]] && [[ \"\$(V)\" == *'env_pfy'* ]] && ! grep -q '^e7_vs_p028x' $O/gates.txt && ! grep -q '^kl2_p213' $O/gates.txt"
setup; run AF MOCK_FAIL_AT=-SG
chk "AF the INFO pair off BY DEFAULT and the single-card server exits (rc_SG): both INFO, BASELINE PASS" "[ \"\$(V)\" = 'BASELINE PASS' ] && grep -q '^skip_e7_af2 INFO the INFO pair not run (P0213G_AF2_E7=0, the default' $O/gates.txt && grep -q '^rc_SG FAIL' $O/gates.txt && ! grep -q 'exact7 g13[0-9]*-da2' $O/summary.txt && grep -q '^start_SG INFO' $O/gates.txt && grep -q 'THE SINGLE-CARD FALLBACK' $O/decision.txt"
setup; run VO MOCK_FOREIGN_AT=-P2
chk "VO a foreign GPU user during P2: foreign_P2 FAIL, its records moved to speed/void, DECODE NOT DECIDED, BASELINE INCOMPLETE (foreign_P2, speed screen)" "grep -q '^foreign_P2 FAIL seen during P2' $O/gates.txt && ls $O/speed/void/P2n.jsonl > /dev/null 2>&1 && [ ! -e $O/speed/P2n.jsonl ] && [[ \"\$(V2)\" == 'DECODE NOT DECIDED'* ]] && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('*'foreign_P2'*'speed screen'* ]]"
setup; run LV MOCK_LEFTOVER_AT=-bpH-decode-2
chk "LV a Basalt H run that left its server behind: void, its records in bp90/void, BASELINE INCOMPLETE (void_bpH-decode-2)" "grep -q '^void_bpH-decode-2 FAIL the run left' $O/gates.txt && [ -s $O/bp90/void/bpH-decode-2.jsonl ] && [ \$(grep -c . $O/bp90/cold-H.jsonl) = 12 ] && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('*'void_bpH-decode-2'* ]]"
setup; run FT MOCK_FATAL_AT=-P3
chk "FT an engine restart line on P3's start: FAIL (fatal_P3)" "[[ \"\$(V)\" == 'BASELINE FAIL ('*'fatal_P3'* ]]"
setup; run SW MOCK_SWAP_AT=-P2
chk "SW (the swap rule) an engine with VmSwap 2048 kB during P2: swap_P2 FAIL with the peak, its records to speed/void, DECODE NOT DECIDED, INCOMPLETE (swap_P2, ...)" "grep -q '^swap_P2 FAIL VmSwap > 0 during P2: peak 2048 kB' $O/gates.txt && [ -e $O/speed/void/P2n.jsonl ] && [[ \"\$(V2)\" == 'DECODE NOT DECIDED'* ]] && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('*'swap_P2'* ]]"
setup; run SWE MOCK_SWAP_E7=p213a
chk "SWE (the swap rule, CLI) VmSwap > 0 during exact7 p213a: swap_e7p213a FAIL, its pair not judged, no repeat / v2 run against it, INCOMPLETE (swap_e7p213a, e7_vs_p028x ...)" "grep -q '^swap_e7p213a FAIL VmSwap > 0 during e7p213a' $O/gates.txt && ! grep -q '^e7_vs_p028x' $O/gates.txt && ! grep -qE 'exact7 g13[0-9]*-(p213b|nov2) \(' $O/summary.txt && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('*'swap_e7p213a'* ]] && [[ \"\$(V)\" == *'e7_vs_p028x'* ]]"
setup; run KF MOCK_KERR_AT=-P1 MOCK_KERR_FATAL=1
chk "KF a kernel error during P1 whose kill leaves an engine-restart line: exit 3; fatal_P1 written after the kstop line and judged as seen at the stop: INCOMPLETE (stopped first), not FAIL" "[ $RC = 3 ] && grep -q '^fatal_P1 FAIL' $O/gates.txt && [ \$(grep -n '^kstop ' $O/gates.txt | head -1 | cut -d: -f1) -lt \$(grep -n '^fatal_P1 ' $O/gates.txt | head -1 | cut -d: -f1) ] && [[ \"\$(V)\" == 'BASELINE INCOMPLETE (stopped'* ]] && grep -q \"seen at the stop (not judged as the port's): .*fatal_P1 FAIL\" $O/decision.txt"
setup; run BS1 MOCK_BP_RC_AT=-bpH-pp16k-2
chk "BS1 Basalt's client ends rc 1 on bpH-pp16k-2: rc_bpH-pp16k-2 FAIL, left out, P (H) pp16k 2 of 3 -> INCOMPLETE (rc_bpH-pp16k-2, Basalt fixtures)" "grep -q '^rc_bpH-pp16k-2 FAIL the client chain ended rc 1' $O/gates.txt && grep -q 'P (H) pp16k 2 of 3 -> NOT DECIDED' $O/decision.txt && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('*'rc_bpH-pp16k-2'*'Basalt fixtures'* ]]"
setup; run BS2 MOCK_BP_DROP_AT=-bpM-decode-3
chk "BS2 a Basalt run that answered rc 0 but without its struct record: B (M) struct 2 of 3 -> INCOMPLETE (Basalt fixtures), no rc gate" "! grep -q '^rc_' $O/gates.txt && grep -q 'B (M) struct 2 of 3' $O/decision.txt && [ \"\$(V)\" = 'BASELINE INCOMPLETE (Basalt fixtures)' ]"
setup; run LO MOCK_LOST_AT=-P1
chk "LO #3961's line in P1's server log: FAIL (startlines_P, lost_answers)" "[[ \"\$(V)\" == 'BASELINE FAIL ('*'lost_answers'* ]] && grep -q '^lost_answers FAIL #3961.s error line in 1 place' $O/gates.txt"
setup; run DL P0213G_MAX_MIN=0
chk "DL a 0-min deadline: the gap opens and closes, every step skipped -> BASELINE INCOMPLETE, end once" "[ $RC = 0 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('* ]] && ! grep -q 'server g13' $O/summary.txt"

setup; echo "INCOMPLETE (C4 NOT RUN)" > $M/swref/verdict.txt; run R1
chk "R1 the switch gap did not PASS: a hard refusal (exit 6), no begin" "[ $RC = 6 ] && [ \$(nbeg) = 0 ] && grep -q \"today's switch gap does not stand for this build\" $O/result.txt && grep -q 'would alert: v0.2.13 baseline gate not started' $O/summary.txt"
setup; run R2 MOCK_P_SHA=000000000000
chk "R2 engine-r23p0213 is not the sha the switch gap measured: exit 6, no begin" "[ $RC = 6 ] && [ \$(nbeg) = 0 ] && grep -q 'engine-r23p0213/strata is 000000000000 now' $O/result.txt"
setup; run R3 MOCK_HEAD=0123456789abcdef0123456789abcdef01234567
chk "R3 the worktree moved since the switch gap: exit 6, no begin" "[ $RC = 6 ] && [ \$(nbeg) = 0 ] && grep -q 'strata-r23p0213 is at 0123456789ab now' $O/result.txt"
setup; run SK MOCK_STOCK_MISSING=1
chk "SK the stock v0.2.13 engine missing: exit 6, no begin" "[ $RC = 6 ] && [ \$(nbeg) = 0 ] && grep -q 'engine-v0213stock/strata is missing' $O/result.txt"
setup; run B8 MOCK_BUILD8_FAIL=1
chk "B8 a configure log without 8-row windows: exit 6, no begin" "[ $RC = 6 ] && [ \$(nbeg) = 0 ] && grep -q '8-row windows' $O/result.txt"
setup; run K MOCK_BUILD_ACTIVE=1
chk "K the build unit build-p0213-stock active: exit 1 (busy), no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'build unit .* is still active' $O/result.txt"
setup; sleep 600 > /dev/null 2>&1 < /dev/null & SP=$!; echo $SP > $M/lockpid; run J; kill $SP 2> /dev/null; rm -f $M/lockpid
chk "J another gap holds the lock: exit 1 (busy), no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'another gap holds the test lock' $O/result.txt"
setup; echo "phase 4 gap: another gap's work (since now)" > $M/hold; run HF
chk "HF the research queue held by someone else: busy, no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'research queue is held by someone else' $O/result.txt"
setup; mkdir -p $O; echo keep > $O/marker; bash -c 'exec -a gap-gate0213-fake sleep 600' > /dev/null 2>&1 < /dev/null & FP=$!; sleep 0.3; echo $FP > $M/driver.pid
run I; kill $FP 2> /dev/null
chk "I a second instance exits 9 and touches nothing" "[ $RC = 9 ] && [ -s $M/out-I/marker ] && [ \"\$(cat $M/driver.pid)\" = $FP ] && [ \$(nbeg) = 0 ] && grep -q 'another gap-gate0213.sh (pid $FP) is running' $M/I.out"
rm -f $M/driver.pid

FIND='{"repos": {"unsloth/Qwen4-Flash-GGUF": {"kind": "Flash", "access": {"private": false, "gated": false}, "weights": {"a.gguf": 1}}}}'
setup; echo "$FIND" > $M/state.json; run H
chk "H the priority hold before the gap: exit 8, no begin" "[ $RC = 8 ] && [ \$(nbeg) = 0 ] && grep -q '^HELD by the priority rule' $O/result.txt"
setup; echo "$FIND" > $M/state.json; echo "2026-11-14: Karl: the Qwen4 day-one work is done" > $M/gate0213-priority-done; run O_
chk "O the dated override: the gap runs, named in the summary and the decision" "[ $RC = 0 ] && grep -q 'THE PRIORITY HOLD IS OVERRIDDEN' $O/summary.txt && grep -q '(info) priority_override' $O/decision.txt && [ \"\$(V)\" = 'BASELINE PASS' ]"
setup; run H2 MOCK_PRIO_AT=-B2
chk "H2 a find during the gap (during screen B2): exit 8, no later start, the gap ended cleanly, INCOMPLETE (stopped)" "[ $RC = 8 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && ! grep -q 'server g13[0-9]*-B3 ' $O/summary.txt && grep -q '^STOPPED: the priority rule stopped the gap' $O/decision.txt && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('*'stopped'* ]] && grep -q '^STOPPED by the priority rule' $O/result.txt"

setup; run KE MOCK_KERR_AT=-P1
chk "KE a kernel error during screen P1: the engine killed at once, exit 3, no later start, the daily back, the marker kept" "[ $RC = 3 ] && ! alive $M/kerr-engine.pid && [ -e $M/out-KE/kerr.seen ] && ! grep -q 'server g13[0-9]*-P2 ' $O/summary.txt && [ \$(nend) = 1 ] && [ -s $M/kernel_error ] && grep -q '^KERNEL ERROR during the gap - stopped at once, the daily back on 8080; kwatch not cleared' $O/result.txt"
setup; run KX MOCK_KERR_E7=p213a
chk "KX a kernel error during exact7 p213a: its engine killed at once, exit 3, no long40 / screen, INCOMPLETE" "[ $RC = 3 ] && ! alive $M/kerr-engine.pid && ! grep -q '3 KL: pf_yardstick' $O/summary.txt && ! grep -q 'server g13' $O/summary.txt && [ \$(nend) = 1 ] && [[ \"\$(V)\" == 'BASELINE INCOMPLETE ('* ]]"
setup; run N MOCK_ENGINES_LEFT=1
chk "N engines left after 8080 stopped: exit 5, the gap closed, nothing measured" "[ $RC = 5 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && grep -q '^not run: engines still running after 8080 stopped' $O/result.txt && ! grep -q 'exact7 g13' $O/summary.txt"
setup; run K2 MOCK_END_FAIL=1
chk "K2 port_gap4.sh end fails: exit 4, an alert, the decision written" "[ $RC = 4 ] && grep -q '^port_gap4.sh end FAILED' $O/result.txt && [ -s $O/decision.txt ] && grep -q 'would alert: v0.2.13 baseline gate: 8080 not back' $O/summary.txt"
setup; bgrun T $O/summary.txt 'server g13[0-9]+-B1 ' MOCK_SLEEP_AT=-B1 MOCK_SLEEP_S=4
chk "T a signal during a server run: exit 7, INTERRUPTED, the gap may still be open, no end, 8080's state named" "[ $RC = 7 ] && grep -q '^INTERRUPTED: the gap may still be open (tmp/port-gap.lockpid): close it with work/r22/port_gap4.sh end; 8080 is' $O/result.txt && [ \$(nend) = 0 ] && [ ! -e $M/driver.pid ]"
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
  env GTS_DRIVER=$ST/drv.sh GTS_BUILD_UNIT=g13-mock-no-such-unit GTS_LOCKPID=$M/lockpid GTS_LOG=$ST/starter.log \
      GTS_COPIES=$ST/copies GTS_RESULT=$ST/result.txt GTS_POLL_S=1 GTS_RETRY_S=1 GTS_SETTLE_S=0 GTS_NOTIFY=$ST/notify.sh \
      "$@" timeout 120 bash $GD/gate-start.sh > $ST/$n.out 2>&1; RC=$?
  cp $ST/starter.log $ST/$n.log 2> /dev/null
  echo "--- starter $n: rc $RC"
}
ready() { echo "reviewed by mock: sha256 $(sha $ST/drv.sh), rules $(sha $GD/gate0213_rules.py), mkcfg $(sha $GD/make_configs0213.py), switch $(sha $WS/work/r23/switch-gap/switch_rules.py), ru $(sha $WS/work/r23/port0211_rules.py), g17 $(sha $WS/work/r22/g17_rules.py), single $(sha $WS/configs/P0213x-single.json), starter $(sha $GD/gate-start.sh)" > $ST/drv.sh.ready; }
setup; rm -f $ST/drv.sh.ready; srun S1 busy1
chk "S1 no .ready -> exit 6, an alert, no try" "[ $RC = 6 ] && grep -q 'v0.2.13 baseline gate not started' $ST/notify.log && [ ! -e $ST/count ]"
setup; ready; sed -i 's/, ru [0-9a-f]*//' $ST/drv.sh.ready; srun S1b busy1
chk "S1b a .ready without port0211_rules.py's sha (rules' still there) -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup; ready; sed -i 's/, single [0-9a-f]*//' $ST/drv.sh.ready; srun S1c busy1
chk "S1c a .ready without P0213x-single.json's sha -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup; ready; sed -i 's/, starter [0-9a-f]*//' $ST/drv.sh.ready; srun S1d busy1
chk "S1d a .ready without the starter's own sha -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup; ready; sleep 600 > /dev/null 2>&1 < /dev/null & SP=$!; echo $SP > $M/lockpid; ( sleep 3; kill $SP; rm -f $M/lockpid ) & srun S2 busy1
chk "S2 waited for the open gap to close, busy once, then done: 2 tries, exit 0" "[ $RC = 0 ] && [ \$(cat $ST/count) = 2 ] && grep -q 'a gap open: yes' $ST/S2.log && [ \$(ls $ST/copies | wc -l) = 2 ]"
setup; ready; srun S3 hold
chk "S3 the priority hold is final: 1 try, exit 8" "[ $RC = 8 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'priority rule (final' $ST/S3.log"
setup; ready; srun S4 busy GTS_RETRY_FOR_S=4
chk "S4 busy past the retry window: exit 1, an alert, more than 1 try" "[ $RC = 1 ] && [ \$(cat $ST/count) -ge 2 ] && grep -q 'stayed busy' $ST/notify.log"
setup; ready; srun S5 noresult
chk "S5 the driver ended without a result line: exit 3, an alert, no retry" "[ $RC = 3 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'without a result' $ST/notify.log"
setup; ready; srun S7 engines
chk "S7 engines left after 8080 stopped (exit 5): an alert, no retry" "[ $RC = 5 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'v0.2.13 baseline gate not run' $ST/notify.log"
setup; ready; srun S8 other
chk "S8 another driver instance (exit 9): an alert, no retry" "[ $RC = 9 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'another baseline-gate driver is running' $ST/notify.log"
setup; ready; srun S9 busy1 GTS_TEST_CORRUPT_SNAPSHOT=1
chk "S9 a snapshot that is not the reviewed file: exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ] && grep -q 'snapshot is not the reviewed file' $ST/notify.log"
setup; ready; echo "edited" >> $ST/drv.sh; srun S6 busy1
chk "S6 a driver edited after its review -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup

echo "--- A decision.txt (first 12 lines, cut)"; head -12 $M/out-A/decision.txt | cut -c1-260
echo "--- A result.txt"; cut -c1-400 $M/out-A/result.txt
echo "gap-mock-test: $NCHK checks, $([ $F = 0 ] && echo 'ALL CHECKS PASSED' || echo 'FAILED')"
exit $F
