#!/bin/bash
# gap13.sh - round 22 gap 13 (10-29): the hand-ported v0.2.7 port's gates (Karl 10-28: "hand-port ours (exact sampling,
# the draft-length rule, the cost gate, GR_FORK, PREFILL_V2). Rerun both distribution checks on the hand-ported
# speculative path (vs speculation off, and each arm vs the reference probabilities). Both must pass cleanly before the
# switch."). Nothing switches here; 8080 gets P021m back at the end (port_gap4.sh end).
# The build: branch r22-port027 (worktree strata-r22p027) = v0.2.7 + 27 commits (results/r22/port-027.md "Hand-port
# done"); the twin r22-port027-meas = + the 4 MEASUREMENT commits. Configs: r27h (the port in P021m's test form: r27a's
# pins of 0.2.7's new defaults + SPEC_EXACT, COST_GATE, DRAFT_CUM, GR_FORK, PREFILL_V2), r27t-hnospec / r27t-ess (the
# twin with the served switches, speculation off / the hand-ported speculative path).
#   1 build          build-port027.sh (engine-r22p027; gap 12's binaries kept as engine-r22p027*-g12)
#   1b twin build    build-port027.sh twin (tests ON: upstream's sampler tests + ours)
#   2 server tests   strata-r22p027/serve, every unit test (gap 12: the one failure is upstream's own)
#   2b sampler tests upstream's spec_prob_test, gated_proposal_test, spec_verify_parity, spec_proposal_parity
#   2c our tests     patch_guard_test, cost_gate_test, draft_cum_test (CPU), prefill_fused_iq_test --v2 --no-timing (GPU)
#   3 repeat gate    exact7 twice on r27h, pin 2500 (must repeat 7/7 MATCHED)
#   4 lossless       patchtest.sh lossless on r27h
#   5 KL check       pf_yardstick long40 on r27h vs gap 8's references (kernel_rule2, the yardstick rule)
#   6 speed screen   P021m's test form (M, r21n-candpm) vs r27h (H), 2 passes in turned order (abarm.sh)
#   7 distribution   arith-j3 at T 0.6: twin speculation off (4,000) vs the hand-ported speculative path (4,000), the '='
#                    frequency (neartie_compare.py), and EACH arm vs the build's own probabilities (sampling_probe.py
#                    analyze own). Karl: clean = every p >= 0.05, no multiple-test correction to lean on.
# Start lines checked for every arm (exact sampling on, the patch guards, PREFILL_V2's line). A kernel error stops
# everything with the gap left open (exit 3). Output: results/r22/gap13/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab; O=$WS/results/r22/gap13; S=$O/summary.txt; C=$WS/configs
Y8=$WS/results/r22/gap8/pfy; Y=$O/pfy; mkdir -p $O $Y logs/r22 tmp/r22
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g13-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
e7() { grep -a -E "^exact7 $1: " $S | tail -1 | grep -oE '[0-9]+/7' | cut -d/ -f1; }
starts() {   # starts NAME CONFIG - the start lines that show the switches are on
  local L; L=$(elog $2)
  say "  start lines $1: exact $(grep -c 'EXACT speculative sampling on' $L 2>/dev/null), v2 $(grep -c 'STRATA_PREFILL_V2' $L 2>/dev/null), guards off $(grep -c -i 'patch guard.*off\|turned off' $L 2>/dev/null), old-rule $(grep -c 'keeps the older acceptance rule' $L 2>/dev/null)"
}
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
H=$C/r27h.json; M=$C/r21n-candpm.json; TN=$C/r27t-hnospec.json; TE=$C/r27t-ess.json

# ---- 0 the gap
work/r22/port_gap4.sh begin "gap 13: the hand-ported v0.2.7 port's gates (build, tests, repeat, lossless, KL, speed, distribution)" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
nvidia-smi --query-gpu=index,name,memory.used,memory.free,temperature.gpu --format=csv,noheader | tee -a $S
for e in engine-r22p027 engine-r22p027m; do [ -d $e ] && [ ! -d $e-g12 ] && cp -a $e $e-g12; done

# ---- 1 build
say "1 build: work/r22/build-port027.sh"
if ! work/r22/build-port027.sh 2>&1 | tail -4 | tee -a $S || [ ! -x engine-r22p027/strata ] || ! grep -q '+ 27 commits' engine-r22p027/SOURCE; then
  say "BUILD FAILED (strata-r22p027/build.log) - the gap ends, P021m back"; end_gap; exit 1
fi
kc build
say "1b twin build: work/r22/build-port027.sh twin (tests ON)"
TWIN_OK=1
if ! work/r22/build-port027.sh twin 2>&1 | tail -2 | tee -a $S || [ ! -x engine-r22p027m/strata ] || ! grep -q '+ 31 commits' engine-r22p027m/SOURCE; then
  say "TWIN BUILD FAILED (strata-r22p027m/build-twin.log) - 2b, 2c and 7 skipped"; TWIN_OK=0
fi
kc twin

