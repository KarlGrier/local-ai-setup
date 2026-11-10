#!/usr/bin/env python3
"""out_hash.py BASE LABEL OUT.json - round 19 step 2: fixed requests whose outputs must not depend on a switch that is
lossless or inert: two greedy (temperature 0) and two seeded sampled (seed 11, the config's other settings) answers of
1,024 tokens to a math and a code prompt. Writes the sha256 (12 hex) of each answer's reasoning + text and the engine's
timings."""
import hashlib, json, sys, urllib.request
base, label, out = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
P = {"math": "Derive, step by step, a closed form for the sum of the first n cubes and prove it by induction. Then use it to compute the sum for n = 2026.",
     "code": "Write a Python module that parses a CSV file of timestamped sensor readings, resamples them to one-minute buckets with linear interpolation, and reports gaps longer than five minutes. Include tests."}
res = []
for mode in ("greedy", "seeded"):
    for k, p in P.items():
        req = {"model": "x", "messages": [{"role": "user", "content": p}], "max_tokens": 1024}
        req.update({"temperature": 0} if mode == "greedy" else {"seed": 11})
        r = json.load(urllib.request.urlopen(urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(req).encode(),
                                                                   headers={"Content-Type": "application/json"}), timeout=900))
        m = r["choices"][0]["message"]; txt = (m.get("reasoning_content") or "") + "\x00" + (m.get("content") or "")
        h = hashlib.sha256(txt.encode()).hexdigest()[:12]; t = r.get("timings", {})
        res.append({"item": f"{mode}-{k}", "hash": h, "tokens": t.get("predicted_n"), "tps": t.get("predicted_per_second")})
        print(f"{label} {mode}-{k}: {h} {t.get('predicted_n')} tokens {t.get('predicted_per_second')} tok/s", flush=True)
json.dump({"label": label, "runs": res}, open(out, "w"), indent=1)
