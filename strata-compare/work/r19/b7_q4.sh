#!/bin/bash
# b7_q4.sh SINGLE_CFG [TREE] - round 19 Part B step 7: configs/r16-q4.json (UD-Q4_K_XL) for the new build, with
# STRATA_ROUTE_TAIL_SKIP=0, and the user's addition (2026-10-11): --resident-experts in place of --resident-budget-gib 66.
#   SINGLE_CFG  the new build's one-GPU config (the launcher's fallback; its engine's tree is built again with K-quants)
#   TREE        the new build's source tree (default bringup/out/r19/strata-patched), built into tmp/r19/engine-new-kq
#               with -DSTRATA_MMQ_KQUANTS=ON in its own build directory (build-kq)
# Steps (one model server at a time; Q4 = a stand-in file: the 6 GiB floor, 5080 >= 300 MiB, swap growth <= 4 GiB; cold
# page cache per run; the kernel log checked after EVERY run, stop at the first error):
#   1. build; configs/r19-q4-b66.json and r19-q4-res.json (work/r19/mk_q4cfg.py)
#   2. lossless: exact7's seven fixed-computation items (--adapt-swaps 0 --suffix-draft 0 --expert-cache 2400: the 5080
#      cannot hold exact7's usual 3500 Q4 slots) on b66, then on res: every output hash must be equal
#   3. B A A B (B = res): a fresh guarded server per arm, the a3b method (the warm-up + the two 32,768-token prompts):
#      32K read time, drive GB, decode, lowest MemAvailable; b66-a doubles as B7's "starts and answers" check
#   4. adopt res in configs/r16-q4.json only if: the 7 hashes equal, all four servers ran clean (guard ok, kernel clean),
#      the 32K read >= 3 % faster (mean) and decode not slower (mean, within 1 %). Else configs/r16-q4.json = b66.
# Ends with the promoted build on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r19; source bringup/lib/env.sh
SINGLE=${1:?the new build\'s one-GPU config} TREE=${2:-bringup/out/r19/strata-patched}
P=.venv/bin/python; R=results/r19; KQ=tmp/r19/engine-new-kq
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED after $1 - b7 stopped, nothing restarted"; exit 1; }; }
kc b7-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }

step "1. K-quant build of $TREE"
BUILD_DIR=build-kq work/r19/build_kq.sh $TREE $KQ "new build ($TREE)" || { step "BUILD FAILED"; exit 1; }
$P work/r19/mk_q4cfg.py $SINGLE $WS/$KQ/strata || exit 1
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
export PROMPT_DIR=$WS/bringup/out/r16q4/prompts

step "2. lossless: exact7 items, b66 then res (--expert-cache 2400)"
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 2400"; S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
for arm in b66 res; do
  for it in "x-math math 1024" "s-math math 1024" "x-code code 1024" "s-code code 1024" "x-p2000 p2000 64" "x-32k 32k 64" "x-112k tf-long112k.prompt 64"; do
    set -- $it; L=r19-b7-e7-$arm-$1
    if [ "${1:0:1}" = s ]; then PROF_SAMPLING="$S" COLD=1 bringup/lib/run.sh $L configs/r19-q4-$arm.json $2 $3 $X > /dev/null
    else COLD=1 bringup/lib/run.sh $L configs/r19-q4-$arm.json $2 $3 $X > /dev/null; fi
    tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170
    kc $L
  done
done
$P - <<'PY' | tee $R/b7-q4-exact.md
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
print("| item | budget 66 | --resident-experts | equal | prompt ms (66 / res) |\n|---|---|---|---|---|")
n = 0
for it in ("x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k"):
    a, b = parse(f"r19-b7-e7-b66-{it}") or {}, parse(f"r19-b7-e7-res-{it}") or {}
    eq = a.get("out") is not None and a.get("out") == b.get("out"); n += eq
    print(f"| {it} | {a.get('out')} | {b.get('out')} | {'yes' if eq else 'NO'} | {a.get('pf_ms', 0):.0f} / {b.get('pf_ms', 0):.0f} |")
print(f"\nexact b66 vs res: {n}/7 identical")
PY

step "3. B A A B: res-a b66-a b66-b res-b (served, the a3b method)"
for arm in res:a b66:a b66:b res:b; do
  IFS=: read -r o s <<< "$arm"; CFG=configs/r19-q4-$o.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
  N0=$( [ -f $ELOG ] && wc -l < $ELOG || echo 0)
  bringup/lib/with_server.sh r19-b7-q4-$o-$s $CFG -- "$P work/r17/cb_bench.py --label b7-$o-$s --sizes warmup,32768 --reps 0,1 --out $R/b7-q4-$o-$s.json" \
    || echo "ARM $o-$s FAILED"
  tail -n +$(( N0 + 1 )) $ELOG | grep -E 'RAM budget|complement ready|lendable|lends|resident RAM mode|TAIL_SKIP|tail skip|borrows' | cut -c1-300 | head -12 > $R/b7-q4-$o-$s-start.txt
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170
  kc r19-b7-q4-$o-$s
