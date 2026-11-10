#!/bin/bash
# gap-ud31.sh - r23, Karl's Unsloth Dynamic v3.1 test (approved 11-04: "P, U, S, R; text NLL and KL against R; speed with
# the no-loss rule; exactness. Put it after the DeepSeek C gap, once tonight's NLL gap has validated the scorer.").
# WRITTEN 11-04, REVISED 11-05 (Karl: STRATA_HC_Q8=1 on U and R, the frozen pack-rounding rule, the decode-path
# follow-up work/r23/gap-ud31-dec.sh), NOT RUN. A step of work/r23/gap-series.sh (`bash <driver>`, no arguments; every
# path absolute). Measurements only: P028x stays served, NOTHING SWITCHES. Rules (written before any run):
# work/r23/ud31_rules.py's docstring, copied to results/r23/ud31/gap/rules.txt when the gap starts.
# Arms (results/qwen4-kit/unsloth-v31/REPORT.md sections 3, 5, 7; configs results/r23/ud31/configs/, = configs/x28h.json
# + only their named differences, checked by `ud31_rules.py cfgcheck`):
#   P  P028x as served without vision: configs/x28h.json (engine-r22p028x, never edited); STRATA_HC_Q8 off (unset)
#   U  UD-IQ3_XXS v3.1 as shipped: pack bringup/out/ud31/pack-u (iq_pack --compat-bf16); x28h with only --pack,
#      --native (shard 1/4), --ple-gguf (shard 4/4) changed + STRATA_HC_Q8=1 (the verify read takes the GGUF's own
#      Q8_0 hyper-connections; the prompt path still reads them as BF16 - the pack-rounding rule)
#   S  the splice: v3.1's 144 routed experts in our ISTA shard 1 (work/r15/splice_shard1.py: shard 1 only, ~54.8 GB,
#      our shard 2 hard-linked; written INSIDE the gap, then sync + evict before any engine starts); pack
#      bringup/out/ud31/pack-s (no --compat-bf16); x28h with the three paths changed; no switch
#   R  UD-Q4_K_XL from the HF cache (the KL reference, quality only): pack bringup/out/ud31/pack-r (--compat-bf16);
#      x28h's switches in r21-yq-udq4's memory form (5080 alone, --resident-budget-gib 52, chat cache 2 GiB) +
#      STRATA_HC_Q8=1 as U (reference rows used for U carry U's switch; R's Q8_0 hc are its file's own)
# The switch is checked from each engine's own log (ud31_rules.py hcline: U and R "0.63 GiB" = their GGUF's own Q8_0
# hc, P and S no line) after each quality arm and each arm's first screen pass.
#   0 before the gap (no GPU, 8080 untouched) - REFUSES (exit 1) unless: the download is complete and verified (4 shards,
#     sizes + SHA256SUMS = tree.json's pinned oids), the NLL gap validated the scorer (validate_ref PASS only - 11-05: the
#     many-positions NLL bound is REVOKED, ADOPTED-BOUND.json is gone and not needed), the configs check, >= 100 GB
#     free after the splice, no gpu-test.lock /
#     other gap / model server other than the 8080 queue's P028x / 8081 listener, the kernel watcher runs, the
#     lossless config check passes on U and S; an earlier attempt's outputs move to results/r23/ud31/prev-*
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down); the 4 shards re-hashed; pack U; the
#     splice + verify; sync, Dirty + Writeback drained, page cache evicted; pack S (dense.bin + index = P028x's); pack R
#   2 exactness: exact7 at pin 2500 U1 (vs P028x's x28h-e7a, INFO), U2 (vs U1: 7/7 + slots MATCHED), S1, S2 the same;
#     each engine's environment checked as it starts (decode_rules.py envcli)
#   3 quality: score.py run --set long11 --rows all:8 on P, U, S, R (nll_rules.py envwatch on each)
#   4 speed: the 9-workload screen (abarm.sh), 3 passes in turned order P U S / S U P / U S P, a fresh test server each
#     (g17_rules.py envcheck); start lines + lossless with the engine log on U and S's first pass
#   5 inside the gap when it fits (else after it, nice 19): validate per arm with its own head + score.py validate on P
#     (head_P), the compare (ud31_rules.py: KL(R || X) and NLL per position -> rows.tsv) -> ud31_rules.py decide: the
#     KL RULES AGAINST R AT THE TEXT LEVEL (8 distinct texts; mean, p90, KL > 1 rows, changed top-1; text NLL INFO
#     only) -> results/r23/ud31/decision.txt (with "=> U DECODE-PATH FOLLOW-UP: WANTED | NOT NEEDED | NOT DECIDED":
#     WANTED unless U is BETTER THAN P (worse, or inside the margin on either side) - the series' next step, gap-ud31-dec.sh, runs only
#     then); port_gap4.sh end (P028x back) + a kernel check
# A kernel check after every step; a failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides).
# No new step after UD31_MAX_MIN (default 120) minutes with 8080 down; a step starts only if its minutes fit. Expected
# ~105 min with 8080 down. Exit 0 = done (outcome in decision.txt), 1 = refused / not opened (8080 untouched), 3 = kernel
# check failed (gap open), 4 = port_gap4.sh end failed. Steps and times: work/r23/GAPS-README.md, section 7.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
P=$WS/.venv/bin/python; KR=$WS/work/r22; LIB=$WS/bringup/lib
RU=$WS/work/r23/ud31_rules.py; NR=$WS/work/r23/nll_rules.py; DR=$WS/work/r23/decode_rules.py; R17=$KR/g17_rules.py
SCORE=$WS/work/r23/nll-many/score.py; SPL=$WS/work/r15/splice_shard1.py
PACKER=$WS/strata-r22p028x/tools/iq_pack.py; GGPY=$WS/strata/third_party/llama.cpp/gguf-py
R=$WS/results/r23/ud31; CF=$R/configs; O=$R/gap; G=$O/gates.txt; NL=$O/nll; SPD=$O/speed
STARTS=$R/gap-ud31-starts.log; S=$STARTS             # until the pre-gap checks pass (then $O/summary.txt)
X=$WS/configs/x28h.json; CU=$CF/ud31-U.json; CS=$CF/ud31-S.json; CR=$CF/ud31-R.json
EXE=$WS/engine-r22p028x/strata; P028X_SHA=f4c4f654fb24          # engine-r22p028x/strata, served on 8080 since 10-30
UD=$WS/models/unsloth-v31/UD-IQ3_XXS; UN=Qwen3.8-Flash-Next-UD-IQ3_XXS; TREE=$WS/work/qwen4-kit/unsloth-v31/dl/tree.json
IS=$WS/models/ISTA-GSQ-RCO/IQ3_S; IS1=$IS/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
IS2=$IS/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
SD=$WS/models/unsloth-v31/splice-S; SB=Qwen3.8-Flash-Next-UD31x-GSQ-RCO-IQ3_S
RD=/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL
RN=Qwen3.8-Flash-Next-UD-Q4_K_XL
PK=$WS/bringup/out/ud31; PU=$PK/pack-u; PS=$PK/pack-s; PR=$PK/pack-r; PP=$WS/bringup/out/r20a/pack
NLL_ROOT=$WS/results/r23/nll-many/gap; PROF=$WS/bringup/out/logs/prof; E7REF=x28h-e7a
MAXM=${UD31_MAX_MIN:-120}; E7_MIN=4; Q_MIN=7; QR_MIN=12; SCR_MIN=5; CMP_MIN=10
TAG=$(date +%m%d%H%M)             # exact7 labels u31-$TAG-U1 ... (bringup/out/logs/prof is shared by every run)
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$IS/*.gguf $UD/*.gguf"
mkdir -p $R $WS/tmp/r23 $WS/logs
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [ud31 $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
KFAIL=0; T0=$(date +%s); DEADLINE=$T0; DONE_Q=0; HAVE_U=0; HAVE_S=0; HAVE_R=0
kc() { $LIB/kcheck.sh "ud31-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; echo "kfail FAIL after $1" >> $G; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # a step starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -I -c "import json; print(json.load(open('$1'))['log'])"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
cfg_of() { case $1 in P) echo $X;; U) echo $CU;; S) echo $CS;; R) echo $CR;; esac; }
hcwant() { case $1 in U|R) echo on;; *) echo off;; esac; }   # STRATA_HC_Q8 (Karl 11-05): U and R on, P and S off
memavail() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }

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
wait_mem() {   # after 8080 stops: its engines gone and their memory back, at most 120 s
  local i x left_p m
  for i in $(seq 60); do
    left_p=""; for x in strata strata-host strata-vision strata-dsv41; do pgrep -x $x > /dev/null && left_p="$left_p $x"; done
    m=$(memavail)
    [ -z "$left_p" ] && [ "$m" -ge 40 ] && break
    sleep 2
  done
  say "8080 down: engines left:${left_p:- none}, MemAvailable ${m} GB"
}
fatalchk() {   # fatalchk NAME ENGINE_LOG OFFSET LABEL: a fatal GPU error / stall / engine restart / non-finite (gap 17)
  local n=$1 L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] && gate fatal_$n PASS "no fatal / stall / restart / non-finite line" \
    || gate fatal_$n FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite (engine log $L from byte $off; $sl)"
}
evict_all() {   # drop the model files' clean pages (scripts/evict.py, posix_fadvise) and report the page cache
  local f=""
  for x in $IS/*.gguf $UD/*.gguf $SD/*.gguf $RD/*.gguf; do [ -e "$x" ] && f="$f $x"; done
  $P -I $WS/scripts/evict.py $f > $O/evict-$1.txt 2>&1
  say "  evicted ($1): $(grep -c 'page cache' $O/evict-$1.txt) files; $(awk '/^(Dirty|Writeback|Cached|MemAvailable|SwapFree):/ {printf "%s %d MiB  ", $1, $2 / 1024}' /proc/meminfo)"
}
pack() {   # pack NAME SHARD1 OUT [--compat-bf16]: tools/iq_pack.py of the served tree (bytecode off: nothing is written there)
  local n=$1 src=$2 out=$3 rc
  shift 3
  mkdir -p $out
  say "pack $n: $(basename $src) -> $out $*"
  env PYTHONDONTWRITEBYTECODE=1 STRATA_GGUF_PY=$GGPY nice -n 5 $P -I -B $PACKER --gguf $src --out $out "$@" < /dev/null > $O/pack-$n.log 2>&1 8>&- 9>&-
  rc=$?
  if [ $rc = 0 ] && [ -s $out/native_experts.txt ] && [ -s $out/index.txt ]; then
    gate pack_$n PASS "rc 0: $(grep -E '^index.txt:|compat-bf16:|conversions.json:' $O/pack-$n.log | tr '\n' ' ' | cut -c1-200)"
  else
    gate pack_$n FAIL "rc $rc: $(tail -3 $O/pack-$n.log | tr '\n' ' ' | cut -c1-200)"; return 1
  fi
  if diff -r -q $out/tokenizer $PP/tokenizer > /dev/null 2>&1; then gate tok_$n PASS "tokenizer = P028x's (bringup/out/r20a/pack/tokenizer)"
  else gate tok_$n FAIL "the pack's tokenizer differs from P028x's (the configs use r20a's): $(diff -r -q $out/tokenizer $PP/tokenizer 2>&1 | head -2 | tr '\n' ' ' | cut -c1-160)"; fi
}
e7() {   # e7 KEY CONFIG REF: exact7 at pin 2500 (bringup/lib/exact7.sh: 7 items, --adapt-swaps 0 --suffix-draft 0), its
  # engine environment checked as it starts (decode_rules.py envcli, mode e7: the config's env exactly, tail skip 0, 2
  # GPUs, the pin); KEY ending in 1 = INFO against P028x, ending in 2 = PASS needed against the first run
  local k=$1 cfg=$2 ref=$3 L=u31-$TAG-$1 jp info=""
  fits $E7_MIN || { say "skipped exact7 $L ($E7_MIN min do not fit before the deadline, or a kernel check)"; return 1; }
  say "exact7 $L ($(basename $cfg), against $ref)"
  ( PIN_CACHE=2500 REF=$ref $LIB/exact7.sh $L $cfg 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $DR envcli $EXE $cfg --job $jp --mode e7 --ngpu 2 --kill --gate env_e7$k --gates $G 8>&- 9>&- 2>&1 \
    | tee $O/env-e7$k.txt | tail -1 | tee -a $S
  wait $jp
  case $k in *1) info=--info;; esac
  $P -I -B $DR e7gate $S $L $info --gate e7_$k --gates $G 8>&- 9>&- | tee -a $S
  kc e7-$k
}
watchdog() {   # watchdog JOB MINUTES NAME: a quality arm past MINUTES (3 x its estimate) is hung - stop the engine in the
  # job's own process tree by its PID (guard.py does not pass a TERM on to its child's session); score.py then ends
  local j=$1 m=$2 n=$3 t p q
  t=$(( $(date +%s) + m * 60 ))
  while kill -0 $j 2> /dev/null; do
    if [ $(date +%s) -ge $t ]; then
      for p in $( { pgrep -x strata; pgrep -x strata-host; } | sort -un); do
        q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != $j ]; do q=$(ppid_of $q); done
        [ "$q" = $j ] && kill -TERM $p 2> /dev/null && echo "watchdog: $n ran past $m min - its engine (pid $p) was stopped" >> $NL/$n.watchdog
      done
      return 0
    fi
    sleep 5
  done
}
qarm() {   # qarm ARM MIN: score.py run (one cold read of the 11 long texts, every 8th prompt row kept), the engine's
  # environment checked as it starts (nll_rules.py envwatch: the config's env + pf_yardstick's fixed env, no other
  # STRATA_*, tail skip 0, the config's GPU count, score.py's engine args); a kernel check after it
  local n=$1 m=$2 cfg jp wd rc t1
  cfg=$(cfg_of $1)
  fits $m || { say "skipped quality arm $n ($m min do not fit before the deadline, or a kernel check)"; return 1; }
  say "quality arm $n ($(basename $cfg); ~$m min)"
  rm -rf $NL/$n; rm -f $NL/$n.rc $NL/$n.watchdog; t1=$(date +%s)
  ( $P $LIB/guard.py ud31nll-$n -- $P -I $SCORE run $cfg $NL/$n --set long11 --rows all:8 > $NL/$n.run.txt 2>&1
    echo $? > $NL/$n.rc ) 8>&- 9>&- &
  jp=$!
  watchdog $jp $(( 3 * m )) $n 8>&- 9>&- &
  wd=$!
  $P -I -B $NR envwatch $jp $cfg --kill --gate env_$n --gates $G 8>&- 9>&- 2>&1 | tail -2 | tee -a $S
  wait $jp
  kill $wd 2> /dev/null; wait $wd 2> /dev/null
  [ -f $NL/$n.watchdog ] && say "  $(cat $NL/$n.watchdog)"
  rc=$(cat $NL/$n.rc 2> /dev/null || echo none)
  grep -E "rows from [0-9]+ texts|^PROBLEM" $NL/$n.run.txt | tail -4 | sed "s/^/  $n: /" | tee -a $S
  if [ "$rc" = 0 ] && [ -f $NL/$n/index.json ]; then
    gate run_$n PASS "score.py run rc 0: $(grep -E 'rows from [0-9]+ texts' $NL/$n.run.txt | tail -1)"
  else
    gate run_$n FAIL "rc $rc: $(grep -E '^PROBLEM|SystemExit|Error|answered|ended before|GUARD' $NL/$n.run.txt | head -3 | tr '\n' ' ' | cut -c1-250)"
  fi
  $P -I -B $RU hcline $NL/$n/stderr.txt $cfg --want $(hcwant $n) --gate hcq8_nll_$n --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
  QLAST=$(( ($(date +%s) - t1 + 59) / 60 )); say "  $n: $QLAST min"
  kc nll-$n
}
sarm() {   # sarm ARM PASS: one 9-workload screen pass on a fresh test server (gap 17 / 18's harness), its engine's env checked
  local a=$1 k=$2 n=$1$2 cfg L off
  cfg=$(cfg_of $1)
  fits $SCR_MIN || { say "skipped screen $n ($SCR_MIN min do not fit before the deadline, or a kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "screen $n ($(basename $cfg))"
  $LIB/with_server.sh ud31-$n $cfg -- "$P -I -B $R17 envcheck $EXE $cfg --ngpu 2 --gate env_scr$n --gates $G && bash $KR/abarm.sh http://127.0.0.1:8081 $off $SPD $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|vram" | tee -a $S
  tail -c +$((off + 1)) $L > $SPD/engine-$n.log
  fatalchk scr$n $L $off ud31-$n
  [ $k = 1 ] && $P -I -B $RU hcline $SPD/engine-$n.log $cfg --want $(hcwant $a) --gate hcq8_scr_$a --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
  kc scr-$n
}
quality_after() {   # quality_after THREADS: CPU only - validate each arm with its own head, the head check on P, the compare
  local th=$1 x c cfgs=""
  say "quality: validate (each arm's own head), head check on P, compare ($th BLAS threads, nice 19)"
  for x in P U S R; do
    [ -f $NL/$x/index.json ] || continue
    c=$(cfg_of $x)
    if [ "$(gstat run_$x)" = PASS ] && [ "$(gstat env_$x)" = PASS ]; then
      nice -n 19 $P -I -B $RU validate $NL/$x $c --json $NL/validate-$x.json --gate validate_$x --gates $G > $NL/validate-$x.txt 2>&1
      tail -1 $NL/validate-$x.txt | sed "s/^/  validate $x: /" | tee -a $S
      cfgs="$cfgs --cfg $x=$c"
    else gate validate_$x FAIL "arm $x did not run cleanly (run $(gstat run_$x), env $(gstat env_$x))"; fi
  done
  if [ -f $NL/P/index.json ]; then
    nice -n 19 $P -I $SCORE validate $NL/P > $NL/validate-P-scorepy.txt 2>&1
    $P -I -B $RU headcheck $NL/validate-P-scorepy.txt $NL/validate-P.json --gate head_P --gates $G 2>&1 | tee -a $S
  fi
  if [ "$(gstat validate_P)" = PASS ] && [ "$(gstat head_P)" = PASS ]; then
    rm -f $O/result.json $O/rows.tsv
    nice -n 19 $P -I -B $RU compare $NL $cfgs --threads $th --json $O/result.json --rows-out $O/rows.tsv \
      --gate compare --gates $G > $O/compare.txt 2>&1 || gate compare FAIL "rc $?: $(tail -2 $O/compare.txt | tr '\n' ' ' | cut -c1-200)"
    tail -1 $O/compare.txt | tee -a $S
  else
    say "no compare: P's own-head validation or the head check did not pass (QUALITY NOT JUDGED)"
  fi
  DONE_Q=1
}
finish() {   # the rules -> decision.txt (results/r23/ud31/ and the gap folder)
  $P -I -B $RU decide $O > /dev/null 2>&1 8>&- 9>&- || say "ud31_rules.py decide failed - rerun it by hand ($RU decide $O)"
  [ -f $O/decision.txt ] && { cp $O/decision.txt $O/decision.json $R/; tee -a $S < $O/decision.txt > /dev/null; }
  [ -f $O/decision.txt ] && say "$(grep -E '^=> U DECODE-PATH FOLLOW-UP' $O/decision.txt | cut -c1-200) (gap-ud31-dec.sh runs only on WANTED)"
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; finish; exit 3; fi
  if [ $DONE_Q = 0 ] && [ -f $NL/P/index.json ] && fits $CMP_MIN; then quality_after 8; fi   # 8080 down: RAM and cores free
  finish
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "v3.1 gap: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  if [ $DONE_Q = 0 ] && [ -f $NL/P/index.json ]; then
    for i in $(seq 60); do [ "$(memavail)" -ge 22 ] && break; sleep 10; done   # two heads (~5 GB) above the 12 GB floor
    if [ "$(memavail)" -ge 22 ]; then quality_after 4
    else say "MemAvailable $(memavail) GB < 22 after 10 min: the compare is NOT run - by hand later: $RU validate / headcheck / compare (see quality_after in this script)"; fi
    finish
  fi
  say "v3.1 gap done"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-ud31.sh (pre-gap checks)"
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
PRE=$R/pre-checks; mkdir -p $PRE       # this attempt's pre-gap check outputs (overwritten by the next attempt)
$P -I -B $RU predl $UD $TREE > $PRE/predl.txt 2>&1 || { say "REFUSED: $(tail -1 $PRE/predl.txt) - not started"; exit 1; }
$P -I -B $RU prenll $NLL_ROOT > $PRE/prenll.txt 2>&1 || { say "REFUSED: $(tail -1 $PRE/prenll.txt) - not started"; exit 1; }
$P -I -B $RU cfgcheck $CF > $PRE/cfg.txt 2>&1 || { say "REFUSED: $(tail -1 $PRE/cfg.txt) - not started"; exit 1; }
for f in $X $CU $CS $CR $RU $NR $DR $R17 $SCORE $SPL $PACKER $GGPY/gguf/__init__.py $KR/port_gap4.sh $KR/abarm.sh \
         $LIB/exact7.sh $LIB/with_server.sh $LIB/guard.py $LIB/kcheck.sh $LIB/run.sh $WS/bringup/patchtest.sh $WS/scripts/evict.py \
         $IS1 $IS2 $PP/index.txt $PP/dense.bin $WS/strata-v0115/mtp/rt/experts.bin $WS/strata-v0115/third_party/llama.cpp/gguf-py/gguf/__init__.py; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
for f in 32k.tokens tf-long28k.prompt tf-long40k.prompt tf-long64k.prompt tf-long112k.prompt pp4k.tokens ldrsyn20k.tokens \
         rep9k.tokens pp32k.tokens tf-long96k.prompt pp8k.tokens math.tokens code.tokens p2000.tokens; do
  [ -s $PROMPT_DIR/$f ] || { say "missing prompt file $f (score.py's long11 set / exact7's items) - not started"; exit 1; }
done
i=0; for n in 10946624 49859583136 49376141504 12087983520; do i=$((i + 1))
  [ "$(stat -L -c %s $RD/$RN-0000$i-of-00004.gguf 2> /dev/null)" = $n ] || { say "R's shard $i is not the HF cache's UD-Q4_K_XL ($n B) - not started"; exit 1; }
done
[ "$(sha12 $EXE)" = $P028X_SHA ] && [ "$(cut -c1-12 $WS/engine-r22p028x/SHA256)" = $P028X_SHA ] || { say "engine-r22p028x is not P028x ($P028X_SHA) - not started"; exit 1; }
[ "$(ls $PROF/$E7REF-*.out 2> /dev/null | wc -l)" = 7 ] || { say "P028x's exact7 $E7REF is not complete (7 .out files) - not started"; exit 1; }
ls $PROF/u31-$TAG-* > /dev/null 2>&1 && { say "exact7 labels u31-$TAG-* exist already - not started"; exit 1; }
grep -q '^STRATA_MMQ_KQUANTS:BOOL=ON' $WS/strata-r22p028x/build/CMakeCache.txt 2> /dev/null && KQ="K-quant prompt kernels ON (R's experts)" || KQ="CMakeCache does not say STRATA_MMQ_KQUANTS=ON: R's prompt path may be slow or refused"
for c in U S; do
  CFG=$(cfg_of $c) TREE=strata-r22p028x $WS/bringup/patchtest.sh lossless 2>&1 8>&- 9>&- | grep -E "PASS|FAIL" | tail -1 > $PRE/lossless-$c.txt
  grep -q "cfg: PASS" $PRE/lossless-$c.txt || { say "the lossless config check fails on $c: $(cat $PRE/lossless-$c.txt) - not started"; exit 1; }
done
old=0; [ -f $SD/$SB-00001-of-00002.gguf ] && old=$(stat -c %s $SD/$SB-00001-of-00002.gguf)
free=$(df --output=avail -B1 $WS/models | tail -1 | tr -d ' ')
after=$(( (free + old - 54817524224 - 8000000000) / 1000000000 ))
[ $after -ge 100 ] || { say "only ~$after GB would be free after the splice, the packs and the dumps (floor 100 GB) - not started"; exit 1; }
PREV=""
if [ -e $O ] || [ -e $R/decision.txt ] || [ -e $R/dec ]; then   # the rules judge only this attempt's files (a follow-up
  PREV=$R/prev-$(date +%m%d-%H%M%S); mkdir -p $PREV               # of an earlier decision goes with that decision)
  for f in $O $R/decision.txt $R/decision.json $R/dec; do [ -e $f ] && mv $f $PREV/; done
fi
mkdir -p $O $NL $SPD
$P -I -B $RU rules --out $O/rules.txt > /dev/null 2>&1 || { say "could not write the rules snapshot $O/rules.txt - not started"; exit 1; }
S=$O/summary.txt
say "UNSLOTH DYNAMIC v3.1 GAP (work/r23/gap-ud31.sh): P, U, S, R - exactness, the KL rules against R at the text level (text NLL INFO: the NLL bound is revoked), speed (Karl 11-04; STRATA_HC_Q8=1 on U and R, the pack-rounding rule, 11-05) - measurements only, P028x stays served, nothing switches"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
gate rules INFO "the rule text at the gap's start (ud31_rules.py's docstring, incl. the frozen pack-rounding rule): gap/rules.txt sha $(sha12 $O/rules.txt)"
gate predl PASS "$(tail -1 $PRE/predl.txt | cut -c1-200)"
gate prenll PASS "$(tail -1 $PRE/prenll.txt | cut -c1-300)"
gate cfg PASS "$(tail -1 $PRE/cfg.txt | cut -c1-200)"
for c in U S; do gate lossless_${c}_cfg PASS "$(cat $PRE/lossless-$c.txt | cut -c1-200)"; done
say "R: $KQ; disk: ~$after GB free after the splice; exact7 labels u31-$TAG-*; ud31-download unit: $(systemctl --user is-active ud31-download 2> /dev/null)"

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 Unsloth v3.1 test gap (P / U / S / R: packs + splice, exact7, score.py NLL + KL, speed screen x3; measurements only, P028x stays served, nothing switches - Karl 11-04)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

# ---- 1 the files: re-hash, pack U, the splice (+ verify, sync, evict), pack S, pack R
say "1 re-hash the 4 shards (sha256 against tree.json's pinned oids; pages dropped as read)"
$P -I -B $RU rehash $UD $TREE --gate dl_sha --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
if [ "$(gstat dl_sha)" != PASS ]; then say "the shards do not hash to the pinned oids: nothing runs on them, the gap ends"; end_gap; fi
pack U $UD/$UN-00001-of-00004.gguf $PU --compat-bf16 && HAVE_U=1
[ $HAVE_U = 1 ] && $P -I -B $RU hcforms $PU --gate hcforms_U --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S   # INFO: the hc rows' pack forms
say "1b the splice: v3.1's routed experts into our ISTA shard 1 (shard 2 hard-linked), then sync + evict"
mkdir -p $SD; rm -f $SD/$SB-00001-of-00002.gguf $SD/$SB-00001-of-00002.gguf.part $SD/$SB-00002-of-00002.gguf
say "  before: $(awk '/^(MemAvailable|Dirty|SwapFree):/ {printf "%s %d MiB  ", $1, $2 / 1024}' /proc/meminfo)"
nice -n 5 $P -I -B $SPL $SD $SB --rest $IS1 --experts $UD/$UN-0000{2,3,4}-of-00004.gguf < /dev/null > $O/splice.log 2>&1 8>&- 9>&-
rc=$?
grep -E "tensors in our shard 1|^wrote|VERIFY" $O/splice.log | cut -c1-300 | tee -a $S
if [ $rc = 0 ] && [ -f $SD/$SB-00001-of-00002.gguf ]; then gate splice PASS "$(grep '^wrote' $O/splice.log | cut -c1-200)"
else gate splice FAIL "rc $rc: $(tail -2 $O/splice.log | tr '\n' ' ' | cut -c1-200)"; rm -f $SD/$SB-00001-of-00002.gguf.part; fi
grep -q "^VERIFY OK" $O/splice.log && gate splice_verify PASS "$(grep '^VERIFY OK' $O/splice.log | cut -c1-250)" \
  || gate splice_verify FAIL "$(grep '^VERIFY' $O/splice.log | cut -c1-250)"
[ -f $SD/$SB-00001-of-00002.gguf ] && sync -f $SD/$SB-00001-of-00002.gguf
$P -I -B $RU dirty --below-mb 256 --max-s 300 --gate dirty --gates $G 2>&1 | tail -1 | tee -a $S
evict_all splice
if [ "$(gstat splice)" = PASS ] && [ "$(gstat splice_verify)" = PASS ] && [ "$(gstat dirty)" = PASS ]; then
  if pack S $SD/$SB-00001-of-00002.gguf $PS; then
    if cmp -s $PS/dense.bin $PP/dense.bin && diff -q <(tail -n +2 $PS/index.txt) <(tail -n +2 $PP/index.txt) > /dev/null; then
      gate pack_S_dense PASS "pack-s dense.bin and index rows = P028x's bringup/out/r20a/pack byte for byte (the dense path is P028x's)"
    else
      gate pack_S_dense FAIL "pack-s dense.bin / index.txt differ from bringup/out/r20a/pack ($(cmp $PS/dense.bin $PP/dense.bin 2>&1 | head -1 | cut -c1-120))"
      pack Pnow $IS1 $PK/pack-p-check && { cmp -s $PS/dense.bin $PK/pack-p-check/dense.bin \
        && gate pack_S_tool INFO "pack-s dense.bin = today's iq_pack of OUR file: the difference is the tool's, not the splice's" \
        || gate pack_S_tool INFO "pack-s dense.bin differs from today's iq_pack of our file too: the splice changed a dense tensor"; }
    fi
    HAVE_S=1; EVICT_GLOB="$EVICT_GLOB $SD/*.gguf"
  fi
else
  say "no S arm (splice $(gstat splice), verify $(gstat splice_verify), page cache $(gstat dirty))"
fi
pack R $RD/$RN-00001-of-00004.gguf $PR --compat-bf16 && HAVE_R=1
[ $HAVE_R = 1 ] && $P -I -B $RU hcforms $PR --gate hcforms_R --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
evict_all packs
$P -I -B $RU dirty --below-mb 256 --max-s 120 2>&1 | tail -1 | tee -a $S
say "  arms: P, U $([ $HAVE_U = 1 ] && echo yes || echo NO), S $([ $HAVE_S = 1 ] && echo yes || echo NO), R $([ $HAVE_R = 1 ] && echo yes || echo NO) ($(( $(left) / 60 )) min to the deadline)"
kc files || end_gap
[ $HAVE_U = 0 ] && [ $HAVE_S = 0 ] && { say "neither U nor S can run: the gap ends"; end_gap; }

# ---- 2 exactness: exact7 twice per new file (repeatability)
say "2 exactness: exact7 at pin 2500, U1 / S1 against P028x's $E7REF (INFO), U2 / S2 against U1 / S1 (7/7 + MATCHED)"
if [ $HAVE_U = 1 ]; then e7 U1 $CU $E7REF; e7 U2 $CU u31-$TAG-U1; fi
if [ $HAVE_S = 1 ]; then e7 S1 $CS $E7REF; e7 S2 $CS u31-$TAG-S1; fi

# ---- 3 quality: score.py's many-positions run on P, U, S, R
say "3 quality: score.py run --set long11 --rows all:8 on P, U, S, R ($(( $(left) / 60 )) min to the deadline)"
QLAST=$Q_MIN
qarm P $Q_MIN
QM=$(( QLAST > Q_MIN ? QLAST + 1 : Q_MIN ))       # U and S read the same texts: P's measured minutes (+1) when longer
[ $HAVE_U = 1 ] && qarm U $QM
[ $HAVE_S = 1 ] && qarm S $QM
[ $HAVE_R = 1 ] && qarm R $(( QR_MIN > QM + 4 ? QR_MIN : QM + 4 ))

# ---- 4 speed: the 9-workload screen, 3 passes in turned order
say "4 speed: the 9-workload screen, 3 passes (P U S / S U P / U S P), a fresh test server each ($(( $(left) / 60 )) min to the deadline)"
for k in 1 2 3; do
  case $k in 1) order="P U S";; 2) order="S U P";; 3) order="U S P";; esac
  arms=""; for a in $order; do case $a in U) [ $HAVE_U = 1 ] && arms="$arms U";; S) [ $HAVE_S = 1 ] && arms="$arms S";; *) arms="$arms P";; esac; done
  n=$(echo $arms | wc -w)
  fits $(( n * SCR_MIN )) || { say "screen pass $k not started ($(( n * SCR_MIN )) min do not fit, or a kernel check)"; break; }
  for a in $arms; do sarm $a $k; done
  if [ $k = 1 ]; then
    sl=""
    for a in $arms; do
      [ -f $SPD/${a}1.startlog ] || continue
      $P -I -B $R17 startlines base $SPD/${a}1.startlog $(slog ud31-${a}1) --gate start_$a --gates $G 8>&- 9>&- | tee -a $S
      sl="$sl $a $(grep -oE 'expert cache [0-9]+ slots' $SPD/${a}1.startlog | tail -1 | grep -oE '[0-9]+')+$(grep -oE 'CUDA1: [0-9]+ additional experts' $SPD/${a}1.startlog | tail -1 | grep -oE '[0-9]+')"
      [ $a = P ] && continue
      CFG=$(cfg_of $a) TREE=strata-r22p028x ELOG=$SPD/engine-${a}1.log $WS/bringup/patchtest.sh lossless 2>&1 8>&- 9>&- | grep -E "PASS|FAIL" | tail -1 > $O/lossless-$a-log.txt
      grep -q "cfg: PASS" $O/lossless-$a-log.txt && grep -q "log clean" $O/lossless-$a-log.txt && gate lossless_${a}_log PASS "$(cut -c1-200 $O/lossless-$a-log.txt)" \
        || gate lossless_${a}_log FAIL "$(cut -c1-200 $O/lossless-$a-log.txt)"
    done
    gate slots INFO "5080 + 4060 Ti slots at start (auto fill):$sl"
  fi
done

# ---- 5 the rules (validate + compare inside the gap when it fits), P028x back
end_gap
