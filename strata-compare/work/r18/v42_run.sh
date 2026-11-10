#!/bin/bash
# v42_run.sh - round 18 part 2 on v0.1.42 (your 12:00 message): the three pull requests rebased onto v0.1.42 (61b3fb5d):
#   1. builds: stock v0.1.42 (tmp/r18/v42-main), v42-b2, v42-side, v42-gate (upstream's tests on; a second configure
#      registers the four native-expert tests), v42-b2-twin (B.2 + the teacher-force hooks, for its gate)
#   2. stock v0.1.42 exact7 twice (does it repeat itself?), then per PR: exact7 switch off / on + ctest (v42_checks.sh);
#      B.2's gate (teacher-forced NLL through the twin; needles); the gate's spec_prob_test + exact7 with SPEC_PROB alone
#   3. a phase end; then per PR the RTX 5080 alone against stock v0.1.42, tail skip on (upstream's default) and
#      STRATA_ROUTE_TAIL_SKIP=0 (v42_measure.sh), a phase end after each PR. Your served build is not changed.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 PROMPT_DIR=$WS/bringup/out/r16/prompts
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
PY=.venv/bin/python; GATEF=$WS/tmp/r18/v42-gate/data/cost_gate_flash_next_mtp.txt
pe() { bringup/lib/phase_end.sh r18-$1 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"; }
echo "=== $(date -Is) v42: builds"
work/r18/pr_build.sh tmp/r18/v42-main tmp/r18/v42-b2 tmp/r18/v42-side tmp/r18/v42-gate tmp/r18/v42-b2-twin
for T in v42-main v42-b2 v42-side v42-gate; do   # the second configure: ctest's 99 tests on every tree
  (cd tmp/r18/$T && nice -n 10 cmake -S . -B build > /dev/null 2>&1 && nice -n 10 cmake --build build -j 16 >> build.log 2>&1); echo "$T reconfigure rc $?"
done
for T in v42-main v42-b2 v42-side v42-gate v42-b2-twin; do [ -x tmp/r18/$T/build/strata ] || { echo "BUILD MISSING: $T"; pe v42-buildfail; exit 1; }; done
# the configs: the community report's stock flags with stock v0.1.42's engine and server
cp work/r17/cfg/cb-stock.json configs/r18v42-cb-two.json; cp work/r17/cfg/cb-stock.shared-settings.json configs/r18v42-cb-two.shared-settings.json
cp work/r17/cfg/cb-stock-5080.json configs/r18v42-cb-one.json; cp work/r17/cfg/cb-stock-5080.shared-settings.json configs/r18v42-cb-one.shared-settings.json
$PY bringup/lib/mkcfg.py r18v42-base-two r18v42-cb-two exe=tmp/r18/v42-main/build/strata server=tmp/r18/v42-main/serve/server.py
$PY bringup/lib/mkcfg.py r18v42-base-one r18v42-cb-one exe=tmp/r18/v42-main/build/strata server=tmp/r18/v42-main/serve/server.py
$PY bringup/lib/mkcfg.py r18v42-prc-main r18v42-base-two env.STRATA_PREFILL_CPU_SHARE=0 > /dev/null
echo "=== $(date -Is) v42: stock exact7 x2"
REF=r18-e7-main bringup/lib/exact7.sh r18v42-e7-main configs/r18v42-prc-main.json 2>&1 | tail -8 | sed 's/^/stock v0.1.42 vs stock v0.1.41: /' | tee results/r18/v42-stock-e7.txt
REF=r18v42-e7-main bringup/lib/exact7.sh r18v42-e7-main2 configs/r18v42-prc-main.json 2>&1 | tail -8 | sed 's/^/stock v0.1.42 again: /' | tee -a results/r18/v42-stock-e7.txt
(cd tmp/r18/v42-main && ctest --test-dir build -j1 --timeout 600 > $WS/results/r18/ctest-v42-main.txt 2>&1); tail -3 results/r18/ctest-v42-main.txt | sed 's/^/ctest main: /'
grep -E "\*\*\*Failed|Not Run|Timeout" results/r18/ctest-v42-main.txt | sed 's/^/ctest main failed: /'
echo "=== $(date -Is) v42: PR checks"
work/r18/v42_checks.sh b2 tmp/r18/v42-b2 "STRATA_QSA_SPLIT_ATTN=1"
CFG=configs/r18v42-prc-b2-on.json TFEXE=$WS/tmp/r18/v42-b2-twin/build/strata TREE=tmp/r18/v42-b2 bringup/patchtest.sh qsa_split_attn 2>&1 | tail -2 | tee -a results/r18/v42-prc-b2.txt
bringup/lib/with_server.sh r18v42-nd-b2 configs/r18v42-prc-b2-on.json -- ".venv/bin/python tmp/r18/v42-main/tools/needle_bench.py --url http://127.0.0.1:8081 --lengths 32k,128k --depths 10,50,90 --out results/r18/v42-needles-b2.json" 2>&1 | grep -E "FOUND|MISS" | tee -a results/r18/v42-prc-b2.txt
work/r18/v42_checks.sh side tmp/r18/v42-side "STRATA_SIDE_MIXER=2"
work/r18/v42_checks.sh gate tmp/r18/v42-gate "STRATA_SPEC_PROB=1 STRATA_COST_GATE=$GATEF"
$PY bringup/lib/mkcfg.py r18v42-prc-gate-sp r18v42-prc-main exe=tmp/r18/v42-gate/build/strata env.STRATA_SPEC_PROB=1 > /dev/null
REF=r18v42-e7-main bringup/lib/exact7.sh r18v42-e7-gate-sp configs/r18v42-prc-gate-sp.json 2>&1 | tail -8 | sed 's/^/spec_prob alone: /' | tee -a results/r18/v42-prc-gate.txt
(cd tmp/r18/v42-gate && ./build/spec_prob_test 2>&1 | grep -E "cost gate|spec_prob_test:") | tee -a results/r18/v42-prc-gate.txt
pe v42-checks
echo "=== $(date -Is) v42: measurements (the RTX 5080 alone)"
for TS in on 0; do work/r18/v42_measure.sh b2 tmp/r18/v42-b2/build/strata "STRATA_QSA_SPLIT_ATTN=1" "" $TS; done; pe v42-b2
for TS in on 0; do work/r18/v42_measure.sh side tmp/r18/v42-side/build/strata "STRATA_SIDE_MIXER=2" "" $TS; done; pe v42-side
for TS in on 0; do work/r18/v42_measure.sh gate tmp/r18/v42-gate/build/strata "STRATA_COST_GATE=$GATEF" "STRATA_SPEC_PROB=1" $TS; done; pe v42-gate
echo "=== $(date -Is) v42_run done"
