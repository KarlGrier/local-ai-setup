#!/bin/bash
# b5d_gate_120k.sh - round 19 B5b, the 120K repeat: in b5c decode after the 120K prompt was 4.9 % lower with the PR's gate
# (one request per arm, 7-8 % spread within each setting), the only place it failed the user's bar. Same build, configs and
# method: B A A B (B = + gate), a fresh guarded server per arm, a warm-up, then 120K r0 and r1 (+768 decoded tokens each).
# Kernel log checked after every server. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB SPEED_FILE
P=.venv/bin/python; R=results/r19; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc b5d-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for arm in gate-a sp-a sp-b gate-b; do
  case $arm in gate*) CFG=configs/r18v42-prc-gate-on.json;; *) CFG=configs/r18v42-prc-gate-sp.json;; esac
  L=r19-b5d-T-$arm; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
  N0=$( [ -f $ELOG ] && wc -l < $ELOG || echo 0)
  echo "=== $(date -Is) $arm: 120K r0 + r1 ($CFG)"
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  if bringup/lib/srv.sh start $L "$CFG"; then
    $P work/r5/warmup.py http://127.0.0.1:8081 > /dev/null
    $P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M) \
      speed --sizes 120k --reps 0,1 > logs/r19/b5d-T-$arm.log 2>&1
    bringup/lib/srv.sh stop
  else echo "$L DID NOT START"; fi
  echo "    gate lines: $(tail -n +$((N0 + 1)) $ELOG | grep -c 'cost-aware draft length ON')"
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
  kc $L
done
$P - <<'PY' | tee $R/b5d-gate-120k.md
import json
from collections import defaultdict
d = defaultdict(list)
for line in open("/home/USER/ai-speed-testing/strata-compare/results/runs.jsonl"):
    try: r = json.loads(line)
    except Exception: continue
    c = str(r.get("config", ""))
    for pre in ("r19-b5c-T-", "r19-b5d-T-"):
        if c.startswith(pre) and r.get("item") == "120k":
            d["gate" if "gate" in c else "sp"].append((c.replace("r19-", "").replace("-T", ""), r.get("rep"), round(r["decode_tps"], 1)))
print("| setting | decode after 120K, each request (run, rep, tok/s) | mean |\n|---|---|---|")
m = {}
for k in ("sp", "gate"):
    v = [x[2] for x in d[k]]; m[k] = sum(v) / len(v) if v else float("nan")
    print(f"| {'STRATA_SPEC_PROB=1' if k == 'sp' else '+ STRATA_COST_GATE (PR)'} | {'; '.join(f'{a} r{b} {c}' for a, b, c in d[k])} | {m[k]:.1f} |")
print(f"\ngate vs SPEC_PROB alone after 120K (b5c + b5d, n = {len(d['gate'])} / {len(d['sp'])}): {100 * (m['gate'] / m['sp'] - 1):+.1f} %")
PY
bringup/lib/phase_end.sh r19-b5d keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc b5d-end
echo "=== $(date -Is) b5d done"
