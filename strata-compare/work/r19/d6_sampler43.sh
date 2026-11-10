#!/bin/bash
# d6_sampler43.sh - round 19 Part D 6: the near-tie bias re-checked on stock v0.1.43 before an issue is drafted (the user's
# condition; v0.1.43 does not change STRATA_SPEC_PROB). The stock v0.1.43 twin (+ the 4 MEASUREMENT commits = the probe's
# hooks only): arith-j3 at T 0.6 with speculation off (4,000: the ground truth), upstream's STRATA_SPEC_PROB=1 (2,000) and
# upstream's default exact-match drafting (2,000); and our exact sampling on the C*17.1 candidate's twin (runbook r19e,
# 2,000). Added 19:2x: STRATA_SPEC_PROB with --spec-min-p 0 and with STRATA_SPEC_PROB_GATE=top (2,000 each) - the test of
# the hypothesis that the bias is --spec-min-p gating on the DRAWN token's q (generate.cpp ~11811, sampler.cu prob[0]). Each against its build's own probabilities (strata_logp); the kernel log after each server. Ends with C*17 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; O=$WS/results/r19/sp-v43; mkdir -p $O; NVCC=/usr/local/cuda-13.3/bin/nvcc
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc d6-start
T=$WS/tmp/r19/stockmeas43
[ -e $T/third_party/llama.cpp ] || ln -sfn $(readlink -f strata-v0115/third_party/llama.cpp) $T/third_party/llama.cpp
[ -x $T/build/strata ] || (cd $T && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
    "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$T/third_party/llama.cpp" > build-configure.log 2>&1 \
  && nice -n 5 cmake --build build --target strata -j 24 > build.log 2>&1) || { echo "BUILD FAILED"; exit 1; }
echo "stock v0.1.43 twin: $(git -C $T rev-parse HEAD^{tree}) $(sha256sum $T/build/strata | cut -c1-12)"
cp bringup/out/accept/acc-c17/sp/sp-cases.json bringup/out/accept/acc-c17/sp/sp-llama.json $O/
cp bringup/out/r19e/configs/twin.json configs/r19e-twin.json
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for arm in nospec:r19-st43-nospec:4000:stock sp:r19-st43-sp:2000:stock spmp0:r19-st43-sp-mp0:2000:stock sptop:r19-st43-sp-top:2000:stock em:r19-st43-em:2000:stock exact:r19e-twin:2000:port; do
  IFS=: read -r a cfg n tree <<< "$arm"; L=v43-$a; rm -f $O/sp-strata-$L.jsonl
  TW=$( [ $tree = stock ] && echo $T || $P -c "import json,pathlib; print(pathlib.Path(json.load(open('configs/$cfg.json'))['server']).parent.parent)")
  bringup/lib/with_server.sh r19-d6-$a configs/$cfg.json -- "SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 $n 0.6 arith-j3 > $O/strata-$a.txt 2>&1; \
    SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $O/logp-$a.txt 2>&1; \
    echo \"request lines with drafts: \$(grep -E 'drafts accepted [0-9]+ of [1-9]' \$ELOG | wc -l) of \$(grep -c 'drafts accepted' \$ELOG)\"; \
    grep -m1 -E 'EXACT speculative|probabilistic draft' \$ELOG | cut -c1-80" 2>&1 | grep -E 'start|done|drafts|EXACT|probabilistic'
  SP_DIR=$O SP_LABEL=$L STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-$a.txt 2>&1
  echo "--- $a:"; grep arith-j3 $O/analyze-own-$a.txt; grep arith-j3 $O/logp-$a.txt | cut -c1-150
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc d6-$a
done
$P - "$O" <<'PY' | tee $O/compare.txt
import json, math, sys
from pathlib import Path
O = Path(sys.argv[1]); c = [x for x in json.loads((O / "sp-cases.json").read_text()) if x["case"] == "arith-j3"][0]
def tally(f):
    on = eq = 0
    for line in open(f):
        r = json.loads(line)
        if r["case"] != "arith-j3" or abs(r["temp"] - 0.6) > 1e-6 or not r["ids"] or r["ids"][:c["j"]] != c["path"]: continue
        on += 1; eq += r["ids"][c["j"]] == 28
    return eq, on
t = {a: tally(O / f"sp-strata-v43-{a}.jsonl") for a in ("nospec", "sp", "spmp0", "sptop", "em", "exact")}
names = {"nospec": "stock v0.1.43, speculation off", "sp": "stock v0.1.43, STRATA_SPEC_PROB=1 (--spec-min-p 0.5, gate on the drawn token's q)",
         "spmp0": "stock v0.1.43, STRATA_SPEC_PROB=1, --spec-min-p 0 (no gate)", "sptop": "stock v0.1.43, STRATA_SPEC_PROB=1, --spec-min-p 0.5 on q's top (STRATA_SPEC_PROB_GATE=top)", "em": "stock v0.1.43, default exact-match drafting",
         "exact": "v0.1.43 + our series, our exact sampling (C*17.1 candidate)"}
for a, (e, n) in t.items(): print(f"{names[a]}: '=' {e} of {n} = {100 * e / n:.1f} %")
def z(x, y):
    (a, n), (b, m) = x, y; p = (a + b) / (n + m); se = math.sqrt(p * (1 - p) * (1 / n + 1 / m)); zz = (a / n - b / m) / se
    return f"{100 * (a / n - b / m):+.1f} pp, z {zz:.2f}, p {math.erfc(abs(zz) / math.sqrt(2)):.2g}"
for a in ("sp", "spmp0", "sptop", "em", "exact"): print(f"{a} vs speculation off: {z(t[a], t['nospec'])}")
PY
bringup/lib/phase_end.sh r19-d6 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d6 done"
