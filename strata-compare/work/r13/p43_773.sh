#!/bin/bash
# p43_773.sh — round 13 Part 4.3: #773 (Linux unbuffered file tier) alone, where it can act. The planner said the Q4
# experts (71.7 GiB) do not fit in RAM beside the floor. #773 acts only with a RAM budget (its 2nd commit: even
# STRATA_UNBUFFERED_LOAD=1 is not honoured without one), and v0.1.39 refuses a RAM budget next to a helper-GPU cache, so
# the test runs on Rehearsal B's tuned candidate (the planner's first choice since 04:00: one GPU +
# --resident-budget-gib 48). Decode screens A B B A: A = that config on the r13-fix engine (buffered: the experts outside
# the RAM copy are page faults of the mapped GGUF), B = the same + #773 (its own decision, read from the engine log).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r13/env.sh
R=$WS/bringup/out/rehB; T=$WS/strata-r13-773
[ -f $R/configs/cand.json ] || { echo "no Rehearsal B candidate config"; exit 1; }
[ -d $T/third_party/llama.cpp ] || ln -s $(readlink -f $WS/strata-v0115/third_party/llama.cpp) $T/third_party/llama.cpp
(cd $T && cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_MMQ_KQUANTS=ON \
  -DSTRATA_GGML_DIR="$T/third_party/llama.cpp" > build-configure.log && cmake --build build --target strata -j 8 > build.log 2>&1) || { tail -5 $T/build.log; exit 1; }
mkdir -p $WS/engine-r13-773 && cp $T/build/strata $WS/engine-r13-773/strata
.venv/bin/python - <<'PY'
import json
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/rehB")
c = json.loads((R / "configs/cand.json").read_text())
assert "--resident-budget-gib" in c["args"] and "--expert-cache-device1" not in c["args"], "cand is not the one-GPU budget config"
d = dict(c); d["exe"] = "/home/USER/ai-speed-testing/strata-compare/engine-r13-773/strata"; d["log"] = str(R / "engine-one773.log")
(R / "configs/one773.json").write_text(json.dumps(d, indent=1) + "\n")
sh = R / "configs/cand.shared-settings.json"
if sh.exists():
    (R / "configs/one773.shared-settings.json").write_text(sh.read_text())
PY
SS=$(date -Iseconds | cut -c1-19)
EVICT_GLOB="$(dirname $(.venv/bin/python -c "import json; a=json.load(open('$R/configs/cand.json'))['args']; print(a[a.index('--native')+1])"))/*.gguf"; export EVICT_GLOB
bringup/lib/decscreen.sh r13-773-A1 $R/configs/cand.json > /dev/null 2>&1
bringup/lib/decscreen.sh r13-773-B1 $R/configs/one773.json > /dev/null 2>&1
bringup/lib/decscreen.sh r13-773-B2 $R/configs/one773.json > /dev/null 2>&1
bringup/lib/decscreen.sh r13-773-A2 $R/configs/cand.json > /dev/null 2>&1
SINCE=$SS .venv/bin/python bringup/lib/ab_table.py one_gpu_budget=r13-773-A1,r13-773-A2 plus_773=r13-773-B1,r13-773-B2 | tee results/r13/p43-773.md
echo "#773's decision: $(grep -iE 'unbuffered|O_DIRECT|direct|file cache' $R/engine-one773.log | tail -3 | tr '\n' ' ' | cut -c1-400)"
echo "without #773: $(grep -iE 'unbuffered|file cache|budget' $R/engine-cand.log | tail -2 | tr '\n' ' ' | cut -c1-300)"
grep -E "r13-773-(A|B)" bringup/out/logs/guard/summary.txt | tail -8 | cut -c1-200
