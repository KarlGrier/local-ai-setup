#!/bin/bash
# NOT RUN: Karl 10-28 skipped the pilot (all four kept, no drop step). Kept for the record only.
# p5-pilot.sh - Phase 5's difficulty pilot (Karl 10-28): one quick-profile run per new harder checkable question
# exactly as Jan's quick answers run (research-runner.py: the baseline profile = pristine LDR, LDR_QUICK_LIMITS=1 - no
# subtopic agents, at most 12 agent cycles - and LDR's quick mode). A question is dropped only if the quick profile answers it
# correctly with no hedge (graded on the Answer section). Holds run/bench.lock (Jan jobs wait); children get 9>&-.
# Restores LDR without the quick limits at the end. Output: results/p5pilot/<id>/ (ldr-client.py research).
set -u
WS=/home/USER/ai/deep-research
Q=$WS/results/bench2/hard-build-p5/questions-p5-extra.DRAFT.jsonl
LOG=$WS/results/bench2/hard-build-p5/pilot.log
cd $WS || exit 1
exec 9>$WS/run/bench.lock; flock 9
echo "$(date '+%F %T') pilot: lock held; LDR -> quick limits" >> $LOG
./run-ldr.sh stop >> $LOG 2>&1 9>&-
env -u LDR_SEARCH_FALLBACK -u LDR_RESEARCH_S2 LDR_DEEP_SETUP_PROFILE= LDR_DEEP_CRITIC= LDR_DEEP_VERIFY2= LDR_DEEP_TRIED= \
  LDR_DEEP_NOTYET= LDR_DEEP_CODE= LDR_DEEP_FIX= LDR_QUICK_LIMITS=1 LDR_PROFILE=baseline ./run-ldr.sh start >> $LOG 2>&1 9>&-
/usr/bin/python3 -I -c "import json,sys; [print(json.loads(l)['id'] + '\t' + json.loads(l)['question']) for l in open('$Q')]" |
while IFS=$'\t' read -r id question; do
  echo "$(date '+%F %T') pilot: $id" >> $LOG
  $WS/.venv/bin/python -I tools/ldr-client.py research p5pilot/$id "$question" --mode quick --max-minutes 25 >> $LOG 2>&1 9>&-
done
./run-ldr.sh stop >> $LOG 2>&1 9>&-
echo "$(date '+%F %T') pilot: done; LDR stopped (the next run starts it with its own settings)" >> $LOG
