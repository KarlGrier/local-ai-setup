#!/bin/bash
# s8_find3.sh — round 15 step 8, your request (1 hour at most, settings and defaults only): where C*15's ~3 % went. On C*15,
# each default that changed since v0.1.40.1 and has a switch set back to its old value, one at a time, on the decode
# screen, against C*14 (and plain C*15) arms interleaved through the run:
#   c14 c15 costgate0 stager0 pinguard0 c14 streamahead0 noq8kavx2 mmvqil0 c15 c14
# STRATA_SPEC_PROB is already off (its old value) in C*15 and #1252's draft-policy change has no switch, so "the draft gate"
# is our cost gate (STRATA_COST_GATE off: its table was fitted on v0.1.40.1). STRATA_MMVQ_IL=0 (upstream's F4 off) is
# not a revert for C*14 (it ran the same switch on as our B.3): it shows whether F4 delivers what B.3 did.
# Table -> results/r15/s8-find3.md. A candidate that looks like it restores the speed gets A B B A vs C*14 next.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB LR_MAX
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
D=$WS/work/r15/cfg; PY=.venv/bin/python; mkdir -p logs/r15
mk() {   # mk NAME "K=V ... -K" -> $D/f3-NAME.json from configs/Cstar15.json
  $PY - "$D/f3-$1.json" "$2" <<'PY'
import json, sys, shutil
from pathlib import Path
dst, kv = sys.argv[1], sys.argv[2]
src = Path("/home/USER/ai-speed-testing/strata-compare/configs/Cstar15.json")
c = json.loads(src.read_text())
for p in kv.split():
    if p.startswith("-"): c["env"].pop(p[1:], None)
    else: k, v = p.split("=", 1); c["env"][k] = v
c["log"] = str(Path(dst).with_suffix(".log")); c["fallback"] = None
Path(dst).write_text(json.dumps(c, indent=1) + "\n")
shutil.copy(src.with_suffix("").as_posix() + ".shared-settings.json", Path(dst).with_suffix("").as_posix() + ".shared-settings.json")
PY
}
mk c15 ""
mk costgate0 "-STRATA_COST_GATE"
mk stager0 "STRATA_STAGER_SLEEP=0"
mk pinguard0 "STRATA_PIN_GUARD=0"
mk streamahead0 "STRATA_PREFILL_STREAM_AHEAD=0"
mk noq8kavx2 "STRATA_NO_Q8K_AVX2=1"
mk mmvqil0 "STRATA_MMVQ_IL=0"
T0=$(date +%s)
i=0
for a in c14:C14 c15:c15 costgate0:costgate0 stager0:stager0 pinguard0:pinguard0 c14:C14 streamahead0:streamahead0 \
         noq8kavx2:noq8kavx2 mmvqil0:mmvqil0 c15:c15 c14:C14; do
  i=$((i + 1)); n=${a%%:*}; k=${a#*:}
  if [ $(( ($(date +%s) - T0) / 60 )) -ge ${F3_MIN:-50} ]; then echo "f3 $n: skipped (time)"; continue; fi
  if [ "$k" = C14 ]; then C=$WS/configs/Cstar14.json; else C=$D/f3-$k.json; fi
  bringup/lib/decscreen.sh r15-f3b-$i-$n $C > logs/r15/f3b-$i-$n.log 2>&1
  echo "f3 $i $n done $(date +%T)"
done
$PY - <<'PY' > results/r15/s8-find3.md
import json, re
from collections import defaultdict
rows = [json.loads(l) for l in open("/home/USER/ai-speed-testing/strata-compare/results/runs.jsonl") if '"r15-f3b-' in l]
g = defaultdict(lambda: [0, 0.0, 0, 0])
order = []
for r in rows:
    e = r.get("engine") or {}
    c = r["config"]
    if c not in order: order.append(c)
    if e.get("generated") and e.get("decode_ms"):
        g[c][0] += e["generated"]; g[c][1] += e["decode_ms"]
        g[c][2] += e.get("drafts_accepted") or 0; g[c][3] += e.get("rounds") or 0
tps = {c: g[c][0] / (g[c][1] / 1000) for c in order if g[c][1]}
c14 = [v for c, v in tps.items() if c.endswith("-c14")]
c15 = [v for c, v in tps.items() if c.endswith("-c15")]
m14 = sum(c14) / len(c14) if c14 else float("nan"); m15 = sum(c15) / len(c15) if c15 else float("nan")
print("# Round 15 step 8 — where C*15's ~3 % went (decode screen, one arm each, interleaved; your sampling)\n")
print(f"C*14 arms: {' / '.join(f'{x:.1f}' for x in c14)} → mean **{m14:.1f}**; plain C*15 arms: {' / '.join(f'{x:.1f}' for x in c15)} → mean **{m15:.1f}** ({100 * (m15 / m14 - 1):+.1f} %)\n")
print("| arm (in order) | decode tok/s | vs C*14 mean | vs C*15 mean |\n|---|---|---|---|")
for c in order:
    if c not in tps: print(f"| {c} | – | – | – |"); continue
    print(f"| {c} | {tps[c]:.1f} | {100 * (tps[c] / m14 - 1):+.1f} % | {100 * (tps[c] / m15 - 1):+.1f} % |")
PY
cat results/r15/s8-find3.md
