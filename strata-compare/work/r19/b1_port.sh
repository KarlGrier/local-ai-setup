#!/bin/bash
# b1_port.sh - round 19 Part B step 1: C*16.1's series on v0.1.42 with the runbook (run r19: clean clones, build, the
# release alone with my flags twice, patched with every switch off = the release, every switch's gate), then every switch
# on (the candidate config, = C*16.1's) against C*16.1's exact7 hashes; ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19
echo "=== $(date -Is) b1: 8080 stopped for the runbook (one model server at a time)"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
bringup/runbook.sh r19 clone inspect fitplan pack build stock patched patches
grep -E 'stock:|patched|patch |build:' bringup/out/r19/runbook.log | cut -c1-300
export PROMPT_DIR=$WS/bringup/out/r19/prompts
echo "=== $(date -Is) b1: every switch on (configs/r19-cand.json) vs C*16.1 (REF c161)"
REF=c161 bringup/lib/exact7.sh r19-e7-cand configs/r19-cand.json 2>&1 | tail -8 | tee results/r19/b1-e7-cand.txt
grep -h 'patch guards' bringup/out/logs/prof/r19-e7-cand-x-math.err | head -2 | tee -a results/r19/b1-e7-cand.txt
bringup/lib/phase_end.sh r19-b1 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) b1 done"
