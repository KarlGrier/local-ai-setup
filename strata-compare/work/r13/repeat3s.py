#!/usr/bin/env python3
"""repeat3s.py LABEL — round 10 Phase A (b) gate for serve-only changes (A.3): one sampled request with a fixed seed
(seed 11, your T / top-p / top-k / min-p, effort high; the long-reasoning math item, 1,024 tokens) on the running server
(127.0.0.1:8081); prints a hash of the reasoning + answer text and appends it to results/r13/repeat3s-LABEL.txt.  Run on
three fresh servers: the three hashes must be equal."""
import hashlib, json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); sys.path.insert(0, str(WS / "scripts"))
from client import stream_chat
L = sys.argv[1]
msgs = {p["id"]: p for p in json.load(open(WS / "prompts/longreason.json"))}["math"]["messages"]
import os   # R3S_TEMP: another temperature (0 = greedy) for the 00:30 served-repeatability diagnosis
r = stream_chat("http://127.0.0.1:8081", {"model": "x", "messages": msgs, "max_tokens": 1024, "seed": 11,
                                          "temperature": float(os.environ.get("R3S_TEMP", "1.0")),
                                          "top_p": 0.95, "top_k": 20, "min_p": 0.05, "reasoning_effort": "high"})
h = hashlib.sha256(((r.get("reasoning") or "") + "\x00" + (r.get("content") or "")).encode()).hexdigest()[:16]
print(f"repeat3s {L}: {h} ({r.get('completion_tokens')} tokens, {r.get('decode_tps') and round(r['decode_tps'], 1)} tok/s)")
with open(WS / f"results/r13/repeat3s-{L}.txt", "a") as f:
    f.write(h + "\n")
