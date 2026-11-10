#!/bin/bash
# gap-switch0213.sh - r23 (written 2026-11-10 at the desk, NOT RUN; only --dry-run and the --mock test ran): THE v0.2.13
# PORT'S SWITCH CHECKS (Karl 11-10: "the v0.2.13 port's switch checks, on the fetch-patch engine (web search end-to-end,
# the served-output comparison against P028x, the C++ parity tests for the files our patches change, the sampled test,
# and how often the lost-answer guard fires) ... Nothing switches; report the verdict."). The plan and its rules:
# results/r23/port-0213/SWITCH-CHECKS-PLAN-1110.md; the rules as implemented, frozen into the gap's rules.txt before any
# engine starts: work/r23/switch-gap/switch_rules.py's docstring and its switches (CITE_FORM, C2_NOREF_FORM). B = the
# daily as served (configs/P028x.json's test form: x28h + U + STRATA_ADAPT_FETCH=2 on engine-r23afetch 153ce47d3ef0,
# server strata-r22p028x); P = the port (configs/P0213x-af2.json's test form, engine-r23p0213 639dfb1b7042, server
# strata-r23p0213). MEASUREMENTS ONLY: 8080 stays the daily, nothing switches, nothing is built, no config of the served
# setup changes. Started by work/r23/switch-gap/switch-start.sh (a user unit) as a snapshot copy; every path is absolute.
# Usage: gap-switch0213.sh [--dry-run | --mock]; any other argument: nothing runs (exit 2). One instance at a time
# (tmp/switch-gap.driver.pid: a second one exits 9 before it touches anything).
#   0 BEFORE THE GAP (no GPU; 8080 untouched). It REFUSES (nothing changed) - exit 1 = busy (the starter retries), exit 6 =
#     a hard refusal (an alert), exit 8 = HELD by the priority rule (final, an alert) - unless:
#     - the build unit build-p0213-switch is inactive and its log says "switchtests: build rc 0" at the port's head, every
#       switchtests program is in strata-r23p0213/build-switch and (real run) ninja -n has nothing to do there; the tree
#       is on 6dd81ecd1 and clean; engine-r23p0213/SOURCE names it; the research queue is not held by anyone else;
#     - THE PRIORITY RULE (Karl 11-09, afetch_rules.py priority): the Qwen4 watch has no open Flash repo with weights - a
#       find HOLDS the gap (exit 8) unless tmp/switch0213-priority-done has a dated reason line (Karl's word only);
#     - no other gap, no held test lock, no model server but 8080's daily (153ce47d3ef0), nothing on 8081; nvidia-smi
#       answers within 20 s; the post-Phase-5 chain is not running; the kernel-log watcher runs and a kernel check passes;
#     - the files are there (the rules, the clients, the harness and its spec, the stored exact7 x28h-e7a, node, Basalt's
#       fixture ids); the two engines are 153ce47d3ef0 / 639dfb1b7042; port_gap4.sh knows 153ce47d3ef0; >= 5 GB free;
#     - switch_rules.py's selftest and forms pass; the arm configs check out (arms + cfgcheck); the C1 program list
#       (ctestlist, from build-switch's CTestTestfile.cmake) is complete; the prompts render to the same ids through B's
#       and P's server code (render); the C2 / C4 / fixture plans are written; the clients' selftests pass; the sampled
#       harness's sq.py selftest, sq_client.py selftest, sq.py selftest-real --spec <the run's spec copy> pass; sq.py
#       derive of the spec copy passes, its configs = the gap's debug arms (cfgcheck --sampled) and sq.py rule writes
#       sampled/rule.txt; the rules and switches are frozen into rules.txt - all BEFORE any engine start;
#     - webpath: the strata_web path of both trees - SearXNG only, or (11-10, both trees) a PAID PATH (the Exa / Tavily
#       fallback): then C4 runs only if the paid budget check passes (switch_rules.py paidcheck through the providers' own
#       counter code: every available provider has >= 25 % of its month + 10 calls left), else "C4 NOT RUN: paid budget"
#       (INFO; the verdict cannot be PASS) and the gap goes on without it;
#     - C1's CPU parts (nice 19, 8080 serving): the CPU ctest entries (CUDA_VISIBLE_DEVICES empty), patch_guard_test, the
#       server test suite of strata-r23p0213/serve with node first on PATH, node --check app.js. (coordinator 11-10) Not
#       PASS -> C1 FAIL / NOT DECIDED with the failing tests named (gate c1_pregap); the gap still opens for the rest.
#   1 port_gap4.sh begin (the research queue held after its running question, the test lock, 8080 down; GAP_MAX_MIN = the
#     worst case below); the engines gone and MemAvailable >= 40 GB (120 s at most; engines still there: the gap ends,
#     exit 5 - named, never killed); PRE = the engine processes running as the gap opened (8080's, stopping: B has the
#     daily's binary): no cleanup ever stops one of them; a kernel check; the watchdog; the priority rule again
#   2 C1 the GPU parity programs (ctest, build-switch's registered entries, both GPUs, a time cap cut at the deadline) +
#     qsa_prompt_attn_parity + prefill_fused_iq_test --edge --no-timing - before any server
#   3 C1 the read-back start VF (P + STRATA_ADAPT_FETCH_VERIFY=1 + STRATA_ADAPT_CHECKRES=1, K 2, budget 300 s), sq.py
#     verify (once more after C2 when not decided)
#   4 C2 served outputs: B1 (B-dbg), B2 (B-dbg again), P (P-dbg), c2_client.py each; switch_rules.py c2compare
#   5 C3 the sampled test: R1 (= B, K 8), X (= P, K 8), R2 (= B, K 4), sq.py ids, the scorer (guard.py + sq.py score
#     --max-min cut to the minutes left, sq.py envwatch --kill, a watchdog), sq.py decide - all or nothing (its minimum)
#   6 C4 web search: B then P (c4_web.py, "strata_web": true) - only when webpath allowed it and 127.0.0.1:8888 listens;
#     on the paid path the budget is checked again right before (paid-start.json); THE HARD LIMIT: the C4 test servers
#     run with PAID_SEARCH_KIND=test / PAID_SEARCH_RUN (one id) / PAID_SEARCH_RUN_CAP B 5, P 10 (paid_budget.py's own
#     run cap), checked in the server's environment by c4_web.py before it sends anything (gate penv_webARM); c4_web.py's
#     stop at 5 per arm / 10 in all is the soft one (the requests not sent: not run); paid-end.json after. Every other
#     test server runs with PAID_SEARCH_KIND=test and no run id (0 paid calls)
#   7 C5 our workload on P: the 9-workload screen (abarm.sh) and the three chat fixtures (fixtures_client.py); then the
#     screen on B (the INFO speed); INFO: exact7 of P against the stored x28h-e7a at pin 2500
#   8 switch_rules.py decide -> verdict.txt / decision.txt / .json; the lock sweep; port_gap4.sh end (the daily back); a
#     kernel check; result.txt, a NOTES.md line, a non-urgent ntfy note. NOTHING SWITCHES: Karl decides.
# The priority rule is checked again before each part and each of its starts: a find stops new steps, the decision is
# written on what ran and the gap ends cleanly (8080 back): exit 8 and an alert.
# Every test server: no foreign GPU user before it (60 s) or during it (a 5 s watch; nvidia-smi not answering within 20 s
# counts as not clear); its engine's env checked before it measures (port0211_rules.py envcheck --pins: the engine AND its
# parent server.py; switch_rules.py armenv: the binary, the fetch / debug keys in the engine and its server, the server's
# --config; the sampled starts also sq.py envcheck); the fetch start line; the fatal-line check; after it, however it
# ended, test_cleanup (a leftover voids the start); its server log recorded for C5; a kernel check. CLI jobs (exact7, the
# scorer) are checked as they start by /proc/PID/exe (br envcli / sq.py envwatch --kill). Children run with 8>&- 9>&- and
# stdin from /dev/null; processes are found by PID, pid file, /proc/PID/exe or exact name (pgrep -x) only.
# TIME with 8080 down (estimates: the shape gap's flash_next parity 11-09, STEPS-adaptfetch.txt, the 11-09 gaps): open ~2,
# GPU parity ~8, VF ~4, C2 3 starts ~6, C3 R1 / X ~3.7 each + R2 ~2.2 + ids 0.5 + the scorer ~12 (80 samples) + decide
# 0.5 = ~23, C4 2 starts ~12 (0 when the budget refuses it), C5 + INFO screen P ~3.7 + fixtures ~1.5 + screen B ~3.7 = ~9, exact7
# ~3.5, decide + close ~4 -> ~72 min (~60 without C4; the plan's estimate 90-110). Deadline SW_MAX_MIN (default 150) minutes
# after the gap opens for any new step; a step starts only if its minimum fits (parity 10, VF 7, a C2 start 4, the
# sampled part 33: R1 / X 5, R2 3, ids 1, scorer 18, decide 1; a C4 start 6, a screen 5, the fixtures 3, exact7 5).
# WORST CASE ~2.9 h with 8080 down (175 min = GAP_MAX_MIN): the deadline 150 + the longest overrun of a step started
# inside its minimum (~7) + the decision ~2 + the lock sweep and port_gap4.sh end ~8 + the open's engine wait ~2, rounded up.
# THE KERNEL-ERROR POLICY (Karl 11-09): any new Xid or kernel error (kwatch's tmp/r19/KERNEL_ERROR, polled every 2 s while
# a test engine, a parity program, exact7 or the scorer runs: this gap's programs - and the running job's tree - are killed
# at once, and again at every poll while the marker exists; checked before every step; or a kernel check failing) stops
# the gap at once: the lock sweep, port_gap4.sh end (the daily back), a critical alert, the result "KERNEL ERROR during
# the gap - stopped at once, ...", exit 3. kwatch is NOT cleared.
# Exit 0 done (the verdict is in verdict.txt / decision.txt), 1 busy (refused, nothing changed), 2 a bad argument, 3 a
# kernel error / kernel check failure, 4 port_gap4.sh end failed, 5 not run: engines still running after 8080 stopped,
# 6 hard refusal (alert), 7 stopped by a signal (alert), 8 the
# priority rule, 9 another instance runs.
# --dry-run: the pre-gap checks that read only (a refusal is printed and the plan goes on), switch_rules.py's selftest,
# the arms, the program list, webpath, render, the plans and the frozen rules (all under work/r23/switch-gap/scratch/),
# then the plan of every command, printed; no lock, no GPU query, no kernel check, no sampled-harness command, no C1 CPU
# test, no ctest, no port_gap4, no request to any port.
# --mock: (work/r23/switch-gap/gap-mock-test.sh only) every tool a stub under work/r23/switch-gap/scratch/mock; the rules
# script runs for real on the stubs' synthetic data; never kills a real process, never queries the GPU (nvidia-smi is a
# stub), writes no NOTES.md / alert / ntfy. MOCK_* variables steer the stubs.
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock descriptor reaches a child (this script holds none itself)
WS=/home/USER/ai-speed-testing/strata-compare
case ${1:-} in ""|--dry-run|--mock) ;; *) echo "usage: gap-switch0213.sh [--dry-run | --mock] (got '${1:-}'): nothing run"; exit 2;; esac
SG=$WS/work/r23/switch-gap
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
MOCK=0; [ "${1:-}" = --mock ] && MOCK=1
M=$SG/scratch/mock
[ $MOCK = 1 ] && { [ -x $M/lib/with_server.sh ] || { echo "--mock needs work/r23/switch-gap/gap-mock-test.sh's stubs"; exit 2; }; }
# ---- one instance at a time: before anything touches the output folder; the pid file is not inside it
PIDF=$WS/tmp/switch-gap.driver.pid; [ $MOCK = 1 ] && PIDF=$M/driver.pid
alive_driver() { [ -n "$1" ] && kill -0 "$1" 2> /dev/null && tr '\0' ' ' < /proc/$1/cmdline 2> /dev/null | grep -q 'gap-switch0213'; }
if [ $DRY = 0 ]; then
  for try in 1 2; do
    ( set -o noclobber; echo $$ > $PIDF ) 2> /dev/null && break
    op=$(cat $PIDF 2> /dev/null)
    if alive_driver "$op"; then echo "another gap-switch0213.sh (pid $op) is running: not started, nothing touched"; exit 9; fi
    [ $try = 1 ] && rm -f $PIDF || { echo "the pid file $PIDF could not be taken: not started, nothing touched"; exit 9; }
  done
  [ "$(cat $PIDF 2> /dev/null)" = "$$" ] || { echo "the pid file $PIDF is not this driver's: not started, nothing touched"; exit 9; }
  trap '[ "$(cat $PIDF 2> /dev/null)" = "$$" ] && rm -f $PIDF' EXIT
