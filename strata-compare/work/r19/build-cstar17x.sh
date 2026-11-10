#!/bin/bash
# build-cstar17x.sh - round 19, the FALLBACK (the user's plan if STRATA_SPEC_PROB or the gate under it is at fault): C*17's serving assets (copy of work/r18/build-cstar161.sh). C*17 = v0.1.42 + C*16.1's series
# with our exact sampling and our cost gate (= C*16.1's combination, which passed the near-tie check): branch r19-port (524a66b3,
# tree 1c05934d = runbook r19's patched tree); our STRATA_SPEC_EXACT=1 + STRATA_COST_GATE, STRATA_PREFILL_CPU_SHARE=0.4 below 1,792 tokens.
#   strata-cstar17   a worktree of r19-port's commit (serve/, tools/), built in a fresh build directory -> engine-cstar17
#   engine-twin17    branch r19-meas (+ the 4 MEASUREMENT commits, tmp/r19/twin), fresh build directory
#   configs          Cstar17.json (= runbook r19's cand.json on these assets), Cstar17-single.json (one GPU: the
#                    launcher's fallback, STRATA_ROUTE_TAIL_SKIP=0), twin17.json (the acceptance suite's twin), R17RT.json
#                    (the twin, round trips), BR17.json (browser-test copy); the launchers' C*17 copies (work/r19/*.c17)
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata-v0115/third_party/llama.cpp)
B=$(git -C strata rev-parse r19-port); T=$(git -C strata rev-parse r19-port^{tree})
[ "$T" = 1c05934d13d2580921eed42410f02352a3ebfa3b ] || { echo "r19-port tree $T is not runbook r19's"; exit 1; }
[ -d strata-cstar17 ] || git -C strata worktree add -q --detach $WS/strata-cstar17 $B
git -C strata-cstar17 checkout -q --detach $B
[ -z "$(git -C strata-cstar17 status --porcelain --untracked-files=no)" ] || { echo "strata-cstar17 is dirty"; exit 1; }
[ -e strata-cstar17/third_party/llama.cpp ] || ln -sfn $LL strata-cstar17/third_party/llama.cpp
build() {   # build TREE
  rm -rf $1/build
  (cd $1 && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
     "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build-configure.log 2>&1 \
   && nice -n 5 cmake --build build --target strata -j 24 > build.log 2>&1)
}
build strata-cstar17
mkdir -p engine-cstar17 && cp strata-cstar17/build/strata engine-cstar17/strata
echo "v0.1.42 + $(git -C strata rev-list --count v0.1.42..$B) commits (branch r19-port $B), tree $T" > engine-cstar17/SOURCE
sha256sum engine-cstar17/strata > engine-cstar17/SHA256; cat engine-cstar17/SOURCE engine-cstar17/SHA256
W=tmp/r19/twin
[ "$(git -C $W rev-list --count $B..HEAD)" = 4 ] && git -C $W merge-base --is-ancestor $B HEAD || { echo "the twin branch is not C*17 + 4"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ -e $W/third_party/llama.cpp ] || ln -sfn $LL $W/third_party/llama.cpp
build $W
mkdir -p engine-twin17 && cp $W/build/strata engine-twin17/strata && sha256sum engine-twin17/strata > engine-twin17/SHA256
echo "C*17 + 4 MEASUREMENT commits (branch r19-meas $(git -C $W rev-parse HEAD), tree $(git -C $W rev-parse HEAD^{tree}))" > engine-twin17/SOURCE
cat engine-twin17/SOURCE engine-twin17/SHA256
.venv/bin/python - <<'PY'
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"
c = json.loads((WS / "bringup/out/r19/configs/cand.json").read_text())
c.update(exe=str(WS / "engine-cstar17/strata"), server=str(WS / "strata-cstar17/serve/server.py"),
         log=str(WS / "logs/engine-Cstar17.log"), fallback=str(WS / "configs/Cstar17-single.json"))
c["env"]["STRATA_PREFILL_CPU_SHARE"] = "0.4"   # B3 (runbook r19's base had 0)
c["env"]["STRATA_PREFILL_CPU_SHARE_MAX"] = "1792"   # b3b / b3c: the share pays up to ~1,500 tokens, costs from ~2,000
c["_comment"] = ("C*17 (round 19): v0.1.42 + C*16.1's series (branch r19-port, 28 commits: our exact sampling "
                 "STRATA_SPEC_EXACT=1 + our cost gate, the combination that passed the near-tie sampler check; upstream's "
                 "STRATA_SPEC_PROB biased it, results/r19/sp-recheck/), STRATA_PREFILL_CPU_SHARE=0.4 (B3) on chunks below "
                 "STRATA_PREFILL_CPU_SHARE_MAX=1792 (b3b / b3c), helper source off (B4); two cards: the tail-skip default "
                 "does not act (B2). Flags and STRATA_MMVQ_IL_ROWS otherwise C*16.1's. Rollback: configs/Cstar161.json.")
def put(name, d):
    (C / f"{name}.json").write_text(json.dumps(d, indent=1) + "\n")
    (C / f"{name}.shared-settings.json").write_text((C / "Cstar161.shared-settings.json").read_text())
put("Cstar17", c)
s = json.loads((C / "Cstar161-single.json").read_text())
s.update(exe=c["exe"], server=c["server"], log=str(WS / "logs/engine-Cstar17-single.log"))
s["env"] = {k: v for k, v in c["env"].items() if k != "STRATA_DISJOINT_ADAPT"}
s["env"]["CUDA_VISIBLE_DEVICES"] = json.loads((C / "Cstar161-single.json").read_text())["env"]["CUDA_VISIBLE_DEVICES"]
s["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"   # one GPU on v0.1.42: the tail-skip default would act (lossy)
s["_comment"] = "C*17 on one GPU (the launcher's fallback when the 4060 Ti is missing); STRATA_ROUTE_TAIL_SKIP=0"
put("Cstar17-single", s)
b = json.loads(json.dumps(c)); b.update(log=str(WS / "logs/engine-BR17.log"), fallback=None); b["_comment"] = "browser-test copy of C*17's config"
put("BR17", b)
t = json.loads(json.dumps(c)); t.update(exe=str(WS / "engine-twin17/strata"), server=str(WS / "tmp/r19/twin/serve/server.py"),
                                     log=str(WS / "logs/engine-twin17.log"), fallback=None)
t["env"]["STRATA_STATE_HASH"] = "1"; t["args"] += ["--adapt-swaps", "0"]
t["_comment"] = "C*17's twin (the 4 MEASUREMENT commits: teacher forcing, force=N, state hashes) for the acceptance suite"
put("twin17", t)
r = json.loads(json.dumps(t)); r.update(log=str(WS / "logs/engine-R17RT.log"))
r["_comment"] = "C*17's twin with the adaptive tier fixed (--adapt-swaps 0): the chat-cache round trips"
put("R17RT", r)
print("configs written: Cstar17, Cstar17-single, BR17, twin17, R17RT")
for n in ("Cstar17", "Cstar17-single"):
    e = json.loads((C / f"{n}.json").read_text())["env"]
    print(n, {k: e.get(k) for k in ("STRATA_SPEC_PROB", "STRATA_SPEC_EXACT", "STRATA_COST_GATE", "STRATA_PREFILL_CPU_SHARE", "STRATA_ROUTE_TAIL_SKIP", "STRATA_DISJOINT_ADAPT")})
PY
for f in run-strata.sh switch-model.sh; do
  sed -e 's#STRATA_CONFIG:-$WS/configs/Cstar161.json}#STRATA_CONFIG:-$WS/configs/Cstar17.json}#' \
      -e 's#default configs/Cstar161.json = C\*16.1 (v0.1.41, round 18); rollback: STRATA_CONFIG=configs/Cstar16.json = C\*16,#default configs/Cstar17.json = C*17 (v0.1.42, round 19); rollback: STRATA_CONFIG=configs/Cstar161.json = C*16.1, configs/Cstar16.json = C*16,#' \
      -e 's#from configs/Cstar161.json (see REPORT.md, "Round 18": C\*16.1 = v0.1.41 + our 27 patches + the side-mixer fix)#from configs/Cstar17.json (see REPORT.md, "Round 19": C*17 = v0.1.42 + our series without exact sampling and the cost gate)#' \
      $f > work/r19/$f.c17
done
grep -n 'STRATA_CONFIG:-' work/r19/run-strata.sh.c17 work/r19/switch-model.sh.c17
diff run-strata.sh work/r19/run-strata.sh.c17 | head -20 || true
