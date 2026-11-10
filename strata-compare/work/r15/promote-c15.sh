#!/bin/bash
# promote-c15.sh — round 15 (run ONLY after C*15 passed its gates and the 2-hour soak): the launchers default to C*15
# (work/r15/*.c15; the old ones kept as work/r15/*.before-c15-promotion), then the real rollback test (stop 8080 ->
# C*14 -> stop -> the default C*15), leaving C*15 on 8080. Rollback any time: STRATA_CONFIG=configs/Cstar14.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r15/run-strata.sh.before-c15-promotion
cp -p switch-model.sh work/r15/switch-model.sh.before-c15-promotion
cp work/r15/run-strata.sh.c15 run-strata.sh && chmod 775 run-strata.sh
cp work/r15/switch-model.sh.c15 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar15.json"
bringup/lib/rollback_test.sh configs/Cstar14.json
