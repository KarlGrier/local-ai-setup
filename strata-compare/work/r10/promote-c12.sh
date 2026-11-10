#!/bin/bash
# promote-c12.sh — round 10 Phase E (run ONLY after C*12's 2-hour soak and every gate passed): the launchers default to
# C*12 (work/r10/*.c12; old copies kept as work/r10/*.before-c12-promotion), then the real rollback test (stop 8080 ->
# C*11 -> stop -> the default C*12), leaving C*12 on 8080. Rollback any time: STRATA_CONFIG=configs/Cstar11.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r10/run-strata.sh.before-c12-promotion
cp -p switch-model.sh work/r10/switch-model.sh.before-c12-promotion
cp work/r10/run-strata.sh.c12 run-strata.sh && chmod 775 run-strata.sh
cp work/r10/switch-model.sh.c12 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar12.json"
work/r10/rollback_test.sh configs/Cstar11.json
