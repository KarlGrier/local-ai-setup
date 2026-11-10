#!/bin/bash
# gap16-toolcalls.sh - round 22 gap 16, step 9b (Karl 10-30 12:3x, added to the switch rule before gap 16's results):
# "the port as served (recovery off) must not make more spurious calls or lose more real calls than P021m on that test.
# If P021m hasn't run it, run it in gap 16." P021m never ran it (gap 15 ran only the port, recovery on vs off).
# gap16.sh was already running, so this step is not in it: g16_rules.py decide runs it inside the gap (lock held, 8080
# stopped) before it decides, when gates.txt has no toolcalls line. The live tool-call test (work/r22/toolrecovery,
# 27 prompts x 2, the same seeds per prompt and repeat) on P021m's test form (r21n-candpm) and on the port as served
# (x28h: both switches, recovery off, conversation cache off); g16_rules.py toolcalls compares them and writes the gate.
# A kernel-check failure writes a FAIL gate (no switch) and exits 3.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=$WS/results/r22/gap16; S=$O/summary.txt; G=$O/gates.txt; C=$WS/configs; T=$WS/work/r22/toolrecovery
TO=$O/toolcalls; mkdir -p $TO/M $TO/X
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
[ -s tmp/port-gap.lockpid ] || { say "9b tool calls: no gap open - not run"; echo "toolcalls FAIL not run (no gap open)" >> $G; exit 1; }
say "9b live tool-call test (Karl 10-30): P021m test form (r21n-candpm) vs the port as served (x28h, recovery off), 27 prompts x 2, same seeds"
for a in M X; do
  case $a in M) cfg=$C/r21n-candpm.json;; X) cfg=$C/x28h.json;; esac
  bringup/lib/with_server.sh g16-tc-$a $cfg -- "$WS/.venv/bin/python -B $T/toolrecovery_live.py http://127.0.0.1:8081 --label g16-$a --reps 2 --out-dir $TO/$a" 2>&1 \
    | grep -E "TOTAL|ready|exited|refus|Error|GUARD" | tee -a $S
  bringup/lib/kcheck.sh "r22g16-tc-$a" || { say "KERNEL CHECK FAILED after the tool-call test $a - no switch"; echo "toolcalls FAIL kernel check after $a" >> $G; exit 3; }
done
MJ=$(ls -t $TO/M/live-g16-M-*.jsonl 2> /dev/null | head -1); XJ=$(ls -t $TO/X/live-g16-X-*.jsonl 2> /dev/null | head -1)
if [ -z "$MJ" ] || [ -z "$XJ" ]; then say "9b tool calls: a result file is missing"; echo "toolcalls FAIL a result file is missing" >> $G; exit 1; fi
$P -I $WS/work/r22/g16_rules.py toolcalls $MJ $XJ --gate toolcalls --gates $G 2>&1 | tee $TO/compare.txt | tee -a $S
