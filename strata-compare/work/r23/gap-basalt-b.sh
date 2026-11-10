#!/bin/bash
# gap-basalt-b.sh - r23, the gate of the Basalt prompt-path port, PART B (speed; GATE-PLAN.md section 4,
# results/r23/basalt-prompt/). WRITTEN 11-04, NOT RUN. Started by work/r23/gap-series.sh (`bash <driver>`, no arguments)
# as the last gap of Karl's 11-04 series. P028x stays served; NOTHING SWITCHES until item 7 is done.
#   0 before the gap (no GPU, 8080 untouched): REFUSES (exit 1) unless part a's decision-a.txt says BUILD PASS, BASELINE
#     PASS, PART_B ALLOWED and engine-r23basalt is still part a's build; refuses if tmp/gpu-test.lock is held, another
#     gap is open or a model server other than the 8080 queue's P028x runs. The arms priced = B + the parts part a
#     classed EXACT / ROUNDING-LEVEL + S (S_PARTS) + C (C_PARTS + --prefill auto:C_CHUNK + FIRST_CHUNK, only when C
#     passed); their configs are (re)written into results/r23/basalt-prompt/gap-configs/ and checked
#   1 port_gap4.sh begin
#   2 B1 Basalt's cold pp16k / pp64k (bp90_client.py; a fresh engine per measurement), 3 passes in turned order (the
#     arms, then reversed, then as first)
#   3 B2 Basalt's decode fixtures (conv, struct, prose), 1 pass, B S C
#   4 B3 the 9-workload screen (work/r22/abarm.sh: W1-W3, agent x2, research4 x4; T 1.0 / 0.95 / 20 / min-p 0.05,
#     effort medium; a warm-up first), 3 passes in turned order (B S C, C S B, S C B)
#   5 B4 the chat-cache trade of T and C (round-11 #693): per arm B / T / C a fresh engine with STRATA_TRACE=1, request 1 =
#     the bp90 16K prompt, request 2 = its first ~16,500 tokens + another question, request 3 = request 1 + its answer +
#     a follow-up (basalt_rules.py chat3) - reported, Karl decides the trade
#   6 basalt_rules.py decide-b -> results/r23/basalt-prompt/gap-b/decision-b.txt; port_gap4.sh end (P028x back)
# Every test server's engine environment is checked before it measures (envcheck: the config's env exactly,
# STRATA_ROUTE_TAIL_SKIP=0, no stray switch, the config's --prefill). Children run with 8>&- 9>&-. A kernel-check failure
# stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). No new step after GB_MAX_MIN (default 150)
# minutes with 8080 down. Exit 0 = done, 1 = refused / not opened (8080 untouched), 3 = kernel check failed (gap open),
# 4 = port_gap4.sh end failed. Steps and times: work/r23/GAPS-README.md (or GAPS-BASALT-README.md).
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock fd reaches a child
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; RU=$WS/work/r23/basalt_rules.py; KR=$WS/work/r22; B90=$KR/basalt-pr90; LIB=$WS/bringup/lib
R=$WS/results/r23/basalt-prompt; OA=$R/gap-a; O=$R/gap-b; CF=$R/gap-configs; S=$O/summary-b.txt; G=$O/gates.txt
BO=$O/bp90; SPD=$O/speed; CH=$O/chat
W=$WS/strata-r23basalt; E23=$WS/engine-r23basalt
P028X_SHA=f4c4f654fb24
MAXM=${GB_MAX_MIN:-150}
mkdir -p $R $WS/logs $WS/tmp/r22
STARTS=$R/gap-b-starts.log
say() { echo "=== $(date '+%F %T') $*" | tee -a ${SAY_TO:-$STARTS}; }
gate() { echo "$1 $2 ${*:3} [23b $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
KFAIL=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc() { $LIB/kcheck.sh "r23bb-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }

preflight() {   # as part a: refuse when the GPU lock is held, another gap is open, or a model server other than the 8080
  # queue's P028x runs (engines by exact name + NVIDIA compute processes, by their ancestry to the 8080 listener)
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
engines_left() { local x out=""; for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x > /dev/null && out="$out $x"; done; echo $out; }

fatalchk() {   # fatalchk GATE ENGINE_LOG OFFSET LABEL
  local L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || gate $1 FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite ($L from byte $off; $sl)"
}

srvrun() {   # srvrun ARM LABEL CONFIG GATE_STEP SLICE CMD: one fresh test server, its engine's env checked, then CMD
  local arm=$1 lab=$2 cfg=$3 st=$4 sl=$5 cmd=$6 L off
  ok_to_go || { say "skipped $lab (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "server $lab ($(basename $cfg))"
  $LIB/with_server.sh $lab $cfg -- "$P -I -B $RU envcheck $E23/strata $cfg --gate env_${arm}_$st --gates $G && $cmd" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |request [123]:|tok/s|ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  [ "$sl" = - ] || tail -c +$((off + 1)) $L > $sl
  fatalchk fatal_${arm}_$st $L $off $lab
  kc $lab
}

bprun() {   # bprun ARM SET PASS: Basalt's community-1 set, cold (a fresh engine), one pass -> bp90/cold-ARM.jsonl
  local a=$1 set=$2 k=$3 out=$BO/cold-$1.jsonl
  [ $set = decode ] && out=$BO/cold-${a}d.jsonl
  srvrun $a r23b-bp$a-$set-$k $CF/r23-$a.json bp$k$set - \
    "$P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label r23b-$a-$set --sets $set --passes 1 --first-pass $k --tree $W --out $out"
}

darm() {   # darm ARM PASS: one screen pass on a fresh server - warm-up, W1-W3, the 2 agent turns, the 4 research replays
  local a=$1 k=$2 n=$1$2 cfg=$CF/r23-$1.json L off
  ok_to_go || { say "skipped screen $n (deadline or kernel check)"; return; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  srvrun $a r23b-$n $cfg scr$k - "bash $KR/abarm.sh http://127.0.0.1:8081 $off $SPD $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1"
}

end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I -B $RU decide-b $O --decision-a $OA/decision-a.txt > /dev/null 2>&1 8>&- 9>&-
  [ -f $O/decision-b.txt ] && tee -a $S < $O/decision-b.txt || say "basalt_rules.py decide-b failed - rerun it by hand ($RU decide-b $O --decision-a $OA/decision-a.txt)"
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "Basalt gap part b done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "BASALT PROMPT-PATH GATE part b (work/r23/gap-basalt-b.sh): speed (a test; P028x stays served, nothing switches)"
if ! $P -I -B $RU preb $OA/decision-a.txt > $R/gap-b-preb.txt 2>&1; then
  say "REFUSED: $(head -1 $R/gap-b-preb.txt) - part b needs part a's build and exact checks (results/r23/basalt-prompt/gap-a/decision-a.txt)"
  exit 1
fi
say "$(head -1 $R/gap-b-preb.txt)"
SP=$(sed -n 's/^S_PARTS=//p' $R/gap-b-preb.txt); CP=$(sed -n 's/^C_PARTS=//p' $R/gap-b-preb.txt); CC=$(sed -n 's/^C_CHUNK=//p' $R/gap-b-preb.txt)
cls() { sed -n "s/^CLASS_$1=//p" $R/gap-b-preb.txt; }
BSHA=$(grep '^build_r23 PASS' $OA/gates.txt | tail -1 | grep -oE 'engine-r23basalt [0-9a-f]{12}' | cut -d' ' -f2)
if [ ! -x $E23/strata ] || [ -z "$BSHA" ] || [ "$(sha12 $E23/strata)" != "$BSHA" ] || [ "$(cut -c1-12 $E23/SHA256)" != "$BSHA" ]; then
  say "REFUSED: engine-r23basalt is not part a's build (${BSHA:-no build_r23 gate}) - not started"; exit 1
fi
preflight
for f in $RU $B90/bp90_client.py $KR/abarm.sh $LIB/with_server.sh $KR/port_gap4.sh $W/serve/server.py; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
if [ -e $O ]; then PREV=$R/gap-b-prev-$(date +%m%d-%H%M%S); mv $O $PREV; say "an earlier attempt's outputs moved to $PREV"; fi
mkdir -p $O $BO $SPD $CH
SAY_TO=$S; cat $STARTS >> $S 2> /dev/null
# the arms: B + every part gap a classed EXACT / ROUNDING-LEVEL, S, and C when it passed
ARMS1="B"
for x in A T U K KP G; do case $(cls $x) in EXACT|ROUNDING-LEVEL) ARMS1="$ARMS1 $x";; esac; done
[ -n "$SP" ] && ARMS1="$ARMS1 S"
HAVE_C=0; [ "$(cls C)" = ROUNDING-LEVEL ] && [ -n "$CC" ] && { ARMS1="$ARMS1 C"; HAVE_C=1; }
if [ $HAVE_C = 1 ]; then
  $P -I -B $RU arms $CF --stack "$SP" --cstack "$CP" --cap $CC --gate cfg --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
else
  $P -I -B $RU arms $CF --stack "$SP" --gate cfg --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
fi
[ "$(gst cfg)" = PASS ] || { say "the arm configs are not P0210x-h + their switches - not started"; exit 1; }
say "arms priced: $ARMS1 (S = ${SP:-none}; C = ${CP:-B} + --prefill auto:${CC:--} + FIRST_CHUNK$([ $HAVE_C = 1 ] || echo ': not priced'))"
REV=$(echo $ARMS1 | tr ' ' '\n' | tac | tr '\n' ' ')
SCR="B"; [ -n "$SP" ] && SCR="$SCR S"; [ $HAVE_C = 1 ] && SCR="$SCR C"

# ================================================================ the gap
$KR/port_gap4.sh begin "Basalt prompt-path gate part b: speed (a test; P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
kc open || end_gap
for i in $(seq 60); do [ -z "$(engines_left)" ] && break; sleep 2; done
if [ -n "$(engines_left)" ]; then say "engine processes still running 120 s after 8080 stopped: $(engines_left) - ending the gap"; end_gap; fi
for i in $(seq 24); do [ "$(awk '/^MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo)" -ge 40 ] && break; sleep 5; done
say "8080 down: no engine left, MemAvailable $(awk '/^MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo) GB"

# ---- 2 B1 Basalt's cold fixtures, prompts: 3 passes in turned order
say "B1 Basalt's cold pp16k / pp64k, a fresh engine per measurement, 3 passes: $ARMS1 / $REV/ $ARMS1"
for k in 1 2 3; do
  case $k in 2) order=$REV;; *) order=$ARMS1;; esac
  for a in $order; do for set in pp16k pp64k; do bprun $a $set $k; done; done
done

# ---- 3 B2 Basalt's decode fixtures, 1 pass: the parts must not move decode
say "B2 Basalt's decode fixtures (conv, struct, prose), 1 pass: $SCR"
for a in $SCR; do bprun $a decode 1; done

# ---- 4 B3 the 9-workload screen, 3 passes in turned order
if [ "$SCR" != B ]; then
  say "B3 the 9-workload screen, 3 passes in turned order: $SCR"
  for k in 1 2 3; do
    case $k in 1) order="B S C";; 2) order="C S B";; 3) order="S C B";; esac
    for a in $order; do case " $SCR " in *" $a "*) darm $a $k;; esac; done
  done
