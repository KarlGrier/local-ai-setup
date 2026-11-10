#!/bin/bash
# d_exact.sh - 2026-10-14 D: the greedy output check with docs/BATCHING.md's exactness settings (configs/r20-b8-exact.json,
# reserve 2213), each prompt alone then together; C*17.1 back on 8080 after.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
PY=$WS/suite/.venv/bin/python
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-dx-start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is running - stop"; exit 1; }
export GUARD_MEM_GIB=8 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
C="$PY work/r20/conc.py run --endpoint http://127.0.0.1:8081"
step "output check (greedy) on b8-exact"
bringup/lib/with_server.sh 9>&- d-b8-exact-g configs/r20-b8-exact.json -- \
  "$C --arm b8-exact-greedy --kind decode --greedy --same-nonce --reps 1 --levels 1,8 --solo-n 8 --max-tokens 1024 && \
   $C --arm b8-exact-greedy --kind agent --greedy --same-nonce --reps 1 --levels 1,4 --solo-n 4 --max-tokens 1024" 2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-220
for k in decode agent; do $PY work/r20/conc.py match --kind $k --solo b8-exact-greedy --batch b8-exact-greedy | tail -10; done
srv_gone || step "server still running"; kc r20-dx
step "C*17.1 back on 8080"; ./switch-model.sh strata 9>&- 2>&1 | tail -3; curl -s -m 10 http://127.0.0.1:8080/health; echo
step "d_exact done"
