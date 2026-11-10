#!/bin/bash
# gap16.sh - round 22 gap 16 (10-30): both switches back on the v0.2.8 port, after the code studies
# (results/r22/switch-diag/: prefill-v2.md, gr-fork.md, decode-loss.md), under Karl's conditions of 10-30:
#   1 the same check-(2) scoring for every build: the reference scored in 1-token windows (STRATA_FORCE_T1, PCIe share
#     0.35 in the check arms) on P021m, stock v0.2.8, and the port with the fork on and off; P021m must pass under it
#   2 the old 3-token-window result next to it, as a diagnostic (a second server per arm, strata_logp only)
#   3 the fork also passes checks (1) and (2) on the speculative path; the samples at the tie position and the smallest
#     difference the checks could detect there are reported (work/r22/g16_rules.py)
#   4 quality gates unchanged: kernel_rule2.py (the form gaps 12-15 used) AND kernel_rule3.py (the 10-26 form with the
#     NLL check), both required
#   5 the switch: only if 1-4 pass, PREFILL_V2's bit-identical tests pass, and the speed screen shows the port matching
#     P021m within noise (conversation cache off). Borderline = no switch. The rule is g16_rules.py decide, written down
#     before the gap; Basalt's community-1 fixtures (cold, 3 passes) are the per-test decode check (Karl 10-30, PR #90).
#   PREFILL_V2  v2 takes the current kernels' term (branch r22-port028x, 8f7a48aa): v2 on = v2 off bit for bit.
#   GR_FORK     carries the decode loss (decode-loss.md: ~3.5 % per step); check (2) now with the 1-token reference.
#   conversation cache  0.2.3's automatic one pinned off in x28h (--conversation-cache-mib 0); x28h-conv keeps it (priced).
# Steps: 1 builds (port, port twin, P021m twin, stock twin), 2 tests, 3 exact7, 4 lossless, 5 KL (byte-identical logits +
# both rules), 6 speed screen (3 passes) + Basalt fixtures (cold, 3 passes), 7 check (2) speculation off on four builds
# (+ the 3-token diagnostic, + STATE_HASH pairing), 8 checks (1) + (2) on the speculative path (port, P021m), 9 the
# served form (chat cache, a picture), 10 the decision, and the switch (switch028x.sh) or P021m back.
# Output: results/r22/gap16/ (summary.txt, gates.txt, decision.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab; O=$WS/results/r22/gap16; S=$O/summary.txt; C=$WS/configs
Y8=$WS/results/r22/gap8/pfy; Y=$O/pfy; G=$O/gates.txt; RU=$WS/work/r22/g16_rules.py; mkdir -p $O $Y logs/r22 tmp/r22
: > $G
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$*" >> $G; say "  gate $*"; }
kc() { bringup/lib/kcheck.sh "r22g16-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
exe_of() { $P -c "import json; print(json.load(open('$1'))['exe'])"; }
e7() { grep -a -E "^exact7 $1: " $S | tail -1 | grep -oE '[0-9]+/7' | cut -d/ -f1; }
starts() {   # starts NAME CONFIG - the start lines that show the switches are on
  local L; L=$(elog $2)
  say "  start lines $1: exact $(grep -c 'EXACT speculative sampling on' $L 2>/dev/null), v2 $(grep -c 'STRATA_PREFILL_V2' $L 2>/dev/null), fork $(grep -c -i 'GR_FORK' $L 2>/dev/null)"
}
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
X=$C/x28h.json; XN=$C/x28h-nov2.json; XC=$C/x28h-conv.json; M=$C/r21n-candpm.json
TN=$C/x28t-hnospec.json; TF=$C/x28t-hnospec-nofork.json; TE=$C/x28t-ess.json

# ---- 0 the gap
work/r22/port_gap4.sh begin "gap 16: both switches back on the v0.2.8 port (exact v2, GR_FORK; Karl's conditions 1-5)" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open

# ---- 1 builds
say "1 build: work/r22/build-port028x.sh"
if ! work/r22/build-port028x.sh 2>&1 | tail -4 | tee -a $S || [ ! -x engine-r22p028x/strata ] || ! grep -q 'v0.2.8 + 28 commits' engine-r22p028x/SOURCE; then
  gate build_x FAIL strata-r22p028x/build.log
  say "BUILD FAILED (strata-r22p028x/build.log) - the gap ends, P021m back"; end_gap; exit 1
fi
gate build_x PASS "$(cut -c1-12 engine-r22p028x/SHA256)"
kc build
say "1b twin build: work/r22/build-port028x.sh twin (tests ON)"
TWIN_OK=1
if ! work/r22/build-port028x.sh twin 2>&1 | tail -2 | tee -a $S || [ ! -x engine-r22p028xm/strata ] || ! grep -q 'v0.2.8 + 33 commits' engine-r22p028xm/SOURCE; then
  say "TWIN BUILD FAILED (strata-r22p028xm/build-twin.log) - 2 and the port's checks skipped"; TWIN_OK=0; gate build_xm FAIL strata-r22p028xm/build-twin.log
else
  gate build_xm PASS "$(cut -c1-12 engine-r22p028xm/SHA256)"
fi
kc twin
for t in m21t s28t; do
  say "1c scoring twin $t: work/r22/build-twin16.sh $t"
  case $t in m21t) e=engine-r22p021mt; want='v0.2.1 + 35 commits';; s28t) e=engine-r22s028t; want='v0.2.8 + 5 commits';; esac
  if work/r22/build-twin16.sh $t 2>&1 | tail -2 | tee -a $S && [ -x $e/strata ] && grep -q "$want" $e/SOURCE; then
    gate build_$t PASS "$(cut -c1-12 $e/SHA256)"
  else
    gate build_$t FAIL "see its worktree's build-twin.log"
  fi
  kc twin-$t
