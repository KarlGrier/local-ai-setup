#!/bin/bash
# builds work/r4/test_gr4 against the r4-gr tree's kernel library (strata-r4-gr/build/libstrata_kernels.a), sm_120 SASS
source /home/USER/ai-speed-testing/strata-compare/work/r4/env.sh
S=/home/USER/ai-speed-testing/strata-compare/strata-r4-gr
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o /home/USER/ai-speed-testing/strata-compare/work/r4/test_gr4 \
  /home/USER/ai-speed-testing/strata-compare/work/r4/test_gr4.cu $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda
