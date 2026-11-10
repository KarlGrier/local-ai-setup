#!/bin/bash
# nsys-engine.sh ARGS... — round 9 Phase 0.5 (copy of round 8 A.1): a config "exe" that runs the TRACE engine (engine-r9t) under nsys, so the
# server's own requests are traced at your settings. Capture = cudaProfilerApi range (STRATA_PROFILE_FROM/ROUNDS over
# served windows); output logs/r9/prof/$NSYS_LABEL.{nsys-rep,sqlite}. Measurement only (traces explain, never decide).
WS=/home/USER/ai-speed-testing/strata-compare
exec /usr/local/cuda-13.3/bin/nsys profile -o $WS/logs/r9/prof/${NSYS_LABEL:-srv} --force-overwrite=true \
  --trace=cuda,nvtx --cuda-graph-trace=node --sample=none --cpuctxsw=none \
  --capture-range=cudaProfilerApi --capture-range-end=stop --export=sqlite \
  $WS/engine-r9t/strata "$@"
