#!/usr/bin/env python3
"""idcheck_client.py BASE OUTDIR - 10-26: the same two seeded requests on a fresh engine (seed 4242, max_tokens 1024, the
config's sampling), the full text of each (thinking + answer) -> OUTDIR/idcheck.json. Run on two builds with the same
settings and a fresh copy of the pinned profile: identical texts = the build serves as the other does (a fresh engine's
seeded requests repeat exactly, 10-26 repeat pairs)."""
import json
import sys
import urllib.request

PROMPTS = ["Write a Python function that returns the n-th Fibonacci number iteratively, with a one-line docstring.",
           "Explain in three sentences why the Moon shows phases."]


def main():
    base, out = sys.argv[1].rstrip("/"), sys.argv[2]
    res = []
    for p in PROMPTS:
        body = {"model": "x", "messages": [{"role": "user", "content": p}], "max_tokens": 1024, "seed": 4242, "stream": False}
        req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            d = json.loads(r.read())
        m = d["choices"][0]["message"]
        res.append({"prompt": p, "text": (m.get("reasoning_content") or m.get("reasoning") or "") + "\n</think>\n" + (m.get("content") or ""),
                    "completion_tokens": (d.get("usage") or {}).get("completion_tokens"), "finish": d["choices"][0].get("finish_reason")})
        print(f"idcheck: {res[-1]['completion_tokens']} tokens, finish {res[-1]['finish']}", flush=True)
    json.dump(res, open(f"{out}/idcheck.json", "w"), indent=1)


if __name__ == "__main__":
    main()
