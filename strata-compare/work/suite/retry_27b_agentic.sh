#!/bin/bash
# retry_27b_agentic.sh - 2026-10-13 16:1x: or-qwen3.8-27b-full's 2 agentic answers lost to DeepInfra 429s in its finish
# phase (a3_cronlite r2, a2_textstats r2). The label's own command (asks only for missing answers, then grades), on
# the heavy lock like api_jobs' finish phase; the $15 stop counts from the label's spend so far.
set -u
cd /home/USER/ai-speed-testing/strata-compare
exec 9> tmp/suite/heavy.lock
flock 9
echo "### $(date -Is) retry (lock held)"
suite/run.sh --label or-qwen3.8-27b-full --endpoint openrouter:qwen/qwen3.8-27b --mode full --estimate-from c171-iq3s-quick 2>&1 | grep -vE 'batch .*in_progress'
echo "### $(date -Is) retry rc ${PIPESTATUS[0]}"
