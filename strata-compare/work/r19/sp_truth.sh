#!/bin/bash
# sp_truth.sh - round 19, the user's ground truth for the near-tie bias (arith-j3: '=' 59.6 % with STRATA_SPEC_PROB + our
# gate vs 51.8 % expected from the engine's own probabilities through the chain top_k -> top_p -> min_p -> temperature,
# the engine's documented non-speculative order, no penalties in the request):
#   1. the same build (C*17's twin), prompt and position with speculation OFF (twin17-nospec: gate off, --spec-min-p 2 so
#      no window extends while the drafter stays loaded, --suffix-draft 0): 2,000 samples at T 0.6 (the failing case's
#      temperature) and 2,000 at T 1.0 (the user's chat setting), its own probabilities; the engine log must show no drafts
#   2. C*17 as configured (twin17: STRATA_SPEC_PROB + our gate) at T 1.0, 2,000 samples (its own probabilities = the
#      0.6 run's, raw log-probabilities; the chain is applied per temperature)
# Kernel log checked after each server. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; O=$WS/results/r19/sp-recheck; TW=$WS/tmp/r19/meas3
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc sptruth-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SP="SP_DIR=$O STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py"
rm -f $O/sp-strata-r19-spchk-nospec.jsonl $O/sp-strata-r19-spchk-gate10.jsonl
bringup/lib/with_server.sh r19-spchk-nospec configs/twin17-nospec.json -- "SP_LABEL=r19-spchk-nospec $SP strata http://127.0.0.1:8081 2000 0.6 arith-j3 > $O/strata-nospec.txt 2>&1; \
  SP_LABEL=r19-spchk-nospec $SP strata http://127.0.0.1:8081 2000 1.0 arith-j3 >> $O/strata-nospec.txt 2>&1; \
  SP_LABEL=r19-spchk-nospec $SP strata_logp http://127.0.0.1:8081 > $O/logp-nospec.txt 2>&1; \
  echo \"requests with drafts accepted > 0 of: \$(grep -c 'drafts accepted' \$ELOG) request lines: \$(grep -E 'drafts accepted [0-9]+ of [1-9]' \$ELOG | wc -l)\"; \
  grep -c 'cost-aware draft length ON' \$ELOG | sed 's/^/gate ON lines: /'" 2>&1 | grep -E 'start|done|drafts|gate ON'
SP_LABEL=r19-spchk-nospec SP_DIR=$O STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-nospec.txt 2>&1
echo "--- nospec:"; grep -E 'arith-j3' $O/analyze-own-nospec.txt
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc sptruth-nospec
bringup/lib/with_server.sh r19-spchk-gate10 configs/twin17.json -- "SP_LABEL=r19-spchk-gate10 $SP strata http://127.0.0.1:8081 2000 1.0 arith-j3 > $O/strata-gate10.txt 2>&1; \
  grep -c 'cost-aware draft length ON' \$ELOG | sed 's/^/gate ON lines: /'" 2>&1 | grep -E 'start|done|gate ON'
cp $O/sp-strata-logp-r19-spchk-gate.json $O/sp-strata-logp-r19-spchk-gate10.json
SP_LABEL=r19-spchk-gate10 SP_DIR=$O STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-gate10.txt 2>&1
echo "--- gate, T 1.0:"; grep -E 'arith-j3' $O/analyze-own-gate10.txt
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc sptruth-gate10
bringup/lib/phase_end.sh r19-sptruth keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) sp_truth done"
