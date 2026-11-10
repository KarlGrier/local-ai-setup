#!/bin/bash
# harness_batch2.sh - second pass: dsh Standard on the repos with the compaction fix (r2), every harness on the real
# task again (r2: one run each was not enough after OpenCode's parse stop), and dsh PTC ("Code" mode, r1), since the
# other modes worked.
set -u
W=/home/USER/ai-speed-testing/strata-compare/work/usability
P=/home/USER/ai-speed-testing/strata-compare/suite/.venv/bin/python
run() { echo "=== $(date -Is) $1 $2 $3"; $P $W/harness_run.py $1 $2 --tag $3 2>&1 | tail -3; }
for t in a1_inventory a2_textstats a3_cronlite; do run dsh-standard $t r2; done
for a in opencode codex dsh-minimal dsh-standard; do run $a rt_effort r2; done
for t in a1_inventory a2_textstats a3_cronlite rt_effort; do run dsh-ptc $t r1; done
echo "=== $(date -Is) batch2 done"
