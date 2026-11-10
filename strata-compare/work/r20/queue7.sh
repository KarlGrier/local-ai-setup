#!/bin/bash
# queue7.sh - 2026-10-14: after queue6 (pid given), the greedy output check on b8-exact again (reserve 2213).
cd /home/USER/ai-speed-testing/strata-compare
while kill -0 "$1" 2>/dev/null; do sleep 10; done
work/r20/d_exact.sh > logs/r20/d_exact.console 2>&1
