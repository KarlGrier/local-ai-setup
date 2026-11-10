#!/bin/bash
# sp_stock.sh - round 19: the near-tie bias on upstream's code alone (for an issue, only if the ground truth on C*17's twin
# is ~52 % and STRATA_SPEC_PROB alone ~60 %): the stock twin (stock v0.1.42 + the 4 MEASUREMENT commits = the probe's
# hooks only; tmp/r19/stockmeas, tree 4ef08685), two cards, this PC's flags minus the local ones, prompt share 0,
# --adapt-swaps 0: arith-j3 at T 0.6, 2,000 samples with STRATA_SPEC_PROB=1 and 2,000 with speculation off, each with its
# own probabilities. Kernel log checked after each server. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; O=$WS/results/r19/sp-recheck; TW=$WS/tmp/r19/stockmeas
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc spstock-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for arm in sp nospec; do
  L=r19-spchk-stock$arm; CFG=configs/r19-stocktwin-$arm.json; rm -f $O/sp-strata-$L.jsonl
  bringup/lib/with_server.sh $L $CFG -- "SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 2000 0.6 arith-j3 > $O/strata-stock$arm.txt 2>&1; \
    SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $O/logp-stock$arm.txt 2>&1; \
    echo \"request lines with drafts: \$(grep -E 'drafts accepted [0-9]+ of [1-9]' \$ELOG | wc -l) of \$(grep -c 'drafts accepted' \$ELOG)\"; \
    grep -m1 -E 'probabilistic draft acceptance' \$ELOG | cut -c1-120" 2>&1 | grep -E 'start|done|drafts|probabilistic'
  SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-stock$arm.txt 2>&1
  echo "--- stock $arm:"; grep -E 'arith-j3' $O/analyze-own-stock$arm.txt; grep arith-j3 $O/logp-stock$arm.txt | cut -c1-160
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc spstock-$arm
done
bringup/lib/phase_end.sh r19-spstock keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) sp_stock done"
