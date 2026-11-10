#!/bin/bash
# promote-c10.sh — round 8 Phase D (run ONLY after C*10's 2-hour soak passed the gate): the launchers default to C*10
# (work/r8/*.c10; old copies kept), then the rollback test (stop 8080 first -> C*9 -> back to the default C*10), leaving C*10 on 8080.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r8/run-strata.sh.before-c10-promotion
cp -p switch-model.sh work/r8/switch-model.sh.before-c10-promotion
cp work/r8/run-strata.sh.c10 run-strata.sh && chmod 775 run-strata.sh
cp work/r8/switch-model.sh.c10 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar10.json"
work/r8/rollback_test.sh configs/Cstar9.json