fi
export RB_CACHE=$WS/tmp/r23                       # (before env.sh: its tool caches and TMPDIR go there)
[ $DRY = 1 ] && export RB_CACHE=$SG/scratch/rb-cache
[ $MOCK = 1 ] && export RB_CACHE=$M/rb-cache
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE PROF_SAMPLING EXE ENVX NSYS COLD
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
for v in $(compgen -e | grep '^SQ_'); do unset "$v"; done                                    # nor a stray sampled-client setting
for v in $(compgen -e | grep '^PAID_SEARCH'); do unset "$v"; done   # (review M7) nor a paid-search run id or cap from outside
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; PY="$P -I -B"; SWR=$SG/switch_rules.py; AFR=$WS/work/r23/afetch-gap/afetch_rules.py
RU=$WS/work/r23/port0211_rules.py; FR=$WS/work/r23/basalt_fix_rules.py; KR=$WS/work/r22; LIB=$WS/bringup/lib
Q=$WS/work/r23/sampled-qwen; C2C=$SG/c2_client.py; C4C=$SG/c4_web.py; FXC=$SG/fixtures_client.py; SPEC=$SG/spec-port0213.json
O=$WS/results/r23/port-0213/switch-gap
[ $DRY = 1 ] && O=$SG/scratch/gap-dry
W28=$WS/strata-r22p028x; W13=$WS/strata-r23p0213; BT=$W13/build-switch
EAF=$WS/engine-r23afetch; E13=$WS/engine-r23p0213; E28=$WS/engine-r22p028x
PROF=$WS/bringup/out/logs/prof; E7REF=x28h-e7a; SLOGDIR=$WS/bringup/out/logs
LOCKPID=$WS/tmp/port-gap.lockpid; HOLD=/home/USER/ai/deep-research/tmp/bench2.hold
NOTE=$WS/configs/usability/bin/ntfy-note.py
STATE=$WS/work/qwen4-kit/hfwatch/state.json; PRIO_DONE=$WS/tmp/switch0213-priority-done
SRVSH=$LIB/srv.sh; STOPMON=$WS/scripts/stopmon.sh
BUILD_UNIT=build-p0213-switch; BUILD_LOG=$WS/logs/r23/build-p0213-switch.log
NODE_DIR=/home/USER/.unsloth/node/bin; NODE=$NODE_DIR/node
GGUF=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf; MTPRT=$WS/strata-v0115/mtp/rt
BPD=/home/USER/ai-speed-testing/basalt-pr90-data; WL=/home/USER/ai-speed-testing/basalt-ab/scripts/workloads.json
PAID_TOOLS=/home/USER/ai/deep-research/tools; PAID_STOP=10; PAID_ARM_STOP=5   # (the counter code; C4's soft stops)
PAID_CAP_B=5; PAID_CAP_P=10   # (review S1 / M6) the HARD limit: paid_budget.py's run cap in each C4 test server, one run id
B_SHA=153ce47d3ef0; P_SHA=639dfb1b7042; PORT_HEAD=6dd81ecd1
HOLDTAG="v0.2.13 switch checks"
MAXM=${SW_MAX_MIN:-150}
PAR_MIN=10; PAR_CAP=25; VF_MIN=7; C2_MIN=4; SQ8_MIN=5; SQ4_MIN=3; IDS_MIN=1; SCORE_MIN=18; DEC_MIN=1; WEB_MIN=6
SCR_MIN=5; FX_MIN=3; E7_MIN=5
SQ_REST=$(( 2 * SQ8_MIN + SQ4_MIN + IDS_MIN + SCORE_MIN + DEC_MIN ))   # 33: the sampled part (all or nothing)
WORST_OVER=25
NVSMI_T=20; GPUCLEAR_N=12; GPUCLEAR_S=5; GW_S=5; KL_S=2; KGRACE_N=10; KGRACE_S=2; KTERM_S=10; SERVE_T=2400
ENGNAMES="strata strata-host"; LOCKF=$WS/tmp/gpu-test.lock
KERR=$WS/tmp/r19/KERNEL_ERROR   # kwatch's marker of a kernel error (never taken from the environment, never cleared here)
LP=r23sw$(date +%m%d%H%M)
MOCKENV=""
if [ $MOCK = 1 ]; then   # every tool, folder and lock file under scratch/mock; the real configs, spec and trees are only read
  O=$M/out; LIB=$M/lib; KR=$M/kr; Q=$M/sq; FR=$M/fr/basalt_fix_rules.py; RU=$M/ru/port0211_rules.py; LOCKPID=$M/lockpid
  HOLD=$M/hold; NOTE=$M/lib/ntfy-note.py; STATE=$M/state.json; PRIO_DONE=$M/switch0213-priority-done; PROF=$M/prof
  SRVSH=$M/lib/srv.sh; STOPMON=$M/lib/stopmon.sh; SLOGDIR=$M/slogs; C2C=$M/clients/c2_client.py; C4C=$M/clients/c4_web.py
  FXC=$M/clients/fixtures_client.py; BT=$M/tree/build-switch; NODE=$M/bin/node; BUILD_UNIT=switch-mock-no-such-unit
  BUILD_LOG=$M/build-switch.log; MOCKENV=" --mock-env $M/engine-env.json"; NVSMI_T=1; GPUCLEAR_N=2; GPUCLEAR_S=1
  GW_S=0.3; KL_S=0.3; KGRACE_N=3; KGRACE_S=0.2; KTERM_S=1; KERR=$M/kernel_error; SERVE_T=60
  ENGNAMES=swmock-eng; EAF=$M/engines/engine-r23afetch; E13=$M/engines/engine-r23p0213; E28=$M/engines/engine-r22p028x
  LOCKF=$M/gpu-test.lock; PAID_TOOLS=$M/paidtools   # (fake engines: never named strata*; fake counter modules)
  export PATH=$M/bin:$PATH        # (nvidia-smi and ctest are stubs there)
fi
CF=$O/configs; S=$O/summary.txt; G=$O/gates.txt; EL=$O/englog; FG=$O/foreign; SPD=$O/speed; SQO=$O/sampled
C1O=$O/c1; C2O=$O/c2; C4O=$O/c4; C5O=$O/c5; WSO=$O/with_server
PREV=""
if [ $DRY = 0 ] && [ $MOCK = 0 ] && [ -n "$(find $EL $SPD $C2O $C4O $C1O/gpu -mindepth 1 -print -quit 2> /dev/null; ls -d $SQO/VF $SQO/R1 $SQO/X $SQO/R2 2> /dev/null)" ]; then
  PREV=$O-prev-$(date +%m%d-%H%M%S); mv $O $PREV                                 # the rules judge only this attempt's files
