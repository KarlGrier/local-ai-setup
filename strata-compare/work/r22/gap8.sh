#!/bin/bash
# gap8.sh [P4S2_START_PID] - round 22 gap 8 (planned 10-21 night, runs after phase 4 stage 2): the P021 backport and the
# switch. The user, 10-21: "if both checks pass in the next gap (the 40-prompt kernel check and the C vs A confirmation
# with the rebuilt tool-call turns), switch 8080 mid-Phase 4 to P021 plus the two lossless ports, not to the 0.2.2 build
# ... Run the same checks on the backport (exactness, needles, 120K, probes, a quick speed check), then switch ... keep
# P021 as the rollback." Gap 7 decisions: the switch = P021 + arm C + v2 prompt kernels + STRATA_DEQUANT_WIDE (identical
# output, rides along); int8 attention joins only if its quality check with int8 K/V passes; "no forced --pcie-frac 0"
# gets extra arms (P021 alone and P021 + C, >= 4 runs per prompt, W1-W3 + a research-shaped long-context call) and the
# user decides on it - it is NOT part of this switch.
# Waits for stage 2 (deep-research-bench.service on queue-plan-p4s2.json) to end, then port_gap4.sh begin, and:
#   1 build          work/r22/build-port021n.sh (r22-port021-next = P021 + 4518c9b3 + 632ae8b7 + 785e45df -> engine-r22p021n)
#                    + the C++ tests (cost_gate_test, draft_cum_test, prefill_fused_iq_test, patch_guard_test)
#   2 exactness      r21n (every switch off) vs P021's own exact7 (r21p-e7) - MUST be 7/7; again vs itself (7/7);
#                    STRATA_DRAFT_CUM at --spec 4 (7/7: today's windows); STRATA_DEQUANT_WIDE (7/7 = identical output,
#                    then it rides along; otherwise it stays off)
#   3 kernel check   the 40-prompt yardstick (pf_yardstick.py --set long40, the 5080 alone): ref, ref2, unfused, cpushare
#                    (the served STRATA_PREFILL_CPU_SHARE=0.4: the second rounding reference, the user 10-22), v2, v2d,
#                    v2g with FP16 K/V; refi8, unfusedi8, cpusharei8, immai8 with the served int8 K/V. Verdict:
#                    gap8_verdicts.py kernel (the user 10-22: within the two references' spread - KL mean <= 1.1x the
#                    larger reference mean, KL max <= 1.5x the worse reference max)
#   4 C vs A         both cards as served, T 1.0, thinking on; arms A (P021 today), C (spec 7 + STRATA_DRAFT_CUM), PA (A
#                    without the forced --pcie-frac 0), PC (C without it); each server: W1-W3, the rebuilt tool-call turns
#                    (prompts/agentturn.json: edit / write calls with code), the research-shaped call (o02 p4base verify
#                    call 1069, ~20K tokens, xhigh); passes A C PA PC / PC PA C A / A C PA PC / PC PA C A = 4 runs per
#                    prompt and arm. Verdict: gap8_verdicts.py cvsa (the user 10-22: >= +3 % on the W1-W3 mean, ahead in
#                    >= 3 of 4 passes, tool-call turns and the research call each no more than 3 % slower)
#   5 candidate      only when 2-4 pass: r21n-cand (C + the chosen v2 + WIDE if identical + IMMA if it passed): exact7
#                    twice (repeatable 7/7), needles 12 x 6, Stop at 120K, probes, the chat-cache checks (its pinned
#                    picture twin), a quick speed check (decode and prompt screens R K K R vs r21n). Gates: 7/7, 12/12,
#                    ALL PASS, chat cache ALL PASS, decode and 32K TTFT not >2 % slower than r21n.
#   6 switch         only when 5 passes: work/r22/switch021n.sh (configs/P021n.json the new default, port_gap4.sh's sha),
#                    then port_gap4.sh end starts it on 8080; otherwise port_gap4.sh end brings P021 back unchanged.
# A kernel error stops everything with the gap left open (exit 3). Output: results/r22/gap8/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; BA=/home/USER/ai-speed-testing/basalt-ab; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=$WS/results/r22/gap8; S=$O/summary.txt; C=$WS/configs; mkdir -p $O logs/r22 tmp/r22
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g8-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
NOSWITCH=""
noswitch() { NOSWITCH="${NOSWITCH:+$NOSWITCH; }$*"; say "NO SWITCH: $*"; }
e7() { grep -a -E "^exact7 $1: " $S | tail -1 | grep -oE '[0-9]+/7' | cut -d/ -f1; }

