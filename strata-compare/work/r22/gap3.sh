#!/bin/bash
# gap3.sh - round 22, the 0.2.1 port's gap (10-20 night: v0.2.1 tagged 03:04, the queue paused itself for the port after
# h08 xhigh). Same checks as gaps 1-2 on branch r22-port021 (v0.2.1 + our 26 commits):
#   1 build          work/r22/build-port021.sh -> engine-r22p021 (a failed build ends the gap)
#   2 quality        exact7 vs the 0.2.0 port's hashes (REF=r22p-e7, information) and again vs itself (must be 7/7),
#                    needles 12 x 6, Stop at 120K, #652 follow-ups / stop strings / tool tags / #931 probe, repeat3
#   3 chat cache     work/r22/chatcache_checks.py on configs/r22p021RT.json
#   4 speed          decode screen A B B A and full screen A B B A, A = C*18t, B = the 0.2.1 port
#   5 pictures       the reader built from 0.2.1's tools/vision; identity reader off vs on with the expert cache pinned
#                    to 3500 in both (is the 8/11 of gap 2 the slot count?); the elastic reader (starts with a picture,
#                    stops after 30 s idle: RAM back?)
#   6 unit tests     serve/ unittest, C++ ctest
# Then port_gap.sh end (C*18t back on 8080, SHA checked, policy off, NOTES.md). The queue service stopped itself on the
# new tag; it is restarted by hand after this. A kernel error stops everything with the gap left open.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=results/r22/gap3; S=$O/summary.txt; mkdir -p $O $O/pictures logs/r22 tmp/r22
A=$WS/configs/Cstar18t.json B=$WS/configs/r22p021.json RT=$WS/configs/r22p021RT.json
RP=$WS/configs/r22p021RTpin.json RPV=$WS/configs/r22p021RTpin-vision.json BE=$WS/configs/r22p021-vision-elastic.json
IMG=$WS/strata-r22p021/docs/terminal-previews/serving-110-stages.png
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g3-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (queue held, 8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap.sh end 2>&1 | tee -a $S; }

work/r22/port_gap.sh begin "gap 3: the 0.2.1 port - build, quality, chat cache, speed, pictures, unit tests" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open"; exit 1; }
kc open

say "1 build"
if ! work/r22/build-port021.sh 2>&1 | tee -a $S; then
  tail -30 strata-r22p021/build.log > $O/build-fail.txt 2> /dev/null; say "BUILD FAILED ($O/build-fail.txt) - ending the gap"; end_gap; exit 1
fi

say "2 quality"
REF=r22p-e7 bringup/lib/exact7.sh r21p-e7 $B 2>&1 | tail -9 | tee -a $S
kc exact7
REF=r21p-e7 bringup/lib/exact7.sh r21p2-e7 $B 2>&1 | tail -9 | tee -a $S
kc exact7-repeat
for l in c18-e7 r22p-e7 r21p-e7; do echo "$l: $(grep -h 'expert cache [0-9]* slots' bringup/out/logs/prof/$l-x-math.err 2> /dev/null | head -1 | cut -c17-70)"; done | tee -a $S
bringup/lib/with_server.sh N-r21p $B -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r21p --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee -a $S
kc needles
bringup/lib/with_server.sh FAIL-r21p $B -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
  | grep -E "PASS|FAIL" | tail -10 | tee -a $S
kc stop120k
bringup/lib/with_server.sh T-r21p $B -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 r21p plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 r21p; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 r21p 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 r21p" 2>&1 \
  | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee -a $S
kc probes
bringup/lib/repeat3.sh rep-r21p $B 2>&1 | tail -1 | tee -a $S
kc repeat3

say "3 chat cache"
bringup/lib/with_server.sh CC-r21p $RT -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
  | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcache.txt | tee -a $S
grep -q "ALL PASS" $O/chatcache.txt || say "CHAT CACHE CHECKS NOT ALL PASS - the parking policy stays off; tell the user (replays)"
kc chatcache

say "4 speed: decode screen and full screen A B B A (A = C*18t, B = 0.2.1 port)"
SS=$(date -Iseconds | cut -c1-19)
for arm in "c18t-a $A" "r21p-a $B" "r21p-b $B" "c18t-b $A"; do
  set -- $arm
  bringup/lib/decscreen.sh r22-g3-D-$1 $2 > logs/r22/g3-D-$1.log 2>&1
  echo "dec arm $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc dec-$1
