#!/bin/bash
# partA19b.sh - round 19 Part A, the clean re-run after the RAM fix (6000 MT/s 1:1; memtest clean; stressapptest PASS first,
# work/r19/stress.sh) on the clean rebuilds (results/r19/integrity/rebuild.txt). Every Part A number is measured again in
# one session, on one build, at the new RAM speed (the 15:36-15:41 runs were at 6200 MT/s on the faulty RAM):
#   1. fio, read-only, the owner's command on the Q8_0 file's expert shards (twice), and once with --ioengine=libaio
#   2. #1682: Q8_0, stock v0.1.42 (tmp/r18/v42-main), the 5080 + --resident-budget-gib 64, CLI greedy math, 1,024 tokens,
#      the read rule vs STRATA_UNBUFFERED_LOAD=1, each block B A A B (unbuffered first: the first buffered load from a low
#      swap level trips the stand-in swap rule), STRATA_IO_THREADS unset, 16, 64
#   3. #1683: UD-Q4_K_XL served (stock v0.1.42 K-quant build), two 32K prompts per arm: --resident-budget-gib 72,
#      --resident-experts, --resident-budget-gib 66
# Rules: stock v0.1.42 with STRATA_ROUTE_TAIL_SKIP=0 (the configs); one model server at a time (8080 stopped first);
# guard floors of the stand-ins (MemAvailable >= 6 GiB, 5080 >= 300 MiB, swap growth <= 4 GiB); cold page cache per run;
# the kernel log checked after every run (bringup/lib/kcheck.sh; the watcher kwatch.sh stops everything at the first
# error). Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r19; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r19/cfg; R=results/r19
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED after $1 - Part A stopped, nothing restarted"; exit 1; }; }
startlines() {   # startlines LOG FROMLINE OUT
  tail -n +$(( $2 + 1 )) "$1" | grep -E 'expert cache|slots|resident|budget|page-lock|file tier|unbuffered|lend|WARNING|CPU share|VRAM free|TAIL_SKIP|tail skip|max context|arena|refus' | cut -c1-400 | head -60 > "$3"
}
nlines() { wc -l < "$1" 2>/dev/null || echo 0; }
[ -f tmp/r19/STRESS_FAIL ] && { step "stressapptest did not pass - Part A not run"; exit 1; }
grep -q 'stress PASS' logs/r19/stress.log 2>/dev/null || { step "no stressapptest PASS on record (logs/r19/stress.log) - Part A not run"; exit 1; }
kc partA-start
step "start: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' '); MemAvailable $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB; swap used $(free -m | awk '/Swap/ {print $3}') MiB"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4

step "1. fio"
Q8=$WS/models/r15/Q8_0/Qwen3.8-Flash-Next-Q8_0
FN=$Q8-00004-of-00006.gguf:$Q8-00005-of-00006.gguf:$Q8-00006-of-00006.gguf
for k in 1 2; do
  fio --name=r --filename=$FN --rw=randread --bs=8M --direct=1 --iodepth=32 --numjobs=8 --runtime=20 --time_based --group_reporting --readonly \
    > $R/a1b-fio-$k.txt 2>&1; echo "fio $k rc $?"; grep -E 'ioengine|READ:|read: IOPS' $R/a1b-fio-$k.txt
done
fio --name=r --filename=$FN --rw=randread --bs=8M --direct=1 --iodepth=32 --numjobs=8 --runtime=20 --time_based --group_reporting --readonly --ioengine=libaio \
  > $R/a1b-fio-libaio.txt 2>&1; echo "fio libaio rc $?"; grep -E 'ioengine|READ:|read: IOPS' $R/a1b-fio-libaio.txt
kc fio

step "2. #1682 Q8_0 A/B"
(
  export EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15/prompts
  for T in def 16 64; do
    for arm in ub1:a rule:a rule:b ub1:b; do
      IFS=: read -r o s <<< "$arm"
      E="STRATA_IO_STATS=1"; [ $o = ub1 ] && E="$E STRATA_UNBUFFERED_LOAD=1"; [ $T != def ] && E="$E STRATA_IO_THREADS=$T"
      ENVX="$E" COLD=1 bringup/lib/run.sh r19b-q8B-t$T-$o-$s $C/q8B-v42.json math 1024 > /dev/null
      grep -h -E 'file tier reads|TAIL_SKIP|tail skip' bringup/out/logs/prof/r19b-q8B-t$T-$o-$s.err | head -4 | cut -c1-250
      tail -1 bringup/out/logs/guard/summary.txt
      kc r19b-q8B-t$T-$o-$s || exit 1
    done
  done
) || exit 1
PFX=r19b TS="def 16 64" $P work/r19/q8_table19.py > $R/a2b-q8B-v42.md 2>&1; cat $R/a2b-q8B-v42.md

step "3. #1683 Q4 lend"
(
  export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
  for o in b72 res b66; do
    CFG=$C/q4-$o-v42.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$(nlines $ELOG)
    bringup/lib/with_server.sh r19b-q4-$o $CFG -- "$P work/r17/cb_bench.py --label q4b-$o --sizes warmup,32768 --reps 0,1 --out $R/a3b-q4-$o.json" \
      || echo "STEP 3 $o FAILED"
    startlines $ELOG $N0 $R/a3b-q4-$o-start.txt
    tail -1 bringup/out/logs/guard/summary.txt
    kc r19b-q4-$o || exit 1
  done
) || exit 1
PFX=r19b A3=a3b $P work/r19/q4_table19.py > $R/a3b-q4-lend.md 2>&1; cat $R/a3b-q4-lend.md

step "4. phase end"
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-partA19b keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc partA-end
step "partA19b done"
