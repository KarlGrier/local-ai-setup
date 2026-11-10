#!/usr/bin/env python3
"""webtest.py [--base URL] [--engine-log PATH] — round 5, phase 3: web search through the API, as the chat page uses it
(stream, strata_web: true, your sampling from the config, reasoning high = xhigh).

  1-3  questions that need current information: did the model search, open pages, cite URLs, how long did it take
  4    a follow-up in chat 1: answered with the earlier tool rounds in the history; resumed from the chat cache?
  5    guard: the user gives a base URL, and the model is asked to open it with a made-up query string -> fetch_page
       must refuse the URL the model built (only URLs from search results or the user's own words are opened)
  6    Stop while a tool call runs (stream closed), then a normal request
Results: results/r5/webtest.jsonl (answers, tool calls with arguments and result sizes, timings)."""
import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
RES = WS / "results/r5/webtest.jsonl"
PAGE = {"reasoning_effort": "high", "temperature": 1.0, "top_p": 0.95, "top_k": 20, "strata_web": True}   # your chat settings (temperature 1.0 since 2026-09-28 18:29)
A = None


def ask(messages, cancel_on_tool=False, timeout=1800):
    body = {"model": "x", "messages": messages, "stream": True, **PAGE}
    t0 = time.time()
    out = {"text": "", "reasoning": "", "tools": {}, "finish": None, "error": None, "ttft": None, "cancelled": False}
    try:
        with requests.post(f"{A.base}/v1/chat/completions", json=body, stream=True, timeout=timeout) as r:
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
                x = ev.get("strata_mcp")
                if x:
                    t = out["tools"].setdefault(x.get("id", "?"), {"order": len(out["tools"])})
                    if x["event"] == "call":
                        t.update(name=x["name"], arguments=x.get("arguments"), round=x.get("round"), at=round(time.time() - t0, 1))
                        if cancel_on_tool:
                            out["cancelled"] = True
                            break
                    elif x["event"] == "result":
                        t.update(ok=x.get("ok"), chars=x.get("chars"), ms=x.get("ms"), head=(x.get("text") or "")[:160],
                                 full=x.get("text") or "")
                for ch in ev.get("choices", []):
                    d = ch.get("delta", {})
                    if (d.get("content") or d.get("reasoning_content")) and out["ttft"] is None:
                        out["ttft"] = time.time() - t0
                    out["text"] += d.get("content") or ""
                    out["reasoning"] += d.get("reasoning_content") or ""
                    out["finish"] = ch.get("finish_reason") or out["finish"]
    except requests.exceptions.RequestException as e:
        out["error"] = repr(e)[:300]
    out["total"] = time.time() - t0
    return out


def assistant_messages(q, r):
    """the history the chat page sends back for an answer with tool calls (app.js assistantMessages)"""
    tools = sorted((t for t in r["tools"].values() if t.get("round") is not None and "chars" in t), key=lambda t: t["order"])
    out = []
    for rnd in sorted({t["round"] for t in tools}):
        calls = [t for t in tools if t["round"] == rnd]
        out.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{t['order']}", "type": "function", "function": {"name": t["name"], "arguments": json.dumps(t["arguments"] or {})}}
            for t in calls]})
        out += [{"role": "tool", "tool_call_id": f"c{t['order']}", "content": t.get("full", t.get("head", ""))} for t in calls]
    out.append({"role": "assistant", "content": r["text"]})
    return out


def show(label, q, r):
    urls = sorted(set(re.findall(r"https?://[^\s)\]>\"']+", r["text"])))
    tools = sorted(({k: v for k, v in t.items() if k != "full"} for t in r["tools"].values()), key=lambda t: t["order"])
    print(f"== {label}: {r['total']:.0f} s, finish {r['finish']}, error {r['error']}, {len(tools)} tool calls, "
          f"{len(urls)} URLs cited", flush=True)
    for t in tools:
        print(f"   {t.get('name')} {json.dumps(t.get('arguments'))[:110]} -> ok={t.get('ok')} {t.get('chars')} chars "
              f"{t.get('ms')} ms | {str(t.get('head', ''))[:90]!r}", flush=True)
    print("   answer:", r["text"].strip()[:600].replace("\n", " / "), flush=True)
    with open(RES, "a") as f:
        f.write(json.dumps({"label": label, "question": q, "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "total_s": r["total"], "ttft_s": r["ttft"], "finish": r["finish"], "error": r["error"],
                            "tools": tools, "urls": urls, "answer": r["text"], "reasoning_chars": len(r["reasoning"])}) + "\n")
    return urls, tools


