#!/bin/bash
# p23neg.sh LABEL CONFIG.json — round 13 Part 2.3, the negative test of the patch guards on the real engine: for each guard,
# STRATA_GUARD_FORCE=<guard> (the guard fails on purpose) against the patch's switch set off by hand; greedy math 1024 and
# sampled math 1024 (exact7's pins: --adapt-swaps 0 --suffix-draft 0 --expert-cache 3500, seed 11). Pass: the engine
# starts, logs the guard's one line, and computes exactly what the switch off computes (same output hashes).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
G="pr245:STRATA_EXPERTS_OLD=1 ple_prefetch:STRATA_PLE_PREFETCH=0 spec_exact:STRATA_SPEC_EXACT=0 side_mixer:STRATA_SIDE_MIXER=0 router_q8k:STRATA_ROUTER_Q8K=0 qsa_split_attn:STRATA_QSA_SPLIT_ATTN=0 mmvq_il:STRATA_MMVQ_IL=0 gr_fork:STRATA_GR_FORK=0"
for g in ${GUARDS:-$G}; do
  n=${g%%:*}; e=${g#*:}
  for arm in force off; do
    if [ $arm = force ]; then EX="STRATA_GUARD_FORCE=$n"; else EX="$e"; fi
    ENVX="$EX" work/r13/run.sh $L-$n-$arm-x $CFG math 1024 $X > /dev/null
    ENVX="$EX" PROF_SAMPLING="$S" work/r13/run.sh $L-$n-$arm-s $CFG math 1024 $X > /dev/null
  done
done
.venv/bin/python - $L "${GUARDS:-$G}" <<'PY'
import sys, re
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r13")
from p0_table import parse
L, G = sys.argv[1], sys.argv[2].split()
ok_all = True
for g in G:
    n = g.split(":")[0]
    h = {f"{a}-{k}": parse(f"{L}-{n}-{a}-{k}").get("out") for a in ("force", "off") for k in ("x", "s")}
    line = open(f"/home/USER/ai-speed-testing/strata-compare/logs/r13/prof/{L}-{n}-force-x.out", errors="replace").read()
    logged = f"patch guard: {n} OFF" in line
    ok = h["force-x"] == h["off-x"] and h["force-s"] == h["off-s"] and None not in h.values() and logged
    ok_all &= ok
    print(f"{n:15s} forced {h['force-x']} {h['force-s']}  switch off {h['off-x']} {h['off-s']}  guard line {'yes' if logged else 'NO'}  {'PASS' if ok else 'FAIL'}")
print(f"p23neg {L}: {'ALL PASS' if ok_all else 'FAIL'}")
PY
