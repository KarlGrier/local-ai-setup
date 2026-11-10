#!/bin/bash
# a1rec.sh LABEL [SET] — round 13 A1 (env: CFGX="mkcfg ops" extra config changes, e.g. the deep arm's
#   'args:--spec-min-p=0.0001 args+=--suffix-draft,0'; IDS=a,b,... a subset of the set's requests) (+ A2 / A3 routing): the oracle recording on the base. One fresh guarded server
# from configs/R12O-LABEL.json = C*13's flags + the oracle build (engine-r12o: the base + the R12 profile commit + the
# oracle) + STRATA_SPEC_ORACLE=results/r13/oracle/LABEL.txt (+ .h: the hidden vectors entering the draft head) +
# STRATA_R12_ROUTE=1 --dump-routing tmp/r13/route-LABEL.bin (every verified row, its fate, who computed each expert).
# Traffic: warm-up, the LDR pool (prompts/r10/ldr-SET.json, default pool: 60 requests, 30 topics, never a holdout) in
# file order, then the decode items (long reasoning math + code at 4,096, correctness x5, 32K + 768). Your settings.
# The oracle syncs after every draft step and copies the logits: timing is NOT served timing (it records, it does not time).
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 SET=${2:-pool}
source $WS/work/r13/env.sh
cd $WS
mkdir -p results/r13/oracle
CFG=configs/R12O-$L.json
.venv/bin/python work/r13/mkcfg.py R12O-$L Cstar13 exe=engine-r12o/strata env.STRATA_SPEC_ORACLE=$WS/results/r13/oracle/$L.txt \
  env.STRATA_R12_ROUTE=1 args+=--dump-routing,$WS/tmp/r13/route-$L.bin ${CFGX:-} > /dev/null
grep -o -- '"--spec-min-p",[^,]*,[^,]*\|--suffix-draft' $CFG | tr '\n' ' '; echo
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r13/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG, ldr-$SET + decode items)"
work/r13/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
LINE0=$(wc -l < "$ELOG")
SES=$L-$(date +%m%dT%H%M)
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
echo "=== $(date -Is) $L traffic start (oracle line $(wc -l < results/r13/oracle/$L.txt 2>/dev/null || echo 0))"
.venv/bin/python work/r13/ldrbench.py --config $L --engine-log $ELOG --set $SET --session $SES ${IDS:+--ids $IDS}
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $SES"
$B longreason --items math,code --max-tokens 4096
$B correctness
$B speed --sizes 32k --reps 1
work/r13/srv.sh stop
scripts/stopmon.sh $L
tail -n +$LINE0 "$ELOG" > logs/r13/a1rec-$L.engine.log
ls -la results/r13/oracle/$L.txt* tmp/r13/route-$L.bin
echo "=== $(date -Is) $L done (session $SES)"
