#!/bin/bash
# gap6.sh - Basalt round 2 (the user, 10-21, while stage 1 is paused): "Make the stock arm required ... Build stock
# v0.2.1 after the Basalt timing runs if needed (same rules as before). Give Basalt a short, fair tuning pass on the
# 5080 alone before its final numbers: spec length (4/5/7), CPU worker count, and its VRAM/expert-cache settings,
# keeping everything lossless. Report its best lossless config." Results: basalt-ab/results/r2/ (summary.txt).
#   1  the gap: work/r22/port_gap4.sh begin (the hold, the test lock, P021 on 8080 stopped; nothing waits on the hold now:
#      the phase 4 queue has finished and the stage 1 runner is stopped, 10:18)
#   2  Basalt (each step `unshare -rn bash basalt_tune.sh STEP`: loopback only): the tuning stages spec, workers, vram,
#      pcie, perlayer (exact head, seeded tune set, the >2 % rule), then fb (best: normal x2, calibration x2, seeded),
#      fb0 (spec 0: seeded, must equal fb's), fbt (the stock binary = two-stage head: normal x2, calibration x1)
#   3  the stock v0.2.1 build (work/r22/build-stock021.sh; skipped when engine-v021stock is already that build)
#   4  Strata arms on the 5080 alone (with_server.sh, port 8081): s0 (stock, upstream setup's config), s1 (stock + our
#      settings), a1r (ours, the anchor): normal x2 + calibration x1 each; s1s7 and a1s7 (spec 7): the struct fixture x1
#   5  tables (abreport --dir results/r2), the decomposition (r2summary.py), the tuning table (tune_pick.py report)
#   6  port_gap4.sh end: P021 back on 8080 (sha and parking policy checked), lock and hold released. Stage 1 stays
#      stopped (the user restarts it).
# A kernel error stops everything with the gap left open (exit 3).
WS=/home/USER/ai-speed-testing/strata-compare; BA=/home/USER/ai-speed-testing/basalt-ab; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; C=$WS/configs/basalt-ab; R=$BA/results/r2; S=$R/summary.txt; mkdir -p $R
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "basalt-r2-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }

arm() {   # arm NAME ARM=SET:REPS[:ONLY] ...: one Strata config under the guard; work/r22/abarm.sh runs the sets
  local n=$1 L; shift; L=$(elog $C/$n.json); touch $L; local off=$(stat -c %s $L)
  say "S $n ($*)"
  bringup/lib/with_server.sh ab-$n $C/$n.json -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n $*" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|vram after|Error" | tee -a $S
  kc $n
}

say "Basalt round 2 starts: tuning + final numbers, the stock v0.2.1 arm"
work/r22/port_gap4.sh begin "Basalt round 2: tuning + stock arm" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { say "the gap did not open"; exit 1; }
nvidia-smi --query-gpu=index,name,power.limit,memory.used --format=csv,noheader | tee -a $S

say "B Basalt tuning (exact head; each step in a network namespace of its own)"
for st in spec workers vram pcie perlayer; do
  unshare -rn bash $BA/scripts/basalt_tune.sh tune $st 2>&1 | tee -a $S
  kc tune-$st
done
unshare -rn bash $BA/scripts/basalt_tune.sh report > /dev/null 2>&1; cat $R/tune/table.md >> $S
say "B Basalt final numbers at the best lossless config"
for st in fb fb0 fbt; do
  unshare -rn bash $BA/scripts/basalt_tune.sh $st 2>&1 | tee -a $S
  kc $st
done

say "build: stock v0.2.1 (after the Basalt timing runs)"
if [ -x engine-v021stock/strata ] && grep -q "stock v0.2.1 (90767252" engine-v021stock/SOURCE 2> /dev/null \
   && sha256sum -c engine-v021stock/SHA256 > /dev/null 2>&1; then
  say "engine-v021stock is already the stock v0.2.1 build: not rebuilt"
else
  bash work/r22/build-stock021.sh 2>&1 | tail -4 | tee -a $S
  [ ${PIPESTATUS[0]} = 0 ] || say "STOCK BUILD FAILED (strata-v021stock/build.log) - the stock arms are skipped"
fi
kc build-stock

say "S Strata arms (the 5080 alone)"
if [ -x engine-v021stock/strata ]; then
  arm s0 s0=normal:2 s0cal=calib:1
  arm s1 s1=normal:2 s1cal=calib:1
fi
arm a1r a1r=normal:2 a1rcal=calib:1
[ -x engine-v021stock/strata ] && arm s1s7 s1s7=calib:1:C-struct
arm a1s7 a1s7=calib:1:C-struct

say "tables"
$P $BA/scripts/abreport.py --dir $R s0 s1 a1r fb fbt > $R/table-normal.md 2>&1; cat $R/table-normal.md | tee -a $S
$P $BA/scripts/abreport.py --dir $R s0cal s1cal a1rcal fbcal fbtcal s1s7 a1s7 > $R/table-calib.md 2>&1; cat $R/table-calib.md | tee -a $S
TA=$($P -c "import json; print(' '.join(sorted(set(json.load(open('$R/tune/measured.json')).values()))))" 2> /dev/null)
[ -n "$TA" ] && $P $BA/scripts/abreport.py --dir $R $TA > $R/table-tune.md 2>&1 && cat $R/table-tune.md | tee -a $S
$P $BA/scripts/r2summary.py --dir $R > $R/decomposition.md 2>&1; cat $R/decomposition.md | tee -a $S
grep -a -h "seeded" $S | tail -2

say "gap end"
work/r22/port_gap4.sh end 2>&1 | tee -a $S
say "Basalt round 2 done"
