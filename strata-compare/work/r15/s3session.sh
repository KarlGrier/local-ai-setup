#!/bin/bash
# s3session.sh LABEL CONFIG.json [PARTS] — round 15 step 3: one placement measured on ONE guarded server (127.0.0.1:8081,
# cold model page cache): warm-up (discarded); prompts of 8K / 32K / 64K / 120K, each + 768 decoded tokens (time to
# first token and the decode right after it); the decode screen's items (long reasoning math + code at a 4,096-token
# cap, correctness x5); the LDR screen's 12 requests (prompts/r10/ldr-screen.json); the 120K needle document (6
# questions, needle2.py). Then the CLI time split (s3split.sh). Your settings (the config's shared settings).
# PARTS (default "prompts dec ldr needle split") picks a subset. The memory guard's floors come from the environment
# (GUARD_MEM_GIB / GUARD_VRAM_MIB / GUARD_SWAP_GROW_GIB). Records: results/runs.jsonl (config = LABEL), the server log,
# bringup/out/logs/guard/srv-LABEL.csv, logs/r15/ssd.csv (the drive's temperatures and reads, logged all round).
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2 PARTS=${3:-"prompts dec ldr needle split"}
source $WS/bringup/lib/env.sh
cd $WS
P=.venv/bin/python
ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
OUT=results/r15/s3; mkdir -p $OUT
echo "=== $(date -Is) s3session $L start ($CFG) parts: $PARTS"
echo "floors: MemAvailable ${GUARD_MEM_GIB:-20} GiB, 5080 ${GUARD_VRAM_MIB:-300} MiB, swap growth ${GUARD_SWAP_GROW_GIB:-off} GiB"
echo "ssd before: $(tail -1 logs/r15/ssd.csv)"
if echo "$PARTS" | grep -qE 'prompts|dec|ldr|needle'; then
  $P scripts/evict.py ${EVICT_GLOB:-$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf} > /dev/null
  (setsid nohup $P scripts/monitor.py --pid-pattern '/strata --serve' --out bringup/out/logs/monitor-$L > /dev/null 2>&1 &)
  EL0=$(wc -l < "$ELOG" 2>/dev/null || echo 0)
  bringup/lib/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; echo "s3session $L: DID NOT START"; tail -40 "$ELOG" > $OUT/$L-nostart.txt; exit 1; }
  # the engine's start lines: placement, budget, page-locking, the file tier's mode, slots, VRAM, context
  tail -n +$((EL0 + 1)) "$ELOG" | grep -E 'resident|budget|page-lock|file tier|unbuffered|expert cache [0-9a]|VRAM free with|CUDA1|peer|layer split|stage|max context|max-context|kv|arena|prefetch|WARNING|refus' | head -40 > $OUT/$L-start.txt
  cat $OUT/$L-start.txt | cut -c1-220
  EP=$(pgrep -f "$($P -c "import json; print(json.load(open('$CFG'))['exe'])") --serve" | head -1)
  echo "engine pid $EP: $(grep -E 'VmPin|VmLck|VmRSS' /proc/$EP/status 2>/dev/null | tr -s ' \t' ' ' | tr '\n' ' ')"
  echo "vram after load: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
  $P work/r5/warmup.py http://127.0.0.1:8081
  B="$P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
  if echo "$PARTS" | grep -q prompts; then
    for sz in 8k 32k 64k 120k; do SPEED_FILE=r15/speed-r15 $B speed --sizes $sz --reps 0; done
  fi
  if echo "$PARTS" | grep -q dec; then
    $B longreason --items math,code --max-tokens 4096
    $B correctness
  fi
  if echo "$PARTS" | grep -q ldr; then
    $P bringup/lib/ldrbench.py --config $L --engine-log $ELOG --set screen --session $L-ldr-$(date +%m%dT%H%M)
  fi
  if echo "$PARTS" | grep -q needle; then
    NEEDLE_DIR=$WS/work/r5/needle2 $P bringup/lib/needle2.py ask --label $L --sizes 120k --runs 0 2>&1 | tail -4
  fi
  echo "engine at end: $(grep -E 'VmPin|VmLck|VmRSS|VmSwap' /proc/$EP/status 2>/dev/null | tr -s ' \t' ' ' | tr '\n' ' ')"
  bringup/lib/srv.sh stop
  scripts/stopmon.sh $L
  tail -n +$((EL0 + 1)) "$ELOG" > $OUT/$L-engine.log
fi
if echo "$PARTS" | grep -q split; then
  work/r15/s3split.sh $L "$CFG"
fi
echo "ssd after: $(tail -1 logs/r15/ssd.csv)"
echo "=== $(date -Is) s3session $L done"