fi
[ $DRY = 1 ] && rm -rf $O
[ $MOCK = 1 ] && rm -rf $O
mkdir -p $O $CF $EL $FG $SPD $C1O/cpu $C1O/gpu $C2O $C4O $C5O $WSO
[ $DRY = 0 ] && [ $MOCK = 0 ] && mkdir -p $WS/tmp/r23 $WS/logs
: > $C5O/serverlogs.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [r23sw $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }   # a gate's last status ("" = not written)
swr() { nice -n 19 $PY $SWR "$@" 8>&- 9>&- < /dev/null; }       # switch_rules.py (CPU only)
afr() { nice -n 19 $PY $AFR "$@" 8>&- 9>&- < /dev/null; }        # afetch_rules.py (its priority rule)
br() { $PY $FR br "$@" 8>&- 9>&- < /dev/null; }                   # basalt_rules.py's subcommands (envcli, e7gate)
sq() { nice -n 19 $PY $Q/sq.py "$@" 8>&- 9>&- < /dev/null; }      # the sampled harness's CPU subcommands
mocked() { [ $DRY = 1 ] || [ $MOCK = 1 ]; }
alert() { mocked && { say "(dry run / mock: would alert: $1 - $2)"; return 0; }; notify-send -a "Strata gaps" -u critical "$1" "$2" 2> /dev/null || true; }
note() { mocked && { say "(dry run / mock: would send the ntfy note: $1 - $2)"; return 0; }; $NOTE "$1" "$2" >> $S 2>&1 8>&- 9>&- < /dev/null || say "(the ntfy note did not go out)"; }
notes_line() { mocked && { say "(dry run / mock: would add to NOTES.md: $1)"; return 0; }; printf -- '- %s v0.2.13 SWITCH CHECKS (Karl 11-10; work/r23/switch-gap/gap-switch0213.sh, results/r23/port-0213/switch-gap/): %s\n' "$(date '+%m-%d %H:%M')" "$1" >> $WS/NOTES.md; }
KFAIL=0; PRIO=0; GAPOPEN=0; ENDING=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 )); WDG=""; KILLED=0; JP=""
PRE=""; T0T=0; CLK=$(getconf CLK_TCK)   # T0T = the gap's open in clock ticks since boot (the processes' start ticks: the same clock)
kc() { $LIB/kcheck.sh "r23sw-$1" > /dev/null 8>&- 9>&- < /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; gate kfail FAIL "after $1"; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
kerr_check() {   # (Karl 11-09) a kernel error recorded by kwatch: no further step (end_gap then stops at once, the daily back)
  [ -e $KERR ] && [ $KFAIL = 0 ] && { KFAIL=1; say "a kernel error is recorded ($(head -c 160 $KERR 2> /dev/null | tr '\n' ' ')): no further step"; gate kfail FAIL "a kernel error is recorded (kwatch not cleared)"; }
  return 0
}
ok_to_go() { kerr_check; [ $KFAIL = 0 ] && [ $PRIO = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # a step starts only if its minimum ends before the deadline
cap() { local c=$(( $1 * 60 )) l=$(( $(left) - 30 )); [ $l -lt $c ] && c=$l; [ $c -lt 60 ] && c=60; echo $c; }   # a run's cap, cut at the deadline
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
ours() { case "$1" in $EAF/*|$E13/*|$E28/*|$BT/*) return 0;; esac; return 1; }   # this gap's binaries (B's is also the daily's)
uptk() { awk -v c=$CLK '{printf "%d", $1 * c}' /proc/uptime; }
ptick() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || { echo 0; return 0; }; s=${s##*) }; set -- $s; echo ${20}; }
our_exe_pids() { find /proc/[0-9]*/exe -maxdepth 0 \( -lname "$EAF/*" -o -lname "$E13/*" -o -lname "$E28/*" -o -lname "$BT/*" \) 2> /dev/null | cut -d/ -f3 | sort -un; }
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
kill_bt() {   # a parity program of this gap still running after its part (build-switch's binaries, ours_new only)
  local p ex n=0
  [ $GAPOPEN = 1 ] && [ $ENDING = 0 ] || return 0
  for p in $(our_exe_pids); do ex=$(readlink /proc/$p/exe 2> /dev/null) || continue; case $ex in $BT/*) ours_new $p "$ex" && kill -KILL $p 2> /dev/null && n=$((n + 1));; esac; done
  [ $n = 0 ] || say "  stopped $n parity program(s) left after the run"
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
preflight() {   # the reviewed rule (gap-afetch.sh): no measurement on the GPU lock, no other gap, no model server but 8080's daily
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
kerr_poll() {   # (Karl 11-09; afetch-adopt's review fix) a kernel error -> this gap's programs are killed at once, and again at
  # EVERY poll while the marker exists (exact7 / ctest start new ones), the running job's tree too; $O/kerr.seen marks it
  local p ex
  [ -e $KERR ] || return 0
  [ -e $O/kerr.seen ] || touch $O/kerr.seen
  [ $ENDING = 0 ] || return 0   # (never during port_gap4.sh end: the daily starting there has B's binary)
  for p in $(our_exe_pids); do ex=$(readlink /proc/$p/exe 2> /dev/null) || continue; ours_new $p "$ex" && kill -KILL $p 2> /dev/null; done
  kill_tree "$JP"
  return 0
}
gwatch() { while [ -e $1 ] && kill -0 $$ 2> /dev/null; do kerr_poll; foreign | sed "s/^/$(date +%T) /" >> $2; kerr_poll; sleep $GW_S; done; }
kloop() { while [ -e $1 ] && kill -0 $$ 2> /dev/null; do kerr_poll; sleep $KL_S; done; }   # (the kernel poll apart from nvidia-smi)
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
wstart() { rm -f $FG/$1.foreign; touch $FG/$1.watching; gwatch $FG/$1.watching $FG/$1.foreign 8>&- 9>&- < /dev/null & WGP=$!
  kloop $FG/$1.watching 8>&- 9>&- < /dev/null & KGP=$!; }
wreap() { local i; [ -n "${1:-}" ] || return 0; for i in $(seq 40); do kill -0 $1 2> /dev/null || { wait $1 2> /dev/null; return 0; }; sleep 1; done; kill $1 2> /dev/null; }   # (never blocks on a stuck nvidia-smi)
wstop() {    # one foreign GPU user seen during the start = foreign_NAME FAIL (the start is left out)
  rm -f $FG/$1.watching; wreap "$WGP"; wreap "$KGP"; WGP=""; KGP=""
  [ -s $FG/$1.foreign ] && gate foreign_$1 FAIL "seen during $1 ($(wc -l < $FG/$1.foreign) sample(s)): $(head -1 $FG/$1.foreign | cut -c1-160) - left out"
  return 0
}
watchdog() {   # watchdog JOB MINUTES NAME: past MINUTES the engine in the job's own tree is stopped by PID
  local j=$1 m=$2 n=$3 t p q
  t=$(( $(date +%s) + m * 60 ))
  while kill -0 $j 2> /dev/null; do
    if [ $(date +%s) -ge $t ]; then
      for p in $( { for x in $ENGNAMES; do pgrep -x $x; done; } | sort -un); do
        q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != $j ]; do q=$(ppid_of $q); done
        [ "$q" = $j ] && kill -TERM $p 2> /dev/null && echo "watchdog: $n ran past $m min - its engine (pid $p) was stopped" >> $SQO/$n.watchdog
      done
      return 0
    fi
    sleep 5
  done
}

# ---------------------------------------------------------------- the priority rule (Karl 11-09), its override
PRIOWHY=""
prio_note() { case $1 in *"PRIORITY OVERRIDDEN"*)
  [ -n "$(gst priority_override)" ] || { gate priority_override INFO "$(echo "$1" | tail -1 | cut -c1-300)"; say "  THE PRIORITY HOLD IS OVERRIDDEN (tmp/switch0213-priority-done): the gap goes on"; };; esac; }
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
left_out() { local k; for k in env fenv envsq line fatal foreign void; do [ "$(gst ${k}_$1)" = FAIL ] && return 0; done; return 1; }
srvrun() {   # srvrun ARM TAG CONFIG RECS CMD [ENVSPEC]: a fresh test server (ENVSPEC: VAR=VALUE words for its server; every
  # one runs with PAID_SEARCH_KIND=test and, unless ENVSPEC gives one, no run id: paid_budget.py allows it 0 paid calls) (with_server.sh: cold page cache, the memory guard, the
  # shared test lock), its engine's env checked (the engine and its server.py), then CMD; test_cleanup (a leftover voids
  # the start); the engine-log slice -> englog/TAG.englog; the fetch start line, the fatal lines, its server log for C5,
  # a kernel check. RECS = the client's record files (their lines = its requests, for C5). Exit 1 = not started
  local arm=$1 tag=$2 cfg=$3 recs=$4 cmd=$5 lab=$LP-$2 L off exe eo=$EL/$2.englog sl_
  ok_to_go || { say "skipped $tag (the deadline, a kernel check or the priority rule)"; gate start_$tag INFO "skipped (deadline / kernel / priority)"; return 1; }
  gpu_clear $tag || { say "$tag NOT started (a foreign GPU user, or nvidia-smi not answering)"; return 1; }
  exe=$(exe_of $cfg); L=$(elog $cfg); mkdir -p $(dirname $L); touch $L; off=$(stat -c %s $L)
  say "server $lab ($(basename $cfg))"
  # (the job in the background, JP set before the watch starts: a kernel error stops its whole tree at once)
  ( env PAID_SEARCH_KIND=test ${6:-} $LIB/with_server.sh $lab $cfg -- "$PY $RU envcheck $exe $cfg --ngpu 2 --pins --gate env_$tag --gates $G && $PY $SWR armenv $exe $cfg --arm $arm --gate fenv_$tag --gates $G$MOCKENV && ${cmd//@OFF@/$off}; echo \"$tag chain rc \$?\"" 8>&- 9>&- < /dev/null > $WSO/$tag.txt 2>&1 ) &
  JP=$!
  wstart $tag
  wait $JP; JP=""
  grep -E "engine pid [0-9]+:|ENV CHECK|ARM ENV|ready|exited|refus|Error|GUARD|Traceback|chain rc|WARNING|budget|done:" $WSO/$tag.txt | cut -c1-300 | tee -a $S
  wstop $tag
  test_cleanup $lab || gate void_$tag FAIL "the run left $CLEANED behind (stopped) - the start is left out"
  tail -c +$((off + 1)) $L > $eo
  fatalchk fatal_$tag $L $off $lab
  swr startline $eo --gate line_$tag --gates $G | tee -a $S
  sl_=$(slog $lab); echo "$tag $arm $lab ${sl_:-none} $(nrecs $recs)" >> $C5O/serverlogs.txt
  gate start_$tag INFO "$(grep -o "$tag chain rc [0-9]*" $WSO/$tag.txt | tail -1 || echo 'no rc line'); $(nrecs $recs) client record(s)"
  kc $lab
  return 0
}
sqarm() {   # sqarm ARM [BUDGET_S]: one sampled arm (the derived cfg/ARM.json): both env checks + sq.py envcheck, sq_client.py;
  # a leftover voids the start (its folder moves to void-ARM-*, so the harness cannot use it)
  local arm=$1 bud=${2:-} kind=B
  case $arm in X|VF) kind=P;; esac
  srvrun $kind sq$arm $SQO/cfg/$arm.json "$SQO/$arm/sampled.jsonl" "$PY $Q/sq.py envcheck $SQO $arm && SQ_SPEC=$SQO/spec.json SQ_ARM=$arm SQ_LABEL=$LP-sq$arm SQ_ELOG_BASE=@OFF@${bud:+ SQ_BUDGET_S=$bud} $PY $Q/sq_client.py http://127.0.0.1:8081 $SQO/$arm" || return 1
  if [ "$(gst void_sq$arm)" = FAIL ] && [ -d $SQO/$arm ]; then mv $SQO/$arm $SQO/void-$arm-$(date +%H%M%S); fi
  if [ -s $SQO/envcheck-$arm.txt ]; then
    tail -1 $SQO/envcheck-$arm.txt | grep -q '^ENV CHECK OK' && gate envsq_sq$arm PASS "$(tail -1 $SQO/envcheck-$arm.txt | cut -c1-200)" \
      || gate envsq_sq$arm FAIL "$(tail -1 $SQO/envcheck-$arm.txt | cut -c1-200)"
  fi
  return 0
}
VFV=""; VFDONE=0; VFTRIES=0
vf_part() {   # the read-back start: VF, then sq.py verify; the verdict read from verify-VF.json. Neither PASS nor FAIL (not
  # started, voided, a foreign GPU user, a crash): VFDONE=0, tried once more (the first try's FAIL gates marked RETRIED)
  local vrc k
  VFDONE=1; VFTRIES=$((VFTRIES + 1))
  if [ $VFTRIES = 2 ]; then
    for k in env_sqVF fenv_sqVF envsq_sqVF line_sqVF fatal_sqVF void_sqVF foreign_sqVF; do [ "$(gst $k)" = FAIL ] && gate $k RETRIED "try 1 FAIL; the read-back start tried again"; done
    [ -d $SQO/VF ] && mv $SQO/VF $SQO/void-VF-try1-$(date +%H%M%S); rm -f $SQO/verify-VF.json $SQO/envcheck-VF.txt
  fi
  sqarm VF 300 || true
  sq verify $SQO VF > $SQO/verify.out 2>&1; vrc=$?
  VFV=$(jget $SQO/verify-VF.json "['verdict']" 2> /dev/null) || VFV=""
  [ "$VFV" = PASS ] && left_out sqVF && VFV="NOT DECIDED (VF's start gates failed)"
  say "  read-back VF (try $VFTRIES): ${VFV:-no verify-VF.json} ($(tail -1 $SQO/verify.out | cut -c1-200); sq.py verify exit $vrc)"
  gate readback_VF $(case $VFV in PASS) echo PASS;; FAIL) echo FAIL;; *) echo NOT-DECIDED;; esac) "try $VFTRIES: verify-VF.json ${VFV:-missing}; sq.py verify exit $vrc"
  if [ "$VFV" != PASS ] && [ "$VFV" != FAIL ] && [ $VFTRIES -lt 2 ]; then VFDONE=0; say "  the read-back start is tried once more later"; fi
}
direct() {   # direct DIR NAME SECONDS WATCH ENVSPEC CMD...: one program run directly (no ctest entry); a line in DIR/direct.txt.
  # WATCH (not -): the GPU watch around it, started after JP is set (its kernel-error poll can then stop the job's tree)
  local d=$1 n=$2 t=$3 w=$4 ev=$5 rc t1 st; shift 5
  t1=$(date +%s)
  ( env $ev timeout --kill-after=20 $t "$@" 8>&- 9>&- < /dev/null > $d/direct-$n.log 2>&1 ) & JP=$!
  [ "$w" = - ] || wstart $w
  wait $JP; rc=$?; JP=""
  [ "$w" = - ] || wstop $w
  case $rc in 0) st=PASS;; 77) st=SKIP;; 124|137) st=FAIL; rc="$rc(timeout ${t} s)";; *) st=FAIL;; esac
  echo "$n $st rc=$rc $(( $(date +%s) - t1 )) s ($*)" >> $d/direct.txt
}
ctest_run() {   # ctest_run DIR ENVSPEC SECONDS WATCH [PREFIX...]: build-switch's registered entries named in DIR/names.txt
  # (their args, env, timeout and skip code apply) -> DIR/ctest.log + junit.xml; WATCH as direct's
  local d=$1 ev=$2 t=$3 w=$4 re rc; shift 4
  re=$(paste -sd'|' $d/names.txt)
  ( env $ev "$@" timeout --kill-after=30 $t ctest --test-dir $BT -R "^($re)\$" --timeout 300 --no-tests=error --output-junit $d/junit.xml \
      8>&- 9>&- < /dev/null > $d/ctest.log 2>&1 ) & JP=$!
  [ "$w" = - ] || wstart $w
  wait $JP; rc=$?; JP=""
  [ "$w" = - ] || wstop $w
  say "  ctest $(basename $d) rc $rc: $(grep -E 'tests passed|tests failed' $d/ctest.log | tail -1)"
}
par_gpu() {   # C1's GPU parity programs, in the gap before any server (the shape gap's parity form)
  local d=$C1O/gpu t
  fits $PAR_MIN || { say "the GPU parity programs do not fit ($(( $(left) / 60 )) min left, $PAR_MIN needed)"; gate skip_par INFO "the deadline"; return 0; }
  gpu_clear par || { say "the GPU parity programs NOT started (a foreign GPU user)"; return 0; }
  t=$(cap $PAR_CAP)
  say "2 C1 the GPU parity programs: $(wc -l < $d/names.txt) ctest entries of build-switch (both GPUs, cut at ${t} s) + $(echo "$DIRECT_GPU_NAMES" | wc -w) direct runs"
  ctest_run $d "CUDA_VISIBLE_DEVICES=$GPUS" $t par
  : > $d/direct.txt
  if fits 2; then direct $d qsa_prompt_attn_parity $(cap 5) par "CUDA_VISIBLE_DEVICES=$GPUS" $BT/qsa_prompt_attn_parity; else echo "qsa_prompt_attn_parity NOTRUN deadline" >> $d/direct.txt; fi
  if fits 2; then direct $d prefill_fused_iq_test_edge $(cap 10) par "CUDA_VISIBLE_DEVICES=$GPUS" $BT/prefill_fused_iq_test --edge --no-timing; else echo "prefill_fused_iq_test_edge NOTRUN deadline" >> $d/direct.txt; fi
  kill_bt
  swr parity $d --names $d/names.txt --label gpu | tee -a $S
  gate par_gpu INFO "$(tail -1 $d/results.txt 2> /dev/null | sed 's/^# //')"
  kc parity
}
c2arm() {   # c2arm B1|B2|P: C2's requests on a fresh server of the debug arm (c2_client.py)
  local a=$1 cfg kind=B
  case $a in P) cfg=$CF/P-dbg.json; kind=P;; *) cfg=$CF/B-dbg.json;; esac
  fits $C2_MIN || { say "skipped C2 $a (under $C2_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_c2 INFO "the deadline at $a"; return 0; }
  srvrun $kind c2$a $cfg "$C2O/$a/c2.jsonl" "$PY $C2C http://127.0.0.1:8081 $C2O/$a --plan $C2O/plan.json --label $LP-c2$a --elog-base @OFF@" || true
}
webarm() {   # webarm B|P: C4's search requests on a fresh server of the test form (c4_web.py). The HARD paid limit is the
  # server's paid_budget.py run cap (one run id for both arms; B 5, P 10: B never more than 5, both never more than 10);
  # c4_web.py first checks those in the server's own environment (gate penv_webARM), then stops softly at 5 / 10
  local a=$1 cap=$PAID_CAP_B
  [ $a = P ] && cap=$PAID_CAP_P
  fits $WEB_MIN || { say "skipped C4 $a (under $WEB_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_c4 INFO "the deadline at $a"; return 0; }
  srvrun $a web$a $CF/$a.json "$C4O/$a/web.jsonl" "$PY $C4C http://127.0.0.1:8081 $C4O/$a --plan $C4O/plan.json --label $LP-web$a --elog-base @OFF@$PAIDARGS --paid-env-run switch0213/$LP --paid-env-cap $cap --paid-env-gate penv_web$a --paid-env-gates $G" \
    "PAID_SEARCH_RUN=switch0213/$LP PAID_SEARCH_RUN_CAP=$cap" || true
}
scrarm() {   # scrarm B|P: one screen pass on a fresh server (warm-up, W1-W3, the 2 agent turns, the 4 research replays)
  local a=$1 n=${1}1 f
  fits $SCR_MIN || { say "skipped the screen $n (under $SCR_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_scr$n INFO "the deadline"; return 0; }
  srvrun $a scr$n $CF/$a.json "$SPD/${n}n.jsonl $SPD/${n}a.jsonl $SPD/${n}r.jsonl $SPD/$n.wu.jsonl" "bash $KR/abarm.sh http://127.0.0.1:8081 @OFF@ $SPD $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" || true
  if left_out scr$n; then mkdir -p $SPD/void; for f in $SPD/${n}n.* $SPD/${n}a.* $SPD/${n}r.* $SPD/$n.*; do [ -e "$f" ] && mv "$f" $SPD/void/; done; fi
  return 0
}
fxarm() {   # the three chat fixtures on P (fixtures_client.py, the standard sampling)
  fits $FX_MIN || { say "skipped the fixtures (under $FX_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_fx INFO "the deadline"; return 0; }
  srvrun P bpP $CF/P.json "$C5O/fixtures-P.jsonl" "$PY $FXC http://127.0.0.1:8081 $C5O/fixtures-P.jsonl --plan $C5O/fixtures-plan.json --label $LP-bpP" || true
}
e7P() {   # INFO: exact7 of P's test form at pin 2500 against the stored x28h-e7a, its engines' env checked
  local L=$LP-P cfg=$CF/P.json jp
  fits $E7_MIN || { say "skipped exact7 $L (under $E7_MIN min to the deadline, a kernel check or the priority rule)"; gate skip_e7 INFO "the deadline"; return 0; }
  gpu_clear e7P || { say "exact7 NOT started (a foreign GPU user)"; return 0; }
  say "INFO exact7 $L (P.json against $E7REF, pin 2500; bit-identity not expected with STRATA_ADAPT_FETCH=2)"
  ( PIN_CACHE=2500 REF=$E7REF $LIB/exact7.sh $L $cfg 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- < /dev/null &
  jp=$!; JP=$jp
  wstart e7P
  br envcli $(exe_of $cfg) $cfg --job $jp --mode e7 --kill --gate env_P_e7 --gates $G 2>&1 | tee -a $S
  wait $jp; JP=""
  wstop e7P
  br e7gate $S $L --gate e7_P --gates $G | tee -a $S
  kill_ours
  kc e7-$L
}
sq_decide() { local sd sdc; sd=$(sq decide $SQO 2>&1); sdc=$?; say "  sq.py decide (exit $sdc): $(echo "$sd" | tail -1 | cut -c1-300)"; gate sampled_decide INFO "exit $sdc: $(echo "$sd" | tail -1 | cut -c1-200)"; }

# ---------------------------------------------------------------- refusals, the signal trap, the end
DRYREF=0
refuse() {   # refuse busy|hard WHY - before the gap, nothing changed. busy: exit 1 (the starter retries); hard: an alert, exit 6
  if [ $DRY = 1 ]; then DRYREF=$((DRYREF + 1)); say "DRY RUN: the real run would REFUSE ($1) here: $2"; return 1; fi
  echo "not started ($1): $2 - nothing changed" > $O/result.txt
  say "NOT STARTED ($1): $2 - nothing changed"
  if [ "$1" = hard ]; then
    notes_line "not started: $2 - nothing changed"
    alert "v0.2.13 switch checks not started" "$(echo "$2" | cut -c1-120); nothing changed"; exit 6
  fi
  exit 1
}
hold() {   # the priority rule before the gap: final (exit 8), an alert, nothing changed
  if [ $DRY = 1 ]; then DRYREF=$((DRYREF + 1)); say "DRY RUN: the real run would be HELD by the priority rule here: $1"; return 1; fi
  echo "HELD by the priority rule (Karl 11-09), before the gap: $1 - nothing changed; the day-one work goes first (override: tmp/switch0213-priority-done with a dated reason line, only on Karl's word)" > $O/result.txt
  say "HELD (priority rule): $1 - nothing changed"
  notes_line "HELD by the priority rule before the gap: $1 - nothing changed; day-one work first"
  alert "v0.2.13 switch checks held" "open Qwen4 Flash weights were found: the day-one work goes first; the gap did not start"
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
  alert "v0.2.13 switch checks interrupted" "the driver was stopped; $( [ $ENDING = 1 ] && echo 'during the end: check 8080 before anything else' || { [ $GAPOPEN = 1 ] && echo 'the gap may still be open' || echo 'the gap was not open'; }); $l80"
  if [ $GAPOPEN = 1 ] && [ $ENDING = 0 ] && [ $T0T -gt 0 ]; then test_cleanup "$LP-" || true; lock_sweep; fi
  exit 7
}
finish() { wdg_stop; echo "$1" > $O/result.txt; say "RESULT: $1"; notes_line "$1"; exit $2; }
judge() {   # switch_rules.py decide (CPU, nice 19) -> verdict.txt / decision.txt / .json / result-line.txt
  swr lost $C5O/serverlogs.txt > $C5O/lost.txt 2>&1
  swr decide $O --sampled $SQO --quiet > $O/decide.out 2>&1 || say "switch_rules.py decide failed - rerun it by hand ($PY $SWR decide $O): $(tail -1 $O/decide.out)"
  [ -f $O/decision.txt ] && tee -a $S < $O/decision.txt > /dev/null
}
end_gap() {   # the lock sweep, then port_gap4.sh end, once (the daily back on 8080: nothing of it changed)
  [ $GAPOPEN = 1 ] || return 0
  judge
  if [ $KFAIL = 1 ]; then   # (Karl 11-09: any new Xid or kernel error -> stop at once, the daily back, an alert; kwatch NOT cleared)
    say "KERNEL ERROR during the gap: stopping and bringing the daily back; kwatch is not cleared"
    [ -e $KERR ] && head -c 300 $KERR | sed 's/^/  /' | tee -a $S > /dev/null
    lock_sweep
    ENDING=1
    if $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
      ENDING=0; GAPOPEN=0
      alert "v0.2.13 switch checks stopped: kernel error" "a kernel error during the switch-check gap; it stopped at once and the daily is back on 8080; kwatch not cleared"
    else   # (ENDING stays 1: end has run and failed; no second end, no cleanup)
      alert "v0.2.13 switch checks: kernel error, 8080 not back" "a kernel error during the switch-check gap and port_gap4 end failed: 8080 and the research queue need a look"
    fi
    finish "KERNEL ERROR during the gap - stopped at once, $([ $GAPOPEN = 0 ] && echo 'the daily back on 8080' || echo '8080 NOT back'); kwatch not cleared; partial results in decision.txt: $(cat $O/result-line.txt 2> /dev/null)" 3
  fi
  lock_sweep
  say "port_gap4.sh end: the daily back on 8080 - nothing switched"
  ENDING=1
  if ! $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"
    alert "v0.2.13 switch checks: 8080 not back" "port_gap4 end failed after the switch-check gap; 8080 and the research queue need a look"
    finish "port_gap4.sh end FAILED - 8080 and the research queue need a look; the results are in decision.txt: $(cat $O/result-line.txt 2> /dev/null)" 4
  fi
  ENDING=0; GAPOPEN=0
}

# ================================================================ 0 before the gap (no GPU; 8080 untouched)
: > $G
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
say "v0.2.13 SWITCH CHECKS (work/r23/switch-gap/gap-switch0213.sh, Karl 11-10): B = the daily ($B_SHA) vs P = the port ($P_SHA); C1 parity + read-back, C2 served outputs, C3 the sampled test, C4 web search, C5 the lost-answer guard - measurements only, nothing switches$([ $DRY = 1 ] && echo ' [DRY RUN]')$([ $MOCK = 1 ] && echo ' [MOCK RUN: every tool a stub under scratch/mock]')"
# -- the order of the queue and the priority rule first (cheap; a hold is final)
build_active() { if [ $MOCK = 1 ]; then [ "${MOCK_BUILD_ACTIVE:-0}" = 1 ]; return; fi; systemctl --user is-active -q $BUILD_UNIT 2> /dev/null; }
build_active && refuse busy "the build unit $BUILD_UNIT is still active (build-switch is being built)"
hold_foreign() { [ -e $HOLD ] && ! grep -qF "$HOLDTAG" $HOLD 2> /dev/null; }   # the research queue held by someone else
hold_foreign && refuse busy "the research queue is held by someone else (bench2.hold: $(head -c 120 $HOLD 2> /dev/null | tr '\n' ' '))"
PR=$(afr priority --state $STATE --override $PRIO_DONE); PRC=$?; say "  $PR"
case $PRC in 0) prio_note "$PR";; 10) hold "$(echo "$PR" | cut -c1-300)";; *) refuse busy "the priority rule cannot be checked: $PR";; esac
if [ $MOCK = 0 ] && [ $DRY = 0 ]; then
  systemctl --user is-active -q post-p5-chain 2> /dev/null && refuse busy "the post-Phase-5 chain is still running"
  preflight   # (the cheap busy checks before the long pre-gap work; again right before the gap opens)
fi
# -- the build, the tree, the engines, the files
grep -q "^switchtests: build rc 0 in $BT at $PORT_HEAD" $BUILD_LOG 2> /dev/null || refuse hard "$BUILD_LOG does not record 'switchtests: build rc 0' in build-switch at $PORT_HEAD"
TGTS=$(swr targets 2> /dev/null); [ -n "$TGTS" ] || refuse hard "switch_rules.py targets gave no program list"
for t in $TGTS; do
  [ -x $BT/$t ] || refuse hard "missing the switchtests program $BT/$t"
done
if [ $DRY = 1 ]; then say "  (dry run: would check: ninja -C $BT -n <the $(echo $TGTS | wc -w) switchtests targets> says 'ninja: no work to do.')"
else   # (review S3, gap-shape0213.sh:449-450's form) the programs are the tree's: nothing left to build
  NJ=$(ninja -C $BT -n $TGTS 8>&- 9>&- < /dev/null 2>&1 | tail -1)
  [ "$NJ" = "ninja: no work to do." ] || refuse hard "build-switch is not up to date with the tree (ninja -n: $(echo "$NJ" | cut -c1-120))"
fi
if [ $MOCK = 0 ]; then
  for f in $SWR $AFR $RU $FR $WS/work/r23/basalt_rules.py $KR/g17_rules.py $WS/work/r23/shape-gap/shape_rules.py $KR/port_gap4.sh \
           $KR/abarm.sh $LIB/with_server.sh $LIB/exact7.sh $LIB/guard.py $LIB/kcheck.sh $SRVSH $STOPMON $NOTE $W28/serve/server.py \
           $W13/serve/server.py $W13/serve/websearch.py $W28/serve/websearch.py $W13/serve/web/app.js $WS/configs/P028x.json \
           $WS/configs/P0213x-af2.json $WS/configs/P0213x.json $WS/configs/x28h.json $Q/sq.py $Q/sq_stat.py $Q/sq_client.py $SPEC \
           $C2C $C4C $FXC $WL /home/USER/ai-speed-testing/basalt-ab/scripts/abrun.py $BPD/conv.ids $BPD/struct.ids $BPD/prose.ids \
           $GGUF $E28/strata $BT/CTestTestfile.cmake; do
    [ -f $f ] || refuse hard "missing: $f"
  done
  [ -d $MTPRT ] || refuse hard "missing the MTP layer $MTPRT"
  [ -x $NODE ] || refuse hard "missing node ($NODE)"
  [ "$(ls $PROF/$E7REF-*.out 2> /dev/null | wc -l)" = 7 ] || refuse hard "the stored exact7 $E7REF is incomplete"
  [ -x $EAF/strata ] && [ "$(sha12 $EAF/strata)" = $B_SHA ] || refuse hard "engine-r23afetch is not the daily's binary ($B_SHA)"
  [ -x $E13/strata ] && [ "$(sha12 $E13/strata)" = $P_SHA ] || refuse hard "engine-r23p0213 is not the port's binary ($P_SHA)"
  grep -q "branch r23-port0213 $PORT_HEAD" $E13/SOURCE 2> /dev/null || refuse hard "engine-r23p0213/SOURCE does not name r23-port0213 $PORT_HEAD"
  h=$(git -C $W13 rev-parse HEAD 2> /dev/null); [ "${h:0:9}" = "$PORT_HEAD" ] || refuse hard "strata-r23p0213 is not at $PORT_HEAD (${h:0:12})"
  [ -z "$(GIT_OPTIONAL_LOCKS=0 git -C $W13 status --porcelain --untracked-files=no 2> /dev/null)" ] || refuse hard "strata-r23p0213 is dirty"
  grep -qE "^SERVED_KNOWN=\"[^\"]*$B_SHA" $KR/port_gap4.sh || refuse hard "work/r22/port_gap4.sh does not know the daily's engine $B_SHA"
  for p in $(pgrep -x ninja); do case $(readlink /proc/$p/cwd 2> /dev/null) in $W13|$W13/*) refuse busy "a ninja build runs in strata-r23p0213 (pid $p)";; esac; done
  free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
  [ "${free:-0}" -ge 5 ] || refuse hard "only ${free} GB free on results/"
  say "  files, engines (B $B_SHA, P $P_SHA), the port tree at $PORT_HEAD, build-switch and port_gap4.sh checked"
fi
# -- the rules: selftest, the switches (synthetic data, under OUTDIR or the dry run's scratch)
ST=$O/selftest-rules; [ $DRY = 1 ] && ST=$SG/scratch/selftest-dry
if [ $MOCK = 0 ] || [ "${MOCK_SELFTEST:-0}" = 1 ]; then
  swr selftest $ST > $O/selftest-rules.out 2>&1 || refuse hard "switch_rules.py selftest failed ($(tail -1 $O/selftest-rules.out | cut -c1-160))"
  say "  $(tail -1 $O/selftest-rules.out)"; rm -rf $ST
fi
FM=$(swr forms 2>&1) || refuse hard "switch_rules.py's switches: $(echo "$FM" | tail -1)"
say "  the switches (frozen into rules.txt): $(echo "$FM" | tr '\n' ' ')"
# -- the arm configs, the C1 program list, the web path, the prompts, the plans
rm -rf $SQO; mkdir -p $SQO; cp $SPEC $SQO/spec-in.json
AC=$(swr arms $CF --spec $SQO/spec-in.json $([ $MOCK = 1 ] && echo "--no-sha --log-dir $M/logs") --gate cfg --gates $G 2>&1 | tail -1); say "  $AC"
[ "$(gst cfg)" = PASS ] || refuse hard "the arm configs do not check out: $AC"
GPUS=$(jget $CF/P.json "['env']['CUDA_VISIBLE_DEVICES']" 2> /dev/null)
[ -n "$GPUS" ] || refuse hard "no CUDA_VISIBLE_DEVICES in the P arm"
CL=$(swr ctestlist $BT --out-cpu $C1O/cpu/names.txt --out-gpu $C1O/gpu/names.txt --json-out $C1O/entries.json --gate ctestlist --gates $G 2>&1 | tail -1)
say "  $(echo "$CL" | cut -c1-300)"
[ "$(gst ctestlist)" = PASS ] || refuse hard "the C1 program list is not complete: $(echo "$CL" | cut -c1-200)"
DIRECT_GPU_NAMES="qsa_prompt_attn_parity prefill_fused_iq_test_edge"
WEBTREES="$W28 $W13"; [ $MOCK = 1 ] && [ "${MOCK_WEB_LOCAL:-0}" = 1 ] && WEBTREES="$M/webtree"
WP=$(swr webpath --trees $WEBTREES --configs $CF/B.json $CF/P.json --tools $PAID_TOOLS --gate webpath --gates $G 2>&1); WPC=$?
echo "$WP" | sed 's/^/  /' | tee -a $S > /dev/null; say "  $(echo "$WP" | tail -1 | cut -c1-300)"
C4OK=0; [ $WPC = 0 ] && C4OK=1
WPAID=0; [ "$(gst webpath)" = PAID ] && WPAID=1   # (the paid path, within the budget: C4 runs bounded)
PAIDARGS=""; [ $WPAID = 1 ] && PAIDARGS=" --paid-base $C4O/paid-start.json --paid-tools $PAID_TOOLS --paid-stop $PAID_STOP --paid-arm-stop $PAID_ARM_STOP"
[ $C4OK = 0 ] && say "  C4 (web search) NOT RUN: $(gst webpath) - $(grep '^webpath ' $G | tail -1 | cut -d' ' -f3- | cut -c1-200); the gap runs without it; the verdict cannot be PASS"
[ $WPAID = 1 ] && say "  C4 runs on the paid path, bounded: $PAID_STOP paid calls at most (PAID_SEARCH_KIND=test, the budget checked again right before C4)"
if [ $MOCK = 0 ]; then
  RD=$(swr render --spec $SQO/spec-in.json --gate render --gates $G 2>&1 | tail -1); say "  $(echo "$RD" | cut -c1-300)"
  [ "$(gst render)" = PASS ] || refuse hard "the sampled prompts do not render to the same ids on B and P: $(echo "$RD" | cut -c1-200)"
  swr fixtures $C5O/fixtures-plan.json --tree $W13 --data $BPD --gguf $GGUF > $C5O/fixtures-plan.out 2>&1 || refuse hard "the fixture plan: $(tail -1 $C5O/fixtures-plan.out | cut -c1-160)"
else cp $M/fixtures-plan.json $C5O/fixtures-plan.json; fi
say "  $(tail -1 $C5O/fixtures-plan.out 2> /dev/null || echo 'fixtures plan (mock)')"
swr c2plan $C2O/plan.json | tee -a $S > /dev/null; swr c4plan $C4O/plan.json | tee -a $S > /dev/null
say "  plans: C2 $(sha12 $C2O/plan.json), C4 $(sha12 $C4O/plan.json), fixtures $(sha12 $C5O/fixtures-plan.json) (the standard sampling in every one)"
# -- the clients' selftests and the sampled harness (STEPS 0b-0d): selftests, derive of the spec copy, the rule BEFORE any engine
if [ $DRY = 1 ]; then
  say "  (dry run: would run: c2_client.py / c4_web.py / fixtures_client.py selftest; sq.py selftest -> SELFTEST OK; sq_client.py selftest -> CLIENT SELFTEST OK; sq.py selftest-real --spec $SQO/spec-in.json -> SELFTEST-REAL OK)"
  say "  (dry run: would run: sq.py derive $SQO/spec-in.json $SQO; switch_rules.py cfgcheck $CF --sampled $SQO; sq.py rule $SQO/spec.json > $SQO/rule.txt)"
else
  for t in "$C2C selftest:C2 CLIENT SELFTEST OK" "$C4C selftest:C4 WEB SELFTEST OK" "$FXC selftest:FIXTURES CLIENT SELFTEST OK" \
           "$Q/sq.py selftest:SELFTEST OK" "$Q/sq_client.py selftest:CLIENT SELFTEST OK" "$Q/sq.py selftest-real --spec $SQO/spec-in.json:SELFTEST-REAL OK"; do
    cmd=${t%%:*}; want=${t#*:}; f=$O/selftest-$(basename ${cmd%% *})-$(echo "$cmd" | awk '{print $2}').out
    nice -n 19 $PY $cmd 8>&- 9>&- < /dev/null > $f 2>&1; rc=$?
    [ $rc = 0 ] && tail -1 $f | grep -qx "$want" || refuse hard "$(basename ${cmd%% *}) $(echo "$cmd" | awk '{print $2}') failed (rc $rc: $(tail -1 $f | cut -c1-120))"
    say "  $(basename ${cmd%% *}) $(echo "$cmd" | awk '{print $2}'): $(tail -1 $f)"
  done
  DV=$(sq derive $SQO/spec-in.json $SQO 2>&1); DRC=$?
  say "  sq.py derive: $(echo "$DV" | head -3 | tr '\n' ' ' | cut -c1-300)"
  [ $DRC = 0 ] || refuse hard "sq.py derive refused the spec: $(echo "$DV" | sed -n 2p | cut -c1-200)"
  for a in VF R1 X R2; do [ -s $SQO/cfg/$a.json ] || refuse hard "sq.py derive wrote no cfg/$a.json"; done
  SC=$(swr cfgcheck $CF --spec $SQO/spec-in.json --sampled $SQO $([ $MOCK = 1 ] && echo "--no-sha --log-dir $M/logs") --gate cfg_sampled --gates $G 2>&1 | tail -1)
  [ "$(gst cfg_sampled)" = PASS ] || refuse hard "the sampled arms are not the gap's debug arms: $(echo "$SC" | cut -c1-200)"
  sq rule $SQO/spec.json > $SQO/rule.txt || refuse hard "sq.py rule failed"
  [ -s $SQO/rule.txt ] || refuse hard "sq.py rule wrote nothing"
  say "  the sampled rule frozen: sampled/rule.txt sha $(sha12 $SQO/rule.txt) (before any engine start)"
fi
swr rules $O/rules.txt | sed 's/^/  /' | tee -a $S
say "  estimate: ~72 min with 8080 down (~60 without C4; open 2, parity 8, VF 4, C2 6, C3 23, C4 12, C5 + INFO 9, exact7 3.5, close 4); deadline $MAXM min for new steps after the gap opens; 8080 down ~2.9 h at most ($((MAXM + WORST_OVER)) min)"
if [ $DRY = 1 ]; then
  say "DRY RUN: would run C1's CPU parts now (nice 19, 8080 serving): env CUDA_VISIBLE_DEVICES= ctest --test-dir $BT -R '^(<$(wc -l < $C1O/cpu/names.txt) CPU names>)\$' --timeout 300 --output-junit ...; CUDA_VISIBLE_DEVICES= $BT/patch_guard_test $GGUF $MTPRT;"
  say "  (cd $C1O && TMPDIR=$C1O/tmp PYTHONDONTWRITEBYTECODE=1 PATH=$NODE_DIR:\$PATH timeout $SERVE_T nice -n 19 $P -B -m unittest discover -v -s $W13/serve -t $W13 -p 'test_*.py'); $NODE --check $W13/serve/web/app.js; switch_rules.py servetests / nodecheck -> not PASS: the gap is NOT opened"
  say "DRY RUN: would check that no other gap / test lock / model server but the daily ($B_SHA) / 8081 listener is there, that the kernel-log watcher runs, and a kernel check"
  say "DRY RUN: the gap would now run:"
  say "  GAP_MAX_MIN=$((MAXM + WORST_OVER)) $KR/port_gap4.sh begin \"$HOLDTAG: ...\"; the watchdog (open at deadline + 20 min: one critical alert); the priority rule; deadline $MAXM min after it opens"
  say "  2 C1 GPU: env CUDA_VISIBLE_DEVICES=$GPUS ctest --test-dir $BT -R '^(<$(wc -l < $C1O/gpu/names.txt) GPU names>)\$' --timeout 300 --output-junit $C1O/gpu/junit.xml (cut at <= $PAR_CAP min); $BT/qsa_prompt_attn_parity; $BT/prefill_fused_iq_test --edge --no-timing; switch_rules.py parity"
  say "  3 C1 VF: with_server.sh $LP-sqVF $SQO/cfg/VF.json -- \"port0211_rules envcheck --pins && switch_rules armenv --arm P && sq.py envcheck && SQ_BUDGET_S=300 sq_client.py\"; sq.py verify $SQO VF"
  for a in B1 B2 P; do say "  4 C2 $a: with_server.sh $LP-c2$a $CF/$([ $a = P ] && echo P || echo B)-dbg.json -- \"envcheck && armenv && c2_client.py http://127.0.0.1:8081 $C2O/$a --plan $C2O/plan.json\""; done
  say "    switch_rules.py c2compare $C2O; (VF once more if not decided)"
  for a in R1 X R2; do say "  5 C3 $a: with_server.sh $LP-sq$a $SQO/cfg/$a.json -- \"envcheck && armenv && sq.py envcheck && sq_client.py http://127.0.0.1:8081 $SQO/$a\""; done
  say "    sq.py ids $SQO R1 X R2; ( $PY $LIB/guard.py sq-score -- $PY $Q/sq.py score $SQO R1 X R2 --max-min <=25 ) & + sq.py envwatch JOB $SQO --kill + watchdog; sq.py decide $SQO"
  if [ $C4OK = 1 ]; then
    [ $WPAID = 1 ] && say "  6 C4 first: switch_rules.py paidcheck --tools $PAID_TOOLS --out $C4O/paid-start.json (REFUSED: C4 NOT RUN: paid budget)"
    for a in B P; do say "  6 C4 $a: env PAID_SEARCH_KIND=test PAID_SEARCH_RUN=switch0213/$LP PAID_SEARCH_RUN_CAP=$([ $a = P ] && echo $PAID_CAP_P || echo $PAID_CAP_B) (the hard limit) with_server.sh $LP-web$a $CF/$a.json -- \"envcheck && armenv && c4_web.py http://127.0.0.1:8081 $C4O/$a --plan $C4O/plan.json$PAIDARGS\""; done
    say "    switch_rules.py paidcheck --out $C4O/paid-end.json; c4judge"
  else say "  6 C4: NOT RUN ($(grep '^webpath ' $G | tail -1 | cut -d' ' -f3- | cut -c1-160))"; fi
  say "  7 C5: with_server.sh $LP-scrP1 $CF/P.json -- \"... abarm.sh http://127.0.0.1:8081 OFF $SPD P1 P1n=normal:1:W1,W2,W3 P1a=agent:1 P1r=research4:1\"; $LP-bpP: fixtures_client.py; $LP-scrB1 (B.json, INFO)"
  say "    INFO: PIN_CACHE=2500 REF=$E7REF $LIB/exact7.sh $LP-P $CF/P.json (+ br envcli --mode e7 --kill; br e7gate)"
  say "  8 switch_rules.py lost / decide $O; the lock sweep; $KR/port_gap4.sh end; kcheck; result.txt, NOTES.md, ntfy"
  say "DRY RUN done: $DRYREF refusal(s) would stop the real run now"
  exit 0
fi
# -- C1's CPU parts (nice 19, 8080 serving; CUDA_VISIBLE_DEVICES empty, so none can reach a GPU)
kerr_pre() { [ -e $KERR ] && refuse hard "a kernel error was recorded during C1's CPU parts ($1; tmp/r19/KERNEL_ERROR: $(head -c 120 $KERR 2> /dev/null | tr '\n' ' ')): Karl clears kwatch"; return 0; }   # (review M2)
say "C1 CPU parts before the gap: $(wc -l < $C1O/cpu/names.txt) ctest entries + patch_guard_test, the server suite with node, node --check"
kerr_pre "before them"
ctest_run $C1O/cpu "CUDA_VISIBLE_DEVICES=" 1200 - nice -n 19
kerr_pre "after the CPU ctest entries"
: > $C1O/cpu/direct.txt
direct $C1O/cpu patch_guard_test 300 - "CUDA_VISIBLE_DEVICES=" nice -n 19 $BT/patch_guard_test $GGUF $MTPRT
kerr_pre "after patch_guard_test"
swr parity $C1O/cpu --names $C1O/cpu/names.txt --label cpu | tee -a $S
mkdir -p $C1O/tmp
if [ $MOCK = 1 ]; then $M/bin/servetests > $C1O/servetests.txt 2>&1
else ( cd $C1O && TMPDIR=$C1O/tmp PYTHONDONTWRITEBYTECODE=1 PATH=$NODE_DIR:$PATH timeout $SERVE_T nice -n 19 $P -B -m unittest discover -v -s $W13/serve -t $W13 -p 'test_*.py' > $C1O/servetests.txt 2>&1 < /dev/null 8>&- 9>&- ); fi
tail -3 $C1O/servetests.txt | sed 's/^/  /' | tee -a $S
kerr_pre "after the server suite"
{ $NODE --check $W13/serve/web/app.js 8>&- 9>&- < /dev/null; echo "rc $?"; } > $C1O/node-check.txt 2>&1
kerr_pre "after node --check"
swr servetests $C1O/servetests.txt --gate servetests --gates $G | tee -a $S
swr nodecheck $C1O/servetests.txt $C1O/node-check.txt --gate node --gates $G | tee -a $S
swr pstatus $C1O/cpu --gate cpu_tests --gates $G | tee -a $S
PREFAIL=$(for k in cpu_tests servetests node; do [ "$(gst $k)" = PASS ] || echo "$k $(gst $k)"; done | tr '\n' ';')
if [ -n "$PREFAIL" ]; then   # (coordinator 11-10) C1 FAIL / NOT DECIDED with the failing tests named; the gap still opens
  PFW=$(for k in cpu_tests servetests node; do [ "$(gst $k)" = PASS ] || echo "$k: $(grep "^$k " $G | tail -1 | cut -d' ' -f3- | cut -c1-200)"; done | tr '\n' ' ')
  gate c1_pregap FAIL "$PFW"
  say "C1's CPU parts did not all pass ($PREFAIL): C1 cannot PASS; the gap opens for the other checks"
fi
# -- right before the gap: the busy checks again, the kernel
preflight
if [ $MOCK = 0 ]; then
  [ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || refuse hard "the kernel-log watcher is not running"
  [ -e $KERR ] && refuse hard "a kernel-error marker is present (tmp/r19/KERNEL_ERROR): Karl clears kwatch"
  $LIB/kcheck.sh r23sw-pre > /dev/null 8>&- 9>&- < /dev/null || refuse hard "a kernel check fails before the gap"
fi
build_active && refuse busy "the build unit $BUILD_UNIT is active again"
hold_foreign && refuse busy "the research queue is held by someone else (bench2.hold: $(head -c 120 $HOLD 2> /dev/null | tr '\n' ' '))"
PR=$(afr priority --state $STATE --override $PRIO_DONE); PRC=$?
case $PRC in 0) prio_note "$PR";; 10) hold "$(echo "$PR" | cut -c1-300)";; *) refuse busy "the priority rule cannot be checked: $PR";; esac
trap on_signal TERM INT HUP

# ================================================================ 1 the gap
GAP_MAX_MIN=$((MAXM + WORST_OVER)) $KR/port_gap4.sh begin "$HOLDTAG: the v0.2.13 port against the daily (Karl 11-10; measurements only, nothing switches)" 8>&- 9>&- < /dev/null 2>&1 | tee -a $S
[ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null || { grep -qF "$HOLDTAG" $HOLD 2> /dev/null && rm -f $HOLD; refuse busy "the gap did not open (our hold removed)"; }
GAPOPEN=1; T0=$(date +%s); T0T=$(uptk); DEADLINE=$(( T0 + MAXM * 60 ))
PRE=$( { for x in $ENGNAMES; do pgrep -x $x; done; } | sort -un | tr '\n' ' ')   # (never this gap's to stop)
echo "$T0 $(date -Is)" > $O/t0.txt
[ -n "$PRE" ] && say "engine processes running as the gap opened (8080's, stopping; never stopped by this gap): $(pre_alive)"
if [ $MOCK = 0 ]; then   # the watchdog: still open 20 min past the deadline -> one critical alert (a hang the deadline cannot cut)
  ( exec 8>&- 9>&- < /dev/null > /dev/null 2>&1; sleep $(( MAXM * 60 + 1200 )); kill -0 $$ 2> /dev/null && [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null \
      && notify-send -a Strata -u critical "v0.2.13 switch checks overrun" "the switch-check gap is still open 20 min past its deadline: 8080 may be down" ) &
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

# ---- 2 C1: the GPU parity programs, before any server
if [ $KFAIL = 0 ] && prio "the parity programs"; then par_gpu; fi
# ---- 3 C1: the read-back start
if [ $KFAIL = 0 ] && prio "the read-back start"; then
  if fits $VF_MIN; then say "3 C1 THE READ-BACK START: VF = P + STRATA_ADAPT_FETCH_VERIFY=1 + STRATA_ADAPT_CHECKRES=1, K 2"; vf_part
  else say "3 the read-back start does not fit ($(( $(left) / 60 )) min left, $VF_MIN needed)"; gate skip_vf INFO "the deadline"; fi
fi
# ---- 4 C2: served outputs, B1 B2 P
if [ $KFAIL = 0 ] && [ $PRIO = 0 ]; then
  say "4 C2 SERVED OUTPUTS: 4 prompts x 2 seeds (the think prompt with an answer_room continuation) on B1, B2 (B-dbg twice), P (P-dbg)"
  for a in B1 B2 P; do [ $KFAIL = 1 ] && break; prio "C2 $a" || break; c2arm $a; done
  swr c2compare $C2O --gates-file $G --gate c2 --gates $G > $C2O/compare.out 2>&1; head -1 $C2O/compare.out | tee -a $S
fi
# ---- the read-back's one retry
if [ $VFDONE = 0 ] && [ $VFTRIES = 1 ] && [ $KFAIL = 0 ] && prio "the read-back start (its retry)"; then fits $VF_MIN && vf_part; fi
# ---- 5 C3: the sampled test (STEPS-adaptfetch.txt 3-6, arms R1 X R2)
if [ $KFAIL = 0 ] && prio "the sampled part"; then
  if fits $SQ_REST; then
    say "5 C3 THE SAMPLED TEST: R1 (= B, K 8), X (= P, K 8), R2 (= B, K 4); with R1: ids and the scorer; sq.py decide"
    DONE_ARMS=""; rest=$SQ_REST
    for arm in R1 X R2; do
      prio "sampled $arm" || break
      fits $rest || { say "  skipped sampled $arm and later (under $rest min to the deadline, or a kernel check failed)"; gate skip_sq_$arm INFO "the deadline: $(( $(left) / 60 )) min left, $rest needed"; break; }
      sqarm $arm || true
      [ -s $SQO/$arm/sampled.jsonl ] && DONE_ARMS="$DONE_ARMS $arm"
      rest=$(( rest - $([ $arm = R2 ] && echo $SQ4_MIN || echo $SQ8_MIN) ))
    done
    if [ $KFAIL = 0 ] && prio "the scorer"; then
      case " $DONE_ARMS " in
        *" R1 "*)
          sq ids $SQO $DONE_ARMS > $SQO/ids.txt 2>&1; gate ids INFO "rc $?: $(tail -1 $SQO/ids.txt | cut -c1-160)"
          sed 's/^/  /' $SQO/ids.txt | tee -a $S
          if fits $SCORE_MIN; then
            mm=$(( $(left) / 60 - 1 )); [ $mm -gt 25 ] && mm=25   # (STEPS' 25, cut to the minutes left: the deadline holds)
            say "  the scorer: one CLI engine (x28h, the decode-path reference) over$DONE_ARMS, --max-min $mm"
            rm -f $SQO/score.rc $SQO/sq-score.watchdog
            ( $PY $LIB/guard.py sq-score -- $PY $Q/sq.py score $SQO $DONE_ARMS --max-min $mm > $SQO/score-run.txt 2>&1; echo $? > $SQO/score.rc ) 8>&- 9>&- < /dev/null &
            jp=$!; JP=$jp
            wstart score
            watchdog $jp $(( mm + 10 )) sq-score 8>&- 9>&- < /dev/null &
            wd=$!
            $PY $Q/sq.py envwatch $jp $SQO --kill 8>&- 9>&- < /dev/null 2>&1 | tee $SQO/envwatch.txt | tee -a $S
            EW=$(tail -1 $SQO/envwatch.txt)
            wait $jp; JP=""
            kill $wd 2> /dev/null; wait $wd 2> /dev/null
            wstop score
            [ -f $SQO/sq-score.watchdog ] && say "  $(cat $SQO/sq-score.watchdog)"
            case $EW in "ENV CHECK OK"*) gate env_sqscore PASS "$EW";; *) gate env_sqscore FAIL "$EW";; esac
            gate score INFO "rc $(cat $SQO/score.rc 2> /dev/null || echo none): $(grep -E '^scored|^PROBLEM' $SQO/score-run.txt | head -2 | tr '\n' ' ' | cut -c1-200)"
            kill_ours
            kc score
          else
            say "  the scorer skipped (under $SCORE_MIN min to the deadline)"; gate skip_score INFO "the deadline"
          fi;;
        *) say "  no R1 samples (arms with samples:${DONE_ARMS:- none}): no ids, no scorer"; gate skip_score INFO "no R1 samples (${DONE_ARMS:-none})";;
      esac
    fi
    sq_decide
  else
    say "5 the sampled part does not fit: $(( $(left) / 60 )) min left, $SQ_REST needed"
    gate skip_sampled INFO "the deadline: $(( $(left) / 60 )) min left, $SQ_REST needed"
  fi
fi
# ---- 6 C4: web search end to end (SearXNG only, or the paid path within the budget: bounded, hard cap in the servers)
if [ $C4OK = 0 ]; then
  gate skip_c4 INFO "C4 NOT RUN before the gap: $(grep '^webpath ' $G | tail -1 | cut -d' ' -f3- | cut -c1-200)"
elif [ $KFAIL = 0 ] && prio "the web search part"; then
  if [ $MOCK = 0 ] && ! ss -H -ltn "( sport = :8888 )" 2> /dev/null | grep -q .; then
    say "6 C4: the local SearXNG (127.0.0.1:8888) is not listening - not run"; gate skip_c4 INFO "the local SearXNG is not listening"
  elif [ $WPAID = 1 ] && { swr paidcheck --tools $PAID_TOOLS --out $C4O/paid-start.json --gate c4budget --gates $G > $C4O/paid-start.out 2>&1; PCR=$?
       sed 's/^/  /' $C4O/paid-start.out | tee -a $S > /dev/null; [ $PCR != 0 ]; }; then
    say "6 C4 NOT RUN: paid budget (checked right before C4: $(tail -1 $C4O/paid-start.out | cut -c1-200))"; gate skip_c4 INFO "C4 NOT RUN: paid budget (right before C4)"
  else
    say "6 C4 WEB SEARCH: 3 search prompts with \"strata_web\": true on B, then P$([ $WPAID = 1 ] && echo " (the paid fallback bounded: $PAID_STOP paid calls at most)" || echo ' (local SearXNG only)')"
    for a in B P; do [ $KFAIL = 1 ] && break; prio "C4 $a" || break; webarm $a; done
    [ $WPAID = 1 ] && { swr paidcheck --tools $PAID_TOOLS --out $C4O/paid-end.json > $C4O/paid-end.out 2>&1; say "  the paid counters after C4: $(tail -1 $C4O/paid-end.out | cut -c1-200)"; }
    swr c4judge $C4O --gates-file $G --gate c4 --gates $G | tee -a $S
  fi
fi
# ---- 7 C5: our workload on P (the screen, the fixtures), the screen on B (INFO), exact7 P (INFO)
if [ $KFAIL = 0 ] && prio "the workload part"; then
  say "7 C5: the 9-workload screen and the three chat fixtures on P; the screen on B (INFO speed); exact7 P (INFO)"
  for st in "scrarm P" fxarm "scrarm B" e7P; do [ $KFAIL = 1 ] && break; prio "$st" || break; $st; done
fi

# ---- 8 the decision, the lock sweep, the daily back
DOWN_WORK=$(( ($(date +%s) - T0) / 60 ))
say "the gap's work took $DOWN_WORK min (deadline $MAXM)"
end_gap
DOWN=$(( ($(date +%s) - T0) / 60 ))
KA=ok; kc after || KA=FAILED
VD=$(cat $O/verdict.txt 2> /dev/null || echo "decision missing - rerun switch_rules.py decide")
RL=$(cat $O/result-line.txt 2> /dev/null || echo "$VD")
say "8080 was down for about $DOWN min; kernel check after the gap: $KA"
[ $KA = ok ] || alert "v0.2.13 switch checks: kernel check" "the kernel check after the switch-check gap failed (8080 is back); see kwatch.log"
if [ $PRIO = 1 ]; then
  alert "v0.2.13 switch checks stopped" "open Qwen4 Flash weights were found during the gap: it ended early, the daily is back; the day-one work goes first"
  finish "STOPPED by the priority rule (Karl 11-09: day-one work first; $PRIOWHY); the daily back after $DOWN min, nothing switched; what ran: $RL" 8
fi
note "v0.2.13 switch checks done" "Measurements only, nothing switched; 8080 back after $DOWN min. $(echo "$VD" | cut -c1-160)"
finish "DONE (measurements only, nothing switched; 8080 down $DOWN min; kernel check after: $KA): $RL" 0
