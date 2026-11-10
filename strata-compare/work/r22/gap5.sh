#!/bin/bash
# gap5.sh - round 22, 10-21: the phase 4 gap after the last baseline (h08), before stage 1. Opened by gap5-wait.sh
# (port_gap4.sh begin: queue and stage 1 held, test lock, P021 on 8080 stopped). CPU builds first, then the 0.2.2 port's
# checks (the user, 10-21: write the port now, build and check it in gaps, do NOT switch 8080 to it in phase 4):
#   1 builds        a 0.2.2 port engine (build-port022.sh -> engine-r22p022)
#                   b Basalt (basalt-ab/scripts/build.sh; no network, own folder) and its debug copy (build.sh headcheck)
#                   c the picture reader with CUDA for the 4060 Ti (sm_89) from P021's tools/vision -> engine-r22p021/
#                     strata-vision-cuda (beside the CPU one, which P021 keeps); for the Basalt A/B's picture item
#   2 quality       exact7 vs the 0.2.1 port's hashes (REF=r21p-e7) and again vs itself (must be 7/7), needles 12 x 6,
#                   Stop at 120K, #652 follow-ups / stop strings / tool tags / #931 probe, repeat3
#   3 chat cache    work/r22/chatcache_checks.py on configs/r22p022RT.json
#   4 speed         decode screen and full screen A B B A, A = the 0.2.1 port (r22p021.json = P021 without the reader),
#                   B = the 0.2.2 port (r22p022.json)
#   5 unit tests    serve/ unittest, C++ ctest
#   6 Basalt A/B    work/r22/gap5b.sh (the user, 10-21: the Basalt GPU tests at the end of gap 5; ~2 h)
# Then port_gap4.sh end (P021 back on 8080, SHA checked, policy on, NOTES.md; the queue logs "queue finished" and stage 1
# starts). A kernel error stops everything with the gap left open. Pictures on 0.2.2 are not checked (not switched).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=results/r22/gap5; S=$O/summary.txt; mkdir -p $O logs/r22 tmp/r22
A=$WS/configs/r22p021.json B=$WS/configs/r22p022.json RT=$WS/configs/r22p022RT.json
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g5-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (queue held, 8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }

[ -s tmp/port-gap.lockpid ] && [ -e /home/USER/ai/deep-research/tmp/bench2.hold ] || { say "the gap is not open (port_gap4.sh begin first)"; exit 1; }
kc open

say "1a build: the 0.2.2 port"
B22OK=1
if ! work/r22/build-port022.sh 2>&1 | tee -a $S; then
  tail -30 strata-r22p022/build.log > $O/build-fail.txt 2> /dev/null; say "PORT BUILD FAILED ($O/build-fail.txt) - its checks are skipped"; B22OK=0
fi
say "1b build: Basalt"
/home/USER/ai-speed-testing/basalt-ab/scripts/build.sh 2>&1 | tee -a $S || { tail -30 /home/USER/ai-speed-testing/basalt-ab/logs/build.log > $O/basalt-build-fail.txt 2> /dev/null; say "BASALT BUILD FAILED ($O/basalt-build-fail.txt)"; }
say "1b' build: Basalt's debug copy (HEADCHECK / exact_head / ppl_top)"
/home/USER/ai-speed-testing/basalt-ab/scripts/build.sh headcheck 2>&1 | tee -a $S || { tail -30 /home/USER/ai-speed-testing/basalt-ab/logs/build-headcheck.log > $O/basalt-headcheck-build-fail.txt 2> /dev/null; say "BASALT DEBUG BUILD FAILED ($O/basalt-headcheck-build-fail.txt)"; }
say "1c build: the picture reader with CUDA (sm_89)"
LL=$(readlink -f strata/third_party/llama.cpp)
rm -rf strata-r22p021/build-vision-cuda
if (cd strata-r22p021 && nice -n 5 cmake -G Ninja -S tools/vision -B build-vision-cuda -DCMAKE_BUILD_TYPE=Release -DLLAMA_DIR="$LL" \
      -DSTRATA_VISION_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89 -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_PORTABLE=OFF \
      > build-vision-cuda-configure.log 2>&1 \
    && nice -n 5 cmake --build build-vision-cuda --target strata-vision -j 16 > build-vision-cuda.log 2>&1); then
  cp strata-r22p021/build-vision-cuda/bin/strata-vision engine-r22p021/strata-vision-cuda
  sha256sum engine-r22p021/strata-vision-cuda | tee engine-r22p021/strata-vision-cuda.SHA256 | tee -a $S
