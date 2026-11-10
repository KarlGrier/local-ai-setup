#!/bin/bash
# conc21.sh - the user's 10-20 afternoon request: a short concurrency test on 0.2.1 (P021) in the next gap between
# Phase 4 runs (never interrupting one), ~45 min max.
#   gap    the Phase 4 queue holds before its next run (deep-research tmp/bench2.hold), the running research run
#          finishes, no Jan job is active; then the measurement lock (shared) is taken and 8080 stopped
#   arms   on 8081 (bringup/lib/with_server.sh: guard 12 GiB, kernel check after each), copies of configs/P021.json:
#            base   as served: one request at a time, the 4060 Ti helper cache (the "one at a time" reference)
#            b4     + --batch 4 (slots sized for 4), batch-mtp off (the default), helper kept
#            b4mtp  + --batch 4 --batch-mtp (forced on), helper kept
#          (b4 / b4mtp: --vram-reserve-mib 1213 instead of 713, as round 20's D needed for batch windows)
#          work/r22/conc21.py: chat = 4 short turns, agent = 4 ~20K-token coding-agent prompts with tools; 512
#          tokens out every request, thinking off, so each request generates exactly max_tokens and answer_room has
#          nothing to change; the user's sampling; N = 1,2,4 (b4mtp: 2,4), 2 reps (1,2,4 then 4,2,1)
#   check  b4 and b4mtp: greedy, each prompt alone then all 4 together, texts compared (rounding-level or not)
#   end    8080 back on P021 (strata-ensure.sh; engine SHA checked; the chat-cache policy is not touched), the lock
#          released, the queue's hold removed, NOTES lines
# Time box 45 min from the gap's start: later arms drop to 1 rep / skip the check when time runs short.
# A kernel error stops everything with 8080 down and the queue held.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; DR=/home/USER/ai/deep-research; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/suite/.venv/bin/python; O=$WS/results/r22/conc; S=$O/summary.txt; mkdir -p $O logs/r22
HOLD=$DR/tmp/bench2.hold; LOCKPID=$WS/tmp/port-gap.lockpid
P021_SHA=c9fe314316c4
BOX=2700
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22c-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; 8080 down, the queue held"; exit 3; }; }
left() { echo $(( BOX - ($(date +%s) - T0) )); }
jan_active() {
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$DR/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE for j in rc.all_jobs()) else 1)"
}
startlines() {   # what the engine says about slots, drafters, the expert caches and VRAM
  grep -E "slot sessions|slot drafters|batch-mtp|batch_slots|expert cache auto|expert cache [0-9]+ slots|device1|helper|pinned" "$1" \
    | grep -vE "^\[strata\] (reading|done)|hit rate" | head -14 | cut -c1-230
}
arm() {   # arm NAME LEVELS CHECK(0/1)
  local name=$1 levels=$2 check=$3 reps=2
  [ $(left) -lt 1500 ] && reps=1
  [ $(left) -lt 1200 ] && check=0
  [ $(left) -lt 480 ] && { say "time box: arm $name skipped ($(left) s left)"; return; }
  say "arm $name: levels $levels, $reps reps, output check $check ($(left) s left)"
  local C="$P work/r22/conc21.py run --endpoint http://127.0.0.1:8081 --arm $name --levels $levels --reps $reps"
  local G="$P work/r22/conc21.py run --endpoint http://127.0.0.1:8081 --arm $name-greedy --greedy --same-nonce --reps 1 --levels 1,4 --solo-n 4"
  local CMD="$C --kind chat && $C --kind agent"
  [ "$check" = 1 ] && CMD="$CMD && $G --kind chat && $G --kind agent"
  : > logs/r22/engine-conc-$name.log
  bringup/lib/with_server.sh conc-$name configs/r22-conc-$name.json -- "$CMD" > logs/r22/conc-$name.out 2>&1
  grep -E "^vram|^engine pid|^\{" logs/r22/conc-$name.out | grep -v '"solo_seq"' | cut -c1-330 | tee -a $S
  echo "guard: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200)" | tee -a $S
  echo "--- engine start lines ($name):" | tee -a $S; startlines logs/r22/engine-conc-$name.log | tee -a $S
  grep -E "strata batch:" logs/r22/engine-conc-$name.log | tail -4 | cut -c1-330 | tee -a $S
  if [ "$check" = 1 ]; then
    for k in chat agent; do $P work/r22/conc21.py match --arm $name-greedy --kind $k 2>&1 | tee -a $S; done
  fi
  kc $name
}

