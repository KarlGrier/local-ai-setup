#!/bin/bash
# build-cstar161.sh - round 18: C*16.1's serving assets. engine-cstar161 = strata-r18's build of branch r18-p1 (C*16's 27
# commits + the side-mixer fix [+ the #567 revert, if part 1 dropped it]); strata-cstar161 = a worktree of the same commit
# (serve/, tools/); engine-twin161 = the same + Round 16's 4 MEASUREMENT commits (branch r18-meas, re-authored); configs:
# Cstar161.json (C*16's flags + STRATA_MMVQ_IL_ROWS = the table measured on this RTX 5080), Cstar161-single.json (one GPU,
# the launcher's fallback), R161RT.json (the twin, --adapt-swaps 0: round trips), twin161.json (the acceptance suite's
# twin), BR161.json (browser-test copy), and the launchers' C*16.1 copies (work/r18/*.c161; promote-c161.sh installs them).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
B=$(git -C strata-r18 rev-parse HEAD); T=$(git -C strata-r18 rev-parse HEAD^{tree})
[ -z "$(git -C strata-r18 status --porcelain --untracked-files=no)" ] || { echo "strata-r18 has uncommitted changes"; exit 1; }
cmake --build strata-r18/build --target strata -j 16 > strata-r18/build.log 2>&1
mkdir -p engine-cstar161 && cp strata-r18/build/strata engine-cstar161/strata
echo "v0.1.41 + $(git -C strata-r18 rev-list --count v0.1.41..HEAD) commits (branch r18-p1 $B), tree $T" > engine-cstar161/SOURCE
sha256sum engine-cstar161/strata > engine-cstar161/SHA256; cat engine-cstar161/SOURCE engine-cstar161/SHA256
[ -d strata-cstar161 ] || git -C strata worktree add -q --detach $WS/strata-cstar161 $B
git -C strata-cstar161 checkout -q --detach $B
[ -e strata-cstar161/third_party/llama.cpp ] || ln -sfn $(readlink -f strata-v0115/third_party/llama.cpp) strata-cstar161/third_party/llama.cpp
W=tmp/r18/wt-meas
[ "$(git -C $W rev-list --count $B..HEAD)" = 4 ] && git -C $W merge-base --is-ancestor $B HEAD || { echo "the twin branch is not C*16.1 + 4"; exit 1; }
[ -e $W/third_party/llama.cpp ] || ln -sfn $(readlink -f strata-v0115/third_party/llama.cpp) $W/third_party/llama.cpp
[ -f $W/build/build.ninja ] || (cd $W && cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build-configure.log)
cmake --build $W/build --target strata -j 16 > $W/build.log 2>&1
mkdir -p engine-twin161 && cp $W/build/strata engine-twin161/strata && sha256sum engine-twin161/strata > engine-twin161/SHA256
echo "C*16.1 + 4 MEASUREMENT commits (branch r18-meas $(git -C $W rev-parse HEAD))" > engine-twin161/SOURCE
.venv/bin/python - <<'PY'
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"
rows = (WS / "work/r18/t5080-table.env").read_text().strip()
base = json.loads((C / "Cstar16.json").read_text())
c = json.loads(json.dumps(base))
c.update(exe=str(WS / "engine-cstar161/strata"), server=str(WS / "strata-cstar161/serve/server.py"),
         log=str(WS / "logs/engine-Cstar161.log"), fallback=str(WS / "configs/Cstar161-single.json"))
c["env"]["STRATA_MMVQ_IL_ROWS"] = rows
c["_comment"] = ("C*16.1 (round 18): C*16 + the side mixer's branches on F4's interleaved kernel with qkv first (exact) + "
                 "STRATA_MMVQ_IL_ROWS = F4's table measured on this RTX 5080 (upstream's mmvq_il_parity --emit-table; bitwise "
                 "the same output). Flags otherwise C*16's. Rollback: configs/Cstar16.json.")
def put(name, d):
    (C / f"{name}.json").write_text(json.dumps(d, indent=1) + "\n")
    sh = C / "Cstar16.shared-settings.json"
    (C / f"{name}.shared-settings.json").write_text(sh.read_text())
put("Cstar161", c)
s = json.loads((C / "Cstar16-single.json").read_text())
s.update(exe=c["exe"], server=c["server"], log=str(WS / "logs/engine-Cstar161-single.log"))
s["env"]["STRATA_MMVQ_IL_ROWS"] = rows
s["_comment"] = "C*16.1 on one GPU (the launcher's fallback when the 4060 Ti is missing)"
put("Cstar161-single", s)
b = json.loads(json.dumps(c)); b.update(log=str(WS / "logs/engine-BR161.log"), fallback=None); b["_comment"] = "browser-test copy of C*16.1's config"
put("BR161", b)
t = json.loads(json.dumps(c)); t.update(exe=str(WS / "engine-twin161/strata"), server=str(WS / "tmp/r18/wt-meas/serve/server.py"),
                                     log=str(WS / "logs/engine-twin161.log"), fallback=None)   # the twin's own server (force=N hooks)
t["env"]["STRATA_STATE_HASH"] = "1"; t["args"] += ["--adapt-swaps", "0"]   # as round 16's twin.json
t["_comment"] = "C*16.1's twin (the 4 MEASUREMENT commits: teacher forcing, force=N, state hashes) for the acceptance suite"
put("twin161", t)
r = json.loads(json.dumps(t)); r.update(log=str(WS / "logs/engine-R161RT.log"))
r["_comment"] = "C*16.1's twin with the adaptive tier fixed (--adapt-swaps 0): the chat-cache round trips"
put("R161RT", r)
print("configs written")
PY
for f in run-strata.sh switch-model.sh; do
  sed -e 's#STRATA_CONFIG:-$WS/configs/Cstar16.json}#STRATA_CONFIG:-$WS/configs/Cstar161.json}#' \
      -e 's#default configs/Cstar16.json = C\*16 (v0.1.41); rollback: STRATA_CONFIG=configs/Cstar15.json = C\*15,#default configs/Cstar161.json = C*16.1 (v0.1.41, round 18); rollback: STRATA_CONFIG=configs/Cstar16.json = C*16, configs/Cstar15.json = C*15,#' \
      -e 's#from configs/Cstar16.json (see REPORT.md, "Round 16": C\*16 = v0.1.41 + our 27 patches)#from configs/Cstar161.json (see REPORT.md, "Round 18": C*16.1 = v0.1.41 + our 27 patches + the side-mixer fix)#' \
      work/r16/$f.c16 > work/r18/$f.c161
done
grep -n 'STRATA_CONFIG:-' work/r18/run-strata.sh.c161 work/r18/switch-model.sh.c161
