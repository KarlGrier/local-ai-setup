#!/bin/bash
# gap-port0211.sh - r23 (Karl 11-05): THE v0.2.11 PORT'S GATES. WRITTEN 11-05, NOT RUN, NOT IN work/r23/gap-series.sh and
# no .ready file: Karl reviews it first. Measurements only - P028x stays served, nothing switches, nothing is built. Run:
# `bash work/r23/gap-port0211.sh` (no arguments; every path absolute). The build under test: engine-r23p0211 from branch
# r23-port0211 (worktree strata-r23p0211 = v0.2.11 c3b3f5035 + our 28, head d797db9f6; work/r23/build-port0211.sh engine),
# its release reference engine-v0211stock (build-port0211.sh stock), the tests in strata-r23p0211/build-tests
# (build-port0211.sh tests); the configs from work/r23/scratch-port0211/make_configs0211.py. The rules, fixed before any
# run: work/r23/port0211_rules.py's docstring (gap 17's baseline for v0.2.11; the arms, the 18 pins). Output:
# results/r23/port-0211/gap/ (summary.txt, gates.txt, decision.txt). Steps, times: results/r23/port-0211/PORT.md.
#   0 before the gap (no GPU, 8080 untouched) - REFUSES (exit 1) on: tmp/gpu-test.lock held, another gap's lock, a model
#     server other than the 8080 queue's P028x, a listener on 8081, no kernel watcher, a missing file / config / engine,
#     an engine that is not the recorded build (engine-r23p0211's SOURCE head = the worktree's head, SHA256 files), < 20 GB
#     free; then the build and pin gates and the CPU-only tests (nice 19; the C++ ones with CUDA_VISIBLE_DEVICES empty):
#     ours, upstream's CPU sampler tests, the server tests, the fence check - a FAIL among them also refuses (the baseline
#     cannot pass; the gap is not opened, decision.txt says why)
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down); wait for the memory; a kernel check
#   2 the GPU unit tests: spec_verify_parity, spec_proposal_parity, prefill_fused_iq_test --v2; INFO: v0.2.11's
#     native_expert_parity on the Q5_0-down pairs (aa678f10d)
#   3 exact7 at pin 2500: s211 (stock v0.2.11), p211off vs s211 (FIRST: every switch off = the release), x28h (P028x),
#     p211a vs x28h, p211b vs p211a, nov2 vs p211a; s028 vs s211 only when p211a is not 7/7; INFO: p211a vs gap 17's
#     stored g17-p210a (the v0.2.10 port)
#   4 pf_yardstick long40 on P; kernel_rule2 + kernel_rule3 against gap 8's references; INFO: the logit files vs gap 16's
#     x28h and gap 17's p210
#   5 the 9-workload screen, 3 passes in turned order (B P / P B / B P): with_server.sh + abarm.sh, the env check (incl.
#     the server process's pins), the fatal-line check, no foreign GPU user before / during an arm (one seen = the
#     arm-pass is void), a kernel check
#   6 Basalt's community-1 fixtures, cold, 3 passes in turned order: M (x28h) and H (P) on decode / pp16k / pp64k; P10
#     (the v0.2.10 port, INFO) on decode
#   7 the served form on P0211x-RTpin-vision (chat-cache checks + a picture) and the live tool-call test, B vs P
#   8 INFO, only if 9 min fit: the many-positions NLL arm on P (score.py run --set long11 --rows all:8)
#   9 lossless, #3961's lost-answer check, port_gap4.sh end (P028x back), a kernel check; after the gap (CPU, nice 19):
#     the speed table, Basalt's report, the NLL compare with the NLL gap's x28h arms (INFO), port0211_rules.py decide
# No new step after the deadline (P0211_MAX_MIN, default 130 min after the gap opens). A kernel-check failure stops new
# steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done (outcome in decision.txt), 1 = refused /
# not opened (8080 untouched), 3 = kernel check failed, 4 = port_gap4.sh end failed.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r23 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=$WS/.venv/bin/python; KR=$WS/work/r22; LIB=$WS/bringup/lib; BA=/home/USER/ai-speed-testing/basalt-ab
B90=$KR/basalt-pr90; TR=$KR/toolrecovery; SCORE=$WS/work/r23/nll-many/score.py; NR=$WS/work/r23/nll_rules.py
RU=$WS/work/r23/port0211_rules.py
D=$WS/results/r23/port-0211; O=$D/gap; G=$O/gates.txt; R=$O/speed; Y=$O/pfy; BO=$O/bp90; NO=$O/nll; TC=$O/toolcalls; UT=$O/tests
S=$D/gap-port0211-starts.log       # until the pre-gap checks pass (then $O/summary.txt)
Y8=$WS/results/r22/gap8/pfy; Y16=$WS/results/r22/gap16/pfy; Y17=$WS/results/r22/gap17/pfy; NLLG=$WS/results/r23/nll-many/gap
W=$WS/strata-r23p0211; E=$WS/engine-r23p0211; EXE=$E/strata; WST=$WS/strata-v0211stock; EST=$WS/engine-v0211stock
W28=$WS/strata-r22p028x; E28=$WS/engine-r22p028x; W10=$WS/strata-r22p0210; E10=$WS/engine-r22p0210; E28S=$WS/engine-r22s028t
C=$WS/configs; H=$C/P0211x-h.json; X=$C/x28h.json; H10=$C/P0210x-h.json; OFF=$C/P0211x-h-off.json; ST=$C/s0211-h.json
S28=$C/s028-h.json; NOV2=$C/P0211x-h-nov2.json; RT=$C/P0211x-RTpin-vision.json; PX=$C/P0211x.json
GGUF=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf; MTP=$WS/strata-v0115/mtp/rt
BT=$W/build-tests
P028X_SHA=f4c4f654fb24             # engine-r22p028x/strata, served on 8080 since 10-30
PORT_HEAD=${P0211_PORT_HEAD:-d797db9f6}   # the head engine-r23p0211 was built from (11-05)
MAXM=${P0211_MAX_MIN:-130}
mkdir -p $D $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [p211 $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }   # a gate's last status ("" = not written)
KFAIL=0; T0=$(date +%s); DEADLINE=$T0
kc() { $LIB/kcheck.sh "p211-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # a step starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" "$1"; }
exe_of() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['exe'])" "$1"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
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
foreign() {   # the GPU users that are not one of this gate's engines (the screen-rerun gap's rule, 11-05): an engine process
  # (exact names) or an NVIDIA compute process holding >= 512 MiB (or an unknown amount) whose binary is in none of the
  # gate's engine folders - one line each. strata-dsv41 / llama-server / ollama count by name
  local p m x ex c
  { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x | sed 's/$/,engine/'; done
    nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2> /dev/null; } | tr -d ' ' \
  | while IFS=, read -r p m; do
      [[ $p =~ ^[0-9]+$ ]] && [ -e /proc/$p ] || continue
      [[ $m =~ ^[0-9]+$ ]] && [ $m -lt 512 ] && continue
      ex=$(readlink /proc/$p/exe 2> /dev/null) || ex=""; c=$(cat /proc/$p/comm 2> /dev/null)
      case $c in strata-dsv41|llama-server|ollama) ;; *) [ -n "$ex" ] || continue
        case $ex in $E/*|$EST/*|$E28/*|$E10/*|$E28S/*|$WS/engine-r22p021/*) continue;; esac;; esac
      echo "pid $p ($c, ${ex:-?}, $m$([[ $m =~ ^[0-9]+$ ]] && echo ' MiB'))"
    done | sort -u
}
gwatch() {   # gwatch FLAG OUT: while FLAG exists (and this driver runs), every 5 s: foreign GPU users >> OUT
  while [ -e $1 ] && kill -0 $$ 2> /dev/null; do foreign | sed "s/^/$(date +%T) /" >> $2; sleep 5; done
}
gpu_clear() {   # gpu_clear NAME: no foreign GPU user before the step (up to 60 s); else foreign_NAME FAIL, not started
  local i f
  for i in $(seq 12); do f=$(foreign); [ -z "$f" ] && return 0; sleep 5; done
  gate foreign_$1 FAIL "not started: $(echo "$f" | head -1) still on the GPU after 60 s"
  return 1
}
WGP=""
wstart() {   # wstart NAME: the foreign-GPU-user watch for one step (gwatch in the background)
  rm -f $O/$1.foreign; touch $O/$1.watching
  gwatch $O/$1.watching $O/$1.foreign 8>&- 9>&- &
  WGP=$!
}
wstop() {    # wstop NAME: the watch ends; one foreign GPU user seen during the step = foreign_NAME FAIL (the step is void)
  rm -f $O/$1.watching; [ -n "$WGP" ] && wait $WGP 2> /dev/null; WGP=""
  [ -s $O/$1.foreign ] && gate foreign_$1 FAIL "seen during $1 ($(wc -l < $O/$1.foreign) sample(s)): $(head -1 $O/$1.foreign | cut -c1-160) - VOID"
  return 0
}
e7() {   # e7 LABEL CONFIG [REF]: exact7 at pin 2500 (bringup/lib/exact7.sh: 7 items, --adapt-swaps 0 --suffix-draft 0)
  ok_to_go || { say "skipped exact7 $1 (deadline or kernel check)"; return 1; }
  gpu_clear $1 || { say "exact7 $1 NOT started (a foreign GPU user)"; return 1; }
  say "exact7 $1 ($(basename $2)${3:+ against $3})"
  wstart $1
  if [ -n "${3:-}" ]; then PIN_CACHE=2500 REF=$3 $LIB/exact7.sh $1 $2 2>&1 | tail -9 | tee -a $S
  else PIN_CACHE=2500 $LIB/exact7.sh $1 $2 2>&1 | tail -9 | tee -a $S; fi
  wstop $1
  kc e7-$1
}
e7g() { $P -I -B $RU e7gate $S $1 --gate $2 --gates $G ${3:-} | tee -a $S; }
ndiff() {   # ndiff DIR_A DIR_B: "differing files of all" over A's first.* logit files
  local nd=0 nf=0 f
  for f in $1/first.*; do [ -e "$f" ] || continue; nf=$((nf + 1)); cmp -s $f $2/$(basename $f) || nd=$((nd + 1)); done
  echo "$nd $nf"
}
darm() {   # darm ARM PASS: one screen pass on a fresh server (gap 17's darm without the edit set): warm-up, W1-W3, the 2
  # agent turns, the 4 research replays (the 9 workloads)
  local a=$1 k=$2 n=$1$2 cfg pf="" L off pc
  case $a in B) cfg=$X;; P) cfg=$H; pf=--pins;; esac
  fits 5 || { say "skipped screen $n (under 5 min to the deadline, or a kernel check failed)"; return 1; }
  gpu_clear $n || { say "screen $n NOT started (a foreign GPU user)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "screen $n ($(basename $cfg))"
  wstart $n
  $LIB/with_server.sh g23p-$n $cfg -- "$P -I -B $RU envcheck $(exe_of $cfg) $cfg --ngpu 2 $pf --gate env_$n --gates $G && bash $KR/abarm.sh http://127.0.0.1:8081 $off $R $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|vram" | tee -a $S
  wstop $n
  tail -c +$((off + 1)) $L > $R/$n.engine.log
  fatalchk $n $L $off g23p-$n
  pc=$($P -I -B $RU pcie $R/$n.engine.log 2> /dev/null | cut -c1-160)
  gate pcie_$n INFO "${pc:-no PCIe share line}"
  kc $n
}
bprun() {   # bprun BUILD SET PASS: Basalt's community-1 set, cold (a fresh engine), one pass; M = x28h, H = P0211x-h,
  # P10 = P0210x-h (the v0.2.10 port, INFO)
  local b=$1 set=$2 k=$3 n=bp$1-$2-$3 cfg tree pf="" L off
  case $b in M) cfg=$X; tree=$W28;; H) cfg=$H; tree=$W; pf=--pins;; P10) cfg=$H10; tree=$W10; pf=--pins;; esac
  fits 3 || { say "skipped Basalt $n (deadline or kernel check)"; return; }
  gpu_clear $n || { say "Basalt $n NOT started (a foreign GPU user)"; return; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  wstart $n
  $LIB/with_server.sh g23p-$n $cfg -- "$P -I -B $RU envcheck $(exe_of $cfg) $cfg --ngpu 2 $pf --gate env_$n --gates $G && $P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label $n --sets $set --passes 1 --first-pass $k --tree $tree --out $BO/cold-$b.jsonl" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  wstop $n
  fatalchk $n $L $off g23p-$n
  kc $n
}
utest() {   # utest NAME TIMEOUT_S CMD...: one unit test under guard.py; its output in $UT/NAME.txt; echoes the rc
  local n=$1 t=$2 rc; shift 2
  timeout $t "$@" > $UT/$n.txt 2>&1 < /dev/null 8>&- 9>&-; rc=$?
  say "  $n rc $rc: $(grep -v '^\s*$' $UT/$n.txt | tail -1 | cut -c1-160)"
  return $rc
}
after_gap() {   # CPU only, nice 19, 8080 back: the speed table, Basalt's report, the NLL compare (INFO), the decision
  local labs l
  labs=$(ls $R/*.jsonl 2> /dev/null | xargs -n1 basename 2> /dev/null | sed 's/\.jsonl$//' | grep -E '^[BP][123][nar]$' | sort | tr '\n' ' ')
  [ -n "$labs" ] && nice -n 19 $P $BA/scripts/abreport.py --dir $R $labs > $O/speed-table.md 2>&1
  BP90_NAME_H="v0.2.11 port, pinned (P0211x-h)" nice -n 19 $P -I $B90/bp90_report.py $BO > $BO/report.md 2>&1 || true
  sed -i 's/P021m (served)/P028x (x28h)/g' $BO/report.md 2> /dev/null
  if [ -f $NO/p211/index.json ] && [ "$(gstat run_nllp211)" = PASS ] && [ "$(gstat env_nllp211)" = PASS ]; then
    for l in x28h x28h-unfused x28h-cpushare; do [ -e $NO/$l ] || ln -s $NLLG/$l $NO/$l; done
    nice -n 19 $P -I -B $NR ident $NO/p211 $NO/x28h --gate nll_ident --gates $G | tee -a $S
    say "many-positions NLL (INFO, Karl 11-05: the bound is revoked): p211 against the NLL gap's x28h / x28h-unfused, x28h-cpushare"
    nice -n 19 $P -I $SCORE --threads 4 compare $NO --ref x28h --refs x28h-unfused,x28h-cpushare --cands p211 \
      --block-scan 2048,text --json $NO/result.json > $NO/compare.txt 2>&1
    l=$(grep -E "^ *p211\b" $NO/compare.txt | tail -1 | tr -s ' ' | cut -c1-220)
    gate nll_info INFO "${l:-see $NO/compare.txt ($(tail -1 $NO/compare.txt | cut -c1-120))}"
  fi
  $P -I -B $RU decide $O > /dev/null 2>&1
  [ -f $O/decision.txt ] && cat $O/decision.txt | tee -a $S || say "port0211_rules.py decide failed - by hand: $P -I -B $RU decide $O"
}
end_gap() {
  if [ $KFAIL = 1 ]; then
    say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"
    $P -I -B $RU decide $O > /dev/null 2>&1 || true; exit 3
  fi
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "v0.2.11 port gate: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  after_gap
  say "v0.2.11 port gate done"
  exit 0
}

# ================================================================ 0 before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-port0211.sh (pre-gap checks)"
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
for f in $H $X $H10 $OFF $ST $S28 $NOV2 $RT $PX $RU $KR/g17_rules.py $NR $SCORE $KR/port_gap4.sh $KR/abarm.sh $KR/pf_yardstick.py \
         $KR/kernel_rule2.py $KR/kernel_rule3.py $KR/gap9_verdicts.py $KR/chatcache_checks.py $KR/vision_check.py \
         $TR/toolrecovery_live.py $B90/bp90_client.py $B90/bp90_report.py $BA/scripts/abreport.py $LIB/with_server.sh \
         $LIB/exact7.sh $LIB/guard.py $LIB/kcheck.sh $W/serve/server.py $W10/serve/server.py $W28/serve/server.py $GGUF \
         $W/docs/terminal-previews/serving-110-stages.png $Y8/ref/index.json $Y16/x28h/index.json $Y17/p210/index.json \
         $WS/bringup/out/logs/prof/g17-p210a-x-math.out $NLLG/x28h/index.json; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ -x $E28/strata ] && [ "$(sha12 $E28/strata)" = $P028X_SHA ] || { say "engine-r22p028x is not P028x ($P028X_SHA) - not started"; exit 1; }
[ -x $E10/strata ] && [ "$(sha12 $E10/strata)" = "$(cut -c1-12 $E10/SHA256)" ] || { say "engine-r22p0210 does not match its SHA256 file - not started"; exit 1; }
# 11-05 19:0x (Claude): the worktree's head = the build's head, or a descendant of it whose changes since then touch only
# serve/server.py and tools/iq_pack.py (5f5aebcc2, the 11-05 review's two Python fixes: no engine source changed, the
# engine built from PORT_HEAD stays the build under test; the gate's server.py is the tree's, so it includes the fixes)
head_ok() { local h ch
  h=$(git -C $W rev-parse HEAD 2> /dev/null) || return 1
  [ "${h:0:9}" = "${PORT_HEAD:0:9}" ] && return 0
  git -C $W merge-base --is-ancestor "$PORT_HEAD" "$h" 2> /dev/null || return 1
  ch=$(git -C $W diff --name-only "$PORT_HEAD" "$h" | grep -vxE 'serve/server\.py|tools/iq_pack\.py')
  [ -z "$ch" ]
}
if [ ! -x $EXE ] || [ "$(sha12 $EXE)" != "$(cut -c1-12 $E/SHA256 2> /dev/null)" ] \
   || ! grep -q "^v0.2.11 + 28 commits (branch r23-port0211 $PORT_HEAD" $E/SOURCE 2> /dev/null \
   || ! head_ok || [ -n "$(git -C $W status --porcelain --untracked-files=no)" ]; then
  say "engine-r23p0211 is not the recorded build of r23-port0211 $PORT_HEAD (or the worktree moved / is dirty) - not started (P0211_PORT_HEAD for a rebuilt port)"; exit 1
fi
if [ ! -x $EST/strata ] || [ "$(sha12 $EST/strata)" != "$(cut -c1-12 $EST/SHA256 2> /dev/null)" ] \
   || ! grep -q "^stock v0.2.11 ($(git -C $WS/strata rev-parse 'v0.2.11^{commit}')" $EST/SOURCE 2> /dev/null \
   || [ "$(git -C $WST rev-parse HEAD 2> /dev/null)" != "$(git -C $WS/strata rev-parse 'v0.2.11^{commit}')" ]; then
  say "engine-v0211stock is not the recorded stock v0.2.11 build - not started"; exit 1
fi
for t in patch_guard_test cost_gate_test draft_cum_test spec_prob_test gated_proposal_test spec_verify_parity spec_proposal_parity prefill_fused_iq_test native_expert_parity; do
  [ -x $BT/$t ] || { say "missing test binary $BT/$t (build-port0211.sh tests) - not started"; exit 1; }
done
for c in $H $OFF $NOV2 $RT $PX; do [ "$(exe_of $c)" = $EXE ] || { say "$(basename $c)'s exe is not $EXE - not started"; exit 1; }; done
[ "$(exe_of $ST)" = $EST/strata ] && [ "$(exe_of $X)" = $E28/strata ] && [ "$(exe_of $H10)" = $E10/strata ] || { say "s0211-h / x28h / P0210x-h do not name their engines - not started"; exit 1; }
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 20 ] || { say "only ${free} GB free on results/ - not started"; exit 1; }
PREV=""
if [ -d $O ] && ls -A $O | grep -q .; then   # the rules judge only this attempt's files
  PREV=$D/gap-prev-$(date +%m%d-%H%M%S); mv $O $PREV
fi
mkdir -p $O $R $Y $BO $NO $TC/B $TC/P $UT
S=$O/summary.txt
say "v0.2.11 PORT GATE (work/r23/gap-port0211.sh): the pinned-off port against P028x - measurements only, P028x stays served, nothing switches (Karl 11-05)"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
gate build_x PASS "engine-r23p0211 $(sha12 $EXE) = $(head -1 $E/SOURCE | cut -c1-120)"
gate build_stock PASS "engine-v0211stock $(sha12 $EST/strata) = $(head -1 $EST/SOURCE | cut -c1-100)"
gate build_tests PASS "$BT: the 9 test binaries"
n8=$(cat $W/build-configure.log $W/build-tests-configure.log $WST/build-configure.log 2> /dev/null | grep -c 'windows hold up to 8 rows')
[ "$n8" = 3 ] && gate build8 PASS "the port, its tests and stock: verify windows hold up to 8 rows" || gate build8 FAIL "$n8 of 3 configure logs say 8 rows"
$P -I -B $RU pins $PX --gate pins --gates $G | tee -a $S
$P -I -B $RU pins $H --gate pins_h --gates $G | tee -a $S
say "0 the CPU-only tests (nice 19; the C++ ones with CUDA_VISIBLE_DEVICES empty, so none can reach a GPU)"
bad=""
for t in patch_guard_test cost_gate_test draft_cum_test; do
  a=""; [ $t = patch_guard_test ] && a="$GGUF $MTP"
  utest $t 900 env CUDA_VISIBLE_DEVICES= nice -n 19 $BT/$t $a || bad="$bad $t"
done
[ -z "$bad" ] && gate tests PASS "patch_guard, cost_gate, draft_cum rc 0" || gate tests FAIL "rc != 0:$bad"
bad=""
for t in spec_prob_test gated_proposal_test; do
  utest $t 900 env CUDA_VISIBLE_DEVICES= STRATA_OLD_SAMPLER=0 STRATA_SAMPLER_ONE_BLOCK=0 nice -n 19 $BT/$t || bad="$bad $t"
done
[ -z "$bad" ] && gate sampler_cpu PASS "spec_prob_test, gated_proposal_test rc 0" || gate sampler_cpu FAIL "rc != 0:$bad"
mkdir -p $UT/tmp
( cd $UT && TMPDIR=$UT/tmp PYTHONDONTWRITEBYTECODE=1 timeout 2400 nice -n 19 $P -m unittest discover -s $W/serve -t $W -p 'test_*.py' > $UT/servetests.txt 2>&1 < /dev/null 8>&- 9>&- )
tail -3 $UT/servetests.txt | tee -a $S
$P -I -B $RU servetests $UT/servetests.txt --gate servetests --gates $G | tee -a $S
nice -n 19 $P -I -B $RU fence4 $W --gate fence4 --gates $G | tee -a $S
PREFAIL=$(for k in build8 pins pins_h tests sampler_cpu servetests fence4; do [ "$(gstat $k)" = PASS ] || echo $k; done | tr '\n' ' ')
if [ -n "$PREFAIL" ]; then
  say "pre-gap gate(s) not PASS: $PREFAIL- the baseline cannot pass, the gap is NOT opened (8080 untouched)"
  $P -I -B $RU decide $O > /dev/null 2>&1; exit 1
fi

# ================================================================ 1 the gap
$KR/port_gap4.sh begin "r23 v0.2.11 port gate (Karl 11-05: the pinned-off port against P028x; measurements only, P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

# ---- 2 the GPU unit tests
if ok_to_go && gpu_clear utests; then
  say "2 GPU unit tests: upstream's sampler parity tests, the v2 unit test (bit-identical H and down rows); INFO: the Q5_0 dot"
  bad=""
  for t in spec_verify_parity spec_proposal_parity; do
    utest $t 900 env STRATA_OLD_SAMPLER=0 STRATA_SAMPLER_ONE_BLOCK=0 $P $LIB/guard.py p211-$t -- $BT/$t || bad="$bad $t"
  done
  [ -z "$bad" ] && gate sampler_gpu PASS "spec_verify_parity, spec_proposal_parity rc 0" || gate sampler_gpu FAIL "rc != 0:$bad"
  utest prefill_fused_v2_test 1800 $P $LIB/guard.py p211-v2test -- $BT/prefill_fused_iq_test --v2 --no-timing \
    && gate v2_unit PASS "prefill_fused_iq_test --v2 rc 0" || gate v2_unit FAIL "prefill_fused_iq_test --v2 rc != 0 ($UT/prefill_fused_v2_test.txt)"
  q=""
  for pr in iq2_s/q5_0 iq3_xxs/q5_0 iq2_s/iq4_nl iq3_xxs/iq4_nl iq2_s/q2_0 iq4_xs/iq4_nl; do
    utest nep-${pr/\//-} 300 $P $LIB/guard.py p211-nep -- $BT/native_expert_parity --synthetic $pr; q="$q $pr:rc$?"
  done
  gate q5_0_parity INFO "native_expert_parity --synthetic:$q (rc 0 = within upstream's tolerance; the Q5_0-down pairs carry aa678f10d's dot)"
  kc utests
fi

# ---- 3 exact7 at pin 2500: "every switch off = the release" FIRST, then the port against P028x, its repeat, v2
say "3 exact7 at pin 2500"
e7 g23p-s211 $ST && e7 g23p-p211off $OFF g23p-s211 && e7g g23p-p211off e7_release
e7 g23p-x28h $X && e7 g23p-p211a $H g23p-x28h && e7g g23p-p211a e7_vs_p028x
if grep -q 'strata patch guards: 7 checked, 0 off' $WS/bringup/out/logs/prof/g23p-p211a-x-math.out 2> /dev/null; then
  gate guards PASS "$(grep -m1 -o 'strata patch guards: 7 checked, 0 off[^;]*' $WS/bringup/out/logs/prof/g23p-p211a-x-math.out)"
else gate guards FAIL "$(grep -m1 -o 'strata patch guards: [^;]*' $WS/bringup/out/logs/prof/g23p-p211a-x-math.out 2> /dev/null || echo 'no patch-guard line')"; fi
e7 g23p-p211b $H g23p-p211a && e7g g23p-p211b e7_repeat
if [ -n "$(gstat e7_vs_p028x)" ] && [ "$(gstat e7_vs_p028x)" != PASS ] && [ -x $E28S/strata ]; then
  say "the port is not exact7-identical to P028x: did upstream itself move (stock 0.2.8 vs stock 0.2.11, both pinned)?"
  e7 g23p-s028 $S28 g23p-s211 && e7g g23p-s028 e7_upstream
fi
e7 g23p-p211nov2 $NOV2 g23p-p211a && e7g g23p-p211nov2 e7_v2
[ -f $WS/bringup/out/logs/prof/g23p-p211a-x-112k.out ] && $P -I -B $RU e7cmp g23p-p211a g17-p210a --info --gate e7_vs_p0210 --gates $G | tail -2 | tee -a $S

# ---- 4 KL: pf_yardstick long40 on P; both KL rules against gap 8's references
if ok_to_go && gpu_clear pfy; then
  say "4 KL: pf_yardstick long40 on P0211x-h"
  for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
  wstart pfy
  $P $LIB/guard.py pfyp211 -- $P -I $KR/pf_yardstick.py run $H $Y/p211 --set long40 8>&- 9>&- 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy p211: /" | tee -a $S
  wstop pfy
  kc pfy
  if [ -f $Y/p211/index.json ]; then
    read nd nf <<< "$(ndiff $Y/p211 $Y16/x28h)"; gate logits_vs_p028x INFO "$nd of $nf first-token logit files differ from gap 16's x28h"
    read nd nf <<< "$(ndiff $Y/p211 $Y17/p210)"; gate logits_vs_p0210 INFO "$nd of $nf first-token logit files differ from gap 17's p210 (the v0.2.10 port)"
    $P $KR/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands p211 2>&1 | tee $O/kl-p211.txt | tee -a $S
    $P -I $KR/kernel_rule3.py $Y --ref ref --refs unfused,cpushare --cands p211 2>&1 | tee $O/kl3-p211.txt | tee -a $S
    l2=$(grep -E "^p211 +top-1" $O/kl-p211.txt | tr -s ' ' | cut -c1-160); l3=$(grep -E "^p211 +KL mean" $O/kl3-p211.txt | tr -s ' ' | cut -c1-170)
    echo "$l2" | grep -q -- '-> PASS' && gate kl2_p211 PASS "$l2" || gate kl2_p211 FAIL "${l2:-no line}"
    echo "$l3" | grep -q -- '-> PASS' && gate kl3_p211 PASS "$l3" || gate kl3_p211 FAIL "${l3:-no line}"
  fi
fi

# ---- 5 the 9-workload screen, 3 passes in turned order: B (x28h = P028x), P (the port)
say "5 the screen: B P x 3 passes in turned order"
for k in 1 2 3; do
  case $k in 1) order="B P";; 2) order="P B";; 3) order="B P";; esac
  for a in $order; do darm $a $k; done
done
[ -f $R/P1.startlog ] && $P -I -B $RU startlines $R/P1.startlog $R/P1?.englog $(slog g23p-P1) --gate startlines_P --gates $G | tee -a $S
if ls $R/P[123][nar].englog > /dev/null 2>&1; then
  $P $KR/gap9_verdicts.py cont $R/P[123][nar].englog > $O/cont-P.txt 2>&1
  r=$(grep -oE '[0-9]+ hits, [0-9]+ misses' $O/cont-P.txt | tail -1); h=$(echo "$r" | grep -oE '^[0-9]+'); m=$(echo "$r" | grep -oE '[0-9]+ misses' | grep -oE '[0-9]+')
  if [ -n "$h" ] && [ "$h" -ge 1 ] && [ "${m:-1}" = 0 ]; then gate cont_P PASS "continuations: $r"; else gate cont_P FAIL "continuations: ${r:-none found}"; fi
fi

# ---- 6 Basalt's community-1 fixtures, cold (a fresh engine per measurement), 3 passes: M = x28h, H = the port
# (decode, 16K, 64K); P10 = the v0.2.10 port on decode (INFO)
say "6 Basalt's fixtures, cold, 3 passes: M (x28h) and H (P0211x-h) decode / pp16k / pp64k; P10 (P0210x-h, INFO) decode"
for k in 1 2 3; do
  case $k in 1) order="M H P10";; 2) order="P10 H M";; 3) order="H M P10";; esac
  for b in $order; do
    case $b in P10) sets="decode";; *) sets="decode pp16k pp64k";; esac
    for set in $sets; do bprun $b $set $k; done
  done
done

# ---- 7 the served form (chat cache resumed = fresh, chat_drop, a picture) and the live tool-call test, B vs P
if fits 6 && gpu_clear rt; then
  say "7 the served form on P0211x-RTpin-vision: chat-cache checks + a picture (v0.2.11's PICTURE_FORMATS, Pillow $($P -I -c 'import PIL; print(PIL.__version__)'))"
  IMG=$W/docs/terminal-previews/serving-110-stages.png; L=$(elog $RT); touch $L; off=$(stat -c %s $L)
  wstart rt
  $LIB/with_server.sh g23p-rt $RT -- "$P -I -B $RU envcheck $EXE $RT --ngpu 2 --pins --gate env_rt --gates $G && { $P $KR/chatcache_checks.py http://127.0.0.1:8081 \$ELOG > $O/chatcache.txt 2>&1; $P $KR/vision_check.py http://127.0.0.1:8081 $IMG $O/picture > $O/vision.txt 2>&1; }" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|ready|exited|refus|Error|GUARD" | tee -a $S
  wstop rt
  fatalchk rt $L $off g23p-rt
  kc served
  grep -E "^(PASS|FAIL)|ALL PASS|FAILED" $O/chatcache.txt 2> /dev/null | tee -a $S
  grep -q "ALL PASS" $O/chatcache.txt 2> /dev/null && gate chatcache PASS "ALL PASS" || gate chatcache FAIL "$(grep -c '^FAIL' $O/chatcache.txt 2> /dev/null) FAIL lines"
  nv=$(grep -c '"answer_chars": [1-9]' $O/vision.txt 2> /dev/null)
  [ "$nv" = 2 ] && gate vision PASS "2 answers (read by hand afterwards: picture-1.txt, picture-2.txt)" || gate vision FAIL "${nv:-0} of 2 answers"
fi
if fits 14; then
  say "7 the live tool-call test (work/r22/toolrecovery, 27 prompts x 2, the same seeds): B (x28h) vs P (P0211x-h), recovery off"
  for a in B P; do
    case $a in B) cfg=$X; pf="";; P) cfg=$H; pf=--pins;; esac
    ok_to_go && gpu_clear tc$a || break
    L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
    wstart tc$a
    $LIB/with_server.sh g23p-tc$a $cfg -- "$P -I -B $RU envcheck $(exe_of $cfg) $cfg --ngpu 2 $pf --gate env_tc$a --gates $G && $P -B $TR/toolrecovery_live.py http://127.0.0.1:8081 --label g23p-$a --reps 2 --out-dir $TC/$a" 8>&- 9>&- 2>&1 \
      | grep -E "engine pid [0-9]+:|ENV CHECK|TOTAL|ready|exited|refus|Error|GUARD" | tee -a $S
    wstop tc$a
    fatalchk tc$a $L $off g23p-tc$a
    kc tc$a
  done
  MJ=$(ls -t $TC/B/live-g23p-B-*.jsonl 2> /dev/null | head -1); XJ=$(ls -t $TC/P/live-g23p-P-*.jsonl 2> /dev/null | head -1)
  if [ -n "$MJ" ] && [ -n "$XJ" ]; then $P -I -B $RU toolcalls $MJ $XJ --gate toolcalls --gates $G 2>&1 | tee $TC/compare.txt | tee -a $S
  else gate toolcalls FAIL "a result file is missing"; fi
fi

# ---- 8 INFO: the many-positions NLL arm on P (Karl 11-05: information only, the bound is revoked) - only if it fits
if fits 9 && gpu_clear nllp211; then
  say "8 INFO: the many-positions NLL arm p211 (score.py run, --set long11 --rows all:8; the NLL gap's x28h is the reference)"
  rm -f $NO/p211.rc
  ( $P $LIB/guard.py nllp211 -- $P -I $SCORE run $H $NO/p211 --set long11 --rows all:8 > $NO/p211.run.txt 2>&1; echo $? > $NO/p211.rc ) 8>&- 9>&- &
  jp=$!
  wstart nllp211
  $P -I -B $NR envwatch $jp $H --kill --gate env_nllp211 --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wstop nllp211
  wait $jp
  rc=$(cat $NO/p211.rc 2> /dev/null || echo none)
  if [ "$rc" = 0 ] && [ -f $NO/p211/index.json ]; then gate run_nllp211 PASS "score.py run rc 0: $(grep -E 'rows from [0-9]+ texts' $NO/p211.run.txt | tail -1)"
  else gate run_nllp211 INFO "rc $rc (INFO arm; not judged): $(grep -E '^PROBLEM|Error' $NO/p211.run.txt | head -2 | tr '\n' ' ' | cut -c1-200)"; fi
  kc nll
else say "8 the many-positions NLL arm (INFO) not started (9 min do not fit, or a stop)"; fi

# ---- 9 lossless (the config + P's engine log of this gap), #3961's lost-answer line in the port's server logs
CFG=$H TREE=strata-r23p0211 ELOG=$(elog $H) $WS/bringup/patchtest.sh lossless 2>&1 | grep -E "PASS|FAIL" | tail -6 | tee $O/lossless.txt | tee -a $S
grep -q 'cfg: PASS' $O/lossless.txt && ! grep -q FAIL $O/lossless.txt && gate lossless PASS "cfg + log clean" || gate lossless FAIL "$(tail -1 $O/lossless.txt | cut -c1-140)"
SL=$(for l in g23p-P1 g23p-P2 g23p-P3 g23p-rt g23p-tcP $(for k in 1 2 3; do for s in decode pp16k pp64k; do echo g23p-bpH-$s-$k; done; done); do slog $l; done | tr '\n' ' ')
[ -n "$SL" ] && $P -I -B $RU lost $SL --gate lost_answers --gates $G | tee -a $S || gate lost_answers FAIL "no server log of the port's arms"
end_gap
