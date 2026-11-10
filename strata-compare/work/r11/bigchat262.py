#!/usr/bin/env python3
"""bigchat262.py BASE LABEL [TOKENS] [ENGINE_LOG] - round 11 D.2: the chat cache with very large chats. Three different
chats of ~TOKENS tokens each (default 190,000; Round 10's LDR trace pool, a unique first line each), one short answer
each, then a follow-up turn in the FIRST chat: with --chat-cache it should be restored from RAM (reused ~ its whole
prompt) instead of read again. Prints per turn the client TTFT, the engine's prompt line and the chat-cache lines, and
appends JSON lines to results/r11/bigchat262-LABEL.jsonl."""
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
TOKENS = int(sys.argv[3]) if len(sys.argv) > 3 else 190000
ELOG = sys.argv[4] if len(sys.argv) > 4 else None


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=1800)


def count(messages):
    with post("/v1/messages/count_tokens", {"model": "x", "max_tokens": 1, "messages": messages}) as r:
        return json.loads(r.read())["input_tokens"]


pool = []
for f in sorted((WS / "work/r10/ldr/corpus/T").glob("*.json")):
    pool += [p["text"] for p in json.loads(f.read_text()).get("pages", []) if p.get("text")]
STREAM = "\n\n".join(pool)


def chat_text(k):
    """A user message of ~TOKENS tokens from stretch k of the pool."""
    head = f"[{LABEL} chat {k} {uuid.uuid4().hex[:10]}]\n"
    ask = "\n\nWhat are the three main disagreements between these sources? Answer in two sentences."
    start = (k * len(STREAM)) // 3
    lo, hi = 10000, 6 * TOKENS
    best = None
    for _ in range(30):
        mid = (lo + hi) // 2
        body = (STREAM[start:] + "\n\n" + STREAM)[:mid]
        n = count([{"role": "user", "content": head + body + ask}])
        best = (head + body + ask, n)
        if abs(n - TOKENS) <= 256:
            break
        if n < TOKENS:
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def log_mark():
    return len(Path(ELOG).read_text(errors="replace").splitlines()) if ELOG else 0


def log_since(mark, keys=("strata serve: prompt", "chat cache")):
    if not ELOG:
        return []
    return [l.split("strata serve: ", 1)[-1][:220] for l in Path(ELOG).read_text(errors="replace").splitlines()[mark:]
            if any(k in l for k in keys)]


def turn(messages, tag):
    mark = log_mark()
    t0 = time.time()
    ttft, text = None, []
    with post("/v1/chat/completions", {"model": "x", "stream": True, "max_tokens": 200, "messages": messages}) as r:
        for raw in r:
            line = raw.decode(errors="replace").strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            d = (json.loads(line[6:]).get("choices") or [{}])[0].get("delta", {})
            if d.get("content"):
                text.append(d["content"])
            if (d.get("content") or d.get("reasoning_content")) and ttft is None:
                ttft = time.time() - t0
    time.sleep(0.5)
    rec = {"label": LABEL, "turn": tag, "ttft_s": round(ttft or -1, 2), "total_s": round(time.time() - t0, 1),
           "engine": log_since(mark)}
    with (WS / f"results/r11/bigchat262-{LABEL}.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[{LABEL}] {tag}: ttft {rec['ttft_s']} s, total {rec['total_s']} s | " + " | ".join(rec["engine"]), flush=True)
    return "".join(text)


chats = []
for k in range(3):
    text, n = chat_text(k)
    msgs = [{"role": "user", "content": text}]
    print(f"[{LABEL}] chat {k}: {n} tokens", flush=True)
    answer = turn(msgs, f"chat{k} first turn ({n} tok)")
    chats.append(msgs + [{"role": "assistant", "content": answer}])
follow = chats[0] + [{"role": "user", "content": "Which of the sources is the most recent? One sentence."}]
turn(follow, "chat0 follow-up (after chats 1 and 2)")
