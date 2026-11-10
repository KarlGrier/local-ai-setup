#!/bin/bash
# promote-c121.sh — round 10 (run ONLY after C*12.1 passed its gates and 2-hour soak): the launchers default to
# C*12.1 (work/r10/*.c121; old copies kept as work/r10/*.before-c121-promotion), then the real rollback test (stop 8080 ->
# C*12 -> stop -> the default C*12.1), leaving C*12.1 on 8080. Rollback any time: STRATA_CONFIG=configs/Cstar12.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r10/run-strata.sh.before-c121-promotion
cp -p switch-model.sh work/r10/switch-model.sh.before-c121-promotion
cp work/r10/run-strata.sh.c121 run-strata.sh && chmod 775 run-strata.sh
cp work/r10/switch-model.sh.c121 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar121.json"
work/r10/rollback_test.sh configs/Cstar12.json
