#!/usr/bin/env python3
"""q4prompts.py LABEL ENGINE_LOG — round 9 Phase 0.4: one 8K and one 32K prompt (+64 decoded tokens) through bench.py's
Runner (records to results/runs.jsonl with the engine's own stats). The 8K prompt = the frozen 32K speed prompt's user
text cut to its first quarter (the frozen set has no 8K item); the 32K = speed 32k rep 0."""
import argparse, copy, json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); sys.path.insert(0, str(WS / "scripts"))
import bench
L, elog = sys.argv[1], sys.argv[2]
a = argparse.Namespace(model="x", base="http://127.0.0.1:8081", engine_log=elog, config=L, session=L, extra="", max_tokens=64)
r = bench.Runner(a)
p32 = next(p for p in bench.load("speed") if p["size"] == "32k" and p["rep"] == 0)
m8 = copy.deepcopy(p32["messages"])
u = m8[-1]; u["content"] = u["content"][: len(u["content"]) // 4]
r.call("speed", "8k", 0, m8, 64)
# the frozen 32K item is 32,769 tokens: with 64 new tokens it does not fit a 32,768 context, so its text is cut to 97 %
m32 = copy.deepcopy(p32["messages"])
u = m32[-1]; u["content"] = u["content"][: int(len(u["content"]) * 0.97)]
r.call("speed", "32k-cut", 0, m32, 64)
