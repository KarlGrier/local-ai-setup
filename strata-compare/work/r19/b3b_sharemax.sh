#!/bin/bash
# b3b_sharemax.sh - round 19 B3, the chunk limit: with an explicit STRATA_PREFILL_CPU_SHARE the share applies to chunks below
# STRATA_PREFILL_CPU_SHARE_MAX = 3072 (prefill.cpp cpu_share_max(); 1024 only for the unset default), but B3 measured 512 and
# 1,000 tokens only, and B6 showed C*17's 1-4K prompts slower (LDR +18 %, exact7 p2000 1,137 vs 1,043 ms). C*17 as built
# (A, configs/r19d-cand-m3072) against STRATA_PREFILL_CPU_SHARE_MAX=1024 (B, r19d-cand-m1024), B A A B, a fresh guarded
# server per arm: the warm-ups, then 512 / 1,000 (prompts/r16/ttft-short.json, 6 each) and 1,500 / 2,000 / 3,000 tokens
# (prompts/r19/ttft-mid.json, 4 each), 64 tokens out. Kernel log checked after every server. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB SPEED_FILE
P=.venv/bin/python; R=results/r19; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc b3b-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SS=$(date -Iseconds | cut -c1-19)
for arm in m1024-a m3072-a m3072-b m1024-b; do
  L=r19-b3b-$arm; CFG=configs/r19d-cand-${arm%-*}.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  echo "=== $(date -Is) $L start ($CFG)"
  bringup/lib/srv.sh start $L "$CFG" || { echo "$L DID NOT START"; continue; }
  $P work/r5/warmup.py http://127.0.0.1:8081 > /dev/null
  B="$P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M) --max-tokens 64"
  SPEED_FILE=r16/ttft-short $B speed --sizes w600 > /dev/null
  SPEED_FILE=r16/ttft-short $B speed --sizes 512,1000 > /dev/null
  SPEED_FILE=r19/ttft-mid $B speed --sizes 1500,2000,3000 > /dev/null
  bringup/lib/srv.sh stop
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
  kc $L
done
SINCE=$SS $P - <<'PY' | tee $R/b3b-sharemax.md
import json, os
from collections import defaultdict
since = os.environ["SINCE"]; v = defaultdict(lambda: defaultdict(list)); e = defaultdict(lambda: defaultdict(list))
for line in open("/home/USER/ai-speed-testing/strata-compare/results/runs.jsonl"):
    try: r = json.loads(line)
    except Exception: continue
    c = str(r.get("config", ""))
    if not c.startswith("r19-b3b-") or str(r.get("started", "")) < since or r.get("error") or r.get("ttft_s") is None: continue
    s = str(r.get("item")); 
    if s not in ("512", "1000", "1500", "2000", "3000"): continue
    k = c.split("-")[2]; v[k][s].append(r["ttft_s"]); st = r.get("server_timings") or {}
    if st.get("prompt_ms") is not None: e[k][s].append(st["prompt_ms"] / 1000)
m = lambda x: sum(x) / len(x) if x else float("nan")
print("| prompt tokens | MAX 3072 (as built): TTFT s (n) | engine read s | MAX 1024: TTFT s (n) | engine read s | 1024 vs 3072 |\n|---|---|---|---|---|---|")
for s in ("512", "1000", "1500", "2000", "3000"):
    a, b = v["m3072"][s], v["m1024"][s]
    print(f"| {s} | {m(a):.3f} ({len(a)}) | {m(e['m3072'][s]):.3f} | {m(b):.3f} ({len(b)}) | {m(e['m1024'][s]):.3f} | {100 * (m(b) / m(a) - 1):+.1f} % |")
PY
bringup/lib/phase_end.sh r19-b3b keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc b3b-end
echo "=== $(date -Is) b3b done"
