#!/bin/bash
# nsys_gr.sh LABEL — per-kernel GPU times of work/r4/test_gr4 (old vs new GR kernels, cold-L2 timing loop) under nsys;
# temp files and caches stay in the workspace (env.sh: TMPDIR, XDG_*, CUDA_CACHE_PATH).
WS=/home/USER/ai-speed-testing/strata-compare; L=$1
source $WS/work/r4/env.sh
/usr/local/cuda-13.3/bin/nsys profile -o $WS/logs/r4/nsys/$L --force-overwrite=true --trace=cuda --sample=none \
  --cpuctxsw=none --export=sqlite $WS/work/r4/test_gr4 > $WS/logs/r4/nsys/$L.out 2> $WS/logs/r4/nsys/$L.err
/usr/local/cuda-13.3/bin/nsys stats --report cuda_gpu_kern_sum --format csv $WS/logs/r4/nsys/$L.sqlite 2>/dev/null |
  grep -E 'gr_|memset|Name' | cut -d, -f1-9 | sed 's/_ZN6strata7kernels[^,]*\(gr_[a-z0-9_]*kernel\)[^,]*/\1/' | head -12
