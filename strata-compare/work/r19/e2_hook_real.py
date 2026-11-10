#!/usr/bin/env python3
"""e2_hook_real.py BASE REQUEST.json N OUT.jsonl - #2028 follow-up (2026-10-12): the exact request (REQUEST.json, parsed from
the reply draft) N times through a live server, one line per response: strata_ids, finish_reason, usage."""
import json
import sys
import time
import urllib.request
from pathlib import Path

base, body, n, out = sys.argv[1], json.loads(Path(sys.argv[2]).read_text()), int(sys.argv[3]), Path(sys.argv[4])
t0 = time.time()
with out.open("w") as f:
    for k in range(n):
        req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read())
        f.write(json.dumps({"ids": resp.get("strata_ids"), "finish": resp["choices"][0].get("finish_reason"),
                            "usage": resp.get("usage")}) + "\n")
print(f"{n} requests in {time.time() - t0:.0f} s")
