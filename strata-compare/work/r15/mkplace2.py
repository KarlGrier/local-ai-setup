#!/usr/bin/env python3
"""mkplace2.py NAME BUDGET_GIB — round 15 step 4 → 3 (your rule: when the largest budget at your 6 GiB floor wins, the
budget placements are probed again at it before the best placement is picked): configs/r15-NAME-{B,C,D}x.json = step 3's
B / C / D with --resident-budget-gib BUDGET and step 4's kept file-tier option (STRATA_UNBUFFERED_LOAD=1); Q8_0's C keeps
its working split (47, reserves 1,613 / 1,213 MiB); configs/r15-q8-Ax.json = A + STRATA_IO_PREFETCH=1 (kept on A)."""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
name, budget = sys.argv[1], sys.argv[2]
src = {"B": f"r15-{name}-B", "C": "r15-q8-C47r2" if name == "q8" else f"r15-{name}-C", "D": f"r15-{name}-D"}
for k, s in src.items():
    c = json.loads((WS / f"configs/{s}.json").read_text())
    a = c["args"]
    a[a.index("--resident-budget-gib") + 1] = budget
    c["env"]["STRATA_UNBUFFERED_LOAD"] = "1"
    c["log"] = str(WS / f"logs/engine-r15-{name}-{k}x.log")
    c["_comment"] = c["_comment"] + f"; step 4's winners: --resident-budget-gib {budget}, STRATA_UNBUFFERED_LOAD=1"
    (WS / f"configs/r15-{name}-{k}x.json").write_text(json.dumps(c, indent=1) + "\n")
    (WS / f"configs/r15-{name}-{k}x.shared-settings.json").write_text((WS / f"configs/r15-{name}-B.shared-settings.json").read_text())
    print(f"configs/r15-{name}-{k}x.json", a[a.index("--resident-budget-gib") + 1], c["env"]["CUDA_VISIBLE_DEVICES"][:14])
if name == "q8":
    c = json.loads((WS / "configs/r15-q8-A.json").read_text())
    c["env"]["STRATA_IO_PREFETCH"] = "1"
    c["log"] = str(WS / "logs/engine-r15-q8-Ax.log")
    c["_comment"] += "; step 4's winner on A: STRATA_IO_PREFETCH=1"
    (WS / "configs/r15-q8-Ax.json").write_text(json.dumps(c, indent=1) + "\n")
    (WS / "configs/r15-q8-Ax.shared-settings.json").write_text((WS / "configs/r15-q8-A.shared-settings.json").read_text())
    print("configs/r15-q8-Ax.json + STRATA_IO_PREFETCH=1")
