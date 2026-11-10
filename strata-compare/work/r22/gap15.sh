#!/bin/bash
# gap15.sh - round 22 gap 15 (10-30): the v0.2.8 port's gates (Karl 10-29: v0.2.8 is the target; gap 14: PREFILL_V2 fails
# the KL rule and GR_FORK fails distribution check (2), only the form without both passes everything - "port the rest
# without it and report the prompt-speed cost"). Branch r22-port028 (worktree strata-r22p028) = v0.2.8 + 27 commits (the
# two switches' code stays in, OFF); twin r22-port028-meas (31). Configs: r28h (the port in P021m's test form without
# PREFILL_V2 / GR_FORK, tool_call_recovery false = the planned served form), r28h-rec (recovery at 0.2.8's default, on),
# r28t-hnospec / r28t-ess (the twin's arms). Steps as gap 13 (build, twin, server / sampler / our tests, exact7 x2, lossless,
# KL, speed vs P021m, both distribution checks) + 8 the tool_call_recovery live test (on vs off, work/r22/toolrecovery).
# Karl's switch rule: KL PASS and every p >= 0.05 on both distribution checks; the served config keeps
# "tool_call_recovery": false unless step 8 shows real calls lost without it AND no false calls with it.
# Nothing switches here; 8080 gets P021m back at the end. Output: results/r22/gap15/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab; O=$WS/results/r22/gap15; S=$O/summary.txt; C=$WS/configs
Y8=$WS/results/r22/gap8/pfy; Y=$O/pfy; mkdir -p $O $Y logs/r22 tmp/r22
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g15-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
e7() { grep -a -E "^exact7 $1: " $S | tail -1 | grep -oE '[0-9]+/7' | cut -d/ -f1; }
starts() {   # starts NAME CONFIG - the start lines that show the switches are on
  local L; L=$(elog $2)
  say "  start lines $1: exact $(grep -c 'EXACT speculative sampling on' $L 2>/dev/null), v2 $(grep -c 'STRATA_PREFILL_V2' $L 2>/dev/null), guards off $(grep -c -i 'patch guard.*off\|turned off' $L 2>/dev/null), old-rule $(grep -c 'keeps the older acceptance rule' $L 2>/dev/null)"
}
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
H=$C/r28h.json; HR=$C/r28h-rec.json; M=$C/r21n-candpm.json; TN=$C/r28t-hnospec.json; TE=$C/r28t-ess.json

# ---- 0 the gap
work/r22/port_gap4.sh begin "gap 15: the v0.2.8 port's gates (build, tests, repeat, lossless, KL, speed, distribution, tool-call recovery)" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
nvidia-smi --query-gpu=index,name,memory.used,memory.free,temperature.gpu --format=csv,noheader | tee -a $S
for e in engine-r22p028 engine-r22p028m; do [ -d $e ] && [ ! -d $e-g12 ] && cp -a $e $e-g12; done

# ---- 1 build
say "1 build: work/r22/build-port028.sh"
if ! work/r22/build-port028.sh 2>&1 | tail -4 | tee -a $S || [ ! -x engine-r22p028/strata ] || ! grep -q 'v0.2.8 + 27 commits' engine-r22p028/SOURCE; then
  say "BUILD FAILED (strata-r22p028/build.log) - the gap ends, P021m back"; end_gap; exit 1
fi
kc build
say "1b twin build: work/r22/build-port028.sh twin (tests ON)"
TWIN_OK=1
if ! work/r22/build-port028.sh twin 2>&1 | tail -2 | tee -a $S || [ ! -x engine-r22p028m/strata ] || ! grep -q 'v0.2.8 + 31 commits' engine-r22p028m/SOURCE; then
  say "TWIN BUILD FAILED (strata-r22p028m/build-twin.log) - 2b, 2c and 7 skipped"; TWIN_OK=0
fi
kc twin

# ---- 2 tests
say "2 server tests (strata-r22p028/serve)"
timeout 1800 $P -m unittest discover -s strata-r22p028/serve -t strata-r22p028 -p 'test_*.py' > $O/servetests.txt 2>&1
tail -3 $O/servetests.txt | tee -a $S
if [ $TWIN_OK = 1 ]; then
  say "2b upstream's sampler tests, 2c ours (strata-r22p028m/build-twin)"
  for t in spec_prob_test gated_proposal_test spec_verify_parity spec_proposal_parity patch_guard_test cost_gate_test draft_cum_test; do
    a=""; [ $t = patch_guard_test ] && a="$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf $WS/strata-v0115/mtp/rt"
    STRATA_OLD_SAMPLER=0 STRATA_SAMPLER_ONE_BLOCK=0 timeout 900 $P bringup/lib/guard.py g15-$t -- strata-r22p028m/build-twin/$t $a > $O/$t.txt 2>&1
    say "  $t rc $?: $(grep -v '^\s*$' $O/$t.txt | tail -1 | cut -c1-160)"
  done
  timeout 1800 $P bringup/lib/guard.py g15-v2test -- strata-r22p028m/build-twin/prefill_fused_iq_test --v2 --no-timing > $O/prefill_fused_v2_test.txt 2>&1
  say "  prefill_fused_iq_test --v2 rc $? (77 = skipped): $(grep -v '^\s*$' $O/prefill_fused_v2_test.txt | tail -1 | cut -c1-160)"
  kc tests
