#!/bin/bash
# gap-nll.sh - round 23 item 6 (Karl 11-04, queued first of three between the remaining 7d questions): the NLL check at
# many positions (results/r23/nll-many/PLAN.md section 5; tool work/r23/nll-many/score.py). WRITTEN 11-04, NOT RUN.
# Measurements only: P028x stays served, nothing switches, nothing is built. Run: `bash work/r23/gap-nll.sh` (no args).
#   0 before the gap (no GPU, 8080 untouched): refuse if tmp/gpu-test.lock is held or a model server other than the 8080
#     queue's P028x runs; configs, engines (SHA), prompt files, kernel watcher, disk; an earlier attempt moved to prev-*
#   1 port_gap4.sh begin (the queue's running question finishes, test lock, 8080 down)
#   2 arm ref (P021n) -> score.py validate at once: the offline head against the engine's own window rows. DOES NOT
#     AGREE -> no further arm, the gap ends, nothing is judged (Karl: the bound is adopted only once validated)
#   3 arms ref2, unfused, cpushare, v2, x28h, x28h-nov2, r28h (~6 min each); optional x28h-unfused, x28h-cpushare (P028x's
#     own rounding references, +12 min) only if each fits before the deadline (NLL_MAX_MIN, default 75 min after the gap
#     opens); every engine's environment checked as it starts (nll_rules.py envwatch); a kernel check after every arm
#   4 byte identity ref2 = ref, x28h-nov2 = x28h; port_gap4.sh end (P028x back) + a kernel check
#   5 after the gap (CPU only, nice 19): validate on the other arms, score.py compare (~10 min on NLL_THREADS=4), the
#     stride re-analyses, the P028x-reference compare (with the optional arms), nll_rules.py decide -> decision.txt
# A kernel-check failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done (the
# outcome is in decision.txt), 1 = refused / not opened (8080 untouched), 4 = port_gap4.sh end failed.
# Output: results/r23/nll-many/gap/ (summary.txt, gates.txt, <arm>/, decision.txt ...). Steps: work/r23/GAPS-README.md.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
P=$WS/.venv/bin/python; C=$WS/configs; KR=$WS/work/r22
SCORE=$WS/work/r23/nll-many/score.py; RU=$WS/work/r23/nll_rules.py
O=$WS/results/r23/nll-many/gap; G=$O/gates.txt
S=$WS/results/r23/nll-many/gap-nll-starts.log    # until the pre-gap checks pass (then $O/summary.txt)
P028X_SHA=f4c4f654fb24             # engine-r22p028x/strata, served on 8080 since 10-30
MAXM=${NLL_MAX_MIN:-75}; ARM_MIN=7; NT=${NLL_THREADS:-4}
REF_CFG=$C/r21n1.json; UNF_CFG=$C/r21n1-unfused.json; V2_CFG=$C/r21n1-v2.json; X_CFG=$C/x28h.json
XN_CFG=$C/x28h-nov2.json; R28_CFG=$C/r28h.json
mkdir -p $O $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [nll $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
KFAIL=0; VFAIL=0; T0=$(date +%s); DEADLINE=$T0
kc() { $WS/bringup/lib/kcheck.sh "r23nll-$1" > /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $VFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # an optional step starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }

preflight() {   # refuse (exit 1, nothing touched) when a measurement holds the GPU lock or a model server other than the
  # 8080 queue's P028x runs: every engine process (exact names) and every NVIDIA compute process must belong to the server
  # listening on 8080, and that server's engine must be P028x (engine-r22p028x, sha $P028X_SHA; its vision helper allowed)
  local l p q apps bad=""
  if [ -s $WS/tmp/port-gap.lockpid ] && kill -0 "$(cat $WS/tmp/port-gap.lockpid)" 2> /dev/null; then
    say "another gap holds the test lock (tmp/port-gap.lockpid $(cat $WS/tmp/port-gap.lockpid)) - not started"; exit 1
  fi
  if ! flock -n -x $WS/tmp/gpu-test.lock true 2> /dev/null; then
    say "tmp/gpu-test.lock is held (a measurement or a test server) - not started"; exit 1
  fi
  l=$(ss -H -ltnp "( sport = :8080 )" 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2> /dev/null) || { say "nvidia-smi did not answer - not started"; exit 1; }
  for p in $( { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x "$x"; done; echo "$apps"; } \
              | tr -d ' ' | grep -E '^[0-9]+$' | sort -un); do
    q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != "${l:-none}" ]; do q=$(ppid_of $q); done
    if [ -n "$l" ] && [ "$q" = "$l" ]; then
      case $(cat /proc/$p/comm 2> /dev/null) in
        strata|strata-host) [ "$(sha12 /proc/$p/exe 2> /dev/null)" = $P028X_SHA ] || bad="$bad 8080-engine:$p($(readlink /proc/$p/exe))";;
        strata-vision) ;;
        *) bad="$bad 8080:$p($(cat /proc/$p/comm 2> /dev/null))";;
      esac
    else bad="$bad $p($(cat /proc/$p/comm 2> /dev/null))"; fi
  done
  ss -H -ltn "( sport = :8081 )" 2> /dev/null | grep -q . && bad="$bad listener-on-8081(a-test-server)"
  [ -z "$bad" ] || { say "a model server other than the 8080 queue's P028x is running:$bad - not started"; exit 1; }
}

