#!/bin/bash
# session2.sh - r17: v0.1.41's CPU prompt-read share on stock v0.1.41 (IQ3_S, this PC's flags): does a FIXED share
# (STRATA_PREFILL_CPU_SHARE=0.4) repeat where auto does not, and what does each give on short prompts?
#   a. CLI repeatability: exact7's four short items (greedy / seeded math and code, 1,024 tokens, fixed computation), auto x2,
#      0.4 x2 (output hashes; v0.1.41 with the share off is known to repeat 7/7: Round 16 r16z)
#   b. served TTFT, A B C C B A = auto / 0.4 / off: fresh guarded server per arm, the 9.5K + two ~600-token warm-ups, 6 prompts
#      of 512 and 6 of 1,000 tokens (prompts/r16/ttft-short.json), 64 tokens each (Round 16 step 1's method)
# Stops C*16 on 8080 first (one model server at a time), ends with C*16 on 8080 and a fresh 48-hour monitor.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r17; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; C=work/r17/cfg; R=results/r17
step() { echo "=== $(date -Is) $*"; }
step "stop 8080 and the monitor"
[ -f logs/r17/uptime-c16/monitor.pid ] && kill "$(cat logs/r17/uptime-c16/monitor.pid)" 2>/dev/null
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '/strata --serve' > /dev/null || break; sleep 1; done
step "a. repeatability"
export PROMPT_DIR=$WS/bringup/out/r16/prompts
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"; S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
for arm in auto:1 f04:1 f04:2 auto:2; do
  IFS=: read -r o n <<< "$arm"
  bringup/lib/run.sh r17-sh-$o-$n-x-math $C/sh-$o.json math 1024 $X > /dev/null
  PROF_SAMPLING="$S" bringup/lib/run.sh r17-sh-$o-$n-s-math $C/sh-$o.json math 1024 $X > /dev/null
  bringup/lib/run.sh r17-sh-$o-$n-x-code $C/sh-$o.json code 1024 $X > /dev/null
  PROF_SAMPLING="$S" bringup/lib/run.sh r17-sh-$o-$n-s-code $C/sh-$o.json code 1024 $X > /dev/null
done
$P - > $R/share-repeat.md <<'PY'
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
print("| item | auto run 1 | auto run 2 | auto repeats | 0.4 run 1 | 0.4 run 2 | 0.4 repeats | prompt ms auto (1 / 2) | prompt ms 0.4 (1 / 2) |")
print("|---|---|---|---|---|---|---|---|---|")
for it in ("x-math", "s-math", "x-code", "s-code"):
    d = {k: parse(f"r17-sh-{k}-{it}") for k in ("auto-1", "auto-2", "f04-1", "f04-2")}
    h = {k: v["out"] for k, v in d.items()}; pm = {k: v.get("pf_ms", 0) for k, v in d.items()}
    print(f"| {it} | {h['auto-1']} | {h['auto-2']} | {'yes' if h['auto-1'] == h['auto-2'] else 'NO'} | {h['f04-1']} | {h['f04-2']} | "
          f"{'yes' if h['f04-1'] == h['f04-2'] else 'NO'} | {pm['auto-1']:.0f} / {pm['auto-2']:.0f} | {pm['f04-1']:.0f} / {pm['f04-2']:.0f} |")
PY
cat $R/share-repeat.md
step "b. served TTFT"
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
SS=$(date -Iseconds | cut -c1-19)
for arm in auto-a f04-a off-a off-b f04-b auto-b; do
  L=r17-sh-srv-$arm; CFG=$C/sh-${arm%-*}.json
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
  tail -1 bringup/out/logs/guard/summary.txt
done
{ echo "auto vs fixed 0.4:"; SINCE=$SS $P work/r16/s1_table.py AUTO=r17-sh-srv-auto-a,r17-sh-srv-auto-b F04=r17-sh-srv-f04-a,r17-sh-srv-f04-b
  echo; echo "auto vs off:"; SINCE=$SS $P work/r16/s1_table.py AUTO=r17-sh-srv-auto-a,r17-sh-srv-auto-b OFF=r17-sh-srv-off-a,r17-sh-srv-off-b
  echo; echo "off vs fixed 0.4:"; SINCE=$SS $P work/r16/s1_table.py OFF=r17-sh-srv-off-a,r17-sh-srv-off-b F04=r17-sh-srv-f04-a,r17-sh-srv-f04-b; } > $R/share-ttft.md 2>&1
