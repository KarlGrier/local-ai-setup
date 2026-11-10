#!/bin/bash
# gap-confirm0211.sh - r23 (Karl 11-07): THE CONFIRMATION GAP for the v0.2.11 port's prompt-speed fail. It was WRITTEN on
# 11-07 and has NOT BEEN RUN. It is NOT IN work/r23/gap-series.sh and has no .ready file.
# Karl: "Run the 25-minute confirmation gap (B vs P, each also with the chat cache off) after Phase 5's queue."
# Measurements only: P028x stays served, nothing switches, nothing is built.
# Run: `bash work/r23/gap-confirm0211.sh` (no arguments; every path absolute).
# The rules, fixed before any run: work/r23/confirm0211_rules.py's docstring, under the 11-07 amendment
# (work/r22/g17_rules.py, "11-07 park amendment"). The design: results/r23/port-0211/HUNT-1107.md section 3.
# Output: results/r23/port-0211/confirm/ (summary.txt, gates.txt, rules.txt, configs/, speed/, decision.txt).
#
#   0 BEFORE THE GAP (no GPU, 8080 untouched).
#     It REFUSES (exit 1) on:
#       - the research queue still active: deep-research-bench.service; Phase 5 must be done first.
#         C0211_AFTER_P5=1 overrides this once Karl's "after Phase 5's queue" holds;
#       - tmp/gpu-test.lock held, or another gap's lock;
#       - a model server other than the 8080 queue's P028x, or a listener on 8081;
#       - no kernel watcher;
#       - a missing file, config or engine;
#       - engine-r22p028x not P028x, or engine-r23p0211 not its recorded build;
#       - under 5 GB free;
#       - confirm0211_rules.py selftest failing (CPU, nice 19).
#     Then the two chat-cache-off configs are made (confirm0211_rules.py mkcfg: only --chat-cache 16 -> 0) and the rule
#     text is frozen into rules.txt.
#     C0211_DRY=1 stops here (exit 0, nothing opened). C0211_OUT=DIR writes this attempt somewhere else (a dry run's
#     scratch).
#   1 port_gap4.sh begin: the running question finishes, the test lock is taken, 8080 goes down. Wait for the memory;
#     a kernel check.
#   2 12 starts on fresh test servers (with_server.sh, port 8081): B P P B B P P B with the chat cache on, then
#     Boff Poff Poff Boff with it off.
#     - B = configs/x28h.json; P = configs/P0211x-h.json; Boff / Poff = the same with --chat-cache 0
#       (confirm/configs/).
#     - Each start runs port0211_rules.py envcheck (--pins for P / Poff), then abarm.sh with the warm-up and
#       research4's R2-report54k and R3-extract5k twice (R2, R3, R2, R3).
#     - Each start is followed by: the fatal-line check; the foreign-GPU-user watch (one seen = the start is void);
#       the engine's page faults sampled every 0.5 s (INFO); a kernel check.
#     - A start begins only if it ends before the deadline (C0211_MAX_MIN, default 35 min after the gap opens).
#   3 port_gap4.sh end (P028x back) and a kernel check. After the gap (CPU, nice 19): the speed table, then
#     confirm0211_rules.py decide -> decision.txt. If the artifact is confirmed and the stored gate passes under the
#     amended rule, the decision reads: "BASELINE PASS under the 11-07 amended rule (switch requirements in the port
#     plan still apply)".
# About 25 min with 8080 down: 12 starts of about 105-110 s (load about 15 s, warm-up about 5 s, 2 x (R2 about 34 s +
# R3 about 8 s)), plus about 4 min to open and close.
# A kernel-check failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides).
# Exit codes: 0 = done (the outcome is in decision.txt); 1 = refused / not opened (8080 untouched); 3 = kernel check
# failed; 4 = port_gap4.sh end failed.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r23 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; KR=$WS/work/r22; LIB=$WS/bringup/lib; BA=/home/USER/ai-speed-testing/basalt-ab
RU=$WS/work/r23/confirm0211_rules.py; R11=$WS/work/r23/port0211_rules.py
D=$WS/results/r23/port-0211; O=${C0211_OUT:-$D/confirm}; G=$O/gates.txt; R=$O/speed; CF=$O/configs
S=$D/confirm-starts.log            # until the pre-gap checks pass (then $O/summary.txt)
[ -n "${C0211_OUT:-}" ] && S=$O.starts.log
W=$WS/strata-r23p0211; E=$WS/engine-r23p0211; EXE=$E/strata; W28=$WS/strata-r22p028x; E28=$WS/engine-r22p028x
C=$WS/configs; H=$C/P0211x-h.json; X=$C/x28h.json
P028X_SHA=f4c4f654fb24             # engine-r22p028x/strata, served on 8080 since 10-30
PORT_HEAD=${P0211_PORT_HEAD:-d797db9f6}   # the head engine-r23p0211 was built from (11-05)
MAXM=${C0211_MAX_MIN:-35}
mkdir -p $(dirname $S) $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [c211 $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
KFAIL=0; T0=$(date +%s); DEADLINE=$T0
kc() { $LIB/kcheck.sh "c211-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # a start begins only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" "$1"; }
exe_of() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['exe'])" "$1"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }

