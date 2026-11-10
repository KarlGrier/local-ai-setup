#!/bin/bash
# chain20.sh - Round 20: post18.sh (soak + promotion), then items 2-4 in order, each script taking the heavy lock itself:
#   2 nvfp4_trial.sh (exit 3 = the 20 GiB floor stopped it: then the NVFP4 quick run is skipped too)
#   3 suite18.sh (C*18 IQ3_S and, unless item 2 stopped at the floor, C*18 NVFP4)
#   4 conc18.sh (C*17.1 again with today's display, then C*18; served configs only)
# A kernel-check failure (exit 1 from any of them) stops the chain.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
step() { echo "=== $(date -Is) $*"; }
step "chain20: post18.sh first (SKIP_STOP=1: the stop test passed 3/3 at 12:59; the soak, SDEC18, the promotion)"
SKIP_STOP=1 work/r20/post18.sh > logs/r20/post18-2.console 2>&1; rc=$?
step "post18 exit $rc"; tail -30 logs/r20/post18-2.console | cut -c1-220
[ $rc = 0 ] || { step "post18 did not finish (exit $rc) - chain stopped"; exit 1; }
work/r20/nvfp4_trial.sh > logs/r20/nvfp4_trial.log 2>&1; rc=$?
step "nvfp4_trial exit $rc"; tail -25 logs/r20/nvfp4_trial.log | cut -c1-220
grep -q "KERNEL CHECK FAILED" logs/r20/nvfp4_trial.log && { step "kernel check failed - chain stopped"; exit 1; }
if [ $rc = 3 ]; then L="iq3s"; step "NVFP4 stopped at the 20 GiB floor: its quick run is skipped"; else L="iq3s nvfp4"; fi
LABELS="$L" work/r20/suite18.sh > logs/r20/suite18.log 2>&1; rc=$?
step "suite18 exit $rc"; tail -12 logs/r20/suite18.log | cut -c1-220
grep -q "KERNEL CHECK FAILED" logs/r20/suite18.log && { step "kernel check failed - chain stopped"; exit 1; }
work/r20/conc18.sh > logs/r20/conc18.log 2>&1; rc=$?
step "conc18 exit $rc"; tail -30 logs/r20/conc18.log | cut -c1-220
step "chain20 done"
