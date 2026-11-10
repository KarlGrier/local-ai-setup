#!/bin/bash
# partA2.sh - round 19 Part A, the default-threads block again: its first run (the rule arm, STRATA_IO_THREADS unset) was
# stopped by the stand-in swap rule (+4.2 GiB from 0 GiB after the morning's restart; Round 17 started at 2.0 GiB), so the
# whole A B B A repeats as "def2". Same rules as partA.sh; ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r19; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r19/cfg; R=results/r19
echo "=== $(date -Is) partA2 start: swap used $(free -m | awk '/Swap/ {print $3}') MiB"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }
(
  export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
  export EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15/prompts
  for arm in rule:a ub1:a ub1:b rule:b; do
    IFS=: read -r o s <<< "$arm"
    E="STRATA_IO_STATS=1"; [ $o = ub1 ] && E="$E STRATA_UNBUFFERED_LOAD=1"
    ENVX="$E" COLD=1 bringup/lib/run.sh r19-q8B-tdef2-$o-$s $C/q8B-v42.json math 1024 > /dev/null
    grep -h -E 'file tier reads|TAIL_SKIP' bringup/out/logs/prof/r19-q8B-tdef2-$o-$s.err | head -3 | cut -c1-200
    tail -1 bringup/out/logs/guard/summary.txt
  done
)
$P work/r19/q8_table19.py > $R/a2-q8B-v42.md 2>&1; cat $R/a2-q8B-v42.md
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-partA2 keep
echo "=== $(date -Is) partA2 done"
