#!/usr/bin/env python3
"""greedy_req.py BASE N - round 18: N greedy requests (temperature 0, 1,024 tokens, no thinking budget change) of two fixed
prompts (a math derivation, a code task) for the engine's per-request decode timing / GPU stage lines."""
import json, sys, urllib.request
base, n = sys.argv[1].rstrip("/"), int(sys.argv[2])
P = ["Derive, step by step, a closed form for the sum of the first n cubes and prove it by induction. Then use it to compute the sum for n = 2026.",
     "Write a Python module that parses a CSV file of timestamped sensor readings, resamples them to one-minute buckets with linear interpolation, and reports gaps longer than five minutes. Include tests."]
for i in range(n):
    for p in P:
        body = json.dumps({"model": "x", "messages": [{"role": "user", "content": p}], "max_tokens": 1024, "temperature": 0}).encode()
        r = json.load(urllib.request.urlopen(urllib.request.Request(base + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"}), timeout=600))
        t = r.get("timings", {})
        print(f"req {i} {p[:20]!r}: {t.get('predicted_n')} tokens at {t.get('predicted_per_second')} tok/s", flush=True)