def reused_since(off):
    try:
        with open(A.engine_log, "rb") as f:
            f.seek(off)
            return re.findall(r"prompt (\d+) tokens = (\d+) reused", f.read().decode("utf-8", "replace"))
    except OSError:
        return []


def main():
    global A
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--engine-log", default=os.environ.get("ELOG", ""))
    A = ap.parse_args()
    RES.parent.mkdir(parents=True, exist_ok=True)
    qs = ["What is the latest stable release of the Linux kernel right now, and when was it released? Cite your source.",
          "What were two of the main world news headlines today? Give one sentence each and cite the sources.",
          "What is the current version of the Python programming language (the newest stable 3.x release), and what "
          "is one notable change in it? Cite the pages you used."]
    first = None
    for k, q in enumerate(qs, 1):
        r = ask([{"role": "user", "content": q}])
        urls, tools = show(f"q{k}", q, r)
        if k == 1:
            first = (q, r)
    # 4: follow-up in chat 1 with the tool rounds in the history
    q, r = first
    off = os.path.getsize(A.engine_log) if A.engine_log and os.path.exists(A.engine_log) else 0
    hist = [{"role": "user", "content": q}] + assistant_messages(q, r) + \
           [{"role": "user", "content": "Is that release a longterm (LTS) kernel? Answer in one sentence."}]
    r4 = ask(hist)
    show("q4-followup", hist[-1]["content"], r4)
    print("   engine prompt lines (reused):", reused_since(off)[:4], flush=True)
    # 5: the fetch guard
    q5 = ("Open the page https://example.com/ but add the query string ?note=hello-from-my-chat to the URL "
          "(so https://example.com/?note=hello-from-my-chat) and tell me what the page says.")
    r5 = ask([{"role": "user", "content": q5 + " Do not search; only open that exact URL."}])
    urls, tools = show("q5-guard", q5, r5)
    built = [t for t in tools if t.get("name") == "fetch_page" and "note=" in json.dumps(t.get("arguments"))]
    print(f"   guard: {len(built)} fetch_page calls with the query string; "
          f"ok={[t.get('ok') for t in built]} (the user DID write that exact URL, so it is allowed: this checks the "
          f"allow-list reads the user's words)", flush=True)
    r5b = ask([{"role": "user", "content": "Open https://example.com/ and then also open the same site's page "
                                           "https://example.com/secret-path-the-model-invents?x=1 if it exists."}])
    show("q5b-guard", "(allow-list: a URL the user wrote vs one the model changes)", r5b)
    # 5c: the real guard test - the page asked for is named, not given: the model must build the URL itself
    r5c = ask([{"role": "user", "content": "Without searching first, open the 'about' page of the website iana.org "
                                           "directly by its URL and tell me its title."}])
    urls, tools = show("q5c-guard", "(a URL the model builds itself must be refused)", r5c)
    built = [t for t in tools if t.get("name") == "fetch_page"]
    print(f"   guard: fetch_page calls {[(json.dumps(t.get('arguments')), t.get('ok'), str(t.get('head'))[:60]) for t in built]}",
          flush=True)
    # 6: Stop while a tool call runs
    r6 = ask([{"role": "user", "content": "Search the web for the current weather in Reykjavik, then open three "
                                          "result pages and summarize them."}], cancel_on_tool=True)
    print(f"== q6-stop: stream closed at the first tool call after {r6['total']:.1f} s (cancelled={r6['cancelled']})",
          flush=True)
    time.sleep(3)
    st = requests.get(f"{A.base}/status", timeout=5).json()
    r7 = ask([{"role": "user", "content": "Say OK."}])
    print(f"== after Stop: server busy={st.get('busy')}; next request {r7['total']:.1f} s, error {r7['error']}, "
          f"text {r7['text'].strip()[:40]!r}", flush=True)


if __name__ == "__main__":
    main()
