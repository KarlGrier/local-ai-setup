#!/usr/bin/env python3
"""mk_q4cfg.py SINGLE_CFG KQ_EXE - round 19 B7: the UD-Q4_K_XL config for the new build, two arms.

configs/r16-q4.json (Round 16: the step-3 build's tree, the 5080 + a 66 GiB RAM budget) moved to the new build: its K-quant
engine (KQ_EXE), its server tree and its one-GPU environment (SINGLE_CFG, the launcher's fallback config: the promoted
config without the second card), plus the Q4 file's own settings as in Round 16 (STRATA_STAGE_PIN=0,
STRATA_UNBUFFERED_LOAD=1, its pack / profile / flags / port / 2 GiB chat cache) and STRATA_ROUTE_TAIL_SKIP=0 (one GPU).
Writes configs/r19-q4-b66.json (--resident-budget-gib 66, as now) and configs/r19-q4-res.json (--resident-experts in its
place: the user's addition, 2026-10-11)."""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
single, kq = json.load(open(sys.argv[1])), sys.argv[2]
q4 = json.load(open(WS / "configs/r16-q4.json"))
env = {k: v for k, v in single["env"].items() if k not in ("STRATA_DISJOINT_ADAPT",)}
env["CUDA_VISIBLE_DEVICES"] = q4["env"]["CUDA_VISIBLE_DEVICES"]          # the 5080 only
env.update({"STRATA_STAGE_PIN": "0", "STRATA_UNBUFFERED_LOAD": "1", "STRATA_ROUTE_TAIL_SKIP": "0"})
for arm in ("b66", "res"):
    c = json.loads(json.dumps(q4))
    c["exe"], c["server"], c["env"] = kq, single["server"], dict(env)
    c["log"] = str(WS / f"logs/r19/engine-q4-{arm}-new.log")
    a = c["args"]
    i = a.index("--resident-budget-gib")
    if arm == "res":
        a[i:i + 2] = ["--resident-experts"]
    c["_comment"] = (f"round 19 B7: UD-Q4_K_XL on the new build ({Path(kq).parent.name}, -DSTRATA_MMQ_KQUANTS=ON; server "
                     f"{Path(single['server']).parent.parent.name}), the one-GPU environment of {Path(sys.argv[1]).name} + "
                     "STRATA_STAGE_PIN=0, STRATA_UNBUFFERED_LOAD=1, STRATA_ROUTE_TAIL_SKIP=0; the 5080 + "
                     + ("--resident-experts (in place of the 66 GiB budget)" if arm == "res" else "a 66 GiB RAM budget")
                     + "; chat cache 2 GiB; the 6 GiB floor")
    out = WS / f"configs/r19-q4-{arm}.json"
    out.write_text(json.dumps(c, indent=1) + "\n")
    print(out, "args:", " ".join(x for x in a if not x.startswith("/")))
print("env:", json.dumps(env))
