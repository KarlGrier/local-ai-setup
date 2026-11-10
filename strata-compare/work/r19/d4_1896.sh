#!/bin/bash
# d4_1896.sh - round 19 Part D 4: PR #1896 (elightcap, the fix for #1683: a budget keeps the prompt path's lend region as far
# as it reaches) on CUDA, which the PR lists as not tested. Stock v0.1.43 and stock v0.1.43 + #1896's commit (cherry-picked,
# clean), both K-quant builds; UD-Q4_K_XL, the 5080 alone, the #1683 method (served, a fresh server per arm, the model's page
# cache dropped, the warm-up + the two 32,768-token prompts), STRATA_ROUTE_TAIL_SKIP=0:
#   --resident-budget-gib 72 on stock v0.1.43 / on + #1896 / --resident-experts on stock v0.1.43
# Lent slots kept in RAM, the 32K read, drive reads per 32K prompt, decode, lowest MemAvailable; the kernel log after each.
# Ends with the promoted build (C*17) on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r19/cfg; R=results/r19
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
nlines() { [ -f "$1" ] && wc -l < "$1" || echo 0; }
kc d4-start
echo "=== $(date -Is) K-quant builds: stock v0.1.43, + #1896"
work/r19/build_kq.sh tmp/r19/v43 tmp/r19/engine-v43-kq "stock v0.1.43" || { echo BUILD FAILED; exit 1; }
work/r19/build_kq.sh tmp/r19/v43-1896 tmp/r19/engine-v43-1896-kq "v0.1.43 + #1896 (29063eb2 cherry-picked)" || { echo BUILD FAILED; exit 1; }
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
for o in b72-v43 b72-1896 res-v43; do
  CFG=$C/q4-$o.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$(nlines $ELOG)
  bringup/lib/with_server.sh r19-d4-$o $CFG -- "$P work/r17/cb_bench.py --label d4-$o --sizes warmup,32768 --reps 0,1 --out $R/d4-q4-$o.json" || echo "ARM $o FAILED"
  tail -n +$(( N0 + 1 )) $ELOG | grep -E 'RAM budget|complement ready|lendable|lend region|lends|resident RAM mode|WARNING|borrows|TAIL_SKIP' | cut -c1-320 | head -12 > $R/d4-q4-$o-start.txt
  cat $R/d4-q4-$o-start.txt | cut -c1-200
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
  kc r19-d4-$o
done
$P - <<'PY' | tee $R/d4-1896.md
import json, re
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/results/r19")
G = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/guard/summary.txt").read_text().splitlines()
print("| arm | RAM copy | lent slots' experts in RAM | 32K read (s) | prompt tok/s | drive GB per 32K prompt | decode tok/s | lowest MemAvailable (GiB) |")
print("|---|---|---|---|---|---|---|---|")
names = {"b72-v43": "`--resident-budget-gib 72`, stock v0.1.43", "b72-1896": "`--resident-budget-gib 72`, v0.1.43 + #1896",
         "res-v43": "`--resident-experts`, stock v0.1.43"}
for o, nm in names.items():
    st = (R / f"d4-q4-{o}-start.txt").read_text(errors="replace") if (R / f"d4-q4-{o}-start.txt").exists() else ""
    m = re.search(r"resident RAM mode: ([\d.]+ GiB)", st); ram = m.group(1) if m else "–"
    m1 = re.search(r"(\d+) of (?:the prompt path's|its) (\d+) (?:lendable )?slots keep their experts in RAM", st)
    m2 = re.search(r"lends (\d+) cache slots to the prompt path, but only (\d+) of their experts fit in RAM", st)
    lend = f"{m1.group(1)} of {m1.group(2)}" if m1 else (f"{m2.group(2)} of {m2.group(1)}" if m2 else "–")
    low = "–"
    for line in G:
        if f" srv-r19-d4-{o} " in line:
            mm = re.search(r"min_MemAvailable=([\d.]+)GiB", line); low = mm.group(1) if mm else low
    f = R / f"d4-q4-{o}.json"
    if not f.exists(): print(f"| {nm} | {ram} | {lend} | did not run | | | | {low} |"); continue
    runs = json.loads(f.read_text())["runs"]
    rd = " / ".join(f"{r['timings']['prompt_ms'] / 1000:.2f}" for r in runs); tps = " / ".join(f"{r['timings']['prompt_per_second']:.0f}" for r in runs)
    gb = " / ".join(f"{r['drive_read_gb']:.1f}" for r in runs); dec = " / ".join(f"{r['timings']['predicted_per_second']:.1f}" for r in runs)
    print(f"| {nm} | {ram} | {lend} | {rd} | {tps} | {gb} | {dec} | {low} |")
PY
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-d4 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc d4-end
echo "=== $(date -Is) d4 done"
