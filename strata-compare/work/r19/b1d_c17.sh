#!/bin/bash
# b1d_c17.sh - round 19: C*17 corrected (our cost gate kept: r19-port3 = patches/r19p28g) through the runbook (run r19d: clean
# release alone with C*17's settings twice, patched with every switch off = the release, each remaining switch's gate),
# then the candidate (every switch on = C*17) twice: it must repeat itself 7/7 (its first exact7 is the new reference).
# Kernel log checked after each stage. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc b1d-start
echo "=== $(date -Is) b1d: 8080 stopped for the runbook"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
for st in "clone inspect fitplan pack build" stock patched patches; do
  bringup/runbook.sh r19d $st || { echo "=== $(date -Is) runbook r19d stopped at: $st"; tail -5 bringup/out/r19d/runbook.log; exit 1; }
  kc "b1d-$(echo $st | cut -d' ' -f1)"
done
grep -E 'stock:|patched|patch |build:' bringup/out/r19d/runbook.log | grep "$(date +%Y-%m-%d)" | cut -c1-300
T=$(git -C bringup/out/r19d/strata-patched rev-parse HEAD^{tree}); echo "patched tree $T (r19-port3: 6c7f161e353dd2205d12bbbd6f86d742140a879a)"
[ "$T" = 6c7f161e353dd2205d12bbbd6f86d742140a879a ] || { echo "TREE MISMATCH - stopped"; exit 1; }
export PROMPT_DIR=$WS/bringup/out/r19d/prompts
echo "=== $(date -Is) b1d: the candidate (C*17's settings, every switch on), twice"
REF=rb-r19d-stock bringup/lib/exact7.sh r19d-e7-cand bringup/out/r19d/configs/cand.json 2>&1 | tail -8 | tee results/r19/b1d-e7-cand.txt
kc r19d-e7-cand
REF=r19d-e7-cand bringup/lib/exact7.sh r19d-e7-cand2 bringup/out/r19d/configs/cand.json 2>&1 | tail -8 | tee -a results/r19/b1d-e7-cand.txt
kc r19d-e7-cand2
grep -h 'patch guards\|probabilistic draft\|CPU share\|cost-aware' bringup/out/logs/prof/r19d-e7-cand-s-math.err | head -4 | cut -c1-220 | tee -a results/r19/b1d-e7-cand.txt
bringup/lib/phase_end.sh r19-b1d keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) b1d done"
