#!/bin/bash
# quality_run.sh LABEL [ENGINE_LOG] — round 5, phase 5 against the server on 127.0.0.1:8081 (Strata or llama.cpp):
# the 5 quality prompts x 3 sampled runs (32,768-token cap) + the harder needle set (32K/64K/120K x 4 runs).
# Your chat settings are sent explicitly, so both engines sample alike: temperature 1.0 (the page's shared setting
# since 2026-09-28 18:29), top_p 0.95, top_k 20, min_p 0.05; reasoning = each server's default (xhigh).
set -u
L=$1; E=${2:-}
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
X='{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}'
for r in 0 1 2; do
  .venv/bin/python scripts/bench.py quality --config $L --base http://127.0.0.1:8081 --model x --rep $r \
    --session $L-quality ${E:+--engine-log $E} --extra "$X"
done
.venv/bin/python work/r5/needle2.py ask --base http://127.0.0.1:8081 --label $L --temperature 1.0
