#!/bin/bash
# token_gate2.sh - r21 item 4: the token gate on deterministic twins (TK18A2 / TK18B2: --adapt-swaps 0, --suffix-draft 0,
# STRATA_PREFILL_CPU_SHARE=0): A, A again (is the server deterministic?), then B; raw outputs compared A-A and A-B.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB LR_MAX
kc() { bringup/lib/kcheck.sh "r21-tg2-$1" || { echo "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
rm -rf results/r21/tk2-A results/r21/tk2-A2 results/r21/tk2-B
for arm in "TK2A configs/TK18A2.json results/r21/tk2-A" "TK2AA configs/TK18A2.json results/r21/tk2-A2" "TK2B configs/TK18B2.json results/r21/tk2-B"; do
  set -- $arm
  bringup/lib/with_server.sh $1 $2 -- ".venv/bin/python work/r21/think_tokens.py send $3" 2>&1 | grep -E "completion_tokens|srv-|done" | cut -c1-200
  kc $1
done
L1=$(ls -t bringup/out/logs/server_TK2A_*.log | head -1); L2=$(ls -t bringup/out/logs/server_TK2AA_*.log | head -1); L3=$(ls -t bringup/out/logs/server_TK2B_*.log | head -1)
echo "=== A vs A (determinism)"; .venv/bin/python work/r21/think_tokens.py compare results/r21/tk2-A results/r21/tk2-A2 $L1 $L2 | tee results/r21/think-token-gate2-AA.txt
echo "=== A vs B (the fix)"; .venv/bin/python work/r21/think_tokens.py compare results/r21/tk2-A results/r21/tk2-B $L1 $L3 | tee results/r21/think-token-gate2-AB.txt
bringup/lib/phase_end.sh r21-tg2 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) token_gate2 done"
