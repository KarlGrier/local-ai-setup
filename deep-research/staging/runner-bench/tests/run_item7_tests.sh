#!/bin/bash
# Item 7's own offline tests (staging/item7/tests, unchanged) against the paid_budget.py staged here (+ the stale check):
# a temp copy of staging/item7 with this paid_budget.py swapped in; the tests name their own folder, so the copy's
# paths are rewritten to the copy. Nothing else changes; staging/item7 itself is not touched.
set -e
PY=/home/USER/ai/deep-research/.venv/bin/python
SRC=/home/USER/ai/deep-research/staging/item7
T=$(mktemp -d "${TMPDIR:-/tmp}/item7-copy-XXXXXX")
trap 'rm -rf "$T"' EXIT
cp -r "$SRC/tools" "$SRC/tests" "$SRC/ldr" "$T/"
find "$T" -name __pycache__ -prune -exec rm -rf {} +
cp /home/USER/ai/deep-research/staging/runner-bench/item7/tools/paid_budget.py "$T/tools/paid_budget.py"
grep -rl "$SRC" "$T/tests" | xargs sed -i "s|$SRC|$T|g"
for t in test_paid_budget test_route test_cache test_paid_search test_tracker; do
  printf '%-18s ' "$t"; nice -n 19 "$PY" -I -B "$T/tests/$t.py" | tail -n 1
done
