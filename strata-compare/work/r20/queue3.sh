#!/bin/bash
# queue3.sh - 2026-10-14: after queue2 (pid given: c_llama_dense, D), the presence-penalty continuation (c_pp05.sh).
cd /home/USER/ai-speed-testing/strata-compare
while kill -0 "$1" 2>/dev/null; do sleep 10; done
work/r20/c_pp05.sh > logs/r20/c_pp05.console 2>&1
