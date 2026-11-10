#!/bin/bash
# q4budget10.sh — round 10 D.3: step the Q4 RAM budget up (24 -> 32 -> 40 -> 48 -> 56 GiB) on the base built with
# -DSTRATA_MMQ_KQUANTS=ON, --vram-reserve-mib 1000 from the start, each a guarded start check (load + one request);
# stop stepping when the guard stopped the server or the lowest MemAvailable fell below 23 GiB (the 20 GB floor with a
# little margin: "until MemAvailable gets close to the 20 GB floor"). Writes the chosen budget to work/r13/q4/budget.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
best=""
for b in 24 32 40 48 56; do
  work/r13/startcheck.sh Q4-$b configs/Q4-$b.json
  line=$(grep "srv-Q4-$b " logs/r13/guard/summary.txt | tail -1); echo "guard: $line"
  ma=$(echo "$line" | grep -o 'min_MemAvailable=[0-9.]*' | cut -d= -f2)
  if echo "$line" | grep -q GUARD-STOP || [ -z "$ma" ]; then echo "budget $b: guard stop or no reading - stop stepping"; break; fi
  best=$b
  if [ "$(echo "$ma < 31" | bc)" = 1 ]; then echo "budget $b: min MemAvailable $ma GiB - the next 8 GiB step would cross 23 GiB, stop"; break; fi
done
echo "${best:-24}" > work/r13/q4/budget; echo "chosen budget: $(cat work/r13/q4/budget) GiB"
