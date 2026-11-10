#!/bin/bash
# a4arms.sh — round 13 A4 (<= 3 h): two requests in one window (v0.1.39's batch slots) on the base, LDR-shaped pairs
# (work/r13/a4pairs.py: the LDR screen's 12 requests as 6 consecutive pairs, both ready). Arms: 1 = one slot (configs/
# R12B.json), both sent at once (the server queues the second: sequential); 2 = two slots configured (configs/
# R12B-par2.json = + --batch 2), one active (each pair sent one after the other); 3 = two slots, both active (sent at
# once). Order: [1] [2 3] [3 2] [1], each bracket one fresh guarded server, cold model page cache, warm-up first.
# The engine log keeps its start lines (expert slots with / without the second slot) and the "strata batch:" lines.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r13/env.sh
srv() {   # LABEL CFG then the a4pairs runs given as "mode arm" pairs
  local L=$1 CFG=$2; shift 2
  .venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
  echo "=== $(date -Is) a4 $L start ($CFG)"
  work/r13/srv.sh start $L "$CFG" || return 1
  .venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
  while [ $# -gt 0 ]; do .venv/bin/python work/r13/a4pairs.py --config $L --mode $1 --arm $2; shift 2; done
  echo "vram: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
  work/r13/srv.sh stop
}
T0=$(date +%s)
srv a4-one1 configs/R12B.json pair arm1
srv a4-two1 configs/R12B-par2.json seq arm2 pair arm3
srv a4-two2 configs/R12B-par2.json pair arm3 seq arm2
srv a4-one2 configs/R12B.json pair arm1
grep -E "expert cache|batch_slots|slots|strata batch:" logs/engine-R12B-par2.log | tail -12
echo "desktop on the 4060 Ti during A4: $(.venv/bin/python work/r13/desk_load.py $T0 $(date +%s) 2>&1 | tail -1)"
echo "=== $(date -Is) a4 done"