# ---- 0 stage 2, then the gap
W=${1:-}
[ -n "$W" ] && while kill -0 $W 2> /dev/null; do sleep 60; done
while systemctl --user is-active --quiet deep-research-bench.service; do sleep 120; done
say "stage 2 has ended: $(grep -a -E 'queue finished|queue stopped|FAILED' /home/USER/ai/deep-research/logs/bench2-queue.log | tail -2 | tr '\n' ' ')"
grep -a -q "KCHECK FAILED" /home/USER/ai/deep-research/logs/p4-stage1-reruns.log && { say "the reruns logged a kernel check failure - not opening the gap"; exit 3; }
grep -a -q "stage 2 NOT started" /home/USER/ai/deep-research/logs/p4-stage1-reruns.log && say "note: stage 2 did not start (the reruns did not end cleanly) - the gap runs anyway"
work/r22/port_gap4.sh begin "gap 8: the P021 backport (draft rule + v2 kernels), its checks, the switch if they pass" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
nvidia-smi --query-gpu=index,name,memory.used,memory.free,temperature.gpu --format=csv,noheader | tee -a $S

# ---- 1 build and the C++ tests
say "1 build: the P021 backport (engine-r22p021n)"
if ! work/r22/build-port021n.sh 2>&1 | tee -a $S; then
  tail -30 strata-r22p021n/build.log > $O/build-fail.txt 2> /dev/null; say "BACKPORT BUILD FAILED ($O/build-fail.txt) - ending the gap, P021 back"; end_gap; exit 1
fi
kc build
if work/r22/build-port021n.sh tests 2>&1 | tee -a $S; then
  (cd strata-r22p021n/build-tests && timeout 3600 ctest --output-on-failure --timeout 600 > $O/ctest.txt 2>&1); echo "ctest rc $?: $(grep -E 'tests passed|tests failed' $O/ctest.txt | tail -1)" | tee -a $S
  grep -E "\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run" $O/ctest.txt | sed 's/^ *[0-9]* - //' | sort | tr '\n' ';' | tee -a $S; echo | tee -a $S
  grep -E "Test +#[0-9]+: (cost_gate_test|draft_cum_test|prefill_fused_iq_test|patch_guard_test) " $O/ctest.txt | tee -a $S
  for t in cost_gate_test draft_cum_test prefill_fused_iq_test patch_guard_test; do
    grep -qE "Test +#[0-9]+: $t \.+ +Passed" $O/ctest.txt || noswitch "$t did not pass"
  done
else
  tail -30 strata-r22p021n/build-tests.log > $O/build-tests-fail.txt 2> /dev/null; noswitch "the test build failed ($O/build-tests-fail.txt)"
fi
kc tests

# ---- 2 exactness
say "2 exactness: every switch off must equal P021 (r21p-e7) bit for bit"
REF=r21p-e7 bringup/lib/exact7.sh r21n-e7 $C/r21n.json 2>&1 | tail -8 | tee -a $S; kc exact7
[ "$(e7 r21n-e7)" = 7 ] || noswitch "switches off: $(e7 r21n-e7)/7 identical to P021 (must be 7/7)"
REF=r21n-e7 bringup/lib/exact7.sh r21n2-e7 $C/r21n.json 2>&1 | tail -8 | tee -a $S; kc exact7-repeat
[ "$(e7 r21n2-e7)" = 7 ] || noswitch "repeat: $(e7 r21n2-e7)/7 (must be 7/7)"
REF=r21n-e7 bringup/lib/exact7.sh r21ncum-e7 $C/r21n-cum4.json 2>&1 | tail -8 | tee -a $S; kc exact7-cum4
[ "$(e7 r21ncum-e7)" = 7 ] || noswitch "STRATA_DRAFT_CUM at --spec 4: $(e7 r21ncum-e7)/7 (the commit keeps today's windows: must be 7/7)"
REF=r21n-e7 bringup/lib/exact7.sh r21nwide-e7 $C/r21n-wide.json 2>&1 | tail -8 | tee -a $S; kc exact7-wide
WIDE=0; [ "$(e7 r21nwide-e7)" = 7 ] && WIDE=1
say "STRATA_DEQUANT_WIDE: $(e7 r21nwide-e7)/7 identical -> $([ $WIDE = 1 ] && echo 'rides along' || echo 'NOT identical: stays off')"

