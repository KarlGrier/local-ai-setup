#!/usr/bin/env python3
"""webreplay.py — round 6, Phase C: one FIXED multi-turn chat with SAVED web-search results, replayed (no live searches).

  webreplay.py capture --base URL          run the chat ONCE with the Web search switch on (live SearXNG), save the whole
                                           transcript incl. every tool call and its full result -> results/r6/webreplay-
                                           transcript.json (done once; the replays never search)
  webreplay.py replay --base URL --label L send the saved chat turn by turn, exactly as a client re-sends a history:
                                           earlier user turns, the saved assistant tool-call rounds, the saved tool
                                           results and the saved earlier answers; the server generates only each turn's
                                           final answer, with web search OFF (no tool can run).  Records per turn: time
                                           to first token, decode tok/s, prompt tokens and reused (cached) tokens,
                                           finish, answer length and a content check -> results/r6/webreplay.jsonl

Requests are shaped like the chat page's (reasoning_effort high); the replay sends the user's settings explicitly
(temperature 1.0, top_p 0.95, top_k 20, min_p 0.05) and max_tokens 3072 per answer.
"""
import argparse
import json
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
TR = WS / "results/r6/webreplay-transcript.json"
OUT = WS / "results/r6/webreplay.jsonl"
USER = {"reasoning_effort": "high", "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
TURNS = [
    ("What is the latest stable release of the Linux kernel right now, and when was it released? Cite your source.",
     ["7."], True),
    ("Is that release a longterm (LTS) kernel? Answer in one sentence.", ["LTS", "longterm", "long-term", "not"], False),
    ("What is the newest Python 3 release, and name one notable change in it. Cite the page you used.", ["3.1"], True),
    ("Compare the two: which of those two projects released more recently? One sentence.", ["Linux", "Python"], False),
    ("Summarize this whole conversation in three bullet points.", ["Linux", "Python"], False),
]


def stream(base, messages, extra, timeout=1800):
    body = {"model": "x", "messages": messages, "stream": True, "stream_options": {"include_usage": True}, **extra}
    t0 = time.time()
    out = {"text": "", "reasoning": "", "tools": {}, "finish": None, "error": None, "ttft": None, "usage": None,
           "n_chunks": 0}
    with requests.post(f"{base}/v1/chat/completions", json=body, stream=True, timeout=timeout) as r:
        if r.status_code != 200:
            out["error"] = f"HTTP {r.status_code}: {r.text[:300]}"
            return out
        for line in r.iter_lines():
            if not line.startswith(b"data: ") or line == b"data: [DONE]":
                continue
            ev = json.loads(line[6:])
            if "error" in ev:
                out["error"] = str(ev["error"])[:300]
                break
            if ev.get("usage"):
                out["usage"] = ev["usage"]
            x = ev.get("strata_mcp")
            if x:
                t = out["tools"].setdefault(x.get("id", "?"), {"order": len(out["tools"])})
                if x["event"] == "call":
                    t.update(name=x["name"], arguments=x.get("arguments"), round=x.get("round"))
                elif x["event"] == "result":
                    t.update(ok=x.get("ok"), full=x.get("text") or "")
            for ch in ev.get("choices", []):
                d = ch.get("delta", {})
                if (d.get("content") or d.get("reasoning_content")) and out["ttft"] is None:
                    out["ttft"] = time.time() - t0
                if d.get("content") or d.get("reasoning_content"):
                    out["n_chunks"] += 1
                out["text"] += d.get("content") or ""
                out["reasoning"] += d.get("reasoning_content") or ""
                out["finish"] = ch.get("finish_reason") or out["finish"]
    out["total"] = time.time() - t0
    return out


def tool_rounds(r):
    """the history a client sends back for an answer with tool calls (the chat page's assistantMessages)"""
    tools = sorted((t for t in r["tools"].values() if t.get("round") is not None and "full" in t), key=lambda t: t["order"])
    msgs = []
    for rnd in sorted({t["round"] for t in tools}):
        calls = [t for t in tools if t["round"] == rnd]
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{t['order']}", "type": "function",
             "function": {"name": t["name"], "arguments": json.dumps(t["arguments"])}} for t in calls]})
        msgs += [{"role": "tool", "tool_call_id": f"c{t['order']}", "content": t["full"]} for t in calls]
    return msgs


