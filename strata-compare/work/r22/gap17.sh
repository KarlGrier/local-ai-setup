#!/bin/bash
# gap17.sh a|b|all - round 22 gap 17 (Karl 11-02, results/PORT-V0210-PLAN.md "approved as written"): the test of our
# Strata port to v0.2.10 (branch r22-port0210 @ fdd2fffa8, worktree strata-r22p0210, engine-r22p0210 89379c28f361 built in
# gap 18; configs/P0210x.json). WRITTEN 11-03, NOT RUN. P028x stays served; NOTHING SWITCHES (Karl 11-02: until item 7 is
# done) - gap 17 is a test with its gates and pricing. The rules, fixed before the gap: work/r22/g17_rules.py. Run order,
# times, what each gate compares: work/r22/GAP17-README.md. Output: results/r22/gap17/ (summary.txt, gates.txt,
# decision.txt). Karl 11-03: parts a and b run in SEPARATE gaps (between 7d questions):
#   a  (~3.7-4.0 h with 8080 down) builds (the port's tests, plain stock v0.2.10), tests, exact7, KL, the speed screen
#      (with the GDN stack and, Karl 11-03, each GDN path alone), Basalt's cold fixtures, the served form, the tool-call
#      test - every gate that needs no MEASUREMENT twin
#   b  (~2.2 h) the MEASUREMENT twins' builds at its start (inside the gap: the port's twin strata-r22p0210m, branch
#      r22-port0210-meas = r22-port0210 + the 5 MEASUREMENT commits; stock's strata-r22s0210t, r22-stock0210-meas =
#      v0.2.10 + the same 5 - both hand-ported 11-03, not compiled), check (2) in 1-token windows (the port; stock's for
#      information, Karl keeps it), checks (1) + (2) on the speculative path with the lookup windows off and on
#   all  a then b in one gap (~6 h) - kept, but not the plan
# Baseline first (the port with every new switch OFF - the 14 pins - against P028x; "patched, every switch off = the
# release" before anything else), then each gated switch on top of it: (0) GDN_TC + GDN_CONVL2, (1) lookup windows up to
# 12, (2) GR_V3_PF=133 only as the GR_FORK=1 identity check, (3) PF_HC_REGION. No DFlash2, no fork-off arms (the GR_FORK=0
# pair of A3 is a diagnostic, only if the greedy lookup items differ).
# Every serve arm's engine environment is checked before it measures (g17_rules.py envcheck: the engine found by
# /proc/PID/exe, never a command-line pattern). A kernel-check failure stops new steps and leaves the gap OPEN (8080
# down, exit 3: Karl decides). No new step after the part's deadline (G17_MAX_MIN, default a 260 / b 160 / all 420).
set -u -o pipefail
PART=${1:-}
case $PART in a|b|all) ;; *) sed -n 2,23p "$0"; exit 2;; esac
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=$WS/.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab; C=$WS/configs; RU=$WS/work/r22/g17_rules.py
O=$WS/results/r22/gap17; S=$O/summary.txt; G=$O/gates.txt; R=$O/speed; Y=$O/pfy; BO=$O/bp90; SPO=$O/sp
Y8=$WS/results/r22/gap8/pfy; Y16=$WS/results/r22/gap16/pfy; B90=$WS/work/r22/basalt-pr90; T=$WS/work/r22/toolrecovery
mkdir -p $O $R $Y $BO $SPO $O/toolcalls/B $O/toolcalls/P logs/r22 tmp/r22
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp)
PORT_HEAD=${G17_PORT_HEAD:-fdd2fffa8}          # the port head gap 17 was written for (engine-r22p0210 89379c28f361)
W10=$WS/strata-r22p0210; WST=$WS/strata-v0210stock; WTW=$WS/strata-r22p0210m; WSTW=$WS/strata-r22s0210t; W28=$WS/strata-r22p028x
E10=$WS/engine-r22p0210; EST=$WS/engine-v0210stock; ETW=$WS/engine-r22p0210m; ESTW=$WS/engine-r22s0210t
GGUF=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf; MTP=$WS/strata-v0115/mtp/rt
H=$C/P0210x-h.json; X=$C/x28h.json
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [17$PART $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
KFAIL=0
kc() { bringup/lib/kcheck.sh "r22g17-$1" > /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
exe_of() { $P -c "import json; print(json.load(open('$1'))['exe'])"; }
slog() { ls -t bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
sha12() { sha256sum "$1" | cut -c1-12; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }   # a gate's last status ("" = not written)
fatalchk() {   # fatalchk NAME ENGINE_LOG OFFSET LABEL: a sticky CUDA error now ENDS the v0.2.10 engine and the server
  local n=$1 L=$2 off=$3 sl hits   # restarts it (3 deaths in 10 min stop it): an arm with one is void
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || { gate fatal_$n FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite (engine log $L from byte $off; $sl)"; }
}
memguard() {   # build_memguard.sh (since 11-03 it watches ninja in strata-r22p021*, strata-v0210stock* and strata-r22s0210t*:
  # every gap 17 tree) - one per gap 17 part, never holding the test lock
  setsid nohup flock -n $WS/tmp/r22/g17-memguard.lock $WS/work/r22/build_memguard.sh 5400 > /dev/null 2>&1 < /dev/null 8>&- 9>&- &
}
b17() {   # b17 TREE BUILDDIR TESTS(ON|OFF) TARGET... - built as build-port0210.sh builds (Release, CUDA 13.3, arch 89;120,
  local w=$1 d=$2 t=$3; shift 3   # the tree's pinned ggml, nice, <= 16 jobs); logs TREE/BUILDDIR{-configure,}.log
  [ "$(git -C $LL rev-parse HEAD)" = "$(cut -d' ' -f1 $w/third_party/ggml/VERSION.txt)" ] || { echo "llama.cpp is not $w's pinned ggml" > $w/$d.log; return 1; }
  rm -rf $w/$d
  nice -n 5 cmake -G Ninja -S $w -B $w/$d -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=$t \
      "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > $w/$d-configure.log 2>&1 \
    && nice -n 5 cmake --build $w/$d --target "$@" -j ${BUILD_JOBS:-16} > $w/$d.log 2>&1
}
twin_ok() {   # twin_ok TREE BRANCH BASE NCOMMITS [ANCESTOR]: the MEASUREMENT twin's branch is there, clean, the right length
  [ -d $1 ] && [ "$(git -C $1 rev-parse --abbrev-ref HEAD 2> /dev/null)" = $2 ] \
    && [ -z "$(git -C $1 status --porcelain --untracked-files=no)" ] \
    && [ "$(git -C $1 rev-list --count $3..HEAD)" = $4 ] \
    && git -C $1 log -1 --format=%s | grep -q 'STRATA_FORCE_T1' \
    && { [ -z "${5:-}" ] || git -C $1 merge-base --is-ancestor $5 HEAD; }
}
e7() {   # e7 LABEL CONFIG [REF]: exact7 at pin 2500 (bringup/lib/exact7.sh: 7 items, --adapt-swaps 0 --suffix-draft 0)
  ok_to_go || { say "skipped exact7 $1 (deadline or kernel check)"; return 1; }
  say "exact7 $1 ($(basename $2)${3:+ against $3})"
  if [ -n "${3:-}" ]; then PIN_CACHE=2500 REF=$3 bringup/lib/exact7.sh $1 $2 2>&1 | tail -9 | tee -a $S
  else PIN_CACHE=2500 bringup/lib/exact7.sh $1 $2 2>&1 | tail -9 | tee -a $S; fi
  kc e7-$1
}
e7g() { $P -I $RU e7gate $S $1 --gate $2 --gates $G ${3:-} | tee -a $S; }
e7L() {   # e7L LABEL LOOKUP_MAX_T [ENVX]: exact7's 7 items on P0210x-h through the CLI with suffix drafts ON (3, the
  # served default) and --lookup-max-t N (the flag wins over the config's STRATA_LOOKUP_MAX_T=0), pin 2500, --adapt-swaps 0
  local L=$1 Xa="--adapt-swaps 0 --suffix-draft 3 --lookup-max-t $2 --expert-cache 2500" SS='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
  ok_to_go || { say "skipped lookup exact7 $L (deadline or kernel check)"; return 1; }
  say "lookup exact7 $L (--suffix-draft 3 --lookup-max-t $2${3:+; $3})"
  ENVX="${3:-}" bringup/lib/run.sh $L-x-math $H math 1024 $Xa > /dev/null
  ENVX="${3:-}" PROF_SAMPLING="$SS" bringup/lib/run.sh $L-s-math $H math 1024 $Xa > /dev/null
  ENVX="${3:-}" bringup/lib/run.sh $L-x-code $H code 1024 $Xa > /dev/null
  ENVX="${3:-}" PROF_SAMPLING="$SS" bringup/lib/run.sh $L-s-code $H code 1024 $Xa > /dev/null
  ENVX="${3:-}" bringup/lib/run.sh $L-x-p2000 $H p2000 64 $Xa > /dev/null
  ENVX="${3:-}" bringup/lib/run.sh $L-x-32k $H 32k 64 $Xa > /dev/null
  ENVX="${3:-}" bringup/lib/run.sh $L-x-112k $H tf-long112k.prompt 64 $Xa > /dev/null
  kc e7L-$L
}
pfy() {   # pfy NAME CONFIG: pf_yardstick long40 (first-token logits after 40 long prompts, gap 8's yardstick settings)
  ok_to_go || { say "skipped pf_yardstick $1 (deadline or kernel check)"; return 1; }
  $P bringup/lib/guard.py pfy17-$1 -- $P -I work/r22/pf_yardstick.py run $2 $Y/$1 --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy $1: /" | tee -a $S
  kc pfy-$1
}
ndiff() {   # ndiff DIR_A DIR_B: "differing files of all" over A's first.* logit files
  local nd=0 nf=0 f
  for f in $1/first.*; do [ -e "$f" ] || continue; nf=$((nf + 1)); cmp -s $f $2/$(basename $f) || nd=$((nd + 1)); done
  echo "$nd $nf"
}
klrules() {   # klrules CAND:GATE...: kernel_rule2.py AND kernel_rule3.py (with the NLL check) on the long40 dirs against
  # gap 8's references (ref; rounding references unfused, cpushare) -> gates kl2_GATE / kl3_GATE for each candidate run
  local c cand gn l2 l3 cands="" tag
  for c in "$@"; do cand=${c%%:*}; [ -f $Y/$cand/index.json ] && cands="$cands,$cand"; done
  [ -n "$cands" ] || return 0
  tag=$(echo ${cands#,} | tr ',' '-')
  $P work/r22/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands ${cands#,} 2>&1 | tee $O/kl-$tag.txt | tee -a $S
  $P -I work/r22/kernel_rule3.py $Y --ref ref --refs unfused,cpushare --cands ${cands#,} 2>&1 | tee $O/kl3-$tag.txt | tee -a $S
  for c in "$@"; do
    IFS=: read -r cand gn <<< "$c"
    [ -f $Y/$cand/index.json ] || continue   # not run (deadline): the gates stay missing
    l2=$(grep -E "^$cand +top-1" $O/kl-$tag.txt | tr -s ' ' | cut -c1-160); l3=$(grep -E "^$cand +KL mean" $O/kl3-$tag.txt | tr -s ' ' | cut -c1-170)
    echo "$l2" | grep -q -- '-> PASS' && gate kl2_$gn PASS "$l2" || gate kl2_$gn FAIL "${l2:-no line}"
    echo "$l3" | grep -q -- '-> PASS' && gate kl3_$gn PASS "$l3" || gate kl3_$gn FAIL "${l3:-no line}"
  done
}
darm() {   # darm NAME CONFIG [noedit]: one screen pass on a fresh server - warm-up, W1-W3, the 2 agent turns, the 4
  # research replays (the 9 workloads) and the 2 file rewrites (abrun.py's frozen "edit" set: prompts/edit.json; left out
  # with noedit - the GDN arms are priced on the 9 and the cold long prompts)
  local n=$1 cfg=$2 L off pf="" ed="${1}e=edit:1"
  [ "${3:-}" = noedit ] && ed=""
  ok_to_go || { say "skipped screen $n (deadline or kernel check)"; return; }
  [ "$(exe_of $cfg)" = $E10/strata ] && pf=--pins
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "screen $n ($(basename $cfg))"
  bringup/lib/with_server.sh g17-$n $cfg -- "$P -I $RU envcheck $(exe_of $cfg) $cfg $pf --gate env_$n --gates $G && bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1 $ed" 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|vram" | tee -a $S
  fatalchk $n $L $off g17-$n
  kc g17-$n
}
bprun() {   # bprun BUILD SET PASS: Basalt's community-1 set, cold (a fresh engine), one pass; M = x28h, H = P0210x-h,
  # G = the GDN stack, T = GDN_TC alone, V = GDN_CONVL2 alone
  local b=$1 set=$2 k=$3 n=bp$1-$2-$3 cfg tree pf="" L off
  case $b in M) cfg=$X; tree=$W28;; H) cfg=$H; tree=$W10; pf=--pins;; G) cfg=$C/P0210x-h-gdn.json; tree=$W10; pf=--pins;;
             T) cfg=$C/P0210x-h-gdntc.json; tree=$W10; pf=--pins;; V) cfg=$C/P0210x-h-gdncv.json; tree=$W10; pf=--pins;; esac
  ok_to_go || { say "skipped Basalt $n (deadline or kernel check)"; return; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  bringup/lib/with_server.sh g17-$n $cfg -- "$P -I $RU envcheck $(exe_of $cfg) $cfg $pf --gate env_$n --gates $G && $P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label $n --sets $set --passes 1 --first-pass $k --tree $tree --out $BO/cold-$b.jsonl" 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  fatalchk $n $L $off g17-$n
  kc g17-$n
}
chk2arm() {   # chk2arm ARM CONFIG CONFIG_T3|- TREE GATE [--info]: check (2), arith-j3 T 0.6, 4,000, speculation off,
  # against the build's own probabilities in 1-token windows (STRATA_FORCE_T1, PCIe 0.35) - gap 16's form
  local a=$1 cfg=$2 cfg3=$3 tree=$4 g=$5 info=${6:-} L=g17-$1 EL off rc
  ok_to_go || { say "skipped check (2) $a (deadline or kernel check)"; return; }
  [ -x "$(exe_of $cfg)" ] || { say "check (2) $a NOT RUN: no engine $(exe_of $cfg)"; return; }
  rm -f $SPO/sp-strata-$L.jsonl
  EL=$(elog $cfg); touch $EL; off=$(stat -c %s $EL)
  bringup/lib/with_server.sh g17-sp$a $cfg -- "$P -I $RU envcheck $(exe_of $cfg) $cfg --pins --gate env_sp$a --gates $G && { SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P $WS/bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-$a.txt 2>&1; SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P $WS/bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-$a.txt 2>&1; }" 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|ready|exited|refus|Error|GUARD" | tee -a $S
  tail -c +$((off + 1)) $EL > $SPO/englog-$a.txt
  say "  start lines $a: exact $(grep -c 'EXACT speculative sampling on' $SPO/englog-$a.txt), v2 $(grep -c 'prompt experts: v2 kernels' $SPO/englog-$a.txt), lookup-12 $(grep -c 'lookup-max-t 12' $SPO/englog-$a.txt)"
  fatalchk sp$a $EL $off g17-sp$a
  kc g17-sp$a
  SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a.txt 2>&1
  say "  check (2), $a, 1-token reference: $($P -I $RU chk2 $SPO/analyze-own-$a.txt --gate $g --gates $G $info)"
  if [ -f $WS/work/r22/switch-diag/hashpair.py ]; then
    python3 -I $WS/work/r22/switch-diag/hashpair.py $SPO/englog-$a.txt --jsonl $SPO/sp-strata-$L.jsonl > $SPO/hashpair-$a.txt 2>&1
    rc=$?
    gate hashpair_$a INFO "rc $rc $(grep -E 'MATCH|DIFFER' $SPO/hashpair-$a.txt | tail -1 | cut -c1-120)"
  fi
  [ "$cfg3" = - ] && return
  ok_to_go || return
  bringup/lib/with_server.sh g17-t3$a $cfg3 -- "SP_DIR=$SPO SP_LABEL=$L-t3 STRATA_SERVE_TREE=$tree $P $WS/bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-$a-t3.txt 2>&1" 2>&1 \
    | grep -E "ready|exited|refus|Error|GUARD" | tee -a $S
  kc g17-t3$a
  cp $SPO/sp-strata-$L.jsonl $SPO/sp-strata-$L-t3.jsonl
  SP_DIR=$SPO SP_LABEL=$L-t3 STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a-t3.txt 2>&1
  say "  diagnostic, $a, 3-token reference: $($P -I $RU chk2 $SPO/analyze-own-$a-t3.txt --gate chk2diag_p210 --gates $G --info)"
}
essarm() {   # essarm ARM CONFIG TREE REF_ARM GATE_SUFFIX: checks (1) + (2) on the speculative path, 4,000 samples
  local a=$1 cfg=$2 tree=$3 ref=$4 g=$5 L=g17-$1 EL off
  ok_to_go || { say "skipped the speculative path $a (deadline or kernel check)"; return; }
  if [ ! -x "$(exe_of $cfg)" ] || [ ! -f $SPO/sp-strata-logp-g17-$ref.json ]; then say "speculative path $a NOT RUN: no engine or no reference ($ref)"; return; fi
  rm -f $SPO/sp-strata-$L.jsonl
  EL=$(elog $cfg); touch $EL; off=$(stat -c %s $EL)
  bringup/lib/with_server.sh g17-sp$a $cfg -- "$P -I $RU envcheck $(exe_of $cfg) $cfg --pins --gate env_sp$a --gates $G && SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P $WS/bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-$a.txt 2>&1" 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|ready|exited|refus|Error|GUARD" | tee -a $S
  tail -c +$((off + 1)) $EL > $SPO/englog-$a.txt
  say "  start lines $a: exact $(grep -c 'EXACT speculative sampling on' $SPO/englog-$a.txt), cumulative $(grep -c 'cumulative draft length ON' $SPO/englog-$a.txt), lookup-12 $(grep -c 'lookup-max-t 12' $SPO/englog-$a.txt), graph drops $(grep -c 'no VRAM for the' $SPO/englog-$a.txt)"
  fatalchk sp$a $EL $off g17-sp$a
  kc g17-sp$a
  cp $SPO/sp-strata-logp-g17-$ref.json $SPO/sp-strata-logp-$L.json
  SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$tree $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a.txt 2>&1
  say "  check (2), $a (against $ref's 1-token reference): $($P -I $RU chk2 $SPO/analyze-own-$a.txt --gate chk2_$g --gates $G)"
  $P -I work/r22/neartie_compare.py $SPO g17-$ref $L > $SPO/compare-$a.txt 2>&1
  say "  check (1), $a vs $ref: $($P -I $RU chk1 $SPO/compare-$a.txt --gate chk1_$g --gates $G)"
}
contgate() {   # contgate NAME FILES...: the answer_room continuations resume from the session (read <= 64 tokens)
  local n=$1 r h m; shift
  $P work/r22/gap9_verdicts.py cont "$@" > $O/cont-$n.txt 2>&1
  r=$(grep -oE '[0-9]+ hits, [0-9]+ misses' $O/cont-$n.txt | tail -1); h=$(echo "$r" | grep -oE '^[0-9]+'); m=$(echo "$r" | grep -oE '[0-9]+ misses' | grep -oE '[0-9]+')
  if [ -n "$h" ] && [ "$h" -ge 1 ] && [ "${m:-1}" = 0 ]; then gate cont_$n PASS "continuations: $r"; else gate cont_$n FAIL "continuations: ${r:-none found}"; fi
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I $RU decide $O > /dev/null 2>&1; cat $O/decision.txt | tee -a $S
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  work/r22/port_gap4.sh end 2>&1 | tee -a $S
  kc end
  say "gap 17 part $PART done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "GAP 17 part $PART (work/r22/gap17.sh): the v0.2.10 port's gates and pricing - a test, nothing switches (Karl 11-02)"
for f in $H $X $C/P0210x-h-off.json $C/s0210-h.json $C/s028-h.json $C/P0210x-h-nov2.json $C/P0210x-h-L12.json $C/P0210x-h-pf133.json \
         $C/P0210x-h-hcr.json $C/P0210x-h-gdn.json $C/P0210x-h-gdntc.json $C/P0210x-h-gdncv.json $C/P0210x-RTpin-vision.json $C/P0210t-hnospec.json $C/P0210t-hnospec-t3.json \
         $C/P0210t-ess.json $C/P0210t-ess-L12.json $C/s0210t-hnospec.json; do
  [ -f $f ] || { say "missing config $f - not started"; exit 1; }
done
if [ "$(sha12 $E10/strata)" = "$(cut -c1-12 $E10/SHA256)" ] && grep -q "v0.2.10 + 28 commits (branch r22-port0210 $PORT_HEAD" $E10/SOURCE \
   && [ "$(git -C $W10 rev-parse HEAD | cut -c1-9)" = "${PORT_HEAD:0:9}" ]; then
  gate build_x PASS "engine-r22p0210 $(sha12 $E10/strata) = $(cat $E10/SOURCE | cut -c1-80)"
else
  say "engine-r22p0210 is not the build gap 17 was written for (head $PORT_HEAD, 89379c28f361) - not started (G17_PORT_HEAD for a rebuilt port)"; exit 1
fi
$P -I $RU pins $C/P0210x.json --gate pins --gates $G | tee -a $S
$P -I $RU pins $H --gate pins_h --gates $G | tee -a $S
if [ $PART != b ] && [ ! -d $WST ]; then
  say "creating the stock worktree strata-v0210stock (detached at v0.2.10 ffa80d731; as build-stock021.sh did for v0.2.1)"
  git -C strata worktree add --detach $WST v0.2.10 2>&1 | tail -1 | tee -a $S
fi
if [ $PART != a ]; then
  if ! twin_ok $WTW r22-port0210-meas v0.2.10 33 $PORT_HEAD; then
    say "part b needs the port's MEASUREMENT twin: worktree strata-r22p0210m on branch r22-port0210-meas = r22-port0210 ($PORT_HEAD) + the 5 MEASUREMENT commits (the last = STRATA_FORCE_T1), clean - not there"
    [ $PART = b ] && { say "part b not started (no gap opened)"; exit 1; }
    say "part all: part a runs; part b's gates stay missing"
  fi
fi
case $PART in a) MAXM=${G17_MAX_MIN:-260};; b) MAXM=${G17_MAX_MIN:-160};; all) MAXM=${G17_MAX_MIN:-420};; esac

# ================================================================ the gap
work/r22/port_gap4.sh begin "gap 17 part $PART: the v0.2.10 port's gates and pricing (a test; P028x stays served, nothing switches - Karl 11-02)" 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc open

part_a() {
  # ---- A1 builds: the port's tests (its own tree, tests ON) and plain stock v0.2.10 (the release, none of our commits)
  memguard
  if ok_to_go; then
    say "A1 build: the port's tests (strata-r22p0210/build-tests; the served engine-r22p0210 is not rebuilt)"
    if b17 $W10 build-tests ON patch_guard_test cost_gate_test draft_cum_test prefill_fused_iq_test spec_prob_test \
         gated_proposal_test spec_verify_parity spec_proposal_parity; then gate build_tests PASS "strata-r22p0210/build-tests"
    else gate build_tests FAIL "strata-r22p0210/build-tests.log: $(tail -2 $W10/build-tests.log | tr '\n' ' ' | cut -c1-160)"; fi
    kc build-tests
  fi
  if ok_to_go; then
    say "A1 build: stock v0.2.10 (strata-v0210stock -> engine-v0210stock)"
    if [ "$(git -C $WST rev-parse HEAD)" = "$(git -C strata rev-parse 'v0.2.10^{commit}')" ] && [ -z "$(git -C $WST status --porcelain --untracked-files=no)" ] \
       && b17 $WST build OFF strata; then
      mkdir -p $EST && cp $WST/build/strata $EST/strata
      echo "stock v0.2.10 ($(git -C $WST rev-parse HEAD), detached worktree strata-v0210stock), none of our commits, tree $(git -C $WST rev-parse 'HEAD^{tree}')" > $EST/SOURCE
      sha256sum $EST/strata > $EST/SHA256
      gate build_stock PASS "engine-v0210stock $(sha12 $EST/strata)"
    else gate build_stock FAIL "strata-v0210stock/build.log or the worktree is not v0.2.10 clean"; fi
    kc build-stock
  fi
  n8=$(cat $W10/build-configure.log $W10/build-tests-configure.log $WST/build-configure.log 2> /dev/null | grep -c 'windows hold up to 8 rows')
  [ "$n8" = 3 ] && gate build8 PASS "the port, its tests and stock: verify windows hold up to 8 rows" || gate build8 FAIL "$n8 of 3 configure logs say 8 rows"

  # ---- A2 tests
  if ok_to_go && [ -x $W10/build-tests/patch_guard_test ]; then
    say "A2 tests: ours, upstream's sampler tests, the v2 unit test (bit-identical H and down rows)"
    bad=""
    for t in patch_guard_test cost_gate_test draft_cum_test; do
      a=""; [ $t = patch_guard_test ] && a="$GGUF $MTP"
      timeout 900 $P bringup/lib/guard.py g17-$t -- $W10/build-tests/$t $a > $O/$t.txt 2>&1
      rc=$?; [ $rc = 0 ] || bad="$bad $t:rc$rc"
      say "  $t rc $rc: $(grep -v '^\s*$' $O/$t.txt | tail -1 | cut -c1-160)"
    done
    [ -z "$bad" ] && gate tests PASS "patch_guard, cost_gate, draft_cum rc 0" || gate tests FAIL "$bad"
    bad=""
    for t in spec_prob_test gated_proposal_test spec_verify_parity spec_proposal_parity; do
      STRATA_OLD_SAMPLER=0 STRATA_SAMPLER_ONE_BLOCK=0 timeout 900 $P bringup/lib/guard.py g17-$t -- $W10/build-tests/$t > $O/$t.txt 2>&1
      rc=$?; [ $rc = 0 ] || bad="$bad $t:rc$rc"
      say "  $t rc $rc: $(grep -v '^\s*$' $O/$t.txt | tail -1 | cut -c1-160)"
    done
    [ -z "$bad" ] && gate sampler_tests PASS "spec_prob, gated_proposal, spec_verify_parity, spec_proposal_parity rc 0" || gate sampler_tests FAIL "$bad"
    timeout 1800 $P bringup/lib/guard.py g17-v2test -- $W10/build-tests/prefill_fused_iq_test --v2 --no-timing > $O/prefill_fused_v2_test.txt 2>&1
    rc=$?
    say "  prefill_fused_iq_test --v2 rc $rc: $(grep -v '^\s*$' $O/prefill_fused_v2_test.txt | tail -1 | cut -c1-160)"
    [ $rc = 0 ] && gate v2_unit PASS "prefill_fused_iq_test --v2 rc 0" || gate v2_unit FAIL "rc $rc"
    kc tests
  fi
  if ok_to_go; then
    say "A2 server tests (strata-r22p0210/serve, unittest discover) and the four-backtick fence check"
    timeout 1800 $P -m unittest discover -s $W10/serve -t $W10 -p 'test_*.py' > $O/servetests.txt 2>&1
    tail -3 $O/servetests.txt | tee -a $S
    $P -I $RU servetests $O/servetests.txt --gate servetests --gates $G | tee -a $S
    $P -I -B $RU fence4 $W10 --gate fence4 --gates $G | tee -a $S
  fi

  # ---- A3 exact7 at pin 2500: "every switch off = the release" FIRST, then the port against P028x, its repeat, and the
  # bitwise switches against the port; then the lookup pair
  say "A3 exact7 at pin 2500"
  if [ -x $EST/strata ]; then
    e7 g17-s210 $C/s0210-h.json && e7 g17-p210off $C/P0210x-h-off.json g17-s210 && e7g g17-p210off e7_release
  fi
  e7 g17-x28h $X && e7 g17-p210a $H g17-x28h && e7g g17-p210a e7_vs_p028x
  if grep -q 'strata patch guards: 7 checked, 0 off' bringup/out/logs/prof/g17-p210a-x-math.out 2> /dev/null; then
    gate guards PASS "$(grep -m1 -o 'strata patch guards: 7 checked, 0 off[^;]*' bringup/out/logs/prof/g17-p210a-x-math.out)"
  else gate guards FAIL "$(grep -m1 -o 'strata patch guards: [^;]*' bringup/out/logs/prof/g17-p210a-x-math.out 2> /dev/null || echo 'no patch-guard line')"; fi
  e7 g17-p210b $H g17-p210a && e7g g17-p210b e7_repeat
  if [ -n "$(gstat e7_vs_p028x)" ] && [ "$(gstat e7_vs_p028x)" != PASS ] && [ -x $WS/engine-r22s028t/strata ] \
     && [ "$(gstat build_stock)" = PASS ]; then
    say "the port is not exact7-identical to P028x: did upstream itself move (stock 0.2.8 vs stock 0.2.10, both pinned)?"
    e7 g17-s028 $C/s028-h.json g17-s210 && e7g g17-s028 e7_upstream
  fi
  e7 g17-p210nov2 $C/P0210x-h-nov2.json g17-p210a && e7g g17-p210nov2 e7_v2
  e7 g17-pf133 $C/P0210x-h-pf133.json g17-p210a && e7g g17-pf133 e7_pf133
  e7 g17-hcr $C/P0210x-h-hcr.json g17-p210a && e7g g17-hcr e7_hcr
  e7L g17-L0 0 && e7L g17-L12 12 && $P -I $RU e7pair g17-L12 g17-L0 --gate lookup_e7 --gates $G 2>&1 | tee -a $S
  if [ "$(gstat lookup_e7)" = DIFFER ]; then
    say "the greedy items differ with the windows on: the control pair with STRATA_GR_FORK=0 (is it the fork or window shape?)"
    e7L g17-L0f 0 STRATA_GR_FORK=0 && e7L g17-L12f 12 STRATA_GR_FORK=0 \
      && $P -I $RU e7pair g17-L12f g17-L0f --control --gate lookup_e7_ctl --gates $G 2>&1 | tee -a $S
  fi

  # ---- A4 KL: pf_yardstick long40 on the port, the GDN stack and PF_HC_REGION; both forms of the rule (gap 8's refs)
  say "A4 KL: pf_yardstick long40 on P0210x-h, -gdn, -hcr"
  for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
  [ -e $Y/x28h ] || ln -s $Y16/x28h $Y/x28h
  pfy p210 $H; pfy p210gdn $C/P0210x-h-gdn.json; pfy p210hcr $C/P0210x-h-hcr.json
  if [ -f $Y/p210hcr/index.json ] && [ -f $Y/p210/index.json ]; then
    read nd nf <<< "$(ndiff $Y/p210hcr $Y/p210)"
    [ "$nf" -gt 0 ] && [ "$nd" = 0 ] && gate hcr_logits PASS "0 of $nf first-token logit files differ (HC_REGION on vs off, v2 on)" || gate hcr_logits FAIL "$nd of $nf differ"
  fi
  if [ -f $Y/p210/index.json ]; then
    read nd nf <<< "$(ndiff $Y/p210 $Y/x28h)"
    gate logits_vs_p028x INFO "$nd of $nf first-token logit files differ from gap 16's x28h (the same yardstick settings)"
  fi
  klrules p210:p210 p210gdn:gdn
  # Karl 11-03: the GDN paths are gated as ONE stack; split only if the stack fails KL. The stack passes -> each path
  # alone is priced too (speed only, no KL: the cold 16K / 64K prompts + the 9-workload screen), so a path that adds
  # nothing can stay off. The stack fails -> each path is KL-gated alone and priced only if it passes.
  GDNS=""   # the GDN arms priced: G (the stack) only when it passes KL; T / V as above
  if [ "$(gstat kl2_gdn)" = PASS ] && [ "$(gstat kl3_gdn)" = PASS ]; then
    GDNS="G T V"; say "the GDN stack passes both KL rules: GDN_TC alone (T) and GDN_CONVL2 alone (V) are priced too, speed only"
  elif [ -n "$(gstat kl2_gdn)" ] && ok_to_go; then
    say "the GDN stack does not pass KL: each path KL-gated alone (pf_yardstick long40 on -gdntc, -gdncv)"
    pfy p210gdntc $C/P0210x-h-gdntc.json; pfy p210gdncv $C/P0210x-h-gdncv.json
    klrules p210gdntc:gdntc p210gdncv:gdncv
    [ "$(gstat kl2_gdntc)" = PASS ] && [ "$(gstat kl3_gdntc)" = PASS ] && GDNS="T"
    [ "$(gstat kl2_gdncv)" = PASS ] && [ "$(gstat kl3_gdncv)" = PASS ] && GDNS="$GDNS V"
    say "  GDN paths priced alone: ${GDNS:-none}"
  fi
  keep() { local x out=""; for x in $1; do case $x in G|T|V) case " $GDNS " in *" $x "*) out="$out $x";; esac;; *) out="$out $x";; esac; done; echo $out; }

  # ---- A5 the 9-workload screen + the edit-turn workload, 3 passes in turned order: B (x28h = P028x), P (the port),
  # L (lookup windows), F (GR_V3_PF=133), G (the GDN stack, when it passes KL) and T / V (each path alone, when priced; G, T, V without
  # the rewrites); R (PF_HC_REGION) one quick pass
  say "A5 the screen: B P L F ${GDNS:+$GDNS }x 3 passes in turned order, R once"
  for k in 1 2 3; do
    case $k in 1) order=$(keep "B P L F G T V");; 2) order=$(keep "V T G F L R P B");; 3) order=$(keep "P B T G V F L");; esac
    for n in $order; do
      ed=""
      case $n in B) cfg=$X;; P) cfg=$H;; L) cfg=$C/P0210x-h-L12.json;; F) cfg=$C/P0210x-h-pf133.json;; R) cfg=$C/P0210x-h-hcr.json;;
                 G) cfg=$C/P0210x-h-gdn.json; ed=noedit;; T) cfg=$C/P0210x-h-gdntc.json; ed=noedit;; V) cfg=$C/P0210x-h-gdncv.json; ed=noedit;; esac
      darm $n$k $cfg $ed
    done
  done
  labs=$(ls $R/*.jsonl 2> /dev/null | xargs -n1 basename 2> /dev/null | sed 's/\.jsonl$//' | grep -E '^[BPLFRGTV][123][nare]$' | sort | tr '\n' ' ')
  [ -n "$labs" ] && $P $BA/scripts/abreport.py --dir $R $labs > $O/speed-table.md 2>&1
  [ -f $R/P1.startlog ] && $P -I $RU startlines base $R/P1.startlog $R/P1?.englog $(slog g17-P1) --gate startlines_P --gates $G | tee -a $S
  [ -f $R/L1.startlog ] && $P -I $RU startlines lookup $R/L1.startlog $R/L[123]?.englog $(slog g17-L1) $(slog g17-L2) $(slog g17-L3) --gate startlines_L --gates $G | tee -a $S
  ls $R/P[123][nre].englog > /dev/null 2>&1 && contgate P $R/P[123][nre].englog
  ls $R/L[123][nre].englog > /dev/null 2>&1 && contgate L $R/L[123][nre].englog

  # ---- A6 Basalt's community-1 fixtures, cold (a fresh engine per measurement), 3 passes: M = x28h, H = the port
  # (decode, 16K, 64K); G = the GDN stack (when it passes KL), T / V = each path alone when priced (16K, 64K: their price)
  say "A6 Basalt's fixtures, cold, 3 passes: M (x28h) and H (P0210x-h) decode / pp16k / pp64k${GDNS:+; $GDNS pp16k / pp64k}"
  for k in 1 2 3; do
    case $k in 1) order=$(keep "M H G T V");; 2) order=$(keep "V T G H M");; 3) order=$(keep "H M T V G");; esac
    for b in $order; do
      case $b in G|T|V) sets="pp16k pp64k";; *) sets="decode pp16k pp64k";; esac
      for set in $sets; do bprun $b $set $k; done
    done
  done
  BP90_NAME_H="v0.2.10 port, pinned (P0210x-h)" $P -I $B90/bp90_report.py $BO > $BO/report.md 2>&1 || true
  sed -i 's/P021m (served)/P028x (x28h)/g' $BO/report.md 2> /dev/null
  for x in G:"GDN_TC + GDN_CONVL2 (P0210x-h-gdn)" T:"GDN_TC alone (P0210x-h-gdntc)" V:"GDN_CONVL2 alone (P0210x-h-gdncv)"; do
    a=${x%%:*}; [ -s $BO/cold-$a.jsonl ] || continue
    d=$O/bp90-gdn-$a; mkdir -p $d; ln -sfn ../bp90/cold-H.jsonl $d/cold-M.jsonl; ln -sfn ../bp90/cold-$a.jsonl $d/cold-H.jsonl
    BP90_NAME_H="${x#*:}" $P -I $B90/bp90_report.py $d > $d/report.md 2>&1 || true
    sed -i 's/P021m (served)/v0.2.10 port, pinned (P0210x-h)/g' $d/report.md 2> /dev/null
  done

  # ---- A7 the served form (chat cache resumed = fresh, chat_drop, a picture) and the live tool-call test, B vs P
  if ok_to_go; then
    say "A7 the served form on P0210x-RTpin-vision: chat-cache checks + a picture"
    IMG=$W10/docs/terminal-previews/serving-110-stages.png; RT=$C/P0210x-RTpin-vision.json; L=$(elog $RT); touch $L; off=$(stat -c %s $L)
    bringup/lib/with_server.sh g17-rt $RT -- "$P -I $RU envcheck $(exe_of $RT) $RT --pins --gate env_rt --gates $G && { $P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG > $O/chatcache.txt 2>&1; $P work/r22/vision_check.py http://127.0.0.1:8081 $IMG $O/picture > $O/vision.txt 2>&1; }" 2>&1 \
      | grep -E "engine pid [0-9]+:|ENV CHECK|ready|exited|refus|Error|GUARD" | tee -a $S
    fatalchk rt $L $off g17-rt
    kc served
    grep -E "^(PASS|FAIL)|ALL PASS|FAILED" $O/chatcache.txt 2> /dev/null | tee -a $S
    grep -q "ALL PASS" $O/chatcache.txt 2> /dev/null && gate chatcache PASS "ALL PASS" || gate chatcache FAIL "$(grep -c '^FAIL' $O/chatcache.txt 2> /dev/null) FAIL lines"
    nv=$(grep -c '"answer_chars": [1-9]' $O/vision.txt 2> /dev/null)
    [ "$nv" = 2 ] && gate vision PASS "2 answers (read by hand afterwards: picture-1.txt, picture-2.txt)" || gate vision FAIL "${nv:-0} of 2 answers"
  fi
  if ok_to_go; then
    say "A7 the live tool-call test (work/r22/toolrecovery, 27 prompts x 2, the same seeds): B (x28h) vs P (P0210x-h), recovery off"
    for a in B P; do
      case $a in B) cfg=$X; pf="";; P) cfg=$H; pf=--pins;; esac
      ok_to_go || break
      L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
      bringup/lib/with_server.sh g17-tc$a $cfg -- "$P -I $RU envcheck $(exe_of $cfg) $cfg $pf --gate env_tc$a --gates $G && $P -B $T/toolrecovery_live.py http://127.0.0.1:8081 --label g17-$a --reps 2 --out-dir $O/toolcalls/$a" 2>&1 \
        | grep -E "engine pid [0-9]+:|ENV CHECK|TOTAL|ready|exited|refus|Error|GUARD" | tee -a $S
      fatalchk tc$a $L $off g17-tc$a
      kc g17-tc$a
    done
    MJ=$(ls -t $O/toolcalls/B/live-g17-B-*.jsonl 2> /dev/null | head -1); XJ=$(ls -t $O/toolcalls/P/live-g17-P-*.jsonl 2> /dev/null | head -1)
    if [ -n "$MJ" ] && [ -n "$XJ" ]; then $P -I $RU toolcalls $MJ $XJ --gate toolcalls --gates $G 2>&1 | tee $O/toolcalls/compare.txt | tee -a $S
    else gate toolcalls FAIL "a result file is missing"; fi
  fi

  # ---- A8 lossless (the config + the port's engine log of this gap)
  CFG=$H TREE=strata-r22p0210 ELOG=$(elog $H) bringup/patchtest.sh lossless 2>&1 | grep -E "PASS|FAIL" | tail -6 | tee $O/lossless.txt | tee -a $S
  grep -q 'cfg: PASS' $O/lossless.txt && ! grep -q FAIL $O/lossless.txt && gate lossless PASS "cfg + log clean" || gate lossless FAIL "$(tail -1 $O/lossless.txt | cut -c1-140)"
}

part_b() {
  # ---- B1 the MEASUREMENT twins (check (2)'s 1-token-window reference needs the force=N hooks and STRATA_FORCE_T1)
  memguard
  if ok_to_go && twin_ok $WTW r22-port0210-meas v0.2.10 33 $PORT_HEAD; then
    say "B1 build: the port's MEASUREMENT twin (strata-r22p0210m -> engine-r22p0210m)"
    if b17 $WTW build-twin OFF strata && grep -q 'windows hold up to 8 rows' $WTW/build-twin-configure.log; then
      mkdir -p $ETW && cp $WTW/build-twin/strata $ETW/strata
      echo "twin: v0.2.10 + $(git -C $WTW rev-list --count v0.2.10..HEAD) commits (branch r22-port0210-meas $(git -C $WTW rev-parse HEAD)), tree $(git -C $WTW rev-parse 'HEAD^{tree}')" > $ETW/SOURCE
      sha256sum $ETW/strata > $ETW/SHA256
      gate build_twin PASS "engine-r22p0210m $(sha12 $ETW/strata), 8-row windows"
    else gate build_twin FAIL "strata-r22p0210m/build-twin.log"; fi
    kc build-twin
  else
    say "B1: no port twin (branch r22-port0210-meas missing or not as expected) - part b's gates stay missing"
  fi
  if ok_to_go && twin_ok $WSTW r22-stock0210-meas v0.2.10 5; then
    say "B1 build: stock v0.2.10's MEASUREMENT twin (strata-r22s0210t -> engine-r22s0210t; reported, not judged)"
    if b17 $WSTW build-twin OFF strata; then
      mkdir -p $ESTW && cp $WSTW/build-twin/strata $ESTW/strata
      echo "twin: v0.2.10 + $(git -C $WSTW rev-list --count v0.2.10..HEAD) commits (branch r22-stock0210-meas $(git -C $WSTW rev-parse HEAD))" > $ESTW/SOURCE
      sha256sum $ESTW/strata > $ESTW/SHA256
      gate build_stwin INFO "engine-r22s0210t $(sha12 $ESTW/strata)"
    else gate build_stwin INFO "build failed: strata-r22s0210t/build-twin.log"; fi
    kc build-stwin
  else
    say "B1: no stock twin (branch r22-stock0210-meas) - its check (2) is skipped (it is reported only)"
  fi
  cp -n results/r20/sp-batch/sp-cases.json results/r20/sp-batch/sp-llama.json $SPO/ 2> /dev/null

  # ---- B2 check (2), speculation off, 1-token reference: the port (+ the 3-token diagnostic), stock v0.2.10 (reported)
  say "B2 check (2): arith-j3 T 0.6, 4,000, speculation off, against the build's own probabilities in 1-token windows"
  [ -x $ETW/strata ] && [ "$(gstat build_twin)" = PASS ] && chk2arm hnospec $C/P0210t-hnospec.json $C/P0210t-hnospec-t3.json $WTW chk2_p210
  [ -x $ESTW/strata ] && chk2arm s210t $C/s0210t-hnospec.json - $WSTW chk2_s210 --info

  # ---- B3 checks (1) + (2) on the speculative path: lookup windows pinned off (the baseline), then on (gate 1)
  say "B3 checks (1) + (2) on the speculative path, 4,000 each: P0210t-ess (windows off), P0210t-ess-L12 (up to 12)"
  if [ -x $ETW/strata ] && [ "$(gstat build_twin)" = PASS ]; then
    essarm ess $C/P0210t-ess.json $WTW hnospec p210_ess
    essarm essL $C/P0210t-ess-L12.json $WTW hnospec p210_essL
  fi
}

case $PART in
  a) part_a;;
  b) part_b;;
  all) part_a; part_b;;
esac
end_gap
