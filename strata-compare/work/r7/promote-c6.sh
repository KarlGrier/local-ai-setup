#!/bin/bash
# promote-c6.sh — round 7 item 1 (run ONLY after the 2-hour soak passed the gate): the launchers default to C*6
# (work/r6/run-strata.sh.new, work/r6/switch-model.sh.new, prepared in round 6), old copies kept, then the fixed rollback
# test (work/r7/rollback_test.sh: 8080 -> C*5 -> back to the default C*6), leaving C*6 on 8080.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r7/run-strata.sh.before-c6-promotion
cp -p switch-model.sh work/r7/switch-model.sh.before-c6-promotion
cp work/r6/run-strata.sh.new run-strata.sh && chmod 775 run-strata.sh
cp work/r6/switch-model.sh.new switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar6.json"
work/r7/rollback_test.sh configs/Cstar5.json
