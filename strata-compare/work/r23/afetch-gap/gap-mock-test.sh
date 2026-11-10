#!/bin/bash
# gap-mock-test.sh - runs gap-afetch.sh --mock against stubs under work/r23/afetch-gap/scratch/mock, and the starter
# afetch-after-shape.sh against a stub driver, and checks their outputs (the shape gap's gap-mock-test.sh form).
# Every tool the driver calls is a stub there (with_server.sh, exact7.sh, kcheck.sh, guard.py, srv.sh, port_gap4.sh,
# abarm.sh, pf_yardstick.py, bp90_client.py, basalt_fix_rules.py's br, sq.py, sq_client.py); the driver's mock mode skips
# the real preflight, never kills a process, never queries the GPU and writes no NOTES.md / alert / ntfy. afetch_rules.py
# runs for real (its decide on the stubs' synthetic data: Basalt-like decode records, the stored port-0211 screen with
# its engine logs as every arm's screen, F1 / F2's decode scaled). Nothing outside scratch/mock is written (the stored
# screen files, the configs and the spec are only read); nothing real runs. Exit 0 = every check passed.
#   scenarios: U a bad argument; A a full run (the frozen switches tol1 / screen / vf-first: F1 CANDIDATE, F2 NO GAIN,
#   quality PASS); B exact7 6/7; C / C2 a read-back mismatch (vf-first: no speed, no sampled arm; speed-first: speed, then
#   no served arm); D / D2 / O the priority hold, an undated override (still held), a dated override (runs); E the
#   priority rule after the long40 run; F / F2 / F3 the shape gap's result lines; G another gap open; I a second instance;
#   H / H2 short deadlines (vf-first / speed-first); K a kernel check failing (left OPEN); K2 port_gap4.sh end failing; L a
#   test server left behind (voided); N nvidia-smi hanging; X engines left after 8080 stopped; R sq.py verify crashing;
#   S no R1 samples; W the watchdog; T / T2 a signal during a server run / during port_gap4.sh end; (review 2) X2 8080's
#   stopping engine left running (named, never killed: exit 5); LE / E7L this gap's leftover engine after a server run /
#   after exact7 (stopped); KE / KE2 a kernel error during a run (stopped at once, P028x back / not back); VR / FV the
#   read-back start's one retry; FS a foreign GPU user during X1 (void); HF / HO another's / this gap's hold; NS no watch
#   state; T3 a signal inside port_gap4.sh begin (8080's engine never touched);
#   the starter: S1 / S1b no or an incomplete .ready, S2 / S2b waiting for the shape gap, S3 the priority hold, S4 busy past
#   6 h, S5 no result line, S6 an edited driver, S7 engines left (exit 5), S8 another instance (exit 9), S9 a snapshot that
#   is not the reviewed file.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; AG=$WS/work/r23/afetch-gap; M=$AG/scratch/mock
P=$WS/.venv/bin/python; PY="$P -I -B"
SRC=$WS/results/r23/port-0211/gap/speed
rm -rf $M; mkdir -p $M/bin $M/lib $M/kr $M/b90 $M/fr $M/sq $M/y16 $M/logs $M/starter
# ---------------------------------------------------------------- the stubs
cat > $M/bin/mockeng.py <<'EOF'
# mockeng.py (gap-mock-test.sh only): the stub engine's log lines and the stub clients' records
import json, os, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
SRC = Path("/home/USER/ai-speed-testing/strata-compare/results/r23/port-0211/gap/speed")
SHA = {"engine-r23afetch": "153ce47d3ef0", "engine-r22p028x": "f4c4f654fb24"}
D0 = {1: {"conv": 140.1, "struct": 225.3, "prose": 129.1}, 2: {"conv": 139.6, "struct": 224.0, "prose": 128.4},
      3: {"conv": 140.6, "struct": 226.1, "prose": 129.8}}
def factor(arm):
    return float(os.environ.get(f"MOCK_DEC_{arm}", {"F1": "1.04", "F2": "1.004"}.get(arm, "1.0")))
def fetch_mode():
    try:
        return json.loads((M / "engine-env.json").read_text())["procs"][0]["env"].get("STRATA_ADAPT_FETCH", "")
    except (OSError, ValueError, KeyError, IndexError):
        return ""
def req_lines(n, fe, gen=1000, ms=7000):
    out = []
    for i in range(n):
        out.append(f"strata serve: prompt 38 tokens = 0 reused + 38 read in 120 ms (316.7 tok/s), {gen} generated in {ms} ms "
                   f"({1000 * gen / ms:.1f} tok/s), drafts accepted 600 of 1100, 0 checkpoints, 400 windows, 2.75 drafts per window")
        if fe:
            adm = 300 if fe == "1" else 500
            out.append(f"strata serve: fetch: {adm} admissions in 400 windows ({adm / 400:.2f} per window)")
        out.append("strata serve: decode expert cache hit rate: 75.0% (60000 hits / 80000 lookups); 25000 more read by the GPU over "
                   "PCIe or from another GPU (23.8% of all 105000 routed)")
        out.append("strata serve: CUDA1: 18000 expert entries, 92 active layer launches, 7.4 MiB returned in this request")
    return "".join(x + "\n" for x in out)
def append(elog, text):
    with open(elog, "a") as f:
        f.write(text)
def prio_find():
    (M / "state.json").write_text(json.dumps({"repos": {"unsloth/Qwen4-Flash-GGUF": {"kind": "Flash", "access": {"private": False,
                                  "gated": False}, "weights": {"Qwen4-Flash-Q4_K_M.gguf": 1}, "first_seen": "mock"}}, "polls": 9,
                                  "last_poll": "mock"}))
cmd = sys.argv[1]
if cmd == "start":                      # start CFG ELOG: the engine's start lines + the fake /proc env for the env checks
    cfg = json.loads(Path(sys.argv[2]).read_text())
    env = dict(cfg.get("env", {}))
    sha = next((v for k, v in SHA.items() if k in cfg["exe"]), "?")
    (M / "engine-env.json").write_text(json.dumps({"procs": [{"pid": 4242, "env": env, "sha12": sha}]}))
    fe = env.get("STRATA_ADAPT_FETCH", "")
    t = "strata generate: memory guard: mock\nstrata mtp: EXACT speculative sampling on (STRATA_SPEC_EXACT): mock\n"
    if fe:
        t += (f"strata serve: STRATA_ADAPT_FETCH={fe}: the PCIe share takes each layer's most-routed misses and admits those "
              f"routed >= 2.00 and 0.50 more than a resident one{'; the tier own copies are off' if fe == '2' else ''}\n")
    append(sys.argv[3], t)
elif cmd == "bp90":                     # bp90 LABEL PASS OUT: Basalt's decode fixtures, the arm from the label
    lab, k, out = sys.argv[2], int(sys.argv[3]), sys.argv[4]
    arm = lab.split("-")[-3]
    f = factor(arm)
    with open(out, "w") as fo:
        for t in ("conv", "struct", "prose"):
            fo.write(json.dumps({"label": lab, "pass": k, "test": t, "decode_tps": round(D0[k][t] * f, 2), "prompt_tps": 120.0}) + "\n")
    append(os.environ["ELOG"], req_lines(3, fetch_mode()))
    print(f"{lab} pass {k} conv: 1000 tokens (stop), {D0[k]['conv'] * f:.1f} tok/s decode")
