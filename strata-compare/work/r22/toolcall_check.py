#!/usr/bin/env python3
"""toolcall_check.py BASE LABEL [REPS] - round 22 gap 10 (10-23): the tool-call check before the continuation-fix switch.

The request shapes of the three clients that call tools on 8080, streamed as they stream them, at T 1.0 / 0.95 / 20 /
min-p 0.05, thinking on (medium):
  opencode-A / opencode-B  prompts/agentturn.json: two OpenCode-style turns (A-edit, B-write) with OpenCode's 6 tools
  jan                      a question that needs a search, with Jan's two MCP tools as Jan sends them (web_search,
                           fetch_page; schemas from ~/ai/deep-research/tools/web-mcp.py)
  research                 o02 p4base's agent call 989 (~33K tokens) with LDR's web_search / fetch_content, as the
                           research proxy sends it (strata_checkpoint false)
Each at its usual cap and at max_tokens 1024: answer_room then closes the thinking at 768 tokens, so the call is
written in the continuation pass - the code path the fix changes. REPS (default 3) of each.

Per response: every tool call's name is one of the request's tools, its arguments parse as a JSON object with the
required keys; no tool-call markup in the visible text (<tool_call>, </tool_call>, <function=); finish reason.
Writes BASE-independent JSON lines to results/r22/gap10/toolcall-LABEL.jsonl; prints one line per response and a
summary line "TOOLCALL LABEL: N responses, C with a valid call, X truncated at max_tokens, M malformed, K leaks".
"""
import json
import pathlib
import sys
import time
import urllib.request
import uuid

WS = pathlib.Path("/home/USER/ai-speed-testing/strata-compare")
CAP = pathlib.Path("/home/USER/ai/deep-research/results/bench2/runs/screen-deep-p4base/o02/capture/calls.jsonl")
NORMAL = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
LEAK = ("<tool_call>", "</tool_call>", "<function=")


def jan_tools():
    tools = pathlib.Path("/home/USER/ai/deep-research/tools")
    ns = {}
    exec((tools / "tool_choice.py").read_text(), ns)                     # TOOL_CHOICE (the text Jan's tools carry)
    src = (tools / "web-mcp.py").read_text()
    start = src.index("TOOLS = [")
    exec(src[start:src.index("\n]\n", start) + 3], ns)                    # TOOLS only (web-mcp's imports not run)
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["inputSchema"]}} for t in ns["TOOLS"]]


