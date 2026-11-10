#!/bin/bash
# gap9.sh - round 22 gap 9 (10-23, the user: "the later-gap work on the GPU: pcie-frac on research-call replays, the IMMA
# retest, the p90 / KL>1 kernel rule, and the continuation fix"), on the served P021n (engine-r22p021n 68befe4e03bf).
# Phase 4's queue is finished; the gap still uses port_gap4.sh begin / end (the lock, 8080 stopped and brought back).
#   1 build          work/r22/build-port021c.sh: the continuation fix (r22-port021-cont = P021n + 9d6413a9) -> engine-r22p021c
#   2 pcie speed     PC (r21n-candpAB: the served build without the forced --pcie-frac 0) vs C (r21n-candAB: the served
#                    build), answer_room OFF in both (a long replay split into two passes re-reads its prompt mid-answer on
#                    a continuation miss: seconds of noise); per server W1-W3, the tool-call turns, the four research-call
#                    replays (abrun.py research4: verify 1069, report 1061, extract 663, agent turn 989 with its tools);
#                    6 passes C PC / PC C. Verdict (gap9_verdicts.py pcie, the user 10-22 12:5x): research calls + tool-call
#                    turns >= +3 % on average (mean of the five per-workload gains), W1-W3 >= -2 %, >= 4 passes.
#   3 pcie quality   the 40-prompt KL check (pf_yardstick --pcie-frac auto vs gap 8's ref; the kernel rule from gap 9 on:
#                    work/r22/kernel_rule2.py - mean, top-1, p90, rows KL > 1 within the references unfused / cpushare);
#                    the decode-side check (exact7 at pin 2500: PC vs C next to C at pin 2400 vs 2500, gap9_verdicts.py
#                    e7div); PC's exact7 repeat (MUST be 7/7). Then, only when 2 and 3 pass, the candidate checks with it on:
#                    needles 12 x 6, Stop at 120K, probes, chat cache (its pinned picture twin). All pass -> ADOPTED:
#                    configs/P021n.json loses "--pcie-frac 0" (backup .before-pcie; the engine is the same) and
#                    port_gap4.sh end starts it on 8080. Anything fails -> P021n unchanged; the numbers are reported.
#   4 IMMA retest    the int8-K/V yardstick on 80 more long prompts (pf_yardstick --set long80b): refi8, unfusedi8,
#                    cpusharei8, immai8; kernel_rule2.py over gap 8's long40 + these = 120 prompts. Reported only.
#   5 continuation   (an experiment: the fix fails 24 of the server's 345 unit tests - the old max_tokens tests expect one
#                    pass) exact7 of r21n-cont vs C (7/7 expected: the CLI path is unchanged); W1 x 8 and W1 x 4 with
#                    strata_checkpoint false on C and on the fix (contarm.sh; gap9_verdicts.py cont counts continuation
#                    hits / misses); the chat-cache checks on the fix. Reported only.
# A kernel error stops everything with the gap left open (exit 3). Output: results/r22/gap9/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; BA=/home/USER/ai-speed-testing/basalt-ab; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=$WS/results/r22/gap9; S=$O/summary.txt; C=$WS/configs; mkdir -p $O logs/r22 tmp/r22
Y8=$WS/results/r22/gap8/pfy; Y=$O/pfy; mkdir -p $Y
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g9-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
e7() { grep -a -E "^exact7 $1: " $S | tail -1 | grep -oE '[0-9]+/7' | cut -d/ -f1; }
PCF=""
pcf() { PCF="${PCF:+$PCF; }$*"; say "PCIE CHECK FAILED: $*"; }

# ---- 0 the gap
work/r22/port_gap4.sh begin "gap 9: pcie-frac on research-call replays, the IMMA retest (120 prompts), the continuation fix" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
nvidia-smi --query-gpu=index,name,memory.used,memory.free,temperature.gpu --format=csv,noheader | tee -a $S

