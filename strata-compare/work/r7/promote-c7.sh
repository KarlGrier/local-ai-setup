#!/bin/bash
# promote-c7.sh — round 7 item 0 (run ONLY after C*7's 2-hour soak passed the gate): the launchers default to C*7
# (work/r7/*.c7; old copies kept), then the rollback test (8080 -> C*6 -> back to the default C*7), leaving C*7 on 8080.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r7/run-strata.sh.before-c7-promotion
cp -p switch-model.sh work/r7/switch-model.sh.before-c7-promotion
cp work/r7/run-strata.sh.c7 run-strata.sh && chmod 775 run-strata.sh
cp work/r7/switch-model.sh.c7 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar7.json"
work/r7/rollback_test.sh configs/Cstar6.json
