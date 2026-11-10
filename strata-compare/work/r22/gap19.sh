#!/bin/bash
# gap19.sh run - round 22 gap 19 (Karl 11-04): a DIAGNOSTIC on STOCK Strata v0.2.10 (engine-v0210stock c8fe72abe45a,
# built in gap 17 from the detached worktree strata-v0210stock at v0.2.10 ffa80d731; nothing is built here). WRITTEN
# 11-04, NOT RUN. Measurements only: P028x stays served, nothing switches. Why: gap 17 failed two v0.2.10 paths on our
# port - the GDN prompt stack (STRATA_GDN_TC + STRATA_GDN_CONVL2: KL far beyond rounding) and STRATA_PF_HC_REGION=1
# (exact7 3/7; upstream says the same bits). Karl: stock on the same checks - the same failure = upstream's, stock fine =
# our port's (then record which patches interact: results/r22/gap19/PATCH-OVERLAP.md).
#   1 pf_yardstick long40 on s0210-h (both GDN paths off) and s0210-h-gdn (TC=1 + CONVL2=2, as stock's server.py sets them)
#   2 gap 17's KL rules (kernel_rule2 + kernel_rule3 with the NLL check, gap 8's references); the port's gap 17 dirs are
#     scored in the same call (one set of bounds)
#   3 exact7 at pin 2500: stock off (g19-s210, against gap 17's g17-s210 = the cross-gap repeat), then stock HC on
#     (g19-s210hcr) against it, slots MATCHED. G19_HCR_SHARE0=1 adds the HC pair with STRATA_PREFILL_CPU_SHARE=0 (3b)
#   4 optional, each only if it fits before the deadline (G19_MAX_MIN, default 45 min after the gap opens): GDN_TC alone,
#     GDN_CONVL2 alone (pf_yardstick + KL), then pf_yardstick on s0210-h-hcr (bitwise against off)
#   5 work/r22/g19_rules.py decide (written before the gap) -> results/r22/gap19/decision.txt; port_gap4.sh end
# Every engine's environment is checked as it starts (g19_rules.py envcli: /proc/PID/exe under the step's own process
# tree, never a command-line pattern; a mismatching engine is stopped by its PID, the arm is void). Children run with
# 8>&- 9>&-. A kernel-check failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides).
# Steps and times: work/r22/GAP19-README.md.
set -u -o pipefail
case ${1:-} in run) ;; *) sed -n 2,19p "$0"; exit 2;; esac
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=$WS/.venv/bin/python; C=$WS/configs; KR=$WS/work/r22; RU=$KR/g19_rules.py
O=$WS/results/r22/gap19; S=$O/summary.txt; G=$O/gates.txt; Y=$O/pfy
Y8=$WS/results/r22/gap8/pfy; Y17=$WS/results/r22/gap17/pfy; PROF=$WS/bringup/out/logs/prof
EST=$WS/engine-v0210stock; WST=$WS/strata-v0210stock; STOCK_SHA=c8fe72abe45a   # gap 17's build_stock
H0=$C/s0210-h.json; HG=$C/s0210-h-gdn.json; HT=$C/s0210-h-gdntc.json; HV=$C/s0210-h-gdncv.json; HR=$C/s0210-h-hcr.json
PFY_MIN=9; E7_MIN=4   # what a step takes, with its kernel check (gap 17: pf_yardstick 8.5 min, exact7 3.3 min)
MAXM=${G19_MAX_MIN:-45}
mkdir -p $O $Y $WS/logs/r22 $WS/tmp/r22
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [19 $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
KFAIL=0
kc() { $WS/bringup/lib/kcheck.sh "r22g19-$1" > /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { [ $KFAIL = 0 ] && [ $(left) -ge $(( $1 * 60 )) ]; }   # an optional step starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }

pfy() {   # pfy NAME CONFIG [MIN]: pf_yardstick long40 (gap 17's form) on the stock engine, its environment checked as it
  # starts; MIN given = an optional step (it starts only if MIN minutes fit before the deadline)
  local n=$1 cfg=$2 jp
  if [ -n "${3:-}" ]; then fits $3 || { say "skipped pf_yardstick $n (optional: $3 min do not fit before the deadline, or a kernel check failed)"; return 1; }
  else ok_to_go || { say "skipped pf_yardstick $n (deadline or kernel check)"; return 1; }; fi
  say "pf_yardstick long40 $n ($(basename $cfg))"
  ( $P $WS/bringup/lib/guard.py pfy19-$n -- $P -I $KR/pf_yardstick.py run $cfg $Y/$n --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy $n: /" | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $EST/strata $cfg --job $jp --mode pfy --kill --gate env_pfy-$n --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  kc pfy-$n
}
e7() {   # e7 LABEL CONFIG REF [ENVX]: exact7 at pin 2500 (bringup/lib/exact7.sh: 7 items, --adapt-swaps 0 --suffix-draft 0)
  # against REF's hashes and slots; every item's engine environment checked as it starts (ENVX: K=V over the config's)
  local L=$1 cfg=$2 ref=$3 ex=${4:-} jp sets="" kv
  ok_to_go || { say "skipped exact7 $L (deadline or kernel check)"; return 1; }
  for kv in $ex; do sets="$sets --set $kv"; done
  say "exact7 $L ($(basename $cfg) against $ref${ex:+; $ex})"
  ( PIN_CACHE=2500 REF=$ref ENVX="$ex" $WS/bringup/lib/exact7.sh $L $cfg 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $EST/strata $cfg --job $jp --mode e7 --kill $sets --gate env_e7-$L --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  kc e7-$L
}
klrules() {   # gap 17's two KL rules on the long40 dirs against gap 8's references (ref; rounding references unfused,
  # cpushare): the stock arms of this gap and the port's gap 17 dirs in ONE call -> kl2_* / kl3_* gates of the stock arms
  local c cands=""
  for c in s210 s210gdn s210gdntc s210gdncv p210 p210gdn p210gdntc p210gdncv; do [ -f $Y/$c/index.json ] && cands="$cands,$c"; done
  case $cands in *s210*) ;; *) say "KL rules: no stock arm finished - nothing to score"; return 0;; esac
  $P -B $KR/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands ${cands#,} > $O/kl2.txt 2>&1
  $P -I -B $KR/kernel_rule3.py $Y --ref ref --refs unfused,cpushare --cands ${cands#,} > $O/kl3.txt 2>&1
  cat $O/kl2.txt $O/kl3.txt | tee -a $S
  $P -I -B $RU klgates $O 2>&1 | tee -a $S
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I -B $RU decide $O > /dev/null 2>&1 || say "g19_rules.py decide failed - rerun it by hand ($RU decide $O)"
  [ -f $O/decision.txt ] && tee -a $S < $O/decision.txt
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "gap 19 done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "GAP 19 (work/r22/gap19.sh): stock v0.2.10 - the GDN prompt paths and PF_HC_REGION on vs off (a diagnostic; P028x stays served, nothing switches - Karl 11-04)"
if [ -s $WS/tmp/port-gap.lockpid ] && kill -0 "$(cat $WS/tmp/port-gap.lockpid)" 2> /dev/null; then
  say "another gap holds the test lock (tmp/port-gap.lockpid $(cat $WS/tmp/port-gap.lockpid)) - not started"; exit 1
fi
if [ -e $G ] || [ -e $O/decision.txt ] || ls -d $Y/s210* > /dev/null 2>&1; then   # the rules judge only this attempt's files
  PREV=$O/prev-$(date +%m%d-%H%M%S); mkdir -p $PREV
  for f in $G $O/decision.txt $O/kl2.txt $O/kl3.txt $O/t0.txt; do [ -e $f ] && mv $f $PREV/; done
  for d in $Y/s210*; do [ -d $d ] && mv $d $PREV/; done
  say "an earlier attempt's outputs moved to $PREV"
fi
for f in $H0 $HG $HT $HV $HR $C/P0210x-h.json $C/P0210x-h-gdn.json $C/P0210x-h-gdntc.json $C/P0210x-h-gdncv.json $C/P0210x-h-hcr.json \
         $RU $KR/pf_yardstick.py $KR/kernel_rule2.py $KR/kernel_rule3.py $WS/bringup/lib/exact7.sh $KR/port_gap4.sh \
         $WS/results/r22/gap17/gates.txt; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
$P -I -B $RU cfgcheck --gate cfg --gates $G 2>&1 | tee -a $S
[ "$(grep '^cfg ' $G | tail -1 | cut -d' ' -f2)" = PASS ] || { say "the stock arms are not the port arms' differences - not started"; exit 1; }
V0210=$(git -C $WS/strata rev-parse 'v0.2.10^{commit}')
if [ -x $EST/strata ] && [ "$(sha12 $EST/strata)" = $STOCK_SHA ] && [ "$(cut -c1-12 $EST/SHA256)" = $STOCK_SHA ] \
   && grep -q "^stock v0.2.10 ($V0210, " $EST/SOURCE && [ "$(git -C $WST rev-parse HEAD)" = "$V0210" ] \
   && [ -z "$(git -C $WST status --porcelain --untracked-files=no)" ]; then
  gate build_stock PASS "engine-v0210stock $STOCK_SHA = $(cut -c1-100 $EST/SOURCE)"
else
  say "engine-v0210stock is not gap 17's stock build ($STOCK_SHA, strata-v0210stock at v0.2.10, clean) - not started (gap 19 builds nothing)"; exit 1
fi
for x in ref unfused cpushare; do ln -sfn $Y8/$x $Y/$x; done                          # gap 8's references (as gap 17)
for x in p210 p210gdn p210gdntc p210gdncv p210hcr; do ln -sfn $Y17/$x $Y/$x; done     # the port's arms (gap 17)
for x in ref unfused cpushare p210 p210gdn p210gdntc p210gdncv p210hcr; do
  [ -f $Y/$x/index.json ] || { say "missing $Y/$x/index.json (gap 8's references / gap 17's port arms) - not started"; exit 1; }
done
for l in g17-p210a g17-hcr; do
  [ "$(ls $PROF/$l-*.out 2> /dev/null | wc -l)" = 7 ] || say "note: gap 17's exact7 $l is incomplete - the port's mechanism table will say so"
done
E7REF=g17-s210; [ "$(ls $PROF/g17-s210-*.out 2> /dev/null | wc -l)" = 7 ] || E7REF=c13
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }

# ================================================================ the gap
$KR/port_gap4.sh begin "gap 19: stock v0.2.10 diagnostic - GDN paths and PF_HC_REGION on vs off (measurements only; P028x stays served, nothing switches - Karl 11-04)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
kc open || end_gap

# ---- 1 pf_yardstick long40: stock with both GDN paths off, then on
say "1 pf_yardstick long40: s0210-h (both GDN paths off) and s0210-h-gdn (TC=1 + CONVL2=2, as stock's server.py sets them)"
pfy s210 $H0
pfy s210gdn $HG

# ---- 2 the KL rules (stock off must pass, as the port's off arm did; stock on: the same failure as the port's?)
say "2 gap 17's KL rules on the stock arms, the port's gap 17 arms beside them"
klrules

# ---- 3 exact7 at pin 2500: stock off, then the HC region on against it
say "3 exact7 at pin 2500: stock off (against gap 17's $E7REF: the cross-gap repeat), then STRATA_PF_HC_REGION=1 against it"
e7 g19-s210 $H0 $E7REF
e7 g19-s210hcr $HR g19-s210
if [ "${G19_HCR_SHARE0:-0}" = 1 ]; then
  if fits $(( 2 * E7_MIN )); then
    say "3b (G19_HCR_SHARE0=1) the HC pair with STRATA_PREFILL_CPU_SHARE=0 - is the change the prompt CPU share's placement? (g19-s210z's line against g19-s210 is not judged: the share itself changes bits)"
    e7 g19-s210z $H0 g19-s210 STRATA_PREFILL_CPU_SHARE=0
    e7 g19-s210hcrz $HR g19-s210z STRATA_PREFILL_CPU_SHARE=0
  else say "skipped 3b (G19_HCR_SHARE0): $(( 2 * E7_MIN )) min do not fit before the deadline"; fi
fi

# ---- 4 optional: each GDN path alone, then the HC region on the yardstick - each only if it ends before the deadline
say "4 optional steps ($(( $(left) / 60 )) min to the deadline): GDN_TC alone, GDN_CONVL2 alone, PF_HC_REGION on the yardstick"
pfy s210gdntc $HT $PFY_MIN
pfy s210gdncv $HV $PFY_MIN
if [ -f $Y/s210gdntc/index.json ] || [ -f $Y/s210gdncv/index.json ]; then klrules; fi
pfy s210hcr $HR $PFY_MIN

# ---- 5 the rules, P028x back
end_gap
