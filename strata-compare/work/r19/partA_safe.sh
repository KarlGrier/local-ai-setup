#!/bin/bash
# partA_safe.sh - round 19 Part A, only the arms that keep the memory floor: on v0.1.42 the buffered "rule" arm of #1682
# (Q8_0, 64 GiB budget, the file cache) ran this PC out of memory three times (15:43, 15:48:40, 15:48:59: the kernel's
# OOM killer ended the engine while it page-locked the copy; the guard's 0.2 s samples did not see it), so no buffered
# arm runs again without your OK, and neither does #1683's --resident-experts arm (70.5 GiB page-locked through the file
# cache; lowest 12.2 GiB in Round 17). Runs: the 64-thread unbuffered pair's B arm (its A arm was the last of partA_r),
# then #1683's budget arms (unbuffered, as in the issue): 72, then 66. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r19; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r19/cfg; R=results/r19
for i in $(seq 300); do pgrep -f '/strata --pack|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --pack|/strata --serve' && { echo "a model process is still running - stop"; exit 1; }
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
echo "=== $(date -Is) safe: swap used $(free -m | awk '/Swap/ {print $3}') MiB"
( export EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15/prompts
  ENVX="STRATA_IO_STATS=1 STRATA_UNBUFFERED_LOAD=1 STRATA_IO_THREADS=64" COLD=1 bringup/lib/run.sh r19-q8B-t64-ub1-b $C/q8B-v42.json math 1024 > /dev/null
  tail -1 bringup/out/logs/guard/summary.txt )
$P work/r19/q8_table19.py > $R/a2-q8B-v42.md 2>&1
nlines() { wc -l < "$1" 2>/dev/null || echo 0; }
( export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
  for o in b72 b66; do
    CFG=$C/q4-$o-v42.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$(nlines $ELOG)
    bringup/lib/with_server.sh r19-q4-$o $CFG -- "$P work/r17/cb_bench.py --label q4-$o --sizes warmup,32768 --reps 0,1 --out $R/a3-q4-$o.json" || echo "Q4 $o FAILED"
    tail -n +$(( N0 + 1 )) $ELOG | grep -E 'expert cache|slots|resident|budget|page-lock|file tier|unbuffered|lend|WARNING|CPU share|VRAM free|TAIL_SKIP|tail skip' | cut -c1-400 | head -60 > $R/a3-q4-$o-start.txt
    tail -1 bringup/out/logs/guard/summary.txt
  done )
$P work/r19/q4_table19.py > $R/a3-q4-lend.md 2>&1; cat $R/a3-q4-lend.md | head -12
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-partA keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) partA_safe done"
