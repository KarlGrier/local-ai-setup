#!/bin/bash
# q4session.sh LABEL CONFIG.json — round 16 Q4 check (1 hour at most, not promoted): UD-Q4_K_XL on the step-3 build, the
# 5080 + a RAM budget, your exception's floors (MemAvailable >= 6 GiB, 5080 >= 300 MiB, a stop if swap grows > 4 GiB; the
# chat cache at 2 GiB), ONE guarded server on 127.0.0.1:8081, cold model page cache: the 9.5K warm-up; the decode screen's
# items exactly as decscreen.sh runs them (long reasoning math + code at 4,096 tokens, correctness x5, 32K r1 + 768); the
# LDR screen's 12 requests (ldrbench --set screen); a 120K prompt (r1) + 768; the 120K needle document once (6 questions,
# needle2.py). Your sampling (the config's shared settings). Records: results/runs.jsonl (config = LABEL), the engine's
# start lines -> results/r16/LABEL-start.txt, the guard's CSV.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/bringup/lib/env.sh
cd $WS
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
P=.venv/bin/python
ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
echo "=== $(date -Is) q4session $L start ($CFG); floors MemAvailable 6 GiB, 5080 300 MiB, swap +4 GiB; swap now $(free -m | awk '/Swap/ {print $3}') MiB"
$P scripts/evict.py $EVICT_GLOB > /dev/null
(setsid nohup $P scripts/monitor.py --pid-pattern '/strata --serve' --out bringup/out/logs/monitor-$L > /dev/null 2>&1 &)
EL0=$(wc -l < "$ELOG" 2>/dev/null || echo 0)
bringup/lib/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; echo "q4session $L: DID NOT START"; tail -40 "$ELOG"; exit 1; }
tail -n +$((EL0 + 1)) "$ELOG" | grep -E 'resident|budget|page-lock|file tier|unbuffered|expert cache [0-9a]|VRAM free with|max context|arena|WARNING|refus|CPU share|stage buffers|transient' | head -40 > results/r16/$L-start.txt
cut -c1-220 results/r16/$L-start.txt
EP=$(pgrep -f "$($P -c "import json; print(json.load(open('$CFG'))['exe'])") --serve" | head -1)
echo "engine pid $EP: $(grep -E 'VmPin|VmLck|VmRSS' /proc/$EP/status 2>/dev/null | tr -s ' \t' ' ' | tr '\n' ' '); MemAvailable $(awk '/MemAvailable/ {printf "%.1f GiB", $2/1048576}' /proc/meminfo)"
echo "vram after load: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
$P work/r5/warmup.py http://127.0.0.1:8081
B="$P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B longreason --items math,code --max-tokens 4096
$B correctness
$B speed --sizes 32k --reps 1
$P bringup/lib/ldrbench.py --config $L --engine-log $ELOG --set screen --session $L-ldr-$(date +%m%dT%H%M)
$B speed --sizes 120k --reps 1
NEEDLE_DIR=$WS/work/r5/needle2 $P bringup/lib/needle2.py ask --label $L --sizes 120k --runs 0 2>&1 | tail -4
echo "engine at end: $(grep -E 'VmPin|VmLck|VmRSS|VmSwap' /proc/$EP/status 2>/dev/null | tr -s ' \t' ' ' | tr '\n' ' ')"
grep -ciE 'error|stall|no progress|watchdog' <(tail -n +$((EL0 + 1)) "$ELOG") | sed 's/^/engine log error-ish lines: /'
bringup/lib/srv.sh stop
scripts/stopmon.sh $L
tail -2 bringup/out/logs/guard/summary.txt
echo "=== $(date -Is) q4session $L done"
