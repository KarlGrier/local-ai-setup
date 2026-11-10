#!/bin/bash
# session.sh - r17 (GitHub prep, 2026-10-09): the measurements behind the drafts, under the standing round rules (one model
# server at a time, 127.0.0.1, guarded runs: 20 GiB / 300 MiB floors on IQ3_S; 6 GiB / 300 MiB / swap +4 GiB on the
# stand-in and Q4 files; cold model page cache per run; stock clocks; caches in tmp/r17) and ending with C*16 on 8080.
#   1. community benchmark: stock v0.1.41 and C*16, IQ3_S, 4K / 32K / 128K x 3 + needles 32k / 128k x 3 depths
#   2. release A/B (CLI, IQ3_S, A B C C B A): stock v0.1.40.1 / v0.1.40.2 / v0.1.41 (share off), same flags
#   3. Q8_0 stand-in, placement B, stock v0.1.41 (CLI, A B B A): the read rule vs STRATA_UNBUFFERED_LOAD=1
#   4. UD-Q4_K_XL, stock v0.1.41 (served, A B B A): --resident-budget-gib 66 vs --resident-experts, two 32K prompts each
#   5. phase end: C*16 on 8080 (kept) + a fresh 48-hour passive monitor
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r17; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r17/cfg; R=results/r17
step() { echo "=== $(date -Is) $*"; }
startlines() {   # startlines LOG FROMLINE OUT: the engine's start lines that matter for the reports
  tail -n +$(( $2 + 1 )) "$1" | grep -E 'expert cache|slots|resident|budget|page-lock|file tier|unbuffered|lend|WARNING|CPU share|VRAM free|max context|arena|refus' | cut -c1-400 | head -60 > "$3"
}
nlines() { wc -l < "$1" 2>/dev/null || echo 0; }

step "start: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' '); MemAvailable $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB; swap used $(free -m | awk '/Swap/ {print $3}') MiB"

# ---- 1. community benchmark
for L in cb-stock cb-c16; do
  CFG=$C/$L.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$(nlines $ELOG)
  step "1. $L"
  bringup/lib/with_server.sh r17-$L $CFG -- "$P work/r17/cb_bench.py --label $L --out $R/$L.json; \
    $P bringup/out/r16/strata-stock/tools/needle_bench.py --url http://127.0.0.1:8081 --lengths 32k,128k --depths 10,50,90 --out $R/$L-needles.json" \
    || echo "STEP 1 $L FAILED"
  startlines $ELOG $N0 $R/$L-start.txt
  tail -1 bringup/out/logs/guard/summary.txt
done

# ---- 2. release A/B
step "2. release A/B"
export PROMPT_DIR=$WS/bringup/out/r16/prompts
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
for arm in v0401:a v0402:a v041:a v041:b v0402:b v0401:b; do
  IFS=: read -r v s <<< "$arm"
  bringup/lib/run.sh r17-rel-$v-$s-x-math $C/rel-$v.json math 1024 $X > /dev/null
  bringup/lib/run.sh r17-rel-$v-$s-x-code $C/rel-$v.json code 1024 $X > /dev/null
  bringup/lib/run.sh r17-rel-$v-$s-a-math $C/rel-$v.json math 1024 > /dev/null
  bringup/lib/run.sh r17-rel-$v-$s-a-code $C/rel-$v.json code 1024 > /dev/null
  echo "$(date -Is) arm $v-$s done"
done
$P work/r17/rel_table.py > $R/rel-ab.md 2>&1; cat $R/rel-ab.md

# ---- 3. Q8_0, placement B, stock v0.1.41
step "3. Q8_0 B"
(
  export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
  export EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15/prompts
  for arm in rule:a ub1:a ub1:b rule:b; do
    IFS=: read -r o s <<< "$arm"
    E="STRATA_IO_STATS=1"; [ $o = ub1 ] && E="$E STRATA_UNBUFFERED_LOAD=1"
    ENVX="$E" COLD=1 bringup/lib/run.sh r17-q8B-$o-$s $C/q8B-stock41.json math 1024 > /dev/null
    grep -h 'file tier reads' bringup/out/logs/prof/r17-q8B-$o-$s.err | head -3
    tail -1 bringup/out/logs/guard/summary.txt
  done
)
$P work/r17/q8_table.py > $R/q8B-stock41.md 2>&1; cat $R/q8B-stock41.md

# ---- 4. UD-Q4_K_XL: budget vs --resident-experts
step "4. Q4 lend"
(
  export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
  export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
  for arm in budget:a resident:a resident:b budget:b; do
    IFS=: read -r o s <<< "$arm"
    CFG=$C/q4-$o.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$(nlines $ELOG)
    bringup/lib/with_server.sh r17-q4-$o-$s $CFG -- "$P work/r17/cb_bench.py --label q4-$o-$s --sizes warmup,32768 --reps 0,1 --out $R/q4-$o-$s.json" \
      || echo "STEP 4 $o-$s FAILED"
    startlines $ELOG $N0 $R/q4-$o-$s-start.txt
    tail -1 bringup/out/logs/guard/summary.txt
  done
)
$P work/r17/q4_table.py > $R/q4-lend.md 2>&1; cat $R/q4-lend.md

# ---- 5. phase end
step "5. phase end"
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r17 keep
(setsid nohup $P work/r13/uptime_monitor.py --out logs/r17/uptime-c16 > /dev/null 2>&1 < /dev/null &)
sleep 5; echo "monitor: $(cat logs/r17/uptime-c16/monitor.pid 2>/dev/null)"
step "session done"
