#!/bin/bash
# build-cstar171.sh - round 19 Part D: C*17.1's serving assets (from work/r19/build-cstar17x.sh). C*17.1 = v0.1.43 + C*17's
# series (branch r19-port43, 29 commits: C*17's 28 rebased + d4e3905a, our chat cache dropped with v0.1.43's non-finite
# guard), tree 1c4d1dbf = runbook r19e's patched tree; C*17's settings (our exact sampling + cost gate, share 0.4 below 1,792).
#   strata-cstar171  a worktree of r19-port43's commit (serve/, tools/), fresh build directory -> engine-cstar171
#   engine-twin171   branch r19-meas43 (+ the 4 MEASUREMENT commits, tmp/r19/meas43), fresh build directory
#   configs          Cstar171.json (= $CAND, default configs/r19e-cand.json, on these assets), Cstar171-single.json (one GPU,
#                    STRATA_ROUTE_TAIL_SKIP=0), twin171.json, R171RT.json, BR171.json; launchers' copies work/r19/*.c171
# The pack and expert profile stay runbook r19e's (byte-identical to r19's).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
CAND=${CAND:-configs/r19e-cand.json}
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata-v0115/third_party/llama.cpp)
B=$(git -C strata rev-parse r19-port43); T=$(git -C strata rev-parse r19-port43^{tree})
[ "$T" = 1c4d1dbf5770ef4103234cbc5a2f4be62fa1fd8b ] || { echo "r19-port43 tree $T is not runbook r19e's"; exit 1; }
[ -d strata-cstar171 ] || git -C strata worktree add -q --detach $WS/strata-cstar171 $B
git -C strata-cstar171 checkout -q --detach $B
[ -z "$(git -C strata-cstar171 status --porcelain --untracked-files=no)" ] || { echo "strata-cstar171 is dirty"; exit 1; }
[ -e strata-cstar171/third_party/llama.cpp ] || ln -sfn $LL strata-cstar171/third_party/llama.cpp
build() {   # build TREE
  rm -rf $1/build
  (cd $1 && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
     "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build-configure.log 2>&1 \
   && nice -n 5 cmake --build build --target strata -j 24 > build.log 2>&1)
}
build strata-cstar171
mkdir -p engine-cstar171 && cp strata-cstar171/build/strata engine-cstar171/strata
echo "v0.1.43 + $(git -C strata rev-list --count v0.1.43..$B) commits (branch r19-port43 $B), tree $T" > engine-cstar171/SOURCE
sha256sum engine-cstar171/strata > engine-cstar171/SHA256; cat engine-cstar171/SOURCE engine-cstar171/SHA256
W=tmp/r19/meas43
[ "$(git -C $W rev-list --count $B..HEAD)" = 4 ] && git -C $W merge-base --is-ancestor $B HEAD || { echo "the twin branch is not C*17.1 + 4"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ -e $W/third_party/llama.cpp ] || ln -sfn $LL $W/third_party/llama.cpp
build $W
mkdir -p engine-twin171 && cp $W/build/strata engine-twin171/strata && sha256sum engine-twin171/strata > engine-twin171/SHA256
echo "C*17.1 + 4 MEASUREMENT commits (branch r19-meas43 $(git -C $W rev-parse HEAD), tree $(git -C $W rev-parse HEAD^{tree}))" > engine-twin171/SOURCE
cat engine-twin171/SOURCE engine-twin171/SHA256
CAND=$CAND .venv/bin/python - <<'PY'
import json, os
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"
c = json.loads((WS / os.environ["CAND"]).read_text())
c.update(exe=str(WS / "engine-cstar171/strata"), server=str(WS / "strata-cstar171/serve/server.py"),
         log=str(WS / "logs/engine-Cstar171.log"), fallback=str(WS / "configs/Cstar171-single.json"))
lag = c["env"].get("STRATA_ADAPT_LAG")
c["_comment"] = ("C*17.1 (round 19 Part D): v0.1.43 + C*17's series (branch r19-port43, 29 commits: C*17's 28 + our chat cache "
                 "dropped with v0.1.43's non-finite guard), C*17's settings: our exact sampling STRATA_SPEC_EXACT=1 + our cost gate, "
                 "STRATA_PREFILL_CPU_SHARE=0.4 below STRATA_PREFILL_CPU_SHARE_MAX=1792, "
                 + (f"STRATA_ADAPT_LAG={lag} (v0.1.43's adaptive overlap stays off with it, D2)" if lag else "STRATA_ADAPT_LAG unset: v0.1.43's adaptive overlap (D2)")
                 + "; STRATA_ROUTE_RESIDENT off (v0.1.43's default). Rollback: configs/Cstar17.json.")
def put(name, d):
    (C / f"{name}.json").write_text(json.dumps(d, indent=1) + "\n")
    (C / f"{name}.shared-settings.json").write_text((C / "Cstar17.shared-settings.json").read_text())
put("Cstar171", c)
s = json.loads((C / "Cstar17-single.json").read_text())
s.update(exe=c["exe"], server=c["server"], log=str(WS / "logs/engine-Cstar171-single.log"))
s["env"] = {k: v for k, v in c["env"].items() if k != "STRATA_DISJOINT_ADAPT"}
s["env"]["CUDA_VISIBLE_DEVICES"] = json.loads((C / "Cstar17-single.json").read_text())["env"]["CUDA_VISIBLE_DEVICES"]
s["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"   # one GPU: the tail-skip default would act (lossy)
s["_comment"] = "C*17.1 on one GPU (the launcher's fallback when the 4060 Ti is missing); STRATA_ROUTE_TAIL_SKIP=0"
put("Cstar171-single", s)
b = json.loads(json.dumps(c)); b.update(log=str(WS / "logs/engine-BR171.log"), fallback=None); b["_comment"] = "browser-test copy of C*17.1's config"
put("BR171", b)
t = json.loads(json.dumps(c)); t.update(exe=str(WS / "engine-twin171/strata"), server=str(WS / "tmp/r19/meas43/serve/server.py"),
                                     log=str(WS / "logs/engine-twin171.log"), fallback=None)
t["env"]["STRATA_STATE_HASH"] = "1"; t["args"] += ["--adapt-swaps", "0"]
t["_comment"] = "C*17.1's twin (the 4 MEASUREMENT commits: teacher forcing, force=N, state hashes) for the acceptance suite"
put("twin171", t)
r = json.loads(json.dumps(t)); r.update(log=str(WS / "logs/engine-R171RT.log"))
r["_comment"] = "C*17.1's twin with the adaptive tier fixed (--adapt-swaps 0): the chat-cache round trips"
put("R171RT", r)
print("configs written: Cstar171, Cstar171-single, BR171, twin171, R171RT")
for n in ("Cstar171", "Cstar171-single"):
    e = json.loads((C / f"{n}.json").read_text())["env"]
    print(n, {k: e.get(k) for k in ("STRATA_SPEC_PROB", "STRATA_SPEC_EXACT", "STRATA_COST_GATE", "STRATA_PREFILL_CPU_SHARE", "STRATA_PREFILL_CPU_SHARE_MAX",
                                     "STRATA_ADAPT_LAG", "STRATA_ROUTE_TAIL_SKIP", "STRATA_ROUTE_RESIDENT", "STRATA_DISJOINT_ADAPT")})
PY
for f in run-strata.sh switch-model.sh; do
  sed -e 's#STRATA_CONFIG:-$WS/configs/Cstar17.json}#STRATA_CONFIG:-$WS/configs/Cstar171.json}#' \
      -e 's#default configs/Cstar17.json = C\*17 (v0.1.42, round 19); rollback: STRATA_CONFIG=configs/Cstar161.json = C\*16.1,#default configs/Cstar171.json = C*17.1 (v0.1.43, round 19 Part D); rollback: STRATA_CONFIG=configs/Cstar17.json = C*17, configs/Cstar161.json = C*16.1,#' \
      -e 's#from configs/Cstar17.json (see REPORT.md, "Round 19": C\*17 = v0.1.42 + our series without exact sampling and the cost gate)#from configs/Cstar171.json (see REPORT.md, "Round 19": C*17.1 = v0.1.43 + our series, with our exact sampling and cost gate)#' \
      $f > work/r19/$f.c171
done
grep -n 'STRATA_CONFIG:-' work/r19/run-strata.sh.c171 work/r19/switch-model.sh.c171
diff run-strata.sh work/r19/run-strata.sh.c171 || true; diff switch-model.sh work/r19/switch-model.sh.c171 || true
