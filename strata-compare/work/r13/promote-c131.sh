#!/bin/bash
# promote-c131.sh — round 13 (run ONLY after C*13.1 passed its gates and 2-hour soak): the launchers default to C*13.1
# (work/r13/*.c131; the old ones kept as work/r13/*.before-c131-promotion), then the real rollback test (stop 8080 ->
# C*13 -> stop -> the default C*13.1), leaving C*13.1 on 8080. Rollback any time: STRATA_CONFIG=configs/Cstar13.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r13/run-strata.sh.before-c131-promotion
cp -p switch-model.sh work/r13/switch-model.sh.before-c131-promotion
cp work/r13/run-strata.sh.c131 run-strata.sh && chmod 775 run-strata.sh
cp work/r13/switch-model.sh.c131 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar131.json"
work/r13/rollback_test.sh configs/Cstar13.json
