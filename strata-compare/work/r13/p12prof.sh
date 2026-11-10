#!/bin/bash
# p12prof.sh LABEL CONFIG.json — round 13 Phase 0: the profiling pass on ONE fresh guarded server (srv.sh, 8081), cold
# model page cache: warm-up, the LDR-shaped screen (prompts/r10/ldr-screen.json, 12 requests in file order), the decode
# screen's items (long reasoning math + code at 4,096, correctness x5, one 32K prompt + 768), then the chat-switch
# scenario (work/r13/chatswitch.py: A, B, back to A, back to B). Your settings (the config's shared settings). With the
# profile build's env (STRATA_R12_PROF / STRATA_VERIFY_PROFILE / STRATA_R11_LAYERPROF / STRATA_DECODE_TIMING) the
# engine log gets, per request, the R12 window / block / draft-round / lead lines and the per-layer profile.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/work/r13/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r13/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG)"
work/r13/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
LINE0=$(wc -l < "$ELOG"); echo "engine log $ELOG from line $LINE0"
SES=$L-$(date +%m%dT%H%M)
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r13/ldrbench.py --config $L --engine-log $ELOG --set screen --session $SES
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $SES"
$B longreason --items math,code --max-tokens 4096
$B correctness
$B speed --sizes 32k --reps 1
.venv/bin/python work/r13/chatswitch.py --config $L --engine-log $ELOG --session $SES
echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
work/r13/srv.sh stop
scripts/stopmon.sh $L
tail -n +$LINE0 "$ELOG" > logs/r13/prof-$L.engine.log
echo "=== $(date -Is) $L done (engine log part: logs/r13/prof-$L.engine.log; session $SES)"
