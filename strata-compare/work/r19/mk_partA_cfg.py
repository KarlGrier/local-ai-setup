#!/usr/bin/env python3
"""mk_partA_cfg.py - round 19 Part A: Round 17's configs (work/r17/cfg) moved to stock v0.1.42, STRATA_ROUTE_TAIL_SKIP=0
on every one (one GPU; so the numbers compare with the issues' v0.1.41 ones), nothing else changed.
  q8B-v42      #1682: the Q8_0 stand-in, the 5080 + --resident-budget-gib 64 (CLI), STRATA_IO_THREADS removed (the
               default); the runs add STRATA_IO_THREADS=16 / 64 and STRATA_UNBUFFERED_LOAD=1 through ENVX
  q4-b66-v42, q4-b72-v42, q4-res-v42   #1683: UD-Q4_K_XL, the 5080 + --resident-budget-gib 66 / 72 (STRATA_UNBUFFERED_LOAD=1,
               as in the issue) and --resident-experts"""
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); R17 = WS / "work/r17/cfg"; OUT = WS / "work/r19/cfg"
STOCK = WS / "tmp/r18/v42-main"          # stock v0.1.42 (61b3fb5d), Round 18's build (no K-quant kernels)
KQ = WS / "tmp/r19/v42-kq"               # stock v0.1.42 with -DSTRATA_MMQ_KQUANTS=ON (the Q4 file)


def put(name, c, src):
    c["log"] = str(WS / f"logs/r19/engine-{name}.log"); c["fallback"] = None
    (OUT / f"{name}.json").write_text(json.dumps(c, indent=1) + "\n")
    (OUT / f"{name}.shared-settings.json").write_text((R17 / f"{src}.shared-settings.json").read_text())
    print(name, c["exe"], " ".join(c["args"][-4:]), {k: v for k, v in c["env"].items() if k.startswith("STRATA_I") or "TAIL" in k or "UNBUF" in k})


c = json.loads((R17 / "q8B-stock41.json").read_text())
c["exe"] = str(STOCK / "build/strata"); c["server"] = str(STOCK / "serve/server.py")
a = c["args"]; a[a.index("--expert-profile") + 1] = str(STOCK / "data/expert-profile.bin")
c["env"].pop("STRATA_IO_THREADS"); c["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"
c["_comment"] = "r19 #1682: Q8_0 stand-in, the 5080 + --resident-budget-gib 64, stock v0.1.42, STRATA_ROUTE_TAIL_SKIP=0, STRATA_IO_THREADS unset"
put("q8B-v42", c, "q8B-stock41")
for name, src, budget in (("q4-b66-v42", "q4-budget", "66"), ("q4-b72-v42", "q4-budget", "72"), ("q4-res-v42", "q4-resident", None)):
    c = json.loads((R17 / f"{src}.json").read_text())
    c["exe"] = str(WS / "tmp/r19/engine-v42-kq/strata"); c["server"] = str(KQ / "serve/server.py")
    a = c["args"]
    if budget: a[a.index("--resident-budget-gib") + 1] = budget
    c["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"
    c["_comment"] = f"r19 #1683: UD-Q4_K_XL, stock v0.1.42 (K-quant build), the 5080 + " + (f"--resident-budget-gib {budget}" if budget else "--resident-experts") + ", STRATA_ROUTE_TAIL_SKIP=0, otherwise as r17's " + src
    put(name, c, src)