done

# ---- 2 tests (the tightened v2 unit test decides v2 first)
if [ $TWIN_OK = 1 ]; then
  say "2 tests (strata-r22p028xm/build-twin): ours, then the v2 unit test that now wants bit-identical H and down rows"
  bad=""
  for t in patch_guard_test cost_gate_test draft_cum_test; do
    a=""; [ $t = patch_guard_test ] && a="$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf $WS/strata-v0115/mtp/rt"
    timeout 900 $P bringup/lib/guard.py g16-$t -- strata-r22p028xm/build-twin/$t $a > $O/$t.txt 2>&1
    rc=$?; [ $rc = 0 ] || bad="$bad $t:rc$rc"
    say "  $t rc $rc: $(grep -v '^\s*$' $O/$t.txt | tail -1 | cut -c1-160)"
  done
  [ -z "$bad" ] && gate tests PASS "patch_guard, cost_gate, draft_cum rc 0" || gate tests FAIL "$bad"
  timeout 1800 $P bringup/lib/guard.py g16-v2test -- strata-r22p028xm/build-twin/prefill_fused_iq_test --v2 --no-timing > $O/prefill_fused_v2_test.txt 2>&1
  rc=$?
  say "  prefill_fused_iq_test --v2 (bit-identical) rc $rc: $(grep -v '^\s*$' $O/prefill_fused_v2_test.txt | tail -1 | cut -c1-160)"
  grep -E 'v2 part|mode 3|bit for bit' $O/prefill_fused_v2_test.txt | head -8 | cut -c1-200 | tee -a $S
  [ $rc = 0 ] && gate v2_unit PASS "prefill_fused_iq_test --v2 rc 0" || gate v2_unit FAIL "rc $rc"
  kc tests
fi

# ---- 3 exact7: v2 exactness across the switch, then the repeat gate
say "3 exact7 at pin 2500: x28h-nov2, x28h against it (v2 exact: want 7/7), x28h again (repeat: want 7/7)"
PIN_CACHE=2500 bringup/lib/exact7.sh x28h-nov2-e7 $XN 2>&1 | tail -9 | tee -a $S; kc e7n
PIN_CACHE=2500 REF=x28h-nov2-e7 bringup/lib/exact7.sh x28h-e7a $X 2>&1 | tail -9 | tee -a $S; kc e7a
PIN_CACHE=2500 REF=x28h-e7a bringup/lib/exact7.sh x28h-e7b $X 2>&1 | tail -9 | tee -a $S; kc e7b
a=$(e7 x28h-e7a); b=$(e7 x28h-e7b)
[ "$a" = 7 ] && gate e7_v2 PASS "v2 on vs off 7/7" || gate e7_v2 FAIL "v2 on vs off ${a:-?}/7"
[ "$b" = 7 ] && gate e7_repeat PASS "repeat 7/7" || gate e7_repeat FAIL "repeat ${b:-?}/7"

# ---- 4 lossless
say "4 lossless: patchtest.sh lossless on x28h"
CFG=$X TREE=strata-r22p028x bringup/patchtest.sh lossless 2>&1 | grep -E "PASS|FAIL" | tail -6 | tee $O/lossless.txt | tee -a $S
grep -q 'cfg: PASS' $O/lossless.txt && ! grep -q FAIL $O/lossless.txt && gate lossless PASS cfg || gate lossless FAIL "$(tail -1 $O/lossless.txt | cut -c1-120)"