# ---- 3 the 40-prompt kernel check
say "3 kernel check: the yardstick on 40 long prompts (2K-32K, 8 texts; the 5080 alone, experts on the CPU)"
Y=$O/pfy; mkdir -p $Y
yrun() {   # yrun LABEL CONFIG [args]
  local l=$1 cfg=$2; shift 2
  $P bringup/lib/guard.py pfy-$l -- $P -I work/r22/pf_yardstick.py run $cfg $Y/$l --set long40 "$@" 2>&1 | grep -v "^engine:" | tail -4 | sed "s/^/pfy $l: /" | tee -a $S
  kc pfy-$l
}
yrun ref $C/r21n1.json; yrun ref2 $C/r21n1.json; yrun unfused $C/r21n1-unfused.json; yrun cpushare $C/r21n1.json --env STRATA_PREFILL_CPU_SHARE=0.4
yrun v2 $C/r21n1-v2.json; yrun v2d $C/r21n1-v2d.json; yrun v2g $C/r21n1-v2g.json
yrun refi8 $C/r21n1.json --kv int8; yrun unfusedi8 $C/r21n1-unfused.json --kv int8; yrun cpusharei8 $C/r21n1.json --kv int8 --env STRATA_PREFILL_CPU_SHARE=0.4
yrun immai8 $C/r21n1-imma.json --kv int8
{ $P -I work/r22/pf_yardstick.py compare $Y/ref $Y/ref2 $Y/unfused $Y/cpushare $Y/v2 $Y/v2d $Y/v2g
  $P -I work/r22/pf_yardstick.py compare $Y/refi8 $Y/unfusedi8 $Y/cpusharei8 $Y/immai8; } 2>&1 | tee $O/pfy.md | tee -a $S
$P work/r22/gap8_verdicts.py kernel $O/pfy.md 2>&1 | tee $O/kernel-verdict.txt | tee -a $S
V2=$(grep -oE '^CHOSEN v2=[0-9a-z]+' $O/kernel-verdict.txt | cut -d= -f2)
IMMA=0; grep -q '^IMMA PASS' $O/kernel-verdict.txt && IMMA=1
[ "${V2:-none}" = none ] && noswitch "no v2 prompt-kernel variant is rounding-level on the 40 prompts"

# ---- 4 C vs A (+ the pcie arms)
say "4 C vs A and the pcie arms (both cards as served; T 1.0 / 0.95 / 20 / min-p 0.05, thinking on; 4 runs per prompt and arm)"
R=$O/cvsa; mkdir -p $R
darm() {   # darm ARM CONFIG PASS
  local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
  say "arm $n pass $k ($(basename $cfg))"
  bringup/lib/with_server.sh g8-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${n}${k}r=research:1" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc g8-$n$k
}
for k in 1 2 3 4; do
  if [ $((k % 2)) = 1 ]; then order="A C PA PC"; else order="PC PA C A"; fi
  for n in $order; do
    case $n in A) cfg=r21n;; C) cfg=r21n-C;; PA) cfg=r21n-pcie;; PC) cfg=r21n-Cpcie;; esac
    darm $n $C/$cfg.json $k
  done
