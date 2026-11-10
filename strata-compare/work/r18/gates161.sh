#!/bin/bash
# gates161.sh LABEL CFG RTCFG BRCFG [REF] - round 18 (copy of work/r16/s3_gates.sh): the gate set for C*16.1; REF = C*16 ("c16"):
# the side-mixer fix is exact and the table bitwise, so C*16.1 must compute what C*16 computes. C*16.1 runs with the CPU
# share off, so the share-off duplicates of round 16 (CFG0, rep-s0) are left out.
#   exact7 (REF: C*16's gate run "c16"),
#   needles 12 x 6 (work/r5/needle2.py), Stop at 120K (work/r5/failures.py stop120k), #652 follow-ups + stop strings +
#   tool tags + #931 probe, repeat 3/3 (adaptive tier live), chat-cache round trips on the twin
#   (RTCFG: --adapt-swaps 0, STATE_HASH; round 16: pass the share-off twin R16RT-share0.json - the round trip tests the
#   cache's exactness, and the share's timing-dependent prompt rounding would differ between the direct and parked
#   builds), the browser test on a config copy (BRCFG).
# Output: results/r18/g-gates-LABEL.txt (+ the tools' own files)
set -u
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB LR_MAX   # round 15-16: IQ3_S keeps the 20 GB floor
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2 RT=$3 BR=$4 REF=${5:-c16}
export PROMPT_DIR=$WS/bringup/out/r16z/prompts RB_CACHE=$WS/tmp/r18 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
O=results/r18/g-gates-$L.txt; : > $O
P=.venv/bin/python
REF=$REF bringup/lib/exact7.sh $L $CFG 2>&1 | tail -8 | tee -a $O
bringup/lib/with_server.sh N-$L $CFG -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-$L --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee -a $O
bringup/lib/with_server.sh FAIL-$L $CFG -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
  | grep -E "PASS|FAIL" | sed "s/FAIL-$L/F-$L/g" | tail -10 | tee -a $O
bringup/lib/with_server.sh T-$L $CFG -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 $L plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 $L; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 $L 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 $L" 2>&1 \
  | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee -a $O
bringup/lib/repeat3.sh rep-$L $CFG 2>&1 | tail -1 | tee -a $O
for m in "direct small $L-direct1" "direct small $L-direct2" "park small $L-park" "editref small $L-editref"; do
  bringup/lib/with_server.sh RT-$L $RT -- "$P bringup/lib/roundtrip.py $m" > /dev/null 2>&1
done
$P bringup/lib/rt_compare.py $L > results/r18/g-roundtrip-$L.md 2>&1; tail -8 results/r18/g-roundtrip-$L.md | tee -a $O
bringup/lib/with_server.sh BR-$L $BR -- "$P work/r5/browser_test.py --engine-log \$ELOG --tag b$L" 2>&1 \
  | grep -E "^(PASS|FAIL)|passed|failed" | tail -50 > results/r18/g-browser-$L.txt
echo "browser: $(grep -c '^PASS' results/r18/g-browser-$L.txt) pass, $(grep -c '^FAIL' results/r18/g-browser-$L.txt) fail: $(grep '^FAIL' results/r18/g-browser-$L.txt | cut -c1-120 | tr '\n' ';')" | tee -a $O