# ---- 5 KL: byte-identical logits with v2 on and off, and both forms of the rule against gap 8's references
say "5 KL: pf_yardstick long40 on x28h and x28h-nov2"
for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
for c in x28h x28h-nov2; do
  $P bringup/lib/guard.py pfy16-$c -- $P -I work/r22/pf_yardstick.py run $C/$c.json $Y/$c --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy $c: /" | tee -a $S
  kc pfy-$c
done
nd=0; nf=0
for f in $Y/x28h-nov2/first.*; do [ -e "$f" ] || continue; b=$(basename $f); nf=$((nf + 1)); cmp -s $f $Y/x28h/$b || nd=$((nd + 1)); done
say "  logit files v2 on vs off: $nd of $nf differ (want 0)"
[ $nf -gt 0 ] && [ $nd = 0 ] && gate logits_identical PASS "0 of $nf differ" || gate logits_identical FAIL "$nd of $nf differ"
$P work/r22/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands x28h,x28h-nov2 2>&1 | tee $O/kl.txt | tee -a $S
grep -q -E '^x28h +top-1 .*-> PASS' $O/kl.txt && gate kl_rule2 PASS "$(grep -E '^x28h +top-1' $O/kl.txt | tr -s ' ' | cut -c1-150)" \
  || gate kl_rule2 FAIL "$(grep -E '^x28h +top-1' $O/kl.txt | tr -s ' ' | cut -c1-150)"
$P -I work/r22/kernel_rule3.py $Y --ref ref --refs unfused,cpushare --cands x28h,x28h-nov2 2>&1 | tee $O/kl3.txt | tee -a $S
grep -q -E '^x28h +KL mean .*-> PASS' $O/kl3.txt && gate kl_rule3 PASS "$(grep -E '^x28h +KL mean' $O/kl3.txt | tr -s ' ' | cut -c1-150)" \
  || gate kl_rule3 FAIL "$(grep -E '^x28h +KL mean' $O/kl3.txt | tr -s ' ' | cut -c1-150)"

# ---- 6 speed screen (3 passes) and Basalt's fixtures (cold, 3 passes)
say "6 speed screen: P021m test form (M) vs x28h (X) vs x28h-conv (Xc), 3 passes in turned order"
R=$O/speed; mkdir -p $R
darm() {   # darm ARM CONFIG PASS
  local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
  say "arm $n pass $k ($(basename $cfg))"
  bringup/lib/with_server.sh g16-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${n}${k}r=research4:1" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc g16-$n$k
}
for k in 1 2 3; do
  case $k in 1) order="M X Xc";; 2) order="Xc X M";; 3) order="X M Xc";; esac
  for n in $order; do
    case $n in M) cfg=$M;; X) cfg=$X;; Xc) cfg=$XC;; esac
    darm $n $cfg $k
  done
done
labs=""; for w in n a r; do for n in M X Xc; do for k in 1 2 3; do labs="$labs $n$k$w"; done; done; done
$P $BA/scripts/abreport.py --dir $R $labs > $O/speed-table.md 2>&1
$P -I $RU speed $O/speed-table.md 2>&1 | tee -a $S
B=$WS/work/r22/basalt-pr90; BO=$O/bp90; mkdir -p $BO
say "6b Basalt's community-1 fixtures, cold (a fresh engine per measurement), 3 passes: M vs X (in bp90's files: H = x28h)"
bprun() {   # bprun SESSION BUILD SETS PASS
  local cfg tree; case $2 in M) cfg=$M; tree=$WS/strata-r22p021m;; H) cfg=$X; tree=$WS/strata-r22p028x;; esac
  bringup/lib/with_server.sh g16-bp-$1 $cfg -- "$WS/.venv/bin/python -I $B/bp90_client.py http://127.0.0.1:8081 --label $1 --sets $3 --passes 1 --first-pass $4 --tree $tree --out $BO/cold-$2.jsonl" 2>&1 \
    | grep -E " pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  kc g16-bp-$1
}
for k in 1 2 3; do
  if [ $k = 2 ]; then order="H M"; else order="M H"; fi
  for b in $order; do for set in decode pp16k pp64k; do bprun cold-$b-$set-$k $b $set $k; done; done
done
BP90_NAME_H="v0.2.8 port, both switches (x28h)" $P -I $B/bp90_report.py $BO > $BO/report.md 2>&1
$P -I $RU bp90 $BO 2>&1 | tee -a $S

