#!/bin/bash
# gap-gate0213.sh - r23 (written 2026-11-10 at the desk, NOT RUN; only --dry-run and the --mock test ran): THE v0.2.13
# PORT'S BASELINE GATE. Karl 11-10: "Baseline gate on the v0.2.13 port: yes, run it next (exactness on the command-line
# path, long40, the 3-pass screen and Basalt's speed rule). If the -2.5% decode turns out real beyond noise, find the cause
# desk-first, the same way as the 1.4% hunt, and note any pin for the Qwen4 port. Add the single-card fallback config only
# if it's cheap." The v0.2.11 port's gate (work/r23/gap-port0211.sh) with today's switch-gap machinery
# (work/r23/switch-gap/gap-switch0213.sh). The rules, frozen into the gate's rules.txt before the gap opens:
# work/r23/gate-0213/gate0213_rules.py's docstring (BASELINE PASS / BORDERLINE / FAIL / INCOMPLETE + THE DECODE LINE); the
# configs: work/r23/gate-0213/make_configs0213.py (written at run time into the gate's configs/). MEASUREMENTS ONLY: 8080
# stays the daily, nothing switches, nothing is built, no config of the served setup changes. Started by
# work/r23/gate-0213/gate-start.sh (a user unit) as a snapshot copy; every path is absolute.
# Usage: gap-gate0213.sh [--dry-run | --mock]; any other argument: nothing runs (exit 2). One instance at a time
# (tmp/gate0213.driver.pid: a second one exits 9 before it touches anything).
#   0 BEFORE THE GAP (no GPU; 8080 untouched). It REFUSES (nothing changed) - exit 1 = busy (the starter retries), exit 6 =
#     a hard refusal (an alert), exit 8 = HELD by the priority rule (final, an alert) - unless:
#     - the build unit build-p0213-stock is inactive; the research queue is not held by anyone else; THE PRIORITY RULE
#       (Karl 11-09; afetch_rules.py priority): no open Qwen4 Flash weights, or tmp/gate0213-priority-done has a dated
#       reason line (Karl's word only); the post-Phase-5 chain is not running; no other gap, no held test lock, no model
#       server but 8080's daily (153ce47d3ef0), nothing on 8081; nvidia-smi answers within 20 s;
#     - TODAY'S SWITCH GAP STANDS FOR THIS BUILD (gate0213_rules.py switchref): its verdict SWITCH CHECKS PASS, its result
#       DONE, its recorded P sha = engine-r23p0213/strata's now (639dfb1b7042), its recorded tree head = strata-r23p0213's
#       HEAD now, the four source configs unchanged since it ran - else a hard refusal;
#     - the files are there; engine-r23p0213 = its SHA256 file, SOURCE names r23-port0213 at that head, the tree clean;
#       engine-v0213stock (stock v0.2.13) is there, = its SHA256 file = strata-v0213stock/build/strata, SOURCE names
#       v0.2.13's commit, that worktree at v0.2.13 and clean (missing / not matching: a hard refusal); engine-r22p028x =
#       f4c4f654fb24; engine-r23afetch = 153ce47d3ef0; port_gap4.sh knows 153ce47d3ef0; both configure logs say 8-row
#       windows; no ninja runs in either tree; >= 10 GB free;
#     - gate0213_rules.py's selftest passes; make_configs0213.py make + check (the arms B, P, PH, OFF, ST, NOV2, SG);
#       the port's 19 pins + 2 keys in configs/P0213x.json and in PH; fence4 (port0211_rules.py fence4 on strata-r23p0213's
#       own parser, CPU, seconds; not PASS: a hard refusal); the single-card plan (switch_rules.py fixtures -> 3 requests at
#       512 tokens); INFO from stored runs (exact7 of the port with fetch=2 against the daily's, 11-10 /
#       11-09); the rules frozen into rules.txt - all BEFORE the gap opens;
#     - right before the gap: the busy checks again, the kernel-log watcher runs, no kernel-error marker, a kernel check.
#   1 port_gap4.sh begin (the research queue held after its running question, the test lock, 8080 down; GAP_MAX_MIN = the
#     worst case below); the engines gone and MemAvailable >= 40 GB (120 s at most; engines still there: the gap ends,
#     exit 5 - named, never killed); PRE = the engine processes running as the gap opened (never stopped by this gap); a
#     kernel check; the watchdog; the priority rule again
#   2 exact7 at pin 2500 on the CLI forms (no STRATA_ADAPT_FETCH): ST (stock v0.2.13), OFF vs ST (FIRST: every switch
#     off = the release), x28h (P028x), PH vs x28h (7/7 expected; not 7/7: stock 0.2.8 vs stock v0.2.13, both pinned,
#     decides as gap 16 / 17's T1 rule and port0211 - upstream moved too -> INFO, the KL rules decide; upstream did not move
#     -> FAIL), the patch guards, PH again (repeat), NOV2 vs PH; a pair is run only against a clean reference run; INFO:
#     PH vs the stored g23p-p211a (the v0.2.11 port); INFO, only with P0213G_AF2_E7=1 (default 0: the same pair is
#     stored, see step 0) and only when it fits beside every required part: P vs B (both fetch=2). Every item's engine
#     checked as it starts (envcli --kill); the VmSwap watch around every run (swap_TAG)
#   3 pf_yardstick long40 on PH (envcli --mode pfy); kernel_rule2 + kernel_rule3 against gap 8's references; INFO: the
#     logit files against gap 16's x28h and the v0.2.11 gate's p211
#   4 the 9-workload screen, 3 passes in turned order (B P / P B / B P) on B / P (the served forms), with_server.sh +
#     abarm.sh; every start: port0211_rules.py envcheck --pins (the engine and its server.py), switch_rules.py armenv and
#     startline (fetch=2), the fatal-line check, no foreign GPU user before / during it, THE SWAP RULE (every GW_S s the
#     VmSwap of this gap's engines from /proc/PID/status; > 0 = swap_TAG FAIL), the client chain's rc (not 0, or none:
#     rc_TAG FAIL), test_cleanup, a kernel check; a left-out start's records go to speed/void/ (INCOMPLETE, named)
#   5 Basalt's community-1 fixtures, cold (a fresh engine each), 3 passes in turned order (M H / H M / M H): M = B, H = P,
#     decode / pp16k / pp64k; per run its own file (a left-out run's to bp90/void/)
#   6 INFO, only if 5 min fit before the deadline: the single-card fallback (configs/P0213x-single.json's test form, the
#     RTX 5080 alone): one start, its checks (envcheck --ngpu 1), 3 short requests at the standard sampling
#   7 the lock sweep, port_gap4.sh end (the daily back), a kernel check; then (CPU, nice 19): lossless, #3961's line in
#     the port's server logs, start lines, continuations, the speed table, Basalt's report, gate0213_rules.py decide ->
#     verdict.txt / decision.txt / .json; result.txt, a NOTES.md line, a non-urgent ntfy note. NOTHING SWITCHES.
# The priority rule is checked again before each part and each start: a find stops new steps, the decision is written on
# what ran and the gap ends cleanly (8080 back): exit 8 and an alert.
# TIME with 8080 down (the v0.2.11 gate's 11-07 timings: exact7 3.3 min a set, long40 8.7, a screen pass 3.6, a cold
# Basalt run 1.3; the single start ~3): open ~1, exact7 6 sets ~20 (+3.3 with stock 0.2.8), long40 ~9, the screen ~22,
# Basalt 18 runs ~24, the single card ~3, the end ~2 -> ~81 min (~84 with s028; +7 with P0213G_AF2_E7=1). Deadline
# P0213G_MAX_MIN (default 130) minutes after the gap opens for any new step; a step starts only if its minimum fits
# (exact7 5, long40 10, a screen pass 5, a Basalt run 3, the single card 5; the INFO exact7 pair only with 2 x 5 + the
# required rest, 94, left). WORST CASE ~2.6 h with 8080 down (155 min = GAP_MAX_MIN): the deadline 130 + the longest
# overrun of a step started inside its minimum (~8) + the lock sweep and port_gap4.sh end ~8 + the open's wait ~2 + slack.
# THE KERNEL-ERROR POLICY (Karl 11-09): any new Xid or kernel error (kwatch's tmp/r19/KERNEL_ERROR, polled every 2 s while
# a test engine or a CLI job runs: this gap's engines - and the running job's tree - are killed at once, and again at
# every poll while the marker exists; checked before every step; or a kernel check failing) stops the gap at once: the
# lock sweep, port_gap4.sh end (the daily back), a critical alert, the result "KERNEL ERROR during the gap - stopped at
# once, ...", exit 3. kwatch is NOT cleared. The first poll that sees the marker writes a "kstop" line into gates.txt
# before it kills anything, and every run checks the marker (kerr_check: the kfail line) before its own gates are written:
# a start gate from the stop on (a fatal line, a lost engine) is "seen at the stop" (INCOMPLETE), never a FAIL.
# Exit 0 done (the verdict in verdict.txt / decision.txt), 1 busy (refused, nothing changed), 2 a bad argument, 3 a kernel
# error / kernel check failure, 4 port_gap4.sh end failed, 5 not run: engines still running after 8080 stopped, 6 hard
# refusal (alert), 7 stopped by a signal (alert), 8 the priority rule, 9 another instance runs.
# --dry-run: the pre-gap checks that read only (a refusal is printed and the plan goes on), the rules' selftest, the
# configs, the pins, the single-card plan and the frozen rules (all under work/r23/gate-0213/scratch/), then the plan of
# every command, printed; no lock, no GPU query, no kernel check, no port_gap4, no request to any port.
# --mock: (work/r23/gate-0213/gap-mock-test.sh only) every tool a stub under work/r23/gate-0213/scratch/mock; the rules
# run for real on the stubs' outputs and stored data; never kills a real process, never queries the GPU (nvidia-smi is a
# stub), writes no NOTES.md / alert / ntfy. MOCK_* variables steer the stubs.
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock descriptor reaches a child (this script holds none itself)
WS=/home/USER/ai-speed-testing/strata-compare
case ${1:-} in ""|--dry-run|--mock) ;; *) echo "usage: gap-gate0213.sh [--dry-run | --mock] (got '${1:-}'): nothing run"; exit 2;; esac
GD=$WS/work/r23/gate-0213
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
MOCK=0; [ "${1:-}" = --mock ] && MOCK=1
M=$GD/scratch/mock
[ $MOCK = 1 ] && { [ -x $M/lib/with_server.sh ] || { echo "--mock needs work/r23/gate-0213/gap-mock-test.sh's stubs"; exit 2; }; }
# ---- one instance at a time: before anything touches the output folder; the pid file is not inside it
PIDF=$WS/tmp/gate0213.driver.pid; [ $MOCK = 1 ] && PIDF=$M/driver.pid
alive_driver() { [ -n "$1" ] && kill -0 "$1" 2> /dev/null && tr '\0' ' ' < /proc/$1/cmdline 2> /dev/null | grep -q 'gap-gate0213'; }
if [ $DRY = 0 ]; then
  for try in 1 2; do
    ( set -o noclobber; echo $$ > $PIDF ) 2> /dev/null && break
    op=$(cat $PIDF 2> /dev/null)
    if alive_driver "$op"; then echo "another gap-gate0213.sh (pid $op) is running: not started, nothing touched"; exit 9; fi
    [ $try = 1 ] && rm -f $PIDF || { echo "the pid file $PIDF could not be taken: not started, nothing touched"; exit 9; }
  done
  [ "$(cat $PIDF 2> /dev/null)" = "$$" ] || { echo "the pid file $PIDF is not this driver's: not started, nothing touched"; exit 9; }
  trap '[ "$(cat $PIDF 2> /dev/null)" = "$$" ] && rm -f $PIDF' EXIT