def capture(a):
    hist, saved = [], []
    for q, _, web in TURNS:
        hist.append({"role": "user", "content": q})
        r = stream(a.base, hist, {**USER, "strata_web": web, "max_tokens": 4096})
        rounds = tool_rounds(r) if web else []
        saved.append({"question": q, "tool_rounds": rounds, "answer": r["text"], "finish": r["finish"],
                      "error": r["error"], "n_tools": len(r["tools"])})
        print(f"capture: {q[:50]}... tools {len(r['tools'])} finish {r['finish']} error {r['error']} answer {len(r['text'])} chars")
        hist += rounds + [{"role": "assistant", "content": r["text"]}]
    TR.write_text(json.dumps({"captured": time.strftime("%Y-%m-%dT%H:%M:%S"), "turns": saved}, indent=1))
    print("saved", TR)


NEW = [  # capture2: follow-ups answered from the pages already read (the live engines rate-limited later searches)
    ("From the kernel.org releases page you opened, which kernel trees are longterm, and until when is each maintained? "
     "Use only what you already read; no new searches.", ["longterm", "LTS", "EOL", "20"]),
    ("Summarize this whole conversation in three bullet points.", ["kernel"]),
]
KEYS = {q: k for q, k, _ in TURNS}
KEYS.update({q: k for q, k in NEW})


def capture2(a):
    """keep the first two captured turns (real saved web results), add NEW turns answered without tools"""
    T = json.loads(TR.read_text())["turns"][:2]
    hist = []
    for t in T:
        hist += [{"role": "user", "content": t["question"]}] + t["tool_rounds"] + [{"role": "assistant", "content": t["answer"]}]
    for q, _ in NEW:
        hist.append({"role": "user", "content": q})
        r = stream(a.base, hist, {**USER, "max_tokens": 4096})
        T.append({"question": q, "tool_rounds": [], "answer": r["text"], "finish": r["finish"], "error": r["error"],
                  "n_tools": len(r["tools"])})
        print(f"capture2: {q[:50]}... finish {r['finish']} error {r['error']} answer {len(r['text'])} chars")
        hist.append({"role": "assistant", "content": r["text"]})
    TR.write_text(json.dumps({"captured": time.strftime("%Y-%m-%dT%H:%M:%S"), "turns": T,
                              "note": "turns 1-2: live capture 13:15 (C*5, SearXNG); 3-4: answered from them (capture2)"}, indent=1))
    print("saved", TR)


def replay(a):
    T = json.loads(TR.read_text())["turns"]
    hist = []
    with OUT.open("a") as f:
        for k, t in enumerate(T):
            keys = KEYS.get(t["question"], [])
            hist.append({"role": "user", "content": t["question"]})
            hist += t["tool_rounds"]
            r = stream(a.base, hist, {**USER, "max_tokens": 3072})
            u = r.get("usage") or {}
            gen = u.get("completion_tokens")
            ttft = r["ttft"] or 0.0
            dec = (gen / (r["total"] - ttft)) if gen and r["total"] > ttft else None
            ok = any(x.lower() in (r["text"] or "").lower() for x in keys)
            rec = {"label": a.label, "turn": k + 1, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "ttft_s": round(ttft, 3),
                   "total_s": round(r["total"], 2), "completion_tokens": gen, "decode_tok_s": round(dec, 1) if dec else None,
                   "prompt_tokens": u.get("prompt_tokens"), "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                   "finish": r["finish"], "error": r["error"], "answer_chars": len(r["text"]), "check": ok,
                   "tools_called": len(r["tools"])}
            f.write(json.dumps(rec) + "\n")
            print(json.dumps(rec))
            hist.append({"role": "assistant", "content": t["answer"]})   # the saved answer: a fixed history


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["capture", "capture2", "replay"])
    p.add_argument("--base", default="http://127.0.0.1:8081")
    p.add_argument("--label", default="x")
    a = p.parse_args()
    {"capture": capture, "capture2": capture2, "replay": replay}[a.mode](a)