# ---- 7 check (2), speculation off, with the 1-token reference on four builds (+ the 3-token diagnostic)
SPO=$O/sp; mkdir -p $SPO; cp results/r20/sp-batch/sp-cases.json results/r20/sp-batch/sp-llama.json $SPO/
HP=$WS/work/r22/switch-diag/hashpair.py
chk2arm() {   # chk2arm ARM CONFIG CONFIG_T3 TREE GATE [--info]
  local a=$1 cfg=$2 cfg3=$3 tree=$4 g=$5 info=${6:-} L=g16-$1 EL off rc
  [ -x "$(exe_of $cfg)" ] || { gate $g FAIL "no engine $(exe_of $cfg)"; return; }
  rm -f $SPO/sp-strata-$L.jsonl
  EL=$(elog $cfg); touch $EL; off=$(stat -c %s $EL)
  bringup/lib/with_server.sh g16-sp-$a $cfg -- "SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-$a.txt 2>&1; SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-$a.txt 2>&1" 2>&1 \
    | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
  tail -c +$((off + 1)) $EL > $SPO/englog-$a.txt
  starts $a $cfg
  kc g16-sp-$a
  SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a.txt 2>&1
  say "  check (2), $a, 1-token reference: $($P -I $RU chk2 $SPO/analyze-own-$a.txt --gate $g --gates $G $info)"
  if [ -f $HP ]; then
    python3 -I $HP $SPO/englog-$a.txt --jsonl $SPO/sp-strata-$L.jsonl > $SPO/hashpair-$a.txt 2>&1
    rc=$?
    echo "hashpair_$a INFO rc $rc $(grep -E 'MATCH|DIFFER' $SPO/hashpair-$a.txt | tail -1 | cut -c1-120)" >> $G
    say "  STATE_HASH sampled vs forced (T = 1), $a: rc $rc $(grep -E 'MATCH|DIFFER' $SPO/hashpair-$a.txt | tail -1 | cut -c1-120)"
  fi
  # the old reference, 3-token windows: the same build and settings without STRATA_FORCE_T1, scored on a fresh server
  bringup/lib/with_server.sh g16-t3-$a $cfg3 -- "SP_DIR=$SPO SP_LABEL=$L-t3 STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-$a-t3.txt 2>&1" 2>&1 \
    | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
  kc g16-t3-$a
  cp $SPO/sp-strata-$L.jsonl $SPO/sp-strata-$L-t3.jsonl
  SP_DIR=$SPO SP_LABEL=$L-t3 STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a-t3.txt 2>&1
  say "  diagnostic, $a, 3-token reference: $($P -I $RU chk2 $SPO/analyze-own-$a-t3.txt --gate chk2diag_$a --gates $G --info)"
}
say "7 check (2): arith-j3 T 0.6, 4,000, speculation off, vs own probabilities in 1-token windows (STRATA_FORCE_T1, PCIe 0.35); the 3-token reference beside it"
[ $TWIN_OK = 1 ] && chk2arm hnospec $TN $C/x28t-hnospec-t3.json $WS/strata-r22p028xm chk2_x_fork
chk2arm m21t-hnospec $C/m21t-hnospec.json $C/m21t-hnospec-t3.json $WS/strata-r22p021mt chk2_m21t_nospec
[ $TWIN_OK = 1 ] && chk2arm hnospec-nofork $TF $C/x28t-hnospec-nofork-t3.json $WS/strata-r22p028xm chk2_x_nofork
chk2arm s28t-hnospec $C/s28t-hnospec.json $C/s28t-hnospec-t3.json $WS/strata-r22s028t chk2_s28t_nospec --info

# ---- 8 checks (1) + (2) on the speculative path: the port with the fork, and P021m
essarm() {   # essarm ARM CONFIG TREE REF_ARM GATE_SUFFIX
  local a=$1 cfg=$2 tree=$3 ref=$4 g=$5 L=g16-$1
  if [ ! -x "$(exe_of $cfg)" ] || [ ! -f $SPO/sp-strata-logp-g16-$ref.json ]; then
    gate chk1_$g FAIL "no engine or no reference"; gate chk2_$g FAIL "no engine or no reference"; return
  fi
  rm -f $SPO/sp-strata-$L.jsonl
  bringup/lib/with_server.sh g16-sp-$a $cfg -- "SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-$a.txt 2>&1" 2>&1 \
    | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
  starts $a $cfg
  kc g16-sp-$a
  cp $SPO/sp-strata-logp-g16-$ref.json $SPO/sp-strata-logp-$L.json
  SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a.txt 2>&1
  say "  check (2), $a (vs $ref's 1-token reference): $($P -I $RU chk2 $SPO/analyze-own-$a.txt --gate chk2_$g --gates $G)"
  $P -I work/r22/neartie_compare.py $SPO g16-$ref $L > $SPO/compare-$a.txt 2>&1
  say "  check (1), $a vs $ref: $($P -I $RU chk1 $SPO/compare-$a.txt --gate chk1_$g --gates $G)"
}
say "8 checks (1) + (2) on the speculative path, 4,000 each: the port with both switches (x28t-ess), P021m (m21t-ess)"
if [ $TWIN_OK = 1 ]; then essarm ess $TE $WS/strata-r22p028xm hnospec x_ess; fi
essarm m21t-ess $C/m21t-ess.json $WS/strata-r22p021mt m21t-hnospec m21t_ess