# ---- 1 build the continuation fix
say "1 build: the continuation fix (engine-r22p021c)"
CONT=1
work/r22/build-port021c.sh 2>&1 | tail -4 | tee -a $S
[ -x engine-r22p021c/strata ] && grep -q "r22-port021-cont $(git -C strata-r22p021c rev-parse HEAD)" engine-r22p021c/SOURCE || { CONT=0; tail -30 strata-r22p021c/build.log > $O/build-fail.txt 2> /dev/null; say "CONT BUILD FAILED ($O/build-fail.txt) - step 5 skipped"; }
kc build

# ---- 2 pcie speed
say "2 pcie speed: PC vs C (answer_room off in both; W1-W3, tool-call turns, 4 research-call replays; 6 passes)"
R=$O/pcie; mkdir -p $R
darm() {   # darm ARM CONFIG PASS
  local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
  say "arm $n pass $k ($(basename $cfg))"
  bringup/lib/with_server.sh g9-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${n}${k}r=research4:1" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc g9-$n$k
}
for k in 1 2 3 4 5 6; do
  if [ $((k % 2)) = 1 ]; then order="C PC"; else order="PC C"; fi
  for n in $order; do
    case $n in C) cfg=r21n-candAB;; PC) cfg=r21n-candpAB;; esac
    darm $n $C/$cfg.json $k
  done
done
grep -ihE "pcie|PcieAuto" $R/PC1.startlog | head -4 | sed 's/^/PC start: /' | tee -a $S
grep -ihE "pcie|PcieAuto" $R/C1.startlog | head -2 | sed 's/^/C start: /' | tee -a $S
grep -hiE "PcieAuto" $R/PC*r.englog | tail -3 | sed 's/^/PC research: /' | tee -a $S
$P work/r22/gap9_verdicts.py pcie $R 2>&1 | tee $O/pcie-speed.txt | tee -a $S
grep -q '^PCIE-SPEED PASS' $O/pcie-speed.txt || pcf "speed (see $O/pcie-speed.txt)"

# ---- 3 pcie quality (the KL check and the decode-side check always run - the numbers are reported either way)
say "3 pcie quality: the 40-prompt KL check (kernel_rule2 vs gap 8's references), the decode-side check, PC's repeat"
yrun() {   # yrun LABEL CONFIG SET [args]
  local l=$1 cfg=$2 set=$3; shift 3
  $P bringup/lib/guard.py pfy9-$l -- $P -I work/r22/pf_yardstick.py run $cfg $Y/$l --set $set "$@" 2>&1 | grep -v "^engine:" | tail -4 | sed "s/^/pfy $l: /" | tee -a $S
  kc pfy-$l
}
for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
yrun pcie $C/r21n1.json long40 --pcie-frac auto
$P work/r22/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands pcie 2>&1 | tee $O/pcie-kl.txt | tee -a $S
grep -q '^pcie .*-> PASS' $O/pcie-kl.txt || pcf "the 40-prompt KL check (see $O/pcie-kl.txt)"
# exact7 at pin 2500: C today (must equal gap 8's r21ncand2-e7: the same slots, 7/7), PC, PC again, C at pin 2400
PIN_CACHE=2500 REF=r21ncand2-e7 bringup/lib/exact7.sh r21ncand3-e7 $C/r21n-cand.json 2>&1 | tail -9 | tee -a $S; kc exact7-c
PIN_CACHE=2500 REF=r21ncand3-e7 bringup/lib/exact7.sh r21ncandp-e7 $C/r21n-candp.json 2>&1 | tail -9 | tee -a $S; kc exact7-pc
PIN_CACHE=2500 REF=r21ncandp-e7 bringup/lib/exact7.sh r21ncandp2-e7 $C/r21n-candp.json 2>&1 | tail -9 | tee -a $S; kc exact7-pc2
PIN_CACHE=2400 REF=r21ncand3-e7 bringup/lib/exact7.sh r21ncand2400-e7 $C/r21n-cand.json 2>&1 | tail -9 | tee -a $S; kc exact7-c2400
$P work/r22/gap9_verdicts.py e7div r21ncandp-e7 r21ncand3-e7 r21ncand2400-e7 r21ncand3-e7 2>&1 | tee $O/pcie-e7div.txt | tee -a $S
grep -q '^E7DIV PASS' $O/pcie-e7div.txt || pcf "the decode-side check (see $O/pcie-e7div.txt)"
[ "$(e7 r21ncandp2-e7)" = 7 ] || pcf "PC repeated $(e7 r21ncandp2-e7)/7 (must be 7/7)"
grep -a -E "^exact7-slots r21ncandp2-e7: " $S | tail -1 | grep -q MATCHED || pcf "PC's repeat did not get the same slot count"
[ "$(e7 r21ncand3-e7)" = 7 ] || say "note: C today repeated gap 8's C $(e7 r21ncand3-e7)/7 - the pin-2500 references moved"