elif cmd == "screen":                   # screen R N: the stored port-0211 screen pass as ARM's, decode scaled
    r, n = Path(sys.argv[2]), sys.argv[3]
    arm, k = n[:-1], n[-1]
    f = factor(arm)
    for s in "nar":
        (r / f"{n}{s}.englog").write_text((SRC / f"B{k}{s}.englog").read_text())
        recs = [json.loads(x) for x in (SRC / f"B{k}{s}.jsonl").read_text().splitlines() if x.strip()]
        for x in recs:
            x["decode_tps"] = round(x["decode_tps"] * f, 2)
        (r / f"{n}{s}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs))
        append(os.environ["ELOG"], req_lines(len(recs), fetch_mode()))
    (r / f"{n}.startlog").write_text("mock\n")
elif cmd == "sqclient":                 # sqclient OUTDIR: the sampled arm's records and its start's engine log
    out = Path(sys.argv[2]); arm = os.environ["SQ_ARM"]; out.mkdir(parents=True, exist_ok=True)
    n = {"R1": 32, "X1": 32, "X2": 32, "R2": 16, "VF": 8}[arm]
    append(os.environ["ELOG"], req_lines(n, fetch_mode(), gen=512, ms=4000))
    (out / "sampled.jsonl").write_text("".join(json.dumps({"name": f"{arm}-{i}", "finish": "length"}) + "\n" for i in range(n)))
    eb = int(os.environ.get("SQ_ELOG_BASE") or 0)
    with open(os.environ["ELOG"], "rb") as fi:
        fi.seek(eb)
        (out / "engine.out").write_bytes(fi.read())
    (out / "server.out").write_text("mock server log\n")
    print(f"sampled {arm}: {n} of {n} requests answered")
elif cmd == "prio":
    prio_find()
EOF
cat > $M/lib/with_server.sh <<'EOF'
#!/bin/bash
# mock with_server.sh LABEL CFG -- CMD: the engine's start lines into the config's log, the fake env, then CMD with $ELOG
M=$(dirname $(dirname $(readlink -f $0))); P=/home/USER/ai-speed-testing/strata-compare/.venv/bin/python
L=$1 CFG=$2; shift 3
export ELOG=$($P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" $CFG)
mkdir -p $(dirname $ELOG); touch $ELOG
echo "=== mock $L start ($CFG)"
[ -n "${MOCK_FAIL_AT:-}" ] && [[ $L == *"$MOCK_FAIL_AT"* ]] && { echo "server exited (mock)"; exit 1; }
[ -n "${MOCK_FAIL_ONCE_AT:-}" ] && [[ $L == *"$MOCK_FAIL_ONCE_AT"* ]] && [ ! -e $M/failed-once ] && { touch $M/failed-once; echo "server exited (mock, once)"; exit 1; }
fake() { $M/engines/$1/afmock-eng 600 > /dev/null 2>&1 < /dev/null & echo $! >> $M/fake.pids; echo $!; }   # a fake engine (never named strata*)
$P -I -B $M/bin/mockeng.py start $CFG $ELOG
echo "server ready (mock: guard pid 1, server pid 2) load_time_s 1.0"
echo "engine pid 4242 pinned/locked: mock"
[ -n "${MOCK_SLEEP_AT:-}" ] && [[ $L == *"$MOCK_SLEEP_AT"* ]] && sleep ${MOCK_SLEEP_S:-4}
if [ -n "${MOCK_FOREIGN_AT:-}" ] && [[ $L == *"$MOCK_FOREIGN_AT"* ]] && [ ! -e $M/foreign-done ]; then   # a foreign GPU user during the run (once; nvidia-smi lists it)
  touch $M/foreign-done; sleep 30 > /dev/null 2>&1 < /dev/null & echo $! > $M/foreign.pid; touch $M/foreign-on; sleep 1.2; rm -f $M/foreign-on; kill $(cat $M/foreign.pid)
fi
if [ -n "${MOCK_KERR_AT:-}" ] && [[ $L == *"$MOCK_KERR_AT"* ]]; then   # a kernel error during the run: kwatch's marker, an engine to kill
  fake engine-r23afetch > $M/kerr-engine.pid; echo "Xid 79 (mock): GPU has fallen off the bus" > $M/kernel_error; sleep 1.2
fi
bash -c "$*"
[ -n "${MOCK_LEFTOVER_AT:-}" ] && [[ $L == *"$MOCK_LEFTOVER_AT"* ]] && touch $M/leftover   # (its server "survives" the stop)
[ -n "${MOCK_ENGINE_LEFT_AT:-}" ] && [[ $L == *"$MOCK_ENGINE_LEFT_AT"* ]] && fake engine-r23afetch > $M/left-engine.pid   # (its engine survives)
echo "=== mock $L done"
EOF
cat > $M/lib/exact7.sh <<'EOF'
#!/bin/bash
# mock exact7.sh LABEL CFG (PIN_CACHE, REF): MOCK_E7 of 7 identical (default 7), slots MATCHED
M=$(dirname $(dirname $(readlink -f $0))); L=$1
echo "$L-x-math  out a46e2e9f (${REF:-?} a46e2e9f) =  ms/round 12.0 (mock, pin ${PIN_CACHE:-?})"
echo "exact7 $L: ${MOCK_E7:-7}/7 identical to ${REF:-?}"
echo "exact7-slots $L: 3238+3300 slots (5080 + 4060 Ti); ${REF:-?}: 3238+3300 -> MATCHED"
[ "${MOCK_PRIO_AT:-}" = e7 ] && /home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B $M/bin/mockeng.py prio
if [ "${MOCK_E7_LEFTOVER:-0}" = 1 ]; then $M/engines/engine-r23afetch/afmock-eng 600 > /dev/null 2>&1 < /dev/null & echo $! >> $M/fake.pids; echo $! > $M/e7-engine.pid; fi
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
[ -e $M/kernel_error ] && { echo "mock KCHECK FAIL $1: kernel error seen: $(cat $M/kernel_error)"; exit 1; }
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
         [ -n "${MOCK_BEGIN_SLEEP:-}" ] && { sleep 600 > /dev/null 2>&1 < /dev/null & echo $! > $M/lockpid; }
         if [ "${MOCK_OLD_ENGINE:-0}" = 1 ]; then   # 8080's stop left its engine running (it has P's binary)
           $M/engines/engine-r22p028x/afmock-eng 600 > /dev/null 2>&1 < /dev/null & echo $! >> $M/fake.pids; echo $! > $M/old-engine.pid
         fi
         [ -n "${MOCK_BEGIN_SLEEP:-}" ] && sleep $MOCK_BEGIN_SLEEP   # (begin still waiting, its lock taken: a signal now)
         [ -s $M/lockpid ] || { sleep 600 > /dev/null 2>&1 < /dev/null & echo $! > $M/lockpid; }; echo "mock port_gap4: gap open";;
  end) echo "end" >> $M/pg4.log; [ -n "${MOCK_END_SLEEP:-}" ] && sleep $MOCK_END_SLEEP
       [ "${MOCK_END_FAIL:-0}" = 1 ] && { echo "mock port_gap4: P021 did not start"; exit 1; }
       kill $(cat $M/lockpid) 2> /dev/null; rm -f $M/lockpid $M/hold; echo "mock port_gap4: served build back";;
esac
EOF
cat > $M/kr/abarm.sh <<'EOF'
#!/bin/bash
# mock abarm.sh URL OFF0 OUTDIR NAME SPEC...: the stored port-0211 screen pass as NAME's (mockeng.py screen)
M=$(dirname $(dirname $(readlink -f $0)))
/home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B $M/bin/mockeng.py screen $3 $4
echo "mock abarm $4: 9 workloads"
EOF
cat > $M/kr/pf_yardstick.py <<'EOF'
# mock pf_yardstick.py run CFG OUTDIR --set long40: gap 16's stored files (the mock copy), one differing with MOCK_PFY_DIFF=1
import os, shutil, subprocess, sys
from pathlib import Path
M = Path(__file__).resolve().parents[1]
out = Path(sys.argv[3])
shutil.copytree(M / "y16", out)
if os.environ.get("MOCK_PFY_DIFF") == "1":
    (out / "first.007").write_bytes(b"different")
print("40 prompts, 40 logit rows (mock)")
if os.environ.get("MOCK_PRIO_AT") == "pfy":
    subprocess.call([sys.executable, "-I", "-B", str(M / "bin/mockeng.py"), "prio"])
EOF
cat > $M/b90/bp90_client.py <<'EOF'
# mock bp90_client.py URL --label L --sets decode --passes 1 --first-pass K --tree T --out OUT
import subprocess, sys
from pathlib import Path
a = sys.argv
M = Path(__file__).resolve().parents[1]
v = lambda k: a[a.index(k) + 1]
sys.exit(subprocess.call([sys.executable, "-I", "-B", str(M / "bin/mockeng.py"), "bp90", v("--label"), v("--first-pass"), v("--out")]))
EOF
cat > $M/fr/basalt_fix_rules.py <<'EOF'
# mock basalt_fix_rules.py br envcheck | envcli | e7gate | same (gates in basalt_rules' form)
import json, os, re, sys, time
from pathlib import Path
M = Path(__file__).resolve().parents[1]
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
cmd = a[0]
if cmd == "envcheck":
    cfg = json.loads(Path(a[2]).read_text()); env = json.loads((M / "engine-env.json").read_text())["procs"][0]["env"]
    ok = env == cfg.get("env", {})
    print("engine pid 4242: mock; " + ("ENV CHECK OK" if ok else "ENV CHECK FAILED"))
    gate("PASS" if ok else "FAIL", "mock envcheck")
    sys.exit(0 if ok else 1)
if cmd == "envcli":
    job = int(opt("--job"))
    while alive(job):
        time.sleep(0.1)
    print(f"ENV CHECK OK: 1 engine start(s) ({opt('--mode')}), mock")
    gate("PASS", f"mock envcli {opt('--mode')}")
    sys.exit(0)
if cmd == "e7gate":
    s, lab = Path(a[1]).read_text(), a[2]
    m = re.findall(rf"^exact7 {re.escape(lab)}: (\d)/7 identical", s, re.M)
    sl = re.findall(rf"^exact7-slots {re.escape(lab)}: .*-> (MATCHED|DIFFER)", s, re.M)
    n, sl = (int(m[-1]) if m else None), (sl[-1] if sl else None)
    ok = n == 7 and sl == "MATCHED"
    print(f"exact7 {lab}: {n}/7, slots {sl} -> {'PASS' if ok else 'FAIL'}")
    gate("PASS" if ok else ("FAIL" if n is not None else "MISSING"), f"exact7 {lab}: {n}/7, slots {sl}")
    sys.exit(0)
if cmd == "same":
    da, db = Path(a[1]), Path(a[2])
    fa = sorted(p.name for p in da.glob("first.*")) if da.is_dir() else []
    nd = sum(1 for f in fa if (da / f).read_bytes() != (db / f).read_bytes())
    ok = len(fa) == 40 and nd == 0
    print(f"same {da.name}: {nd} of {len(fa)} differ -> {'PASS' if ok else 'FAIL'}")
    gate("PASS" if ok else "FAIL", f"{nd} of {len(fa)} first-token logit files differ (mock)")
    sys.exit(0)
sys.exit(2)
EOF
cat > $M/sq/sq.py <<'EOF'
# mock sq.py: selftest | selftest-real | derive | rule | envcheck | verify | ids | score | envwatch | decide
import json, os, sys, time
from pathlib import Path
M = Path(__file__).resolve().parents[1]
WS = "/home/USER/ai-speed-testing/strata-compare"
a = sys.argv[1:]
cmd = a[0]
if cmd == "selftest":
    print("mock\nSELFTEST OK"); sys.exit(0)
if cmd == "selftest-real":
    print("mock\nSELFTEST-REAL OK"); sys.exit(0)
if cmd == "derive":
    spec, o = json.loads(Path(a[1]).read_text()), Path(a[2])
    (o / "cfg").mkdir(parents=True, exist_ok=True); (o / "logs").mkdir(exist_ok=True)
    fe = {"R1": {}, "R2": {}, "X1": {"STRATA_ADAPT_FETCH": "1"}, "X2": {"STRATA_ADAPT_FETCH": "2"},
          "VF": {"STRATA_ADAPT_FETCH": "2", "STRATA_ADAPT_FETCH_VERIFY": "1", "STRATA_ADAPT_CHECKRES": "1"}}
    for n, e in fe.items():
        exe = f"{WS}/engine-r23afetch/strata" if e else f"{WS}/engine-r22p028x/strata"
        (o / "cfg" / f"{n}.json").write_text(json.dumps({"exe": exe, "log": str(o / "logs" / f"engine-{n}.log"), "args": [],
                                                          "env": {"STRATA_DEBUG": "1", **e}}))
    (o / "cfg" / "scorer.json").write_text(json.dumps({"exe": f"{WS}/engine-r22p028x/strata", "log": str(o / "logs/engine-scorer.log")}))
    (o / "spec.json").write_text(json.dumps(dict(spec, resolved={"mock": True})))
    print(f"derive OK: 5 arm configs + the scorer in {o}/cfg (mock)"); sys.exit(0)
if cmd == "rule":
    print("mock rule text of " + json.loads(Path(a[1]).read_text())["name"]); sys.exit(0)
if cmd == "envcheck":
    Path(a[1], f"envcheck-{a[2]}.txt").write_text("engine pid 4242: mock\nENV CHECK OK\n"); print("ENV CHECK OK"); sys.exit(0)
if cmd == "verify":
    o, arm = Path(a[1]), a[2]
    if os.environ.get("MOCK_VF") == "CRASH":
        print("Traceback (mock): verify crashed before writing verify-VF.json"); sys.exit(1)
    if not (o / arm / "engine.out").exists():
        v = {"verdict": "NOT DECIDED", "why": "no engine.out (the verify start's engine log)"}
        (o / f"verify-{arm}.json").write_text(json.dumps(v)); print(f"read-back {arm}: NOT DECIDED - {v['why']}"); sys.exit(2)
    bad = os.environ.get("MOCK_VF") == "FAIL"
    v = {"verdict": "FAIL" if bad else "PASS", "why": "read-back mismatch: 3 mismatch line(s)" if bad else
         "412 admitted slots read back, 0 differ, no mismatch line", "read_back": 412, "differ": 3 if bad else 0,
         "mismatch_lines": 3 if bad else 0}
    (o / f"verify-{arm}.json").write_text(json.dumps(v)); print(f"read-back {arm}: {v['verdict']} - {v['why']}")
    sys.exit(1 if bad else 0)
if cmd == "ids":
    for arm in a[2:]:
        print(f"ids {arm}: 32 of 32 samples valid -> {a[1]}/{arm}/score-ids.json (mock)")
    sys.exit(0)
if cmd == "score":
    print(f"scorer engine: mock\nscored 112 of 112 samples (65400 positions) in 1 s"); sys.exit(0)
if cmd == "envwatch":
    job = int(a[1])
    while Path(f"/proc/{job}").exists() and "zombie" not in Path(f"/proc/{job}/status").read_text():
        time.sleep(0.1)
    print("engine pid 4243 -> ENV OK\nENV CHECK OK: 1 scorer engine start(s)"); sys.exit(0)
if cmd == "decide":
    o = Path(a[1]); vf = json.loads((o / "verify-VF.json").read_text()) if (o / "verify-VF.json").exists() else {"verdict": "NOT DECIDED"}
    have = all((o / x / "sampled.jsonl").exists() for x in ("R1", "X1", "X2", "R2"))
    cand = {x: ({"verdict": os.environ.get(f"MOCK_SQ_{x}", "PASS"), "why": "D2 0.8 <= band 11.345 (mock)"} if have else
                {"verdict": "NOT DECIDED", "why": "R1 missing"}) for x in ("X1", "X2")}
    ov = {}
    for x, c in cand.items():
        o_ = "FAIL" if "FAIL" in (c["verdict"], vf["verdict"]) else ("PASS" if c["verdict"] == vf["verdict"] == "PASS" else "NOT DECIDED")
        ov[x] = {"verdict": o_, "sampled": c["verdict"], "read_back": {"VF": vf["verdict"]}}
    vs = [v["verdict"] for v in ov.values()]
    rc = 1 if "FAIL" in vs else (0 if all(v == "PASS" for v in vs) else 2)
    res = {"spec": "mock", "verdict": {0: "ALL PASS", 1: "FAIL", 2: "NOT DECIDED"}[rc], "candidates": cand, "overall": ov, "flags": []}
    (o / "decision.json").write_text(json.dumps(res)); (o / "decision.txt").write_text(json.dumps(res) + "\n")
    print(f"decision {res['verdict']}: " + "; ".join(f"{x} {v['verdict']}" for x, v in ov.items())); sys.exit(rc)
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
cat > $M/bin/nvidia-smi <<'EOF'
#!/bin/bash
# mock nvidia-smi: no compute process; the first MOCK_NVSMI_HANG calls hang (the driver's timeout must cut them)
M=$(dirname $(dirname $(readlink -f $0))); n=$(( $(cat $M/nvsmi.count 2> /dev/null || echo 0) + 1 )); echo $n > $M/nvsmi.count
[ $n -le ${MOCK_NVSMI_HANG:-0} ] && exec sleep 5
[ -e $M/foreign-on ] && echo "$(cat $M/foreign.pid), 1000"
exit 0
EOF
chmod +x $M/lib/* $M/kr/*.sh $M/bin/nvidia-smi
mkdir -p $M/engines/engine-r22p028x $M/engines/engine-r23afetch   # the fake engines: a copy of sleep, named afmock-eng
cp /bin/sleep $M/engines/engine-r22p028x/afmock-eng; cp /bin/sleep $M/engines/engine-r23afetch/afmock-eng
for i in $(seq -w 0 39); do printf 'logits %s\n' $i > $M/y16/first.0$i; done
echo '{"mock": true}' > $M/y16/index.json
CLEAR='{"repos": {"Qwen/Qwen4-Flash": {"kind": "Flash", "access": {"private": false, "gated": "manual"}, "weights": {"model-00001.safetensors": 1}}}, "polls": 3, "last_poll": "mock"}'

# ---------------------------------------------------------------- the driver scenarios
F=0
chk() { if eval "$2"; then echo "  ok   $1"; else echo "  FAIL $1"; F=1; fi; }
O=$M/out
setup() {   # setup: a clean mock state (the shape gap ran, the watch state CLEAR, no gap open, no hold, no hooks left)
  [ -s $M/lockpid ] && kill $(cat $M/lockpid) 2> /dev/null
  for fp in $(cat $M/fake.pids 2> /dev/null); do kill $fp 2> /dev/null; done
  rm -f $M/pg4.log $M/lockpid $M/hold $M/engine-env.json $M/leftover $M/nvsmi.count $M/wdg.log $M/afetch-priority-done $M/driver.pid
  rm -f $M/fake.pids $M/*-engine.pid $M/kernel_error $M/failed-once $M/foreign-on $M/foreign.pid $M/foreign-done
  rm -rf $M/logs $M/rb-cache $O; mkdir -p $M/logs   # ($O too: a background run's wait pattern must not match the last run's summary)
  echo "DONE (information only, nothing switched; 8080 down 41 min; kernel check after: ok): mock" > $M/shape-result.txt
  echo "$CLEAR" > $M/state.json
}
run() {   # run NAME [VAR=VALUE ...]: the driver in mock mode -> $M/NAME.out, rc in RC
  local n=$1; shift
  env "$@" timeout 600 bash $AG/gap-afetch.sh --mock > $M/$n.out 2>&1; RC=$?
  rm -rf $M/out-$n; cp -r $O $M/out-$n 2> /dev/null
  echo "--- scenario $n: driver rc $RC"
}
bgrun() {   # bgrun NAME WAITFILE PATTERN [VAR=VALUE ...]: the driver in the background; TERM once PATTERN shows in WAITFILE
  local n=$1 wf=$2 pat=$3 i; shift 3
  env "$@" bash $AG/gap-afetch.sh --mock > $M/$n.out 2>&1 & local dp=$!
  for i in $(seq 600); do grep -qE "$pat" $wf 2> /dev/null && break; sleep 0.1; done
  grep -qE "$pat" $wf 2> /dev/null || { echo "  FAIL $n: /$pat/ never showed in 60 s (the TERM is sent anyway)"; F=1; }
  kill -TERM $dp; wait $dp; RC=$?
  rm -rf $M/out-$n; cp -r $O $M/out-$n 2> /dev/null
  echo "--- scenario $n: driver rc $RC (TERM sent once /$pat/ was in $(basename $wf))"
}
alive() { [ -s "$1" ] && kill -0 "$(cat $1)" 2> /dev/null; }   # alive PIDFILE
nbeg() { local n; n=$(grep -c '^begin' $M/pg4.log 2> /dev/null); echo ${n:-0}; }   # (grep -c prints 0 and exits 1 on no match)
nend() { local n; n=$(grep -c '^end' $M/pg4.log 2> /dev/null); echo ${n:-0}; }
line_of() { grep -n -- "$2" $1 | head -1 | cut -d: -f1; }

# U: an unknown argument runs nothing - the check itself (the driver's lines up to it, run alone) and its place (the first command)
sed -n '1,/^case \${1:-} in/p' $AG/gap-afetch.sh > $M/argcheck.sh; echo 'echo PAST-THE-CHECK' >> $M/argcheck.sh
chk "U --bogus: exit 2, nothing after the check" "bash $M/argcheck.sh --bogus > $M/U.out 2>&1; [ \$? = 2 ] && ! grep -q PAST $M/U.out && grep -q 'nothing run' $M/U.out"
chk "U --mock / --dry-run / no argument pass the check" "bash $M/argcheck.sh --mock | grep -q PAST && bash $M/argcheck.sh --dry-run | grep -q PAST && bash $M/argcheck.sh | grep -q PAST"
chk "U the check is the driver's first command (only set / exec / WS= before it)" "[ -z \"\$(sed -n '1,/^case \${1:-} in/p' $AG/gap-afetch.sh | grep -vE '^#|^\$|^set -u -o pipefail\$|^exec 8>&- 9>&-|^WS=|^case ')\" ]"

setup; sleep 0 & wait $!; echo $! > $M/driver.pid   # (a stale pid file: a dead pid)
run A MOCK_SELFTEST=1
chk "A exit 0" "[ $RC = 0 ]"
chk "A result DONE" "grep -q '^DONE (measurements only, nothing switched' $O/result.txt"
chk "A a stale pid file is taken over; the pid file is gone at the exit" "[ ! -e $M/driver.pid ]"
chk "A port_gap4 begin once, end once" "[ \$(nbeg) = 1 ] && [ \$(nend) = 1 ]"
chk "A gap closed (no lock left, no hold)" "[ ! -e $M/lockpid ] && [ ! -e $M/hold ]"
chk "A the rules' selftest ran in the preflight" "grep -q 'afetch_rules selftest: 0 failure(s)' $O/summary.txt"
chk "A the switches as frozen (Karl 11-09): tol1, screen, vf-first" "grep -q 'the switches (frozen into rules.txt): B3_PROMPT_FORM=tol1 GAIN_FORM=screen ORDER_FORM=vf-first' $O/summary.txt && grep -q '^rules forms (frozen): B3_PROMPT_FORM tol1, GAIN_FORM screen, ORDER_FORM vf-first' $O/decision.txt && grep -q 'ORDER_FORM = vf-first' $O/rules.txt"
chk "A sampled rule.txt written before the gap opened" "[ -s $O/sampled/rule.txt ] && [ \$(line_of $O/summary.txt 'the sampled rule frozen') -lt \$(line_of $O/summary.txt 'mock port_gap4: gap open') ]"
chk "A rules.txt frozen with the files' shas (this one's own included)" "grep -q 'work/r23/afetch-gap/afetch_rules.py ' $O/rules.txt && grep -q 'sq_client.py ' $O/rules.txt"
chk "A vf-first: the read-back start after long40 and before the first speed start" "[ \$(line_of $O/summary.txt 'pf_yardstick long40') -lt \$(line_of $O/summary.txt 'sampled VF: server') ] && [ \$(line_of $O/summary.txt 'sampled VF: server') -lt \$(line_of $O/summary.txt 'server r23af[0-9]*-bpP-1') ]"
chk "A build vs switch PASS" "grep -q '^BUILD VS SWITCH (the fetch build with the switch unset = P028x bitwise): PASS' $O/decision.txt"
chk "A F1 PROPOSAL, speed CANDIDATE (the screen decode geomean, its primary target)" "grep -q '^F1 (STRATA_ADAPT_FETCH=1): PROPOSAL for Karl' $O/decision.txt && grep -q '  speed vs P: CANDIDATE - decode targets (GAIN_FORM screen)' $O/decision.txt"
chk "A F2 QUALITY PASS, NO SPEED GAIN" "grep -q '^F2 (STRATA_ADAPT_FETCH=2): QUALITY PASS, NO SPEED GAIN' $O/decision.txt"
chk "A 9 B2 files + 27 screen files, every start's env / fenv / line gates PASS, no void" "[ \$(ls $O/bp90/*-decode-*.jsonl | wc -l) = 9 ] && [ \$(ls $O/speed/*[0-9][nar].jsonl | wc -l) = 27 ] && [ \$(grep -cE '^(env|fenv|line)_(P|F1|F2)_(bp[123]decode|scr[123]) PASS' $O/gates.txt) = 54 ] && ! grep -q '^void_' $O/gates.txt"
chk "A the Latin square order of B2 pass 2 (F2 P F1)" "grep -E 'server r23af[0-9]+-bp(P|F1|F2)-2 ' $O/summary.txt | sed -E 's/.*-bp(P|F1|F2)-2 .*/\1/' | tr '\n' ' ' | grep -qx 'F2 P F1 '"
chk "A sampled arms in STEPS order VF R1 X1 X2 R2, VF once" "grep -oE 'sampled (VF|R1|X1|X2|R2): server' $O/summary.txt | awk '{print \$2}' | tr -d ':' | tr '\n' ' ' | grep -qx 'VF R1 X1 X2 R2 '"
chk "A the read-back verdict from verify-VF.json, the scorer's env checked, sq.py decide ALL PASS" "grep -q '^readback_VF PASS try 1: verify-VF.json PASS' $O/gates.txt && grep -q '^env_sqscore PASS' $O/gates.txt && grep -q '^sampled_decide INFO exit 0' $O/gates.txt"
chk "A quality PASS + read-back PASS listed for both" "[ \$(grep -c '  QUALITY (sampled AND read-back): PASS' $O/decision.txt) = 2 ] && [ \$(grep -c '  read-back (VF = X2 + STRATA_ADAPT_FETCH_VERIFY=1 + STRATA_ADAPT_CHECKRES=1): PASS' $O/decision.txt) = 2 ]"
chk "A admissions per window: F1 0.750, F2 1.250, P none" "grep -q '  B2: 9 requests, admissions per window 0.750' $O/decision.txt && grep -q '  B2: 9 requests, admissions per window 1.250' $O/decision.txt && grep -q 'INFO P B2: 9 requests, admissions per window - (no fetch line)' $O/decision.txt"
chk "A placement split per arm" "[ \$(grep -c 'placement main 57.1 % / helper 17.1 % / PCIe 6.7 % / CPU 19.0 %' $O/decision.txt) -ge 6 ]"
chk "A the lock sweep before port_gap4.sh end" "[ \$(line_of $O/summary.txt 'lock sweep before the end') -lt \$(line_of $O/summary.txt 'port_gap4.sh end: P028x back') ]"
chk "A the port note beside the PROPOSAL" "grep -q 'carries to the v0.2.13 port' $O/decision.txt"
chk "A nothing written to NOTES.md / ntfy (mock)" "grep -q 'dry run / mock: would add to NOTES.md' $O/summary.txt && grep -q 'dry run / mock: would send the ntfy note' $O/summary.txt"
chk "A the engine logs went to scratch/mock/logs only" "[ -s $M/logs/engine-r23af-F1.log ] && [ ! -e $WS/logs/engine-r23af-F1.log ]"
chk "A no FLAG in the decision, no watchdog in the mock, no engine from before the gap" "! grep -q '^FLAG' $O/decision.txt && [ ! -e $M/wdg.log ] && ! grep -q 'running as the gap opened' $O/summary.txt"
chk "A the GPU watch ran (the mock's nvidia-smi was asked during the starts)" "[ \$(cat $M/nvsmi.count) -gt 30 ]"

setup; run B MOCK_E7=6
chk "B exit 0, build vs switch FAIL" "[ $RC = 0 ] && grep -q '^BUILD VS SWITCH .*: FAIL' $O/decision.txt"
chk "B no read-back, speed or sampled start" "[ -z \"\$(ls $O/bp90 $O/speed 2> /dev/null | grep -v ':' | grep .)\" ] && ! grep -q 'sampled VF: server' $O/summary.txt"
chk "B speed and sampled NOT RUN, FAIL (build vs switch FAIL), no port note" "[ \$(grep -c '  speed vs P: NOT RUN - build vs switch FAIL' $O/decision.txt) = 2 ] && grep -q '^F1 (STRATA_ADAPT_FETCH=1): FAIL (build vs switch FAIL)' $O/decision.txt && ! grep -q 'carries to the v0.2.13 port' $O/decision.txt"
chk "B gap opened and closed once" "[ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && [ ! -e $M/lockpid ]"

setup; run C MOCK_VF=FAIL
chk "C vf-first, a read-back mismatch: no speed start, no served sampled arm, exit 0" "[ $RC = 0 ] && [ ! -e $O/bp90/P-decode-1.jsonl ] && ! grep -qE 'sampled (R1|X1|X2|R2): server' $O/summary.txt"
chk "C speed NOT RUN with the reason, quality FAIL for both, sq.py decide still ran" "[ \$(grep -c '  speed vs P: NOT RUN - a read-back mismatch at VF' $O/decision.txt) = 2 ] && [ \$(grep -c '  QUALITY (sampled AND read-back): FAIL' $O/decision.txt) = 2 ] && grep -q '^sampled_decide INFO exit 1' $O/gates.txt"
setup; run C2 MOCK_VF=FAIL MOCK_ORDER_FORM=speed-first
chk "C2 speed-first: speed decided (F1 CANDIDATE), then VF's mismatch skips the served arms and the scorer" "[ $RC = 0 ] && grep -q '  speed vs P: CANDIDATE' $O/decision.txt && ! grep -qE 'sampled (R1|X1|X2|R2): server' $O/summary.txt && grep -q '^skip_sqarms INFO a read-back mismatch at VF' $O/gates.txt && ! grep -q '^env_sqscore' $O/gates.txt"
chk "C2 the mock order override is gated, proposals FAIL (quality)" "grep -q '^order_form INFO speed-first (mock override)' $O/gates.txt && [ \$(grep -cE '^F[12] .*: FAIL \(quality FAIL' $O/decision.txt) = 2 ]"

FIND='{"repos": {"unsloth/Qwen4-Flash-GGUF": {"kind": "Flash", "access": {"private": false, "gated": false}, "weights": {"a.gguf": 1}}}}'
setup; echo "$FIND" > $M/state.json; run D
chk "D exit 8 (HELD), no begin" "[ $RC = 8 ] && [ \$(nbeg) = 0 ] && grep -q '^HELD by the priority rule' $O/result.txt"
chk "D the alert (mock: logged)" "grep -q 'would alert: ADAPT_FETCH gap held' $O/summary.txt"
setup; echo "$FIND" > $M/state.json; echo "day-one work done" > $M/afetch-priority-done; run D2
chk "D2 an override without a dated first line is ignored: HELD" "[ $RC = 8 ] && [ \$(nbeg) = 0 ] && grep -q 'no dated reason line' $O/summary.txt"
setup; echo "$FIND" > $M/state.json; echo "2026-11-14: Karl: the Qwen4 day-one work is done" > $M/afetch-priority-done; run O_
chk "O the override (dated reason): the gap runs, exit 0, named in the summary, the decision and the result" "[ $RC = 0 ] && grep -q 'THE PRIORITY HOLD IS OVERRIDDEN' $O/summary.txt && grep -q '^PRIORITY OVERRIDE: ' $O/decision.txt && grep -q 'priority hold OVERRIDDEN (PRIORITY OVERRIDDEN' $O/result.txt"

setup; run E MOCK_PRIO_AT=pfy
chk "E exit 8, the gap ended cleanly (begin 1, end 1)" "[ $RC = 8 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && [ ! -e $M/lockpid ]"
chk "E stopped after the long40 run: no read-back, speed or sampled start" "[ ! -e $O/bp90/P-decode-1.jsonl ] && ! grep -q 'sampled VF: server' $O/summary.txt && grep -q '^priority FAIL before the read-back start' $O/gates.txt"
chk "E the decision lists the stop, build vs switch PASS" "grep -q '^STOPPED: the priority rule stopped the gap' $O/decision.txt && grep -q '^BUILD VS SWITCH .*: PASS' $O/decision.txt && grep -q '^STOPPED by the priority rule' $O/result.txt"

setup; rm -f $M/shape-result.txt; run F
chk "F exit 1 (busy: the shape gap first), no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q '^not started (busy): the v0.2.13 shape gap must run first' $O/result.txt"
for l in "not started (busy): another gap holds the test lock - nothing changed" "INTERRUPTED: the gap may still be open (tmp/port-gap.lockpid): close it; 8080 is listening" "not run: engines still running after 8080 stopped (nothing changed)" "port_gap4.sh end FAILED - 8080 and the research queue need a look" "kernel check FAILED inside the gap - the gap is left OPEN" "KERNEL ERROR during the gap - stopped at once, P028x back on 8080; kwatch not cleared"; do
  setup; echo "$l" > $M/shape-result.txt; run F2
  chk "F2 a shape result '${l:0:30}...' does not count (busy; only DONE does)" "[ $RC = 1 ] && grep -q 'shape gap must run first' $O/result.txt && [ \$(nbeg) = 0 ]"
done
setup; echo "phase 4 gap: another gap's work (since now)" > $M/hold; run HF
chk "HF the research queue held by someone else: busy, no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'research queue is held by someone else' $O/result.txt"
setup; echo "phase 4 gap: ADAPT_FETCH gap: an earlier attempt (since then)" > $M/hold; run HO
chk "HO this gap's own leftover hold does not block it" "[ $RC = 0 ] && grep -q '^DONE' $O/result.txt"
setup; rm -f $M/state.json; run NS
chk "NS no watch state file: busy (the priority rule cannot be checked), no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'the priority rule cannot be checked: PRIORITY UNKNOWN: .*state file .* is missing' $O/result.txt"

setup; sleep 600 > /dev/null 2>&1 < /dev/null & SP=$!; echo $SP > $M/lockpid; run G; kill $SP 2> /dev/null; rm -f $M/lockpid
chk "G exit 1 (busy: another gap), no begin" "[ $RC = 1 ] && [ \$(nbeg) = 0 ] && grep -q 'another gap holds the test lock' $O/result.txt"

setup; mkdir -p $O; echo keep > $O/marker; bash -c 'exec -a gap-afetch-fake sleep 600' > /dev/null 2>&1 < /dev/null & FP=$!; sleep 0.3; echo $FP > $M/driver.pid
run I; kill $FP 2> /dev/null
chk "I a second instance exits 9 and touches nothing (the output folder, the pid file, no begin)" "[ $RC = 9 ] && [ -s $M/out-I/marker ] && [ \"\$(cat $M/driver.pid)\" = $FP ] && [ \$(nbeg) = 0 ] && grep -q 'another gap-afetch.sh (pid $FP) is running' $M/I.out"
rm -f $M/driver.pid

setup; run H AF_MAX_MIN=40
chk "H vf-first, 40 min: VF runs, every speed start cut to keep the sampled rest (38 min), the sampled rest ran" "[ $RC = 0 ] && grep -q 'sampled VF: server' $O/summary.txt && grep -q '^skip_speed INFO the deadline cut 18 speed start(s)' $O/gates.txt && grep -q 'sampled R2: server' $O/summary.txt"
chk "H speed NOT RUN (its reason), quality PASS, proposal NOT DECIDED" "grep -q '  speed vs P: NOT RUN - the deadline cut 18' $O/decision.txt && grep -q '  QUALITY (sampled AND read-back): PASS' $O/decision.txt && grep -q '^F1 (STRATA_ADAPT_FETCH=1): NOT DECIDED (speed NOT RUN)' $O/decision.txt"
setup; run H2 AF_MAX_MIN=46 MOCK_ORDER_FORM=speed-first
chk "H2 speed-first, 46 min: the speed cut to keep the whole sampled part (45 min), which ran with VF first" "[ $RC = 0 ] && grep -q '^skip_speed INFO the deadline cut 18 speed start(s)' $O/gates.txt && grep -q 'sampled VF: server' $O/summary.txt && grep -q 'sampled R2: server' $O/summary.txt"

setup; run K MOCK_KFAIL_AT=bpF1-1
chk "K a kernel check fails after F1's first B2 start: stopped at once, exit 3, P028x back (begin 1, end 1), no later start" "[ $RC = 3 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && [ ! -e $M/lockpid ] && [ ! -e $O/bp90/F2-decode-1.jsonl ] && ! grep -q 'sampled R1: server' $O/summary.txt"
chk "K the result 'KERNEL ERROR during the gap - stopped at once, P028x back', the alert, a partial decision" "grep -q '^KERNEL ERROR during the gap - stopped at once, P028x back on 8080; kwatch not cleared' $O/result.txt && [ -s $O/decision.txt ] && grep -q 'would alert: ADAPT_FETCH gap stopped: kernel error' $O/summary.txt && [ \$(line_of $O/summary.txt 'lock sweep before the end') -lt \$(line_of $O/summary.txt 'mock port_gap4: served build back') ]"
setup; run KE MOCK_KERR_AT=bpF1-1
chk "KE a kernel error (kwatch's marker) during a run: the GPU watch kills this gap's engine at once, kerr.seen" "[ -e $M/out-KE/kerr.seen ] && ! alive $M/kerr-engine.pid"
chk "KE stopped at once: exit 3, no later start, P028x back, the marker NOT cleared" "[ $RC = 3 ] && [ ! -e $O/bp90/F2-decode-1.jsonl ] && [ \$(nend) = 1 ] && [ ! -e $M/lockpid ] && [ -s $M/kernel_error ] && grep -q '^KERNEL ERROR during the gap - stopped at once, P028x back on 8080; kwatch not cleared' $O/result.txt && grep -q 'Xid 79 (mock)' $O/summary.txt"
setup; run KE2 MOCK_KERR_AT=bpF1-1 MOCK_END_FAIL=1
chk "KE2 a kernel error and port_gap4.sh end failing: exit 3, '8080 NOT back', its alert" "[ $RC = 3 ] && grep -q '^KERNEL ERROR during the gap - stopped at once, 8080 NOT back' $O/result.txt && grep -q 'would alert: ADAPT_FETCH gap: kernel error, 8080 not back' $O/summary.txt"
setup; run K2 MOCK_END_FAIL=1
chk "K2 port_gap4.sh end fails: exit 4, an alert, the decision written" "[ $RC = 4 ] && grep -q '^port_gap4.sh end FAILED' $O/result.txt && grep -q 'would alert: ADAPT_FETCH gap: 8080 not back' $O/summary.txt && [ -s $O/decision.txt ]"

setup; run L MOCK_LEFTOVER_AT=bpF2-2
chk "L a run that left its test server behind: test_cleanup stops it, the start is voided and left out" "[ $RC = 0 ] && grep -q '^void_F2_bp2decode FAIL the run left the test server' $O/gates.txt && [ -e $O/bp90/void/F2-decode-2.jsonl ] && [ ! -e $O/bp90/F2-decode-2.jsonl ]"
chk "L F2 judged on its 2 other passes, the void flagged" "grep -q '^F2 (STRATA_ADAPT_FETCH=2): QUALITY PASS, NO SPEED GAIN' $O/decision.txt && grep -q 'conv: [0-9.]* vs [0-9.]* tok/s ([^)]*2/3 passes)' $O/decision.txt && grep -q '^FLAG start(s) voided' $O/decision.txt"

setup; run N MOCK_NVSMI_HANG=2
chk "N nvidia-smi hanging: cut at its timeout, taken as not clear: the first start (VF) not started" "[ $RC = 0 ] && grep -q '^foreign_sqVF FAIL not started: nvidia-smi did not answer within 1 s (taken as: not clear)' $O/gates.txt && grep -q 'read-back VF (try 1): NOT DECIDED' $O/summary.txt"
chk "N later starts ran (B2); the read-back tried once more (try 2 PASS) -> quality PASS" "[ -e $O/bp90/P-decode-1.jsonl ] && grep -q 'read-back VF (try 2): PASS' $O/summary.txt && [ \$(grep -c '  QUALITY (sampled AND read-back): PASS' $O/decision.txt) = 2 ]"

setup; run X2 MOCK_OLD_ENGINE=1
chk "X2 (M1) 8080's stopping engine still running (P's binary): exit 5, named as from before the gap, NEVER killed" "[ $RC = 5 ] && alive $M/old-engine.pid && grep -q 'from before the gap, left alone: [0-9]*(afmock-eng' $O/result.txt && grep -q 'running since before the gap - left alone' $O/summary.txt && [ \$(nend) = 1 ]"
setup; run LE MOCK_ENGINE_LEFT_AT=bpP-2
chk "LE an engine of this gap left after its run: stopped by test_cleanup, the start voided and left out" "[ $RC = 0 ] && ! alive $M/left-engine.pid && grep -q '^void_P_bp2decode FAIL the run left 1 engine process(es) behind' $O/gates.txt && [ -e $O/bp90/void/P-decode-2.jsonl ]"
setup; run E7L MOCK_E7_LEFTOVER=1
chk "E7L (m4) an exact7 engine of this gap left running: stopped after exact7, the gap goes on" "[ $RC = 0 ] && ! alive $M/e7-engine.pid && grep -q 'stopped 1 engine process(es) of this gap left after its run' $O/summary.txt && grep -q '^build_switch PASS' $O/gates.txt"
setup; run X MOCK_ENGINES_LEFT=1
chk "X engines still running after 8080 stopped: exit 5, the gap closed (begin 1, end 1), nothing measured" "[ $RC = 5 ] && [ \$(nbeg) = 1 ] && [ \$(nend) = 1 ] && grep -q '^not run: engines still running after 8080 stopped' $O/result.txt && ! grep -q 'exact7 r23af' $O/summary.txt"

setup; run R MOCK_VF=CRASH
chk "R sq.py verify crashing (exit 1, no verify-VF.json) is NOT a mismatch: tried once more (2 tries, no third), speed and the arms run" "[ $RC = 0 ] && grep -q '^readback_VF NOT-DECIDED try 2: verify-VF.json missing; sq.py verify exit 1' $O/gates.txt && ! grep -q 'try 3' $O/summary.txt && [ \$(grep -c 'sampled VF: server' $O/summary.txt) = 2 ] && [ -e $O/bp90/P-decode-1.jsonl ] && grep -q 'sampled R1: server' $O/summary.txt"
setup; run VR MOCK_FAIL_ONCE_AT=sqVF
chk "VR (m3) the read-back start not started on its first try: tried again at the sampled part, PASS, quality PASS" "[ $RC = 0 ] && grep -q 'read-back VF (try 2): PASS' $O/summary.txt && [ \$(line_of $O/summary.txt 'server r23af[0-9]*-bpP-1') -lt \$(line_of $O/summary.txt 'read-back VF (try 2)') ] && [ \$(grep -c '  QUALITY (sampled AND read-back): PASS' $O/decision.txt) = 2 ]"
setup; run FS MOCK_FOREIGN_AT=sqX1
chk "FS (m6) a foreign GPU user during X1: X1 void (F1 sampled NOT DECIDED), F2 still PASS" "[ $RC = 0 ] && grep -q '^foreign_sqX1 FAIL seen during sqX1' $O/gates.txt && grep -q '  sampled (X1 vs R1, noise twin R2): NOT DECIDED - sq.py gave PASS' $O/decision.txt && grep -q '^F2 (STRATA_ADAPT_FETCH=2): QUALITY PASS' $O/decision.txt"
setup; run FV MOCK_FOREIGN_AT=sqVF
chk "FV (m6) a foreign GPU user during VF: the read-back voided, tried again (try 2 PASS), the first try's gate RETRIED" "[ $RC = 0 ] && grep -q 'read-back VF (try 1): NOT DECIDED (a foreign GPU user during VF)' $O/summary.txt && grep -q 'read-back VF (try 2): PASS' $O/summary.txt && [ \$(grep '^foreign_sqVF ' $O/gates.txt | tail -1 | cut -d' ' -f2) = RETRIED ] && [ \$(grep -c '  QUALITY (sampled AND read-back): PASS' $O/decision.txt) = 2 ]"

setup; run S MOCK_FAIL_AT=sqR1
chk "S no R1 samples: no ids, no scorer; the other arms ran; quality NOT DECIDED" "[ $RC = 0 ] && grep -q '^skip_score INFO no R1 samples' $O/gates.txt && ! grep -q '^env_sqscore' $O/gates.txt && grep -q 'sampled X1: server' $O/summary.txt && [ \$(grep -c '  QUALITY (sampled AND read-back): NOT DECIDED' $O/decision.txt) = 2 ]"

setup; run W MOCK_WDG_S=1 MOCK_SLEEP_AT=bpP-1 MOCK_SLEEP_S=3
chk "W the watchdog fires once while the gap is still open past its time (mock: seconds, a log line)" "[ $RC = 0 ] && [ \$(grep -c 'mock watchdog' $M/wdg.log 2> /dev/null) = 1 ]"

setup; bgrun T $O/summary.txt 'server r23af[0-9]+-bpP-1' MOCK_SLEEP_AT=bpP-1 MOCK_SLEEP_S=3
chk "T a signal during a server run: exit 7, INTERRUPTED, the gap may still be open, 8080's state said, no end" "[ $RC = 7 ] && grep -q '^INTERRUPTED: the gap may still be open (tmp/port-gap.lockpid): close it with work/r22/port_gap4.sh end; 8080 is' $O/result.txt && [ \$(nend) = 0 ] && grep -q 'would alert: ADAPT_FETCH gap interrupted' $O/summary.txt && [ ! -e $M/driver.pid ]"
setup; bgrun T2 $M/pg4.log '^end' MOCK_END_SLEEP=3
chk "T2 a signal during port_gap4.sh end: exit 7, no second end suggested, 8080's state said" "[ $RC = 7 ] && grep -q '^INTERRUPTED: the driver was stopped while port_gap4.sh end was running: do NOT run end a second time blindly' $O/result.txt && grep -qE '8080 is (NOT )?listening; nothing switched' $O/result.txt && [ \$(nend) = 1 ]"
setup; bgrun T3 $M/lockpid '[0-9]' MOCK_BEGIN_SLEEP=3 MOCK_OLD_ENGINE=1
chk "T3 a signal inside port_gap4.sh begin (the lock already taken): exit 7, 'may have opened', and 8080's engine NOT touched" "[ $RC = 7 ] && grep -q '^INTERRUPTED: the gap may have opened as it was stopped (lock held)' $O/result.txt && alive $M/old-engine.pid"
setup

# ---------------------------------------------------------------- the starter against a stub driver
ST=$M/starter
cat > $ST/drv.sh <<'EOF'
#!/bin/bash
# stub driver: MODE busy1 (busy once, then done), hold, busy, noresult, engines, other; writes the result file the starter reads
ST=__ST__   # (a fixed path: the starter runs a snapshot copy from another folder)
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
  env AFS_DRIVER=$ST/drv.sh AFS_SHAPE_RES=$M/shape-result.txt AFS_SHAPE_UNIT=afetch-mock-no-such-unit AFS_LOCKPID=$M/lockpid \
      AFS_LOG=$ST/starter.log AFS_COPIES=$ST/copies AFS_RESULT=$ST/result.txt AFS_POLL_S=1 AFS_RETRY_S=1 AFS_SETTLE_S=0 \
      AFS_NOTIFY=$ST/notify.sh "$@" timeout 120 bash $AG/afetch-after-shape.sh > $ST/$n.out 2>&1; RC=$?
  cp $ST/starter.log $ST/$n.log 2> /dev/null
  echo "--- starter $n: rc $RC"
}
ready() { echo "reviewed by mock: sha256 $(sha $ST/drv.sh), rules $(sha $AG/afetch_rules.py), client $(sha $WS/work/r23/sampled-qwen/sq_client.py), spec $(sha $WS/work/r23/sampled-qwen/spec-adaptfetch.json)" > $ST/drv.sh.ready; }
setup; rm -f $ST/drv.sh.ready; srun S1 busy1
chk "S1 no .ready -> exit 6, an alert, no try" "[ $RC = 6 ] && grep -q 'ADAPT_FETCH gap not started' $ST/notify.log && [ ! -e $ST/count ]"
setup; ready; sed -i 's/, spec [0-9a-f]*//' $ST/drv.sh.ready; srun S1b busy1
chk "S1b a .ready without the spec's sha -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"
setup; ready; rm -f $M/shape-result.txt; ( sleep 3; echo "DONE (mock shape)" > $M/shape-result.txt ) & srun S2 busy1
chk "S2 waited for the shape result, busy once, then done: 2 tries, exit 0" "[ $RC = 0 ] && [ \$(cat $ST/count) = 2 ] && grep -q 'the shape gap has run' $ST/S2.log && [ \$(ls $ST/copies | wc -l) = 2 ]"
setup; ready; echo "INTERRUPTED: the gap may still be open (mock shape)" > $M/shape-result.txt; ( sleep 3; echo "DONE (mock shape)" > $M/shape-result.txt ) & srun S2b busy1
chk "S2b an interrupted shape gap keeps the starter waiting (then DONE: it runs)" "[ $RC = 0 ] && grep -q 'has not run to an end yet: INTERRUPTED' $ST/S2b.log"
setup; ready; srun S3 hold
chk "S3 the priority hold is final: 1 try, exit 8" "[ $RC = 8 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'priority rule (final' $ST/S3.log"
setup; ready; srun S4 busy AFS_RETRY_FOR_S=4
chk "S4 busy past the retry window: exit 1, an alert, more than 1 try" "[ $RC = 1 ] && [ \$(cat $ST/count) -ge 2 ] && grep -q 'stayed busy' $ST/notify.log"
setup; ready; srun S5 noresult
chk "S5 the driver ended without a result line: exit 3, an alert, no retry" "[ $RC = 3 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'without a result' $ST/notify.log"
setup; ready; srun S7 engines
chk "S7 engines left after 8080 stopped (exit 5): an alert, no retry" "[ $RC = 5 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'ADAPT_FETCH gap not run' $ST/notify.log"
setup; ready; srun S8 other
chk "S8 another driver instance (exit 9): an alert, no retry" "[ $RC = 9 ] && [ \$(cat $ST/count) = 1 ] && grep -q 'another ADAPT_FETCH driver is running' $ST/notify.log"
setup; ready; srun S9 busy1 AFS_TEST_CORRUPT_SNAPSHOT=1
chk "S9 a snapshot that is not the reviewed file: exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ] && grep -q 'snapshot is not the reviewed file' $ST/notify.log"
setup; ready; echo "edited" >> $ST/drv.sh; srun S6 busy1
chk "S6 a driver edited after its review -> exit 6, no try" "[ $RC = 6 ] && [ ! -e $ST/count ]"

echo "--- A decision.txt (first 14 lines, cut)"; head -14 $M/out-A/decision.txt | cut -c1-260
echo "--- A result.txt"; cut -c1-400 $M/out-A/result.txt
echo "gap-mock-test: $([ $F = 0 ] && echo 'ALL CHECKS PASSED' || echo 'FAILED')"
exit $F
