#!/usr/bin/env python3
"""steady.py LABEL [--base URL] [--engine-log PATH] — round 5, phase 6: how many verify windows decode needs after a
fresh start to reach its steady speed (the adaptive expert tier moves the hot experts into VRAM as it sees them).

On a FRESH server: the long-reasoning math prompt, 6,144 tokens, three times in a row (sampled, your settings). The
first run starts with the start-up profile's expert set; the later ones start adapted. From the stream's timestamps:
decode speed per 256-token block; windows = tokens / tokens-per-window (engine DONE line of each request). Steady =
the first block from which the rolling speed stays within 5 % of the third run's median block speed."""
import argparse
import json
import re
import statistics
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
RES = WS / "results/r5/steady.jsonl"


def run(base, messages, n):
    body = {"model": "x", "messages": messages, "stream": True, "max_tokens": n}
    stamps, usage = [], {}
    t0 = time.time()
    with requests.post(f"{base}/v1/chat/completions", json=body, stream=True, timeout=3600) as r:
        for line in r.iter_lines():
            if not line.startswith(b"data: ") or line == b"data: [DONE]":
                continue
            ev = json.loads(line[6:])
            for ch in ev.get("choices", []):
                d = ch.get("delta", {})
                if d.get("content") or d.get("reasoning_content"):
                    stamps.append(time.time() - t0)
            u = ev.get("usage")
            if u:
                usage = u
    return stamps, usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--engine-log", default="")
    ap.add_argument("--tokens", type=int, default=6144)
    a = ap.parse_args()
    lr = json.load(open(WS / "prompts/longreason.json"))
    msgs = next(p for p in lr if p["id"] == "math")["messages"]
    out = []
    for k in range(3):
        off = Path(a.engine_log).stat().st_size if a.engine_log else 0
        stamps, usage = run(a.base, msgs, a.tokens)
        time.sleep(0.5)
        done = []
        if a.engine_log:
            with open(a.engine_log, "rb") as f:
                f.seek(off)
                done = re.findall(r"(\d+) generated in (\d+) ms .*?drafts accepted (\d+) of (\d+)", f.read().decode("utf-8", "replace"))
        # chunks arrive per window's tokens; a block = 256 stream chunks is roughly 256 tokens
        n = usage.get("completion_tokens", len(stamps)) if usage else len(stamps)
        per_chunk = n / max(1, len(stamps))
        blocks = []
        B = 256
        for i in range(B, len(stamps), B):
            dt = stamps[i] - stamps[i - B]
            blocks.append(round(B * per_chunk / dt, 1) if dt > 0 else None)
        gen, ms, acc, off_ = (int(x) for x in done[-1]) if done else (n, 0, 0, 0)
        tok_per_window = gen / max(1, gen - acc) if done else None
        rec = {"label": a.label, "run": k, "tokens": n, "blocks_tok_s": blocks, "tok_per_window": tok_per_window,
               "engine_tok_s": round(gen / (ms / 1000), 1) if ms else None, "time": time.strftime("%H:%M:%S")}
        out.append(rec)
        print(f"[{a.label}] run {k}: {n} tokens, engine {rec['engine_tok_s']} tok/s, {tok_per_window and round(tok_per_window, 2)} "
              f"tok/window; per 256-token block: {blocks}", flush=True)
    ref = statistics.median([b for b in out[2]["blocks_tok_s"] if b])
    first = out[0]["blocks_tok_s"]
    steady = None
    for i in range(len(first)):
        tail = [b for b in first[i:] if b]
        if tail and all(b >= 0.95 * ref for b in tail[:4]):
            steady = i
            break
    tpw = out[0]["tok_per_window"] or 2.3
    summary = {"label": a.label, "ref_tok_s": ref, "first_run_blocks": first, "steady_block": steady,
               "steady_tokens": None if steady is None else steady * 256,
               "steady_windows": None if steady is None else round(steady * 256 / tpw)}
    print(f"[{a.label}] steady-state reference (3rd run median) {ref} tok/s; the first run reaches it from block {steady} "
          f"= ~{summary['steady_tokens']} tokens = ~{summary['steady_windows']} windows", flush=True)
    RES.parent.mkdir(parents=True, exist_ok=True)
    with open(RES, "a") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
        f.write(json.dumps(summary) + "\n")


if __name__ == "__main__":
    main()
