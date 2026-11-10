#!/bin/bash
# pr_build.sh TREE... - round 18 part 2: Release CUDA build (sm_89 + sm_120, the setup.py-pinned ggml) of each tree with
# upstream's tests (STRATA_BUILD_TESTS=ON): the engine and every test target, at low CPU priority.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
for T in "$@"; do
  cd $WS/$T || continue
  [ -e third_party/llama.cpp ] || ln -sfn $(readlink -f $WS/strata-v0115/third_party/llama.cpp) third_party/llama.cpp
  t0=$(date +%s)
  nice -n 10 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
    "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build-configure.log 2>&1 \
    && nice -n 10 cmake --build build -j 16 > build.log 2>&1
  rc=$?   # (the report's $(date) used to reset $? before it was read: a failed build printed rc 0)
  echo "$(date -Is) $T rc $rc in $(( $(date +%s) - t0 )) s; $(git log --oneline -1 | cut -c1-60)"
done