done
$P work/r22/gap8_verdicts.py cvsa $R 2>&1 | tee $O/cvsa-verdict.txt | tee -a $S
for x in A C PA PC; do for t in n a r; do cat $R/$x[1-4]$t.jsonl > $R/$x$t.jsonl 2> /dev/null; cat $R/$x[1-4]$t.englog > $R/$x$t.englog 2> /dev/null; cp $R/${x}1$t.startlog $R/$x$t.startlog 2> /dev/null; done; done
for t in n a r; do $P $BA/scripts/abreport.py --dir $R A$t C$t PA$t PC$t > $R/table-$t.md 2>&1; cat $R/table-$t.md | tee -a $S; done
grep -q '^CVSA PASS' $O/cvsa-verdict.txt || noswitch "C vs A did not pass (see $O/cvsa-verdict.txt)"


# ---- 4b the matched-slot exactness check (the user, 10-22 10:3x: in this gap, after the measurements)
# Step 2's 2/7 came from the slot counts: exact7's old pin (--expert-cache 3500) is a byte budget above the free VRAM,
# so P021 (gap 3: 4551 slots) and the backport (4529: ~160 MiB less free) were both sized by the free VRAM - different
# experts on the GPU, different rounding. bringup/lib/exact7.sh now pins 2500 (under both) and prints the slot counts.
# P021 (r22p021.json, as in gap 3) and the backport with every new switch off (r21n.json) at the same pin: 7/7 with
# MATCHED slots = exactness passed. Otherwise: stop - P021 back, stage 3 not started, the user decides.
say "4b matched-slot exactness: P021 vs the backport (every new switch off), the same pinned slot count"
mexact() {   # mexact PIN -> EXM (identical of 7), SLM (MATCHED / DIFFER)
  PIN_CACHE=$1 REF=r21p-e7 bringup/lib/exact7.sh r21pm$1-e7 $C/r22p021.json 2>&1 | tail -10 | tee -a $S; kc exact7-p021-pin$1
  PIN_CACHE=$1 REF=r21pm$1-e7 bringup/lib/exact7.sh r21nm$1-e7 $C/r21n.json 2>&1 | tail -10 | tee -a $S; kc exact7-r21n-pin$1
  EXM=$(e7 r21nm$1-e7); SLM=$(grep -a -E "^exact7-slots r21nm$1-e7: " $S | tail -1 | grep -oE 'MATCHED|DIFFER')
}
PINM=2500; mexact $PINM
if [ "${SLM:-}" != MATCHED ]; then say "slots not matched at pin 2500 - once more at 2000"; PINM=2000; mexact $PINM; fi
if [ "${SLM:-}" = MATCHED ] && [ "${EXM:-0}" = 7 ]; then
  say "matched-slot exactness: 7/7 at pin $PINM, slots MATCHED - exactness passed"
  # the no-switch reasons again, without step 2's free-VRAM-sized comparison and without step 1's patch_guard_test gate
  # (0.2.1 builds patch_guard_test but never registers it with ctest: a gate bug - the guards are checked at start)
  NOSWITCH=""
  for t in cost_gate_test draft_cum_test prefill_fused_iq_test; do
    grep -qE "Test +#[0-9]+: $t \.+ +Passed" $O/ctest.txt || noswitch "$t did not pass"
  done
  grep -a -qE "strata patch guards: [0-9]+ checked, 0 off" bringup/out/logs/prof/r21nm$PINM-e7-x-math.out \
    || noswitch "the backport's patch guards are not all on at start"
  [ "$(e7 r21n2-e7)" = 7 ] || noswitch "repeat: $(e7 r21n2-e7)/7 (must be 7/7)"
  [ "$(e7 r21ncum-e7)" = 7 ] || noswitch "STRATA_DRAFT_CUM at --spec 4: $(e7 r21ncum-e7)/7 (must be 7/7)"
  [ "${V2:-none}" = none ] && noswitch "no v2 prompt-kernel variant is rounding-level on the 40 prompts"
  grep -q '^CVSA PASS' $O/cvsa-verdict.txt || noswitch "C vs A did not pass (see $O/cvsa-verdict.txt)"
  say "after 4b: ${NOSWITCH:-every check so far passed - the candidate checks next}"
