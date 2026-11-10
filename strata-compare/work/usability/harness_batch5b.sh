#!/bin/bash
# harness_batch5b.sh - 2026-10-17 00:30: batch5's r5 runs again. Those ran without the test venv (tmp/usability/venv-rt went with tmp/usability/
# at item 6 and was rebuilt only at 22:19), so .venv was a dangling link for the agents and grading failed; they are in
# tmp/usability/runs-invalid/ and logs/usability/turns-invalid/ as *-novenv. Otherwise as batch5: the real bug-fix task
# (rt_effort) at your sampling T 1.0 (OpenCode sends it; dsh gets it from Strata) on C*18t (configs/Cstar18t.json
# on 8080), OpenCode and DeepSeek Harness Minimal, 1 run each (tag r5). The recorder (turnlog.py 8090 -> 8080)
# runs for the batch; each run first checks that Strata answers. Strata is left on 8080 with C*18t (the caller decides
# what stays).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
exec 9> tmp/suite/heavy.lock; flock 9   # serialised with the other GPU jobs; children get 9>&-
W=$WS/work/usability P=$WS/suite/.venv/bin/python
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
STRATA_CONFIG=configs/Cstar18t.json ./switch-model.sh strata 9>&- 2>&1 | grep -E "running|config|health" | head -3
EXE=$(.venv/bin/python -c "import json; print(json.load(open('configs/Cstar18t.json'))['exe'])")
(GUARD_VRAM_MODE=warn60 GUARD_FOLLOW_PORT=8080 setsid nohup .venv/bin/python bringup/lib/guard.py r21-batch5b \
  --watch-pattern "$EXE --serve" > /dev/null 2>&1 < /dev/null 9>&- &)
O=logs/usability/turns; echo batch5b > $O/LABEL
python3 $W/turnlog.py --listen 8090 --upstream 8080 --out $O > logs/usability/turnlog-batch5b.log 2>&1 9>&- &
TL=$!
sleep 2
alive() { curl -s -m 180 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"Say OK."}],"max_tokens":16,"reasoning_effort":"none"}' | grep -q '"finish_reason"'; }
run() { alive || { echo "=== $(date -Is) STRATA NOT ANSWERING before $1 $2 $3 - batch5b halted"; kill $TL; exit 1; }
        echo "=== $(date -Is) $1 $2 $3"; $P $W/harness_run.py $1 $2 --tag $3 9>&- 2>&1 | tail -3; }
[ -x tmp/usability/venv-rt/bin/python ] || { echo "=== no test venv - batch5b halted"; kill $TL; exit 1; }
# ARMS=dsh-minimal: 10-17, OpenCode's r5 is done
for tag in r5; do for a in ${ARMS:-opencode dsh-minimal}; do run $a rt_effort $tag; done; done
kill $TL
GP=$(pgrep -f "bringup/lib/guard.py r21-batch5b" | head -1); [ -n "$GP" ] && kill $GP   # the next phase end attaches the standing guard
echo "=== $(date -Is) batch5b done"
# what each harness sent (recorded requests): your sampling expected from OpenCode, none from dsh (Strata's defaults)
for d in opencode-rt_effort-r5 dsh-minimal-rt_effort-r5; do
  f1=$(ls logs/usability/turns/$d/*.req.json.gz 2>/dev/null | head -1)
  [ -n "$f1" ] && echo "$d sent: $(zcat $f1 | python3 -c "import json,sys; b=json.load(sys.stdin); print({k: b.get(k) for k in ('temperature','top_p','top_k','min_p','reasoning_effort')})")"
done
