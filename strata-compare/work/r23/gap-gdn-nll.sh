#!/bin/bash
# gap-gdn-nll.sh - r23 (Karl 11-04: "If tonight's NLL gap validates the many-positions scorer, add a stock on-vs-off arm
# with it (~6 min each)."). Stock Strata v0.2.10's two GDN prompt paths OFF vs ON (STRATA_GDN_TC=1 + STRATA_GDN_CONVL2=2,
# what stock serve/server.py's gdn_stack_env sets on Linux / CUDA / Qwen3.8), scored with the NLL many-positions scorer
# (work/r23/nll-many/score.py: ~31K positions instead of gap 19's 36), so Karl's upstream issue about these paths does
# not rest on the 36-position check. WRITTEN 11-04, NOT RUN. The step after gap-nll.sh in work/r23/gap-series.sh (`bash
# <driver>`, no arguments; every path absolute). Measurements only: P028x stays served, NOTHING SWITCHES, nothing built.
# Rules (written before any run): work/r23/gdn_nll_rules.py (its docstring is the rule text).
#   0 before the gap (no GPU, 8080 untouched) - REFUSES (exit 1) unless: the NLL gap validated the scorer (its
#     decision.json JUDGED + validate_ref PASS + ADOPTED-BOUND.json + a band source), the two stock configs differ only in
#     the GDN pair (= stock server.py's GDN_STACK_CUDA), score.py's head is the stock build's (the same GGUF and pack,
#     the pack's output_hc_* bytes = the GGUF's), engine-v0210stock = c8fe72abe45a; no gpu-test.lock / other gap /
#     model server other than the 8080 queue's P028x / 8081 listener; the kernel watcher; prompt files; >= 20 GB free
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down)
#   2 arms s210 (configs/s0210-h.json: both paths off) and s210gdn (configs/s0210-h-gdn.json: TC=1 + CONVL2=2):
#     score.py run --set long11 --rows all:8 (~6 min each), each engine's environment checked as it starts
#     (nll_rules.py envwatch), a watchdog (3 x 7 min), a kernel check after each. s210 not clean -> no further arm
#   3 optional, only if 14 min fit before the deadline (GDN_NLL_MAX_MIN, default 35 min after the gap opens): the stock
#     build's own rounding pair s210unf (+ STRATA_PF_FUSED=0) and s210cpu (+ STRATA_PREFILL_CPU_SHARE=0.4), so the band
#     is the stock build's own; else the band is borrowed from the NLL gap (P028x's own pair if it ran, else P021n's)
#   4 port_gap4.sh end (P028x back) + a kernel check
#   5 after the gap (CPU only, nice 19, GDN_NLL_THREADS=4, MemAvailable >= 20 GB): score.py validate on every arm
#     (validate_s210 PASS = score.py's head applies to the stock build), gdn_nll_rules.py compare (s210gdn vs s210 with
#     the adopted bound's statistics), decide -> results/r23/gdn-nll/decision.txt
# A kernel-check failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done (the
# outcome is in decision.txt), 1 = refused / not opened (8080 untouched), 3 = kernel check failed, 4 = port_gap4.sh end
# failed. Output: results/r23/gdn-nll/ (decision.txt / .json, pre-checks.txt) and results/r23/gdn-nll/gap/ (summary.txt,
# gates.txt, <arm>/, validate-*.txt, compare.txt, result.json, rows.tsv). Steps: work/r23/GAPS-README.md, section 1b.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
P=$WS/.venv/bin/python; C=$WS/configs; KR=$WS/work/r22; LIB=$WS/bringup/lib
SCORE=$WS/work/r23/nll-many/score.py; RU=$WS/work/r23/gdn_nll_rules.py; NR=$WS/work/r23/nll_rules.py
R=$WS/results/r23/gdn-nll; O=$R/gap; G=$O/gates.txt; NLL_ROOT=$WS/results/r23/nll-many/gap
S=$R/gap-gdn-nll-starts.log      # until the pre-gap checks pass (then $O/summary.txt)
EST=$WS/engine-v0210stock; STOCK_SHA=c8fe72abe45a; P028X_SHA=f4c4f654fb24   # P028x: engine-r22p028x, served on 8080
H0=$C/s0210-h.json; HG=$C/s0210-h-gdn.json
GGUF=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
MAXM=${GDN_NLL_MAX_MIN:-35}; ARM_MIN=7; NT=${GDN_NLL_THREADS:-4}; MEM_GB=20
mkdir -p $R $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [gdn $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
KFAIL=0; T0=$(date +%s); DEADLINE=$T0
kc() { $LIB/kcheck.sh "r23gdn-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; echo "kfail FAIL after $1" >> $G; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # an optional step starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
memavail() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }
ok_arm() { [ "$(gstat run_$1)" = PASS ] && [ "$(gstat env_$1)" = PASS ]; }

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
wait_mem() {   # after 8080 stops: its engines gone and their memory back (score.py run needs 16 GB free), at most 120 s
  local i x left_p m
  for i in $(seq 60); do
    left_p=""; for x in strata strata-host strata-vision strata-dsv41; do pgrep -x $x > /dev/null && left_p="$left_p $x"; done
    m=$(memavail)
    [ -z "$left_p" ] && [ "$m" -ge 40 ] && break
    sleep 2
  done
  say "8080 down: engines left:${left_p:- none}, MemAvailable ${m} GB"
}
watchdog() {   # watchdog JOB MINUTES NAME: an arm past MINUTES is hung - stop the engine in the job's own process tree by
  # its PID (guard.py does not pass a TERM on to its child's session); score.py then ends with a non-zero exit
  local j=$1 m=$2 n=$3 t p q
  t=$(( $(date +%s) + m * 60 ))
  while kill -0 $j 2> /dev/null; do
    if [ $(date +%s) -ge $t ]; then
      for p in $( { pgrep -x strata; pgrep -x strata-host; } | sort -un); do
        q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != $j ]; do q=$(ppid_of $q); done
        [ "$q" = $j ] && kill -TERM $p 2> /dev/null && echo "watchdog: $n ran past $m min - its engine (pid $p) was stopped" >> $O/$n.watchdog
      done
      return 0
    fi
    sleep 5
  done
}

