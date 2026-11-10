#!/bin/bash
# p2_gate2.sh - round 18 part 2.3: the cost gate, second version (the gate applies only to the requests STRATA_SPEC_PROB
# judges, so greedy requests keep --spec-min-p; the first version also changed greedy windows: exact7 2/7 with it on).
# After p2_b2_measure.sh: rebuild tmp/r18/pr-gate, the checks (exact7 off / on, exact7 with STRATA_SPEC_PROB=1 alone for
# the sampled items' reference, ctest, spec_prob_test), the measurement (stock main vs main + the patch, both arms with
# STRATA_SPEC_PROB=1), then a phase end. The first version's results: results/r18/prc-gate-v1.txt, ctest-gate-v1.txt.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 PROMPT_DIR=$WS/bringup/out/r16/prompts
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
GATEF=$WS/tmp/r18/pr-gate/data/cost_gate_flash_next_mtp.txt; PY=.venv/bin/python
while pgrep -f 'work/r18/p2_b2_measure.sh' > /dev/null; do sleep 30; done
echo "=== $(date -Is) PR gate v2: build"
# a second configure registers upstream's four native-expert tests (CMakeLists uses STRATA_NATIVE_EXPERTS before its option()),
# so ctest runs the same 99 tests as on the other two branches
cmake -S tmp/r18/pr-gate -B tmp/r18/pr-gate/build > /dev/null 2>&1 || echo "RECONFIGURE FAILED"
cmake --build tmp/r18/pr-gate/build -j16 2>&1 | grep -E "error|warning: unused|Linking CXX executable (strata|spec_prob_test)$" | head -20
[ "${PIPESTATUS[0]}" = 0 ] || { echo "BUILD FAILED"; bringup/lib/phase_end.sh r18-pr-gate2-buildfail 2>&1 | grep -E "phase end|answered|8080:"; exit 1; }
work/r18/pr_checks.sh gate tmp/r18/pr-gate "STRATA_SPEC_PROB=1 STRATA_COST_GATE=$GATEF"
$PY bringup/lib/mkcfg.py r18-prc-gate-sp r18-prc-main exe=$WS/tmp/r18/pr-gate/build/strata env.STRATA_SPEC_PROB=1 > /dev/null
REF=r18-e7-main bringup/lib/exact7.sh r18-e7-gate-sp configs/r18-prc-gate-sp.json 2>&1 | tail -8 | sed 's/^/spec_prob alone: /' | tee -a results/r18/prc-gate.txt
(cd tmp/r18/pr-gate && ./build/spec_prob_test 2>&1 | grep -E "cost gate|spec_prob_test:") | tee -a results/r18/prc-gate.txt
work/r18/pr_measure.sh gate tmp/r18/pr-gate/build/strata "STRATA_COST_GATE=$GATEF" "STRATA_SPEC_PROB=1"
bringup/lib/phase_end.sh r18-pr-gate2 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) p2_gate2 done"
