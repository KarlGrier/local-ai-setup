#!/bin/bash
# s1_tflong2.sh — round 16 step 1 (fixed copy of s1_tflong.sh: the forced text is the 1,535 tokens right after the cut, so it continues its prompt), the long-text NLL check for v0.1.41's CPU prompt-read share: teacher-forced NLL (the
# twin engine of r16z, C*16's flags, --adapt-swaps 0) with the share at upstream's default (on) vs off, A B B A
# (on, off, off, on). The long texts' prompts are cut to N x 16,384 + 700 tokens (bringup/out/r16z/tfcut2) so their last
# prompt chunk (700 tokens) is one the share acts on - the harness's own long prompts are 4,096-multiples and never
# leave a chunk below 1,024; math (136-token prompt) and corpus (16) as the switch gates use them. 1,535 scored tokens each.
# Table -> results/r16/s1-tflong2.md (bringup/lib/s1... below): mean NLL per text per arm, on - off, the two same-arm runs'
# difference (the noise: the share's auto mode picks layers by timing).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/bringup/out/r16z
export PROMPT_DIR=$R/tfcut2 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB
TEXTS="math corpus long24kc long28kc long40kc long64kc long96kc long112kc"
for arm in on-a off-a off-b on-b; do
  CFG=$R/configs/twin-share${arm%-*}.json
  TF_ENV="" bringup/lib/tf.sh r16-tfs2-$arm $CFG $R/engine-twin/strata $TEXTS 2>&1 | grep -E "teacher-forced|prompt chunk|FAILED|CPU share" | cut -c1-200
done
.venv/bin/python - $TEXTS <<'PY' > results/r16/s1-tflong2.md
import statistics as st, sys
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/results")
def m(arm, t):
    f = R / f"tf-r16-tfs2-{arm}-{t}.nll"
    return st.mean(float(x) for x in f.read_text().split()) if f.exists() else None
print("| text (prompt tokens) | on a | on b | off a | off b | on − off (means) | on a − on b | off a − off b |")
print("|---|---|---|---|---|---|---|---|")
rows = []
for t in sys.argv[1:]:
    v = {a: m(a, t) for a in ("on-a", "on-b", "off-a", "off-b")}
    if None in v.values(): print(f"| {t} | missing |"); continue
    on, off = (v["on-a"] + v["on-b"]) / 2, (v["off-a"] + v["off-b"]) / 2
    rows.append((t, on - off))
    print(f"| {t} | {v['on-a']:.5f} | {v['on-b']:.5f} | {v['off-a']:.5f} | {v['off-b']:.5f} | {on - off:+.5f} | {v['on-a'] - v['on-b']:+.5f} | {v['off-a'] - v['off-b']:+.5f} |")
lg = [d for t, d in rows if t.startswith("long")]
print(f"\nlong texts: mean on − off {st.mean(lg):+.5f} nats, largest |on − off| {max(abs(d) for d in lg):.5f} (bound 0.005 per text, as the switch gates)" if lg else "")
PY
cat results/r16/s1-tflong2.md
