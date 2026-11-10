#!/bin/bash
# gap18.sh - round 22 gap 18 (11-03, Karl: "GPU work while 7d is being built, only when no LDR run is live. These are
# measurements only: P028x stays the served build, and nothing switches until item 7 is done"):
#   1 the measuring gap: P028x on the 5080 alone (x28h-solo) with its timing logs on - one screen pass with
#     STRATA_DECODE_TIMING=1, one with STRATA_VERIFY_PROFILE=1 (measured waits instead of SINGLE-CARD-STUDY.md's fit)
#   2 exact7 at pin 2500: the base x28h, the base again (repeat), and each switch arm (STRATA_DF_PDL=1, STRATA_IQ_GATHER=1,
#     STRATA_GRAPH_PRIO=1, STRATA_FUSE_WAIT=2, all four) against the base - must be 7/7 identical
#   3 the 9-workload screen, 3 passes in turned order: B (x28h) and the five switch arms (configs/x28h-sw-*.json)
#   4 work/r22/g18_rules.py (written before the gap) -> results/r22/gap18/decision.txt; P028x back (port_gap4.sh end)
#   5 (11-03) the v0.2.10 port's build after the measurements (engine-r22p0210; work/r22/build-port0210.sh)
# Every arm's engine environment is checked before it measures (STRATA_ROUTE_TAIL_SKIP=0, the GPU count). Gap 16's
# harness (bringup/lib/with_server.sh + work/r22/abarm.sh; bringup/lib/exact7.sh). A kernel-check failure stops with the
# gap open (8080 down). No new step after 140 min.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=.venv/bin/python; O=$WS/results/r22/gap18; S=$O/summary.txt; R=$O/speed; C=$WS/configs; mkdir -p $R
EXE28=$WS/engine-r22p028x/strata; CHK=/home/USER/ai-speed-testing/basalt-020/scripts/p028x_env_check.sh
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
KFAIL=0
kc() { bringup/lib/kcheck.sh "r22g18-$1" > /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I work/r22/g18_rules.py $O 2>&1 | tee -a $S
  say "P028x back on 8080 (port_gap4.sh end)"
  work/r22/port_gap4.sh end 2>&1 | tee -a $S
  kc end
  say "gap 18 done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
}
darm() {   # darm NAME CONFIG NGPU: one screen pass (warm-up + W1-W3, agent x2, research4 x4) on one fresh server
  local n=$1 cfg=$2 g=$3 L off; L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  ok_to_go || { say "skipped screen $n (deadline or kernel check)"; return; }
  say "screen $n ($(basename $cfg))"
  bringup/lib/with_server.sh g18-$n $cfg -- "bash $CHK $EXE28 $g && bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" 2>&1 \
    | grep -E "engine pid [0-9]+: STRATA|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc g18-$n
}
e7() {   # e7 LABEL ENVX [REF]
  ok_to_go || { say "skipped exact7 $1"; return; }
  say "exact7 $1 (${2:-base})"
  if [ -n "${3:-}" ]; then PIN_CACHE=2500 REF=$3 ENVX="$2" bringup/lib/exact7.sh $1 $C/x28h.json 2>&1 | tail -9 | tee -a $S
  else PIN_CACHE=2500 ENVX="$2" bringup/lib/exact7.sh $1 $C/x28h.json 2>&1 | tail -9 | tee -a $S; fi
  kc e7-$1
}

# ---- 0 the gap
say "GAP 18 (work/r22/gap18.sh): the measuring gap + the screen of the four bitwise switches (Karl 11-03)"
work/r22/port_gap4.sh begin "gap 18: P028x timing logs on the 5080 alone + the bitwise-switch screen (measurements only; Karl 11-03)" 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + 140 * 60 ))
kc open || end_gap

# ---- 1 the measuring gap (the 5080 alone, timing logs)
say "1 P028x on the 5080 alone with its timing logs (x28h-solo + STRATA_DECODE_TIMING=1, + STRATA_VERIFY_PROFILE=1)"
darm SOLOt $C/x28h-solo-dtime.json 1
darm SOLOv $C/x28h-solo-vprof.json 1
for n in SOLOt SOLOv; do cp -f $(elog $C/x28h-solo-$([ $n = SOLOt ] && echo dtime || echo vprof).json) $O/engine-$n.log 2>/dev/null; done

# ---- 2 exact7 (must be 7/7 identical to the base)
say "2 exact7 at pin 2500: the base, its repeat, and each switch arm against the base"
e7 g18-base ""
e7 g18-base2 "" g18-base
e7 g18-pdl "STRATA_DF_PDL=1" g18-base
e7 g18-gather "STRATA_IQ_GATHER=1" g18-base
e7 g18-prio "STRATA_GRAPH_PRIO=1" g18-base
e7 g18-fwait "STRATA_FUSE_WAIT=2" g18-base
e7 g18-all "STRATA_DF_PDL=1 STRATA_IQ_GATHER=1 STRATA_GRAPH_PRIO=1 STRATA_FUSE_WAIT=2" g18-base

# ---- 3 the screen, 3 passes in turned order
say "3 the 9-workload screen: B (x28h) and the five switch arms, 3 passes in turned order"
for k in 1 2 3; do
  case $k in 1) order="B pdl gather prio fwait all";; 2) order="all fwait prio gather pdl B";; 3) order="gather B all pdl fwait prio";; esac
  for n in $order; do
    if [ $n = B ]; then darm B$k $C/x28h.json 2; else darm $n$k $C/x28h-sw-$n.json 2; fi
  done
done

# ---- 4 the v0.2.10 port's build (gap 17 prep, Karl 11-03): here because nothing else may run during a compile (no LDR
# run - the queue is held - and no timed run - the measurements are done); 8080 stays down for it (~15-20 min)
if ok_to_go; then
  say "4 build the v0.2.10 port (work/r22/build-port0210.sh -> engine-r22p0210)"
  if work/r22/build-port0210.sh 2>&1 | tail -3 | tee -a $S && [ -x engine-r22p0210/strata ]; then
    say "v0.2.10 port built: $(cut -c1-12 engine-r22p0210/SHA256)"
  else
    say "v0.2.10 PORT BUILD FAILED (strata-r22p0210/build.log) - P028x unaffected"
  fi
  kc build0210
else
  say "skipped the v0.2.10 build (deadline or kernel check)"
fi
end_gap
