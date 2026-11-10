#!/bin/bash
# night_chain4.sh - 2026-10-17 00:3x: batch5's two r5 runs again (harness_batch5b.sh, ~1 h; batch5's ran without the test
# venv), then the Q8_0 honesty run (q8_honesty.sh: decode screen, h03/h05/h07/h12 x 2 at xhigh, "high" if time before
# 10:00, C*18t back on 8080).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
step() { echo "=== $(date -Is) $*"; }
step "1 r5 runs again (batch5b)"
work/usability/harness_batch5b.sh > logs/usability/batch5b.log 2>&1
tail -8 logs/usability/batch5b.log
step "2 Q8_0 honesty"
work/r21/q8_honesty.sh > logs/r21/q8_honesty.log 2>&1
tail -30 logs/r21/q8_honesty.log
step "night_chain4 done"
