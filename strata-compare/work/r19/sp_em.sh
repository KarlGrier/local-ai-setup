#!/bin/bash
# sp_em.sh - round 19: is our exact sampling's +2-3 pp at arith-j3 (T 0.6) a sampler bias or the window's numerics? The same
# build with upstream's default drafting (twin17x-em: argmax drafts, exact-match: each token a plain sample of its verify
# window's p, the same windows as speculative sampling): 4,000 samples. ~ our exact sampling -> numerics (p as computed in
# a multi-token window); ~ speculation off -> a bias in our sampler. Kernel log checked. Ends with the promoted build on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; O=$WS/results/r19/sp-c17x; TW=$WS/tmp/r19/twin
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc spem-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
L=c17x-em; rm -f $O/sp-strata-$L.jsonl
bringup/lib/with_server.sh r19-spem configs/twin17x-em.json -- "SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $O/strata-em.txt 2>&1; \
  echo \"request lines with drafts: \$(grep -E 'drafts accepted [0-9]+ of [1-9]' \$ELOG | wc -l) of \$(grep -c 'drafts accepted' \$ELOG)\"; \
  grep -m1 -E 'EXACT speculative|probabilistic draft|coupled draft' \$ELOG | cut -c1-90 || echo 'no speculative-sampling line (exact-match mode)'" 2>&1 | grep -E 'start|done|drafts|EXACT|probabilistic|coupled|exact-match'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc spem
cp $O/sp-strata-logp-c17x-all.json $O/sp-strata-logp-$L.json
SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-em.txt 2>&1
echo "--- exact-match:"; grep arith-j3 $O/analyze-own-em.txt
$P - "$O" <<'PY' | tee $O/em-compare.txt
import json, math, sys
from pathlib import Path
O = Path(sys.argv[1]); c = [x for x in json.loads((O / "sp-cases.json").read_text()) if x["case"] == "arith-j3"][0]
def tally(fs):
    on = eq = 0
    for f in fs:
        for line in open(f):
            r = json.loads(line)
            if r["case"] != "arith-j3" or abs(r["temp"] - 0.6) > 1e-6 or not r["ids"] or r["ids"][:c["j"]] != c["path"]: continue
            on += 1; eq += r["ids"][c["j"]] == 28
    return eq, on
arms = {"exact-match (upstream default)": [O / "sp-strata-c17x-em.jsonl"],
        "our exact sampling (pooled)": [O / "sp-strata-c17x-pool-exact.jsonl"],
        "speculation off (pooled)": [O / "sp-strata-c17x-pool-nospec.jsonl"]}
t = {k: tally(v) for k, v in arms.items()}
for k, (a, n) in t.items(): print(f"{k}: '=' {a} of {n} = {100 * a / n:.2f} %")
def z(x, y):
    (a, n), (b, m) = x, y; p = (a + b) / (n + m); se = math.sqrt(p * (1 - p) * (1 / n + 1 / m)); zz = (a / n - b / m) / se
    return f"{100 * (a / n - b / m):+.2f} pp, z {zz:.2f}, p {math.erfc(abs(zz) / math.sqrt(2)):.4f}"
k = list(t)
print(f"exact-match vs our exact sampling: {z(t[k[0]], t[k[1]])}")
print(f"exact-match vs speculation off:    {z(t[k[0]], t[k[2]])}")
print(f"our exact sampling vs spec off:    {z(t[k[1]], t[k[2]])}")
PY
bringup/lib/phase_end.sh r19-spem keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) sp_em done"
