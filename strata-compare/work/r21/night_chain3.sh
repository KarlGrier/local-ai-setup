#!/bin/bash
# night_chain3.sh (night_chain.sh resumed at its step 2) - 2026-10-16 night, in order after the C*18t vs NVFP4 A B B A (nv_vs_c18t.sh):
#   1 sampling_apply.sh (your sampling on every path), then C*18t restarted on 8080 and its start lines checked
#     (config defaults T 1.0 / 0.95 / 20 / 0.05 + the Chat settings) - stops the chain if not
#   2 harness_batch5.sh: OpenCode vs dsh Minimal on rt_effort at T 1.0, 2 runs each; C*18t back with the standing guard
#   3 effort_test.sh: C*18t, xhigh vs medium, h03 / h05 / h07 / h12 / c14 x 3
# The Q8_0 honesty run (q8_honesty.sh) is started after this chain ends.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
LOCK=tmp/suite/heavy.lock
step() { echo "=== $(date -Is) $*"; }
step "1 done by hand: sampling applied 21:49, C*18t restarted on 8080 at 21:53 with the config defaults T 1.0 / 0.95 / 20 / 0.05 + the Chat settings (night_chain2 stopped: the launcher took its wait loop's command line for a model server)"
step "2 harness rerun at T 1.0 (batch5)"
work/usability/harness_batch5.sh > logs/usability/batch5.log 2>&1
tail -14 logs/usability/batch5.log
flock -o $LOCK bringup/lib/phase_end.sh r21-batch5 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
step "3 effort test"
work/r21/effort_test.sh > logs/r21/effort_test.log 2>&1
tail -40 logs/r21/effort_test.log
grep -q "KERNEL CHECK FAILED" logs/r21/effort_test.log logs/usability/batch5.log && { step "kernel check failed - chain stopped"; exit 1; }
step "night_chain done"
