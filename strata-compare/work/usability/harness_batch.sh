#!/bin/bash
# harness_batch.sh - the harness comparison, one run at a time (Strata answers one request at a time anyway).
# ARMS / TASKS may be overridden; results in tmp/usability/runs/<arm>-<task>-r1/result.json, summary lines here.
set -u
W=/home/USER/ai-speed-testing/strata-compare/work/usability
P=/home/USER/ai-speed-testing/strata-compare/suite/.venv/bin/python
for task in ${TASKS:-a1_inventory a2_textstats a3_cronlite rt_effort}; do
  for arm in ${ARMS:-opencode codex dsh-minimal dsh-standard}; do
    echo "=== $(date -Is) $arm $task"
    $P $W/harness_run.py $arm $task 2>&1 | tail -3
  done
done
echo "=== $(date -Is) batch done"
