#!/bin/bash
# builds work/r3/test_ple_batch against the r3 tree's kernel library (strata-r3/build/libstrata_kernels.a)
S=/home/USER/ai-speed-testing/strata-compare/strata-r3
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o /home/USER/ai-speed-testing/strata-compare/work/r3/test_ple_batch \
  /home/USER/ai-speed-testing/strata-compare/work/r3/test_ple_batch.cu $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda
