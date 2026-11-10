#!/bin/bash
# p2_b2_measure.sh - round 18 part 2.2: B.2's measurement refused at 08:46 (the needle server was still exiting; pr_measure.sh
# now waits up to 60 s). Runs it after p2_run.sh (side, gate) has ended, then a phase end.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
while pgrep -f 'work/r18/p2_run.sh' > /dev/null; do sleep 30; done
echo "=== $(date -Is) PR b2 measurement (re-run)"
work/r18/pr_measure.sh b2 tmp/r18/pr-b2/build/strata "STRATA_QSA_SPLIT_ATTN=1"
bringup/lib/phase_end.sh r18-pr-b2-measure 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) p2_b2_measure done"