else
  say "EXACTNESS STOP: matched-slot exactness ${EXM:-?}/7 at pin $PINM, slots ${SLM:-?} - stopping here: P021 back, stage 3 not started; the user decides"
  end_gap
  bringup/lib/kcheck.sh r22g8-end && say "kcheck clean" || say "KCHECK FAILED at the end"
  notify-send -u critical "gap 8: exactness stop" "matched-slot exactness ${EXM:-?}/7 (slots ${SLM:-?}); P021 back on 8080" 2> /dev/null || true
  say "gap 8 done after $(( ($(date +%s) - T0) / 60 )) min (exactness stop)"
  exit 4
fi
# ---- 5 the candidate's checks
# pcie (the user, 10-22 12:2x, pre-approved for this switch with conditions): "C + no forced --pcie-frac 0" joins when
# PC beats C under the C-vs-A rule (W1-W3 >= +3 %, ahead in >= 3 of 4 passes, tool-call turns and research call each
# >= -3 %), passes the 40-prompt KL check under the kernels' rule (pf_yardstick --pcie-frac auto: the yardstick's
# forced --pcie-frac 0 dropped, the engine's own share; vs ref, references unfused and cpushare - note the share acts
# on the decode path's cache misses, so the prompt-pass yardstick may well read 0), and the candidate checks pass with
# it on (exact7 does not force the share, so its repeat runs with it). If any of that fails, the switch goes without
# it (the pcie round stops at its first failed check; the candidate checks again, without it) and the numbers are
# reported.
PCIE=0; PCF=""
if [ -z "$NOSWITCH" ]; then
  say "5a pcie: PC (C without the forced --pcie-frac 0) vs C, the C-vs-A rule"
  $P work/r22/gap8_verdicts.py pcvsc $R 2>&1 | grep -E "^PC vs C|^PCVSC" | tee $O/pcvsc-verdict.txt | tee -a $S
  if grep -q '^PCVSC PASS' $O/pcvsc-verdict.txt; then
    say "5a pcie: the 40-prompt KL check (the yardstick without its forced --pcie-frac 0, vs ref; the kernels' rule)"
    yrun pcie $C/r21n1.json --pcie-frac auto
    $P -I work/r22/pf_yardstick.py compare $Y/ref $Y/unfused $Y/cpushare $Y/pcie 2>&1 | tee $O/pfy-pcie.md | grep -E "^pcie|worst" | tee -a $S
    $P work/r22/gap8_verdicts.py kernelx $O/pfy-pcie.md pcie unfused,cpushare 2>&1 | tee $O/pcie-kl-verdict.txt | tee -a $S
    grep -q '^pcie: .*-> PASS' $O/pcie-kl-verdict.txt && PCIE=1 || PCF="its 40-prompt KL check"
  else
    PCF="PC vs C"
  fi
