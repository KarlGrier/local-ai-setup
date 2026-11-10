#!/usr/bin/env python3
"""agents2.py MODE LABEL [--base URL] — round 7 item 4e: two independent "agents" (fixed two-turn tasks that need web
search, run by the server's own web_search / fetch_page tools = the page's Web search switch, strata_web) against one
Strata server with the chat cache on.

MODE seq: agent A's turns, then agent B's (one after another).  MODE ovl: both agents at once, each in its own thread;
the server's FIFO interleaves them (a turn holds the engine only while it generates; tool calls run between turns).
Identical requests in both modes: the same messages, your chat settings (temperature 1.0, top_p 0.95, top_k 20,
reasoning_effort high; min_p 0.05 from the config), a fixed seed per turn, max_tokens 4096 per turn.
Counts only the tokens the server returns (usage.completion_tokens = accepted output tokens; drafts are not counted).

Writes results/r7/agents2.jsonl (one row per request) and prints the per-agent and total figures."""
import argparse
import json
import threading
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = WS / "results/r7/agents2.jsonl"
SETTINGS = {"reasoning_effort": "high", "temperature": 1.0, "top_p": 0.95, "top_k": 20}
AGENTS = {
    "A": ["Use web search: what is the newest stable Linux kernel release right now, and on what date was it "
          "released? Cite the page you used.",
          "Now check which kernel versions are currently longterm (LTS) releases, and when the oldest of them reaches "
          "end of life. Cite the page."],
    "B": ["Use web search: which Node.js release line is the current Active LTS, and when does its active support "
          "end? Cite the page you used.",
          "And what is the newest Python 3 feature release and its release date? Cite the page."],
}
lock = threading.Lock()


def turn(base, agent, k, msgs, label, mode):
    body = {"model": "x", "messages": msgs, "stream": True, "stream_options": {"include_usage": True},
            "max_tokens": 4096, "seed": 7000 + 10 * ord(agent) + k, "strata_web": True, **SETTINGS}
    t0 = time.time()
    t_first = t_content = None
    content, reasoning, usage, finish, err = [], [], None, None, None
    tools = {}
    try:
        with requests.post(base + "/v1/chat/completions", json=body, stream=True, timeout=3600) as r:
            if r.status_code != 200:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
            for raw in r.iter_lines():
                if not raw.startswith(b"data: ") or raw[6:] == b"[DONE]":
                    continue
                c = json.loads(raw[6:])
                if c.get("usage"):
                    usage = c["usage"]
                x = c.get("strata_mcp")
                if x and x.get("id"):
                    t = tools.setdefault(x["id"], {"id": x["id"], "name": x.get("name"), "t_start": time.time() - t0})
                    if x.get("event") == "call":
                        t.update(name=x["name"], arguments=x.get("arguments"), round=x.get("round"))
                    elif x.get("event") == "result":
                        t.update(ok=x.get("ok"), ms=x.get("ms"), chars=x.get("chars"), result=x.get("text"),
                                 skipped=x.get("skipped"), t_result=time.time() - t0)
                for ch in c.get("choices") or []:
                    d = ch.get("delta") or {}
                    now = time.time()
                    if d.get("reasoning_content"):
                        reasoning.append(d["reasoning_content"])
                        t_first = t_first or now
                    if d.get("content"):
                        content.append(d["content"])
                        t_first = t_first or now
                        t_content = t_content or now
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
    except Exception as e:  # noqa: BLE001
        err = repr(e)[:200]
    t1 = time.time()
    ran = [t for t in tools.values() if t.get("round") is not None and t.get("result") is not None and not t.get("skipped")]
    row = {"label": label, "mode": mode, "agent": agent, "turn": k, "t0": t0, "t1": t1, "total_s": t1 - t0,
           "ttft_s": (t_first - t0) if t_first else None, "t_content_s": (t_content - t0) if t_content else None,
           "completion_tokens": (usage or {}).get("completion_tokens"), "prompt_tokens": (usage or {}).get("prompt_tokens"),
           "finish": finish, "error": err, "tools": [(t.get("name"), t.get("ok"), t.get("ms"), t.get("chars")) for t in tools.values()],
           "tool_ms": sum((t.get("ms") or 0) for t in tools.values()), "answer": "".join(content)[:400]}
    with lock:
        with open(OUT, "a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{time.strftime('%H:%M:%S')} {label} {mode} {agent}{k} ttft {row['ttft_s'] or 0:6.2f}s total {row['total_s']:6.1f}s "
              f"out {row['completion_tokens']} prompt {row['prompt_tokens']} tools {len(tools)} ({row['tool_ms'] / 1000:.1f} s) "
              f"{finish}{' ERR ' + err if err else ''}", flush=True)
    # the page's way of sending the tool rounds back on the next turn
    out = []
    for rnd in sorted({t["round"] for t in ran}):
        calls = [t for t in ran if t["round"] == rnd]
        out.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": t["id"], "type": "function", "function": {"name": t["name"], "arguments": json.dumps(t.get("arguments") or {})}}
            for t in calls]})
        out += [{"role": "tool", "tool_call_id": t["id"], "content": t["result"]} for t in calls]
    out.append({"role": "assistant", "content": "".join(content)})
    return row, out


def agent(base, name, label, mode, rows):
    msgs = []
    for k, q in enumerate(AGENTS[name]):
        msgs.append({"role": "user", "content": q})
        row, add = turn(base, name, k, msgs, label, mode)
        rows.append(row)
        msgs += add


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["seq", "ovl"])
    ap.add_argument("label")
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    a = ap.parse_args()
    rows = []
    T0 = time.time()
    if a.mode == "seq":
        agent(a.base, "A", a.label, a.mode, rows)
        agent(a.base, "B", a.label, a.mode, rows)
    else:
        th = [threading.Thread(target=agent, args=(a.base, n, a.label, a.mode, rows)) for n in "AB"]
        for t in th:
            t.start()
        for t in th:
            t.join()
    T1 = time.time()
    print(f"=== {a.label} {a.mode}: total {T1 - T0:.1f} s")
    for n in "AB":
        r = [x for x in rows if x["agent"] == n]
        tok = sum(x["completion_tokens"] or 0 for x in r)
        wall = max(x["t1"] for x in r) - min(x["t0"] for x in r)
        print(f"  agent {n}: {tok} output tokens in {wall:.1f} s = {tok / wall:.1f} tok/s end to end; first-token "
              f"latency {', '.join(f'{x['ttft_s']:.2f}' for x in r if x['ttft_s'])} s; tool time {sum(x['tool_ms'] for x in r) / 1000:.1f} s")
    tok = sum(x["completion_tokens"] or 0 for x in rows)
    print(f"  both: {tok} output tokens in {T1 - T0:.1f} s = {tok / (T1 - T0):.1f} tok/s")


if __name__ == "__main__":
    main()