fi
export RB_CACHE=$WS/tmp/r23                       # (before env.sh: its tool caches and TMPDIR go there)
[ $DRY = 1 ] && export RB_CACHE=$GD/scratch/rb-cache
[ $MOCK = 1 ] && export RB_CACHE=$M/rb-cache
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE PROF_SAMPLING EXE ENVX NSYS COLD REF PIN_CACHE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
for v in $(compgen -e | grep '^PAID_SEARCH'); do unset "$v"; done   # nor a paid-search run id or cap from outside
for v in $(compgen -e | grep '^SQ_'); do unset "$v"; done
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; PY="$P -I -B"
GR=$GD/gate0213_rules.py; MK=$GD/make_configs0213.py; SWR=$WS/work/r23/switch-gap/switch_rules.py
AFR=$WS/work/r23/afetch-gap/afetch_rules.py; RU=$WS/work/r23/port0211_rules.py; RUE=$RU; FR=$WS/work/r23/basalt_fix_rules.py
KR=$WS/work/r22; LIB=$WS/bringup/lib; B90=$KR/basalt-pr90; BA=/home/USER/ai-speed-testing/basalt-ab
FXC=$WS/work/r23/switch-gap/fixtures_client.py; PATCHTEST=$WS/bringup/patchtest.sh
O=$WS/results/r23/port-0213/gate; SWO=$WS/results/r23/port-0213/switch-gap; LOGD=$WS/logs/r23/gate0213
[ $DRY = 1 ] && { O=$GD/scratch/gate-dry; LOGD=$GD/scratch/gate-dry-logs; }
W28=$WS/strata-r22p028x; W13=$WS/strata-r23p0213; WST=$WS/strata-v0213stock
EAF=$WS/engine-r23afetch; E13=$WS/engine-r23p0213; E28=$WS/engine-r22p028x; EST=$WS/engine-v0213stock; E28S=$WS/engine-r22s028t
C=$WS/configs; X=$C/x28h.json; S28=$C/s028-h.json; P13=$C/P0213x.json; SGC=$C/P0213x-single.json
PROF=$WS/bringup/out/logs/prof; SLOGDIR=$WS/bringup/out/logs
Y8=$WS/results/r22/gap8/pfy; Y16=$WS/results/r22/gap16/pfy; Y11=$WS/results/r23/port-0211/gap/pfy
LOCKPID=$WS/tmp/port-gap.lockpid; HOLD=/home/USER/ai/deep-research/tmp/bench2.hold
NOTE=$WS/configs/usability/bin/ntfy-note.py
STATE=$WS/work/qwen4-kit/hfwatch/state.json; PRIO_DONE=$WS/tmp/gate0213-priority-done
SRVSH=$LIB/srv.sh; STOPMON=$WS/scripts/stopmon.sh
BUILD_UNIT=build-p0213-stock; BUILD_LOG=$WS/logs/r23/build-p0213-stock.log
GGUF=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
BPD=/home/USER/ai-speed-testing/basalt-pr90-data; WL=$BA/scripts/workloads.json
B_SHA=153ce47d3ef0; P_SHA=639dfb1b7042; X28_SHA=f4c4f654fb24
E7STORED_P=r23sw11101048-P; E7STORED_B=r23aa11091954-S2; E7P211=g23p-p211a   # (stored exact7 runs: INFO)
HOLDTAG="v0.2.13 baseline gate"
MAXM=${P0213G_MAX_MIN:-130}; AF2E7=${P0213G_AF2_E7:-0}   # (the INFO exact7 pair: off by default - its stored pair is e7_af2_stored)
E7_MIN=5; PFY_MIN=10; SCR_MIN=5; BP_MIN=3; SG_MIN=5
REST_MIN=$(( PFY_MIN + 6 * SCR_MIN + 18 * BP_MIN ))   # 94: the required parts after exact7 (the INFO pair never takes it)
WORST_OVER=25
NVSMI_T=20; GPUCLEAR_N=12; GPUCLEAR_S=5; GW_S=5; KL_S=2; KGRACE_N=10; KGRACE_S=2; KTERM_S=10
ENGNAMES="strata strata-host"; LOCKF=$WS/tmp/gpu-test.lock
KERR=$WS/tmp/r19/KERNEL_ERROR   # kwatch's marker of a kernel error (never taken from the environment, never cleared here)
LP=g13$(date +%m%d%H%M)
MOCKENV=""; NOSHA=""
if [ $MOCK = 1 ]; then   # every tool, folder and lock file under scratch/mock; the real configs and stored results are only read
  O=$M/out; LIB=$M/lib; KR=$M/kr; B90=$M/b90; BA=$M/ba; FR=$M/fr/basalt_fix_rules.py; RUE=$M/ru/port0211_rules.py
  FXC=$M/clients/fixtures_client.py; PATCHTEST=$M/lib/patchtest.sh; SWO=$M/swref; LOGD=$M/logs; PROF=$M/prof
  SLOGDIR=$M/slogs; Y8=$M/y8; Y16=$M/y16; Y11=$M/y11; LOCKPID=$M/lockpid; HOLD=$M/hold; NOTE=$M/lib/ntfy-note.py
  STATE=$M/state.json; PRIO_DONE=$M/gate0213-priority-done; SRVSH=$M/lib/srv.sh; STOPMON=$M/lib/stopmon.sh
  BUILD_UNIT=g13-mock-no-such-unit; KERR=$M/kernel_error; LOCKF=$M/gpu-test.lock
  EAF=$M/engines/engine-r23afetch; E13=$M/engines/engine-r23p0213; E28=$M/engines/engine-r22p028x
  EST=$M/engines/engine-v0213stock; E28S=$M/engines/engine-r22s028t
  ENGNAMES=g13mock-eng; MOCKENV=" --mock-env $M/engine-env.json"; NOSHA=--no-sha
  NVSMI_T=1; GPUCLEAR_N=2; GPUCLEAR_S=1; GW_S=0.3; KL_S=0.3; KGRACE_N=3; KGRACE_S=0.2; KTERM_S=1
  export PATH=$M/bin:$PATH        # (nvidia-smi is a stub there)
fi
CF=$O/configs; S=$O/summary.txt; G=$O/gates.txt; EL=$O/englog; FG=$O/foreign; SPD=$O/speed; BO=$O/bp90; Y=$O/pfy
SGO=$O/single; WSO=$O/with_server
PREV=""
if [ $DRY = 0 ] && [ $MOCK = 0 ] && [ -n "$(find $EL $SPD $BO/runs $Y $FG -mindepth 1 -print -quit 2> /dev/null; ls $SGO/single.jsonl $O/t0.txt 2> /dev/null)" ]; then
  # (only what a gap writes counts: a refused attempt leaves configs/, the plans and empty folders, which are rewritten)
  PREV=$O-prev-$(date +%m%d-%H%M%S); mv $O $PREV                                 # the rules judge only this attempt's files
