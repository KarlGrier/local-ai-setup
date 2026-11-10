#!/bin/bash
# b6_screens.sh CAND [TAG] - round 19 Part B step 6: the new build (CAND: v0.1.42 + the ported series, steps 3-5's settings)
# against C*16.1 as served (configs/Cstar161.json), A B B A (A = C*16.1), each arm a fresh guarded server, your config and
# sampling, the 20 GB floor: the LDR screen, the decode screen and the full screen per arm.
# Tables -> results/r19/b6-{ldr,dec,full}-TAG.md. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
CAND=${1:?candidate config} TAG=${2:-c17}; A=$WS/configs/Cstar161.json; PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SS=$(date -Iseconds | cut -c1-19)
for arm in "c161-a $A" "$TAG-a $CAND" "$TAG-b $CAND" "c161-b $A"; do
  set -- $arm
  bringup/lib/ldrscreen.sh r19-b6-L-$1 $2 > logs/r19/b6-L-$1.log 2>&1
  bringup/lib/decscreen.sh r19-b6-D-$1 $2 > logs/r19/b6-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r19-b6-F-$1 $2 > logs/r19/b6-F-$1.log 2>&1
  echo "=== $(date -Is) arm $1 done: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-120)"
done
U=${TAG^^}
SINCE=$SS $PY bringup/lib/ldr_table.py C161=r19-b6-L-c161-a,r19-b6-L-c161-b $U=r19-b6-L-$TAG-a,r19-b6-L-$TAG-b > results/r19/b6-ldr-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py C161=r19-b6-D-c161-a,r19-b6-D-c161-b $U=r19-b6-D-$TAG-a,r19-b6-D-$TAG-b > results/r19/b6-dec-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py C161=r19-b6-F-c161-a,r19-b6-F-c161-b $U=r19-b6-F-$TAG-a,r19-b6-F-$TAG-b > results/r19/b6-full-$TAG.md 2>&1
for f in results/r19/b6-*-$TAG.md; do echo "$f: $(grep -iE '^\| *(decode|ms per|ttft)' $f | head -4 | tr -s ' ' | tr '\n' ' ' | cut -c1-300)"; done
bringup/lib/phase_end.sh r19-b6 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) b6 done"
