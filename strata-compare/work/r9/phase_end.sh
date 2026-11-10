#!/bin/bash
# phase_end.sh NAME [keep] — round 9: "end every phase with the promoted build on 8080". Run through the queue (no other
# model server then): the guard's floors are checked before the load and the guard watches the engine after it; ./switch-model.sh strata starts the launchers' default
# (the promoted build) on 127.0.0.1:8080, the health endpoint and one short chat request must answer, the engine's
# binary is recorded. Without "keep" it is stopped again afterwards, because the next phase's measurements need the
# GPU (one model server at a time).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
N=$1 KEEP=${2:-}
CFG=$(grep -o 'CFG=\${STRATA_CONFIG:-[^}]*}' switch-model.sh | head -1 | sed 's/.*:-//; s/}//; s#\$WS#'$WS'#')
EXE=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['exe'])" "$CFG")
echo "=== $(date -Is) phase end $N: promoted build ($CFG) on 8080"
# the memory guard's floors before the load (MemAvailable >= 20 GiB, RTX 5080 >= 300 MiB free), then it watches the engine
MA=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
VF=$(nvidia-smi --id=GPU-UUID-RTX5080 --query-gpu=memory.free --format=csv,noheader,nounits)
echo "before load: MemAvailable $MA MiB, RTX 5080 free $VF MiB"
if [ "$MA" -lt 20480 ] || [ "$VF" -lt 300 ]; then echo "GUARD: below a floor, not starting"; exit 1; fi
# round 9 fix: the previous run's monitor ("--pid-pattern /strata --serve") can still be exiting, and the launcher's
# check for another model server matches its command line - wait for it (up to 60 s) instead of failing the start
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
./switch-model.sh strata 2>&1 | grep -v "^$" | tail -5
if [ "$KEEP" = keep ]; then   # round 9 fix: a kept server's guard runs detached (waiting on it blocked the queue)
  (setsid nohup .venv/bin/python work/r9/guard.py PHASE-END-$N --watch-pattern "$EXE --serve" > /dev/null 2>&1 < /dev/null &)
  GP=""
else
  .venv/bin/python work/r9/guard.py PHASE-END-$N --watch-pattern "$EXE --serve" > /dev/null 2>&1 &
  GP=$!
fi
curl -s -m 10 http://127.0.0.1:8080/health || { echo "PHASE END FAILED: nothing answers on 8080"; exit 1; }; echo
curl -s -m 120 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"Say OK."}],"max_tokens":64}' | \
  .venv/bin/python -c "import json,sys; d=json.load(sys.stdin); c=d['choices'][0]; print('answered:', c.get('finish_reason'), d.get('usage', {}).get('completion_tokens'), 'tokens')"
P=$(ss -H -ltnp "( sport = :8080 )" | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
E=$(pgrep -P "$P" -f 'strata --serve' | head -1)
echo "8080: server $P engine $E exe $(readlink /proc/$E/exe) sha $(sha256sum "$(readlink /proc/$E/exe)" | cut -c1-12)"
if [ "$KEEP" != keep ]; then
  STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
  echo "=== $(date -Is) phase end $N: stopped again for the next phase"
fi
[ -n "$GP" ] && { wait $GP 2>/dev/null || true; }
tail -1 logs/r9/guard/summary.txt