done
SINCE=$SS $P bringup/lib/ab_table.py C18T=r22-g3-D-c18t-a,r22-g3-D-c18t-b P021=r22-g3-D-r21p-a,r22-g3-D-r21p-b > $O/dec.md 2>&1
grep -iE '^\| *(decode|ms per|tokens per|long|ttft)' $O/dec.md | head -7 | tee -a $S
SS=$(date -Iseconds | cut -c1-19)
for arm in "c18t-a $A" "r21p-a $B" "r21p-b $B" "c18t-b $A"; do
  set -- $arm
  bringup/lib/fullscreen.sh r22-g3-F-$1 $2 > logs/r22/g3-F-$1.log 2>&1
  echo "full arm $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc full-$1
done
SINCE=$SS $P bringup/lib/ab_table.py C18T=r22-g3-F-c18t-a,r22-g3-F-c18t-b P021=r22-g3-F-r21p-a,r22-g3-F-r21p-b > $O/full.md 2>&1
grep -iE '^\| *(decode|ms per|tokens per|ttft|total|long)' $O/full.md | head -10 | tee -a $S
grep -ahE "file tier|io prefetch" $(ls -t bringup/out/logs/server_r22-g3-F-r21p-b_*.log | head -1) | head -3 | cut -c1-200 | tee -a $S

say "5 pictures"
LL=$(readlink -f strata/third_party/llama.cpp)
rm -rf strata-r22p021/build-vision
if (cd strata-r22p021 && nice -n 5 cmake -G Ninja -S tools/vision -B build-vision -DCMAKE_BUILD_TYPE=Release -DLLAMA_DIR="$LL" \
      -DSTRATA_VISION_CUDA=OFF -DSTRATA_PORTABLE=OFF > build-vision-configure.log 2>&1 \
    && nice -n 5 cmake --build build-vision --target strata-vision -j 16 > build-vision.log 2>&1); then
  cp strata-r22p021/build-vision/bin/strata-vision engine-r22p021/strata-vision
  sha256sum engine-r22p021/strata-vision | tee engine-r22p021/strata-vision.SHA256 | tee -a $S
  bringup/lib/with_server.sh VIP-off $RP -- "$P work/r22/vision_identity.py run http://127.0.0.1:8081 $O/pictures/identity-pin-off.json" 2>&1 | grep -E "replies|exited" | tee -a $S
  kc pic-off
  bringup/lib/with_server.sh VIP-on $RPV -- "$P work/r22/vision_identity.py run http://127.0.0.1:8081 $O/pictures/identity-pin-on.json" 2>&1 | grep -E "replies|exited" | tee -a $S
  kc pic-on
  for l in logs/engine-r22p021RTpin.log logs/engine-r22p021RTpin-vision.log; do echo "$l: $(grep -a 'expert cache [0-9]* slots' $l | tail -1 | cut -c17-70)"; done | tee -a $S
  $P work/r22/vision_identity.py compare $O/pictures/identity-pin-off.json $O/pictures/identity-pin-on.json | tee $O/pictures/identity-pin.txt | tail -12 | tee -a $S
  bringup/lib/with_server.sh VE $BE -- "$P work/r22/vision_elastic_check.py http://127.0.0.1:8081 $IMG $WS/$O/pictures/elastic-answer" 2>&1 \
    | grep -E "^[1-4] " | tee $O/pictures/elastic.txt | tee -a $S
  kc pic-elastic
else
  tail -20 strata-r22p021/build-vision.log > $O/pictures/build-fail.txt 2> /dev/null; say "READER BUILD FAILED - pictures skipped"
fi

say "6 unit tests"
(cd strata-r22p021 && timeout 1800 $WS/$P -m unittest discover -s serve -p 'test_*.py' -t . > $WS/$O/unittest-serve-all.txt 2>&1); echo "serve/test_*.py rc $?: $(tail -3 $O/unittest-serve-all.txt | tr '\n' ' ')" | tee -a $S
if work/r22/build-port021.sh tests 2>&1 | tee -a $S; then
  (cd strata-r22p021/build-tests && timeout 3600 ctest --output-on-failure --timeout 600 > $WS/$O/ctest.txt 2>&1); echo "ctest rc $?: $(grep -E 'tests passed|tests failed' $O/ctest.txt | tail -1)" | tee -a $S
  grep -E "\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run" $O/ctest.txt | sed 's/^ *[0-9]* - //' | sort | tr '\n' ';' | tee -a $S; echo | tee -a $S
fi
kc tests

say "gap 3 done - switching back"
end_gap
say "end"
