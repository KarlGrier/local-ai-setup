#!/bin/bash
# harness_batch4.sh - r21 item 4: the real bug-fix task (rt_effort) again on C*18 + the think-fence fix (configs/Cstar18t.json
# on 8080), OpenCode and DeepSeek Harness Minimal, 2 runs each (tags r3, r4). The recorder (turnlog.py 8090 -> 8080)
# runs for the batch; each run first checks that Strata answers. Strata is left on 8080 with C*18t (the caller decides
# what stays).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
W=$WS/work/usability P=$WS/suite/.venv/bin/python
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
STRATA_CONFIG=configs/Cstar18t.json ./switch-model.sh strata 2>&1 | grep -E "running|config|health" | head -3
EXE=$(.venv/bin/python -c "import json; print(json.load(open('configs/Cstar18t.json'))['exe'])")
(GUARD_VRAM_MODE=warn60 GUARD_FOLLOW_PORT=8080 setsid nohup .venv/bin/python bringup/lib/guard.py r21-batch4 \
  --watch-pattern "$EXE --serve" > /dev/null 2>&1 < /dev/null &)
O=logs/usability/turns; echo batch4 > $O/LABEL
python3 $W/turnlog.py --listen 8090 --upstream 8080 --out $O > logs/usability/turnlog-batch4.log 2>&1 &
TL=$!
sleep 2
alive() { curl -s -m 180 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"Say OK."}],"max_tokens":16,"reasoning_effort":"none"}' | grep -q '"finish_reason"'; }
run() { alive || { echo "=== $(date -Is) STRATA NOT ANSWERING before $1 $2 $3 - batch4 halted"; kill $TL; exit 1; }
        echo "=== $(date -Is) $1 $2 $3"; $P $W/harness_run.py $1 $2 --tag $3 2>&1 | tail -3; }
for tag in r3 r4; do for a in opencode dsh-minimal; do run $a rt_effort $tag; done; done
kill $TL
GP=$(pgrep -f "bringup/lib/guard.py r21-batch4" | head -1); [ -n "$GP" ] && kill $GP   # the next phase end attaches the standing guard
echo "=== $(date -Is) batch4 done"
