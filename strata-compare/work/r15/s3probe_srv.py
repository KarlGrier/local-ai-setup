#!/usr/bin/env python3
"""s3probe_srv.py LABEL ENGINE_LOG [BASE] — round 15 step 3: the probe of a placement the engine runs only under --serve
(the layer split): on a running guarded server, the math prompt (prompts/longreason.json "math", with the CLI probe's
system line) greedy (temperature 0), 1,024 tokens: a warm-up, then up to 4 probes until two consecutive ones agree
(decode within 3 %, your rule), then the 32K speed prompt with 64 tokens. Numbers from the engine's per-request lines
(the prompt / generated line, the expert-cache hit rate, the decode timing). Writes results/r15/s3/LABEL-probe.txt."""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
L, ELOG = sys.argv[1], Path(sys.argv[2])
BASE = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8081"
OUT = WS / f"results/r15/s3/{L}-probe.txt"
SYS = ("Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider "
       "plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer.")
math = [i for i in json.loads((WS / "prompts/longreason.json").read_text()) if i["id"] == "math"][0]["messages"]
k32 = [p for p in json.loads((WS / "prompts/speed.json").read_text()) if p["size"] == "32k" and p["rep"] == 0][0]["messages"]
LINE = re.compile(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms \(([\d.]+) tok/s\), "
                  r"(\d+) generated in ([\d.]+) ms \(([\d.]+) tok/s\), drafts accepted (\d+) of (\d+)")
HIT = re.compile(r"decode expert cache hit rate: ([\d.]+)% \((\d+) hits / (\d+) lookups\)(?:; (\d+) more read)?")


def ask(messages, n):
    off = ELOG.stat().st_size
    body = json.dumps({"model": "x", "messages": messages, "max_tokens": n, "temperature": 0, "stream": False}).encode()
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(BASE + "/v1/chat/completions", body,
                                                       {"Content-Type": "application/json"}), timeout=3600) as r:
        d = json.loads(r.read())
    wall = time.time() - t0
    time.sleep(1.0)
    with open(ELOG, "rb") as f:
        f.seek(off)
        t = f.read().decode("utf-8", "replace")
    m = list(LINE.finditer(t))
    h = list(HIT.finditer(t))
    if not m:
        return {"wall": wall, "err": "no engine line"}
    g = m[-1].groups()
    rounds = int(g[5]) - int(g[8])
    r = {"wall": wall, "prompt": int(g[0]), "prompt_ms": float(g[3]), "gen": int(g[5]), "dec_ms": float(g[6]),
         "tps": float(g[7]), "acc": int(g[8]) / max(1, int(g[9])), "tpr": int(g[5]) / max(1, rounds),
         "ms_round": float(g[6]) / max(1, rounds), "text": d["choices"][0]["message"].get("content") or ""}
    if h:
        x = h[-1].groups()
        tot = int(x[2]) + int(x[3] or 0)
        r["share5080"] = int(x[1]) / tot if tot else None
        r["share_card2"] = int(x[3] or 0) / tot if tot else None
    return r


with open(OUT, "a") as o:
    def say(s):
        print(s, flush=True)
        o.write(s + "\n")
    w = ask([{"role": "system", "content": SYS}] + math, 1024)
    say(f"started (served; warm-up: decode {w.get('tps', 0):.2f} tok/s over {w.get('gen')} tokens)")
    prev, agreed = None, None
    for k in range(1, 5):
        r = ask([{"role": "system", "content": SYS}] + math, 1024)
        say(f"probe {k}: decode {r.get('tps', 0):.2f} tok/s, {r.get('ms_round', 0):.1f} ms/round, {r.get('tpr', 0):.2f} tokens/round, "
            f"acceptance {r.get('acc', 0):.3f}, 5080 share {r.get('share5080')}, 4060 Ti share {r.get('share_card2')}")
        (WS / f"results/r15/s3/{L}-probe-{k}.json").write_text(json.dumps(r))
        if prev and abs(r["tps"] / prev["tps"] - 1) <= 0.03:
            agreed = (k - 1, k)
            say(f"  {k - 1} vs {k}: AGREE: decode {prev['tps']:.2f} vs {r['tps']:.2f} tok/s (within 3 %)")
            break
        if prev:
            say(f"  {k - 1} vs {k}: DIFFER: decode {prev['tps']:.2f} vs {r['tps']:.2f} tok/s")
        prev = r
    say(f"AGREED {agreed[0]} {agreed[1]}" if agreed else "AGREED none (4 probes; the last two are reported)")
    r = ask(k32, 64)
    say(f"32K: prompt {r.get('prompt')} tokens read in {r.get('prompt_ms', 0) / 1000:.1f} s (served), decode {r.get('tps', 0):.2f} tok/s")
