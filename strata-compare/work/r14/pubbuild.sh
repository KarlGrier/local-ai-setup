#!/bin/bash
# pubbuild.sh — round 14 step 9: every local pub14/* branch compiles (sm_120 + sm_89), one worktree (strata-pub), incremental.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS/strata-pub; export RB_CACHE=$WS/tmp/r14; source $WS/bringup/lib/env.sh
[ -e third_party/llama.cpp/ggml ] || ln -sfn $(readlink -f $WS/strata-v0115/third_party/llama.cpp) third_party/llama.cpp
for b in $(git -C $WS/strata branch --list "pub14/*" --format="%(refname:short)"); do
  git checkout -q $b
  cmake -G Ninja -S . -B build14 -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
    "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
    -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build14-configure.log 2>&1
  if cmake --build build14 --target strata -j 16 > build14-$(basename $b).log 2>&1; then echo "$b: builds"; else echo "$b: BUILD FAILED $(grep -m1 'error' build14-$(basename $b).log | cut -c1-160)"; fi
done | tee $WS/results/r14/s9-pubbuild.txt
git checkout -q --detach v0.1.40.1
