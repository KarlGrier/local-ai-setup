#!/bin/bash
# night_chain.sh - 2026-10-16 night, in order after the C*18t vs NVFP4 A B B A (nv_vs_c18t.sh):
#   1 sampling_apply.sh (your sampling on every path), then C*18t restarted on 8080 and its start lines checked
#     (config defaults T 1.0 / 0.95 / 20 / 0.05 + the Chat settings) - stops the chain if not
#   2 harness_batch5.sh: OpenCode vs dsh Minimal on rt_effort at T 1.0, 2 runs each; C*18t back with the standing guard
#   3 effort_test.sh: C*18t, xhigh vs medium, h03 / h05 / h07 / h12 / c14 x 3
# The Q8_0 honesty run (q8_honesty.sh) is started after this chain ends.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
LOCK=tmp/suite/heavy.lock
step() { echo "=== $(date -Is) $*"; }
while kill -0 558840 2>/dev/null; do sleep 30; done
grep -q "nv_vs_c18t done" logs/r21/nv_vs_c18t.log || { step "nv_vs_c18t.sh did not finish cleanly - chain stopped"; exit 1; }
step "1 sampling"
flock -o $LOCK work/r21/sampling_apply.sh || { step "sampling_apply failed - chain stopped"; exit 1; }
# a real restart, so the edited config is read (its standing guard ends with it; phase_end attaches a new one)
flock -o $LOCK bash -c 'STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
  for i in $(seq 60); do pgrep -f "^[^ ]*/strata --serve" > /dev/null || break; sleep 1; done
  bringup/lib/phase_end.sh r21-sampling keep 2>&1' | grep -E "stopped|phase end|answered|8080:|GUARD|FAILED"
L=$(ls -t logs/run/strata_*_8080.log | head -1)
grep -E '^\[strata\] (sampling defaults|other apps use)' $L | sed "s|^|8080 ($(basename $L)): |"
grep -q '^\[strata\] sampling defaults from the config: temperature=1.0, top_p=0.95, top_k=20, min_p=0.05' $L && \
  grep -q '^\[strata\] other apps use the Chat settings: .*temperature=1.0, top_p=0.95, top_k=20' $L || \
  { step "8080 does not start with your sampling - chain stopped"; exit 1; }
step "2 harness rerun at T 1.0 (batch5)"
work/usability/harness_batch5.sh > logs/usability/batch5.log 2>&1
tail -14 logs/usability/batch5.log
flock -o $LOCK bringup/lib/phase_end.sh r21-batch5 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
step "3 effort test"
work/r21/effort_test.sh > logs/r21/effort_test.log 2>&1
tail -40 logs/r21/effort_test.log
grep -q "KERNEL CHECK FAILED" logs/r21/effort_test.log logs/usability/batch5.log && { step "kernel check failed - chain stopped"; exit 1; }
step "night_chain done"
