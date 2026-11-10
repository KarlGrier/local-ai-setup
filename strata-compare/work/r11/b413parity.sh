#!/bin/bash
# b413parity.sh — round 10 B.2: #413's own parity test (gdn_rec_parity: gdn_rec_kh_kernel against gdn_rec_cols_pipe_kernel,
# output / state / FP16 output bit for bit for T 1..4099, then --bench timings) built from the transplant branch with tests
# on, on the RTX 5080 (84 SMs: the new kernel's band), under the memory guard.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r11/env.sh
S=$WS/strata-v36b413; D=$WS/results/r11; cd $S
[ -d third_party/llama.cpp ] || cp -a $WS/strata-v0115/third_party/llama.cpp third_party/
cmake -G Ninja -S . -B build-tests -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$S/third_party/llama.cpp" > build-tests-configure.log || { tail build-tests-configure.log; exit 1; }
cmake --build build-tests --target gdn_rec_parity -j 16 > build-tests.log 2>&1 || { tail -30 build-tests.log; exit 1; }
cd $WS
CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 .venv/bin/python work/r11/guard.py b413-parity -- $S/build-tests/gdn_rec_parity > $D/b413-parity.txt 2>&1; echo "parity exit $?"; tail -5 $D/b413-parity.txt
CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 .venv/bin/python work/r11/guard.py b413-bench -- $S/build-tests/gdn_rec_parity --bench > $D/b413-bench.txt 2>&1; echo "bench exit $?"; tail -25 $D/b413-bench.txt
