#!/bin/bash
# sp_more.sh - round 19: the fallback C*17's one borderline sampler count (arith-j3 T 0.6, our exact sampling + the gate,
# 2,000 samples: '=' 54.7 % vs 51.8 %, p 0.0103; vs the spec-off arm 52.3 % p 0.13). 4,000 more samples with our exact
# sampling + gate (twin17) and 4,000 more with speculation off on the same build (twin17x-nospec), then all samples of
# each pooled (6,000 per arm with the earlier 2,000) against the build's own probabilities and against each other.
# Kernel log checked after each server. Ends with the promoted build on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; O=$WS/results/r19/sp-c17x; TW=$WS/tmp/r19/twin
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc spmore-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for arm in exact:twin17 nospec:twin17x-nospec; do
  IFS=: read -r a cfg <<< "$arm"; L=c17x-more-$a
  bringup/lib/with_server.sh r19-spmore-$a configs/$cfg.json -- "SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $O/strata-more-$a.txt 2>&1; \
    echo \"request lines with drafts: \$(grep -E 'drafts accepted [0-9]+ of [1-9]' \$ELOG | wc -l) of \$(grep -c 'drafts accepted' \$ELOG)\"; \
    grep -m1 -E 'EXACT speculative|cost-aware' \$ELOG | cut -c1-90" 2>&1 | grep -E 'start|done|drafts|EXACT|cost-aware'
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc spmore-$a
done
# pooled: exact = c17x-j3 (2,000) + c17x-more-exact (4,000); spec off = c17x-more-nospec (4,000) + the C*17 SPEC_PROB
# build's spec-off arm (r19-spchk-nospec, T 0.6: the same target computation, 2,000)
cat $O/sp-strata-c17x-j3.jsonl $O/sp-strata-c17x-more-exact.jsonl > $O/sp-strata-c17x-pool-exact.jsonl
grep '"temp": 0.6' $WS/results/r19/sp-recheck/sp-strata-r19-spchk-nospec.jsonl | cat - $O/sp-strata-c17x-more-nospec.jsonl > $O/sp-strata-c17x-pool-nospec.jsonl
for l in more-exact more-nospec pool-exact pool-nospec; do
  cp $O/sp-strata-logp-c17x-all.json $O/sp-strata-logp-c17x-$l.json
  SP_DIR=$O SP_LABEL=c17x-$l STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-$l.txt 2>&1
  echo "--- $l:"; grep arith-j3 $O/analyze-own-$l.txt
done
$P - "$O" <<'PY' | tee $O/pooled-compare.txt
import json, math, sys
from pathlib import Path
O = Path(sys.argv[1]); cases = {c["case"]: c for c in json.loads((O / "sp-cases.json").read_text())}
c = cases["arith-j3"]
def tally(f):
    on = eq = 0
    for line in open(f):
        r = json.loads(line)
        if r["case"] != "arith-j3" or abs(r["temp"] - 0.6) > 1e-6 or not r["ids"]: continue
        ids = r["ids"]
        if ids[:c["j"]] != c["path"]: continue
        on += 1; eq += ids[c["j"]] == 28
    return eq, on
a, n = tally(O / "sp-strata-c17x-pool-exact.jsonl"); b, m = tally(O / "sp-strata-c17x-pool-nospec.jsonl")
p = (a + b) / (n + m); se = math.sqrt(p * (1 - p) * (1 / n + 1 / m)); z = (a / n - b / m) / se
print(f"our exact sampling: '=' {a} of {n} = {100 * a / n:.1f} %; speculation off: {b} of {m} = {100 * b / m:.1f} %; "
      f"difference {100 * (a / n - b / m):+.1f} pp, z {z:.2f}, two-sided p {math.erfc(abs(z) / math.sqrt(2)):.3f}")
PY
bringup/lib/phase_end.sh r19-spmore keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) sp_more done"
