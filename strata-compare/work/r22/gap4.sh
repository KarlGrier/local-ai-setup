#!/bin/bash
# gap4.sh - round 22, the user's 10-20 morning item 3: before 0.2.1 is promoted, find its 1.7-2.0 % decode loss vs C*18t
# (gap 3). Time box about an hour, in a gap after the level replays. Decode screen only (~2.3 min an arm).
#   Found before the gap (no GPU): the pool is the same (15 workers on CPUs 1-15, host on 0, in both engines' logs);
#   0.2.1's server closes thinking at 3/4 of max_tokens ("answer_room", new since 0.1.45), so the decode screen's
#   4,096-token long reasoning was different work in the two arms (C*18t thinks 4,096 and stops on length; 0.2.1 thinks
#   3,072 and answers). New RTX 50 defaults that C*18t lacks: STRATA_SM120_PERF's set, MMVQ_IL_120, MMVQ_IL_WIDE.
#   step 1  A = C*18t, B = 0.2.1 + answer_room off (the same work), C = B + the new RTX 50 defaults off;
#           A B C C B A A B C C B A
#   step 2  only if C differs from B by 1 % or more and 15+ min are left: C1 = SM120_PERF=0 only, C2 = the two row
#           tables off only; C1 C2 C2 C1
# Then port_gap.sh end (C*18t back on 8080). A kernel error stops everything with the gap left open.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=.venv/bin/python; O=results/r22/gap4; S=$O/summary.txt; mkdir -p $O logs/r22
A=$WS/configs/Cstar18t.json B=$WS/configs/r22p021-ar0.json C=$WS/configs/r22p021-ar0-sm0.json
C1=$WS/configs/r22p021-ar0-sm0a.json C2=$WS/configs/r22p021-ar0-sm0b.json
T0=$(date +%s); BOX=3600
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g4-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
left() { echo $(( BOX - ($(date +%s) - T0) )); }
arm() {   # arm LABEL CONFIG
  bringup/lib/decscreen.sh r22-g4-$1 $2 > logs/r22/g4-$1.log 2>&1
  echo "arm $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc $1
}
dec_pct() { grep -E '^\| decode \(tok/s\)' "$1" | awk -F'|' '{print $5}' | tr -d ' %+'; }

work/r22/port_gap.sh begin "gap 4: the 0.2.1 decode loss (answer_room, RTX 50 defaults; 1 h box)" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open"; exit 1; }
kc open

say "step 1: A = C*18t, B = 0.2.1 answer_room off, C = B + RTX 50 defaults off"
SS=$(date -Iseconds | cut -c1-19); n=0
for x in "a1 $A" "b1 $B" "c1 $C" "c2 $C" "b2 $B" "a2 $A" "a3 $A" "b3 $B" "c3 $C" "c4 $C" "b4 $B" "a4 $A"; do
  set -- $x
  [ $(left) -lt 300 ] && { say "time box: stopping step 1 after $n arms"; break; }
  arm $1 $2; n=$((n + 1))
done
L() { seq 1 4 | sed "s/^/r22-g4-$1/" | paste -sd,; }   # r22-g4-a1,...,r22-g4-a4
SINCE=$SS $P bringup/lib/ab_table.py C18T=$(L a) P021AR0=$(L b) > $O/AvsB.md 2>&1
SINCE=$SS $P bringup/lib/ab_table.py P021AR0=$(L b) RTX50OFF=$(L c) > $O/BvsC.md 2>&1
for f in AvsB BvsC; do echo "-- $f"; grep -iE '^\| *(metric|decode|ms per|tokens per|acceptance|long|ttft|all req)' $O/$f.md | head -9; done | tee -a $S
d=$(dec_pct $O/BvsC.md); say "C vs B decode: ${d:-?} %"

if [ -n "$d" ] && awk -v d="$d" 'BEGIN{exit !(d >= 1.0 || d <= -1.0)}' && [ $(left) -ge 900 ]; then
  say "step 2: C1 = SM120_PERF=0 only, C2 = MMVQ_IL_120=0 + MMVQ_IL_WIDE=0 only"
  SS2=$(date -Iseconds | cut -c1-19)
  for x in "d1 $C1" "e1 $C2" "e2 $C2" "d2 $C1"; do set -- $x; [ $(left) -lt 240 ] && { say "time box: step 2 cut short"; break; }; arm $1 $2; done
  SINCE=$SS2 $P bringup/lib/ab_table.py SM120OFF=r22-g4-d1,r22-g4-d2 ROWSOFF=r22-g4-e1,r22-g4-e2 > $O/C1vsC2.md 2>&1
  grep -iE '^\| *(metric|decode|ms per|tokens per)' $O/C1vsC2.md | head -5 | tee -a $S
else
  say "step 2 skipped (C vs B under 1 %, or under 15 min left)"
fi

say "gap 4 done after $(( ($(date +%s) - T0) / 60 )) min - switching back"
PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1
work/r22/port_gap.sh end 2>&1 | tee -a $S
kc end
say "end"
