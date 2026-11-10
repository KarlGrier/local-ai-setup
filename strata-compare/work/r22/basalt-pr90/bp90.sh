#!/bin/bash
# bp90.sh - the Basalt PR #90 check (Karl 10-30): Basalt's "community-1" prompts (data/bench/*.ids at b2fe96bf30, read as
# data; no Basalt build, install or run) sent to P021m (its test form r21n-candpm = P021m's engine flags without --vision)
# and the v0.2.8 port candidate r28h (gap 15's), on 127.0.0.1:8081 inside a port gap (8080 stopped, P021m back at the end).
#   cold  Basalt's method: a fresh engine per measurement - one server for the three decode fixtures (conv, struct, prose in
#         that order), one for the 16K prefill, one for the 64K prefill; 3 passes, builds in turned order (M H / H M / M H)
#   warm  one server per build, 4 passes of everything (pass 1 = the first in the process; passes 2-4 = warm)
# Client: bp90_client.py (prompt ids checked against our tokenizer + template; Basalt's request keys, min_p 0 and no
# penalties). Report: bp90_report.py -> results/r22/basalt-pr90/report.md. A kernel error stops everything with the gap
# open (exit 3).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; B=$WS/work/r22/basalt-pr90; O=$WS/results/r22/basalt-pr90; S=$O/summary.txt; C=$WS/configs
mkdir -p $O
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "bp90-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
cfg_of() { case $1 in M) echo $C/r21n-candpm.json;; H) echo $C/r28h.json;; esac; }
tree_of() { case $1 in M) echo $WS/strata-r22p021m;; H) echo $WS/strata-r22p028;; esac; }
run() {   # run SESSION BUILD SETS PASSES FIRST OUT
  local s=$1 b=$2
  bringup/lib/with_server.sh bp90-$s $(cfg_of $b) -- "$WS/.venv/bin/python -I $B/bp90_client.py http://127.0.0.1:8081 --label $s --sets $3 --passes $4 --first-pass $5 --tree $(tree_of $b) --out $6" 2>&1 \
    | grep -E " pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  kc $s
}

work/r22/port_gap4.sh begin "Basalt PR #90 check: Basalt's community-1 prompts on P021m and the v0.2.8 port (cold + warm)" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
[ -x engine-r22p028/strata ] && grep -q 'v0.2.8 + 27 commits' engine-r22p028/SOURCE || { say "the v0.2.8 port build is not in place - stopped"; end_gap; exit 1; }

say "cold: a fresh engine per measurement, 3 passes in turned order"
for k in 1 2 3; do
  if [ $k = 2 ]; then order="H M"; else order="M H"; fi
  for b in $order; do
    for set in decode pp16k pp64k; do run cold-$b-$set-$k $b $set 1 $k $O/cold-$b.jsonl; done
  done
done
say "warm: one engine per build, 4 passes (pass 1 = the first in the process)"
for b in H M; do run warm-$b $b decode,pp16k,pp64k 4 1 $O/warm-$b.jsonl; done

end_gap
bringup/lib/kcheck.sh bp90-end && say "kcheck clean" || say "KCHECK FAILED at the end"
$P -I $B/bp90_report.py $O > $O/report.md 2>&1
cat $O/report.md >> $S
say "Basalt PR #90 check done after $(( ($(date +%s) - T0) / 60 )) min (report: results/r22/basalt-pr90/report.md)"
