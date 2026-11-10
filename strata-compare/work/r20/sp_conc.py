#!/usr/bin/env python3
"""sp_conc.py BASE N TEMP CASES WORKERS - 2026-10-14 D: the near-tie sampling probe (bringup/lib/sampling_probe.py
`strata`), with WORKERS requests in flight at once, so that on a server with --batch slots the tie is drawn in a batch
slot (WORKERS 1 = one at a time = the solo path with our exact speculative sampling).  Same requests and the same
output file format (SP_DIR / sp-strata-<SP_LABEL>.jsonl), so `sampling_probe.py analyze own` reads it as before."""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
import sampling_probe as SP  # noqa: E402

base, n, temp, only, workers = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4].split(","), int(sys.argv[5])
cases = [c for c in json.loads(SP.CASES.read_text()) if c["case"] in only]
prompts = {p["id"]: p["messages"] for p in json.loads((SP.WS / "prompts/correctness.json").read_text())}
lock = threading.Lock()
with open(SP.STRATA, "a") as f:
    for c in cases:
        todo = list(range(n))
        t0 = time.time()
        done = [0]

        def work():
            while True:
                with lock:
                    if not todo:
                        return
                    todo.pop()
                r = SP.post(base, "/v1/chat/completions", {**SP.PAGE, "temperature": temp, "messages": prompts[c["item"]],
                                                           "strata_prefix_ids": c["prefix"], "max_tokens": c["j"] + 1,
                                                           "strata_return_ids": True})
                with lock:
                    f.write(json.dumps({"case": c["case"], "temp": temp, "ids": r.get("strata_ids"), "workers": workers}) + "\n")
                    done[0] += 1
                    if done[0] % 250 == 0:
                        f.flush()
                        print(f"  {c['case']} T={temp} x{workers}: {done[0]} samples, {(time.time() - t0) / done[0]:.3f} s each",
                              flush=True)

        ths = [threading.Thread(target=work) for _ in range(workers)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
