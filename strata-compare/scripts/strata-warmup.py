#!/usr/bin/env python3
"""warmup.py [BASE] — read one full prompt chunk right after the server starts: ~9,500 tokens (one full 8,192-token chunk and
a remainder), 1 output token, no thinking. The prompt path's kernels load and its GPU memory pool (ggml's MMQ buffers)
is allocated now, while the VRAM is surely free - not in the middle of your first long prompt, when another program may
have taken it (round 5: the engine then stopped with "out of memory: cudaMalloc"). Takes ~4 s."""
import json
import sys
import time
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
words = ("The warm-up reads this filler once so the prompt path is ready. " * 1000)[:44000]
body = {"model": "x", "stream": False, "max_tokens": 1, "reasoning_effort": "none",
        "messages": [{"role": "user", "content": f"[warm-up {time.time():.0f}] {words}\n\nReply with OK."}]}
t0 = time.time()
req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=300) as r:
    d = json.loads(r.read())
print(f"warm-up: {d['usage']['prompt_tokens']} prompt tokens in {time.time() - t0:.1f} s", flush=True)
