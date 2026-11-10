#!/bin/bash
# Item 7 offline tests (no network beyond 127.0.0.1, temp files only, no keys): run them all at low priority.
set -e
PY=/home/USER/ai/deep-research/.venv/bin/python
for t in test_paid_budget test_route test_cache test_paid_search test_tracker; do
  nice -n 19 "$PY" -I -B "/home/USER/ai/deep-research/staging/item7/tests/$t.py" | tail -n 1
done