fi
[ $DRY = 1 ] && rm -rf $O $LOGD
[ $MOCK = 1 ] && rm -rf $O
mkdir -p $O $CF $EL $FG $SPD $BO/runs $Y $SGO $WSO $LOGD
[ $DRY = 0 ] && [ $MOCK = 0 ] && mkdir -p $WS/tmp/r23 $WS/logs
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [g13 $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }   # a gate's last status ("" = not written)
swr() { nice -n 19 $PY $SWR "$@" 8>&- 9>&- < /dev/null; }        # switch_rules.py (CPU only)
gr() { nice -n 19 $PY $GR "$@" 8>&- 9>&- < /dev/null; }          # gate0213_rules.py (CPU only)
afr() { nice -n 19 $PY $AFR "$@" 8>&- 9>&- < /dev/null; }        # afetch_rules.py (its priority rule)
br() { $PY $FR br "$@" 8>&- 9>&- < /dev/null; }                   # basalt_rules.py's subcommands (envcli)
ru() { nice -n 19 $PY $RU "$@" 8>&- 9>&- < /dev/null; }          # port0211_rules.py (CPU subcommands)
mocked() { [ $DRY = 1 ] || [ $MOCK = 1 ]; }
alert() { mocked && { say "(dry run / mock: would alert: $1 - $2)"; return 0; }; notify-send -a "Strata gaps" -u critical "$1" "$2" 2> /dev/null || true; }
note() { mocked && { say "(dry run / mock: would send the ntfy note: $1 - $2)"; return 0; }; $NOTE "$1" "$2" >> $S 2>&1 8>&- 9>&- < /dev/null || say "(the ntfy note did not go out)"; }
notes_line() { mocked && { say "(dry run / mock: would add to NOTES.md: $1)"; return 0; }; printf -- '- %s v0.2.13 BASELINE GATE (Karl 11-10; work/r23/gate-0213/gap-gate0213.sh, results/r23/port-0213/gate/): %s\n' "$(date '+%m-%d %H:%M')" "$1" >> $WS/NOTES.md; }
KFAIL=0; PRIO=0; GAPOPEN=0; ENDING=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 )); WDG=""; KILLED=0; JP=""
PRE=""; T0T=0; CLK=$(getconf CLK_TCK)   # T0T = the gap's open in clock ticks since boot (the processes' start ticks: the same clock)
kc() { $LIB/kcheck.sh "g13-$1" > /dev/null 8>&- 9>&- < /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; gate kfail FAIL "after $1"; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
kerr_check() {   # (Karl 11-09) a kernel error recorded by kwatch: no further step (end_gap then stops at once, the daily back)
  [ -e $KERR ] && [ $KFAIL = 0 ] && { KFAIL=1; say "a kernel error is recorded ($(head -c 160 $KERR 2> /dev/null | tr '\n' ' ')): no further step"; gate kfail FAIL "a kernel error is recorded (kwatch not cleared)"; }
  return 0
}
ok_to_go() { kerr_check; [ $KFAIL = 0 ] && [ $PRIO = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # a step starts only if its minimum ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
jget() { nice -n 19 $P -I -B -c "import json, sys; print(json.load(open(sys.argv[1]))$2)" "$1"; }
elog() { jget "$1" "['log']"; }
exe_of() { jget "$1" "['exe']"; }
slog() { ls -t $SLOGDIR/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
nrecs() { local f n=0; for f in "$@"; do [ -f "$f" ] && n=$(( n + $(grep -c . "$f") )); done; echo $n; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
memav() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }
engines_left() {
  local x out=""
  if [ $MOCK = 1 ]; then for x in $ENGNAMES; do pgrep -x $x > /dev/null && out="$out $x"; done; [ "${MOCK_ENGINES_LEFT:-0}" = 1 ] && out="$out strata-host"; echo $out; return 0; fi
  for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x > /dev/null && out="$out $x"; done; echo $out
}
listener8080() { ss -H -ltnp "( sport = :8080 )" 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }
ours() { case "$1" in $EAF/*|$E13/*|$E28/*|$EST/*|$E28S/*) return 0;; esac; return 1; }   # this gap's binaries (B's is also the daily's)
uptk() { awk -v c=$CLK '{printf "%d", $1 * c}' /proc/uptime; }
ptick() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || { echo 0; return 0; }; s=${s##*) }; set -- $s; echo ${20}; }
our_exe_pids() { find /proc/[0-9]*/exe -maxdepth 0 \( -lname "$EAF/*" -o -lname "$E13/*" -o -lname "$E28/*" -o -lname "$EST/*" -o -lname "$E28S/*" \) 2> /dev/null | cut -d/ -f3 | sort -un; }
under8080() {   # under8080 PID: the process descends from the 8080 listener (the served daily: never this gap's to stop)
  local l q; l=$(listener8080); [ -n "$l" ] || return 1
  q=$1; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != "$l" ]; do q=$(ppid_of $q); done; [ "$q" = "$l" ]
}
ours_new() {   # ours_new PID EXE: this gap's binary AND started after the gap opened AND not one of PRE AND not under 8080
  ours "$2" && [ $GAPOPEN = 1 ] && [ $T0T -gt 0 ] || return 1
  case " $PRE " in *" $1 "*) return 1;; esac
  [ "$(ptick $1)" -ge $T0T ] || return 1
  under8080 $1 && return 1
  return 0
}
pre_alive() { local p; for p in $PRE; do [ -e /proc/$p ] && echo "$p($(cat /proc/$p/comm 2> /dev/null), $(readlink /proc/$p/exe 2> /dev/null))"; done | tr '\n' ' '; }
ours_running() { local p ex x; for p in $( { for x in $ENGNAMES; do pgrep -x $x; done; } | sort -un); do ex=$(readlink /proc/$p/exe 2> /dev/null) || continue; ours_new $p "$ex" && echo $p; done; }
kill_ours() {   # this gap's engines still running after a run: 20 s to exit, then TERM, 10 s, KILL; KILLED = how many
  local p i n=0
  KILLED=0
  [ $GAPOPEN = 1 ] && [ $ENDING = 0 ] || return 0
  for i in $(seq $KGRACE_N); do [ -z "$(ours_running)" ] && return 0; sleep $KGRACE_S; done
  for p in $(ours_running); do kill -TERM $p 2> /dev/null && n=$((n + 1)); done
  sleep $KTERM_S
  for p in $(ours_running); do kill -KILL $p 2> /dev/null; done
  KILLED=$n
  [ $n = 0 ] || say "  stopped $n engine process(es) of this gap left after its run"
}
CLEANED=""
test_cleanup() {   # after every test-server run, however it ended: the guard and server.py (their own sessions), a server
  # still on 8081, the monitor, this gap's engines. 0 = nothing was left; 1 = CLEANED names it (the caller voids the start)
  local lab=$1 gp c pg me sig
  CLEANED=""
  if [ $MOCK = 1 ]; then   # (the mock: a stub server; this gap's fake engines are found and stopped for real)
    PORT=8081 $SRVSH stop > /dev/null 2>&1; $STOPMON $lab > /dev/null 2>&1
    if [ -e $M/leftover ]; then rm -f $M/leftover; CLEANED="the test server's guard and its server (mock)"; say "  stopped $CLEANED, left after the run"; fi
    kill_ours
    [ $KILLED -gt 0 ] && CLEANED="${CLEANED:+$CLEANED, }$KILLED engine process(es)"
    [ -z "$CLEANED" ]; return
  fi
  me=$(ps -o pgid= -p $$ 2> /dev/null | tr -d ' ')
  gp=$(cat $WS/bringup/out/logs/srv.pid 2> /dev/null)
  if [ -n "$gp" ] && kill -0 "$gp" 2> /dev/null && tr '\0' ' ' < /proc/$gp/cmdline 2> /dev/null | grep -qF "srv-$lab"; then
    for sig in TERM KILL; do
      for c in $(pgrep -P $gp); do
        pg=$(ps -o pgid= -p $c 2> /dev/null | tr -d ' ')
        [ -n "$pg" ] && [ "$pg" != "$me" ] && kill -$sig -- -$pg 2> /dev/null; kill -$sig $c 2> /dev/null
      done
      [ $sig = TERM ] && sleep 5
    done
    kill -TERM $gp 2> /dev/null; sleep 2; kill -0 $gp 2> /dev/null && kill -KILL $gp 2> /dev/null
    CLEANED="the test server's guard ($gp) and its server"
    say "  stopped $CLEANED, left after the run"
  fi
  if ss -H -ltn "( sport = :8081 )" 2> /dev/null | grep -q .; then
    PORT=8081 $SRVSH stop 8>&- 9>&- < /dev/null > /dev/null 2>&1
    CLEANED="${CLEANED:+$CLEANED, }a server still on 8081"; say "  stopped a server still on 8081 after the run"
  fi
  $STOPMON $lab 8>&- 9>&- < /dev/null > /dev/null 2>&1
  kill_ours
  [ $KILLED -gt 0 ] && CLEANED="${CLEANED:+$CLEANED, }$KILLED engine process(es)"
  [ -z "$CLEANED" ]
}
lock_sweep() {   # before port_gap4 end and in on_signal: nothing of this gap may still run or hold the test lock (strata-ensure
  # refuses while anyone holds it): this gap's programs are killed (never one under the 8080 listener or from before the gap),
  # its leftovers (monitor / guard of this gap's labels, a job naming this gap's folder) stopped, anything else is named
  local p ex cmd lp pp bad=""
  [ $GAPOPEN = 1 ] && [ $ENDING = 0 ] || return 0
  say "  lock sweep before the end"
  lp=$(cat $LOCKPID 2> /dev/null); pp=$(ppid_of ${lp:-0})
  for p in $(our_exe_pids); do
    [ "$p" = $$ ] && continue
    ex=$(readlink /proc/$p/exe 2> /dev/null) || continue
    if ours_new $p "$ex"; then kill -KILL $p 2> /dev/null; bad="$bad $p(${ex##*/}: this gap's, killed)"
    else case " $PRE " in *" $p "*) bad="$bad $p(${ex##*/}: running since before the gap - left alone)";; esac; fi
  done
  for p in $(find /proc/[0-9]*/fd -maxdepth 1 -lname "$LOCKF" 2> /dev/null | cut -d/ -f3 | sort -un); do   # the test lock's holders
    { [ "$p" = $$ ] || [ "$p" = "$lp" ] || [ "$p" = "$pp" ]; } && continue   # (the gap's own lock holder)
    cmd=$(tr '\0' ' ' < /proc/$p/cmdline 2> /dev/null | cut -c1-400)
    case $cmd in *monitor-$LP-*|*srv-$LP-*|*$O/*) kill -TERM $p 2> /dev/null; bad="$bad $p(this gap's leftover, stopped)";;
      *) bad="$bad $p($(cat /proc/$p/comm 2> /dev/null) holds the test lock)";; esac
  done
  [ -n "$bad" ] && { say "  lock sweep before the end:$bad"; gate lock_sweep INFO "$bad"; sleep 3; }
  return 0
}
wdg_stop() { local c; [ -n "$WDG" ] || return 0; for c in $(pgrep -P $WDG 2> /dev/null); do kill $c 2> /dev/null; done; kill $WDG 2> /dev/null; WDG=""; }
preflight() {   # the reviewed rule (gap-switch0213.sh): no measurement on the GPU lock, no other gap, no model server but the daily
  local l p q apps bad="" x
  if [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; then
    refuse busy "another gap holds the test lock (tmp/port-gap.lockpid $(cat $LOCKPID))"; return 1
  fi
  [ $MOCK = 1 ] && return 0
  if ! flock -n -x $WS/tmp/gpu-test.lock true 2> /dev/null; then
    refuse busy "tmp/gpu-test.lock is held (a measurement or a test server)"; return 1
  fi
  l=$(listener8080)
  apps=$(timeout -k 5 $NVSMI_T nvidia-smi --query-compute-apps=pid --format=csv,noheader 2> /dev/null) || { refuse busy "nvidia-smi did not answer within $NVSMI_T s"; return 1; }
  for p in $( { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x "$x"; done; echo "$apps"; } \
              | tr -d ' ' | grep -E '^[0-9]+$' | sort -un); do
    q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != "${l:-none}" ]; do q=$(ppid_of $q); done
    if [ -n "$l" ] && [ "$q" = "$l" ]; then
      case $(cat /proc/$p/comm 2> /dev/null) in
        strata|strata-host) [ "$(sha12 /proc/$p/exe 2> /dev/null)" = $B_SHA ] || bad="$bad 8080-engine:$p($(readlink /proc/$p/exe))";;
        strata-vision) ;;
        *) bad="$bad 8080:$p($(cat /proc/$p/comm 2> /dev/null))";;
      esac
    else bad="$bad $p($(cat /proc/$p/comm 2> /dev/null))"; fi
  done
  ss -H -ltn "( sport = :8081 )" 2> /dev/null | grep -q . && bad="$bad listener-on-8081(a-test-server)"
  [ -z "$bad" ] || { refuse busy "a model server other than the 8080 queue's daily ($B_SHA) is running:$bad"; return 1; }
}
fatalchk() {   # fatalchk GATE ENGINE_LOG OFFSET LABEL: a fatal GPU error / stall / engine restart / non-finite in the slice
  local L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || gate $1 FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite ($L from byte $off; $sl)"
}
foreign() {   # GPU users that are not this gap's: an engine process (exact names) or an NVIDIA compute process holding >= 512
  # MiB (or an unknown amount) that is not one of this gap's own programs (ours_new: a restarted 8080 engine with B's
  # binary counts as foreign); nvidia-smi not answering within NVSMI_T s = "not clear". (--mock: nvidia-smi is the stub)
  local p m x ex c
  { [ $MOCK = 1 ] || for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x | sed 's/$/,engine/'; done
    timeout -k 5 $NVSMI_T nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2> /dev/null || echo 'NVSMIFAIL,0'; } | tr -d ' ' \
  | while IFS=, read -r p m; do
      [ "$p" = NVSMIFAIL ] && { echo "nvidia-smi did not answer within $NVSMI_T s (taken as: not clear)"; continue; }
      [[ $p =~ ^[0-9]+$ ]] && [ -e /proc/$p ] || continue
      [[ $m =~ ^[0-9]+$ ]] && [ $m -lt 512 ] && continue
      ex=$(readlink /proc/$p/exe 2> /dev/null) || ex=""; c=$(cat /proc/$p/comm 2> /dev/null)
      case $c in strata-dsv41|llama-server|ollama) ;; *) [ -n "$ex" ] || continue; ours_new $p "$ex" && continue;; esac
      echo "pid $p ($c, ${ex:-?}, $m$([[ $m =~ ^[0-9]+$ ]] && echo ' MiB'))"
    done | sort -u
}
desc() { local c; for c in $(pgrep -P $1 2> /dev/null); do echo $c; desc $c; done; }
kill_tree() { local p; [ -n "${1:-}" ] && kill -0 $1 2> /dev/null || return 0; for p in $(desc $1) $1; do kill -KILL $p 2> /dev/null; done; }
kerr_poll() {   # kerr_poll [TAG] (Karl 11-09) a kernel error -> this gap's programs are killed at once, and again at EVERY poll
  # while the marker exists (exact7 starts a new engine per item), the running job's tree too; $O/kerr.seen marks it. The
  # first poll that sees it writes "kstop INFO ... during TAG" into gates.txt BEFORE anything is killed: every start gate
  # written from that line on (a fatal line or a lost engine the kill caused) is "seen at the stop" for decide, not a FAIL
  local p ex
  [ -e $KERR ] || return 0
  [ -e $O/kerr.seen ] || touch $O/kerr.seen
  mkdir $O/kerr.seen.d 2> /dev/null && echo "kstop INFO a kernel-error marker seen during ${1:-a step} [g13 $(date '+%m-%d %H:%M:%S')]" >> $G
  [ $ENDING = 0 ] || return 0   # (never during port_gap4.sh end: the daily starting there has B's binary)
  for p in $(our_exe_pids); do ex=$(readlink /proc/$p/exe 2> /dev/null) || continue; ours_new $p "$ex" && kill -KILL $p 2> /dev/null; done
  kill_tree "$JP"
  return 0
}
vmswap() {   # vmswap PID: its VmSwap in kB ("" when unreadable); (--mock: scratch/mock/vmswap.kB while that file exists)
  if [ $MOCK = 1 ] && [ -s $M/vmswap.kB ]; then cat $M/vmswap.kB; return 0; fi
  awk '/^VmSwap:/ {print $2}' /proc/$1/status 2> /dev/null
}
swapchk() {   # swapchk OUT: (the standing swap rule: an engine with VmSwap > 0 fails its run) every engine of this gap running
  # now (ours_new: this gap's binary, started after the open, not under 8080) with VmSwap > 0 -> one line in OUT
  local p ex kb
  for p in $(our_exe_pids); do
    ex=$(readlink /proc/$p/exe 2> /dev/null) || continue; ours_new $p "$ex" || continue
    kb=$(vmswap $p); [[ $kb =~ ^[0-9]+$ ]] && [ $kb -gt 0 ] && echo "$(date +%T) pid $p (${ex##*/}) VmSwap $kb kB" >> $1
  done
  return 0
}
gwatch() {   # gwatch FLAG OUT: every GW_S s while FLAG exists: the kernel poll, foreign GPU users >> OUT, this gap's engines' VmSwap
  local tg=$(basename ${2%.foreign}) sw=${2%.foreign}.swap
  while [ -e $1 ] && kill -0 $$ 2> /dev/null; do kerr_poll $tg; foreign | sed "s/^/$(date +%T) /" >> $2; swapchk $sw; kerr_poll $tg; sleep $GW_S; done
}
kloop() { local tg=$(basename ${1%.watching}); while [ -e $1 ] && kill -0 $$ 2> /dev/null; do kerr_poll $tg; sleep $KL_S; done; }   # (the kernel poll apart from nvidia-smi)
gpu_clear() {   # gpu_clear NAME: no foreign GPU user and no leftover engine of this gap before the start (up to 60 s)
  local i f
  for i in $(seq $GPUCLEAR_N); do
    f=$(foreign; o_=$(ours_running | tr '\n' ' '); [ -n "$o_" ] && echo "this gap's own engine(s) still running: $o_")
    [ -z "$f" ] && return 0; sleep $GPUCLEAR_S
  done
  gate foreign_$1 FAIL "not started: $(echo "$f" | head -1) still after $(( GPUCLEAR_N * GPUCLEAR_S )) s"
  return 1
}
WGP=""; KGP=""
wstart() { rm -f $FG/$1.foreign $FG/$1.swap; touch $FG/$1.watching; gwatch $FG/$1.watching $FG/$1.foreign 8>&- 9>&- < /dev/null & WGP=$!
  kloop $FG/$1.watching 8>&- 9>&- < /dev/null & KGP=$!; }
