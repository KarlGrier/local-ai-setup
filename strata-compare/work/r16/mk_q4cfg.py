#!/usr/bin/env python3
"""mk_q4cfg.py NAME BUDGET_GIB [unbuffered] — round 16 Q4 check: configs/NAME.json = the step-3 build's config
(configs/Cstar16.json: C*15's flags, the CPU-share setting step 1 chose) moved to UD-Q4_K_XL on the 5080 alone: the
Q4 pack (bringup/out/r16q4/pack, --compat-bf16) and shards, the K-quant build of the same tree (r16q4's engine-patched,
-DSTRATA_MMQ_KQUANTS=ON), --resident-budget-gib BUDGET (a budget is refused beside the helper cache), the budget's
+100 MiB VRAM reserve (813, Rehearsal B), your 2 GiB chat cache, STRATA_STAGE_PIN=0 (kept off), no helper, no
STRATA_DISJOINT_ADAPT (a helper switch); 'unbuffered' adds STRATA_UNBUFFERED_LOAD=1 (only if experts come from the SSD)."""
import json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); R = WS / "bringup/out/r16q4"
name, budget = sys.argv[1], sys.argv[2]; unbuf = len(sys.argv) > 3 and sys.argv[3] == "unbuffered"
c = json.loads((WS / "configs/Cstar16.json").read_text()); a = c["args"]
ins = json.loads((R / "inspect.json").read_text())
def setarg(f, v):
    if f in a: a[a.index(f) + 1] = v
    else: a.extend([f, v])
def droparg(f):
    if f in a: i = a.index(f); del a[i:i + 2]
setarg("--pack", str(R / "pack")); setarg("--native", ins["file"][0]); setarg("--ple-gguf", ins["ple_shard"])
setarg("--expert-profile", str(R / "strata-patched/data/expert-profile.bin"))
droparg("--expert-cache-device1"); setarg("--resident-budget-gib", budget); setarg("--vram-reserve-mib", "813")
setarg("--chat-cache-mib", "2048")
c["env"]["CUDA_VISIBLE_DEVICES"] = c["env"]["CUDA_VISIBLE_DEVICES"].split(",")[0]
c["env"].pop("STRATA_DISJOINT_ADAPT", None); c["env"]["STRATA_STAGE_PIN"] = "0"
if unbuf: c["env"]["STRATA_UNBUFFERED_LOAD"] = "1"
else: c["env"].pop("STRATA_UNBUFFERED_LOAD", None)
c.update(exe=str(R / "engine-patched/strata"), cwd=str(R), tokenizer=str(R / "pack/tokenizer"),
         log=str(WS / f"logs/engine-{name}.log"), fallback=None, model_name="strata-qwen3.8-flash-next-ud-q4kxl")
c["_comment"] = (f"round 16 Q4 check (not promoted): UD-Q4_K_XL on the step-3 build's tree (v0.1.41 + patches/r16p27, built "
                 f"with -DSTRATA_MMQ_KQUANTS=ON), the 5080 + a {budget} GiB RAM budget, chat cache 2 GiB, your 6 GiB floor; "
                 f"STRATA_STAGE_PIN=0{'; STRATA_UNBUFFERED_LOAD=1 (experts from the SSD)' if unbuf else ''}; flags and CPU-share "
                 "setting = configs/Cstar16.json's")
(WS / f"configs/{name}.json").write_text(json.dumps(c, indent=1) + "\n")
(WS / f"configs/{name}.shared-settings.json").write_text((WS / "configs/Cstar16.shared-settings.json").read_text())
print(f"configs/{name}.json: budget {budget} GiB, unbuffered {unbuf}, env {c['env']}")