done

step "4. decision"
$P - <<'PY' | tee $R/b7-q4.md
import json, re
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); R = WS / "results/r19"
G = (WS / "bringup/out/logs/guard/summary.txt").read_text().splitlines()
ex = (R / "b7-q4-exact.md").read_text(); exact_ok = "7/7 identical" in ex
print("# r19 B7 — UD-Q4_K_XL on the new build: --resident-experts vs --resident-budget-gib 66 (B A A B, STRATA_ROUTE_TAIL_SKIP=0)\n")
print("| arm | RAM copy / lent slots in RAM | 32K r0 / r1 read (s) | prompt tok/s | drive GB per 32K prompt | decode tok/s | lowest MemAvailable (GiB) | guard |")
print("|---|---|---|---|---|---|---|---|")
agg, clean = {"b66": {"rd": [], "dec": []}, "res": {"rd": [], "dec": []}}, True
for o, s in (("res", "a"), ("b66", "a"), ("b66", "b"), ("res", "b")):
    L = f"r19-b7-q4-{o}-{s}"; sf = R / f"b7-q4-{o}-{s}-start.txt"
    st = sf.read_text(errors="replace") if sf.exists() else ""
    m = re.search(r"resident RAM mode: ([\d.]+ GiB)", st); ram = m.group(1) if m else "–"
    m = re.search(r"(\d+) of the prompt path's (\d+) lendable", st) or re.search(r"lends (\d+) cache slots.*?only (\d+) of", st)
    lend = (f"{m.group(1)} of {m.group(2)}" if "lendable" in m.group(0) else f"{m.group(2)} of {m.group(1)}") if m else "–"
    gl = [l for l in G if f" srv-{L} " in l]; g = gl[-1] if gl else ""
    mm = re.search(r"min_MemAvailable=([\d.]+)GiB", g); low = mm.group(1) if mm else "–"
    ok = g.endswith(" ok"); clean &= ok
    f = R / f"b7-q4-{o}-{s}.json"
    if not f.exists():
        clean = False; print(f"| {o}-{s} | {ram} / {lend} | did not run | | | | {low} | {g[-40:]} |"); continue
    runs = json.loads(f.read_text())["runs"]
    rd = [r["timings"]["prompt_ms"] / 1000 for r in runs]; dec = [r["timings"]["predicted_per_second"] for r in runs]
    agg[o]["rd"] += rd; agg[o]["dec"] += dec
    print(f"| {o}-{s} | {ram} / {lend} | {' / '.join(f'{x:.2f}' for x in rd)} | {' / '.join(str(round(r['timings']['prompt_per_second'])) for r in runs)} | "
          f"{' / '.join(str(r['drive_read_gb']) for r in runs)} | {' / '.join(f'{x:.1f}' for x in dec)} | {low} | {'ok' if ok else g[-60:]} |")
mean = lambda v: sum(v) / len(v) if v else float("nan")
rb, rr = mean(agg["b66"]["rd"]), mean(agg["res"]["rd"]); db, dr = mean(agg["b66"]["dec"]), mean(agg["res"]["dec"])
faster = rr <= 0.97 * rb; dec_ok = dr >= 0.99 * db
print(f"\n- 32K read: budget 66 {rb:.2f} s, --resident-experts {rr:.2f} s ({100 * (rr / rb - 1):+.1f} %); decode {db:.1f} vs {dr:.1f} tok/s ({100 * (dr / db - 1):+.1f} %)")
print(f"- lossless (exact7 items equal): {'yes' if exact_ok else 'NO'}; every run clean (guard ok; the kernel checks passed or the script stopped): {'yes' if clean else 'NO'}")
print(f"- read >= 3 % faster: {'yes' if faster else 'no'}; decode not slower (within 1 %): {'yes' if dec_ok else 'no'}")
adopt = exact_ok and clean and faster and dec_ok
print(f"\nDECISION: {'ADOPT --resident-experts' if adopt else 'KEEP --resident-budget-gib 66'}")
(R / "b7-q4-decision.txt").write_text("res\n" if adopt else "b66\n")
PY
D=$(cat $R/b7-q4-decision.txt)
[ -f configs/r16-q4.json.pre-r19 ] || cp configs/r16-q4.json configs/r16-q4.json.pre-r19
$P - $D <<'PY'
import json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); d = sys.argv[1]
c = json.load(open(WS / f"configs/r19-q4-{d}.json")); c["log"] = str(WS / "logs/engine-r16-q4.log")
c["_comment"] += f" (configs/r16-q4.json from round 19 B7: {'--resident-experts adopted' if d == 'res' else 'the budget kept'}; results/r19/b7-q4.md)"
(WS / "configs/r16-q4.json").write_text(json.dumps(c, indent=1) + "\n"); print("configs/r16-q4.json <- configs/r19-q4-" + d + ".json")
PY
step "5. phase end"
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-b7 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc b7-end
step "b7 done"
