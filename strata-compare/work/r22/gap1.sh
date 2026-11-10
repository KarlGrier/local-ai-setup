#!/bin/bash
# gap1.sh - round 22, the 0.2.0 port's gap 1 (after o08 deep medium; results/r22/port-020-beta.md "Gap plan").
# Opens the gap itself (port_gap.sh begin: the queue holds after its running run, test lock, 8080 down), then:
#   1 build          work/r22/build-port.sh -> engine-r22port (a failed build ends the gap)
#   2 quality        exact7 vs C*18t's hashes (REF=c18-e7: 0.2.0's split attention sums in another order, so differences
#                    are expected - reported, not a gate), exact7 again vs itself (must be 7/7: deterministic), needles
#                    12 x 6, Stop at 120K, #652 follow-ups / stop strings / tool tags / #931 probe, repeat3
#   3 chat cache     work/r22/chatcache_checks.py on configs/r22portRT.json (resumed = fresh, ckpt=0 = plain, the
#                    research drop)
#   4 speed          decode screen (long reasoning math + code, correctness x5, 32K prompt + 768) A B B A,
#                    A = C*18t (configs/Cstar18t.json), B = the port (configs/r22port.json); fresh guarded server each
#   5 unit tests     serve/ unittest (test_server + the rest), then the C++ tests (build-tests/, ctest)
# Then port_gap.sh end: C*18t back on 8080 (SHA checked), the parking policy forced off, NOTES.md, queue resumes.
# A kernel error stops everything and leaves the gap open (queue held, 8080 down): the user's rule.
# Memory floor: the guard's default 16 GiB. Output: results/r22/gap1/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=.venv/bin/python; O=results/r22/gap1; S=$O/summary.txt; mkdir -p $O logs/r22 tmp/r22
A=$WS/configs/Cstar18t.json B=$WS/configs/r22port.json RT=$WS/configs/r22portRT.json
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g1-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (queue held, 8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap.sh end 2>&1 | tee -a $S; }   # any test server left on 8081 first

work/r22/port_gap.sh begin "gap 1: build, quality checks, chat-cache checks, A B B A, unit tests" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed, queue resumes)"; exit 1; }
kc open

say "1 build"
if ! work/r22/build-port.sh 2>&1 | tee -a $S; then
  tail -30 strata-r22port/build.log > $O/build-fail.txt 2>/dev/null
  say "BUILD FAILED (results/r22/gap1/build-fail.txt) - ending the gap"; end_gap; exit 1
fi

say "2 quality"
REF=c18-e7 bringup/lib/exact7.sh r22p-e7 $B 2>&1 | tail -9 | tee -a $S
kc exact7
REF=r22p-e7 bringup/lib/exact7.sh r22p2-e7 $B 2>&1 | tail -9 | tee -a $S
kc exact7-repeat
for l in c18-e7 r22p-e7 r22p2-e7; do echo "$l: $(grep -h 'expert cache [0-9]* slots' bringup/out/logs/prof/$l-x-math.err 2>/dev/null | head -1 | cut -c17-70)"; done | tee -a $S
bringup/lib/with_server.sh N-r22p $B -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r22p --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee -a $S
kc needles
bringup/lib/with_server.sh FAIL-r22p $B -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
  | grep -E "PASS|FAIL" | tail -10 | tee -a $S
kc stop120k
bringup/lib/with_server.sh T-r22p $B -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 r22p plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 r22p; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 r22p 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 r22p" 2>&1 \
  | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee -a $S
kc probes
bringup/lib/repeat3.sh rep-r22p $B 2>&1 | tail -1 | tee -a $S
kc repeat3

say "3 chat cache (resumed = fresh, ckpt=0, research drop) on the fixed-computation twin"
bringup/lib/with_server.sh CC-r22p $RT -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
  | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcache.txt | tee -a $S
grep -q "ALL PASS" $O/chatcache.txt || say "CHAT CACHE CHECKS NOT ALL PASS - the parking policy stays off; tell the user (replays)"
kc chatcache

say "4 speed A B B A (A = C*18t, B = port)"
SS=$(date -Iseconds | cut -c1-19)
for arm in "c18t-a $A" "r22p-a $B" "r22p-b $B" "c18t-b $A"; do
  set -- $arm
  bringup/lib/decscreen.sh r22-g1-D-$1 $2 > logs/r22/g1-D-$1.log 2>&1
  echo "arm $1 done: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc speed-$1
done
SINCE=$SS $P bringup/lib/ab_table.py C18T=r22-g1-D-c18t-a,r22-g1-D-c18t-b PORT=r22-g1-D-r22p-a,r22-g1-D-r22p-b > $O/dec.md 2>&1
grep -iE '^\| *(decode|ms per|ttft|total|hit)' $O/dec.md | head -8 | tee -a $S

say "5 unit tests"
(cd strata-r22port && timeout 1800 $WS/$P -m unittest serve.test_server > $WS/$O/unittest-server.txt 2>&1); echo "serve.test_server rc $?: $(tail -3 $O/unittest-server.txt | tr '\n' ' ')" | tee -a $S
(cd strata-r22port && timeout 1800 $WS/$P -m unittest discover -s serve -p 'test_*.py' -t . > $WS/$O/unittest-serve-all.txt 2>&1); echo "serve/test_*.py rc $?: $(tail -3 $O/unittest-serve-all.txt | tr '\n' ' ')" | tee -a $S
if work/r22/build-port.sh tests 2>&1 | tee -a $S; then
  (cd strata-r22port/build-tests && timeout 3600 ctest --output-on-failure --timeout 600 > $WS/$O/ctest.txt 2>&1); echo "ctest rc $?: $(grep -E 'tests passed|tests failed' $O/ctest.txt | tail -1)" | tee -a $S
  grep -E "\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run" $O/ctest.txt | head -20 | tee -a $S
else
  tail -30 strata-r22port/build-tests.log > $O/build-tests-fail.txt 2>/dev/null; say "TEST BUILD FAILED (results/r22/gap1/build-tests-fail.txt)"
fi
kc tests

say "gap 1 done - switching back"
end_gap
say "end"
