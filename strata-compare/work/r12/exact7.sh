#!/bin/bash
# exact7.sh LABEL CONFIG.json — round 9: round 8's seven fixed-computation exact pairs (--adapt-swaps 0 --suffix-draft 0
# --expert-cache 3500) on CONFIG's engine + flags (ENVX for extra environment), and the output hashes against C*10's
# known ones: greedy math ab1c7748 / code 58cd4381, sampled (seed 11, T 1.0 / 0.95 / 20) math 4d16b9b9 / code d04a9666,
# prompts p2000 3e219376 / 32k 651f56c8 / tf-long112k b806e832. Through the queue.
# round 10: REF=c11 compares with C*11's all-on hashes (Round 9 Phase C: f7459cdf 42db798e faf0fb9d e99b4f6a
# 3e219376 651f56c8 a393ca0a); REF=c10 with C*10's.
# round 12: REF=c13 (default) = C*13's hashes (a46e2e9f ea6fbe6c 3748f95d 94953719 3e219376 651f56c8 a944c147).
# round 11: REF=c121 compares with C*12.1's full-flag hashes (Round 10, exact7 c121full on configs/C121.json:
# 02deb3f1 f7d7afbb ae3b089b 9bb1459f 3e219376 651f56c8 a393ca0a). REF=<label> (e.g. v39): that earlier exact7 run's hashes.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
work/r12/run.sh $L-x-math $CFG math 1024 $X > /dev/null
PROF_SAMPLING="$S" work/r12/run.sh $L-s-math $CFG math 1024 $X > /dev/null
work/r12/run.sh $L-x-code $CFG code 1024 $X > /dev/null
PROF_SAMPLING="$S" work/r12/run.sh $L-s-code $CFG code 1024 $X > /dev/null
work/r12/run.sh $L-x-p2000 $CFG p2000 64 $X > /dev/null
work/r12/run.sh $L-x-32k $CFG 32k 64 $X > /dev/null
work/r12/run.sh $L-x-112k $CFG tf-long112k.prompt 64 $X > /dev/null
.venv/bin/python - $L ${REF:-c13} <<'PY'
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r12")
from p0_table import parse
L, R = sys.argv[1], sys.argv[2]
ref10 = {"x-math": "ab1c7748", "s-math": "4d16b9b9", "x-code": "58cd4381", "s-code": "d04a9666", "x-p2000": "3e219376",
       "x-32k": "651f56c8", "x-112k": "b806e832"}
ref11 = {"x-math": "f7459cdf", "s-math": "42db798e", "x-code": "faf0fb9d", "s-code": "e99b4f6a", "x-p2000": "3e219376",
         "x-32k": "651f56c8", "x-112k": "a393ca0a"}
ref121 = {"x-math": "02deb3f1", "s-math": "f7d7afbb", "x-code": "ae3b089b", "s-code": "9bb1459f", "x-p2000": "3e219376",
          "x-32k": "651f56c8", "x-112k": "a393ca0a"}
ref13 = {"x-math": "a46e2e9f", "s-math": "ea6fbe6c", "x-code": "3748f95d", "s-code": "94953719", "x-p2000": "3e219376",
         "x-32k": "651f56c8", "x-112k": "a944c147"}   # round 12: C*13 (Round 11 Phase G, exact7 cstar13 / cstar13b)
if R in ("c11", "c10", "c121", "c13"):
    ref = {"c11": ref11, "c10": ref10, "c121": ref121, "c13": ref13}[R]
    RN = {"c11": "C*11", "c10": "C*10", "c121": "C*12.1", "c13": "C*13"}[R]
else:   # round 11 (v0.1.39): REF=<label of an earlier exact7 run> compares with that run's own hashes
    ref = {k: parse(f"{R}-{k}")["out"] for k in ref121}
    RN = R
ok = 0
for k, h in ref.items():
    d = parse(f"{L}-{k}")
    same = d["out"] == h
    ok += same
    print(f"{L}-{k:8s} out {d['out']} ({RN} {h}) {'=' if same else 'DIFFERENT'}  ms/round {d.get('ms_round', 0):.2f}  prompt ms {d.get('pf_ms', 0):.0f}")
print(f"exact7 {L}: {ok}/7 identical to {RN}")
PY
