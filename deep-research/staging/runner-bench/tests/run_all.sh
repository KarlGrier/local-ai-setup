#!/bin/bash
# staging/runner-bench offline tests (10-29), all at nice 19: no GPU, no model, no services, no live file written.
# Temp folders go to $TMPDIR (default /tmp) and are removed. ~1.5 min.
set -e
PY=/home/USER/ai/deep-research/.venv/bin/python
S=/home/USER/ai/deep-research/staging/runner-bench
echo "== bash -n"; bash -n "$S/run-ldr.sh" && bash -n "$S/tools/bench2-queue.sh" && echo "ok: run-ldr.sh, bench2-queue.sh"
echo "== py_compile"; "$PY" -I -B -c "import ast, sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]; print('ok:', len(sys.argv) - 1, 'files')" \
  "$S/tools/ldr_runfiles.py" "$S/tools/research-runner.py" "$S/tools/bench2.py" "$S/item7/tools/paid_budget.py"
for t in test_runfiles test_runner test_queue; do
  echo "== $t"; nice -n 19 "$PY" -I -B "$S/tests/$t.py" 2>/dev/null | tail -n 1
done
echo "== item 7's own tests with the staged paid_budget.py"; "$S/tests/run_item7_tests.sh"
# dry check on the live paths, read-only: today's LDR (no run/ldr.modelprofile, no profiles/ before C3) fits flash-next
echo "== dry check, live run/ (read-only)"
"$PY" -I -B "$S/tools/ldr_runfiles.py" mp-check --want flash-next && echo "ok: today's LDR fits flash-next (no restart for the model profile)"
echo "paid-run.json: $("$PY" -I -B "$S/tools/ldr_runfiles.py" paid-show)"
