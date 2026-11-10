#!/bin/bash
# s3_run.sh NAME RUN PLAN_JSON_KEY EVICT_GLOB — round 15 step 3 for one stand-in: the placement configs from the runbook's
# candidate (work/r15/mkplace.py), then the warmed, repeat-gated probe of every placement (work/r15/s3probe.sh), then the
# probe table (work/r15/probe_table.py -> results/r15/s3-probes-NAME.md: which placements get the full served set).
# Your floors for the stand-ins: MemAvailable >= 6 GiB, the 5080 >= 300 MiB, swap growth <= 4 GiB.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NAME=$1 RUN=$2 PLAN=$3
export EVICT_GLOB="$4"
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
export PROMPT_DIR=$WS/bringup/out/$RUN/prompts
.venv/bin/python work/r15/mkplace.py $RUN $NAME $PLAN
for X in ${PLACEMENTS:-A B C D E}; do
  work/r15/s3probe.sh r15-$NAME-$X configs/r15-$NAME-$X.json
done
.venv/bin/python work/r15/probe_table.py $NAME > results/r15/s3-probes-$NAME.md 2>&1
cat results/r15/s3-probes-$NAME.md
