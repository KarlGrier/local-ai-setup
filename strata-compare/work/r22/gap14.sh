#!/bin/bash
# gap14.sh - round 22 gap 14 (Karl 10-29: "Go on the per-switch check ... the KL check and the check-2 arm without
# PREFILL_V2, without GR_FORK, and without both. If one switch is the cause and can't be fixed cleanly, port the rest
# without it and report the prompt-speed cost."). Gap 13 (results/r22/gap13): the hand-ported port r27h failed the KL
# rule (mean 0.585) and distribution check (2) on both arms (speculation off p 0.006, hand-ported path p 0.020); check (1)
# passed (p 0.772). Gap 12's 0.2.7 build without our switches passed both. No build here (gap 13's binaries).
#   1 KL           pf_yardstick long40 on r27h-nov2 / -nofork / -noboth vs gap 8's references (kernel_rule2, with r27h)
#   2 check (2)    each variant's speculation-off twin arm (r27t-hnospec-<v>), arith-j3 T 0.6, 4,000, vs ITS OWN
#                  probabilities (strata_logp in that arm; sampling_probe.py analyze own)
#   3 the pick     a variant passes when its KL line says PASS and its check-(2) p >= 0.05; preference: the one-switch drops
#                  (nov2, nofork - both if both pass), else noboth
#   4 checks (1)+(2) on the speculative path of each passing variant: r27t-ess-<v> (4,000) vs its nospec arm (check 1)
#                  and vs its own probabilities (check 2) - Karl: every p >= 0.05 before any switch
#   5 speed        r27h vs each passing variant, 2 passes in turned order (abarm.sh): the prompt-speed cost of the drop
# Nothing switches here; 8080 gets P021m back at the end. A kernel error stops everything with the gap open (exit 3).
# Output: results/r22/gap14/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab; O=$WS/results/r22/gap14; S=$O/summary.txt; C=$WS/configs
Y8=$WS/results/r22/gap8/pfy; Y13=$WS/results/r22/gap13/pfy; Y=$O/pfy; SPO=$O/sp; mkdir -p $O $Y $SPO logs/r22 tmp/r22
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g14-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
starts() { local L; L=$(elog $2); say "  start lines $1: exact $(grep -c 'EXACT speculative sampling on' $L 2>/dev/null), v2 $(grep -c 'STRATA_PREFILL_V2' $L 2>/dev/null), fork $(grep -c -i 'GR_FORK' $L 2>/dev/null)"; }
pval() { grep arith-j3 "$1" 2> /dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$7); print $7}'; }
ge05() { $P -c "import sys; sys.exit(0 if '$1' and float('$1') >= 0.05 else 1)" 2> /dev/null; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
VARS="nov2 nofork noboth"
cp results/r20/sp-batch/sp-cases.json results/r20/sp-batch/sp-llama.json $SPO/

# ---- 0 the gap
work/r22/port_gap4.sh begin "gap 14: the per-switch check of the hand-ported port (KL + distribution check 2 without PREFILL_V2 / GR_FORK / both)" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
grep -q '+ 27 commits' engine-r22p027/SOURCE && grep -q '+ 31 commits' engine-r22p027m/SOURCE || { say "gap 13's binaries are not in place - stopped"; end_gap; exit 1; }

# ---- 1 KL per variant
say "1 KL: pf_yardstick long40 on r27h-nov2 / -nofork / -noboth vs gap 8's references"
for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
[ -e $Y/r27h ] || ln -s $Y13/r27h $Y/r27h
for v in $VARS; do
  $P bringup/lib/guard.py pfy14-$v -- $P -I work/r22/pf_yardstick.py run $C/r27h-$v.json $Y/r27h-$v --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy r27h-$v: /" | tee -a $S
  kc pfy-$v
done
$P work/r22/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands r27h,r27h-nov2,r27h-nofork,r27h-noboth 2>&1 | tee $O/kl.txt | tee -a $S

# ---- 2 check (2) on each variant's speculation-off arm
say "2 check (2): each variant's speculation-off twin arm, arith-j3 T 0.6, 4,000, vs its own probabilities"
for v in $VARS; do
  L=g14-hnospec-$v; rm -f $SPO/sp-strata-$L.jsonl
  bringup/lib/with_server.sh g14-sp-n$v $C/r27t-hnospec-$v.json -- "SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-hnospec-$v.txt 2>&1; SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-hnospec-$v.txt 2>&1" 2>&1 \
    | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
  starts hnospec-$v $C/r27t-hnospec-$v.json
  kc sp-n$v
  SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-hnospec-$v.txt 2>&1
  say "  check (2) speculation off, $v: p $(pval $SPO/analyze-own-hnospec-$v.txt) | $(grep arith-j3 $SPO/analyze-own-hnospec-$v.txt | head -1 | cut -c1-150)"
done

# ---- 3 the pick
PASS=""
for v in nov2 nofork; do
  if grep -E "^r27h-$v " $O/kl.txt | grep -q -- '-> PASS' && ge05 "$(pval $SPO/analyze-own-hnospec-$v.txt)"; then PASS="$PASS $v"; fi
done
if [ -z "$PASS" ] && grep -E "^r27h-noboth " $O/kl.txt | grep -q -- '-> PASS' && ge05 "$(pval $SPO/analyze-own-hnospec-noboth.txt)"; then PASS="noboth"; fi
say "3 variants passing KL + check (2) (speculation off):${PASS:- none}"

# ---- 4 checks (1) + (2) on the speculative path of each passing variant
for v in $PASS; do
  L=g14-ess-$v; rm -f $SPO/sp-strata-$L.jsonl
  bringup/lib/with_server.sh g14-sp-e$v $C/r27t-ess-$v.json -- "SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-ess-$v.txt 2>&1" 2>&1 \
    | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
  starts ess-$v $C/r27t-ess-$v.json
  kc sp-e$v
  cp $SPO/sp-strata-logp-g14-hnospec-$v.json $SPO/sp-strata-logp-$L.json 2>/dev/null
  SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-ess-$v.txt 2>&1
  say "  check (2) speculative path, $v: p $(pval $SPO/analyze-own-ess-$v.txt)"
  $P -I work/r22/neartie_compare.py $SPO g14-hnospec-$v $L 2>&1 | tee $SPO/compare-$v.txt | tail -1 | sed "s/^/  check (1), $v: /" | tee -a $S
done

# ---- 5 speed: the prompt-speed cost of each passing drop
if [ -n "$PASS" ]; then
  say "5 speed: r27h (H) vs${PASS}, 2 passes in turned order"
  R=$O/speed; mkdir -p $R
  darm() {   # darm ARM CONFIG PASS
    local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
    say "arm $n pass $k ($(basename $cfg))"
    bringup/lib/with_server.sh g14-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${n}${k}r=research4:1" 2>&1 \
      | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
    kc g14-$n$k
  }
  arms="H"; for v in $PASS; do arms="$arms $v"; done
  rev=$(echo $arms | tr ' ' '\n' | tac | tr '\n' ' ')
  for k in 1 2; do
    if [ $k = 1 ]; then order=$arms; else order=$rev; fi
    for n in $order; do
      case $n in H) cfg=$C/r27h.json;; *) cfg=$C/r27h-$n.json;; esac
      darm $n $cfg $k
    done
  done
  labs=""; for kind in n a r; do for n in $arms; do labs="$labs ${n}1$kind ${n}2$kind"; done; done
  $P $BA/scripts/abreport.py --dir $R $labs > $O/speed-table.md 2>&1
  tail -30 $O/speed-table.md | tee -a $S > /dev/null
fi

end_gap
bringup/lib/kcheck.sh r22g14-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 14 done after $(( ($(date +%s) - T0) / 60 )) min - Karl's rule: a variant switches only with KL PASS and every p >= 0.05 on both checks"
