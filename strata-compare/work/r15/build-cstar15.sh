#!/bin/bash
# build-cstar15.sh — round 15 step 8 (copy of work/r14/build-cstar14.sh): C*15's serving assets from the clean-clone run
# r15 (runbook, 07:53; no rebuild): engine-cstar15 = r15's engine-patched (v0.1.40.2 + patches/r15p27), strata-cstar15 =
# a checkout of the same tree (serve/, tools/), configs/Cstar15.json = r15's cand.json (C*14's flags) with the stable
# paths (C*14's pack and profile: the fresh v0.1.40.2 pack is byte-identical apart from its conversions.json, which the
# engine does not read; the profile is identical), Cstar15-single.json (one GPU, the launcher's fallback), the shared
# settings, the round-trip twin config R15RT.json and the browser copy BR15.json, the launchers' C*15 copies
# (work/r15/*.c15; not installed here - promote-c15.sh installs them after the gates and the soak).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
R=$WS/bringup/out/r15
mkdir -p engine-cstar15 && cp $R/engine-patched/strata engine-cstar15/strata && cp $R/engine-patched/SOURCE engine-cstar15/SOURCE
sha256sum engine-cstar15/strata > engine-cstar15/SHA256; cat engine-cstar15/SOURCE engine-cstar15/SHA256
[ -d strata-cstar15 ] || git -C strata worktree add -q --detach $WS/strata-cstar15 r15-port
[ "$(git -C strata-cstar15 rev-parse HEAD^{tree})" = "$(git -C $R/strata-patched rev-parse HEAD^{tree})" ] || { echo "tree mismatch"; exit 1; }
[ -e strata-cstar15/third_party/llama.cpp ] || ln -sfn $(readlink -f strata-v0115/third_party/llama.cpp) strata-cstar15/third_party/llama.cpp
.venv/bin/python - <<'PY'
import json, shutil
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
R = WS / "bringup/out/r15"
c = json.loads((R / "configs/cand.json").read_text())
a = c["args"]
def setarg(a, f, v): a[a.index(f) + 1] = v
setarg(a, "--pack", str(WS / "strata-v0115/packs/iq3_s"))
setarg(a, "--expert-profile", str(WS / "strata-v0115/data/expert-profile.bin"))
c.update(exe=str(WS / "engine-cstar15/strata"), server=str(WS / "strata-cstar15/serve/server.py"),
         cwd=str(WS / "strata-v0115"), tokenizer=str(WS / "strata-v0115/packs/iq3_s/tokenizer"),
         log=str(WS / "logs/engine-Cstar15.log"), fallback=str(WS / "configs/Cstar15-single.json"))
c["_comment"] = ("C*15 (round 15): Strata v0.1.40.2 + patches/r15p27 (27 commits: the ledger pass onto v0.1.40.2; B.3 dropped "
                 "for upstream's F4 (STRATA_MMVQ_IL, same switch), row 28 for #954; our exact sampling beside upstream's "
                 "STRATA_SPEC_PROB, our side mixer beside STRATA_DF_BRANCH). Flags = C*14's. Rollback: configs/Cstar14.json.")
(WS / "configs/Cstar15.json").write_text(json.dumps(c, indent=1) + "\n")
s = json.loads(json.dumps(c))
if "--expert-cache-device1" in s["args"]:
    i = s["args"].index("--expert-cache-device1"); del s["args"][i:i + 2]
s["env"]["CUDA_VISIBLE_DEVICES"] = s["env"]["CUDA_VISIBLE_DEVICES"].split(",")[0]
s["env"].pop("STRATA_DISJOINT_ADAPT", None)
s.update(log=str(WS / "logs/engine-Cstar15-single.log"), fallback=None)
s["_comment"] = "C*15 on one GPU (the launcher's fallback when the 4060 Ti is missing)"
(WS / "configs/Cstar15-single.json").write_text(json.dumps(s, indent=1) + "\n")
# the round-trip twin (Round 14's R14RT.json pattern): the twin engine, --adapt-swaps 0, STRATA_STATE_HASH=1
rt = json.loads((WS / "configs/R14RT.json").read_text())
t = json.loads(json.dumps(c)); ta = t["args"]
setarg(ta, "--pack", str(R / "pack")); setarg(ta, "--expert-profile", str(R / "strata-twin/data/expert-profile.bin"))
if "--adapt-swaps" in ta: setarg(ta, "--adapt-swaps", "0")
else: ta.extend(["--adapt-swaps", "0"])
t["env"]["STRATA_STATE_HASH"] = "1"
t.update(exe=str(R / "engine-twin/strata"), server=str(R / "strata-twin/serve/server.py"), port=rt.get("port", 8081),
         log=str(WS / "logs/engine-R15RT.log"), fallback=None)
t["_comment"] = "round 15: chat-cache round trips on C*15's twin"
(WS / "configs/R15RT.json").write_text(json.dumps(t, indent=1) + "\n")
b = json.loads(json.dumps(c)); b.update(port=8081, log=str(WS / "logs/engine-BR15.log"), fallback=None)
b["_comment"] = "browser-test copy of C*15's config"
(WS / "configs/BR15.json").write_text(json.dumps(b, indent=1) + "\n")
for n in ("Cstar15", "Cstar15-single", "R15RT", "BR15"):
    shutil.copy(WS / "configs/Cstar14.shared-settings.json", WS / f"configs/{n}.shared-settings.json")
print("configs/Cstar15.json, Cstar15-single.json, R15RT.json, BR15.json written")
PY
.venv/bin/python - <<'PY'
from pathlib import Path
for f in ("run-strata.sh", "switch-model.sh"):
    s = Path(f).read_text()
    s = s.replace("(default configs/Cstar14.json = C*14 (v0.1.40.1); rollback: STRATA_CONFIG=configs/Cstar131.json = C*13.1,",
                  "(default configs/Cstar15.json = C*15 (v0.1.40.2); rollback: STRATA_CONFIG=configs/Cstar14.json = C*14, configs/Cstar131.json = C*13.1,")
    s = s.replace('Strata = engine + settings from configs/Cstar14.json (see REPORT.md, "Round 14": C*14 = v0.1.40.1 + our 35 patches)',
                  'Strata = engine + settings from configs/Cstar15.json (see REPORT.md, "Round 15": C*15 = v0.1.40.2 + our 27 patches)')
    s = s.replace("$WS/configs/Cstar14.json}", "$WS/configs/Cstar15.json}")
    Path(f"work/r15/{f}.c15").write_text(s)
PY
for f in run-strata.sh switch-model.sh; do diff $f work/r15/$f.c15 | grep "^[<>]" | cut -c1-140 || true; done
(cd strata-cstar15 && timeout 900 $WS/.venv/bin/python -m unittest discover -s serve -t . 2>&1 | tail -1)
