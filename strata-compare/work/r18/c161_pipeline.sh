#!/bin/bash
# c161_pipeline.sh - round 18 part 1: C*16.1 from assets to promotion, with a phase end (the promoted build on 8080, health
# + one answer) after each measuring step and two holds for my reading of the results:
#   1 build-cstar161.sh   2 gates161.sh   (phase end)   3 the acceptance suite   (phase end)
#   hold c161-soak (released only if the gates and the suite passed)   4 the 2-hour soak of C*16.1 on 8080 + the soaked
#   decode screen   5 tags check   hold c161-promote   6 promote-c161.sh (launchers + rollback test to C*16 and back)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18
step() { echo "=== $(date -Is) $*"; }
pe() { bringup/lib/phase_end.sh r18-$1 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED" ; }
step "1 build"; work/r18/build-cstar161.sh || { echo "BUILD FAILED"; exit 1; }
step "2 gates"; work/r18/gates161.sh c161 configs/Cstar161.json configs/R161RT.json configs/BR161.json c16 > logs/r18/gates161.log 2>&1; cat results/r18/g-gates-c161.txt
pe gates
step "3 acceptance suite"; bringup/acceptance.sh acc-c161 configs/Cstar161.json configs/twin161.json > results/r18/accept-c161.txt 2>&1; tail -22 bringup/out/accept/acc-c161/table.md
pe accept
work/r18/hold.sh c161-soak
step "4 soak (2 h, C*16.1 on 8080)"; STRATA_CONFIG=configs/Cstar161.json bringup/lib/soak13.sh 120 > logs/r18/soak161.log 2>&1; tail -30 logs/r18/soak161.log
bringup/lib/soakdec.sh SDEC161 configs/Cstar161.json > logs/r18/soakdec161.log 2>&1; tail -3 logs/r18/soakdec161.log
step "5 tags"; git ls-remote --tags https://github.com/Niko1221/Strata.git 2>/dev/null | grep -o 'refs/tags/v[0-9.]*$' | sort -V | tail -3
work/r18/hold.sh c161-promote
step "6 promote"; work/r18/promote-c161.sh > logs/r18/promote-c161.log 2>&1; tail -20 logs/r18/promote-c161.log
step "pipeline done"
