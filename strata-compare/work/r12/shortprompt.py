#!/usr/bin/env python3
"""shortprompt.py LABEL [--base URL] — round 9 Phase 0: time-to-first-token of SHORT prompt reads on a running server
(v0.1.30 streams every expert from 1,024-token chunks, 0.1.29 from 2,048).  Three kinds, all at your settings
(T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05, effort high = xhigh), 8 output tokens each (only the prompt read matters):
  fresh   — new chats of ~1,024 / 1,536 / 2,000 / 3,000 / 4,000 prompt tokens, 3 reps each (unique first line: no reuse)
  follow  — a 3,000-token document chat, then 5 short follow-up turns (~40-250 new tokens each; read by verify windows)
  tool    — a question, then scripted fetch_page rounds whose results add ~1,200 / 1,800 / 2,500 / 3,500 / 5,000 new tokens
            (the prefix is identical request to request, so only the new call + result is read)
Server timings (prompt_n = tokens read, cache_n = reused, prompt_ms) come from the stream's final `timings`.
One JSON line per request -> results/r12/shortprompt.jsonl."""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from client import stream_chat  # noqa: E402
from common import load_tokenizer  # noqa: E402

SETTINGS = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "reasoning_effort": "high"}
tok = load_tokenizer()
SPEED = json.load(open(WS / "prompts/speed.json"))
CORPUS = SPEED[-1]["messages"][0]["content"]          # the 120K document: plenty of distinct text


_IDS = {}


def cut(text, n, start=0):
    """n tokens of `text` from token `start` (the text is tokenized once)"""
    if id(text) not in _IDS:
        _IDS[id(text)] = tok.encode(text)
    return tok.decode(_IDS[id(text)][start:start + n])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--out", default=str(WS / "results/r12/shortprompt.jsonl"))
    a = ap.parse_args()
    run = uuid.uuid4().hex[:6]
    out = open(a.out, "a")

    def call(kind, size, rep, messages):
        body = dict(SETTINGS, model="x", max_tokens=8, messages=messages)
        r = stream_chat(a.base, body)
        t = r.get("server_timings") or {}
        rec = {"label": a.label, "run": run, "kind": kind, "size": size, "rep": rep, "time": time.strftime("%H:%M:%S"),
               "ttft_s": r.get("ttft_s"), "t_total_s": r.get("t_total_s"), "prompt_tokens": r.get("prompt_tokens"),
               "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"), "prompt_ms": t.get("prompt_ms"),
               "error": r.get("error")}
        out.write(json.dumps(rec) + "\n"); out.flush()
        print(f"[{a.label}] {kind:6s} {size:>5} r{rep}: read {rec['prompt_n']} (+{rec['cache_n']} reused) "
              f"prompt_ms {rec['prompt_ms']} ttft {rec['ttft_s'] and round(rec['ttft_s'], 3)} s"
              f"{' ERROR ' + str(rec['error']) if rec['error'] else ''}", flush=True)
        return r

    # --- fresh prompts (distinct text per request: offsets into the corpus)
    off = 0
    for rep in range(3):
        for n in (1024, 1536, 2000, 3000, 4000):
            body = cut(CORPUS, n - 40, off)
            off += n
            call("fresh", n, rep, [{"role": "user", "content": f"[sp {run}-{rep}-{n}] Summarize the key point of this "
                                                               f"text in one sentence.\n\n{body}"}])
    # --- short follow-ups on a 3,000-token document chat
    doc = cut(CORPUS, 3000, off); off += 3000
    hist = [{"role": "user", "content": f"[sp {run} follow] Read this document.\n\n{doc}\n\nWhat is it about?"}]
    call("follow", 0, 0, hist)
    qs = ["Give me one more detail.", "Which part of it would a beginner find hardest, and why? Please answer briefly "
          "and point to the relevant passage in the document so I can read it again later.",
          "Thanks.", "Now list three questions an expert reviewer might ask about the document, each with a one-line "
          "suggested answer, and keep the whole reply under a hundred words. " * 2, "OK, last one: a title?"]
    for k, q in enumerate(qs):
        hist.append({"role": "assistant", "content": f"(answer {k}) " + cut(CORPUS, 30 + 10 * k, off)}); off += 60
        hist.append({"role": "user", "content": q})
        call("follow", len(tok.encode(q)), k + 1, hist)
    # --- tool-result appends (scripted fetch_page rounds)
    tools = [{"type": "function", "function": {"name": "fetch_page", "description": "Fetch a web page as text.",
                                               "parameters": {"type": "object", "properties": {"url": {"type": "string"}},
                                                              "required": ["url"]}}}]
    msgs = [{"role": "user", "content": f"[sp {run} tool] Look up what the pages say about the topic and summarize."}]

    def tcall(size, rep):
        body = dict(SETTINGS, model="x", max_tokens=8, messages=msgs, tools=tools)
        r = stream_chat(a.base, body)
        t = r.get("server_timings") or {}
        rec = {"label": a.label, "run": run, "kind": "tool", "size": size, "rep": rep, "time": time.strftime("%H:%M:%S"),
               "ttft_s": r.get("ttft_s"), "t_total_s": r.get("t_total_s"), "prompt_tokens": r.get("prompt_tokens"),
               "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"), "prompt_ms": t.get("prompt_ms"),
               "error": r.get("error")}
        out.write(json.dumps(rec) + "\n"); out.flush()
        print(f"[{a.label}] tool   {size:>5} r{rep}: read {rec['prompt_n']} (+{rec['cache_n']} reused) prompt_ms "
              f"{rec['prompt_ms']} ttft {rec['ttft_s'] and round(rec['ttft_s'], 3)} s"
              f"{' ERROR ' + str(rec['error']) if rec['error'] else ''}", flush=True)

    tcall(0, 0)
    for k, n in enumerate((1200, 1800, 2500, 3500, 5000)):
        cid = f"call_{run}_{k}"
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": cid, "type": "function", "function": {"name": "fetch_page",
                                                         "arguments": json.dumps({"url": f"https://example.org/p{k}"})}}]})
        msgs.append({"role": "tool", "tool_call_id": cid, "content": cut(CORPUS, n, off)}); off += n
        tcall(n, k + 1)


if __name__ == "__main__":
    main()
