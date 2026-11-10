#!/bin/bash
# s7_q4prep.sh — round 15 step 7: UD-Q4_K_XL (read-only, the HF cache) on v0.1.40.2: its pack (the runbook's inspect /
# fitplan / pack stages, run r15q4, the r15q5s tree: K-quant kernels) and a twin config from r15q5s's (the same engine)
# with the Q4 paths and Rehearsal B's 48 GiB RAM budget (the 20 GB floor) -> work/r15/cfg/s7-q4-twin.json
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
R=$WS/bringup/out/r15q4
[ -e $R/strata-patched ] || ln -sfn $WS/bringup/out/r15q5s/strata-patched $R/strata-patched
bringup/runbook.sh r15q4 inspect fitplan pack
.venv/bin/python - <<'PY'
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); R = WS / "bringup/out/r15q4"
c = json.loads((WS / "bringup/out/r15q5s/configs/twin.json").read_text()); a = c["args"]
ins = json.loads((R / "inspect.json").read_text())
def setarg(f, v):
    if f in a: a[a.index(f) + 1] = v
    else: a.extend([f, v])
setarg("--pack", str(R / "pack")); setarg("--native", ins["file"][0]); setarg("--ple-gguf", ins.get("ple_shard") or ins["file"][-1])
setarg("--resident-budget-gib", "48"); setarg("--vram-reserve-mib", "813")
c["cwd"] = str(R); c["tokenizer"] = str(R / "pack/tokenizer"); c["log"] = str(WS / "logs/r15/engine-s7-q4.log")
c["_comment"] = "Round 15 step 7: UD-Q4_K_XL scored on v0.1.40.2 + r15p27's twin (r15q5s's engine), the 5080 + 48 GiB budget"
Path(WS / "work/r15/cfg/s7-q4-twin.json").write_text(json.dumps(c, indent=1) + "\n")
print("wrote work/r15/cfg/s7-q4-twin.json:", " ".join(x for x in a if "q4" in x.lower() or x.startswith("--resident")))
PY
