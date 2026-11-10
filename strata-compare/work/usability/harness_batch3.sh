#!/bin/bash
# harness_batch3.sh - the rest of batch 2 after Strata's engine was stopped at 20:47 by the round-20 phase-end guard
# (RTX 5080 free VRAM 176 MiB < 300): OpenCode and Codex rt_effort r2 again (no request reached Strata), then the runs
# batch 2 had not started. Each run first checks that Strata answers; if not, the batch stops.
set -u
W=/home/USER/ai-speed-testing/strata-compare/work/usability
P=/home/USER/ai-speed-testing/strata-compare/suite/.venv/bin/python
alive() { curl -s -m 120 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"Say OK."}],"max_tokens":16,"reasoning_effort":"none"}' | grep -q '"finish_reason"'; }
run() { alive || { echo "=== $(date -Is) STRATA NOT ANSWERING before $1 $2 $3 - batch3 halted"; exit 1; }
        echo "=== $(date -Is) $1 $2 $3"; $P $W/harness_run.py $1 $2 --tag $3 2>&1 | tail -3; }
for a in opencode codex dsh-minimal dsh-standard; do run $a rt_effort r2; done
for t in a1_inventory a2_textstats a3_cronlite rt_effort; do run dsh-ptc $t r1; done
echo "=== $(date -Is) batch3 done"
