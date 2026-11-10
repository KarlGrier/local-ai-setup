#!/bin/bash
# queue2.sh - 2026-10-14: after c_llama.sh (pid given), c_llama_dense.sh, then d_conc.sh.
cd /home/USER/ai-speed-testing/strata-compare
while kill -0 "$1" 2>/dev/null; do sleep 5; done
work/r20/c_llama_dense.sh > logs/r20/c_llama_dense.console 2>&1
work/r20/d_conc.sh > logs/r20/d_conc.console 2>&1
