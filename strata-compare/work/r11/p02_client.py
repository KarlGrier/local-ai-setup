#!/usr/bin/env python3
"""p02_client.py MODE [BASE] — round 10 Phase 0.2: one decode-heavy request at your settings (T 1.0, top-p 0.95, top-k 20,
min-p 0.05, effort high = xhigh) for the served profile.  MODE: math / code (the long-reasoning items, 1,200 tokens) or
ldr (the aging pool's first synthesis request, ~24K-token prompt, 1,500 tokens; never a screen or holdout prompt)."""
import json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); sys.path.insert(0, str(WS / "scripts"))
from client import stream_chat
mode = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8081"
if mode in ("math", "code"):
    msgs = {p["id"]: p for p in json.load(open(WS / "prompts/longreason.json"))}[mode]["messages"]
else:
    pool = json.load(open(WS / "prompts/r10/ldr-pool.json"))
    msgs = next(r for r in pool if r["kind"] == "synthesis")["messages"]
body = {"model": "x", "max_tokens": 1500 if mode == "ldr" else 1200, "messages": msgs, "reasoning_effort": "high",
        "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
r = stream_chat(base, body)
print(f"p02 {mode}: prompt {r.get('prompt_tokens')} gen {r.get('completion_tokens')} at "
      f"{r.get('decode_tps') and round(r['decode_tps'], 1)} tok/s, ttft {r.get('ttft_s') and round(r['ttft_s'], 2)} s, "
      f"error {r.get('error')}")
