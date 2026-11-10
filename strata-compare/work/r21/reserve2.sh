#!/bin/bash
# reserve2.sh - 2026-10-16 morning item 2: C*18 with --vram-reserve-mib 512 (configs/Cstar18r.json) against C*18 as served
# (713), now that the desktop runs on the iGPU. Gates: exact7 at the natural cache size (PIN_CACHE=auto) against C*18's
# own hashes (REF=c18-e7), then speed A B B A (decode screen + full screen, which has the 32K prompt read), each arm a
# fresh guarded server. VRAM floor 128 MiB for these runs (the candidate is meant to run at ~300 MiB free; the desktop is
# off the 5080); the memory floor stays 20 GiB. Tables -> results/r21/res-{dec,full}.md. Ends with C*18 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
A=$WS/configs/Cstar18.json B=$WS/configs/Cstar18r.json PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
export GUARD_VRAM_MIB=128
kc() { bringup/lib/kcheck.sh "r21-res-$1" || { echo "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
# exact7 c18r-e7 (candidate, natural cache 4696 slots) ran first: 2/7 vs c18-e7 (4510 slots) - decode outputs follow the
# cache's slot count. Two checks separate the causes: C*18 as served at today's natural size, and the candidate at
# c18-e7's pinned budget (same slot count -> must be 7/7 if the reserve changes nothing else).
echo "=== $(date -Is) exact7: C*18 at its natural cache size today; the candidate pinned like c18-e7"
PIN_CACHE=auto REF=c18-e7 bringup/lib/exact7.sh c18n-e7 $A 2>&1 | tail -9 | tee results/r21/res-exact7-c18n.txt
kc exact7-c18n
REF=c18-e7 bringup/lib/exact7.sh c18rp-e7 $B 2>&1 | tail -9 | tee results/r21/res-exact7-c18rp.txt
kc exact7-c18rp
for l in c18-e7 c18n-e7 c18r-e7 c18rp-e7; do echo "$l: $(grep -h 'expert cache [0-9]* slots' bringup/out/logs/prof/$l-x-math.err | head -1 | cut -c17-70)"; done | tee results/r21/res-exact7-slots.txt
SS=$(date -Iseconds | cut -c1-19)
for arm in "c18-a $A" "c18r-a $B" "c18r-b $B" "c18-b $A"; do
  set -- $arm
  bringup/lib/decscreen.sh r21-res-D-$1 $2 > logs/r21/res-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r21-res-F-$1 $2 > logs/r21/res-F-$1.log 2>&1
  echo "=== $(date -Is) arm $1 done: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)"
  echo "$(date -Is) r21-res-$1 5080_used_MiB=$(nvidia-smi --id=GPU-UUID-RTX5080 --query-gpu=memory.used --format=csv,noheader,nounits) apps=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader | tr '\n' ';')" >> logs/r21/display.log
done
kc speed
SINCE=$SS $PY bringup/lib/ab_table.py C18=r21-res-D-c18-a,r21-res-D-c18-b C18R=r21-res-D-c18r-a,r21-res-D-c18r-b > results/r21/res-dec.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py C18=r21-res-F-c18-a,r21-res-F-c18-b C18R=r21-res-F-c18r-a,r21-res-F-c18r-b > results/r21/res-full.md 2>&1
for f in results/r21/res-dec.md results/r21/res-full.md; do echo "$f:"; grep -iE '^\| *(decode|ms per|ttft|total|hit)' $f | head -8; done
unset GUARD_VRAM_MIB
bringup/lib/phase_end.sh r21-res keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) reserve done"
