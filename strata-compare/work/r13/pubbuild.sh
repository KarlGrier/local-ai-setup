#!/bin/bash
# pubbuild.sh — round 13 Part 6 (c): every local pub/* branch compiles (sm_120 + sm_89), one worktree, incremental.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS/strata-pub; source $WS/work/r13/env.sh
[ -d third_party/llama.cpp ] || cp -a $WS/strata-v0115/third_party/llama.cpp third_party/
for b in $(git -C $WS/strata branch --list "pub/*" --format="%(refname:short)"); do
  git checkout -q $b
  cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
    "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
    -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build-configure.log 2>&1
  if cmake --build build --target strata -j 16 > build-$(basename $b).log 2>&1; then echo "$b: builds"; else echo "$b: BUILD FAILED $(grep -m1 'error' build-$(basename $b).log | cut -c1-160)"; fi
done
git checkout -q --detach v0.1.39
