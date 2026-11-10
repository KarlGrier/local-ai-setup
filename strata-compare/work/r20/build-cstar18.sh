#!/bin/bash
# build-cstar18.sh - Round 20 item 1: C*18's serving assets (from work/r19/build-cstar171.sh). C*18 = v0.1.44.1 + C*17.1's
# 29-commit series only (branch r20-trial-v04441, tree 8641a6c1 = runbook r20a's patched tree); no MEASUREMENT commit.
# C*17.1's settings (configs/Cstar171.json: our exact sampling + cost gate, share 0.4 below 1,792, STRATA_ADAPT_LAG=2,
# helper 3300) on runbook r20a's pack / prompts; every v0.1.44.1 default as shipped unless CB0=1
# (STRATA_COMMIT_BATCH=0: only if exact7 shows the new default is not bitwise).
#   strata-cstar18   a worktree of r20-trial-v04441 (serve/, tools/), fresh build directory -> engine-cstar18
#   engine-twin18    branch r20-trial-meas-v04441 (+ the 4 MEASUREMENT commits, worktree tmp/r20/meas441) -> measurements only
#   configs          Cstar18.json, Cstar18-single.json (one GPU, STRATA_ROUTE_TAIL_SKIP=0), twin18.json, R18RT.json,
#                    BR18.json; the launchers' copies work/r20/*.c18 (installed only by promote-c18.sh)
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata-v0115/third_party/llama.cpp)
B=$(git -C strata rev-parse r20-trial-v04441); T=$(git -C strata rev-parse r20-trial-v04441^{tree})
[ "$T" = 8641a6c149f7d67b7bed73090700e2ab5f4871e2 ] || { echo "r20-trial-v04441 tree $T is not runbook r20a's"; exit 1; }
[ "$(git -C strata rev-list --count v0.1.44.1..$B)" = 29 ] || { echo "not 29 commits on v0.1.44.1"; exit 1; }
! git -C strata log --format=%s v0.1.44.1..$B | grep -q MEASUREMENT || { echo "a MEASUREMENT commit in C*18's series"; exit 1; }
[ -d strata-cstar18 ] || git -C strata worktree add -q --detach $WS/strata-cstar18 $B
git -C strata-cstar18 checkout -q --detach $B
[ -z "$(git -C strata-cstar18 status --porcelain --untracked-files=no)" ] || { echo "strata-cstar18 is dirty"; exit 1; }
[ -e strata-cstar18/third_party/llama.cpp ] || ln -sfn $LL strata-cstar18/third_party/llama.cpp
build() {   # build TREE
  rm -rf $1/build
  (cd $1 && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
     "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build-configure.log 2>&1 \
   && nice -n 5 cmake --build build --target strata -j 24 > build.log 2>&1)
}
build strata-cstar18
mkdir -p engine-cstar18 && cp strata-cstar18/build/strata engine-cstar18/strata
echo "v0.1.44.1 + $(git -C strata rev-list --count v0.1.44.1..$B) commits (branch r20-trial-v04441 $B), tree $T" > engine-cstar18/SOURCE
sha256sum engine-cstar18/strata > engine-cstar18/SHA256; cat engine-cstar18/SOURCE engine-cstar18/SHA256
echo "runbook r20a's patched engine: $(cut -c1-16 bringup/out/r20a/engine-patched/SHA256)"
M=$(git -C strata rev-parse r20-trial-meas-v04441); W=tmp/r20/meas441
[ "$(git -C strata rev-list --count $B..$M)" = 4 ] && git -C strata merge-base --is-ancestor $B $M || { echo "the twin branch is not C*18 + 4"; exit 1; }
[ -d $W ] || git -C strata worktree add -q --detach $WS/$W $M
git -C $W checkout -q --detach $M
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ -e $W/third_party/llama.cpp ] || ln -sfn $LL $W/third_party/llama.cpp
build $W
mkdir -p engine-twin18 && cp $W/build/strata engine-twin18/strata && sha256sum engine-twin18/strata > engine-twin18/SHA256
echo "C*18 + 4 MEASUREMENT commits (branch r20-trial-meas-v04441 $M, tree $(git -C $W rev-parse HEAD^{tree})) - measurements only, never served" > engine-twin18/SOURCE
cat engine-twin18/SOURCE engine-twin18/SHA256
CB0=${CB0:-0} .venv/bin/python - <<'PY'
import json, os
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"; R = WS / "bringup/out/r20a"
c = json.loads((C / "Cstar171.json").read_text())
a = c["args"]
def setarg(flag, val):
    a[a.index(flag) + 1] = val
setarg("--pack", str(R / "pack")); setarg("--expert-profile", str(WS / "strata-cstar18/data/expert-profile.bin"))
c.update(exe=str(WS / "engine-cstar18/strata"), server=str(WS / "strata-cstar18/serve/server.py"), cwd=str(R),
         tokenizer=str(R / "pack/tokenizer"), log=str(WS / "logs/engine-Cstar18.log"), fallback=str(C / "Cstar18-single.json"))