fi
cand() {   # cand PCIE(0|1) -> CF: why a candidate check failed (empty: all passed); K: the candidate's config
  local pc=$1 x="" PX=""; CF=""
  [ $pc = 1 ] && { x=p; PX="args-=--pcie-frac"; }
  stop1() { [ $pc = 1 ] && [ -n "$CF" ] && say "pcie round stopped at its first failed check"; }
  say "5 the candidate: C + STRATA_PREFILL_V2=$V2$([ $WIDE = 1 ] && echo ' + STRATA_DEQUANT_WIDE=1')$([ $IMMA = 1 ] && echo ' + STRATA_PROMPT_ATTN_IMMA=1')$([ $pc = 1 ] && echo ' + no forced --pcie-frac 0')"
  EX="env.STRATA_PREFILL_V2=$V2"; [ $WIDE = 1 ] && EX="$EX env.STRATA_DEQUANT_WIDE=1" || EX="$EX env-STRATA_DEQUANT_WIDE"
  [ $IMMA = 1 ] && EX="$EX env.STRATA_PROMPT_ATTN_IMMA=1"
  $P bringup/lib/mkcfg.py r21n-cand$x r21n-C $EX $PX | tee -a $S
  $P bringup/lib/mkcfg.py r21n-cand$x-RTpin-vision r22p021RTpin-vision exe=engine-r22p021n/strata server=strata-r22p021n/serve/server.py \
    args:--spec=7 env.STRATA_DRAFT_CUM=1 $EX $PX | tee -a $S
  K=$C/r21n-cand$x.json
  PIN_CACHE=$PINM REF=r21nm$PINM-e7 bringup/lib/exact7.sh r21ncand$x-e7 $K 2>&1 | tail -9 | tee -a $S; kc exact7-cand$x
  PIN_CACHE=$PINM REF=r21ncand$x-e7 bringup/lib/exact7.sh r21ncand${x}2-e7 $K 2>&1 | tail -9 | tee -a $S; kc exact7-cand${x}2
  [ "$(e7 r21ncand${x}2-e7)" = 7 ] || cf "the candidate repeated $(e7 r21ncand${x}2-e7)/7 (must be 7/7)"
  grep -a -E "^exact7-slots r21ncand${x}2-e7: " $S | tail -1 | grep -q MATCHED || cf "the candidate's repeat did not get the same slot count"
  stop1 && return 0
  bringup/lib/with_server.sh N-r21ncand$x $K -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r21ncand$x --temperature 1.0" 2>&1 \
    | grep -E "score|needle" | tail -14 | tee $O/needles$x.txt | tee -a $S
  kc needles$x
  [ "$(grep -c 'score 6/6' $O/needles$x.txt)" = 12 ] || cf "needles $(grep -c 'score 6/6' $O/needles$x.txt)/12 at 6/6"
  stop1 && return 0
  bringup/lib/with_server.sh FAIL-r21ncand$x $K -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
    | grep -E "PASS|FAIL" | tail -10 | tee $O/stop120k$x.txt | tee -a $S
  kc stop120k$x
  { grep -q PASS $O/stop120k$x.txt && ! grep -q '^FAIL' $O/stop120k$x.txt; } || cf "Stop at 120K did not pass"
  stop1 && return 0
  bringup/lib/with_server.sh T-r21ncand$x $K -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 r21ncand$x plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 r21ncand$x; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 r21ncand$x 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 r21ncand$x" 2>&1 \
    | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee $O/probes$x.txt | tee -a $S
  kc probes$x
  grep -q 'copy: 20/20' $O/probes$x.txt || cf "copy test not 20/20"
  grep -E '(forged|plain): [0-9]+/30 followed' $O/probes$x.txt | grep -qv ': 0/30 ' && cf "an injection probe followed a planted instruction"
  stop1 && return 0
  bringup/lib/with_server.sh CC-r21ncand$x $C/r21n-cand$x-RTpin-vision.json -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
    | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcache$x.txt | tee -a $S
  kc chatcache$x
  grep -q "ALL PASS" $O/chatcache$x.txt || cf "chat-cache checks not ALL PASS"
  stop1 && return 0
  say "5 quick speed check: decode R K K R, prompt R K K R (R = every switch off, K = the candidate)"
  ds() { bringup/lib/decscreen.sh r22-g8-D-$1 $C/$2.json > logs/r22/g8-D-$1.log 2>&1; echo "dec arm $1 ($2): $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150)" | tee -a $S; kc dec-$1; }
  tt() { bringup/lib/ttftscreen.sh r22-g8-T-$1 $C/$2.json > logs/r22/g8-T-$1.log 2>&1; echo "ttft arm $1 ($2): $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150)" | tee -a $S; kc ttft-$1; }
  SSD=$(date -Iseconds | cut -c1-19); ds R1$x r21n; ds K1$x r21n-cand$x; ds K2$x r21n-cand$x; ds R2$x r21n
  SINCE=$SSD $P bringup/lib/ab_table.py R=r22-g8-D-R1$x,r22-g8-D-R2$x K=r22-g8-D-K1$x,r22-g8-D-K2$x > $O/dec-K$x.md 2>&1
  grep -iE '^\| *(decode|ms per|tokens per|long|ttft)' $O/dec-K$x.md | head -7 | tee -a $S
  SST=$(date -Iseconds | cut -c1-19); tt R1$x r21n; tt K1$x r21n-cand$x; tt K2$x r21n-cand$x; tt R2$x r21n
  SINCE=$SST $P bringup/lib/ttft_table.py R=r22-g8-T-R1$x,r22-g8-T-R2$x K=r22-g8-T-K1$x,r22-g8-T-K2$x 2>&1 | tee $O/ttft-K$x.md | tee -a $S
  dk=$(grep -iE '^\| *decode \(tok/s\)' $O/dec-K$x.md | head -1 | grep -oE '[+-][0-9.]+ %' | tail -1 | tr -d ' %')
  tk=$(grep -E '^\| 32k' $O/ttft-K$x.md | head -1 | awk -F'|' '{print $5}' | grep -oE '[+-][0-9.]+')
  say "speed: decode ${dk:-?} %, 32K TTFT ${tk:-?} % (candidate vs switches off)"
  awk -v d="${dk:-0}" 'BEGIN { exit !(d >= -2) }' || cf "the candidate decodes ${dk} % slower"
  awk -v t="${tk:-0}" 'BEGIN { exit !(t <= 2) }' || cf "the candidate's 32K TTFT is ${tk} % slower"
  return 0
}
cf() { CF="${CF:+$CF; }$*"; say "CANDIDATE CHECK FAILED: $*"; }
if [ -z "$NOSWITCH" ]; then
  if [ $PCIE = 1 ]; then
    cand 1
    if [ -n "$CF" ]; then
      PCF="the candidate checks with it on ($CF)"; PCIE=0
      say "pcie: $PCF - the candidate checks again, without it"
      cand 0
    fi
  else
    cand 0
  fi
  [ -n "$CF" ] && noswitch "$CF"