arm() {   # arm NAME CONFIG [K=V ...] [--optional]: one cold read of the 11 long texts, every 8th prompt row kept (score.py
  # run, pf_yardstick's settings), the engine's environment checked as it starts; a kernel check after it
  local n=$1 cfg=$2 opt=0 e envs="" jp rc; shift 2
  for e in "$@"; do case $e in --optional) opt=1;; *) envs="$envs --env $e";; esac; done
  if [ $opt = 1 ]; then fits $ARM_MIN || { say "skipped optional arm $n ($ARM_MIN min do not fit before the deadline, or a stop)"; return 1; }
  else ok_to_go || { say "skipped arm $n (deadline, validation or kernel check)"; return 1; }; fi
  say "arm $n ($(basename $cfg)${envs:+;$envs})"
  rm -f $O/$n.rc
  ( $P $WS/bringup/lib/guard.py nll23-$n -- $P -I $SCORE run $cfg $O/$n --set long11 --rows all:8 $envs > $O/$n.run.txt 2>&1
    echo $? > $O/$n.rc ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envwatch $jp $cfg $envs --kill --gate env_$n --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  rc=$(cat $O/$n.rc 2> /dev/null || echo none)
  grep -E "tokens, [0-9]+ rows|rows from [0-9]+ texts|^PROBLEM" $O/$n.run.txt | tail -14 | sed "s/^/  $n: /" | tee -a $S
  if [ "$rc" = 0 ] && [ -f $O/$n/index.json ]; then
    gate run_$n PASS "score.py run rc 0: $(grep -E 'rows from [0-9]+ texts' $O/$n.run.txt | tail -1)"
  else
    gate run_$n FAIL "rc $rc: $(grep -E '^PROBLEM|SystemExit|Error|answered|ended before' $O/$n.run.txt | head -3 | tr '\n' ' ' | cut -c1-250)"
  fi
  kc nll-$n
}
validate() {   # validate NAME: score.py validate (CPU, ~20 s): the engine's window rows at the 5 check prompts vs the
  # offline head on the full read's rows -> gate validate_NAME (PASS = AGREES)
  local n=$1 rc line
  if [ "$(gstat run_$n)" != PASS ] || [ "$(gstat env_$n)" != PASS ]; then gate validate_$n FAIL "arm $n did not run cleanly"; return 1; fi
  nice -n 19 $P -I $SCORE validate $O/$n > $O/validate-$n.txt 2>&1; rc=$?
  line=$(grep -E "offline head (AGREES|DOES NOT AGREE)" $O/validate-$n.txt | tail -1 | cut -c1-200)
  grep -E "KL\(window" $O/validate-$n.txt | sed "s/^/  validate $n: /" | tee -a $S
  if [ $rc = 0 ] && echo "$line" | grep -q "head AGREES"; then gate validate_$n PASS "$line"; return 0; fi
  gate validate_$n FAIL "rc $rc: ${line:-$(tail -1 $O/validate-$n.txt | cut -c1-200)}"; return 1
}
ok_arm() { [ "$(gstat run_$1)" = PASS ] && [ "$(gstat env_$1)" = PASS ]; }
wait_mem() {   # after 8080 stops: its engines gone and their memory back (score.py run needs 16 GB free), at most 120 s
  local i x left_p m
  for i in $(seq 60); do
    left_p=""; for x in strata strata-host strata-vision strata-dsv41; do pgrep -x $x > /dev/null && left_p="$left_p $x"; done
    m=$(awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo)
    [ -z "$left_p" ] && [ "$m" -ge 40 ] && break
    sleep 2
  done
  say "8080 down: engines left:${left_p:- none}, MemAvailable ${m} GB"
}

