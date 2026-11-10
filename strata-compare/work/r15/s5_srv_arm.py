#!/usr/bin/env python3
"""s5_srv_arm.py LABEL ENGINE_LOG — one arm of work/r15/s5_srv.sh on a running server (127.0.0.1:8081): a warm-up and two
requests of the math prompt (prompts/longreason.json "math" with the CLI probes' system line) at the server's sampling
(your shared settings: no sampling fields sent), 1,024 tokens; decode = the engine's generated / decode time of the two.
Writes results/r15/s5/LABEL.json."""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
L, ELOG = sys.argv[1], Path(sys.argv[2])
SYS = ("Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider "
       "plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer.")
math = [i for i in json.loads((WS / "prompts/longreason.json").read_text()) if i["id"] == "math"][0]["messages"]
LINE = re.compile(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms \(([\d.]+) tok/s\), "
                  r"(\d+) generated in ([\d.]+) ms \(([\d.]+) tok/s\), drafts accepted (\d+) of (\d+)")


def ask():
    off = ELOG.stat().st_size
    body = json.dumps({"model": "x", "messages": [{"role": "system", "content": SYS}] + math, "max_tokens": 1024,
                       "stream": False}).encode()
    with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions", body,
                                                       {"Content-Type": "application/json"}), timeout=3600) as r:
        r.read()
    time.sleep(1.0)
    with open(ELOG, "rb") as f:
        f.seek(off)
        m = list(LINE.finditer(f.read().decode("utf-8", "replace")))
    g = m[-1].groups()
    return int(g[5]), float(g[6]), int(g[8]), int(g[9])


def ask32k():
    """the 32K speed prompt with 64 tokens: the prompt read (your rule for C's split point / chunk size)"""
    import os  # noqa
    k32 = [p for p in json.loads((WS / "prompts/speed.json").read_text()) if p["size"] == "32k" and p["rep"] == 0][0]["messages"]
    off = ELOG.stat().st_size
    body = json.dumps({"model": "x", "messages": k32, "max_tokens": 64, "stream": False}).encode()
    with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions", body,
                                                       {"Content-Type": "application/json"}), timeout=3600) as r:
        r.read()
    time.sleep(1.0)
    with open(ELOG, "rb") as f:
        f.seek(off)
        m = list(LINE.finditer(f.read().decode("utf-8", "replace")))
    return float(m[-1].groups()[3])


ask()   # warm-up
runs = [ask(), ask()]
gen = sum(r[0] for r in runs); ms = sum(r[1] for r in runs)
out = {"tps": gen / (ms / 1000), "each": [r[0] / (r[1] / 1000) for r in runs],
       "acc": sum(r[2] for r in runs) / max(1, sum(r[3] for r in runs))}
import os
if os.environ.get("S5_PROMPT") == "1":
    out["prompt_ms"] = ask32k()
# what the engine really ran at this start (the last start in the log): the prompt chunk and the split's stages
t = ELOG.read_text(errors="replace"); t = t[t.rfind("engine started"):]
mc = re.findall(r"prompt chunk auto: (\d+) tokens|prompt chunk \d+ -> (\d+) tokens", t)
out["chunk"] = int(next(x for x in mc[-1] if x)) if mc else None
ms_ = re.findall(r"layer split: layers ([0-9,() A-Z-]+), one hand-off", t)
out["split"] = ms_[-1].strip() if ms_ else None
(WS / f"results/r15/s5/{L}.json").write_text(json.dumps(out))
print(f"{L}: {out['tps']:.2f} tok/s ({' / '.join(f'{x:.2f}' for x in out['each'])}), acceptance {out['acc']:.3f}, "
      f"chunk {out['chunk']}, split {out['split']}" + (f", 32K read {out['prompt_ms'] / 1000:.1f} s" if "prompt_ms" in out else ""))
