#!/bin/bash
# sgbudget39.sh — round 11 F (SG39-* configs); sgbudget.sh — round 10 (your addition): the same budget stepping as Q4 (q4budget10.sh) for the Signal pack: a guarded
# start check per budget (load + one request) 24 -> 32 -> 40 -> 48 -> 56 GiB; stops on a guard stop, an engine that
# refuses the file (reported: which tensor / format, then the test stops), or MemAvailable heading below 23 GiB.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
[ -f work/r13/signal/STOP ] && { echo "Signal test stopped at the packer: $(cat work/r13/signal/STOP)"; exit 0; }
best=""
for b in 24 32 40 48 56; do
  work/r13/startcheck.sh SG39-$b configs/SG39-$b.json 2>&1 | tee tmp/r13/sg-$b.out
  ELOG=$(.venv/bin/python -c "import json; print(json.load(open('configs/SG39-$b.json'))['log'])")
  line=$(grep "srv-SG39-$b " logs/r13/guard/summary.txt | tail -1); echo "guard: $line"
  ma=$(echo "$line" | grep -o 'min_MemAvailable=[0-9.]*' | cut -d= -f2)
  if ! grep -q "answered:" tmp/r13/sg-$b.out; then
    echo "budget $b: the engine did not answer - its log says:"; grep -iE 'error|unsupported|not supported|cannot|refus|type' $ELOG | tail -8
    [ -z "$best" ] && { echo "ENGINE REJECTED the Signal file at the first budget (see above); the Signal test stops here" | tee work/r13/signal/STOP; exit 0; }
    break
  fi
  if echo "$line" | grep -q GUARD-STOP || [ -z "$ma" ]; then echo "budget $b: guard stop - stop stepping"; break; fi
  best=$b
  if [ "$(echo "$ma < 31" | bc)" = 1 ]; then echo "budget $b: min MemAvailable $ma GiB - stop"; break; fi
done
echo "${best:-24}" > work/r13/signal/budget; echo "chosen budget: $(cat work/r13/signal/budget) GiB"
