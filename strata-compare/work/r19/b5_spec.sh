#!/bin/bash
# b5_spec.sh - round 19 Part B step 5: our exact sampling as served (STRATA_SPEC_EXACT=1 + the cost gate) against upstream's
# STRATA_SPEC_PROB=1 with our cost gate, on the candidate (two cards), the decode screen A B B A (A = ours). Your rule: if
# upstream's is as fast or faster (within 1 %), switch to it and drop our patch. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB SPEED_FILE
P=.venv/bin/python; R=results/r19; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SS=$(date -Iseconds | cut -c1-19)
for arm in ex-a sp-a sp-b ex-b; do
  case $arm in ex*) CFG=configs/r19-cand.json;; *) CFG=configs/r19-cand-sp.json;; esac
  bringup/lib/decscreen.sh r19-b5-D-$arm $CFG > logs/r19/b5-D-$arm.log 2>&1
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
done
SINCE=$SS $P bringup/lib/ab_table.py EXACT=r19-b5-D-ex-a,r19-b5-D-ex-b SPEC_PROB=r19-b5-D-sp-a,r19-b5-D-sp-b | tee $R/b5-spec-dec.md
bringup/lib/phase_end.sh r19-b5 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) b5 done"
