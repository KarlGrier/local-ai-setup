#!/bin/bash
# gap6b.sh - Basalt round 2, the stock-defaults arm again (10-21 11:15): s0 was stopped by the guard in gap 6 (5080 free
# 276 MiB < 300 with upstream's default reserve and the 106K draft head); now with --vram-reserve-mib 800. Then the
# round 2 tables and the decomposition again, and the gap end.
WS=/home/USER/ai-speed-testing/strata-compare; BA=/home/USER/ai-speed-testing/basalt-ab; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; C=$WS/configs/basalt-ab; R=$BA/results/r2; S=$R/summary.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "basalt-r2-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
say "gap 6b: the stock-defaults arm again (s0, --vram-reserve-mib 800)"
work/r22/port_gap4.sh begin "Basalt round 2: the stock-defaults arm again" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { say "the gap did not open"; exit 1; }
rm -f $R/s0.jsonl $R/s0cal.jsonl $R/s0*.englog $R/s0*.startlog
n=s0; L=$(elog $C/$n.json); touch $L; off=$(stat -c %s $L)
say "S $n (s0=normal:2 s0cal=calib:1)"
bringup/lib/with_server.sh ab-$n $C/$n.json -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n s0=normal:2 s0cal=calib:1" 2>&1 \
  | grep -E "tok/s|ready|exited|refus|vram after|Error|GUARD" | tee -a $S
kc $n
say "tables"
$P $BA/scripts/abreport.py --dir $R s0 s1 a1r fb fbt > $R/table-normal.md 2>&1; cat $R/table-normal.md >> $S
$P $BA/scripts/abreport.py --dir $R s0cal s1cal a1rcal fbcal fbtcal s1s7 a1s7 > $R/table-calib.md 2>&1; cat $R/table-calib.md >> $S
$P $BA/scripts/r2summary.py --dir $R > $R/decomposition.md 2>&1; cat $R/decomposition.md | tee -a $S
say "gap end"
work/r22/port_gap4.sh end 2>&1 | tee -a $S
