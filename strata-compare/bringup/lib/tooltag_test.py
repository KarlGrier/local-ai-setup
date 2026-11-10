#!/usr/bin/env python3
"""tooltag_test.py BASE LABEL [N] — round 11 Phase 0.3, the live test for upstream PR #700: the model is asked to name the
`<tool_call>` tag in prose before making a real call (OpenAI tools API, one web_search tool, no thinking, your sampling
otherwise), streamed and not, N times each.  Before the fix the parser took everything after the first tag as the call
body and the request ended with "malformed tool call"; after it the prose is content and the real call is parsed.
A case passes when the request completes, returns exactly one web_search call with a query, and the content keeps the
sentence.  Results to bringup/out/results/tooltag-LABEL.jsonl."""
import json
import sys
import urllib.error
import urllib.request

BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 3
TOOLS = [{"type": "function", "function": {"name": "web_search", "description": "Search the web.",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}]
SYS = ("You are a research assistant with a web_search tool. Before every tool call, first write this exact sentence on "
       "its own line: I will now use the <tool_call> format to search. Then make the call.")
USER = "Find the boiling point of water at 2,000 m altitude."


def run(stream):
    body = {"model": "x", "stream": stream, "reasoning_effort": "none", "max_tokens": 400, "tools": TOOLS,
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": USER}]}
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read()[:300]!r}"}
    if not stream:
        d = json.loads(r.read())
        if "error" in d:
            return {"error": str(d["error"])[:300]}
        m = d["choices"][0]["message"]
        return {"content": m.get("content") or "", "calls": [(c["function"]["name"], c["function"]["arguments"])
                                                              for c in m.get("tool_calls") or []],
                "finish": d["choices"][0].get("finish_reason")}
    content, calls, finish, err = [], {}, None, None
    for raw in r:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:") or line[5:].strip() in ("", "[DONE]"):
            continue
        x = json.loads(line[5:].strip())
        if "error" in x:
            err = str(x["error"])[:300]
            continue
        for ch in x.get("choices", []):
            dl = ch.get("delta", {})
            if dl.get("content"):
                content.append(dl["content"])
            for tc in dl.get("tool_calls") or []:
                c = calls.setdefault(tc.get("index", 0), ["", ""])
                c[0] += (tc.get("function") or {}).get("name") or ""
                c[1] += (tc.get("function") or {}).get("arguments") or ""
            finish = ch.get("finish_reason") or finish
    out = {"content": "".join(content), "calls": [tuple(v) for v in calls.values()], "finish": finish}
    if err:
        out["error"] = err
    return out


ok_n = tot = 0
with open(f"/home/USER/ai-speed-testing/strata-compare/bringup/out/results/tooltag-{LABEL}.jsonl", "w") as f:
    for stream in (False, True):
        for i in range(N):
            r = run(stream)
            named = "<tool_call>" in (r.get("content") or "")
            good = ("error" not in r and len(r.get("calls", [])) == 1 and r["calls"][0][0] == "web_search"
                    and "query" in r["calls"][0][1])
            ok = good and named
            tot += 1
            ok_n += ok
            r.update(stream=stream, run=i, ok=ok, tag_in_content=named)
            f.write(json.dumps(r) + "\n")
            print(f"{'PASS' if ok else 'FAIL'} stream={stream} run={i} finish={r.get('finish')} calls={r.get('calls')} "
                  f"tag in content={named} error={r.get('error', '')[:160]} content={(r.get('content') or '')[:90]!r}",
                  flush=True)
print(f"tooltag {LABEL}: {ok_n}/{tot} pass")
