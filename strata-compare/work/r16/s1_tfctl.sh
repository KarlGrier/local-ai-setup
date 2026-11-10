#!/bin/bash
# s1_tfctl.sh — round 16 step 1, the control for the long-text NLL check: how far do two KNOWN rounding-level switches
# (B.1 STRATA_GR_FORK=0, B.2 STRATA_QSA_SPLIT_ATTN=0 - both pass their TF gates at 0.005 nats on the short texts) move the
# same in-context long texts (bringup/out/r16z/tfcut2), with the share off (deterministic: one run each against the share
# A/B's off arms, labels r16-tfs2-off-a/b). Table -> results/r16/s1-tfctl.md.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/bringup/out/r16z
export PROMPT_DIR=$R/tfcut2 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB
TEXTS="math corpus long24kc long28kc long40kc long64kc long96kc long112kc"
TF_ENV="STRATA_GR_FORK=0" bringup/lib/tf.sh r16-tfc-b1off $R/configs/twin-shareoff.json $R/engine-twin/strata $TEXTS 2>&1 | grep -E "teacher-forced|FAILED" | cut -c1-160
TF_ENV="STRATA_QSA_SPLIT_ATTN=0" bringup/lib/tf.sh r16-tfc-b2off $R/configs/twin-shareoff.json $R/engine-twin/strata $TEXTS 2>&1 | grep -E "teacher-forced|FAILED" | cut -c1-160
.venv/bin/python - $TEXTS <<'PY' > results/r16/s1-tfctl.md
import statistics as st, sys
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/results")
L = lambda lab, t: [float(x) for x in (R / f"tf-{lab}-{t}.nll").read_text().split()]
print("Per text: the change of mean NLL against C*16 with the share off (nats), and per token the mean |difference| / tokens with |d| > 0.5.\n")
print("| text | share on (a / b) | B.1 off | B.2 off | per token mean abs d: share on a / B.1 off / B.2 off | abs d > 0.5: share on a / B.1 / B.2 |")
print("|---|---|---|---|---|---|")
agg = {"on": [], "b1": [], "b2": []}
for t in sys.argv[1:]:
    off = L("r16-tfs2-off-a", t); mo = st.mean(off)
    v = {"on-a": L("r16-tfs2-on-a", t), "on-b": L("r16-tfs2-on-b", t), "b1": L("r16-tfc-b1off", t), "b2": L("r16-tfc-b2off", t)}
    dm = {k: st.mean(x) - mo for k, x in v.items()}
    ad = {k: st.mean(abs(a - b) for a, b in zip(x, off)) for k, x in v.items()}
    big = {k: sum(abs(a - b) > 0.5 for a, b in zip(x, off)) for k, x in v.items()}
    if t.startswith("long"):
        agg["on"] += [dm["on-a"], dm["on-b"]]; agg["b1"].append(dm["b1"]); agg["b2"].append(dm["b2"])
    print(f"| {t} | {dm['on-a']:+.4f} / {dm['on-b']:+.4f} | {dm['b1']:+.4f} | {dm['b2']:+.4f} | {ad['on-a']:.3f} / {ad['b1']:.3f} / {ad['b2']:.3f} | {big['on-a']} / {big['b1']} / {big['b2']} |")
print("\nLong texts, per-text change of mean NLL: " + "; ".join(f"{k}: mean {st.mean(x):+.4f}, mean abs {st.mean(abs(y) for y in x):.4f}, n {len(x)}" for k, x in agg.items()))
PY
cat results/r16/s1-tfctl.md
