#!/bin/bash
# b5b_gate.sh - round 19 Part B step 5b (the user's addition, 2026-10-11): the cost gate on two cards with upstream's
# sampling. STRATA_SPEC_PROB=1 alone (A, configs/r19-cand-spng.json) against STRATA_SPEC_PROB=1 + our cost gate (B,
# configs/r19-cand-sp.json), on the candidate (C*16.1's flags on v0.1.42, two cards), B A A B, a fresh guarded server per
# arm and per part: 1. the decode screen (decscreen.sh: long reasoning math + code, correctness x5, 32K + 768);
# 2. decode after long prompts (fullscreen.sh's method: warm-up, then 32K r0 and 120K r0, each + 768 decoded tokens).
# The user's bar for opening the cost-gate PR (pr18/gate): >= 2 % on two cards and decode after the 32K / 120K prompts
# not slower. The kernel log is checked after every server. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB SPEED_FILE
P=.venv/bin/python; R=results/r19; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - b5b stopped, nothing restarted"; exit 1; }; }
$P bringup/lib/mkcfg.py r19-cand-spng r19-cand-sp env-STRATA_COST_GATE \
  "_comment=Round 19 r19-cand-spng: the candidate with upstream's STRATA_SPEC_PROB=1 instead of our STRATA_SPEC_EXACT=1, without the cost gate"
$P -c "import json; e=json.load(open('configs/r19-cand-spng.json'))['env']; print('spng env: SPEC_PROB', e.get('STRATA_SPEC_PROB'), 'SPEC_EXACT', e.get('STRATA_SPEC_EXACT'), 'COST_GATE', e.get('STRATA_COST_GATE'))"
kc b5b-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SS=$(date -Iseconds | cut -c1-19)
for arm in gate-a nog-a nog-b gate-b; do
  case $arm in gate*) CFG=configs/r19-cand-sp.json;; *) CFG=configs/r19-cand-spng.json;; esac
  echo "=== $(date -Is) b5b $arm: decode screen ($CFG)"
  bringup/lib/decscreen.sh r19-b5g-D-$arm $CFG > logs/r19/b5g-D-$arm.log 2>&1
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
  kc r19-b5g-D-$arm
  echo "=== $(date -Is) b5b $arm: decode after 32K / 120K"
  L=r19-b5g-T-$arm; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  if bringup/lib/srv.sh start $L "$CFG"; then
    $P work/r5/warmup.py http://127.0.0.1:8081 > /dev/null
    B="$P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
    $B speed --sizes 32k --reps 0 > logs/r19/b5g-T-$arm.log 2>&1
    $B speed --sizes 120k --reps 0 >> logs/r19/b5g-T-$arm.log 2>&1
    bringup/lib/srv.sh stop
  else echo "$L DID NOT START"; fi
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
  kc $L
done
SINCE=$SS $P bringup/lib/ab_table.py SPEC_PROB=r19-b5g-D-nog-a,r19-b5g-D-nog-b SPEC_PROB+GATE=r19-b5g-D-gate-a,r19-b5g-D-gate-b | tee $R/b5b-gate-dec.md
SINCE=$SS $P bringup/lib/ab_table.py SPEC_PROB=r19-b5g-T-nog-a,r19-b5g-T-nog-b SPEC_PROB+GATE=r19-b5g-T-gate-a,r19-b5g-T-gate-b | tee $R/b5b-gate-long.md
bringup/lib/phase_end.sh r19-b5b keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc b5b-end
echo "=== $(date -Is) b5b done"
