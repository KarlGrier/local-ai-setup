#!/bin/bash
# conc18.sh - Round 20 item 4: concurrency on C*18, the served config only (your rule: no --batch arms unless the release
# notes change batching or expert sharing; v0.1.43.1-0.1.44.1 do not for one GPU + helper). N = 1, 2, 4, 8 simultaneous
# requests, 2 repetitions (1,2,4,8 then 8,4,2,1), decode-style then ~27.7K-token agent-style prompts with tools
# (work/r20/conc.py, D's driver and prompts). Arms on config copies on 8081 (logs only differ): c171 = C*17.1 as served
# again (D's numbers were taken with the monitor on the iGPU; it is on the 5080 now), then c18 = C*18 as served.
# The standing 20 GiB MemAvailable floor (guard default); kernel check and display state after each server; C*17.1 /
# the promoted build back on 8080 at the end (phase end).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
PY=$WS/suite/.venv/bin/python
step() { echo "=== $(date -Is) $*"; }
G0=GPU-UUID-RTX5080
disp() { echo "$(date -Is) $1 display_active=$(nvidia-smi --id=$G0 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=$G0 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc '/strata --serve')" | tee -a logs/r20/display.log; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; disp "$1"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-conc18-start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is running - stop"; exit 1; }
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
.venv/bin/python - <<'PY'
import json
from pathlib import Path
C = Path("/home/USER/ai-speed-testing/strata-compare/configs")
for arm, src in (("c171", "Cstar171"), ("c18", "Cstar18")):
    c = json.loads((C / f"{src}.json").read_text())
    c.update(log=f"/home/USER/ai-speed-testing/strata-compare/logs/r20/engine-conc-{arm}.log", fallback=None)
    c["_comment"] = f"2026-10-15 Round 20 concurrency, a copy of configs/{src}.json as served; only the log differs"
    (C / f"r20-conc-{arm}.json").write_text(json.dumps(c, indent=1) + "\n")
    (C / f"r20-conc-{arm}.shared-settings.json").write_text((C / f"{src}.shared-settings.json").read_text())
PY
C="$PY work/r20/conc.py run --endpoint http://127.0.0.1:8081"
for arm in ${ARMS:-c171 c18}; do
  step "arm $arm"
  : > logs/r20/engine-conc-$arm.log
  bringup/lib/with_server.sh 9>&- conc-$arm configs/r20-conc-$arm.json -- \
    "$C --arm r20-$arm --kind decode && $C --arm r20-$arm --kind agent" 2>&1 | grep -vE '^\[strata\]'
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-230
  grep -hE "expert cache (auto|[0-9]+ slots)|filling the GPU's expert cache" logs/r20/engine-conc-$arm.log | head -3 | cut -c1-200
  srv_gone || step "server still running after $arm"
  kc r20-conc-$arm
done
for k in decode agent; do $PY work/r20/conc.py table --kind $k --arms base,r20-c171,r20-c18 2>&1; done
bringup/lib/phase_end.sh r20-conc18 keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc r20-conc18-end
step "conc18 done"
