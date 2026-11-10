#!/usr/bin/env python3
"""a1_client.py MODE [--base URL] — round 9 Phase 0.5 (copy of round 8 A.1): one decode-heavy request for the served nsys trace (the server runs the
trace engine under nsys; the capture range is served windows 150-269). MODE sampled = your settings (T 1.0, top-p 0.95,
top-k 20, min-p 0.05, effort high), greedy = temperature 0. Prompt: the long-reasoning math item, 1,200 tokens."""
import json, sys, time
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); sys.path.insert(0, str(WS / "scripts"))
from client import stream_chat
mode = sys.argv[1]; base = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8081"
lr = {p["id"]: p for p in json.load(open(WS / "prompts/longreason.json"))}
body = {"model": "x", "max_tokens": 1200, "messages": lr["math"]["messages"], "reasoning_effort": "high", "seed": 7}
body.update({"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05} if mode == "sampled" else {"temperature": 0.0})
r = stream_chat(base, body)
print(f"a1 {mode}: gen {r.get('completion_tokens')} at {r.get('decode_tps') and round(r['decode_tps'], 1)} tok/s, error {r.get('error')}")
