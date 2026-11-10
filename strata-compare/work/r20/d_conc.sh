#!/bin/bash
# d_conc.sh - 2026-10-14 D: concurrency on C*17.1, on config copies (configs/Cstar171.json itself untouched).
# Arms (each a fresh guarded server on 8081): base (as served: the helper cache, one request at a time), b8 (--batch 8
# + the helper), b8-nohelp (--batch 8, the 5080 alone, tail skip 0), b8-mtp (--batch 8 --batch-mtp + the helper).
# Each: N = 1, 2, 4, 8 simultaneous requests, 2 repetitions (1,2,4,8 then 8,4,2,1), decode-style then agent-style.
# Then the output check (greedy, each prompt alone vs 8 together) on b8 and on b8-exact (docs/BATCHING.md's exactness
# settings), and the near-tie sampling probe (arith-j3, T 0.6, 2,000 samples) on the measurement twin with --batch 8:
# 8 in flight (batch slots) vs one at a time (the solo path, our exact sampling), with the twin's own probabilities.
# Kernel check after every server; C*17.1 back on 8080 at the end.  ARMS="..." limits the arms.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
PY=$WS/suite/.venv/bin/python
O=$WS/results/r20/conc; mkdir -p $O
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
back() { step "C*17.1 back on 8080"; ./switch-model.sh strata 9>&- 2>&1 | tail -3
         curl -s -m 10 http://127.0.0.1:8080/health; echo; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-d-start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1     # C*17.1 on 8080 comes back at the end
srv_gone || { step "a model server is running - stop"; exit 1; }
export GUARD_MEM_GIB=8 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
C="$PY work/r20/conc.py run --endpoint http://127.0.0.1:8081"
startlines() {   # what the engine says about slots, the helper and the expert cache
  grep -E "batch_slots|--batch|batch-mtp|slot|expert cache|helper|device1|TAIL_SKIP|tail skip|KV|kv" "$1" | grep -vE "^\[strata\] (reading|done)" | head -30 | cut -c1-240
}
for arm in ${ARMS:-b8 base b8-nohelp b8-mtp}; do
  step "arm $arm"
  : > logs/r20/engine-$arm.log
  bringup/lib/with_server.sh 9>&- d-$arm configs/r20-$arm.json -- \
    "$C --arm $arm --kind decode && $C --arm $arm --kind agent" 2>&1 | grep -vE '^\[strata\]'
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-220
  echo "--- engine start lines ($arm):"; startlines logs/r20/engine-$arm.log
  grep -E "strata batch:" logs/r20/engine-$arm.log | tail -3 | cut -c1-300
  srv_gone || step "server still running after $arm"
  kc r20-d-$arm
done

if [ -z "${ARMS:-}" ] || [ "${CHECKS:-1}" = 1 ]; then
  for arm in b8 b8-exact; do
    step "output check (greedy) on $arm"
    : > logs/r20/engine-$arm-greedy.log
    bringup/lib/with_server.sh 9>&- d-$arm-g configs/r20-$arm.json -- \
      "$C --arm $arm-greedy --kind decode --greedy --same-nonce --reps 1 --levels 1,8 --solo-n 8 --max-tokens 1024 && \
       $C --arm $arm-greedy --kind agent --greedy --same-nonce --reps 1 --levels 1,4 --solo-n 4 --max-tokens 1024" 2>&1 | grep -vE '^\[strata\]'
    tail -1 bringup/out/logs/guard/summary.txt | cut -c1-220
    for k in decode agent; do $PY work/r20/conc.py match --kind $k --solo $arm-greedy --batch $arm-greedy | tail -12; done
    srv_gone || step "server still running"
    kc r20-d-$arm-greedy
  done

  step "near-tie sampling probe on the twin with --batch 8"
  SPD=$WS/results/r20/sp-batch; mkdir -p $SPD
  cp results/r19/sp-recheck/sp-cases.json results/r19/sp-recheck/sp-llama.json $SPD/
  TW=$WS/tmp/r19/meas43
  bringup/lib/with_server.sh 9>&- d-twin-b8 configs/r20-twin-b8.json -- \
    "SP_DIR=$SPD SP_LABEL=batch8 STRATA_SERVE_TREE=$TW $PY work/r20/sp_conc.py http://127.0.0.1:8081 2000 0.6 arith-j3 8; \
     SP_DIR=$SPD SP_LABEL=solo STRATA_SERVE_TREE=$TW $PY work/r20/sp_conc.py http://127.0.0.1:8081 2000 0.6 arith-j3 1; \
     SP_DIR=$SPD SP_LABEL=batch8 STRATA_SERVE_TREE=$TW $PY bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081; \
     grep -cE 'strata batch:' \$ELOG | sed 's/^/batch window lines: /'" 2>&1 | grep -vE '^\[strata\]'
  cp $SPD/sp-strata-logp-batch8.json $SPD/sp-strata-logp-solo.json
  for L in batch8 solo; do
    SP_DIR=$SPD SP_LABEL=$L STRATA_SERVE_TREE=$TW $PY bringup/lib/sampling_probe.py analyze own > $SPD/analyze-own-$L.txt 2>&1
    echo "--- $L:"; grep -E 'arith-j3' $SPD/analyze-own-$L.txt
  done
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-220
  srv_gone || step "server still running"
  kc r20-d-twin
fi
for k in decode agent; do $PY work/r20/conc.py table --kind $k --arms $(for a in ${ARMS:-base b8 b8-nohelp b8-mtp}; do printf '%s,' $a; done | sed 's/,$//') 2>&1; done
back
kc r20-d-end
step "D done"
