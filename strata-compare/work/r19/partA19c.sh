#!/bin/bash
# partA19c.sh - round 19 Part A, the clean re-run's missing arm: in partA19b the first buffered run (STRATA_IO_THREADS
# unset, rule-a, 01:07) was stopped by the stand-in swap rule (+4.0 GiB; swap was 0 after the reboot, so the page-locking
# pushed the desktop's pages out). Every later buffered run passed (+2.2 GiB). So the default setting gets one more full
# block, "def2" (B A A B: ub1-a rule-a rule-b ub1-b), same configs, same method; then the table with def2.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r19; source bringup/lib/env.sh
P=.venv/bin/python; C=work/r19/cfg; R=results/r19
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED after $1 - stopped, nothing restarted"; exit 1; }; }
kc partA19c-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
step "#1682 Q8_0 A/B, STRATA_IO_THREADS unset, repeated (def2)"
(
  export EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15/prompts
  T=def2
  for arm in ub1:a rule:a rule:b ub1:b; do
    IFS=: read -r o s <<< "$arm"
    E="STRATA_IO_STATS=1"; [ $o = ub1 ] && E="$E STRATA_UNBUFFERED_LOAD=1"
    ENVX="$E" COLD=1 bringup/lib/run.sh r19b-q8B-t$T-$o-$s $C/q8B-v42.json math 1024 > /dev/null
    grep -h -E 'file tier reads|TAIL_SKIP|tail skip' bringup/out/logs/prof/r19b-q8B-t$T-$o-$s.err | head -4 | cut -c1-250
    tail -1 bringup/out/logs/guard/summary.txt
    kc r19b-q8B-t$T-$o-$s || exit 1
  done
) || exit 1
PFX=r19b TS="def 16 64 def2" $P work/r19/q8_table19.py > $R/a2b-q8B-v42.md 2>&1; cat $R/a2b-q8B-v42.md
step "phase end"
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-partA19c keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc partA19c-end
step "partA19c done"
