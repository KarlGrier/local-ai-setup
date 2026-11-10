#!/bin/bash
# s2_screens.sh CAND [TAG] — round 16 step 2: the candidate (v0.1.41 + patches/r16p27, step 1's share setting) vs C*15
# (configs/Cstar15.json, served now) and C*14 (configs/Cstar14.json, for the 2-3 % question): A B C C B A (A = C*15,
# B = the candidate, C = C*14) on the LDR screen, the decode screen, the full screen and a TTFT screen (8K / 32K / 120K;
# work/r16/ttft3.sh), each a fresh guarded server, your config, the 20 GB floor.
# Tables -> results/r16/s2-{ldr,dec,full,ttft}-TAG.md (two-way: C*15 vs candidate; C*14 vs candidate).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
CAND=${1:?candidate config} TAG=${2:-c16}; P=$WS/configs/Cstar15.json; Q=$WS/configs/Cstar14.json; PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
mkdir -p logs/r16 results/r16
SS=$(date -Iseconds | cut -c1-19)
for arm in "c15-a $P" "$TAG-a $CAND" "c14-a $Q" "c14-b $Q" "$TAG-b $CAND" "c15-b $P"; do
  set -- $arm
  ls $WS/bringup/out/tmp/NEW-RELEASE-* 2>/dev/null | while read f; do [ -f $WS/bringup/out/tmp/release-seen-$(basename $f) ] || echo "NOTE: new release flag $(cat $f)"; done
  bringup/lib/ldrscreen.sh r16-s2-L-$1 $2 > logs/r16/s2-L-$1.log 2>&1
  bringup/lib/decscreen.sh r16-s2-D-$1 $2 > logs/r16/s2-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r16-s2-F-$1 $2 > logs/r16/s2-F-$1.log 2>&1
  work/r16/ttft3.sh r16-s2-T-$1 $2 > logs/r16/s2-T-$1.log 2>&1
  echo "=== $(date -Is) arm $1 done"
done
U=${TAG^^}
for ref in c15 c14; do R=${ref^^}
  SINCE=$SS $PY bringup/lib/ldr_table.py $R=r16-s2-L-$ref-a,r16-s2-L-$ref-b $U=r16-s2-L-$TAG-a,r16-s2-L-$TAG-b > results/r16/s2-ldr-$TAG-vs-$ref.md 2>&1
  SINCE=$SS $PY bringup/lib/ab_table.py $R=r16-s2-D-$ref-a,r16-s2-D-$ref-b $U=r16-s2-D-$TAG-a,r16-s2-D-$TAG-b > results/r16/s2-dec-$TAG-vs-$ref.md 2>&1
  SINCE=$SS $PY bringup/lib/ab_table.py $R=r16-s2-F-$ref-a,r16-s2-F-$ref-b $U=r16-s2-F-$TAG-a,r16-s2-F-$TAG-b > results/r16/s2-full-$TAG-vs-$ref.md 2>&1
  SINCE=$SS $PY work/r16/s2_ttft.py $R=r16-s2-F-$ref-a,r16-s2-F-$ref-b,r16-s2-T-$ref-a,r16-s2-T-$ref-b $U=r16-s2-F-$TAG-a,r16-s2-F-$TAG-b,r16-s2-T-$TAG-a,r16-s2-T-$TAG-b > results/r16/s2-ttft-$TAG-vs-$ref.md 2>&1
done
for f in results/r16/s2-*-$TAG-vs-*.md; do echo "$f: $(grep -iE '^\| *(decode|8k|32k|120k)' $f | head -4 | tr -s ' ' | tr '\n' ' ' | cut -c1-300)"; done
