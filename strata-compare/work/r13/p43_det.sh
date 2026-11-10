#!/bin/bash
# p43_det.sh — round 13 Part 4.3: is exact7 repeatable on the Q4 file with --mmap-experts + the helper? Rehearsal B's
# patched-off run matched stock on 3/7; run stock and patched-off once more each with the runbook's environment.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/bringup/out/rehB; source $R/run.env
export EVICT_GLOB="$(dirname $RB_GGUF)/*.gguf" PROMPT_DIR=$R/prompts
export PIN_CACHE=$(.venv/bin/python -c "import json; print(min(3500, int(json.load(open('$R/fitplan.json'))['slots_5080'] * 0.9)))")
REF=rb-rehB-stock bringup/lib/exact7.sh rb-rehB-stock2 $R/configs/stock.json > $R/exact7-stock2.txt 2>&1; tail -1 $R/exact7-stock2.txt
REF=rb-rehB-poff bringup/lib/exact7.sh rb-rehB-poff2 $R/configs/patched-off.json > $R/exact7-poff2.txt 2>&1; tail -1 $R/exact7-poff2.txt
for f in stock stock2 poff poff2; do echo "$f $(grep -E '^rb-rehB' $R/exact7-$f.txt | awk '{printf "%s ", $3}')"; done
