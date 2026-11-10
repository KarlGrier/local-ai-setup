#!/bin/bash
# rollback_test.sh — round 9 copy of round 8 (round 7 fix of work/r6/rollback_test.sh) (round 6: after the launchers point at C*6, prove the rollback: 8080 -> C*5 (the round-5 build,
# ROUND 7 FIX: the round-6 version never switched - switch-model.sh keeps any running Strata whatever STRATA_CONFIG
# says (it compares the server KIND, not the config), so both "switches" left C*6 running. Each switch now stops 8080 first.
# Usage: rollback_test.sh [ROLLBACK_CFG] [DEFAULT_NAME] (defaults configs/Cstar5.json, the launchers' default).
# STRATA_CONFIG=configs/Cstar5.json), check it answers and runs engine-cstar5, then back to the default (C*6), check again.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
eng() { local p; p=$(ss -H -ltnp "( sport = :8080 )" | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); \
        local e; e=$(pgrep -P "$p" -f 'strata --serve' | head -1); \
        echo "server $p engine $e exe $(readlink /proc/$e/exe) sha $(sha256sum $(readlink /proc/$e/exe) | cut -c1-12) config $(tr '\0' ' ' < /proc/$p/cmdline | grep -o -- '--config [^ ]*')"; }
floors() {   # round 9: the memory guard's floors before every model load (MemAvailable >= 20 GiB, 5080 >= 300 MiB free)
  local ma vf; ma=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  vf=$(nvidia-smi --id=GPU-UUID-RTX5080 --query-gpu=memory.free --format=csv,noheader,nounits)
  echo "before load: MemAvailable $ma MiB, RTX 5080 free $vf MiB"
  if [ "$ma" -lt 20480 ] || [ "$vf" -lt 300 ]; then echo "GUARD: below a floor, not starting"; exit 1; fi; }
watch() {    # round 9: the guard watches the engine that now serves 8080 (detached; it ends with that engine)
  local p e; p=$(ss -H -ltnp "( sport = :8080 )" | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); e=$(pgrep -P "$p" -f 'strata --serve' | head -1)
  (setsid nohup .venv/bin/python bringup/lib/guard.py $1 --watch-pattern "$(readlink /proc/$e/exe) --serve" > /dev/null 2>&1 < /dev/null &); }
echo "=== $(date -Is) rollback: stop 8080, then STRATA_CONFIG=${1:-configs/Cstar5.json} ./switch-model.sh strata"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2   # round 7: switch-model.sh keeps ANY running Strata, whatever STRATA_CONFIG says
floors
t0=$(date +%s); STRATA_CONFIG=${1:-configs/Cstar5.json} ./switch-model.sh strata 2>&1 | tail -4; echo "switch took $(( $(date +%s) - t0 )) s"
watch ROLLBACK-old
eng
curl -s -m 60 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"What is 17*3? Answer with the number only."}],"max_tokens":400}' | .venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print('answer:', d['choices'][0]['message']['content'][:60].strip(), '| finish', d['choices'][0]['finish_reason'])"
nvidia-smi --query-compute-apps=pid,gpu_uuid,used_memory --format=csv,noheader
echo "=== $(date -Is) back to the default: stop 8080, then ./switch-model.sh strata"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
floors
t0=$(date +%s); ./switch-model.sh strata 2>&1 | tail -4; echo "switch took $(( $(date +%s) - t0 )) s"
watch ROLLBACK-default
eng
curl -s -m 60 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"What is 17*3? Answer with the number only."}],"max_tokens":400}' | .venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print('answer:', d['choices'][0]['message']['content'][:60].strip(), '| finish', d['choices'][0]['finish_reason'])"
nvidia-smi --query-compute-apps=pid,gpu_uuid,used_memory --format=csv,noheader
./switch-model.sh status 2>&1 | head -8
echo "=== $(date -Is) rollback test done"