say "=== conc21: concurrency test on 0.2.1 (P021, engine $P021_SHA)"
echo "0.2.1 concurrency test (the user, 10-20 afternoon; ~45 min): $(date '+%F %T')" > $HOLD
say "queue hold set; waiting for the running research run to finish"
while ! flock -n $DR/run/bench.lock true; do sleep 20; done
say "research run done; waiting for any active Jan job"
while jan_active; do sleep 60; done
T0=$(date +%s)
setsid bash -c "exec flock -s '$WS/tmp/gpu-test.lock' bash -c 'echo \$\$ > \"$LOCKPID\"; exec sleep infinity'" < /dev/null > /dev/null 2>&1 &
for _ in $(seq 30); do [ -s "$LOCKPID" ] && break; sleep 1; done
[ -s "$LOCKPID" ] || { rm -f $HOLD; say "could not take tmp/gpu-test.lock - hold removed, nothing run"; exit 1; }
STRATA_PORT=8080 ./run-strata.sh stop > /dev/null 2>&1 || true
printf '\n* %s 0.2.1 concurrency test GAP BEGIN (the user, 10-20): queue held after its run, test lock taken, 8080 (P021) stopped; arms on 8081.\n' "$(date '+%F %H:%M')" >> $DR/NOTES.md
say "gap open: lock held (pid $(cat $LOCKPID)), 8080 stopped; MemAvailable $(awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo) GiB"
kc open

arm base 1,2,4 0
arm b4 1,2,4 1
arm b4mtp 2,4 1

for k in chat agent; do $P work/r22/conc21.py table --arms base,b4,b4mtp --kind $k 2>&1; done | tee $O/tables.md | tee -a $S
say "arms done after $(( ($(date +%s) - T0) / 60 )) min - 8080 back on P021"

# the end: 8080 on P021 (the launchers' default), checked; the lock released; the queue's hold removed
kill "$(cat $LOCKPID)" 2> /dev/null || true; rm -f $LOCKPID
for _ in $(seq 60); do flock -n tmp/gpu-test.lock true && break; sleep 1; done
L0=$(wc -l < logs/run/strata-ensure.log)
env -u HTTP_PROXY -u HTTPS_PROXY configs/usability/bin/strata-ensure.sh "conc test end" || say "8080 did not start"
for _ in $(seq 120); do tail -n +$((L0 + 1)) logs/run/strata-ensure.log | grep -q "^8080: server" && break; sleep 1; done
tail -n +$((L0 + 1)) logs/run/strata-ensure.log | grep -E "^answered|^8080:" | tee -a $S
sha=$(tail -n +$((L0 + 1)) logs/run/strata-ensure.log | grep "^8080:" | grep -o "sha [0-9a-f]*" | tail -1 | cut -d' ' -f2)
pol=$(python3 -c "import json; print('on' if json.load(open('$DR/run/chat-cache-policy.json')).get('enabled') else 'off')")
if [ "$sha" = "$P021_SHA" ] && [ "$pol" = on ]; then
  rm -f $HOLD
  printf '* %s 0.2.1 concurrency test GAP END: 8080 back on P021 (engine sha %s), chat-cache policy still on; queue released. Results: strata-compare results/r22/conc/summary.txt.\n' "$(date '+%F %H:%M')" "$sha" >> $DR/NOTES.md
  say "8080 on P021 ($sha), policy $pol, queue hold removed"
else
  say "8080 engine sha '$sha' (want $P021_SHA) or policy '$pol': the queue stays held - look before releasing"
fi
kc end
say "conc21 done after $(( ($(date +%s) - T0) / 60 )) min"
