#!/bin/bash
# build-cstar16.sh — round 16 (copy of work/r15/build-cstar15.sh): C*16's serving assets from the clean-clone run
# r16z (runbook; no rebuild): engine-cstar16 = r16z's engine-patched (v0.1.41 + patches/r16p27), strata-cstar16 =
# a checkout of the same tree (serve/, tools/), configs/Cstar16.json = r16z's cand.json (C*15's flags) with the stable
# paths (C*15's pack and profile: the fresh v0.1.41 pack is byte-identical apart from its conversions.json, which the
# engine does not read) and STEP 1's share setting (SHARE=default|0, argument 1), Cstar16-single.json (one GPU, the
# launcher's fallback), the shared settings, the round-trip twin config R16RT.json and the browser copy BR16.json, the
# launchers' C*16 copies (work/r16/*.c16; not installed here - promote-c16.sh installs them after the gates and the soak).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
R=$WS/bringup/out/r16z
SHARE=${1:?default or 0 (step 1)}
mkdir -p engine-cstar16 && cp $R/engine-patched/strata engine-cstar16/strata && cp $R/engine-patched/SOURCE engine-cstar16/SOURCE
sha256sum engine-cstar16/strata > engine-cstar16/SHA256; cat engine-cstar16/SOURCE engine-cstar16/SHA256
[ -d strata-cstar16 ] || git -C strata worktree add -q --detach $WS/strata-cstar16 r16-port
[ "$(git -C strata-cstar16 rev-parse HEAD^{tree})" = "$(git -C $R/strata-patched rev-parse HEAD^{tree})" ] || { echo "tree mismatch"; exit 1; }
[ -e strata-cstar16/third_party/llama.cpp ] || ln -sfn $(readlink -f strata-v0115/third_party/llama.cpp) strata-cstar16/third_party/llama.cpp
SHARE=$SHARE .venv/bin/python - <<'PY'
import json, shutil
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
R = WS / "bringup/out/r16z"
import os
SHARE = os.environ["SHARE"]
c = json.loads((R / "configs/cand.json").read_text())
a = c["args"]
def setarg(a, f, v): a[a.index(f) + 1] = v
setarg(a, "--pack", str(WS / "strata-v0115/packs/iq3_s"))
setarg(a, "--expert-profile", str(WS / "strata-v0115/data/expert-profile.bin"))
c.update(exe=str(WS / "engine-cstar16/strata"), server=str(WS / "strata-cstar16/serve/server.py"),
         cwd=str(WS / "strata-v0115"), tokenizer=str(WS / "strata-v0115/packs/iq3_s/tokenizer"),
         log=str(WS / "logs/engine-Cstar16.log"), fallback=str(WS / "configs/Cstar16-single.json"))
c["env"].pop("STRATA_PREFILL_CPU_SHARE", None)
if SHARE == "0": c["env"]["STRATA_PREFILL_CPU_SHARE"] = "0"
c["_comment"] = ("C*16 candidate (round 16): Strata v0.1.41 + patches/r16p27 (C*15's 27 commits; one test-file conflict "
                 "resolved: #567's tests beside 0.1.41's piece-cache tests). Flags = C*15's; CPU prompt-read share: "
                 + ("upstream's default (on for chunks below 1,024 tokens)" if SHARE != "0" else "off (STRATA_PREFILL_CPU_SHARE=0)")
                 + ". Rollback: configs/Cstar15.json.")
(WS / "configs/Cstar16.json").write_text(json.dumps(c, indent=1) + "\n")
s = json.loads(json.dumps(c))
if "--expert-cache-device1" in s["args"]:
    i = s["args"].index("--expert-cache-device1"); del s["args"][i:i + 2]
s["env"]["CUDA_VISIBLE_DEVICES"] = s["env"]["CUDA_VISIBLE_DEVICES"].split(",")[0]
s["env"].pop("STRATA_DISJOINT_ADAPT", None)
s.update(log=str(WS / "logs/engine-Cstar16-single.log"), fallback=None)
s["_comment"] = "C*16 on one GPU (the launcher's fallback when the 4060 Ti is missing)"
(WS / "configs/Cstar16-single.json").write_text(json.dumps(s, indent=1) + "\n")
# the round-trip twin (Round 15's R15RT.json pattern): the twin engine, --adapt-swaps 0, STRATA_STATE_HASH=1
rt = json.loads((WS / "configs/R15RT.json").read_text())
t = json.loads(json.dumps(c)); ta = t["args"]
setarg(ta, "--pack", str(R / "pack")); setarg(ta, "--expert-profile", str(R / "strata-twin/data/expert-profile.bin"))
if "--adapt-swaps" in ta: setarg(ta, "--adapt-swaps", "0")
else: ta.extend(["--adapt-swaps", "0"])
t["env"]["STRATA_STATE_HASH"] = "1"
t.update(exe=str(R / "engine-twin/strata"), server=str(R / "strata-twin/serve/server.py"), port=rt.get("port", 8081),
         log=str(WS / "logs/engine-R16RT.log"), fallback=None)
t["_comment"] = "round 16: chat-cache round trips on C*16's twin"
(WS / "configs/R16RT.json").write_text(json.dumps(t, indent=1) + "\n")
b = json.loads(json.dumps(c)); b.update(port=8081, log=str(WS / "logs/engine-BR16.log"), fallback=None)
b["_comment"] = "browser-test copy of C*16's config"
(WS / "configs/BR16.json").write_text(json.dumps(b, indent=1) + "\n")
for n in ("Cstar16", "Cstar16-single", "R16RT", "BR16"):
    shutil.copy(WS / "configs/Cstar15.shared-settings.json", WS / f"configs/{n}.shared-settings.json")
print("configs/Cstar16.json, Cstar16-single.json, R16RT.json, BR16.json written")
PY
.venv/bin/python - <<'PY'
from pathlib import Path
for f in ("run-strata.sh", "switch-model.sh"):
    s = Path(f).read_text()
    s = s.replace("(default configs/Cstar15.json = C*15 (v0.1.40.2); rollback: STRATA_CONFIG=configs/Cstar14.json = C*14, configs/Cstar131.json = C*13.1,",
                  "(default configs/Cstar16.json = C*16 (v0.1.41); rollback: STRATA_CONFIG=configs/Cstar15.json = C*15, configs/Cstar14.json = C*14, configs/Cstar131.json = C*13.1,")
    s = s.replace('Strata = engine + settings from configs/Cstar15.json (see REPORT.md, "Round 15": C*15 = v0.1.40.2 + our 27 patches)',
                  'Strata = engine + settings from configs/Cstar16.json (see REPORT.md, "Round 16": C*16 = v0.1.41 + our 27 patches)')
    s = s.replace("$WS/configs/Cstar15.json}", "$WS/configs/Cstar16.json}")
    Path(f"work/r16/{f}.c16").write_text(s)
PY
for f in run-strata.sh switch-model.sh; do diff $f work/r16/$f.c16 | grep "^[<>]" | cut -c1-140 || true; done
(cd strata-cstar16 && timeout 900 $WS/.venv/bin/python -m unittest discover -s serve -t . 2>&1 | tail -1)
