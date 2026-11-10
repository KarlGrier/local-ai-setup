#!/bin/bash
# Stuck-run watchdog tests (staged 11-03). Offline: no network, no LDR, no live file written; temp files only under
# staging/watchdog/scratch (removed by each test). Runs the STAGED tools/ldr-client.py, bench2.py, bench2-queue.sh.
set -e
PY=/home/USER/ai/deep-research/.venv/bin/python
T=/home/USER/ai/deep-research/staging/watchdog/tests
for t in test_watchdog test_client_loop test_bench2_rc test_queue; do
  nice -n 19 "$PY" -I -B -W ignore "$T/$t.py" | tail -n 1
done
