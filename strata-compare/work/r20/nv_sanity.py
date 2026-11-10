#!/usr/bin/env python3
"""nv_sanity.py ENDPOINT OUT_JSON - Round 20 item 2: does a freshly loaded model answer sensibly?  Five short questions
with known answers (arithmetic, a fact, code, a unit conversion, a short reasoning puzzle), your sampling (T 1.0, top-p
0.95, top-k 20, min-p 0.05), reasoning effort low (short thinking), up to 3,072 tokens each.  Prints each answer's
start, whether the expected string is in it, the finish reason and tok/s; writes everything to OUT_JSON."""
import json
import sys
import time
import urllib.request

EP, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
QS = [
    ("arith", "What is 347 * 29? Answer with the number only.", ["10063"]),
    ("fact", "What is the chemical symbol of tungsten? One word.", ["W"]),
    ("code", "Write a Python function is_prime(n) that returns True for primes. Only the code.", ["def is_prime"]),
    ("units", "How many metres are in 3.5 kilometres? Answer with the number only.", ["3500", "3,500"]),
    ("puzzle", "Alice is older than Bob. Bob is older than Carol. Who is the youngest? One name.", ["Carol"]),
]
res = []
for name, q, want in QS:
    body = {"model": "strata", "messages": [{"role": "user", "content": q}], "max_tokens": 3072, "temperature": 1.0,
            "top_p": 0.95, "top_k": 20, "min_p": 0.05, "reasoning_effort": "low", "stream": False}
    t0 = time.time()
    req = urllib.request.Request(EP + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    dt = time.time() - t0
    m = d["choices"][0]["message"]
    ans = (m.get("content") or "").strip()
    reas = m.get("reasoning_content") or m.get("reasoning") or ""
    toks = (d.get("usage") or {}).get("completion_tokens") or 0
    ok = any(w in ans for w in want)
    res.append({"name": name, "ok": ok, "answer": ans, "reasoning_chars": len(reas), "finish": d["choices"][0].get("finish_reason"),
                "completion_tokens": toks, "wall_s": round(dt, 1)})
    print(f"{name:7} {'OK ' if ok else 'BAD'} finish={d['choices'][0].get('finish_reason')} tokens={toks} {toks / dt:.0f} tok/s "
          f"reasoning={len(reas)} chars | {ans[:160]!r}", flush=True)
json.dump(res, open(OUT, "w"), indent=1)
print(f"sanity: {sum(r['ok'] for r in res)} of {len(res)} answers contain the expected string")
