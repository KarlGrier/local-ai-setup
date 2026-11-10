#!/bin/bash
# promote-c9.sh — round 8 Phase C (run ONLY after C*9's 2-hour soak passed the gate): the launchers default to C*9
# (work/r8/*.c9; old copies kept), then the rollback test (stop 8080 first -> C*8 -> back to the default C*9), leaving C*9 on 8080.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r8/run-strata.sh.before-c9-promotion
cp -p switch-model.sh work/r8/switch-model.sh.before-c9-promotion
cp work/r8/run-strata.sh.c9 run-strata.sh && chmod 775 run-strata.sh
cp work/r8/switch-model.sh.c9 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar9.json"
work/r8/rollback_test.sh configs/Cstar8.json
