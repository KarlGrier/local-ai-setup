#!/bin/bash
# d5_side43.sh - round 19 Part D 5: the #1889 rebase (branch pr18-v043/side = 38b03280 on v0.1.43): build (tests on,
# configured twice), exact7 with STRATA_SIDE_MIXER off vs stock v0.1.43 (runbook r19e's engine-stock, the same flags) and
# with it on (=2) vs off (the PR's claim: bitwise the same), then ctest. Round 18's PR flags (this PC's minus the local
# ones). Kernel check after each. Ends with the promoted build (C*17) on 8080. Nothing pushed.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
P=.venv/bin/python; R=results/r19; T=$WS/tmp/r19/side43; NVCC=/usr/local/cuda-13.3/bin/nvcc
export RB_CACHE=$WS/tmp/r19 PROMPT_DIR=$WS/bringup/out/r19e/prompts
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc d5-start
[ -e $T/third_party/llama.cpp ] || ln -sfn $(readlink -f strata-v0115/third_party/llama.cpp) $T/third_party/llama.cpp
echo "=== $(date -Is) build (tests on, configure x2)"
for n in 1 2; do (cd $T && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
    "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$T/third_party/llama.cpp" > build-configure$n.log 2>&1); done
nice -n 5 cmake --build $T/build -j 24 > $T/build.log 2>&1 || { echo "BUILD FAILED"; tail -5 $T/build.log; exit 1; }
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
echo "=== $(date -Is) exact7: stock v0.1.43, the PR switch off, switch on"
REF=c121 bringup/lib/exact7.sh r19d5-e7-main configs/r19-v43-prc-main.json 2>&1 | tail -1 | tee $R/d5-side43-e7.txt; kc d5-main
REF=r19d5-e7-main bringup/lib/exact7.sh r19d5-e7-off configs/r19-v43-prc-side-off.json 2>&1 | tail -8 | tee -a $R/d5-side43-e7.txt; kc d5-off
REF=r19d5-e7-off bringup/lib/exact7.sh r19d5-e7-on configs/r19-v43-prc-side-on.json 2>&1 | tail -8 | tee -a $R/d5-side43-e7.txt; kc d5-on
grep -h -E 'SIDE_MIXER|side mixer' bringup/out/logs/prof/r19d5-e7-on-x-math.err | head -2 | cut -c1-160
echo "=== $(date -Is) ctest"
(cd $T/build && timeout 3600 ctest --output-on-failure -j 1 > $WS/$R/d5-side43-ctest.txt 2>&1)
echo "ctest: $(grep -E 'tests passed|tests failed' $R/d5-side43-ctest.txt | tail -1)"; grep -E '\*\*\*Failed|Not Run|Timeout' $R/d5-side43-ctest.txt | head -6
kc d5-ctest
bringup/lib/phase_end.sh r19-d5 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d5 done"