def shapes():
    agent = {w["id"]: w for w in json.load(open(WS / "prompts/agentturn.json"))}
    c989 = next(c for c in map(json.loads, open(CAP, encoding="utf-8")) if c["id"] == 989)
    ldr = [{"type": "function", "function": {"name": "web_search", "description": "Search the selected source and return result snippets with source indices.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
           {"type": "function", "function": {"name": "fetch_content", "description": "Download and read the full text content from a URL. Use when search snippets aren't detailed enough.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}]
    jan_q = [{"role": "user", "content": "What is the newest stable Linux kernel release right now, and when did it come "
                                         "out? Look it up, don't answer from memory."}]
    return [
        ("opencode-A", agent["A-edit"]["messages"], agent["A-edit"]["tools"], agent["A-edit"]["max_tokens"], {}),
        ("opencode-B", agent["B-write"]["messages"], agent["B-write"]["tools"], agent["B-write"]["max_tokens"], {}),
        ("jan", jan_q, jan_tools(), 4096, {}),
        ("research", c989["messages"], ldr, 2048, {"strata_checkpoint": False}),
    ]


def ask(base, msgs, tools, cap, extra):
    msgs = [dict(msgs[0], content=f"[request {uuid.uuid4().hex[:8]}]\n" + msgs[0]["content"])] + msgs[1:] \
        if isinstance(msgs[0].get("content"), str) else msgs
    body = {"model": "x", "messages": msgs, "max_tokens": cap, "stream": True, "tools": tools,
            "reasoning_effort": "medium", **NORMAL, **extra}
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    calls, content, finish, err = {}, [], None, None
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    ev = json.loads(data)
                except ValueError:
                    continue
                if ev.get("error"):
                    err = str(ev["error"])[:200]
                for ch in ev.get("choices") or []:
                    d = ch.get("delta") or {}
                    if d.get("content"):
                        content.append(d["content"])
                    for tc in d.get("tool_calls") or []:
                        c = calls.setdefault(tc.get("index", 0), {"name": "", "args": ""})
                        f = tc.get("function") or {}
                        c["name"] += f.get("name") or ""
                        c["args"] += f.get("arguments") or ""
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
    except Exception as e:                       # noqa: BLE001 - an HTTP error is a result here
        err = f"{type(e).__name__}: {e}"[:200]
    return [calls[k] for k in sorted(calls)], "".join(content), finish, err, round(time.monotonic() - t0, 1)


def check(calls, tools):
    spec = {t["function"]["name"]: t["function"].get("parameters", {}).get("required", []) for t in tools}
    bad = []
    for c in calls:
        if c["name"] not in spec:
            bad.append(f"unknown tool {c['name']!r}")
            continue
        try:
            a = json.loads(c["args"] or "{}")
        except ValueError:
            bad.append(f"{c['name']}: arguments not JSON: {c['args'][:80]!r}")
            continue
        if not isinstance(a, dict) or any(k not in a for k in spec[c["name"]]):
            bad.append(f"{c['name']}: missing {[k for k in spec[c['name']] if k not in (a or {})]}")
    return bad


def main():
    base, label = sys.argv[1], sys.argv[2]
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    out = WS / f"results/r22/gap10/toolcall-{label}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = valid = cut = malformed = leaks = errors = 0
    with open(out, "a") as fo:
        for name, msgs, tools, cap0, extra in shapes():
            for cap in (cap0, 1024):
                for rep in range(reps):
                    calls, content, finish, err, secs = ask(base, msgs, tools, cap, extra)
                    bad = check(calls, tools)
                    leak = [m for m in LEAK if m in content]
                    # 10-23 (the user, after gap 10): a call whose arguments stop at max_tokens (finish "length") is
                    # "truncated", not malformed - the client sees finish_reason "length" (gap 10 counted 3 + 3 OpenCode
                    # write calls at the 1,024 cap as malformed). The 1,024 cap stays: it puts the call in answer_room's
                    # continuation pass; the shapes' own caps are 2,048-4,096.
                    is_cut = bool(bad) and finish == "length" and all("arguments not JSON" in b for b in bad)
                    n += 1
                    valid += bool(calls) and not bad
                    cut += is_cut
                    malformed += bool(bad) and not is_cut
                    leaks += bool(leak)
                    errors += bool(err)
                    rec = {"label": label, "shape": name, "cap": cap, "rep": rep, "finish": finish, "secs": secs, "truncated": is_cut,
                           "calls": [c["name"] for c in calls], "bad": bad, "leak": leak, "error": err,
                           "content_chars": len(content)}
                    fo.write(json.dumps(rec) + "\n")
                    ok = "ok" if not bad and not leak and not err else "truncated at max_tokens" if is_cut and not leak and not err \
                        else "PROBLEM"
                    print(f"{label} {name:10} cap {cap:4} r{rep}: finish {finish}, calls {[c['name'] for c in calls]}, "
                          f"{len(content)} text chars, {secs} s - {ok}{(' ' + '; '.join(bad + leak)) if bad or leak else ''}"
                          f"{(' error ' + err) if err else ''}", flush=True)
    print(f"TOOLCALL {label}: {n} responses, {valid} with a valid call, {cut} truncated at max_tokens, {malformed} malformed, {leaks} leaks, "
          f"{errors} errors")


if __name__ == "__main__":
    main()
