#!/bin/bash
# p1_screens.sh - round 18 part 1, the formal measurement: served decode screens (bringup/lib/decscreen.sh: fresh guarded
# server per arm, cold page cache, warm-up, long reasoning math + code to 4,096 tokens, correctness x5, a 32K prompt + 768;
# your config's sampling), A B B A per suspect on the r18 build (= C*16's tree; switches off = C*16):
#   S1 off vs STRATA_SIDE_IL=1   S2 off vs STRATA_QUANT_IL=1   S3 off vs STRATA_SIDE_MIXER=0
#   S4 off / both / C*14: A B C C B A (the combined fix and the gap that is left)
# Tables -> results/r18/p1-S*.md. 8080 must be stopped; the guard's 20 GiB / 300 MiB floors.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
PY=.venv/bin/python; C=configs; SS=$(date -Iseconds | cut -c1-19)
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
arm() {   # + the arena's huge-page share (work/r18/thp_sampler.sh), the last sample of the session
  work/r18/thp_sampler.sh logs/r18/thp-$1.txt & local TP=$!
  bringup/lib/decscreen.sh r18-$1 $C/$2.json > logs/r18/$1.log 2>&1
  kill $TP 2>/dev/null
  echo "$(date -Is) $1 done; $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150); THP: $(tail -1 logs/r18/thp-$1.txt | cut -d' ' -f4-)"
}
for S in ${STEPS:-S1 S2 S3 S4}; do
  case $S in
    S1) for a in off-a:r18-p1 side-a:r18-p1-side side-b:r18-p1-side off-b:r18-p1; do arm S1-${a%%:*} ${a#*:}; done
        SINCE=$SS $PY bringup/lib/ab_table.py OFF=r18-S1-off-a,r18-S1-off-b SIDE_IL=r18-S1-side-a,r18-S1-side-b > results/r18/p1-S1.md;;
    S2) for a in off-a:r18-p1 quant-a:r18-p1-quant quant-b:r18-p1-quant off-b:r18-p1; do arm S2-${a%%:*} ${a#*:}; done
        SINCE=$SS $PY bringup/lib/ab_table.py OFF=r18-S2-off-a,r18-S2-off-b QUANT_IL=r18-S2-quant-a,r18-S2-quant-b > results/r18/p1-S2.md;;
    S3) for a in off-a:r18-p1 sm0-a:r18-p1-sm0 sm0-b:r18-p1-sm0 off-b:r18-p1; do arm S3-${a%%:*} ${a#*:}; done
        SINCE=$SS $PY bringup/lib/ab_table.py SM2=r18-S3-off-a,r18-S3-off-b SM0=r18-S3-sm0-a,r18-S3-sm0-b > results/r18/p1-S3.md;;
    S5) for a in off-a:r18-p1 sf-a:r18-p1-sf sft-a:r18-p1-sft c14-a:Cstar14 c14-b:Cstar14 sft-b:r18-p1-sft sf-b:r18-p1-sf off-b:r18-p1; do arm S5-${a%%:*} ${a#*:}; done
        SINCE=$SS $PY bringup/lib/ab_table.py C16=r18-S5-off-a,r18-S5-off-b SIDE_FIXES=r18-S5-sf-a,r18-S5-sf-b SIDE_FIXES_TABLE=r18-S5-sft-a,r18-S5-sft-b C14=r18-S5-c14-a,r18-S5-c14-b > results/r18/p1-S5.md;;
    S4) for a in off-a:r18-p1 both-a:r18-p1-both c14-a:Cstar14 c14-b:Cstar14 both-b:r18-p1-both off-b:r18-p1; do arm S4-${a%%:*} ${a#*:}; done
        SINCE=$SS $PY bringup/lib/ab_table.py C16=r18-S4-off-a,r18-S4-off-b FIX=r18-S4-both-a,r18-S4-both-b C14=r18-S4-c14-a,r18-S4-c14-b > results/r18/p1-S4.md;;
  esac
  echo "=== $S"; cat results/r18/p1-$S.md | head -6
done
