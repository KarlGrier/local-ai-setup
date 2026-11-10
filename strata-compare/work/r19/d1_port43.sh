#!/bin/bash
# d1_port43.sh - round 19 Part D 1: C*17's series on v0.1.43 through the runbook (run r19e: clean clones, build, the release
# alone twice with C*17's settings, patched with every switch off = the release, each switch's gate, then every switch on
# vs C*17's exact7 hashes, RB_REF=c17x-e7, with every v0.1.43 default as shipped). Kernel check after each stage. Ends
# with the promoted build (C*17) on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc d1-start
echo "$(date -Is) PLANNED: Part D 1 (runbook r19e) stops 8080 between its steps" >> logs/r19/uptime-c17/events.log
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { echo "a model server is still running - stop"; exit 1; }
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
for st in "clone inspect fitplan pack build" stock patched patches; do
  bringup/runbook.sh r19e $st || { echo "=== $(date -Is) runbook r19e stopped at: $st"; tail -5 bringup/out/r19e/runbook.log; exit 1; }
  kc "d1-$(echo $st | cut -d' ' -f1)"
done
grep -E 'stock:|patched|patch |build:|all on' bringup/out/r19e/runbook.log | grep "$(date +%Y-%m-%d)" | cut -c1-300
T=$(git -C bringup/out/r19e/strata-patched rev-parse HEAD^{tree}); echo "patched tree $T (r19-port43: 1c4d1dbf5770ef4103234cbc5a2f4be62fa1fd8b)"
[ "$T" = 1c4d1dbf5770ef4103234cbc5a2f4be62fa1fd8b ] || { echo "TREE MISMATCH - stopped"; exit 1; }
cat bringup/out/r19e/exact7-cand.txt | tail -9 | tee results/r19/d1-e7-cand-vs-c17.txt
grep -h -E 'non-finite|NAN_GUARD|ADAPT_OVERLAP|adaptive copies|overlap' bringup/out/logs/prof/rb-r19e-cand-x-math.err | head -5 | cut -c1-200
bringup/lib/phase_end.sh r19-d1 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d1 done"