# ---- 9 the served form: chat cache and a picture (as gap 10 checked P021m before its switch)
say "9 the served form: chat-cache checks + a picture on x28h-RTpin-vision"
IMG=$WS/strata-r22p028x/docs/terminal-previews/serving-110-stages.png
bringup/lib/with_server.sh g16-served $C/x28h-RTpin-vision.json -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG > $O/chatcache.txt 2>&1; $P work/r22/vision_check.py http://127.0.0.1:8081 $IMG $O/picture > $O/vision.txt 2>&1" 2>&1 \
  | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
kc served
grep -E "^(PASS|FAIL)|ALL PASS|FAILED" $O/chatcache.txt | tee -a $S
grep -q "ALL PASS" $O/chatcache.txt && gate chatcache PASS "ALL PASS" || gate chatcache FAIL "$(grep -c '^FAIL' $O/chatcache.txt) FAIL lines"
nv=$(grep -c '"answer_chars": [1-9]' $O/vision.txt)
[ "$nv" = 2 ] && gate vision PASS "2 answers (read by hand afterwards: picture-1.txt, picture-2.txt)" || gate vision FAIL "$nv of 2 answers"

# ---- 10 the decision (g16_rules.py decide, written before the gap), then the switch or P021m back
$P -I $RU decide $G $O/speed-table.md $BO > $O/decision.txt 2>&1
DEC=$?
cat $O/decision.txt | tee -a $S
if [ $DEC = 0 ]; then
  say "10 every condition holds - switching 8080 to the port (work/r22/switch028x.sh)"
  if work/r22/switch028x.sh 2>&1 | tee -a $S; then
    end_gap
    NEW=$(cut -c1-12 engine-r22p028x/SHA256)
    sha=$(grep -a "^8080: server" logs/run/strata-ensure.log | tail -1 | grep -o "sha [0-9a-f]*" | cut -d' ' -f2)
    say "8080 engine sha '$sha' (want $NEW)"
    $P work/r22/vision_check.py http://127.0.0.1:8080 $IMG $O/picture8080 2>&1 | tail -3 | tee -a $S
    curl -s -m 300 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"x","messages":[{"role":"user","content":"In your reasoning, list every prime number below 3000 one by one. Then answer with only how many there are."}],"max_tokens":1100,"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0.05}' \
      | $P -c "import json,sys; d=json.load(sys.stdin); c=d['choices'][0]; m=c['message']; print('answer_room check: finish', c.get('finish_reason'), '| answer', repr((m.get('content') or '')[:60]), '| completion tokens', d['usage']['completion_tokens'])" 2>&1 | tee -a $S
    T=$(date '+%F %H:%M:%S')
    printf '\n%s SWITCH (Karl 10-30, gap 16 rule): 8080 runs P028x = the v0.2.8 port (branch r22-port028x = v0.2.8 + 28: GR_FORK and PREFILL_V2 back, v2 bit-identical; 0.2.7 defaults pinned off, conversation cache off, tool_call_recovery false; engine %s; configs/P028x.json). Rollback: STRATA_CONFIG=configs/P021m.json (engine-r22p021m 7b38796237f5; or switch-model.sh / run-strata.sh / work/r22/port_gap4.sh *.before-p028x). Checks: strata-compare results/r22/gap16/ (summary.txt, decision.txt).\n' \
      "$T" "$sha" | tee -a /home/USER/ai/deep-research/NOTES.md >> NOTES.md
    say "switch logged at $T (both NOTES.md)"
  else
    say "switch028x.sh failed - P021m back"; end_gap
  fi
else
  say "10 NO SWITCH (decision.txt) - P021m back on 8080"
  end_gap
fi
bringup/lib/kcheck.sh r22g16-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 16 done after $(( ($(date +%s) - T0) / 60 )) min - $(grep -m1 DECISION $O/decision.txt 2>/dev/null)"