wreap() { local i; [ -n "${1:-}" ] || return 0; for i in $(seq 40); do kill -0 $1 2> /dev/null || { wait $1 2> /dev/null; return 0; }; sleep 1; done; kill $1 2> /dev/null; }   # (never blocks on a stuck nvidia-smi)
wstop() {    # one foreign GPU user seen during the step = foreign_NAME FAIL; one of this gap's engines with VmSwap > 0 =
  # swap_NAME FAIL (the standing swap rule) - either way the step is left out (INCOMPLETE, named)
  rm -f $FG/$1.watching; wreap "$WGP"; wreap "$KGP"; WGP=""; KGP=""
  [ -s $FG/$1.foreign ] && gate foreign_$1 FAIL "seen during $1 ($(wc -l < $FG/$1.foreign) sample(s)): $(head -1 $FG/$1.foreign | cut -c1-160) - left out"
  [ -s $FG/$1.swap ] && gate swap_$1 FAIL "VmSwap > 0 during $1: peak $(grep -o 'VmSwap [0-9]*' $FG/$1.swap | awk '$2 > m {m = $2} END {print m + 0}') kB ($(wc -l < $FG/$1.swap) sample(s); $(head -1 $FG/$1.swap | cut -c1-120)) - left out (an engine with VmSwap > 0 fails its run)"
  return 0
}

# ---------------------------------------------------------------- the priority rule (Karl 11-09), its override
PRIOWHY=""
prio_note() { case $1 in *"PRIORITY OVERRIDDEN"*)
  [ -n "$(gst priority_override)" ] || { gate priority_override INFO "$(echo "$1" | tail -1 | cut -c1-300)"; say "  THE PRIORITY HOLD IS OVERRIDDEN (tmp/gate0213-priority-done): the gap goes on"; };; esac; }
prio() {   # prio WHERE: 0 = go on; 1 = a find (PRIO=1: no new step, the gap ends cleanly) or one already made
  local out rc
  [ $PRIO = 1 ] && return 1
  out=$(afr priority --state $STATE --override $PRIO_DONE 2>&1); rc=$?
  case $rc in
    0) prio_note "$out"; return 0;;
    10) PRIO=1; PRIOWHY=$(echo "$out" | tail -1 | cut -c1-300)
        say "PRIORITY RULE before $1: $PRIOWHY - no new step; the gap ends (the daily back)"
        gate priority FAIL "before $1: $PRIOWHY"; return 1;;
    *) gate priority_$(echo "$1" | tr -c 'A-Za-z0-9\n' '_' | cut -c1-40) INFO "$(echo "$out" | tail -1 | cut -c1-200)"
       say "(the priority check before $1 could not read the watch state - going on; it reads it again before the next part)"
       return 0;;
  esac
}

