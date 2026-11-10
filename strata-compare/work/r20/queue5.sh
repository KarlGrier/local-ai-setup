#!/bin/bash
# queue5.sh - 2026-10-14: D after c_pp05.sh (pid given) - queue4 skipped D (d_conc.sh was not executable).
cd /home/USER/ai-speed-testing/strata-compare
while kill -0 "$1" 2>/dev/null; do sleep 10; done
work/r20/d_conc.sh > logs/r20/d_conc.console 2>&1