cat $R/share-ttft.md
step "c. #652 and #567 on C*16 (same binary; the PR off by its switch)"
for arm in def-a encold-a commitall-a commitall-b encold-b def-b; do
  L=r17-pr-$arm; CFG=$C/c16-${arm%-*}.json
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  echo "=== $(date -Is) $L start ($CFG)"
  bringup/lib/srv.sh start $L "$CFG" || { echo "$L DID NOT START"; continue; }
  $P work/r5/warmup.py http://127.0.0.1:8081
  case $arm in def-*|commitall-*) timeout 1800 $P bringup/lib/followup652.py http://127.0.0.1:8081 $L plain think 2>&1 | grep -E 'follow-ups|resumed|re-read' | tail -3;; esac
  case $arm in def-*|encold-*) timeout 1800 $P work/r17/ttft567b.py http://127.0.0.1:8081 $L 2>&1 | grep -E 'chat: first read' ;; esac
  bringup/lib/srv.sh stop
  tail -1 bringup/out/logs/guard/summary.txt
done
$P work/r17/ttft567_table.py NEW=r17-pr-def-a,r17-pr-def-b OLD=r17-pr-encold-a,r17-pr-encold-b > $R/ttft567.md 2>&1; cat $R/ttft567.md
step "e. PR #1455 (head 94befcee, #567's approach on current main) on stock v0.1.41: cached-turn TTFT, reuse on vs STRATA_PROMPT_REUSE=0"
for arm in on-a off-a off-b on-b; do
  L=r17-p1455-$arm; CFG=$C/p1455-${arm%-*}.json
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  echo "=== $(date -Is) $L start ($CFG)"
  bringup/lib/srv.sh start $L "$CFG" || { echo "$L DID NOT START"; continue; }
  $P work/r5/warmup.py http://127.0.0.1:8081
  timeout 1800 $P work/r17/ttft567b.py http://127.0.0.1:8081 $L 2>&1 | grep -E 'chat: first read'
  bringup/lib/srv.sh stop
  tail -1 bringup/out/logs/guard/summary.txt
done
$P work/r17/ttft567_table.py REUSE=r17-p1455-on-a,r17-p1455-on-b OFF=r17-p1455-off-a,r17-p1455-off-b > $R/ttft1455.md 2>&1; cat $R/ttft1455.md
step "phase end"
bringup/lib/phase_end.sh r17b keep
(setsid nohup $P work/r13/uptime_monitor.py --out logs/r17/uptime-c16 > /dev/null 2>&1 < /dev/null &)
sleep 5; echo "monitor: $(cat logs/r17/uptime-c16/monitor.pid 2>/dev/null)"
step "d. #567 ids on the v0.1.41-based tree (CPU only; C*16 idle on 8080)"
timeout 3600 nice $P bringup/lib/t567_ids.py $WS/strata-cstar16 2000 > $R/t567-ids.txt 2>&1; tail -5 $R/t567-ids.txt
step "f. PR #1455: its own tests and the id check on v0.1.41 (CPU only)"
(cd work/r17/pr1455 && timeout 1200 nice $WS/$P -m unittest serve.test_prompt_encoder serve.test_server -q) > $R/p1455-unittest.txt 2>&1; tail -4 $R/p1455-unittest.txt
(cd bringup/out/r16/strata-stock && timeout 1200 nice $WS/$P -m unittest serve.test_server -q) > $R/stock041-unittest.txt 2>&1; tail -4 $R/stock041-unittest.txt
timeout 3600 nice $P work/r17/t567_ids_any.py $WS/work/r17/pr1455 2000 > $R/p1455-ids.txt 2>&1; tail -5 $R/p1455-ids.txt
step "session2 done"
