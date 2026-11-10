#!/bin/bash
# switch-gap10b.sh - round 22 (10-23 11:1x), the user after gap 10: "Switch before stage 2" - gap 10's checks all passed
# except my tool-call rule, which counted 3 max_tokens cut-offs as malformed (identical on the served build). A short gap:
# port_gap4.sh begin, work/r22/switch021m.sh (configs/P021m.json the default; port_gap4.sh's sha), port_gap4.sh end
# (starts P021m on 8080, checks its sha and the parking policy, releases the queue hold); the switch time in both NOTES.md.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
S=$WS/results/r22/gap10/summary.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
work/r22/port_gap4.sh begin "the switch to P021m (the continuation fix), the user after gap 10" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the switch gap did not open"; exit 1; }
bringup/lib/kcheck.sh r22g10b-open || { say "KERNEL CHECK FAILED at the switch gap's start - stopped, gap open"; exit 3; }
if work/r22/switch021m.sh 2>&1 | tee -a $S; then
  # 10-23: the first run ended the gap 1 s after begin, while the old server's guard was still exiting, and logged a
  # switch that had not happened: wait for every guard / server of the old build first, and log only when end succeeded
  for _ in $(seq 60); do pgrep -f "engine-r22p021[n]/strata|strata-r22p021[n]/serve" > /dev/null || break; sleep 2; done
  work/r22/port_gap4.sh end 2>&1 | tee -a $S || { say "port_gap4.sh end failed - no switch logged; 8080 may be down"; exit 1; }
  sha=$(grep -a "^8080: server" logs/run/strata-ensure.log | tail -1 | grep -o "sha [0-9a-f]*" | cut -d' ' -f2)
  T=$(date '+%F %H:%M:%S')
  printf '\n10-23 SWITCH %s: 8080 runs P021m (P021n as served since gap 9, no forced --pcie-frac 0, + the answer_room continuation fix in its minimal form: branch r22-port021-cont2 = P021n + a653ae6c; engine %s; configs/P021m.json). Phase 4 runs from here are on P021m (item 4 stage 2 onward); stage 3 and earlier ran on P021n / P021. Rollback: STRATA_CONFIG=configs/P021n.json (engine-r22p021n 68befe4e03bf; or switch-model.sh / run-strata.sh *.before-p021m). Checks: strata-compare results/r22/gap10/summary.txt (the tool-call rule re-judged: both builds 21 valid, 3 cut off at max_tokens, 0 malformed).\n' \
    "$T" "$sha" | tee -a /home/USER/ai/deep-research/NOTES.md >> NOTES.md
  say "switch logged at $T (both NOTES.md)"
else
  say "switch021m.sh failed - P021n back"; work/r22/port_gap4.sh end 2>&1 | tee -a $S
fi
bringup/lib/kcheck.sh r22g10b-end && say "kcheck clean" || say "KCHECK FAILED at the end"