# ---------------------------------------------------------------- one test server
left_out() { local k; for k in env fenv line fatal foreign void swap rc; do [ "$(gst ${k}_$1)" = FAIL ] && return 0; done; return 1; }
srvrun() {   # srvrun ARM TAG CONFIG RECS CMD [NGPU] [FETCHLINE]: a fresh test server (with_server.sh: cold page cache, the memory
  # guard, the shared test lock; PAID_SEARCH_KIND=test, no run id: 0 paid calls), its engine's env checked (port0211_rules.py
  # envcheck --pins: the engine AND its parent server.py; switch_rules.py armenv: the binary, the fetch keys, the parent's
  # --config), then CMD; test_cleanup (a leftover voids the start); the engine-log slice -> englog/TAG.englog; the fetch
  # start line (FETCHLINE 1, the default), the fatal lines, the client chain's rc (not 0 or none: rc_TAG FAIL, left out), the
  # VmSwap watch (swap_TAG), a kernel check. RECS = the client's record files. 1 = not started
  local arm=$1 tag=$2 cfg=$3 recs=$4 cmd=$5 ng=${6:-2} fl=${7:-1} lab=$LP-$2 L off exe eo=$EL/$2.englog rcl rcn
  ok_to_go || { say "skipped $tag (the deadline, a kernel check or the priority rule)"; gate skip_$tag INFO "skipped (deadline / kernel / priority)"; return 1; }
  prio "the start $tag" || return 1
  gpu_clear $tag || { say "$tag NOT started (a foreign GPU user, or nvidia-smi not answering)"; return 1; }
  exe=$(exe_of $cfg); L=$(elog $cfg); mkdir -p $(dirname $L); touch $L; off=$(stat -c %s $L)
  say "server $lab ($(basename $cfg))"
  # (the job in the background, JP set before the watch starts: a kernel error stops its whole tree at once)
  ( env PAID_SEARCH_KIND=test $LIB/with_server.sh $lab $cfg -- "$PY $RUE envcheck $exe $cfg --ngpu $ng --pins --gate env_$tag --gates $G && $PY $SWR armenv $exe $cfg --arm $arm --gate fenv_$tag --gates $G$MOCKENV && ${cmd//@OFF@/$off}; echo \"$tag chain rc \$?\"" 8>&- 9>&- < /dev/null > $WSO/$tag.txt 2>&1 ) &
  JP=$!
  wstart $tag
  wait $JP; JP=""
  kerr_check   # (a kernel error during the run: kfail is written before this start's own gates - they are "seen at the stop")
  grep -E "engine pid [0-9]+:|ENV CHECK|ARM ENV|ready|exited|refus|Error|GUARD|Traceback|chain rc|WARNING|tok/s| pass |fixture " $WSO/$tag.txt | cut -c1-300 | tee -a $S
  wstop $tag
  test_cleanup $lab || gate void_$tag FAIL "the run left $CLEANED behind (stopped) - the start is left out"
  tail -c +$((off + 1)) $L > $eo
  fatalchk fatal_$tag $L $off $lab
  [ "$fl" = 1 ] && swr startline $eo --gate line_$tag --gates $G | tee -a $S
  rcl=$(grep -o "$tag chain rc [0-9]*" $WSO/$tag.txt | tail -1); rcn=${rcl##* }
  gate start_$tag INFO "${rcl:-no rc line}; $(nrecs $recs) client record(s)"
  [ -n "$rcl" ] && [ "$rcn" = 0 ] || gate rc_$tag FAIL "the client chain $([ -n "$rcl" ] && echo "ended rc $rcn" || echo 'wrote no rc line (the server did not start, or the run was stopped)') - the start is left out"
  kc $tag
  return 0
}
darm() {   # darm ARM PASS: one screen pass on a fresh server of the served form (warm-up, W1-W3, the 2 agent turns, the 4
  # research replays: the 9 workloads); a left-out start's records go to speed/void/
  local a=$1 k=$2 n=$1$2 f
  fits $SCR_MIN || { say "skipped the screen $n (under $SCR_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_$n INFO "the deadline"; return 0; }
  srvrun $a $n $CF/$a.json "$SPD/${n}n.jsonl $SPD/${n}a.jsonl $SPD/${n}r.jsonl $SPD/$n.wu.jsonl" "bash $KR/abarm.sh http://127.0.0.1:8081 @OFF@ $SPD $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" || return 0
  gate pcie_$n INFO "$(ru pcie $EL/$n.englog 2> /dev/null | cut -c1-160)"
  if left_out $n; then mkdir -p $SPD/void; for f in $SPD/${n}n.* $SPD/${n}a.* $SPD/${n}r.* $SPD/$n.*; do [ -e "$f" ] && mv "$f" $SPD/void/; done; say "  the screen pass $n is left out (its start gates)"; fi
  return 0
}
bprun() {   # bprun BUILD SET PASS: Basalt's community-1 set, cold (a fresh engine), one pass; M = B, H = P; its own record file,
  # appended to cold-BUILD.jsonl only when the start is clean (else to bp90/void/)
  local b=$1 set=$2 k=$3 n=bp$1-$2-$3 cfg tree arm out
  case $b in M) arm=B; cfg=$CF/B.json; tree=$W28;; H) arm=P; cfg=$CF/P.json; tree=$W13;; esac
  fits $BP_MIN || { say "skipped Basalt $n (under $BP_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_$n INFO "the deadline"; return 0; }
  out=$BO/runs/$n.jsonl; rm -f $out
  srvrun $arm $n $cfg "$out" "$PY $B90/bp90_client.py http://127.0.0.1:8081 --label $LP-$n --sets $set --passes 1 --first-pass $k --tree $tree --out $out" || return 0
  if left_out $n; then mkdir -p $BO/void; [ -e $out ] && mv $out $BO/void/; say "  Basalt $n is left out (its start gates)"
  elif [ -s $out ]; then cat $out >> $BO/cold-$b.jsonl; fi
  return 0
}
E7OK=" "      # the exact7 runs of this gap that ran clean (their env checked, no foreign GPU user, no swap): a later pair
eok() { case "$E7OK" in *" $1 "*) return 0;; esac; return 1; }   # compares against a reference only when it is in here
e7() {   # e7 NAME CONFIG [REFNAME] [info]: exact7 at pin 2500 (LABEL $LP-NAME; REF = $LP-REFNAME's own hashes and slots); every
  # item's engine checked as it starts (envcli --mode e7 --kill: env_NAME_e7, an INFO run's infoenv_NAME_e7); the GPU and
  # kernel watch and the VmSwap watch around it (swap_e7NAME). 1 = not run, or not clean (its engines not as configured, a
  # foreign GPU user, VmSwap > 0): its pair is then not judged (INCOMPLETE)
  local n=$1 cfg=$2 ref=${3:-} info=${4:-} L=$LP-$1 jp eg tg
  eg=env_${n}_e7; tg=e7$n; [ -n "$info" ] && { eg=infoenv_${n}_e7; tg=infoe7$n; }
  fits $E7_MIN || { say "skipped exact7 $L (under $E7_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_e7$n INFO "the deadline"; return 1; }
  prio "exact7 $n" || return 1
  gpu_clear $tg || { say "exact7 $L NOT started (a foreign GPU user)"; return 1; }
  say "exact7 $L ($(basename $cfg)${ref:+ against $LP-$ref}, pin 2500)"
  ( if [ -n "$ref" ]; then PIN_CACHE=2500 REF=$LP-$ref $LIB/exact7.sh $L $cfg; else PIN_CACHE=2500 $LIB/exact7.sh $L $cfg; fi 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- < /dev/null &
  jp=$!; JP=$jp
  wstart $tg
  br envcli $(exe_of $cfg) $cfg --job $jp --mode e7 --kill --gate $eg --gates $G 2>&1 | tail -2 | tee -a $S
  wait $jp; JP=""
  kerr_check
  wstop $tg
  kill_ours
  kc $tg || return 1
  [ "$(gst $eg)" = PASS ] && [ "$(gst foreign_$tg)" != FAIL ] && [ "$(gst swap_$tg)" != FAIL ] || return 1
  E7OK="$E7OK$n "
}
e7g() { ru e7gate $S $LP-$1 --gate $2 --gates $G ${3:-} | tee -a $S; }
ndiff() {   # ndiff DIR_A DIR_B: "differing files of all" over A's first.* logit files
  local nd=0 nf=0 f
  for f in $1/first.*; do [ -e "$f" ] || continue; nf=$((nf + 1)); cmp -s $f $2/$(basename $f) || nd=$((nd + 1)); done
  echo "$nd $nf"
}
pfy_part() {   # pf_yardstick long40 on PH (envcli --mode pfy --kill); the KL rules against gap 8's references
  local jp nd nf l2 l3 x
  fits $PFY_MIN || { say "skipped long40 (under $PFY_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_pfy INFO "the deadline"; return 0; }
  gpu_clear pfy || { say "long40 NOT started (a foreign GPU user)"; return 0; }
  say "3 KL: pf_yardstick long40 on PH (the port's CLI form); kernel_rule2 + kernel_rule3 against gap 8's references"
  for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
  ( $P $LIB/guard.py pfy$LP -- $P -I $KR/pf_yardstick.py run $CF/PH.json $Y/p213 --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy p213: /" | tee -a $S ) 8>&- 9>&- < /dev/null &
  jp=$!; JP=$jp
  wstart pfy
  br envcli $(exe_of $CF/PH.json) $CF/PH.json --job $jp --mode pfy --kill --gate env_pfy --gates $G 2>&1 | tail -2 | tee -a $S
  wait $jp; JP=""
  kerr_check
  wstop pfy
  kill_ours
  kc pfy || return 0
  if [ -f $Y/p213/index.json ] && [ "$(gst env_pfy)" = PASS ] && [ "$(gst foreign_pfy)" != FAIL ] && [ "$(gst swap_pfy)" != FAIL ]; then
    read nd nf <<< "$(ndiff $Y/p213 $Y16/x28h)"; gate logits_vs_p028x INFO "$nd of $nf first-token logit files differ from gap 16's x28h"
    if [ -f $Y11/p211/index.json ]; then read nd nf <<< "$(ndiff $Y/p213 $Y11/p211)"; gate logits_vs_p0211 INFO "$nd of $nf first-token logit files differ from the v0.2.11 gate's p211"; fi
    nice -n 19 $P $KR/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands p213 8>&- 9>&- < /dev/null 2>&1 | tee $O/kl-p213.txt | tee -a $S
    nice -n 19 $P -I $KR/kernel_rule3.py $Y --ref ref --refs unfused,cpushare --cands p213 8>&- 9>&- < /dev/null 2>&1 | tee $O/kl3-p213.txt | tee -a $S
    l2=$(grep -E "^p213 +top-1" $O/kl-p213.txt | tr -s ' ' | cut -c1-160); l3=$(grep -E "^p213 +KL mean" $O/kl3-p213.txt | tr -s ' ' | cut -c1-170)
    echo "$l2" | grep -q -- '-> PASS' && gate kl2_p213 PASS "$l2" || gate kl2_p213 FAIL "${l2:-no line}"
    echo "$l3" | grep -q -- '-> PASS' && gate kl3_p213 PASS "$l3" || gate kl3_p213 FAIL "${l3:-no line}"
  fi
}
single_part() {   # INFO: the single-card fallback (configs/P0213x-single.json's test form, the RTX 5080 alone): one start, its
  # checks (envcheck --ngpu 1 --pins, armenv, the start lines, fatal, #3961's line, lossless), 3 short requests
  local sl
  [ -s $CF/SG.json ] || { gate skip_SG INFO "no configs/P0213x-single.json: no single-card start"; return 0; }
  [ -s $SGO/single-plan.json ] || { gate skip_SG INFO "no single-card plan"; return 0; }
  fits $SG_MIN || { say "the single-card start (INFO) skipped: under $SG_MIN min to the deadline"; gate skip_SG INFO "the deadline: $(( $(left) / 60 )) min left, $SG_MIN needed"; return 0; }
  say "6 INFO the single-card fallback: one start of P0213x-single (the RTX 5080 alone), 3 requests of 512 tokens at the standard sampling"
  srvrun P SG $CF/SG.json "$SGO/single.jsonl" "$PY $FXC http://127.0.0.1:8081 $SGO/single.jsonl --plan $SGO/single-plan.json --label $LP-SG" 1 0 || return 0
  sl=$(slog $LP-SG)
  ru startlines $EL/SG.englog $sl --gate lines_SG --gates $G | tee -a $S
  [ -n "$sl" ] && ru lost $sl --gate lost_SG --gates $G | tee -a $S
  gr single $O --gate single_SG --gates $G | tee -a $S
  return 0
}

# ---------------------------------------------------------------- refusals, the signal trap, the end
DRYREF=0
refuse() {   # refuse busy|hard WHY - before the gap, nothing changed. busy: exit 1 (the starter retries); hard: an alert, exit 6
  if [ $DRY = 1 ]; then DRYREF=$((DRYREF + 1)); say "DRY RUN: the real run would REFUSE ($1) here: $2"; return 1; fi
  echo "not started ($1): $2 - nothing changed" > $O/result.txt
  say "NOT STARTED ($1): $2 - nothing changed"
  if [ "$1" = hard ]; then
    notes_line "not started: $2 - nothing changed"
    alert "v0.2.13 baseline gate not started" "$(echo "$2" | cut -c1-120); nothing changed"; exit 6
  fi
  exit 1
}
hold() {   # the priority rule before the gap: final (exit 8), an alert, nothing changed
  if [ $DRY = 1 ]; then DRYREF=$((DRYREF + 1)); say "DRY RUN: the real run would be HELD by the priority rule here: $1"; return 1; fi
  echo "HELD by the priority rule (Karl 11-09), before the gap: $1 - nothing changed; the day-one work goes first (override: tmp/gate0213-priority-done with a dated reason line, only on Karl's word)" > $O/result.txt
  say "HELD (priority rule): $1 - nothing changed"
  notes_line "HELD by the priority rule before the gap: $1 - nothing changed; day-one work first"
  alert "v0.2.13 baseline gate held" "open Qwen4 Flash weights were found: the day-one work goes first; the gap did not start"
  exit 8
}
on_signal() {   # stopped from outside: result.txt, the NOTES line and the alert FIRST (a 90-s systemd stop timeout must not lose
  # them), then the test server and this gap's leftovers (never during port_gap4.sh end; never an engine from before the gap)
  trap - TERM INT HUP
  say "SIGNAL: the driver was stopped"
  wdg_stop
  kill_tree "$JP"
  local st
  if [ $ENDING = 1 ]; then
    st="the driver was stopped while port_gap4.sh end was running: do NOT run end a second time blindly - check first whether 8080 serves the daily, whether tmp/port-gap.lockpid and the research-queue hold are gone"
  elif [ $GAPOPEN = 1 ]; then
    st="the gap may still be open (tmp/port-gap.lockpid): close it with work/r22/port_gap4.sh end"
  else
    st="the gap was not open"
    if grep -qF "$HOLDTAG" $HOLD 2> /dev/null; then
      if [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; then st="the gap may have opened as it was stopped (lock held): close it with work/r22/port_gap4.sh end"; GAPOPEN=1
      else rm -f $HOLD; st="the gap was not open (this gap's research-queue hold lifted)"; fi
    fi
  fi
  local l80="8080 is NOT listening"; ss -H -ltn "( sport = :8080 )" 2> /dev/null | grep -q . && l80="8080 is listening"
  st="$st; $l80"
  echo "INTERRUPTED: $st; nothing switched" > $O/result.txt
  say "INTERRUPTED: $st"
  notes_line "INTERRUPTED: $st; nothing switched"
  alert "v0.2.13 baseline gate interrupted" "the driver was stopped; $( [ $ENDING = 1 ] && echo 'during the end: check 8080 before anything else' || { [ $GAPOPEN = 1 ] && echo 'the gap may still be open' || echo 'the gap was not open'; }); $l80"
  if [ $GAPOPEN = 1 ] && [ $ENDING = 0 ] && [ $T0T -gt 0 ]; then test_cleanup "$LP-" || true; lock_sweep; fi
  exit 7
}
finish() { wdg_stop; echo "$1" > $O/result.txt; say "RESULT: $1"; notes_line "$1"; exit $2; }
after_checks() {   # CPU only (after port_gap4.sh end): lossless, #3961's line, P's start lines, the continuations
  local sl k s r h m
  cat $EL/P[123].englog $EL/bpH-*.englog > $O/P-slices.log 2> /dev/null
  if [ -s $O/P-slices.log ]; then
    CFG=$CF/P.json TREE=strata-r23p0213 ELOG=$O/P-slices.log nice -n 19 $PATCHTEST lossless 8>&- 9>&- < /dev/null 2>&1 | grep -E "PASS|FAIL" | tail -6 > $O/lossless.txt
    grep -q 'cfg: PASS' $O/lossless.txt && ! grep -q FAIL $O/lossless.txt && gate lossless PASS "cfg + this gate's P engine-log slices clean" || gate lossless FAIL "$(tail -1 $O/lossless.txt | cut -c1-140)"
  fi
  if [ -s $EL/SG.englog ]; then
    CFG=$CF/SG.json TREE=strata-r23p0213 ELOG=$EL/SG.englog nice -n 19 $PATCHTEST lossless 8>&- 9>&- < /dev/null 2>&1 | grep -E "PASS|FAIL" | tail -2 > $SGO/lossless.txt
    gate lossless_SG INFO "$(tail -1 $SGO/lossless.txt | cut -c1-160)"
  fi
  sl=$(for k in 1 2 3; do slog $LP-P$k; for s in decode pp16k pp64k; do slog $LP-bpH-$s-$k; done; done | tr '\n' ' ')
  if [ -n "${sl// /}" ]; then ru lost $sl --gate lost_answers --gates $G | tee -a $S; fi
  for k in 1 2 3; do
    [ -f $SPD/P$k.startlog ] || continue
    ru startlines $SPD/P$k.startlog $SPD/P$k?.englog $(slog $LP-P$k) --gate startlines_P --gates $G | tee -a $S; break
  done
  if ls $SPD/P[123][nar].englog > /dev/null 2>&1; then
    nice -n 19 $P $KR/gap9_verdicts.py cont $SPD/P[123][nar].englog 8>&- 9>&- < /dev/null > $O/cont-P.txt 2>&1
    r=$(grep -oE '[0-9]+ hits, [0-9]+ misses' $O/cont-P.txt | tail -1); h=$(echo "$r" | grep -oE '^[0-9]+'); m=$(echo "$r" | grep -oE '[0-9]+ misses' | grep -oE '[0-9]+')
    if [ -n "$h" ] && [ "$h" -ge 1 ] && [ "${m:-1}" = 0 ]; then gate cont_P PASS "continuations: $r"; else gate cont_P FAIL "continuations: ${r:-none found}"; fi
  fi
}
after_gap() {   # CPU only, nice 19, after the end: the checks, the speed table, Basalt's report, the decision
  local labs
  after_checks
  labs=$(ls $SPD/*.jsonl 2> /dev/null | xargs -n1 basename 2> /dev/null | sed 's/\.jsonl$//' | grep -E '^[BP][123][nar]$' | sort | tr '\n' ' ')
  [ -n "$labs" ] && nice -n 19 $P $BA/scripts/abreport.py --dir $SPD $labs 8>&- 9>&- < /dev/null > $O/speed-table.md 2>&1
  if ls $BO/cold-*.jsonl > /dev/null 2>&1; then
    BP90_NAME_H="the v0.2.13 port (P0213x-af2's test form)" nice -n 19 $P -I $B90/bp90_report.py $BO 8>&- 9>&- < /dev/null > $BO/report.md 2>&1 || true
    sed -i 's/P021m (served)/the daily (P028x test form, the fetch build)/g' $BO/report.md 2> /dev/null
  fi
  gr decide $O --swdir $SWO --quiet > $O/decide.out 2>&1 || say "gate0213_rules.py decide failed - rerun it by hand ($PY $GR decide $O): $(tail -1 $O/decide.out)"
  [ -f $O/decision.txt ] && tee -a $S < $O/decision.txt > /dev/null
  return 0
}
end_gap() {   # the lock sweep, then port_gap4.sh end, once (the daily back on 8080: nothing of it changed)
  [ $GAPOPEN = 1 ] || return 0
  if [ $KFAIL = 1 ]; then   # (Karl 11-09: any new Xid or kernel error -> stop at once, the daily back, an alert; kwatch NOT cleared)
    say "KERNEL ERROR during the gap: stopping and bringing the daily back; kwatch is not cleared"
    [ -e $KERR ] && head -c 300 $KERR | sed 's/^/  /' | tee -a $S > /dev/null
    lock_sweep
    ENDING=1
    if $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
      ENDING=0; GAPOPEN=0
      alert "v0.2.13 baseline gate stopped: kernel error" "a kernel error during the baseline gate; it stopped at once and the daily is back on 8080; kwatch not cleared"
    else   # (ENDING stays 1: end has run and failed; no second end, no cleanup)
      alert "v0.2.13 baseline gate: kernel error, 8080 not back" "a kernel error during the baseline gate and port_gap4 end failed: 8080 and the research queue need a look"
    fi
    after_gap
    finish "KERNEL ERROR during the gap - stopped at once, $([ $GAPOPEN = 0 ] && echo 'the daily back on 8080' || echo '8080 NOT back'); kwatch not cleared; partial results in decision.txt: $(cat $O/result-line.txt 2> /dev/null)" 3
  fi
  lock_sweep
  say "port_gap4.sh end: the daily back on 8080 - nothing switched"
  ENDING=1
  if ! $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"
    alert "v0.2.13 baseline gate: 8080 not back" "port_gap4 end failed after the baseline gate; 8080 and the research queue need a look"
    after_gap
    finish "port_gap4.sh end FAILED - 8080 and the research queue need a look; the results are in decision.txt: $(cat $O/result-line.txt 2> /dev/null)" 4
  fi
  ENDING=0; GAPOPEN=0
}

# ================================================================ 0 before the gap (no GPU; 8080 untouched)
: > $G
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
say "v0.2.13 BASELINE GATE (work/r23/gate-0213/gap-gate0213.sh, Karl 11-10): the pinned-off port ($P_SHA) against P028x - exact7 + long40 on the CLI forms, the 3-pass screen and Basalt's speed rule on the served forms (B = the daily $B_SHA, P = the port), the decode line, the single-card fallback (INFO) - measurements only, nothing switches$([ $DRY = 1 ] && echo ' [DRY RUN]')$([ $MOCK = 1 ] && echo ' [MOCK RUN: every tool a stub under scratch/mock]')"
# -- the order of the queue and the priority rule first (cheap; a hold is final)
build_active() { if [ $MOCK = 1 ]; then [ "${MOCK_BUILD_ACTIVE:-0}" = 1 ]; return; fi; systemctl --user is-active -q $BUILD_UNIT 2> /dev/null; }
build_active && refuse busy "the build unit $BUILD_UNIT is still active (the stock v0.2.13 engine is being built)"
hold_foreign() { [ -e $HOLD ] && ! grep -qF "$HOLDTAG" $HOLD 2> /dev/null; }   # the research queue held by someone else
hold_foreign && refuse busy "the research queue is held by someone else (bench2.hold: $(head -c 120 $HOLD 2> /dev/null | tr '\n' ' '))"
PR=$(afr priority --state $STATE --override $PRIO_DONE); PRC=$?; say "  $PR"
case $PRC in 0) prio_note "$PR";; 10) hold "$(echo "$PR" | cut -c1-300)";; *) refuse busy "the priority rule cannot be checked: $PR";; esac
if [ $MOCK = 0 ] && [ $DRY = 0 ]; then
  systemctl --user is-active -q post-p5-chain 2> /dev/null && refuse busy "the post-Phase-5 chain is still running"
  preflight   # (the cheap busy checks before the long pre-gap work; again right before the gap opens)
fi
# -- today's switch gap stands for this build (the parts this gate leaves out)
if [ $MOCK = 1 ]; then SHNOW=${MOCK_P_SHA:-$P_SHA}; HNOW=${MOCK_HEAD:-$(git -C $W13 rev-parse HEAD 2> /dev/null)}
else SHNOW=$(sha12 $E13/strata 2> /dev/null); HNOW=$(git -C $W13 rev-parse HEAD 2> /dev/null); fi
SR=$(gr switchref $SWO --sha "${SHNOW:-none}" --head "${HNOW:-none}" --gate switchref --gates $G 2>&1); say "  $(echo "$SR" | tail -1 | cut -c1-400)"
[ "$(gst switchref)" = PASS ] || refuse hard "today's switch gap does not stand for this build: $(echo "$SR" | tail -1 | cut -c1-200)"
# -- the builds, the engines, the trees, the files
if [ $MOCK = 0 ]; then
  for f in $GR $MK $SWR $AFR $RU $FR $WS/work/r23/basalt_rules.py $KR/g17_rules.py $WS/work/r23/sampled-qwen/sq.py $KR/port_gap4.sh \
           $KR/abarm.sh $KR/pf_yardstick.py $KR/kernel_rule2.py $KR/kernel_rule3.py $KR/gap9_verdicts.py $B90/bp90_client.py \
           $B90/bp90_report.py $BA/scripts/abreport.py $BA/scripts/abrun.py $WL $LIB/with_server.sh $LIB/exact7.sh $LIB/run.sh \
           $LIB/guard.py $LIB/kcheck.sh $LIB/p0_table.py $SRVSH $STOPMON $NOTE $PATCHTEST $FXC $W28/serve/server.py \
           $W13/serve/server.py $WST/serve/server.py $C/P028x.json $C/P0213x-af2.json $P13 $X $S28 $GGUF $BPD/conv.ids \
           $BPD/struct.ids $BPD/prose.ids $Y8/ref/index.json $Y8/unfused/index.json $Y8/cpushare/index.json $Y16/x28h/index.json \
           $SWO/rules.txt; do
    [ -f $f ] || refuse hard "missing: $f"
  done
  [ -d $PROMPT_DIR ] || refuse hard "missing the prompt folder $PROMPT_DIR"
  [ -x $E28/strata ] && [ "$(sha12 $E28/strata)" = $X28_SHA ] || refuse hard "engine-r22p028x is not P028x's CLI reference ($X28_SHA)"
  [ -x $EAF/strata ] && [ "$(sha12 $EAF/strata)" = $B_SHA ] || refuse hard "engine-r23afetch is not the daily's binary ($B_SHA)"
  if [ ! -x $E13/strata ] || [ "$(sha12 $E13/strata)" != $P_SHA ] || [ "$(cut -c1-12 $E13/SHA256 2> /dev/null)" != $P_SHA ] \
     || ! grep -q "^v0.2.13 + [0-9]* commits (branch r23-port0213 $HNOW)" $E13/SOURCE 2> /dev/null; then
    refuse hard "engine-r23p0213 is not the recorded build of r23-port0213 ${HNOW:0:12} ($P_SHA, its SHA256 file, its SOURCE)"
  fi
  [ -z "$(GIT_OPTIONAL_LOCKS=0 git -C $W13 status --porcelain --untracked-files=no 2> /dev/null)" ] || refuse hard "strata-r23p0213 is dirty"
  V13=$(git -C $WS/strata rev-parse 'v0.2.13^{commit}' 2> /dev/null)
  if [ ! -x $EST/strata ]; then refuse hard "engine-v0213stock/strata is missing (work/r23/build-port0213.sh stock; its log: $(tail -1 $BUILD_LOG 2> /dev/null | cut -c1-120))"
  elif [ "$(sha12 $EST/strata)" != "$(cut -c1-12 $EST/SHA256 2> /dev/null)" ] || ! grep -q "^stock v0.2.13 ($V13," $EST/SOURCE 2> /dev/null \
       || [ -z "$V13" ] || [ "$(git -C $WST rev-parse HEAD 2> /dev/null)" != "$V13" ] \
       || [ "$(sha12 $WST/build/strata 2> /dev/null)" != "$(sha12 $EST/strata)" ]; then
    refuse hard "engine-v0213stock is not the recorded stock v0.2.13 build (its SHA256 file, SOURCE = v0.2.13 ${V13:0:12}, strata-v0213stock at it, = strata-v0213stock/build/strata)"
  fi
  [ -z "$(GIT_OPTIONAL_LOCKS=0 git -C $WST status --porcelain --untracked-files=no 2> /dev/null)" ] || refuse hard "strata-v0213stock is dirty"
  grep -qE "^SERVED_KNOWN=\"[^\"]*$B_SHA" $KR/port_gap4.sh || refuse hard "work/r22/port_gap4.sh does not know the daily's engine $B_SHA"
  for p in $(pgrep -x ninja); do case $(readlink /proc/$p/cwd 2> /dev/null) in $W13|$W13/*|$WST|$WST/*) refuse busy "a ninja build runs in $(readlink /proc/$p/cwd) (pid $p)";; esac; done
  free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
  [ "${free:-0}" -ge 10 ] || refuse hard "only ${free} GB free on results/"
  [ -x $E28S/strata ] || say "  (engine-r22s028t missing: the stock 0.2.8 check cannot run if PH is not 7/7 - e7_upstream then INCOMPLETE)"
  gate build_x PASS "engine-r23p0213 $(sha12 $E13/strata 2> /dev/null) = $(head -1 $E13/SOURCE 2> /dev/null | cut -c1-120)"
  gate build_stock PASS "engine-v0213stock $(sha12 $EST/strata 2> /dev/null) = $(head -1 $EST/SOURCE 2> /dev/null | cut -c1-110)"
  n8=$(cat $W13/build-configure.log $WST/build-configure.log 2> /dev/null | grep -c 'windows hold up to 8 rows')
  [ "$n8" = 2 ] && gate build8 PASS "the port and stock v0.2.13: verify windows hold up to 8 rows" || gate build8 FAIL "$n8 of 2 configure logs say 8 rows"
  say "  files, engines (B $B_SHA, P $P_SHA, x28h $X28_SHA, stock $(sha12 $EST/strata 2> /dev/null)), the trees and port_gap4.sh checked"
else
  [ "${MOCK_STOCK_MISSING:-0}" = 1 ] && refuse hard "engine-v0213stock/strata is missing (mock)"
  gate build_x PASS "(mock) engine-r23p0213 $P_SHA"; gate build_stock PASS "(mock) engine-v0213stock"
  [ "${MOCK_BUILD8_FAIL:-0}" = 1 ] && gate build8 FAIL "(mock) 1 of 2 configure logs say 8 rows" || gate build8 PASS "(mock) 8-row windows"
fi
[ "$(gst build8)" = PASS ] || refuse hard "a configure log does not say 8-row windows: the baseline cannot pass"
# -- the rules: selftest (stored and synthetic data, under OUTDIR or the dry run's scratch)
ST_=$O/selftest-rules; [ $DRY = 1 ] && ST_=$GD/scratch/selftest-dry
if [ $MOCK = 0 ] || [ "${MOCK_SELFTEST:-0}" = 1 ]; then
  gr selftest $ST_ > $O/selftest-rules.out 2>&1 || refuse hard "gate0213_rules.py selftest failed ($(tail -1 $O/selftest-rules.out | cut -c1-160))"
  say "  $(tail -1 $O/selftest-rules.out)"; rm -rf $ST_
fi
# -- the configs, the pins
MC=$(nice -n 19 $PY $MK make $CF --log-dir $LOGD $NOSHA --gate cfg --gates $G 8>&- 9>&- < /dev/null 2>&1 | tail -1); say "  $(echo "$MC" | cut -c1-400)"
[ "$(gst cfg)" = PASS ] || refuse hard "the gate's configs do not check out: $(echo "$MC" | cut -c1-200)"
gr pins $P13 --gate pins --gates $G | tee -a $S
gr pins $CF/PH.json --gate pins_h --gates $G | tee -a $S
[ "$(gst pins)" = PASS ] && [ "$(gst pins_h)" = PASS ] || refuse hard "the port's pins are not in P0213x.json / PH: the baseline cannot pass"
ru fence4 $W13 --gate fence4 --gates $G | tee -a $S   # (port0211's / gap 17's: the port's own parser, CPU, seconds)
[ "$(gst fence4)" = PASS ] || refuse hard "fence4 fails on strata-r23p0213's parser: the baseline cannot pass"
# -- INFO from stored runs (no GPU): the port with fetch=2 against the daily, both stored at pin 2500
if [ -f $PROF/$E7STORED_P-x-112k.out ] && [ -f $PROF/$E7STORED_B-x-112k.out ]; then
  ru e7cmp $E7STORED_P $E7STORED_B --info --gate e7_af2_stored --gates $G | tail -2 | tee -a $S
fi
# -- the single-card plan (CPU: the fixtures rendered with P's tree, cut to 512 tokens)
if [ -s $CF/SG.json ]; then
  if [ $MOCK = 1 ]; then cp $M/fixtures-plan.json $SGO/fixtures-plan.json
  else swr fixtures $SGO/fixtures-plan.json --tree $W13 --data $BPD --gguf $GGUF > $SGO/fixtures-plan.out 2>&1 || say "  (the single-card plan could not be made: $(tail -1 $SGO/fixtures-plan.out | cut -c1-160) - the INFO start is skipped)"; fi
  [ -s $SGO/fixtures-plan.json ] && { gr singleplan $SGO/fixtures-plan.json $SGO/single-plan.json | sed 's/^/  /' | tee -a $S; }
fi
gr rules $O/rules.txt | sed 's/^/  /' | tee -a $S
say "  estimate: ~81 min with 8080 down (open 1, exact7 6 sets 20 (+3.3 with stock 0.2.8), long40 9, the screen 22, Basalt 18 cold runs 24, the single card 3, the end 2; +7 with P0213G_AF2_E7=1); deadline $MAXM min for new steps after the gap opens; 8080 down ~2.6 h at most ($((MAXM + WORST_OVER)) min)"
if [ $DRY = 1 ]; then
  say "DRY RUN: would check that no other gap / test lock / model server but the daily ($B_SHA) / 8081 listener is there, that the kernel-log watcher runs, and a kernel check"
  say "DRY RUN: the gap would now run:"
  say "  GAP_MAX_MIN=$((MAXM + WORST_OVER)) $KR/port_gap4.sh begin \"$HOLDTAG: ...\"; the watchdog (open at deadline + 20 min: one critical alert); the priority rule; deadline $MAXM min after it opens"
  for e in "s213 ST" "p213off OFF s213" "x28h $X" "p213a PH x28h" "p213b PH p213a" "nov2 NOV2 p213a"; do
    set -- $e; c=$2; [ -f "$c" ] || c=$CF/$2.json
    say "  2 exact7: PIN_CACHE=2500 ${3:+REF=$LP-$3 }$LIB/exact7.sh $LP-$1 $c (+ br envcli --mode e7 --kill)"
  done
  say "    e7gate: e7_release (p213off), e7_vs_p028x (p213a), guards ($PROF/$LP-p213a-x-math.out), e7_repeat (p213b), e7_v2 (nov2); e7_upstream (s028 = $S28 vs s213) only when p213a is not 7/7; INFO e7cmp $LP-p213a $E7P211"
  say "    INFO (P0213G_AF2_E7=$AF2E7, only with $(( 2 * E7_MIN + REST_MIN )) min left): exact7 $LP-da2 $CF/B.json, $LP-pa2 $CF/P.json against da2"
  say "  3 $P $LIB/guard.py pfy$LP -- $P -I $KR/pf_yardstick.py run $CF/PH.json $Y/p213 --set long40 (+ br envcli --mode pfy --kill); kernel_rule2.py / kernel_rule3.py $Y --ref ref --refs unfused,cpushare --cands p213"
  for k in 1 2 3; do case $k in 2) o="P B";; *) o="B P";; esac; for a in $o; do say "  4 screen $a$k: with_server.sh $LP-$a$k $CF/$a.json -- \"envcheck --pins && armenv --arm $a && abarm.sh http://127.0.0.1:8081 OFF $SPD $a$k ...\"; startline; fatal"; done; done
  for k in 1 2 3; do case $k in 2) o="H M";; *) o="M H";; esac; for b in $o; do say "  5 Basalt $b pass $k: with_server.sh $LP-bp$b-{decode,pp16k,pp64k}-$k $CF/$([ $b = M ] && echo B || echo P).json -- \"envcheck && armenv && bp90_client.py ... --sets SET --first-pass $k\""; done; done
  say "  6 INFO (only with $SG_MIN min left): with_server.sh $LP-SG $CF/SG.json -- \"envcheck --ngpu 1 --pins && armenv --arm P && fixtures_client.py http://127.0.0.1:8081 $SGO/single.jsonl --plan $SGO/single-plan.json\"; startlines / lost / lossless (INFO)"
  say "  7 the lock sweep; $KR/port_gap4.sh end; kcheck; then (CPU) patchtest.sh lossless, port0211_rules.py lost / startlines, gap9_verdicts.py cont, abreport.py, bp90_report.py, gate0213_rules.py decide $O; result.txt, NOTES.md, ntfy"
  say "DRY RUN done: $DRYREF refusal(s) would stop the real run now"
  exit 0
fi
# -- right before the gap: the busy checks again, the kernel
preflight
if [ $MOCK = 0 ]; then
  [ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || refuse hard "the kernel-log watcher is not running"
  [ -e $KERR ] && refuse hard "a kernel-error marker is present (tmp/r19/KERNEL_ERROR): Karl clears kwatch"
  $LIB/kcheck.sh g13-pre > /dev/null 8>&- 9>&- < /dev/null || refuse hard "a kernel check fails before the gap"
else
  [ -e $KERR ] && refuse hard "a kernel-error marker is present (mock)"
fi
build_active && refuse busy "the build unit $BUILD_UNIT is active again"
hold_foreign && refuse busy "the research queue is held by someone else (bench2.hold: $(head -c 120 $HOLD 2> /dev/null | tr '\n' ' '))"
PR=$(afr priority --state $STATE --override $PRIO_DONE); PRC=$?
case $PRC in 0) prio_note "$PR";; 10) hold "$(echo "$PR" | cut -c1-300)";; *) refuse busy "the priority rule cannot be checked: $PR";; esac
trap on_signal TERM INT HUP

# ================================================================ 1 the gap
GAP_MAX_MIN=$((MAXM + WORST_OVER)) $KR/port_gap4.sh begin "$HOLDTAG: the v0.2.13 port against P028x (Karl 11-10; measurements only, nothing switches)" 8>&- 9>&- < /dev/null 2>&1 | tee -a $S
[ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null || { grep -qF "$HOLDTAG" $HOLD 2> /dev/null && rm -f $HOLD; refuse busy "the gap did not open (our hold removed)"; }
GAPOPEN=1; T0=$(date +%s); T0T=$(uptk); DEADLINE=$(( T0 + MAXM * 60 ))
PRE=$( { for x in $ENGNAMES; do pgrep -x $x; done; } | sort -un | tr '\n' ' ')   # (never this gap's to stop)
echo "$T0 $(date -Is)" > $O/t0.txt
[ -n "$PRE" ] && say "engine processes running as the gap opened (8080's, stopping; never stopped by this gap): $(pre_alive)"
if [ $MOCK = 0 ]; then   # the watchdog: still open 20 min past the deadline -> one critical alert (a hang the deadline cannot cut)
  ( exec 8>&- 9>&- < /dev/null > /dev/null 2>&1; sleep $(( MAXM * 60 + 1200 )); kill -0 $$ 2> /dev/null && [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null \
      && notify-send -a Strata -u critical "v0.2.13 baseline gate overrun" "the baseline gate is still open 20 min past its deadline: 8080 may be down" ) &
  WDG=$!
elif [ -n "${MOCK_WDG_S:-}" ]; then
  ( exec 8>&- 9>&- < /dev/null > /dev/null 2>&1; sleep $MOCK_WDG_S; kill -0 $$ 2> /dev/null && [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null \
      && echo "mock watchdog: the gap is still open past its deadline" >> $M/wdg.log ) &
  WDG=$!
fi
if [ $MOCK = 0 ]; then for i in $(seq 60); do [ -z "$(engines_left)" ] && [ "$(memav)" -ge 40 ] && break; sleep 2; done; fi
say "8080 down: engines left:$(engines_left | sed 's/^/ /;s/^ $/ none/') MemAvailable $(memav) GB; deadline $(date -d @$DEADLINE '+%H:%M') ($MAXM min)"
kc open || { end_gap; }
if [ -n "$(engines_left)" ]; then
  EL5="$(engines_left)"; PA=$(pre_alive)
  say "engine processes still running 120 s after 8080 stopped: $EL5 - nothing run; from before the gap (left alone, never killed): ${PA:-none}"
  gate skip_all INFO "engines left after 8080 stopped"
  end_gap
  finish "not run: engines still running after 8080 stopped ($EL5; from before the gap, left alone: ${PA:-none}); nothing measured, the daily back" 5
fi
prio "the first step (the gap had waited in port_gap4.sh begin)"

# ---- 2 exact7 at pin 2500 on the CLI forms: the release first, the port against P028x, its repeat, v2; INFO pairs
if [ $KFAIL = 0 ] && prio "exact7"; then
  say "2 exact7 at pin 2500 (CLI forms, no STRATA_ADAPT_FETCH): stock v0.2.13, every switch off = the release FIRST, x28h, the port = P028x, its repeat, v2 on = off"
  e7 s213 $CF/ST.json && e7 p213off $CF/OFF.json s213 && e7g p213off e7_release
  e7 x28h $X && e7 p213a $CF/PH.json x28h && e7g p213a e7_vs_p028x
  if [ -f $PROF/$LP-p213a-x-math.out ]; then
    if grep -q 'strata patch guards: 7 checked, 0 off' $PROF/$LP-p213a-x-math.out; then
      gate guards PASS "$(grep -m1 -o 'strata patch guards: 7 checked, 0 off[^;]*' $PROF/$LP-p213a-x-math.out)"
    else gate guards FAIL "$(grep -m1 -o 'strata patch guards: [^;]*' $PROF/$LP-p213a-x-math.out || echo 'no patch-guard line')"; fi
  fi
  eok p213a && e7 p213b $CF/PH.json p213a && e7g p213b e7_repeat
  if [ -n "$(gst e7_vs_p028x)" ] && [ "$(gst e7_vs_p028x)" != PASS ]; then
    if [ -x $E28S/strata ] || { [ $MOCK = 1 ] && [ -d $E28S ]; }; then
      say "the port's CLI form is not exact7-identical to P028x: did upstream itself move (stock 0.2.8 vs stock v0.2.13, both pinned)?"
      eok s213 && e7 s028 $S28 s213 && e7g s028 e7_upstream
    else gate skip_s028 INFO "engine-r22s028t is missing: e7_upstream not run"; fi
  fi
  eok p213a && e7 nov2 $CF/NOV2.json p213a && e7g nov2 e7_v2
  [ -f $PROF/$LP-p213a-x-112k.out ] && [ -f $PROF/$E7P211-x-112k.out ] && ru e7cmp $LP-p213a $E7P211 --info --gate e7_vs_p0211 --gates $G | tail -2 | tee -a $S
  if [ "$AF2E7" = 1 ]; then
    if fits $(( 2 * E7_MIN + REST_MIN )); then
      say "  INFO: the served forms' pair at pin 2500 (B = the daily, P = the port, both STRATA_ADAPT_FETCH=2)"
      e7 da2 $CF/B.json "" info && e7 pa2 $CF/P.json da2 info && e7g pa2 e7_af2 --info
    else gate skip_e7_af2 INFO "the INFO pair not run: $(( $(left) / 60 )) min left, $(( 2 * E7_MIN + REST_MIN )) needed with the required rest"; fi
  else gate skip_e7_af2 INFO "the INFO pair not run (P0213G_AF2_E7=0, the default: the same pair is stored - e7_af2_stored)"; fi
fi
# ---- 3 long40 and the KL rules
if [ $KFAIL = 0 ] && prio "long40"; then pfy_part; fi
# ---- 4 the screen: B P x 3 passes in turned order, the served forms
if [ $KFAIL = 0 ] && prio "the screen"; then
  say "4 the screen: B P x 3 passes in turned order (B P / P B / B P) on the served forms"
  for k in 1 2 3; do
    case $k in 2) order="P B";; *) order="B P";; esac
    for a in $order; do { [ $KFAIL = 1 ] || [ $PRIO = 1 ]; } && break 2; darm $a $k; done
  done
fi
# ---- 5 Basalt's fixtures, cold, 3 passes: M = B, H = P
if [ $KFAIL = 0 ] && prio "Basalt"; then
  say "5 Basalt's community-1 fixtures, cold, 3 passes in turned order (M H / H M / M H): M = B (the daily), H = P (the port); decode / pp16k / pp64k"
  for k in 1 2 3; do
    case $k in 2) order="H M";; *) order="M H";; esac
    for b in $order; do for set in decode pp16k pp64k; do { [ $KFAIL = 1 ] || [ $PRIO = 1 ]; } && break 3; bprun $b $set $k; done; done
  done
fi
# ---- 6 INFO: the single-card fallback
if [ $KFAIL = 0 ] && prio "the single-card start"; then single_part; fi

# ---- 7 the lock sweep, the daily back, the decision
DOWN_WORK=$(( ($(date +%s) - T0) / 60 ))
say "the gap's work took $DOWN_WORK min (deadline $MAXM)"
end_gap
DOWN=$(( ($(date +%s) - T0) / 60 ))
KA=ok; $LIB/kcheck.sh g13-after > /dev/null 8>&- 9>&- < /dev/null || KA=FAILED
[ $KA = ok ] && gate kcheck_after PASS "the kernel check after the daily came back" || gate kcheck_after FAIL "the kernel check after the daily came back failed (see kwatch.log)"
say "8080 was down for about $DOWN min; kernel check after the gap: $KA"
[ $KA = ok ] || alert "v0.2.13 baseline gate: kernel check" "the kernel check after the baseline gate failed (8080 is back); see kwatch.log"
after_gap
VD=$(head -2 $O/verdict.txt 2> /dev/null | tr '\n' ' ' || echo "decision missing - rerun gate0213_rules.py decide")
RL=$(cat $O/result-line.txt 2> /dev/null || echo "$VD")
if [ $PRIO = 1 ]; then
  alert "v0.2.13 baseline gate stopped" "open Qwen4 Flash weights were found during the gap: it ended early, the daily is back; the day-one work goes first"
  finish "STOPPED by the priority rule (Karl 11-09: day-one work first; $PRIOWHY); the daily back after $DOWN min, nothing switched; what ran: $RL" 8
fi
note "v0.2.13 baseline gate done" "Measurements only, nothing switched; 8080 back after $DOWN min. $(echo "$RL" | cut -c1-160)"
finish "DONE (measurements only, nothing switched; 8080 down $DOWN min; kernel check after: $KA): $RL" 0
