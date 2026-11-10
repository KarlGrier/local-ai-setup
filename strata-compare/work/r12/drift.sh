#!/bin/bash
# drift.sh LABEL [N] — round 12 A8 (the long-prompt drift, <= 2 h): does the drafter's state after a long prompt depend
# on timing? The oracle build (engine-r12o) on the base's flags with exact7's pins (--adapt-swaps 0 --suffix-draft 0
# --expert-cache 3500), exact sampling off, seed 11 at T 1.0 / 0.95 / 20 (every run computes the same tokens unless
# something depends on timing), the 16,110-token LDR synthesis prompt (work/prof/ldrsyn20k.tokens) + 96 new tokens,
# N runs (default 6), warm page cache. Each run's oracle file: tmp/r12/drift-LABEL-i.txt (V12 = the target's rows, D12 =
# the drafter's raw logits). drift_cmp.py finds the first line where runs differ and whether it is a target or a draft line.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 N=${2:-6}
S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
for i in $(seq 1 $N); do
  rm -f tmp/r12/drift-$L-$i.txt tmp/r12/drift-$L-$i.txt.h
  COLD=0 ENVX="STRATA_SPEC_EXACT=0 STRATA_SPEC_ORACLE=$WS/tmp/r12/drift-$L-$i.txt" PROF_SAMPLING="$S" \
    EXE=$WS/engine-r12o/strata work/r12/run.sh drift-$L-$i configs/R12B.json ${PROMPT:-ldrsyn20k} ${NEW:-96} $X > /dev/null
  echo "run $i: $(grep -c '^V12' tmp/r12/drift-$L-$i.txt) V12, $(grep -c '^D12' tmp/r12/drift-$L-$i.txt) D12, output $(grep -m1 '^output' logs/r12/prof/drift-$L-$i.out | sha256sum | cut -c1-8)"
done
.venv/bin/python work/r12/drift_cmp.py $L $N
