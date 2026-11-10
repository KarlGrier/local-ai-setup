#!/bin/bash
# gap11.sh - round 22 gap 11 (10-23, the user after the switch: "fix the tool-call check so its cap doesn't cut off
# file-write calls (raise it to at least 4,096 tokens, or count a call cut off at the cap as "truncated", not
# "malformed"), and rerun it on the new build in the next gap for the record"). work/r22/toolcall_check.py now counts a
# call whose arguments stop at max_tokens (finish "length") as truncated; its 1,024 cap stays (it puts the call in
# answer_room's continuation pass; the shapes' own caps are 2,048-4,096). One run on the served build P021m (test form
# r21n-candpm: engine-r22p021m 7b38796237f5, no picture reader), 3 of each shape and cap. For the record only.
# Started by work/r22/gap11-wait.sh after phase 4's item 4 stage 2 (p4s4) has finished. Output: results/r22/gap11/.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=$WS/results/r22/gap11; S=$O/summary.txt; mkdir -p $O
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
work/r22/port_gap4.sh begin "gap 11: the corrected tool-call check on P021m, for the record" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
bringup/lib/kcheck.sh r22g11-open || { say "KERNEL CHECK FAILED at the start - stopped, the gap stays open (8080 down)"; exit 3; }
rm -f results/r22/gap10/toolcall-P021m.jsonl
bringup/lib/with_server.sh TC-P021m configs/r21n-candpm.json -- "$P work/r22/toolcall_check.py http://127.0.0.1:8081 P021m 3" 2>&1 \
  | grep -E "^(P021m |TOOLCALL)" | tee $O/toolcall-P021m.txt | tail -1 | tee -a $S
mv -f results/r22/gap10/toolcall-P021m.jsonl $O/ 2> /dev/null
bringup/lib/kcheck.sh r22g11-tc || say "KERNEL CHECK FAILED after the tool-call check"
for _ in $(seq 60); do pgrep -f "engine-r22p021[m]/strata --serve.*8081" > /dev/null || break; sleep 2; done
PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1
work/r22/port_gap4.sh end 2>&1 | tee -a $S || say "port_gap4.sh end FAILED - 8080 may be down"
bringup/lib/kcheck.sh r22g11-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 11 done after $(( ($(date +%s) - T0) / 60 )) min"
