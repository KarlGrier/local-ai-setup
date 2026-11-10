#!/bin/bash
# Item 7d offline tests (no network beyond 127.0.0.1, temp files under staging/item7d/scratch, fake keys only): the staged
# search_route / paid_search / s2_search with the LIVE exa_fallback / tavily_fallback / paid_budget / paid_cache, plus
# item 7's own suites run against the staged files (regression: everything 7a-7c relied on still holds).
set -e
PY=/home/USER/ai/deep-research/.venv/bin/python
T=/home/USER/ai/deep-research/staging/item7d/tests
for t in test_select test_paid_search_7d test_s2; do
  nice -n 19 "$PY" -I -B "$T/$t.py" | tail -n 1
done
nice -n 19 "$PY" -I -B "$T/item7_regression.py" | tail -n 1