arm() {   # arm NAME CONFIG [K=V ...] [--optional]: one cold read of the 11 long texts, every 8th prompt row kept (score.py
  # run, the NLL gap's settings), the engine's environment checked as it starts; a kernel check after it
  local n=$1 cfg=$2 opt=0 e envs="" jp wd rc; shift 2
  for e in "$@"; do case $e in --optional) opt=1;; *) envs="$envs --env $e";; esac; done
  if [ $opt = 1 ]; then fits $ARM_MIN || { say "skipped optional arm $n ($ARM_MIN min do not fit before the deadline, or a stop)"; return 1; }
  else ok_to_go || { say "skipped arm $n (deadline or kernel check)"; return 1; }; fi
  say "arm $n ($(basename $cfg)${envs:+;$envs})"
  rm -f $O/$n.rc $O/$n.watchdog
  ( $P $LIB/guard.py gdn23-$n -- $P -I $SCORE run $cfg $O/$n --set long11 --rows all:8 $envs > $O/$n.run.txt 2>&1
    echo $? > $O/$n.rc ) 8>&- 9>&- &
  jp=$!
  watchdog $jp $(( 3 * ARM_MIN )) $n 8>&- 9>&- &
  wd=$!
  $P -I -B $NR envwatch $jp $cfg $envs --kill --gate env_$n --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  kill $wd 2> /dev/null; wait $wd 2> /dev/null
  [ -f $O/$n.watchdog ] && say "  $(cat $O/$n.watchdog)"
  rc=$(cat $O/$n.rc 2> /dev/null || echo none)
  grep -E "tokens, [0-9]+ rows|rows from [0-9]+ texts|^PROBLEM" $O/$n.run.txt | tail -14 | sed "s/^/  $n: /" | tee -a $S
  if [ "$rc" = 0 ] && [ -f $O/$n/index.json ]; then
    gate run_$n PASS "score.py run rc 0: $(grep -E 'rows from [0-9]+ texts' $O/$n.run.txt | tail -1)"
  else
    gate run_$n FAIL "rc $rc: $(grep -E '^PROBLEM|SystemExit|Error|answered|ended before|GUARD' $O/$n.run.txt | head -3 | tr '\n' ' ' | cut -c1-250)"
  fi
  kc arm-$n
}
validate() {   # validate NAME: score.py validate (CPU, ~35 s with the head's load): the engine's window rows at the 5 check
  # prompts vs score.py's offline head on the full read's rows -> gate validate_NAME (PASS = AGREES)
  local n=$1 rc line
  if ! ok_arm $n; then gate validate_$n FAIL "arm $n did not run cleanly"; return 1; fi
  nice -n 19 $P -I $SCORE validate $O/$n > $O/validate-$n.txt 2>&1; rc=$?
  line=$(grep -E "offline head (AGREES|DOES NOT AGREE)" $O/validate-$n.txt | tail -1 | cut -c1-200)
  grep -E "KL\(window" $O/validate-$n.txt | sed "s/^/  validate $n: /" | tee -a $S
  if [ $rc = 0 ] && echo "$line" | grep -q "head AGREES"; then gate validate_$n PASS "$line"; return 0; fi
  gate validate_$n FAIL "rc $rc: ${line:-$(tail -1 $O/validate-$n.txt | cut -c1-200)}"; return 1
}
decide() {
  $P -I -B $RU decide $O --nll-root $NLL_ROOT --out $R > /dev/null 2>&1 8>&- 9>&- || true
  [ -f $R/decision.txt ] && tee -a $S < $R/decision.txt > /dev/null || say "gdn_nll_rules.py decide failed - rerun it by hand ($RU decide $O --out $R)"
}
after_gap() {   # CPU only, nice 19, 8080 back: validation, compare, decide
  local i x rc
  say "after the gap (CPU, nice 19, $NT BLAS threads): validate, compare, decide"
  for i in $(seq 60); do [ "$(memavail)" -ge $MEM_GB ] && break; sleep 10; done   # one offline head (~3.5 GB) above the 12 GB floor
  if [ "$(memavail)" -lt $MEM_GB ]; then
    say "MemAvailable $(memavail) GB < $MEM_GB after 10 min: validate / compare NOT run - by hand later (score.py validate $O/<arm>; $RU compare $O --threads $NT --json $O/result.json --rows-out $O/rows.tsv --gate compare --gates $G)"
    decide; return
  fi
  for x in s210 s210gdn s210unf s210cpu; do [ -f $O/$x/index.json ] && validate $x; done
  if [ "$(gstat validate_s210)" = PASS ] && ok_arm s210 && ok_arm s210gdn; then
    rm -f $O/result.json $O/rows.tsv
    say "compare: s210gdn (+ the stock pair where it ran) against s210, the adopted bound's statistics (~31K positions)"
    nice -n 19 $P -I -B $RU compare $O --nll-root $NLL_ROOT --threads $NT --json $O/result.json --rows-out $O/rows.tsv \
      --gate compare --gates $G > $O/compare.txt 2>&1 8>&- 9>&-
    rc=$?
    [ $rc = 0 ] || [ "$(gstat compare)" = FAIL ] || gate compare FAIL "rc $rc: $(tail -2 $O/compare.txt | tr '\n' ' ' | cut -c1-200)"
    grep -vE "^\s*$" $O/compare.txt | tail -12 | tee -a $S
  else
    say "not compared: s210 did not validate (score.py's head on the stock build), or s210 / s210gdn did not run cleanly"
  fi
  decide
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; decide; exit 3; fi
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; decide; exit 3; }
  say "GDN NLL gap: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  after_gap
  say "GDN NLL gap done"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-gdn-nll.sh (pre-gap checks)"
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
for f in $H0 $HG $SCORE $RU $NR $KR/pf_yardstick.py $KR/port_gap4.sh $LIB/guard.py $LIB/kcheck.sh $GGUF $EST/strata; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
for f in 32k.tokens tf-long28k.prompt tf-long40k.prompt tf-long64k.prompt tf-long112k.prompt pp4k.tokens ldrsyn20k.tokens \
         rep9k.tokens pp32k.tokens tf-long96k.prompt pp8k.tokens; do
  [ -s $WS/bringup/out/r20a/prompts/$f ] || { say "missing prompt file $f (score.py's long11 set) - not started"; exit 1; }
