#!/bin/bash
# sp_recheck.sh - round 19: C*17's acceptance suite failed one sampler row - arith-j3 at T 0.6 (the tie inside a speculative
# window) '=' 125 vs 102.0, ' ' 72 vs 95.0 of 197 on path, p = 0.001 (criterion p >= 0.01; the other 5 cases 0.06-0.92; C*16.1
# 0.229, B3's share-0.4 suite with our exact sampling 0.820). Bias or chance (min p <= 0.001 of 6 cases under the null:
# ~0.6 %)? The same case with 2,000 samples on C*17's twin as the suite runs it (twin17: STRATA_SPEC_PROB + our cost gate)
# and with the gate off (twin17-nogate: STRATA_SPEC_PROB alone), each with its own probabilities (strata_logp, force=N).
# Kernel log checked after each server. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; O=$WS/results/r19/sp-recheck; mkdir -p $O
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
cp bringup/out/accept/acc-c17/sp/sp-cases.json bringup/out/accept/acc-c17/sp/sp-llama.json $O/
kc spchk-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
TW=$WS/tmp/r19/meas3
for arm in gate nogate; do
  case $arm in gate) CFG=configs/twin17.json;; *) CFG=configs/twin17-nogate.json;; esac
  rm -f $O/sp-strata-r19-spchk-$arm.jsonl
  bringup/lib/with_server.sh r19-spchk-$arm $CFG -- "SP_DIR=$O SP_LABEL=r19-spchk-$arm STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 2000 0.6 arith-j3 > $O/strata-$arm.txt 2>&1; \
    SP_DIR=$O SP_LABEL=r19-spchk-$arm STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $O/logp-$arm.txt 2>&1; \
    grep -c 'cost-aware draft length ON' \$ELOG | sed 's/^/gate ON lines in the engine log: /'" 2>&1 | grep -E 'start|done|gate ON'
  SP_DIR=$O SP_LABEL=r19-spchk-$arm STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-$arm.txt 2>&1
  echo "--- $arm:"; grep -E 'arith-j3' $O/analyze-own-$arm.txt
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150
  kc spchk-$arm
done
bringup/lib/phase_end.sh r19-spchk keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) sp_recheck done"