after_gap() {   # CPU only, nice 19, 8080 back: validation of the other arms, compare, strides, the P028x reference, decide
  local x cands="" cx="" rc
  say "after the gap (CPU, nice 19, $NT BLAS threads): validate the other arms, compare, decide"
  for x in ref2 unfused cpushare v2 x28h x28h-nov2 r28h x28h-unfused x28h-cpushare; do
    [ -f $O/$x/index.json ] && validate $x
  done
  if [ "$(gstat validate_ref)" = PASS ] && ok_arm ref && ok_arm unfused && ok_arm cpushare; then
    for x in ref2 v2 x28h x28h-nov2 r28h; do ok_arm $x && cands="$cands,$x"; done
    rm -f $O/result.json $O/result-s2.json $O/result-s8.json $O/result-x28h.json $O/rows.tsv
    say "compare: ref / unfused, cpushare / ${cands#,} (~31K positions each)"
    nice -n 19 $P -I $SCORE --threads $NT compare $O --ref ref --refs unfused,cpushare --cands ${cands#,} \
      --block-scan 1024,2048,4096,8192,text --rows-out $O/rows.tsv --json $O/result.json > $O/compare.txt 2>&1
    rc=$?
    grep -vE "^\s*$" $O/compare.txt | tail -22 | tee -a $S
    if [ -s $O/result.json ]; then gate compare PASS "rc $rc (1 = a candidate fails the proposed rule): result.json, rows.tsv"
    else gate compare FAIL "rc $rc, no result.json: $(tail -2 $O/compare.txt | tr '\n' ' ' | cut -c1-200)"; fi
    if [ -s $O/rows.tsv ]; then
      for x in 2 8; do   # every 16th / every 64th row: what N buys, from the gap's own data
        nice -n 19 $P -I $SCORE compare $O --from-rows $O/rows.tsv --stride $x --ref ref --refs unfused,cpushare \
          --cands ${cands#,} --json $O/result-s$x.json > $O/compare-s$x.txt 2>&1
      done
    fi
    if ok_arm x28h && ok_arm x28h-unfused && ok_arm x28h-cpushare; then
      for x in x28h-nov2 r28h; do ok_arm $x && cx="$cx,$x"; done
      if [ -n "$cx" ]; then
        say "compare with P028x as the reference (INFO): x28h / x28h-unfused, x28h-cpushare / ${cx#,}"
        nice -n 19 $P -I $SCORE --threads $NT compare $O --ref x28h --refs x28h-unfused,x28h-cpushare --cands ${cx#,} \
          --block-scan 2048,text --json $O/result-x28h.json > $O/compare-x28h.txt 2>&1
        [ -s $O/result-x28h.json ] && gate compare_x28h INFO "result-x28h.json" || gate compare_x28h INFO "failed: $(tail -1 $O/compare-x28h.txt | cut -c1-160)"
      fi
    fi
  else
    say "not compared: the ref arm did not validate, or ref / a rounding reference did not run cleanly"
  fi
  $P -I -B $RU decide $O > /dev/null 2>&1
  [ -f $O/decision.txt ] && tee -a $S < $O/decision.txt || say "nll_rules.py decide failed - rerun it by hand ($RU decide $O)"
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  [ -f $O/ref2/index.json ] && [ -f $O/ref/index.json ] && $P -I -B $RU ident $O/ref2 $O/ref --gate ident_ref2 --gates $G | tee -a $S
  [ -f $O/x28h-nov2/index.json ] && [ -f $O/x28h/index.json ] && $P -I -B $RU ident $O/x28h-nov2 $O/x28h --gate ident_nov2 --gates $G | tee -a $S
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "NLL gap: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  after_gap
  say "NLL gap done"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-nll.sh (pre-gap checks)"
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
PREV=""
if [ -e $G ] || [ -e $O/decision.txt ] || ls -d $O/ref > /dev/null 2>&1; then   # the rules judge only this attempt's files
  PREV=$WS/results/r23/nll-many/prev-$(date +%m%d-%H%M%S); mv $O $PREV; mkdir -p $O
fi
S=$O/summary.txt
say "NLL MANY-POSITIONS GAP (work/r23/gap-nll.sh): PLAN.md section 5 - measurements only, P028x stays served, nothing switches (Karl 11-04)"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
for f in $REF_CFG $UNF_CFG $V2_CFG $X_CFG $XN_CFG $R28_CFG $SCORE $RU $KR/pf_yardstick.py $KR/port_gap4.sh $WS/bringup/lib/guard.py \
         $WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
for f in 32k.tokens tf-long28k.prompt tf-long40k.prompt tf-long64k.prompt tf-long112k.prompt pp4k.tokens ldrsyn20k.tokens \
         rep9k.tokens pp32k.tokens tf-long96k.prompt pp8k.tokens; do
  [ -s $WS/bringup/out/r20a/prompts/$f ] || { say "missing prompt file $f (score.py's long11 set) - not started"; exit 1; }
done
bad=""; eng=""
for e in engine-r22p021n engine-r22p028x engine-r22p028; do
  [ -x $WS/$e/strata ] || { bad="$bad $e:missing"; continue; }
  h=$(sha12 $WS/$e/strata); eng="$eng $e=$h"
  [ "$h" = "$(cut -c1-12 $WS/$e/SHA256 2> /dev/null)" ] || bad="$bad $e:sha-not-its-SHA256-file"
done
[ "$(sha12 $WS/engine-r22p028x/strata 2> /dev/null)" = $P028X_SHA ] || bad="$bad engine-r22p028x:not-P028x"
[ -z "$bad" ] || { say "engines not as recorded:$bad - not started"; exit 1; }
gate engines PASS "$eng (the past cases' binaries; nothing is built)"
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 20 ] || { say "only ${free} GB free on results/ (the arms keep ~0.7 GB each) - not started"; exit 1; }

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 NLL many-positions gap (item 6: score.py, 8 arms + 2 optional; measurements only, P028x stays served, nothing switches - Karl 11-04)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

say "1 arm ref (P021n, configs/r21n1.json) and the validation of the offline head (score.py validate)"
arm ref $REF_CFG
if ! validate ref; then
  VFAIL=1
  say "the offline head does NOT agree with the engine's own output on ref (or ref did not run): no further arm, nothing is judged (Karl 11-04: the bound is adopted only once validated)"
  end_gap
fi
say "2 the references and candidates ($(( $(left) / 60 )) min to the deadline)"
arm ref2 $REF_CFG
arm unfused $UNF_CFG
arm cpushare $REF_CFG STRATA_PREFILL_CPU_SHARE=0.4
arm v2 $V2_CFG
arm x28h $X_CFG
arm x28h-nov2 $XN_CFG
arm r28h $R28_CFG
say "3 optional: P028x's own rounding references, each only if it fits ($(( $(left) / 60 )) min to the deadline)"
arm x28h-unfused $X_CFG STRATA_PF_FUSED=0 --optional
arm x28h-cpushare $X_CFG STRATA_PREFILL_CPU_SHARE=0.4 --optional
end_gap
