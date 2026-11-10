#!/bin/bash
# promote-c14.sh — round 14 (run ONLY after C*14 passed its gates and the 2-hour soak): the launchers default to C*14
# (work/r14/*.c14; the old ones kept as work/r14/*.before-c14-promotion), then the real rollback test (stop 8080 ->
# C*13.1 -> stop -> the default C*14), leaving C*14 on 8080. Rollback any time: STRATA_CONFIG=configs/Cstar131.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r14/run-strata.sh.before-c14-promotion
cp -p switch-model.sh work/r14/switch-model.sh.before-c14-promotion
cp work/r14/run-strata.sh.c14 run-strata.sh && chmod 775 run-strata.sh
cp work/r14/switch-model.sh.c14 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar14.json"
bringup/lib/rollback_test.sh configs/Cstar131.json