fi

# ---- 3 the repeat-run gate
say "3 repeat-run gate: exact7 twice on r28h, pin 2500"
PIN_CACHE=2500 bringup/lib/exact7.sh r28h-e7a $H 2>&1 | tail -9 | tee -a $S; kc e7a
PIN_CACHE=2500 REF=r28h-e7a bringup/lib/exact7.sh r28h-e7b $H 2>&1 | tail -9 | tee -a $S; kc e7b
say "repeat gate: r28h repeats $(e7 r28h-e7b)/7 (want 7/7 MATCHED)"

# ---- 4 lossless
say "4 lossless: patchtest.sh lossless on r28h"
CFG=$H TREE=strata-r22p028 bringup/patchtest.sh lossless 2>&1 | grep -E "PASS|FAIL" | tail -6 | tee -a $S

# ---- 5 KL check
say "5 KL check: pf_yardstick long40 on r28h vs gap 8's references"
for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
$P bringup/lib/guard.py pfy15-r28h -- $P -I work/r22/pf_yardstick.py run $H $Y/r28h --set long40 2>&1 | grep -v "^engine:" | tail -4 | sed "s/^/pfy r28h: /" | tee -a $S
kc pfy
$P work/r22/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands r28h 2>&1 | tee $O/kl.txt | tee -a $S

# ---- 6 speed screen
say "6 speed screen: P021m test form (M) vs r28h (H), 2 passes"
R=$O/speed; mkdir -p $R
darm() {   # darm ARM CONFIG PASS
  local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
  say "arm $n pass $k ($(basename $cfg))"
  bringup/lib/with_server.sh g15-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${n}${k}r=research4:1" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc g15-$n$k
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
    L=g15-$a; rm -f $SPO/sp-strata-$L.jsonl
    case $a in hnospec) cfg=$TN;; ess) cfg=$TE;; esac
    LOGP=""; [ $a = hnospec ] && LOGP="; SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p028m $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-$a.txt 2>&1"
    bringup/lib/with_server.sh g15-sp-$a $cfg -- "SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p028m $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-$a.txt 2>&1$LOGP" 2>&1 \
      | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
    starts $a $cfg
    kc g15-sp-$a
  done
  cp $SPO/sp-strata-logp-g15-hnospec.json $SPO/sp-strata-logp-g15-ess.json 2>/dev/null
  for a in hnospec ess; do
    SP_DIR=$SPO SP_LABEL=g15-$a STRATA_SERVE_TREE=$WS/strata-r22p028m $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a.txt 2>&1
    say "  vs own probabilities, $a: $(grep arith-j3 $SPO/analyze-own-$a.txt | head -1 | cut -c1-170)"
  done
  $P -I work/r22/neartie_compare.py $SPO g15-hnospec g15-ess 2>&1 | tee $SPO/compare.txt | tee -a $S
  say "Karl's rule: clean = every p >= 0.05 (check (1) compare.txt, check (2) both analyze-own lines) - no switch otherwise"
fi

# ---- 8 tool_call_recovery live test (Karl 10-29): recovery on (r28h-rec) vs off, the same seeds
T=$WS/work/r22/toolrecovery; mkdir -p $O/toolrecovery
say "8 tool_call_recovery live test: on (r28h-rec) vs off, 27 prompts x 2"
bringup/lib/with_server.sh g15-tr-on $HR -- "$WS/.venv/bin/python -B $T/toolrecovery_live.py http://127.0.0.1:8081 --label on --reps 2" 2>&1 | tail -4 | tee -a $S
kc tr-on
OFFCFG=$($WS/.venv/bin/python -B $T/toolrecovery_live.py offconfig $HR)
bringup/lib/with_server.sh g15-tr-off "$OFFCFG" -- "$WS/.venv/bin/python -B $T/toolrecovery_live.py http://127.0.0.1:8081 --label off --reps 2" 2>&1 | tail -4 | tee -a $S
kc tr-off
ON=$(ls -t $T/results/live-on-*.jsonl 2>/dev/null | head -1); OFF=$(ls -t $T/results/live-off-*.jsonl 2>/dev/null | head -1)
[ -n "$ON" ] && [ -n "$OFF" ] && $WS/.venv/bin/python -B $T/toolrecovery_live.py compare $ON $OFF 2>&1 | tee $O/toolrecovery/compare.txt | tail -25 | tee -a $S
say "Karl's rule: the served config keeps tool_call_recovery false unless 'on' recovers real calls 'off' loses AND makes no false call"

end_gap
bringup/lib/kcheck.sh r22g15-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 15 done after $(( ($(date +%s) - T0) / 60 )) min"