if os.environ["CB0"] == "1":
    c["env"]["STRATA_COMMIT_BATCH"] = "0"
c["_comment"] = ("C*18 (round 20): v0.1.44.1 + C*17.1's series (branch r20-trial-v04441, 29 commits, no MEASUREMENT commit), "
                 "C*17.1's settings: our exact sampling STRATA_SPEC_EXACT=1 + our cost gate, STRATA_PREFILL_CPU_SHARE=0.4 below "
                 "STRATA_PREFILL_CPU_SHARE_MAX=1792, STRATA_ADAPT_LAG=2 (the adaptive overlap stays off; v0.1.43.1 made it opt-in again), "
                 "helper cache 3300 on the 4060 Ti (the route tail skip is off with a helper GPU); "
                 + ("STRATA_COMMIT_BATCH=0 (the v0.1.44 default was not bitwise here). " if os.environ["CB0"] == "1"
                    else "v0.1.44's STRATA_COMMIT_BATCH default kept (bitwise in exact7). ")
                 + "STRATA_HC_Q8 unset (off on CUDA). Rollback: configs/Cstar171.json.")
def put(name, d):
    (C / f"{name}.json").write_text(json.dumps(d, indent=1) + "\n")
    (C / f"{name}.shared-settings.json").write_text((C / "Cstar171.shared-settings.json").read_text())
put("Cstar18", c)
s = json.loads((C / "Cstar171-single.json").read_text())
s.update(exe=c["exe"], server=c["server"], log=str(WS / "logs/engine-Cstar18-single.log"))
s["env"] = {k: v for k, v in c["env"].items() if k != "STRATA_DISJOINT_ADAPT"}
s["env"]["CUDA_VISIBLE_DEVICES"] = json.loads((C / "Cstar171-single.json").read_text())["env"]["CUDA_VISIBLE_DEVICES"]
s["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"   # one GPU: the tail-skip default would act (lossy)
s["_comment"] = "C*18 on one GPU (the launcher's fallback when the 4060 Ti is missing); STRATA_ROUTE_TAIL_SKIP=0"
put("Cstar18-single", s)
b = json.loads(json.dumps(c)); b.update(log=str(WS / "logs/engine-BR18.log"), fallback=None); b["_comment"] = "browser-test copy of C*18's config"
put("BR18", b)
t = json.loads(json.dumps(c)); t.update(exe=str(WS / "engine-twin18/strata"), server=str(WS / "tmp/r20/meas441/serve/server.py"),
                                     log=str(WS / "logs/engine-twin18.log"), fallback=None)
t["env"]["STRATA_STATE_HASH"] = "1"; t["args"] += ["--adapt-swaps", "0"]
t["_comment"] = "C*18's twin (the 4 MEASUREMENT commits: teacher forcing, force=N, state hashes) for the acceptance suite; never served"
put("twin18", t)
r = json.loads(json.dumps(t)); r.update(log=str(WS / "logs/engine-R18RT.log"))
r["_comment"] = "C*18's twin with the adaptive tier fixed (--adapt-swaps 0): the chat-cache round trips"
put("R18RT", r)
print("configs written: Cstar18, Cstar18-single, BR18, twin18, R18RT")
o = json.loads((C / "Cstar171.json").read_text())
print("Cstar18 vs Cstar171: env added", {k: v for k, v in c["env"].items() if k not in o["env"]}, "changed",
      {k: (o["env"][k], v) for k, v in c["env"].items() if k in o["env"] and o["env"][k] != v}, "removed", [k for k in o["env"] if k not in c["env"]])
print("args equal apart from paths:", [x for x in c["args"] if not x.startswith("/")] == [x for x in o["args"] if not x.startswith("/")])
PY
for f in run-strata.sh switch-model.sh; do
  sed -e 's#STRATA_CONFIG:-$WS/configs/Cstar171.json}#STRATA_CONFIG:-$WS/configs/Cstar18.json}#' \
      -e 's#default configs/Cstar171.json = C\*17.1 (v0.1.43, round 19 Part D); rollback: STRATA_CONFIG=configs/Cstar17.json = C\*17,#default configs/Cstar18.json = C*18 (v0.1.44.1, round 20); rollback: STRATA_CONFIG=configs/Cstar171.json = C*17.1, configs/Cstar17.json = C*17,#' \
      -e 's#from configs/Cstar171.json (see REPORT.md, "Round 19": C\*17.1 = v0.1.43 + our series, with our exact sampling and cost gate)#from configs/Cstar18.json (see REPORT.md, "Round 20": C*18 = v0.1.44.1 + our series, with our exact sampling and cost gate)#' \
      $f > work/r20/$f.c18
done
grep -n 'STRATA_CONFIG:-' work/r20/run-strata.sh.c18 work/r20/switch-model.sh.c18
diff run-strata.sh work/r20/run-strata.sh.c18 || true; diff switch-model.sh work/r20/switch-model.sh.c18 || true
