#!/usr/bin/env python3
"""ttft567.py BASE LABEL — round 11 Phase 0.4, part 2: time to first token on CACHED turns of a 32K and a 100K chat.
Each chat starts with one long user message (frozen web pages of Round 10's aging-pool corpus, work/r10/ldr/corpus/T —
not a holdout) and a short answer; then 6 follow-up turns, each sending the whole history back (as a chat client does)
plus a short new question, streamed, no thinking, max_tokens 32.  The engine reuses the conversation, so a follow-up's
TTFT is the server's prompt handling (template + tokenization) + the few new tokens read.  Client-side TTFT (request
sent -> first content byte) and the server's prompt_ms / reused are recorded.  Records: results/r13/ttft567-LABEL.jsonl."""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from common import load_tokenizer  # noqa: E402

TOK = load_tokenizer()
pages = []
for f in sorted((WS / "work/r10/ldr/corpus/T").glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    pages += [p["text"] for p in d["pages"] if p.get("text") and len(p["text"]) > 1500]


def doc(target):
    out, n = [], 0
    for p in pages:
        k = len(TOK.encode(p))
        if n + k > target:
            break
        out.append(p)
        n += k
    return "\n\n---\n\n".join(out), n


def stream(messages, max_tokens=32):
    body = {"model": "x", "stream": True, "reasoning_effort": "none", "max_tokens": max_tokens, "messages": messages}
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    ttft, text = None, []
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() in ("", "[DONE]"):
                continue
            x = json.loads(line[5:].strip())
            for ch in x.get("choices", []):
                c = ch.get("delta", {}).get("content")
                if c:
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    text.append(c)
    return ttft, "".join(text), time.perf_counter() - t0


def last():
    with urllib.request.urlopen(BASE + "/metrics?requests=all", timeout=30) as r:
        return json.loads(r.read())["requests"][0]


QS = ["In one sentence, what is the main topic?", "Name one number the text mentions.", "Is any source critical? One line.",
      "Give a three-word title.", "Which page is the longest? One line.", "Say OK."]
with open(WS / f"results/r13/ttft567-{LABEL}.jsonl", "a") as f:
    for target in (31000, 98000):
        text, n = doc(target)
        msgs = [{"role": "user", "content": "Read these pages; I will ask questions.\n\n" + text}]
        ttft, ans, tot = stream(msgs, 16)
        rec = last()
        print(f"[{LABEL}] {target // 1000}K chat: first read {rec.get('prompt_total')} tokens, TTFT {ttft:.2f} s", flush=True)
        msgs.append({"role": "assistant", "content": ans})
        for i, q in enumerate(QS):
            msgs.append({"role": "user", "content": q})
            ttft, ans, tot = stream(msgs)
            rec = last()
            row = {"label": LABEL, "chat": f"{target // 1000}K", "turn": i + 1, "prompt_total": rec.get("prompt_total"),
                   "reused": rec.get("reused"), "read": rec.get("prompt_read"), "prompt_ms": rec.get("prompt_ms"),
                   "ttft_s": round(ttft or -1, 4), "total_s": round(tot, 3)}
            f.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
            msgs.append({"role": "assistant", "content": ans})