# ---- 2 tests
say "2 server tests (strata-r22p027/serve)"
timeout 1800 $P -m unittest discover -s strata-r22p027/serve -t strata-r22p027 -p 'test_*.py' > $O/servetests.txt 2>&1
tail -3 $O/servetests.txt | tee -a $S
if [ $TWIN_OK = 1 ]; then
  say "2b upstream's sampler tests, 2c ours (strata-r22p027m/build-twin)"
  for t in spec_prob_test gated_proposal_test spec_verify_parity spec_proposal_parity patch_guard_test cost_gate_test draft_cum_test; do
    STRATA_OLD_SAMPLER=0 STRATA_SAMPLER_ONE_BLOCK=0 timeout 900 $P bringup/lib/guard.py g13-$t -- strata-r22p027m/build-twin/$t > $O/$t.txt 2>&1
    say "  $t rc $?: $(grep -v '^\s*$' $O/$t.txt | tail -1 | cut -c1-160)"
  done
  timeout 1800 $P bringup/lib/guard.py g13-v2test -- strata-r22p027m/build-twin/prefill_fused_iq_test --v2 --no-timing > $O/prefill_fused_v2_test.txt 2>&1
  say "  prefill_fused_iq_test --v2 rc $? (77 = skipped): $(grep -v '^\s*$' $O/prefill_fused_v2_test.txt | tail -1 | cut -c1-160)"
  kc tests
fi

# ---- 3 the repeat-run gate
say "3 repeat-run gate: exact7 twice on r27h, pin 2500"
PIN_CACHE=2500 bringup/lib/exact7.sh r27h-e7a $H 2>&1 | tail -9 | tee -a $S; kc e7a
starts r27h $H
PIN_CACHE=2500 REF=r27h-e7a bringup/lib/exact7.sh r27h-e7b $H 2>&1 | tail -9 | tee -a $S; kc e7b
say "repeat gate: r27h repeats $(e7 r27h-e7b)/7 (want 7/7 MATCHED)"

# ---- 4 lossless
say "4 lossless: patchtest.sh lossless on r27h"
CFG=$H TREE=strata-r22p027 bringup/patchtest.sh lossless 2>&1 | grep -E "PASS|FAIL" | tail -6 | tee -a $S

# ---- 5 KL check
say "5 KL check: pf_yardstick long40 on r27h vs gap 8's references"
for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
$P bringup/lib/guard.py pfy13-r27h -- $P -I work/r22/pf_yardstick.py run $H $Y/r27h --set long40 2>&1 | grep -v "^engine:" | tail -4 | sed "s/^/pfy r27h: /" | tee -a $S
kc pfy
$P work/r22/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands r27h 2>&1 | tee $O/kl.txt | tee -a $S

# ---- 6 speed screen
say "6 speed screen: P021m test form (M) vs r27h (H), 2 passes"
R=$O/speed; mkdir -p $R
darm() {   # darm ARM CONFIG PASS
  local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
  say "arm $n pass $k ($(basename $cfg))"
  bringup/lib/with_server.sh g13-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${n}${k}r=research4:1" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc g13-$n$k
}
for k in 1 2; do
  if [ $k = 1 ]; then order="M H"; else order="H M"; fi
  for n in $order; do
    case $n in M) cfg=$M;; H) cfg=$H;; esac
    darm $n $cfg $k
  done
done
$P $BA/scripts/abreport.py --dir $R M1n M2n H1n H2n M1a M2a H1a H2a M1r M2r H1r H2r > $O/speed-table.md 2>&1
tail -30 $O/speed-table.md | tee -a $S > /dev/null

# ---- 7 the distribution checks (Karl 10-28: both must pass cleanly before the switch)
if [ $TWIN_OK = 1 ]; then
  say "7 distribution checks: arith-j3 T 0.6, twin speculation off 4,000 vs the hand-ported speculative path 4,000"
  SPO=$O/sp; mkdir -p $SPO; cp results/r20/sp-batch/sp-cases.json results/r20/sp-batch/sp-llama.json $SPO/
  for a in hnospec ess; do
    L=g13-$a; rm -f $SPO/sp-strata-$L.jsonl
    case $a in hnospec) cfg=$TN;; ess) cfg=$TE;; esac
    LOGP=""; [ $a = hnospec ] && LOGP="; SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-$a.txt 2>&1"
    bringup/lib/with_server.sh g13-sp-$a $cfg -- "SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-$a.txt 2>&1$LOGP" 2>&1 \
      | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
    starts $a $cfg
    kc g13-sp-$a
  done
  cp $SPO/sp-strata-logp-g13-hnospec.json $SPO/sp-strata-logp-g13-ess.json 2>/dev/null
  for a in hnospec ess; do
    SP_DIR=$SPO SP_LABEL=g13-$a STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a.txt 2>&1
    say "  vs own probabilities, $a: $(grep arith-j3 $SPO/analyze-own-$a.txt | head -1 | cut -c1-170)"
  done
  $P -I work/r22/neartie_compare.py $SPO g13-hnospec g13-ess 2>&1 | tee $SPO/compare.txt | tee -a $S
  say "Karl's rule: clean = every p >= 0.05 (check (1) compare.txt, check (2) both analyze-own lines) - no switch otherwise"
fi

end_gap
bringup/lib/kcheck.sh r22g13-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 13 done after $(( ($(date +%s) - T0) / 60 )) min"
