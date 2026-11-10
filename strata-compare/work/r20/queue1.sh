#!/bin/bash
# queue1.sh - 2026-10-14: run in order (each takes the heavy lock itself): c_llama.sh (rerun) then d_conc.sh.
cd /home/USER/ai-speed-testing/strata-compare
while pgrep -f "work/r20/c_probe3.sh" > /dev/null; do sleep 5; done
work/r20/c_llama.sh > logs/r20/c_llama2.console 2>&1
work/r20/d_conc.sh > logs/r20/d_conc.console 2>&1
