#!/bin/bash
# gap5b.sh - Basalt A/B GPU block (the user, 10-21: at the end of gap 5, then P021 back on 8080 and the queue released
# for stage 1; results to the user as soon as they are in). Called by gap5.sh before end_gap, inside the gap (queue held,
# test lock, 8080 down). Plan: basalt-ab/PLAN.md. Every server binds 127.0.0.1; one model server at a time.
#   S  our arms (with_server.sh, port 8081; answer_room off so both engines think to the same cap):
#        a (both cards, spec 4) | a1 (the 5080 alone, spec 4) | b4 b5 b7 (both cards + Basalt's tuned MTP dense part)
#        | b7v (b7 + Basalt's draft vocabulary, 1 rep) | a1s7 (the 5080 alone, spec 7: calibration fixtures)
#   V  pictures: vcpu (the reader on the CPU, as served) vs vgpu (the CUDA reader on the 4060 Ti, helper slots 2800)
#   D  logit dumps of our engine (two cards; the 5080 alone) on the teacher-forced corpus
#   B  Basalt (basalt-ab/scripts/basalt_block.sh): stock on the 5080 alone, the same client; calibration; its own bench;
#      greedy spec on/off identity; logit dump; the exact-head debug build (HEADCHECK)
# A kernel error stops everything with the gap left open (the caller's rule).
WS=/home/USER/ai-speed-testing/strata-compare; BA=/home/USER/ai-speed-testing/basalt-ab; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=$WS/.venv/bin/python; C=$WS/configs/basalt-ab; R=$BA/results; S=$R/summary.txt; mkdir -p $R/pictures $R/dumps
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "basalt-ab-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }

arm() {   # arm NAME SET REPS [ONLY]: one of our configs under the guard, the client's requests, the engine-log slice
  local n=$1 set=$2 reps=$3 only=${4:-} L; L=$(elog $C/$n.json); touch $L; local off=$(stat -c %s $L)
  say "S $n ($set x$reps${only:+ $only})"
  bringup/lib/with_server.sh ab-$n $C/$n.json -- "$P $BA/scripts/abrun.py run --base http://127.0.0.1:8081 --arm $n --set warmup --reps 1 --out $R/$n.warmup.jsonl; $P $BA/scripts/abrun.py run --base http://127.0.0.1:8081 --arm $n --set $set --reps $reps ${only:+--only $only}" 2>&1 \
    | grep -E "tok/s|ready|exited|refus" | tee -a $S
  tail -c +$((off + 1)) $L > $R/$n.englog; cp $R/$n.englog $R/$n.startlog
  kc $n
}

say "Basalt A/B GPU block starts (inside gap 5)"
[ -s tmp/port-gap.lockpid ] || { say "the gap is not open"; exit 1; }
nvidia-smi --query-gpu=index,name,power.limit,memory.used --format=csv,noheader | tee -a $S

arm a normal 2
arm a1 normal 2
arm b4 normal 2
arm b5 normal 2
arm b7 normal 2
arm b7v normal 1
arm a1s7 calib 2

say "V pictures"
for v in vcpu vgpu; do
  L=$(elog $C/$v.json); touch $L; off=$(stat -c %s $L)
  bringup/lib/with_server.sh ab-$v $C/$v.json -- "for img in $WS/strata-r22p021/docs/terminal-previews/serving-110-stages.png $R/pictures/large-4032x3024.jpg; do $P $WS/work/r22/vision_check.py http://127.0.0.1:8081 \$img $R/pictures/$v-\$(basename \$img .png); done; nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader; $P $BA/scripts/abrun.py run --base http://127.0.0.1:8081 --arm $v --reps 2 --only W1,W2" 2>&1 \
    | tee $R/pictures/$v.txt | grep -E -v "^\s*$" | tail -16 | tee -a $S
  tail -c +$((off + 1)) $L > $R/$v.englog; cp $R/$v.englog $R/$v.startlog
  kc $v
done

say "D logit dumps (our engine, CLI)"
for d in a a1; do
  (exec 8> $WS/tmp/gpu-test.lock; flock -s 8; $P $BA/scripts/strata_dump.py $C/$d.json $R/dumps/strata-$d.bin) 2>&1 | tee -a $S
  kc dump-$d
done
$P $BA/scripts/logitcmp.py $R/dumps/strata-a.bin $R/dumps/strata-a1.bin --label "ours: two cards vs the 5080 alone, all 1,024 rows" | tee -a $S

say "B Basalt (each step in a network namespace of its own: unshare -rn)"
for st in c1 c0 bench hc ppl; do
  unshare -rn bash $BA/scripts/basalt_block.sh $st 2>&1 | tee -a $S
  kc basalt-$st
done

say "lossless: the same 511 teacher-forced rows (positions 512-1022), against ours on the 5080 alone"
$P $BA/scripts/topcmp.py $R/dumps/strata-a1.bin $R/dumps/strata-a.bin --label "ours, two cards (rounding reference)" | tee -a $S
$P $BA/scripts/topcmp.py $R/dumps/strata-a1.bin $R/dumps/basalt-exact.tsv.top --label "Basalt, exact Q6_K head" | tee -a $S
$P $BA/scripts/topcmp.py $R/dumps/strata-a1.bin $R/dumps/basalt-two.tsv.top --label "Basalt, two-stage head (as it samples)" | tee -a $S
$P - $R/dumps/basalt-two.tsv.top $R/dumps/basalt-exact.tsv.top <<'PY' 2>&1 | tee -a $S
import sys
a = [l.rstrip("\n").split("\t") for l in open(sys.argv[1])]; b = [l.rstrip("\n").split("\t") for l in open(sys.argv[2])]
n = min(len(a), len(b))
same64 = sum(x[4:] == y[4:] for x, y in zip(a, b)); same20 = sum(x[4:24] == y[4:24] for x, y in zip(a, b))
print(f"Basalt two-stage vs exact head, {n} rows: top-20 ids+logits bit-identical {same20}, top-64 {same64}")
PY

say "tables"
$P $BA/scripts/abreport.py a a1 b4 b5 b7 b7v vcpu vgpu c1 > $R/table-normal.md 2>&1; cat $R/table-normal.md | tee -a $S
$P $BA/scripts/abreport.py a1s7 c1cal > $R/table-calib.md 2>&1; cat $R/table-calib.md | tee -a $S
grep -a -h "HEADCHECK total" $R/c1hc.englog 2> /dev/null | tail -1 | tee -a $S
say "Basalt A/B GPU block done"