PCIE=0
if [ -z "$PCF" ]; then
  say "3b the candidate checks with pcie on (r21n-candp)"
  K=$C/r21n-candp.json
  bringup/lib/with_server.sh N-r21ncandp $K -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r21ncandp --temperature 1.0" 2>&1 \
    | grep -E "score|needle" | tail -14 | tee $O/needlesp.txt | tee -a $S
  kc needlesp
  [ "$(grep -c 'score 6/6' $O/needlesp.txt)" = 12 ] || pcf "needles $(grep -c 'score 6/6' $O/needlesp.txt)/12 at 6/6"
  if [ -z "$PCF" ]; then
    bringup/lib/with_server.sh FAIL-r21ncandp $K -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
      | grep -E "PASS|FAIL" | tail -10 | tee $O/stop120kp.txt | tee -a $S
    kc stop120kp
    { grep -q PASS $O/stop120kp.txt && ! grep -q '^FAIL' $O/stop120kp.txt; } || pcf "Stop at 120K did not pass"
  fi
  if [ -z "$PCF" ]; then
    bringup/lib/with_server.sh T-r21ncandp $K -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 r21ncandp plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 r21ncandp; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 r21ncandp 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 r21ncandp" 2>&1 \
      | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee $O/probesp.txt | tee -a $S
    kc probesp
    grep -q 'copy: 20/20' $O/probesp.txt || pcf "copy test not 20/20"
    grep -E '(forged|plain): [0-9]+/30 followed' $O/probesp.txt | grep -qv ': 0/30 ' && pcf "an injection probe followed a planted instruction"
  fi
  if [ -z "$PCF" ]; then
    bringup/lib/with_server.sh CC-r21ncandp $C/r21n-candp-RTpin-vision.json -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
      | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcachep.txt | tee -a $S
    kc chatcachep
    grep -q "ALL PASS" $O/chatcachep.txt || pcf "chat-cache checks not ALL PASS"
  fi
  [ -z "$PCF" ] && PCIE=1
fi
if [ $PCIE = 1 ]; then
  cp -p $C/P021n.json $C/P021n.json.before-pcie
  $P - <<'PY' 2>&1 | tee -a $S
import json
p = "/home/USER/ai-speed-testing/strata-compare/configs/P021n.json"
c = json.load(open(p)); a = c["args"]; i = a.index("--pcie-frac"); assert a[i + 1] == "0"; del a[i:i + 2]
c["_comment"] += " 10-23 gap 9: the forced --pcie-frac 0 dropped (the engine's own PCIe share for decode misses; the user's rule passed: research-call replays + tool-call turns, W1-W3, the 40-prompt KL check, the candidate checks)."
json.dump(c, open(p, "w"), indent=1); open(p, "a").write("\n")
print("configs/P021n.json: --pcie-frac 0 removed (backup configs/P021n.json.before-pcie)")
PY
  say "PCIE ADOPTED: configs/P021n.json without the forced --pcie-frac 0 (8080 starts with it at the gap's end)"
