#!/usr/bin/env python3
"""chat5.py BASE OUTDIR ENGINE_LOG SLOT_DIR - 10-24 DeepSeek-V4.1 tuning round, items C.9 and C.10.
C.9 (the user: "a 5-turn conversation growing to ~10K tokens. Does each turn reuse the conversation cache (RAM or the
new on-disk state) or re-read the whole conversation? Report time to first token per turn, and how much the on-disk
conversation state writes per turn"): conversation A, 5 turns, each a ~2K-token excerpt of Strata's public docs plus a
question (thinking on at the template's default effort, 1,200 tokens per answer); then conversation B (1 turn, so A is
displaced into a slot), then A's 6th turn (back to A). Per turn: TTFT, prompt tokens, the engine's own "reused + read"
line, the engine's write_bytes, and the size of the slot folder (the server's STRATA_DS4_SLOT_KEEP / AUTO_PIN are set in
the arm's config). -> OUTDIR/chat.jsonl
C.10 ("how long DS4.1 thinks by default on W1-W3"): W1, W2 and W3 once each at the default effort ("high" = 75) with
8,192 tokens (the server leaves 6,144 for thinking) -> OUTDIR/think.jsonl (reasoning / answer characters, finish).
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402

DOCS = "/home/USER/ai-speed-testing/strata-compare/strata-v024/docs"
QUESTIONS = [
    "Here is part of a document about my inference engine. Summarise what it says about memory use, in five bullet points.",
    "Here is the next part. How does it relate to what you summarised before? Anything that contradicts it?",
    "Next part. Which of the settings mentioned so far would matter most on a PC with a 16 GB and an 8 GB GPU?",
    "Next part. List any numbers (speeds, sizes) given across all the parts so far, with what they refer to.",
    "Last part. Give me a one-paragraph overall summary of all five parts and the three most useful tips.",
]


def doc_chunks(n, size=7600):
    text = ""
    for name in ("MULTI_GPU.md", "DEEPSEEK41.md", "CONFIG.md", "PERFORMANCE.md", "SETUP.md", "README.md"):
        p = os.path.join(DOCS, name)
        if os.path.exists(p):
            text += open(p, encoding="utf-8", errors="replace").read() + "\n\n"
    if len(text) < n * size:
        for p in sorted(os.listdir(DOCS)):
            if p.endswith(".md") and len(text) < n * size * 2:
                text += open(os.path.join(DOCS, p), encoding="utf-8", errors="replace").read() + "\n\n"
    return [text[i * size:(i + 1) * size] for i in range(n)]


def engine_pid():
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if os.path.basename(os.readlink(f"/proc/{p}/exe")) == "strata-dsv41":
                    return int(p)
            except OSError:
                pass


def wbytes(pid):
    try:
        return int(next(l for l in open(f"/proc/{pid}/io") if l.startswith("write_bytes:")).split()[1])
    except (OSError, StopIteration):
        return None


def du(d):
    if not os.path.isdir(d):
        return 0
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs)


def chat(base, messages, max_tokens):
    body = {"model": "x", "messages": messages, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}, "reasoning_effort": "high", **abrun.NORMAL}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic(); t1 = None; content = []; usage = None; finish = None; rch = 0
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            usage = ev.get("usage") or usage
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if (d.get("content") or d.get("reasoning_content") or d.get("reasoning")) and t1 is None:
                    t1 = time.monotonic()
                content.append(d.get("content") or "")
                rch += len(d.get("reasoning_content") or d.get("reasoning") or "")
                finish = ch.get("finish_reason") or finish
    t2 = time.monotonic()
    return {"ttft_s": round(t1 - t0, 2) if t1 else None, "total_s": round(t2 - t0, 1), "answer": "".join(content),
            "reasoning_chars": rch, "usage": usage, "finish": finish}


def main():
    base, out, elog, slots = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], sys.argv[4]
    pid = engine_pid()
    chunks = doc_chunks(6)
    off = os.path.getsize(elog) if os.path.exists(elog) else 0
    A = [{"role": "system", "content": "You are a helpful assistant. Answer clearly and concisely."}]
    B = [{"role": "system", "content": "You are a helpful assistant. Answer clearly and concisely."}]
    plan = [("A", i) for i in range(5)] + [("B", 0), ("A", 5)]
    for conv, i in plan:
        msgs = A if conv == "A" else B
        if conv == "A" and i < 5:
            q = f"{QUESTIONS[i]}\n\n[part {i + 1}, ref {uuid.uuid4().hex[:6]}]\n{chunks[i]}"
        elif conv == "A":
            q = "One more question about all of this: which single change would you try first to make long prompts faster, and why?"
        else:
            q = f"Different topic. Summarise this text in three bullet points:\n\n{chunks[5]}"
        msgs.append({"role": "user", "content": q})
        w0 = wbytes(pid); s0 = du(slots)
        r = chat(base, msgs, 1200)
        time.sleep(1.0)                                   # the engine writes its profile (and any slot) after the reply
        w1 = wbytes(pid); s1 = du(slots)
        new = open(elog, encoding="utf-8", errors="replace").read()[off:] if os.path.exists(elog) else ""
        off = os.path.getsize(elog) if os.path.exists(elog) else off
        reuse = re.findall(r"[^\n]*(?:reused|restor|slot)[^\n]*", new, re.I)
        msgs.append({"role": "assistant", "content": r["answer"]})
        rec = {"conv": conv, "turn": i + 1, "ttft_s": r["ttft_s"], "total_s": r["total_s"],
               "prompt_tokens": (r["usage"] or {}).get("prompt_tokens"), "completion_tokens": (r["usage"] or {}).get("completion_tokens"),
               "finish": r["finish"], "engine_write_mb": round((w1 - w0) / 1e6, 2) if w0 is not None and w1 is not None else None,
               "slot_dir_mb": round(s1 / 1e6, 2), "slot_dir_delta_mb": round((s1 - s0) / 1e6, 2), "engine_lines": [x[:200] for x in reuse[-4:]]}
        with open(f"{out}/chat.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{conv}{i + 1}: prompt {rec['prompt_tokens']} TTFT {rec['ttft_s']} s, write {rec['engine_write_mb']} MB, "
              f"slots {rec['slot_dir_mb']} MB; {' | '.join(rec['engine_lines'][-2:])}", flush=True)
    wl = json.load(open(abrun.WL))
    for w in wl["normal"]:
        if w["id"].startswith(("W1", "W2", "W3")):
            rec = abrun.one(base, "think", dict(w, effort="high", max_tokens=8192), abrun.NORMAL, {}, 0, f"{out}/think.jsonl")
            print(f"{w['id']}: {rec.get('completion_tokens')} tokens, reasoning {rec.get('reasoning_chars')} chars, answer "
                  f"{rec.get('content_chars')} chars, finish {rec.get('finish')}", flush=True)


if __name__ == "__main__":
    main()