else
  say "B3 not run: no S or C to screen"
fi

# ---- 5 B4 the chat-cache trade of T and C
say "B4 the chat-cache trade (#693): B, T, C with STRATA_TRACE=1, request 2 shares ~16,500 tokens with request 1"
for a in B T C; do
  case $a in T) case $(cls T) in ROUNDING-LEVEL) ;; *) say "  T not in B4 (part a: $(cls T))"; continue;; esac;; C) [ $HAVE_C = 1 ] || continue;; esac
  srvrun $a r23b-chat$a $CF/r23-${a}c.json chat $CH/chat-$a.englog \
    "$P -I -B $RU chat3 http://127.0.0.1:8081 --label r23b-chat$a --out $CH/chat-$a.jsonl --tree $W"
done
$P -I -B $RU chatrep $CH --gate chat_trade --gates $G 8>&- 9>&- | tee -a $S
if [ $HAVE_C = 1 ]; then
  labs=""; for k in 1 2 3; do for set in pp16k pp64k; do labs="$labs srv-r23b-bpC-$set-$k"; done; labs="$labs srv-r23b-C$k"; done
  $P -I -B $RU vram $labs srv-r23b-bpC-decode-1 srv-r23b-chatC --gate vram_Cb --gates $G 8>&- 9>&- | tee -a $S
fi

# ---- 6 the rules, P028x back
end_gap
