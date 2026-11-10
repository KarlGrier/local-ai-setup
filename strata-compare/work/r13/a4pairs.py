#!/usr/bin/env python3
"""a4pairs.py --config LABEL --mode pair|seq [--engine-log LOG] — round 13 A4: LDR-shaped request PAIRS, both ready.
Pairs = consecutive requests of the LDR screen (prompts/r10/ldr-screen.json: 6 pairs). mode pair: both requests of a
pair are sent at the same instant (two client threads) and the pair completes when the later one ends; mode seq: the
two are sent one after the other (one active). Same streaming client as the screens (scripts/bench.py stream_chat);
one record per request in results/r13/a4pairs.jsonl: arm, pair, request, start / ttft / end (wall), completion and
prompt tokens, decode tok/s seen by the client. Your settings (the config's shared settings; no sampling fields)."""
import argparse
import json
import sys
import threading
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import stream_chat  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--mode", choices=["pair", "seq"], required=True)
ap.add_argument("--base", default="http://127.0.0.1:8081")
ap.add_argument("--arm", default="")
a = ap.parse_args()
reqs = json.loads((WS / "prompts/r10/ldr-screen.json").read_text(encoding="utf-8"))
pairs = [(reqs[i], reqs[i + 1]) for i in range(0, len(reqs) - 1, 2)]
OUT = WS / "results/r13/a4pairs.jsonl"
lock = threading.Lock()


def one(arm, pi, r, t_go, out):
    body = {"model": "x", "messages": r["messages"], "max_tokens": r["max_tokens"]}
    if r.get("tools"):
        body["tools"] = r["tools"]
    while time.time() < t_go:
        time.sleep(0.0005)
    t0 = time.time()
    res = stream_chat(a.base, body)
    t1 = time.time()
    rec = {"config": a.config, "arm": arm, "mode": a.mode, "pair": pi, "id": r["id"], "kind": r["kind"], "start": t0,
           "end": t1, "ttft_s": res.get("ttft_s"), "total_s": t1 - t0, "completion_tokens": res.get("completion_tokens"),
           "prompt_tokens": res.get("prompt_tokens"), "decode_tps": res.get("decode_tps"), "finish": res.get("finish_reason"),
           "error": res.get("error")}
    with lock:
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
    out.append(rec)


arm = a.arm or f"{a.config}-{a.mode}"
for pi, (x, y) in enumerate(pairs):
    got = []
    if a.mode == "pair":
        t_go = time.time() + 0.2
        th = [threading.Thread(target=one, args=(arm, pi, r, t_go, got)) for r in (x, y)]
        for t in th:
            t.start()
        for t in th:
            t.join()
    else:
        for r in (x, y):
            one(arm, pi, r, time.time(), got)
    s = min(r["start"] for r in got); e = max(r["end"] for r in got)
    toks = sum(r["completion_tokens"] or 0 for r in got)
    print(f"[{arm}] pair {pi} ({x['id']} + {y['id']}): completion {e - s:.1f} s, {toks} tokens, {toks / (e - s):.1f} tok/s total; "
          + "; ".join(f"{r['id']} {r['total_s']:.1f} s ttft {r['ttft_s'] or 0:.2f}" for r in got), flush=True)
