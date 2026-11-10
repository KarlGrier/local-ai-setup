#!/bin/bash
# build-cstar14.sh — round 14 step 8: C*14's serving assets from the clean-clone run r14f (no rebuild): engine-cstar14 =
# r14f's engine-patched (v0.1.40.1 + patches/r14c35), strata-cstar14 = a checkout of the same tree (serve/, tools/),
# configs/Cstar14.json = r14f's cand.json with the stable paths (C*13.1's pack and profile: byte-identical to the fresh
# v0.1.40.1 pack apart from its new conversions.json, which the engine does not read), Cstar14-single.json (one GPU,
# the launcher's fallback), the shared settings, the launchers' C*14 copies (work/r14/*.c14; not installed here).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
R=$WS/bringup/out/r14f
mkdir -p engine-cstar14 && cp $R/engine-patched/strata engine-cstar14/strata && cp $R/engine-patched/SOURCE engine-cstar14/SOURCE
sha256sum engine-cstar14/strata > engine-cstar14/SHA256; cat engine-cstar14/SOURCE engine-cstar14/SHA256
[ -d strata-cstar14 ] || git -C strata worktree add -q --detach $WS/strata-cstar14 r14-port3g
[ "$(git -C strata-cstar14 rev-parse HEAD^{tree})" = "$(git -C $R/strata-patched rev-parse HEAD^{tree})" ] || { echo "tree mismatch"; exit 1; }
[ -e strata-cstar14/third_party/llama.cpp ] || ln -sfn $(readlink -f strata-v0115/third_party/llama.cpp) strata-cstar14/third_party/llama.cpp
.venv/bin/python - <<'PY'
import json, shutil
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
c = json.loads((WS / "bringup/out/r14f/configs/cand.json").read_text())
a = c["args"]
def setarg(f, v): a[a.index(f) + 1] = v
setarg("--pack", str(WS / "strata-v0115/packs/iq3_s"))
setarg("--expert-profile", str(WS / "strata-v0115/data/expert-profile.bin"))
c.update(exe=str(WS / "engine-cstar14/strata"), server=str(WS / "strata-cstar14/serve/server.py"),
         cwd=str(WS / "strata-v0115"), tokenizer=str(WS / "strata-v0115/packs/iq3_s/tokenizer"),
         log=str(WS / "logs/engine-Cstar14.log"), fallback=str(WS / "configs/Cstar14-single.json"))
c["_comment"] = ("C*14 (round 14): Strata v0.1.40.1 (82f46a8) + patches/r14c35 (35 commits: the ledger pass, PR245 / the "
                 "n-gram prefetch / our landing / our helper rule dropped for v0.1.40's own, + the cost-aware draft gate). "
                 "Flags = C*13.1's; STRATA_ADAPT_LAG=2 and STRATA_DISJOINT_ADAPT=1 are upstream's forms of our former "
                 "ADAPT_LAND=2 / ADAPT_HELPER=1 (bit-identical); STRATA_COST_GATE = Round 12's table. Rollback: configs/Cstar131.json.")
(WS / "configs/Cstar14.json").write_text(json.dumps(c, indent=1) + "\n")
s = json.loads(json.dumps(c))
if "--expert-cache-device1" in s["args"]:
    i = s["args"].index("--expert-cache-device1"); del s["args"][i:i + 2]
s["env"]["CUDA_VISIBLE_DEVICES"] = s["env"]["CUDA_VISIBLE_DEVICES"].split(",")[0]
s["env"].pop("STRATA_DISJOINT_ADAPT", None)
s.update(log=str(WS / "logs/engine-Cstar14-single.log"), fallback=None)
s["_comment"] = "C*14 on one GPU (the launcher's fallback when the 4060 Ti is missing)"
(WS / "configs/Cstar14-single.json").write_text(json.dumps(s, indent=1) + "\n")
for n in ("Cstar14", "Cstar14-single"):
    shutil.copy(WS / "configs/Cstar131.shared-settings.json", WS / f"configs/{n}.shared-settings.json")
print("configs/Cstar14.json, Cstar14-single.json written")
PY
.venv/bin/python - <<'PY'
from pathlib import Path
for f in ("run-strata.sh", "switch-model.sh"):
    s = Path(f).read_text()
    s = s.replace("(default configs/Cstar131.json = C*13.1; rollback: STRATA_CONFIG=configs/Cstar13.json = C*13,",
                  "(default configs/Cstar14.json = C*14 (v0.1.40.1); rollback: STRATA_CONFIG=configs/Cstar131.json = C*13.1, configs/Cstar13.json = C*13,")
    s = s.replace('Strata = engine + settings from configs/Cstar131.json (see REPORT.md, "Round 13": C*13.1 = C*13 + the round 13 fixes and guards, on v0.1.39)',
                  'Strata = engine + settings from configs/Cstar14.json (see REPORT.md, "Round 14": C*14 = v0.1.40.1 + our 35 patches)')
    s = s.replace("$WS/configs/Cstar131.json}", "$WS/configs/Cstar14.json}")
    Path(f"work/r14/{f}.c14").write_text(s)
PY
for f in run-strata.sh switch-model.sh; do diff $f work/r14/$f.c14 | grep '^[<>]' | cut -c1-140; done