done
$P -I -B $RU pre $NLL_ROOT $H0 $HG > $R/pre-checks.txt 2>&1 8>&- 9>&- || { say "REFUSED: $(tail -1 $R/pre-checks.txt | cut -c1-400) - not started"; exit 1; }
[ "$(sha12 $EST/strata)" = $STOCK_SHA ] || { say "engine-v0210stock is not $STOCK_SHA - not started"; exit 1; }
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 20 ] || { say "only ${free} GB free on results/ (the arms keep ~0.7 GB each) - not started"; exit 1; }
PREV=""
if [ -e $O ] || [ -e $R/decision.txt ]; then   # the rules judge only this attempt's files
  PREV=$R/prev-$(date +%m%d-%H%M%S); mkdir -p $PREV
  for f in $O $R/decision.txt $R/decision.json; do [ -e $f ] && mv $f $PREV/; done
fi
mkdir -p $O
S=$O/summary.txt
say "GDN PATHS ON vs OFF ON STOCK v0.2.10, MANY POSITIONS (work/r23/gap-gdn-nll.sh): score.py at the NLL gap's settings - measurements only, P028x stays served, nothing switches (Karl 11-04)"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
gate pre PASS "$(tail -1 $R/pre-checks.txt | cut -c1-600)"

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 GDN prompt paths on vs off on stock v0.2.10 at many positions (score.py; 2 arms + 2 optional; measurements only, P028x stays served, nothing switches - Karl 11-04)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

say "1 arms s210 (s0210-h: both GDN paths off) and s210gdn (s0210-h-gdn: TC=1 + CONVL2=2, as stock's server.py sets them)"
arm s210 $H0
if ! ok_arm s210; then say "s210 did not run cleanly: nothing to compare against - no further arm"; end_gap; fi
arm s210gdn $HG
if ok_arm s210gdn && fits $(( 2 * ARM_MIN )); then
  say "2 optional: the stock build's own rounding pair ($(( $(left) / 60 )) min to the deadline)"
  arm s210unf $H0 STRATA_PF_FUSED=0 --optional
  arm s210cpu $H0 STRATA_PREFILL_CPU_SHARE=0.4 --optional
else
  say "2 optional stock rounding pair not started ($(( 2 * ARM_MIN )) min do not fit before the deadline, s210gdn did not run cleanly, or a stop): the band is borrowed from the NLL gap"
fi
end_gap
