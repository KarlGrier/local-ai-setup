#!/usr/bin/env python3
"""chunks693.py BASE LABEL SIZES [REPS] - round 11 D.1: prompts of exact token counts around the prompt chunk's
boundaries (just below / above the chunk, a tail just under / over stream_all_min, two and three chunks), each a
different stretch of Round 10's LDR trace pool (work/r10/ldr/corpus/T: fetched web pages, never a holdout), with a
unique first line so nothing is reused. The size is set with the server's own count (/v1/messages/count_tokens,
the template included). Per prompt: client TTFT, then 256 decoded tokens (the decode right after the prompt), and
the engine's prompt line (tokens, read time, chunks). One JSON line each to results/r11/chunks693-LABEL.jsonl.
SIZES: comma list of token counts; REPS: repetitions of each (default 2)."""
import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
SIZES = [int(x) for x in sys.argv[3].split(",")]
REPS = int(sys.argv[4]) if len(sys.argv) > 4 else 2
ELOG = sys.argv[5] if len(sys.argv) > 5 else None


def post(path, body, stream=False):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=900)


def count(text):
    with post("/v1/messages/count_tokens", {"model": "x", "max_tokens": 1, "messages": [{"role": "user", "content": text}]}) as r:
        return json.loads(r.read())["input_tokens"]


# the pool's page texts, topic by topic, one long stream
pool = []
for f in sorted((WS / "work/r10/ldr/corpus/T").glob("*.json")):
    d = json.loads(f.read_text())
    pool += [p.get("text", "") for p in d.get("pages", []) if p.get("text")]
STREAM = "\n\n".join(pool)
ASK = "\n\nSummarize the sources above in three sentences."
cursor = 0


def prompt_of(target):
    """A prompt of `target` tokens (template included) from the next stretch of the stream."""
    global cursor
    head = f"[{LABEL} {target} {uuid.uuid4().hex[:12]}]\n"
    lo, hi = 1000, 12 * target            # characters
    best = None
    for _ in range(40):
        mid = (lo + hi) // 2
        body = STREAM[cursor:cursor + mid]
        if len(body) < mid:               # wrap around the pool
            cursor = 0
            continue
        n = count(head + body + ASK)
        if n == target:
            best = (head + body + ASK, n, mid)
            break
        if n < target:
            lo = mid + 1
        else:
            hi = mid - 1
        best = (head + body + ASK, n, mid) if best is None or abs(n - target) < abs(best[1] - target) else best
        if lo > hi:
            break
    text, n, used = best
    cursor += used
    return text, n


def engine_prompt_line(after):
    if not ELOG:
        return None
    lines = Path(ELOG).read_text(errors="replace").splitlines()[after:]
    for l in lines:
        if "strata serve: prompt " in l and " read in " in l:
            return l.split("strata serve: ", 1)[1][:200]
    return None


out = (WS / f"results/r11/chunks693-{LABEL}.jsonl").open("a")
for rep in range(REPS):
    for target in SIZES:
        text, n = prompt_of(target)
        mark = len(Path(ELOG).read_text(errors="replace").splitlines()) if ELOG else 0
        body = {"model": "x", "stream": True, "max_tokens": 256, "messages": [{"role": "user", "content": text}]}
        t0 = time.time()
        ttft, ntok = None, 0
        with post("/v1/chat/completions", body) as r:
            for raw in r:
                line = raw.decode(errors="replace").strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                d = json.loads(line[6:])
                delta = (d.get("choices") or [{}])[0].get("delta", {})
                if (delta.get("content") or delta.get("reasoning_content")) and ttft is None:
                    ttft = time.time() - t0
        total = time.time() - t0
        time.sleep(0.5)
        eng = engine_prompt_line(mark)
        m = re.search(r"read in (\d+) ms", eng or "")
        g = re.search(r"(\d+) generated in (\d+) ms", eng or "")
        rec = {"label": LABEL, "rep": rep, "target": target, "tokens": n, "ttft_s": round(ttft or -1, 3),
               "total_s": round(total, 2), "read_ms": int(m.group(1)) if m else None,
               "decode_tps": round(int(g.group(1)) / (int(g.group(2)) / 1000.0), 1) if g and int(g.group(2)) else None,
               "engine": eng}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(f"[{LABEL}] {target} ({n} tok) rep {rep}: ttft {rec['ttft_s']} s, read {rec['read_ms']} ms, decode {rec['decode_tps']} tok/s | {eng}", flush=True)
