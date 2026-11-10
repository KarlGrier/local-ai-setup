#!/bin/bash
# build_trial.sh - 2026-10-14: compile check of the trial port (branch r20-trial-v04441) at low priority: C*17.1's
# build options (Release, CUDA sm_89 + sm_120, tests off) on v0.1.44.1's CMake (the K-quant library builds by default).
set -u
T=/home/USER/ai-speed-testing/strata-compare/tmp/r20/port-trial; cd $T
t0=$(date +%s)
nice -n 10 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR="$T/third_party/llama.cpp" > build-configure.log 2>&1 \
  && nice -n 10 cmake --build build --target strata -j 16 > build.log 2>&1
rc=$?
echo "$(date -Is) rc $rc in $(( $(date +%s) - t0 )) s"
grep -E "error|Error" build.log | head -20
