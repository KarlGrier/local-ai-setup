#!/bin/bash
# fixpair.sh LABEL CONFIG_A CONFIG_B [N] — round 11: a fixed-computation pair for EXACT changes (the tie-breaker when a
# served A/B's decode change is explained by tokens per round): the CLI on each config's served flags, exact sampling off,
# seed 11 at T 1.0 / 0.95 / 20, so both arms compute the same tokens (hash-checked); an LDR synthesis prompt (16,110
# tokens, work/prof/ldrsyn20k.tokens) + N new tokens (default 2048), order A B B A A B, warm page cache;
# exact7's pins (--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500) so the computation is fixed. ms per verify
# round per run, and A vs B.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 A=$2 B=$3 N=${4:-2048}
S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
# 08:50 fix: the served flags are not a fixed computation (--expert-cache auto sizes the cache from free VRAM, the
# adaptive tier swaps experts on timing: an expert moving between CPU and GPU changes rounding) -> exact7's pins
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
# 18:45: the 16K LDR prompt still drifted between runs of one config (b4kern) - long prompt + drafting; the default
# prompt is now the short math one (pinned short-prompt runs never drifted); PROMPT=ldrsyn20k for the long form.
i=0
for arm in A B B A A B; do
  i=$((i + 1)); cfg=$([ $arm = A ] && echo $A || echo $B)
  COLD=0 ENVX="STRATA_SPEC_EXACT=0" PROF_SAMPLING="$S" work/r12/run.sh fx-$L-$arm-$i $cfg ${PROMPT:-math} $N $X > /dev/null
done
.venv/bin/python - $L <<'PY' | tee results/r12/fixpair-$1.md
import sys, statistics as st
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r12")
from p0_table import parse
L = sys.argv[1]
runs = {"A": [], "B": []}
for i, arm in enumerate("ABBAAB", 1):
    runs[arm].append(parse(f"fx-{L}-{arm}-{i}"))
hashes = {d["out"] for v in runs.values() for d in v}
print(f"fixpair {L}: output hashes {sorted(hashes)} ({'identical' if len(hashes) == 1 else 'DIFFERENT - not a fixed computation'})")
for arm in "AB":
    ms = [d.get("ms_round", 0) for d in runs[arm]]
    print(f"  {arm}: ms per verify round {' / '.join(f'{m:.2f}' for m in ms)} -> mean {st.mean(ms):.3f}, decode {st.mean(d.get('tps', 0) for d in runs[arm]):.1f} tok/s")
a = st.mean(d.get("ms_round", 0) for d in runs["A"]); b = st.mean(d.get("ms_round", 0) for d in runs["B"])
print(f"  B vs A: ms per verify round {100 * (b / a - 1):+.2f} %")
PY