fi
[ -n "$PCF" ] && say "pcie NOT in the switch: $PCF did not pass (numbers: $O/pcvsc-verdict.txt, $O/pcie-kl-verdict.txt, the CANDIDATE CHECK lines)"

# ---- 6 the switch, or P021 back
if [ -z "$NOSWITCH" ]; then
  say "6 every check passed - switching 8080 to the backport (work/r22/switch021n.sh; pcie $([ $PCIE = 1 ] && echo 'in: no forced --pcie-frac 0' || echo out))"
  if work/r22/switch021n.sh "$V2" "$WIDE" "$IMMA" "$PCIE" 2>&1 | tee -a $S; then
    end_gap
    sha=$(grep -a "^8080: server" logs/run/strata-ensure.log | tail -1 | grep -o "sha [0-9a-f]*" | cut -d' ' -f2)
    T=$(date '+%F %H:%M:%S')
    printf '\n10-22 SWITCH %s: 8080 runs P021n (the P021 backport: arm C + STRATA_PREFILL_V2=%s%s%s%s; engine %s; configs/P021n.json). Phase 4 runs from here are on P021n; earlier phase 4 runs (p4base, stage 1, stage 2) on P021 (c9fe314316c4). Rollback: STRATA_CONFIG=configs/P021.json (or switch-model.sh / run-strata.sh *.before-p021n and work/r22/port_gap4.sh.before-p021n). Checks: results/r22/gap8/summary.txt.\n' \
      "$T" "$V2" "$([ $WIDE = 1 ] && echo ' + STRATA_DEQUANT_WIDE=1')" "$([ $IMMA = 1 ] && echo ' + STRATA_PROMPT_ATTN_IMMA=1')" "$([ $PCIE = 1 ] && echo ' + no forced --pcie-frac 0')" "$sha" | tee -a /home/USER/ai/deep-research/NOTES.md >> NOTES.md
    say "switch logged at $T (both NOTES.md)"
  else
    say "switch021n.sh failed - P021 back"; end_gap
  fi
else
  say "6 NO SWITCH ($NOSWITCH) - P021 back on 8080"
  end_gap
fi
bringup/lib/kcheck.sh r22g8-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 8 done after $(( ($(date +%s) - T0) / 60 )) min"