preflight() {   # refuse (exit 1, nothing touched) when a measurement holds the GPU lock or a model server other than the
  # 8080 queue's P028x runs (gap-port0211.sh's preflight): every engine process (exact names) and every NVIDIA compute
  # process must belong to the server listening on 8080, and that server's engine must be P028x
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
    m=$(awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo)
    [ -z "$left_p" ] && [ "$m" -ge 40 ] && break
    sleep 2
  done
  say "8080 down: engines left:${left_p:- none}, MemAvailable ${m} GB"
}
fatalchk() {   # fatalchk NAME ENGINE_LOG OFFSET LABEL (gap 17): a fatal GPU error / stall / engine restart / non-finite
  local n=$1 L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || gate fatal_$n FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite (engine log $L from byte $off; $sl)"
}
foreign() {   # the GPU users that are not one of this gap's two engines (gap-port0211.sh's rule): an engine process (exact
  # names) or an NVIDIA compute process holding >= 512 MiB (or an unknown amount) whose binary is in neither engine folder
  local p m x ex c
  { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x | sed 's/$/,engine/'; done
    nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2> /dev/null; } | tr -d ' ' \
  | while IFS=, read -r p m; do
      [[ $p =~ ^[0-9]+$ ]] && [ -e /proc/$p ] || continue
      [[ $m =~ ^[0-9]+$ ]] && [ $m -lt 512 ] && continue
      ex=$(readlink /proc/$p/exe 2> /dev/null) || ex=""; c=$(cat /proc/$p/comm 2> /dev/null)
      case $c in strata-dsv41|llama-server|ollama) ;; *) [ -n "$ex" ] || continue
        case $ex in $E/*|$E28/*) continue;; esac;; esac
      echo "pid $p ($c, ${ex:-?}, $m$([[ $m =~ ^[0-9]+$ ]] && echo ' MiB'))"
    done | sort -u
}
gwatch() {   # gwatch FLAG OUT: while FLAG exists (and this driver runs), every 5 s: foreign GPU users >> OUT
  while [ -e $1 ] && kill -0 $$ 2> /dev/null; do foreign | sed "s/^/$(date +%T) /" >> $2; sleep 5; done
}
gpu_clear() {   # gpu_clear NAME: no foreign GPU user before the start (up to 60 s); else foreign_NAME FAIL, not started
  local i f
  for i in $(seq 12); do f=$(foreign); [ -z "$f" ] && return 0; sleep 5; done
  gate foreign_$1 FAIL "not started: $(echo "$f" | head -1) still on the GPU after 60 s"
  return 1
}
WGP=""
wstart() { rm -f $O/$1.foreign; touch $O/$1.watching; gwatch $O/$1.watching $O/$1.foreign 8>&- 9>&- & WGP=$!; }
wstop() {    # one foreign GPU user seen during the start = foreign_NAME FAIL (the start is void)
  rm -f $O/$1.watching; [ -n "$WGP" ] && wait $WGP 2> /dev/null; WGP=""
  [ -s $O/$1.foreign ] && gate foreign_$1 FAIL "seen during $1 ($(wc -l < $O/$1.foreign) sample(s)): $(head -1 $O/$1.foreign | cut -c1-160) - VOID"
  return 0
}
fsample() {   # fsample FLAG OUT EXE: while FLAG exists, every 0.5 s: "t minflt majflt rss_kb" of the engine running EXE
  # (found by /proc/PID/exe; INFO for the save's two levels - the allocator hypothesis, HUNT-1107.md section 4)
  local flag=$1 out=$2 exe=$3 d pid="" st f
  echo "# t minflt majflt rss_kb (the engine $exe)" > $out
  while [ -e $flag ] && kill -0 $$ 2> /dev/null; do
    if [ -z "$pid" ] || [ ! -e /proc/$pid ]; then
      pid=""; for d in /proc/[0-9]*; do [ "$(readlink $d/exe 2> /dev/null)" = "$exe" ] && { pid=${d#/proc/}; break; }; done
    fi
    if [ -n "$pid" ] && st=$(cat /proc/$pid/stat 2> /dev/null); then
      st=${st##*) }; read -r -a f <<< "$st"     # f[0] = field 3 (state): minflt = field 10, majflt 12, rss 24 (pages)
      echo "$(date +%s.%N | cut -c1-14) ${f[7]} ${f[9]} $(( ${f[21]} * 4 ))" >> $out
    fi
    sleep 0.5
  done
}
carm() {   # carm ARM START: one start on a fresh server: warm-up, then R2, R3, R2, R3 (research4, 2 reps)
  local a=$1 k=$2 n=$1$2 cfg pf="" L off fs
  case $a in B) cfg=$X;; P) cfg=$H; pf=--pins;; Boff) cfg=$CF/x28h-cc0.json;; Poff) cfg=$CF/P0211x-h-cc0.json; pf=--pins;; esac
  fits 3 || { say "skipped $n (under 3 min to the deadline, or a kernel check failed)"; return 1; }
  gpu_clear $n || { say "$n NOT started (a foreign GPU user)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "start $n ($(basename $cfg))"
  wstart $n
  touch $O/$n.sampling; fsample $O/$n.sampling $O/faults-$n.tsv $(exe_of $cfg) 8>&- 9>&- & fs=$!
  $LIB/with_server.sh c211-$n $cfg -- "$P -I -B $R11 envcheck $(exe_of $cfg) $cfg --ngpu 2 $pf --gate env_$n --gates $G && bash $KR/abarm.sh http://127.0.0.1:8081 $off $R $n ${n}r=research4:2:R2,R3" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|vram" | tee -a $S
  rm -f $O/$n.sampling; wait $fs 2> /dev/null
  wstop $n
  tail -c +$((off + 1)) $L > $R/$n.engine.log
  fatalchk $n $L $off c211-$n
  kc $n
}
after_gap() {   # CPU only, nice 19, 8080 back: the speed table and the decision
  local labs
  labs=$(ls $R/*.jsonl 2> /dev/null | xargs -n1 basename 2> /dev/null | sed 's/\.jsonl$//' | grep -E '^(B|P|Boff|Poff)[1-4]r$' | sort | tr '\n' ' ')
  [ -n "$labs" ] && nice -n 19 $P $BA/scripts/abreport.py --dir $R $labs > $O/speed-table.md 2>&1
  nice -n 19 $P -I -B $RU decide $O > /dev/null 2>&1
  [ -f $O/decision.txt ] && cat $O/decision.txt | tee -a $S || say "confirm0211_rules.py decide failed - by hand: $P -I -B $RU decide $O"
}
end_gap() {
  if [ $KFAIL = 1 ]; then
    say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"
    nice -n 19 $P -I -B $RU decide $O > /dev/null 2>&1 || true; exit 3
  fi
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "confirmation gap: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  after_gap
  say "confirmation gap done"
  exit 0
}

# ================================================================ 0 before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-confirm0211.sh (pre-gap checks)${C0211_DRY:+ - DRY RUN, nothing is opened}"
if systemctl --user is-active -q deep-research-bench.service && [ "${C0211_AFTER_P5:-0}" != 1 ]; then
  say "the research queue (deep-research-bench.service, Phase 5) is still active - Karl 11-07: this gap runs after Phase 5's queue (C0211_AFTER_P5=1 once it is done) - not started"; exit 1
fi
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
for f in $H $X $RU $R11 $KR/g17_rules.py $KR/port_gap4.sh $KR/abarm.sh $BA/scripts/abrun.py $BA/scripts/abreport.py \
         $LIB/with_server.sh $LIB/kcheck.sh $LIB/guard.py $W/serve/server.py $W28/serve/server.py \
         $D/gap/gates.txt $D/gap/speed/B1r.englog; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ -x $E28/strata ] && [ "$(sha12 $E28/strata)" = $P028X_SHA ] || { say "engine-r22p028x is not P028x ($P028X_SHA) - not started"; exit 1; }
if [ ! -x $EXE ] || [ "$(sha12 $EXE)" != "$(cut -c1-12 $E/SHA256 2> /dev/null)" ] \
   || ! grep -q "^v0.2.11 + 28 commits (branch r23-port0211 $PORT_HEAD" $E/SOURCE 2> /dev/null; then
  say "engine-r23p0211 is not the recorded build of r23-port0211 $PORT_HEAD (the one port-0211's gate measured) - not started"; exit 1
fi
[ "$(exe_of $H)" = $EXE ] && [ "$(exe_of $X)" = $E28/strata ] || { say "P0211x-h / x28h do not name their engines - not started"; exit 1; }
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 5 ] || { say "only ${free} GB free on results/ - not started"; exit 1; }
ST=$(mktemp -d $WS/tmp/r23/c211-selftest.XXXXXX)
if ! nice -n 19 $P -I -B $RU selftest $ST > $ST.out 2>&1; then
  say "confirm0211_rules.py selftest failed ($(tail -1 $ST.out | cut -c1-160)) - not started"; exit 1
fi
say "  confirm0211_rules.py selftest: $(tail -1 $ST.out)"; rm -rf $ST $ST.out
PREV=""
if [ -d $O ] && ls -A $O | grep -q .; then   # the rules judge only this attempt's files
  PREV=$O-prev-$(date +%m%d-%H%M%S); mv $O $PREV
fi
mkdir -p $O $R $CF
$P -I -B $RU mkcfg $X $CF/x28h-cc0.json | tee -a $S && $P -I -B $RU mkcfg $H $CF/P0211x-h-cc0.json | tee -a $S \
  || { say "mkcfg failed - not started"; exit 1; }
$P -I -B $RU rules $O/rules.txt
S=$O/summary.txt
say "CONFIRMATION GAP (work/r23/gap-confirm0211.sh, Karl 11-07): B (x28h) vs P (P0211x-h), each also with --chat-cache 0, on R2 / R3 - measurements only, P028x stays served, nothing switches; rules sha $(sha12 $O/rules.txt)"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
if [ "${C0211_DRY:-0}" = 1 ]; then say "DRY RUN: the pre-gap checks passed; the gap is not opened (exit 0)"; exit 0; fi

# ================================================================ 1 the gap
$KR/port_gap4.sh begin "r23 v0.2.11 port confirmation gap: B vs P with and without --chat-cache 0 on R2 / R3 (measurements only; P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

say "2 the starts: B P P B B P P B (chat cache on), Boff Poff Poff Boff (off); deadline $MAXM min"
declare -A K=([B]=0 [P]=0 [Boff]=0 [Poff]=0)
for a in B P P B B P P B Boff Poff Poff Boff; do
  K[$a]=$(( ${K[$a]} + 1 ))
  carm $a ${K[$a]} < /dev/null || true
done
end_gap
