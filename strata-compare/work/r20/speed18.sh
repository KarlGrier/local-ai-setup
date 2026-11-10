#!/bin/bash
# speed18.sh CAND [TAG] - round 20 (copy of work/r19/d7_speed.sh): CAND against A_CFG (default C*17.1, configs/Cstar171.json)
# as served, A B B A (A = A_CFG), each arm a fresh guarded server, your config and
# sampling, the 20 GB floor: the LDR screen, the decode screen and the full screen per arm.
# Tables -> results/r20/s18-{ldr,dec,full}-TAG.md; the display state logged per arm (logs/r20/display.log). Ends with the promoted build on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
CAND=${1:?candidate config} TAG=${2:-c18}; A=$WS/${A_CFG:-configs/Cstar171.json}; AT=${A_TAG:-c171}; PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SS=$(date -Iseconds | cut -c1-19)
for arm in "$AT-a $A" "$TAG-a $CAND" "$TAG-b $CAND" "$AT-b $A"; do
  set -- $arm
  bringup/lib/ldrscreen.sh r20-s18-L-$1 $2 > logs/r20/s18-L-$1.log 2>&1
  bringup/lib/decscreen.sh r20-s18-D-$1 $2 > logs/r20/s18-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r20-s18-F-$1 $2 > logs/r20/s18-F-$1.log 2>&1
  echo "=== $(date -Is) arm $1 done: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-120)"
  echo "$(date -Is) speed18-arm-$1 display_active=$(nvidia-smi --id=GPU-UUID-RTX5080 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=GPU-UUID-RTX5080 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc "/strata --serve")" >> logs/r20/display.log
done
U=${TAG^^}
SINCE=$SS $PY bringup/lib/ldr_table.py ${AT^^}=r20-s18-L-$AT-a,r20-s18-L-$AT-b $U=r20-s18-L-$TAG-a,r20-s18-L-$TAG-b > results/r20/s18-ldr-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py ${AT^^}=r20-s18-D-$AT-a,r20-s18-D-$AT-b $U=r20-s18-D-$TAG-a,r20-s18-D-$TAG-b > results/r20/s18-dec-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py ${AT^^}=r20-s18-F-$AT-a,r20-s18-F-$AT-b $U=r20-s18-F-$TAG-a,r20-s18-F-$TAG-b > results/r20/s18-full-$TAG.md 2>&1
for f in results/r20/s18-*-$TAG.md; do echo "$f: $(grep -iE '^\| *(decode|ms per|ttft)' $f | head -4 | tr -s ' ' | tr '\n' ' ' | cut -c1-300)"; done
bringup/lib/phase_end.sh r20-s18 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) s18 done"
