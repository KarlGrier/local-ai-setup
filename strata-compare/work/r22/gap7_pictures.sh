#!/bin/bash
# gap7_pictures.sh - round 22 pictures, image budget (the user, 10-21): a 4K screenshot with small text
# (work/r22/pic_budget.py make: basalt-ab/results/pictures/budget/) at budgets 300 / 1,000 / 2,000 tokens on the CPU
# reader (P021's) and the 4060 Ti reader (engine-r22p021/strata-vision-cuda, cuda_device 1, helper experts 3,300 ->
# 2,800 MiB). Per arm, one test server on 8081 (configs/basalt-ab/pvNNN{c,g}.json, P021's flags, answer_room off):
# the picture twice ("describe", cold then repeat) and once "transcribe" (13 table rows + 6 log lines scored against
# truth.json), the VRAM after the pictures, then W1 + W2 once (the decode cost: the helper card's experts). Run INSIDE a
# gap (8080 down, test lock held) by the next gap's driver: `bash work/r22/gap7_pictures.sh SUMMARY_FILE`.
# pv2000g2 (helper 2,300 MiB) only runs if pv2000g did not finish its transcription (the reader did not fit).
WS=/home/USER/ai-speed-testing/strata-compare; BA=/home/USER/ai-speed-testing/basalt-ab; cd $WS; source bringup/lib/env.sh
P=$WS/.venv/bin/python; C=$WS/configs/basalt-ab; O=$BA/results/pictures/budget; S=${1:-$O/summary.txt}
mkdir -p $O; [ -s $O/truth.json ] || $P -I work/r22/pic_budget.py make $O
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "pic-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }

parm() {   # parm NAME
  local n=$1 L; L=$(elog $C/$n.json); touch $L; local off=$(stat -c %s $L)
  rm -f $O/$n.jsonl
  say "P $n"
  bringup/lib/with_server.sh ab-$n $C/$n.json -- "$P -I $WS/work/r22/pic_budget.py run http://127.0.0.1:8081 $O $n; \
nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ' | sed 's/^/vram after pictures: /'; echo; \
bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $O $n ${n}dec=normal:1:W1,W2" 2>&1 \
    | grep -E "first_answer|transcribe|vram after|tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc $n
}

for n in pv300c pv1000c pv2000c pv300g pv1000g pv2000g; do parm $n; done
grep -q '"transcribe"' $O/pv2000g.jsonl 2> /dev/null || parm pv2000g2

say "pictures: the table"
$P -I work/r22/pic_budget.py score $O pv300c pv1000c pv2000c pv300g pv1000g pv2000g pv2000g2 | tee $O/table.md | tee -a $S
$P $BA/scripts/abreport.py --dir $O pv300cdec pv1000cdec pv2000cdec pv300gdec pv1000gdec pv2000gdec pv2000g2dec 2>&1 \
  | grep -E "^\| (arm|pv)" | tee -a $S
