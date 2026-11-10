#!/bin/bash
# partA_r.sh - round 19 Part A, resumed: the 15:36 session (partA.sh) was ended at 15:42 when my Claude session closed
# (the queue and its run were killed; fio and the default-threads block's two unbuffered runs had finished, its first rule
# run had been stopped by the stand-in swap rule). This runs the rest under the same rules (stock v0.1.42,
# STRATA_ROUTE_TAIL_SKIP=0, floors 6 GiB / 300 MiB / swap growth 4 GiB, cold page cache per run), each block in the
# mirrored order B A A B (unbuffered first: the first buffered load from a low swap level pushes idle pages out and
# tripped the swap rule):
#   2. #1682 Q8_0 A/B: STRATA_IO_THREADS 16, 64, then unset again ("def2", the default's complete block)
#   3. #1683 Q4: --resident-budget-gib 72, --resident-experts, --resident-budget-gib 66
#   4. phase end: C*16.1 on 8080 (kept)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r19; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r19/cfg; R=results/r19
step() { echo "=== $(date -Is) $*"; }
startlines() {
  tail -n +$(( $2 + 1 )) "$1" | grep -E 'expert cache|slots|resident|budget|page-lock|file tier|unbuffered|lend|WARNING|CPU share|VRAM free|TAIL_SKIP|tail skip|max context|arena|refus' | cut -c1-400 | head -60 > "$3"
}
nlines() { wc -l < "$1" 2>/dev/null || echo 0; }
step "resume: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' '); MemAvailable $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB; swap used $(free -m | awk '/Swap/ {print $3}') MiB"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
step "2. Q8_0 A/B (resumed)"
(
  export EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15/prompts
  for T in 16 64 def2; do
    for arm in ub1:a rule:a rule:b ub1:b; do
      IFS=: read -r o s <<< "$arm"
      E="STRATA_IO_STATS=1"; [ $o = ub1 ] && E="$E STRATA_UNBUFFERED_LOAD=1"; case $T in 16|64) E="$E STRATA_IO_THREADS=$T";; esac
      ENVX="$E" COLD=1 bringup/lib/run.sh r19-q8B-t$T-$o-$s $C/q8B-v42.json math 1024 > /dev/null
      grep -h -E 'file tier reads|TAIL_SKIP' bringup/out/logs/prof/r19-q8B-t$T-$o-$s.err | head -3 | cut -c1-200
      tail -1 bringup/out/logs/guard/summary.txt
    done
  done
)
$P work/r19/q8_table19.py > $R/a2-q8B-v42.md 2>&1; cat $R/a2-q8B-v42.md
step "3. Q4 lend"
(
  export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
  for o in b72 res b66; do
    CFG=$C/q4-$o-v42.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$(nlines $ELOG)
    bringup/lib/with_server.sh r19-q4-$o $CFG -- "$P work/r17/cb_bench.py --label q4-$o --sizes warmup,32768 --reps 0,1 --out $R/a3-q4-$o.json" \
      || echo "STEP 3 $o FAILED"
    startlines $ELOG $N0 $R/a3-q4-$o-start.txt
    tail -1 bringup/out/logs/guard/summary.txt
  done
)
$P work/r19/q4_table19.py > $R/a3-q4-lend.md 2>&1; cat $R/a3-q4-lend.md
step "4. phase end"
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-partA keep
step "partA_r done"
