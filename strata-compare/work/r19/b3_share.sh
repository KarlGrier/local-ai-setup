#!/bin/bash
# b3_share.sh - round 19 Part B step 3: STRATA_PREFILL_CPU_SHARE=0.4 against 0 on the candidate (C*16.1's flags on v0.1.42):
#   a. exact repeat of exact7's four short-prompt items (greedy / seeded math and code, CLI, fixed computation) with 0.4, twice
#   b. served time to first token at 512 and 1,000 tokens, A B B A (A = 0.4, B = 0): fresh guarded server per arm, the 9.5K
#      + two ~600-token warm-ups, 6 prompts of each size (prompts/r16/ttft-short.json), 64 tokens each (Round 16's method)
#   c. if 0.4 is >= 3 % faster at either size: the acceptance suite with 0.4 (candidate + its twin)
# Your rule: keep 0.4 only if it passes the suite and is >= 3 % faster. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB SPEED_FILE
P=.venv/bin/python; R=results/r19; export PROMPT_DIR=$WS/bringup/out/r19/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
echo "=== $(date -Is) b3 a. repeat with 0.4"
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"; S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
for n in 1 2; do
  bringup/lib/run.sh r19-sh04-$n-x-math configs/r19-cand-sh04.json math 1024 $X > /dev/null
  PROF_SAMPLING="$S" bringup/lib/run.sh r19-sh04-$n-s-math configs/r19-cand-sh04.json math 1024 $X > /dev/null
  bringup/lib/run.sh r19-sh04-$n-x-code configs/r19-cand-sh04.json code 1024 $X > /dev/null
  PROF_SAMPLING="$S" bringup/lib/run.sh r19-sh04-$n-s-code configs/r19-cand-sh04.json code 1024 $X > /dev/null
done
grep -h 'CPU share' bringup/out/logs/prof/r19-sh04-1-x-math.err | head -2 | cut -c1-200
$P - <<'PY' | tee $R/b3-share-repeat.md
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
print("| item | 0.4 run 1 | 0.4 run 2 | 0.4 repeats | share off (exact7 r19-e7-cand) | prompt ms 0.4 (1 / 2) | prompt ms off |")
print("|---|---|---|---|---|---|---|")
for it in ("x-math", "s-math", "x-code", "s-code"):
    a, b, o = parse(f"r19-sh04-1-{it}"), parse(f"r19-sh04-2-{it}"), parse(f"r19-e7-cand-{it}")
    print(f"| {it} | {a['out']} | {b['out']} | {'yes' if a['out'] == b['out'] else 'NO'} | {o['out']} | {a.get('pf_ms', 0):.0f} / {b.get('pf_ms', 0):.0f} | {o.get('pf_ms', 0):.0f} |")
PY
echo "=== $(date -Is) b3 b. served TTFT, A B B A"
SS=$(date -Iseconds | cut -c1-19)
for arm in f04-a off-a off-b f04-b; do
  L=r19-sh-$arm; case $arm in f04*) CFG=configs/r19-cand-sh04.json;; *) CFG=configs/r19-cand.json;; esac
  ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  echo "=== $(date -Is) $L start ($CFG)"
  bringup/lib/srv.sh start $L "$CFG" || { echo "$L DID NOT START"; continue; }
  grep -E 'CPU share' "$ELOG" | tail -1 | cut -c1-200
  $P work/r5/warmup.py http://127.0.0.1:8081
  B="$P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M) --max-tokens 64"
  SPEED_FILE=r16/ttft-short $B speed --sizes w600 > /dev/null
  SPEED_FILE=r16/ttft-short $B speed --sizes 512,1000 > /dev/null
  bringup/lib/srv.sh stop
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
done
SINCE=$SS $P work/r16/s1_table.py OFF=r19-sh-off-a,r19-sh-off-b F04=r19-sh-f04-a,r19-sh-f04-b | tee $R/b3-share-ttft.md
GAIN=$($P - "$R/b3-share-ttft.md" <<'PY'
import re, sys
g = [float(m) for m in re.findall(r"\| ([-+]?[\d.]+) % \| [-+]?[\d.]+ % \|$", open(sys.argv[1]).read(), re.M)]
print("yes" if g and min(g) <= -3.0 else "no")
PY
)
echo "0.4 >= 3 % faster at either size: $GAIN"
if [ "$GAIN" = yes ]; then
  echo "=== $(date -Is) b3 c. acceptance suite with 0.4"
  bringup/acceptance.sh acc-r19-sh04 configs/r19-cand-sh04.json configs/r19-twin-sh04.json > $R/b3-accept-sh04.txt 2>&1
  tail -22 bringup/out/accept/acc-r19-sh04/table.md
fi
bringup/lib/phase_end.sh r19-b3 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) b3 done"
