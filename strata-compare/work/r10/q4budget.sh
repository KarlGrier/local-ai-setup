#!/bin/bash
# q4budget.sh — round 9 Phase 0.4: step the Q4 RAM budget up (24 -> 32 -> 40 -> 48 GiB) on the STOCK binary with a start
# check each (guarded load + one request); stop stepping when the guard stopped the server or the lowest MemAvailable
# fell below 26 GiB (keeps the 20 GiB floor with margin). Writes the chosen budget to work/r10/q4/budget.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
best=""
for b in 24 32 40 48; do
  work/r10/startcheck.sh Q4s-$b configs/Q4s-$b.json
  line=$(grep "srv-Q4s-$b " logs/r10/guard/summary.txt | tail -1); echo "guard: $line"
  ma=$(echo "$line" | grep -o 'min_MemAvailable=[0-9.]*' | cut -d= -f2)
  if echo "$line" | grep -q GUARD-STOP || [ -z "$ma" ] || [ "$(echo "$ma < 26" | bc)" = 1 ]; then echo "budget $b: stop stepping (min MemAvailable $ma GiB)"; break; fi
  best=$b
done
echo "${best:-24}" > work/r10/q4/budget; echo "chosen budget: $(cat work/r10/q4/budget) GiB"
