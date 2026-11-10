#!/bin/bash
# p2_run.sh KEY... - round 18 part 2.2: for each chosen pull request, in order: the default-path / ctest checks
# (pr_checks.sh), the patch's own gate, then the measurement (pr_measure.sh: stock main vs main + the patch, A B B A, the
# 5080 alone and with the helper card, decode + prompt-read screens); a phase end after each pull request.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18
GATEF=$WS/tmp/r18/pr-gate/data/cost_gate_flash_next_mtp.txt
pe() { bringup/lib/phase_end.sh r18-$1 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"; }
for K in "$@"; do
  echo "=== $(date -Is) PR $K"
  case $K in
    b2)
      work/r18/pr_checks.sh b2 tmp/r18/pr-b2 "STRATA_QSA_SPLIT_ATTN=1"
      CFG=configs/r18-prc-b2-on.json TFEXE=$WS/tmp/r18/pr-b2-twin/build/strata TREE=tmp/r18/pr-b2 bringup/patchtest.sh qsa_split_attn 2>&1 | tail -2 | tee -a results/r18/prc-b2.txt
      bringup/lib/with_server.sh r18-nd-b2 configs/r18-prc-b2-on.json -- ".venv/bin/python bringup/out/r16/strata-stock/tools/needle_bench.py --url http://127.0.0.1:8081 --lengths 32k,128k --depths 10,50,90 --out results/r18/needles-b2.json" 2>&1 | grep -E "FOUND|MISS" | tee -a results/r18/prc-b2.txt
      work/r18/pr_measure.sh b2 tmp/r18/pr-b2/build/strata "STRATA_QSA_SPLIT_ATTN=1" ;;
    spec)
      work/r18/pr_checks.sh spec tmp/r18/pr-spec "STRATA_SPEC_EXACT=1"
      (cd tmp/r18/pr-spec && ./build/spec_exact_test 2>&1 | tail -4) | tee -a results/r18/prc-spec.txt
      work/r18/pr_measure.sh spec tmp/r18/pr-spec/build/strata "STRATA_SPEC_EXACT=1" ;;
    gate)
      work/r18/pr_checks.sh gate tmp/r18/pr-gate "STRATA_SPEC_PROB=1 STRATA_COST_GATE=$GATEF"
      (cd tmp/r18/pr-gate && ./build/spec_prob_test 2>&1 | grep -E "cost gate|spec_prob_test:") | tee -a results/r18/prc-gate.txt
      work/r18/pr_measure.sh gate tmp/r18/pr-gate/build/strata "STRATA_COST_GATE=$GATEF" "STRATA_SPEC_PROB=1" ;;
    side)
      work/r18/pr_checks.sh side tmp/r18/pr-side "STRATA_SIDE_MIXER=2"
      work/r18/pr_measure.sh side tmp/r18/pr-side/build/strata "STRATA_SIDE_MIXER=2" ;;
  esac
  pe pr-$K
done
echo "=== $(date -Is) p2_run done"
