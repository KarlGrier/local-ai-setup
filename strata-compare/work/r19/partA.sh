#!/bin/bash
# partA.sh - round 19 Part A (the owner's questions on #1682 and #1683), stock v0.1.42 with STRATA_ROUTE_TAIL_SKIP=0, under
# the standing rules (one model server at a time: 8080 is stopped first; 127.0.0.1; guarded runs with the stand-in /
# Q4 floors: MemAvailable >= 6 GiB, 5080 >= 300 MiB, swap growth <= 4 GiB; cold model page cache per run; stock clocks;
# caches in tmp/r19) and ending with the promoted build (C*16.1) on 8080.
#   1. fio, read-only, the owner's command on the Q8_0 file's expert shards (twice), and once with --ioengine=libaio
#   2. #1682: Q8_0, the 5080 + --resident-budget-gib 64 (CLI, greedy math, 1,024 tokens), the rule vs
#      STRATA_UNBUFFERED_LOAD=1, A B B A, with STRATA_IO_THREADS unset (the default), 16, and 64 (the issue's setting)
#   3. #1683: UD-Q4_K_XL served, two 32K prompts per arm: --resident-budget-gib 72, --resident-experts, --resident-budget-gib 66
#   4. phase end: C*16.1 on 8080 (kept)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r19; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r19/cfg; R=results/r19
step() { echo "=== $(date -Is) $*"; }
startlines() {   # startlines LOG FROMLINE OUT
  tail -n +$(( $2 + 1 )) "$1" | grep -E 'expert cache|slots|resident|budget|page-lock|file tier|unbuffered|lend|WARNING|CPU share|VRAM free|TAIL_SKIP|tail skip|max context|arena|refus' | cut -c1-400 | head -60 > "$3"
}
nlines() { wc -l < "$1" 2>/dev/null || echo 0; }
step "start: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' '); MemAvailable $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB; swap used $(free -m | awk '/Swap/ {print $3}') MiB"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }

export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4

# ---- 1. fio
step "1. fio"
Q8=$WS/models/r15/Q8_0/Qwen3.8-Flash-Next-Q8_0
FN=$Q8-00004-of-00006.gguf:$Q8-00005-of-00006.gguf:$Q8-00006-of-00006.gguf
for k in 1 2; do
  echo "--- fio run $k (the owner's command + --readonly)"
  fio --name=r --filename=$FN --rw=randread --bs=8M --direct=1 --iodepth=32 --numjobs=8 --runtime=20 --time_based --group_reporting --readonly \
    > $R/a1-fio-$k.txt 2>&1; echo "rc $?"; grep -E 'ioengine|READ:|read: IOPS' $R/a1-fio-$k.txt
done
echo "--- fio with --ioengine=libaio (so --iodepth=32 takes effect)"
fio --name=r --filename=$FN --rw=randread --bs=8M --direct=1 --iodepth=32 --numjobs=8 --runtime=20 --time_based --group_reporting --readonly --ioengine=libaio \
  > $R/a1-fio-libaio.txt 2>&1; echo "rc $?"; grep -E 'ioengine|READ:|read: IOPS' $R/a1-fio-libaio.txt

# ---- 2. #1682 A/B
step "2. Q8_0 A/B"
(
  export EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15/prompts
  for T in def 16 64; do
    for arm in rule:a ub1:a ub1:b rule:b; do
      IFS=: read -r o s <<< "$arm"
      E="STRATA_IO_STATS=1"; [ $o = ub1 ] && E="$E STRATA_UNBUFFERED_LOAD=1"; [ $T != def ] && E="$E STRATA_IO_THREADS=$T"
      ENVX="$E" COLD=1 bringup/lib/run.sh r19-q8B-t$T-$o-$s $C/q8B-v42.json math 1024 > /dev/null
      grep -h -E 'file tier reads|TAIL_SKIP|tail skip' bringup/out/logs/prof/r19-q8B-t$T-$o-$s.err | head -4 | cut -c1-250
      tail -1 bringup/out/logs/guard/summary.txt
    done
  done
)
$P work/r19/q8_table19.py > $R/a2-q8B-v42.md 2>&1; cat $R/a2-q8B-v42.md

# ---- 3. #1683: budget 72 / resident / budget 66
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

# ---- 4. phase end
step "4. phase end"
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-partA keep
step "partA done"