else
  tail -20 strata-r22p021/build-vision-cuda.log > $O/vision-cuda-build-fail.txt 2> /dev/null; say "CUDA READER BUILD FAILED ($O/vision-cuda-build-fail.txt)"
fi
kc builds
[ $B22OK = 1 ] || { say "gap 5 done (port build failed) - switching back"; end_gap; exit 1; }

say "2 quality"
REF=r21p-e7 bringup/lib/exact7.sh r222p-e7 $B 2>&1 | tail -9 | tee -a $S
kc exact7
REF=r222p-e7 bringup/lib/exact7.sh r222p2-e7 $B 2>&1 | tail -9 | tee -a $S
kc exact7-repeat
for l in r21p-e7 r222p-e7; do echo "$l: $(grep -h 'expert cache [0-9]* slots' bringup/out/logs/prof/$l-x-math.err 2> /dev/null | head -1 | cut -c17-70)"; done | tee -a $S
bringup/lib/with_server.sh N-r222p $B -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r222p --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee -a $S
kc needles
bringup/lib/with_server.sh FAIL-r222p $B -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
  | grep -E "PASS|FAIL" | tail -10 | tee -a $S
kc stop120k
bringup/lib/with_server.sh T-r222p $B -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 r222p plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 r222p; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 r222p 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 r222p" 2>&1 \
  | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee -a $S
kc probes
bringup/lib/repeat3.sh rep-r222p $B 2>&1 | tail -1 | tee -a $S
kc repeat3

say "3 chat cache"
bringup/lib/with_server.sh CC-r222p $RT -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
  | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcache.txt | tee -a $S
grep -q "ALL PASS" $O/chatcache.txt || say "CHAT CACHE CHECKS NOT ALL PASS on the 0.2.2 port - tell the user"
kc chatcache

say "4 speed: decode screen and full screen A B B A (A = the 0.2.1 port, B = the 0.2.2 port)"
SS=$(date -Iseconds | cut -c1-19)
for arm in "p021-a $A" "p022-a $B" "p022-b $B" "p021-b $A"; do
  set -- $arm
  bringup/lib/decscreen.sh r22-g5-D-$1 $2 > logs/r22/g5-D-$1.log 2>&1
  echo "dec arm $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc dec-$1
done
SINCE=$SS $P bringup/lib/ab_table.py P021=r22-g5-D-p021-a,r22-g5-D-p021-b P022=r22-g5-D-p022-a,r22-g5-D-p022-b > $O/dec.md 2>&1
grep -iE '^\| *(decode|ms per|tokens per|long|ttft)' $O/dec.md | head -7 | tee -a $S
SS=$(date -Iseconds | cut -c1-19)
for arm in "p021-a $A" "p022-a $B" "p022-b $B" "p021-b $A"; do
  set -- $arm
  bringup/lib/fullscreen.sh r22-g5-F-$1 $2 > logs/r22/g5-F-$1.log 2>&1
  echo "full arm $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc full-$1
done
SINCE=$SS $P bringup/lib/ab_table.py P021=r22-g5-F-p021-a,r22-g5-F-p021-b P022=r22-g5-F-p022-a,r22-g5-F-p022-b > $O/full.md 2>&1
grep -iE '^\| *(decode|ms per|tokens per|ttft|total|long)' $O/full.md | head -10 | tee -a $S

say "5 unit tests"
(cd strata-r22p022 && timeout 1800 $WS/$P -m unittest discover -s serve -p 'test_*.py' -t . > $WS/$O/unittest-serve-all.txt 2>&1); echo "serve/test_*.py rc $?: $(tail -3 $O/unittest-serve-all.txt | tr '\n' ' ')" | tee -a $S
if work/r22/build-port022.sh tests 2>&1 | tee -a $S; then
  (cd strata-r22p022/build-tests && timeout 3600 ctest --output-on-failure --timeout 600 > $WS/$O/ctest.txt 2>&1); echo "ctest rc $?: $(grep -E 'tests passed|tests failed' $O/ctest.txt | tail -1)" | tee -a $S
  grep -E "\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run" $O/ctest.txt | sed 's/^ *[0-9]* - //' | sort | tr '\n' ';' | tee -a $S; echo | tee -a $S
fi
kc tests

say "6 the Basalt A/B GPU block (the user, 10-21: at the end of gap 5, before P021 goes back)"
work/r22/gap5b.sh 2>&1 | tail -80 | tee -a $S
[ ${PIPESTATUS[0]} = 3 ] && { say "kernel check failed in the Basalt block - the gap stays open"; exit 3; }

say "gap 5 done - switching back"
end_gap
say "end"
