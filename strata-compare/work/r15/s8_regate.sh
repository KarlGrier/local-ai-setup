#!/bin/bash
# s8_regate.sh — round 15 step 8: C*15's gates differed from C*14's in two sampled tests (the stop test's "stopped early"
# count 156 vs a limit of 151.5 = 0.75 x its own control's 202 tokens, text and stop sequence right; 2 of 19 follow-ups
# fell back to an earlier checkpoint, re-reading 69 / 23 tokens). Both again on C*15 and on C*14, same method.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python
for x in "c15b configs/Cstar15.json" "c14b configs/Cstar14.json"; do
  set -- $x
  bringup/lib/with_server.sh RG-$1 $2 -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 $1 plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 $1" 2>&1 \
    | grep -E "follow-ups resumed|stoptest" | tee -a results/r15/s8-regate.txt
done