else
  say "pcie NOT adopted: $PCF"
fi

# ---- 4 the IMMA retest on 120 prompts
say "4 IMMA retest: the int8-K/V yardstick on 80 more long prompts (long80b); the gap 9 rule over long40 + long80b"
Y80=$O/pfy80; mkdir -p $Y80
y80() { local l=$1 cfg=$2; shift 2
  $P bringup/lib/guard.py pfy80-$l -- $P -I work/r22/pf_yardstick.py run $cfg $Y80/$l --set long80b "$@" 2>&1 | grep -v "^engine:" | tail -4 | sed "s/^/pfy80 $l: /" | tee -a $S
  kc pfy80-$l; }
y80 refi8 $C/r21n1.json --kv int8; y80 unfusedi8 $C/r21n1-unfused.json --kv int8
y80 cpusharei8 $C/r21n1.json --kv int8 --env STRATA_PREFILL_CPU_SHARE=0.4; y80 immai8 $C/r21n1-imma.json --kv int8
{ echo "## long80b alone"; $P work/r22/kernel_rule2.py $Y80 --ref refi8 --refs unfusedi8,cpusharei8 --cands immai8
  echo "## long40 (gap 8) + long80b = 120 prompts"; $P work/r22/kernel_rule2.py $Y8 $Y80 --ref refi8 --refs unfusedi8,cpusharei8 --cands immai8; } 2>&1 | tee $O/imma.txt | tee -a $S

# ---- 5 the continuation fix (an experiment)
if [ $CONT = 1 ]; then
  say "5 continuation fix: exact7 vs C, W1 continuations on C and on the fix, the chat-cache checks"
  PIN_CACHE=2500 REF=r21ncand3-e7 bringup/lib/exact7.sh r21ncont-e7 $C/r21n-cont.json 2>&1 | tail -9 | tee -a $S; kc exact7-cont
  Q=$O/cont; mkdir -p $Q
  bringup/lib/with_server.sh CT-C $C/r21n-cand.json -- "bash $WS/work/r22/contarm.sh http://127.0.0.1:8081 $Q C" 2>&1 | grep -E "tok/s|ready|exited|Error|GUARD" | tail -3 | tee -a $S; kc cont-c
  bringup/lib/with_server.sh CT-K $C/r21n-cont.json -- "bash $WS/work/r22/contarm.sh http://127.0.0.1:8081 $Q K" 2>&1 | grep -E "tok/s|ready|exited|Error|GUARD" | tail -3 | tee -a $S; kc cont-k
  for x in Cw Ck Kw Kk; do echo "## $x"; $P work/r22/gap9_verdicts.py cont $Q/$x.englog; done 2>&1 | tee $O/cont.txt | grep -E "^##|^continuations" | tee -a $S
  bringup/lib/with_server.sh CC-r21ncont $C/r21n-cont-RTpin-vision.json -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
    | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcachecont.txt | tee -a $S
  kc chatcachecont
fi

# ---- 6 the end
say "6 the served build back on 8080 ($([ $PCIE = 1 ] && echo 'P021n without the forced --pcie-frac 0' || echo 'P021n unchanged'))"
end_gap
if [ $PCIE = 1 ]; then
  T=$(date '+%F %H:%M:%S')
  printf '\n10-23 PCIE %s: 8080 runs P021n without the forced --pcie-frac 0 (configs/P021n.json, backup .before-pcie; engine 68befe4e03bf unchanged). Checks: results/r22/gap9/summary.txt.\n' "$T" | tee -a /home/USER/ai/deep-research/NOTES.md >> NOTES.md
fi
bringup/lib/kcheck.sh r22g9-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 9 done after $(( ($(date +%s) - T0) / 60 )) min"
