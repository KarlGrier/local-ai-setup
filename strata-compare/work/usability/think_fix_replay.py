#!/usr/bin/env python3
"""think_fix_replay.py - 2026-10-16 (r21 item 4): replay every recorded tool-enabled turn of the usability round through
two OutputParsers offline (no GPU): A = the served tree's (default strata-cstar18) and B = the patched tree's (default
strata-r21think: a `</think>` inside a code fence of the reasoning is quoted; an unclosed fence falls back to the last
`</think>`).  The gate: B differs from A only on the 7 turns whose tool call the quoted tag lost (7 recoveries), and
B's events are the same whether the text arrives 1 character, 7 characters or all at once.

    .venv/bin/python work/usability/think_fix_replay.py [A_TREE] [B_TREE]
"""
import gzip
import importlib.util
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")


def load(tree, name):
    spec = importlib.util.spec_from_file_location(name, WS / tree / "serve/frontend.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.OutputParser


A = load(sys.argv[1] if len(sys.argv) > 1 else "strata-cstar18", "frontend_a")
B = load(sys.argv[2] if len(sys.argv) > 2 else "strata-r21think", "frontend_b")


def call_text(name, args):
    try:
        a = json.loads(args) if isinstance(args, str) else args
    except json.JSONDecodeError:
        a = {"_raw": args}
    ps = "".join(f"<parameter={k}>\n{v if isinstance(v, str) else json.dumps(v)}\n</parameter>\n" for k, v in a.items())
    return f"<tool_call>\n<function={name}>\n{ps}</function>\n</tool_call>"


def rebuild(req, raw):
    reasoning = content = ""
    calls = {}
    for line in raw.splitlines():
        if not line.startswith("data:") or "[DONE]" in line:
            continue
        ev = json.loads(line[5:])
        t = ev.get("type", "")
        if t == "response.output_text.delta":
            content += ev["delta"]
        elif t.startswith("response.reasoning") and t.endswith(".delta"):
            reasoning += ev["delta"]
        elif t == "response.output_item.done" and ev["item"].get("type") == "function_call":
            calls[len(calls)] = [ev["item"]["name"], ev["item"].get("arguments", "{}")]
        for ch in ev.get("choices", []):
            d = ch.get("delta", {})
            reasoning += d.get("reasoning_content") or ""
            content += d.get("content") or ""
            for tc in d.get("tool_calls") or []:
                c = calls.setdefault(tc.get("index", 0), ["", ""])
                f = tc.get("function", {})
                c[0] += f.get("name") or ""
                c[1] += f.get("arguments") or ""
    text = reasoning + "</think>\n\n" + content
    for k in sorted(calls):
        text += ("\n" if text and not text.endswith("\n") else "") + call_text(*calls[k])
    tools = []
    for t in req.get("tools", []):
        if "function" in t:
            tools.append({"name": t["function"]["name"], "parameters": t["function"].get("parameters")})
        elif t.get("type") == "function":
            tools.append({"name": t["name"], "parameters": t.get("parameters")})
    return text, tools, len(calls)


def events(cls, text, tools, width=7):
    p, evs = cls(thinking=True, tools=tools), []
    for k in range(0, len(text), width):
        evs += p.feed(text[k:k + width])
    evs += p.finish()
    calls = [(e.call.name, json.dumps(e.call.arguments, sort_keys=True)) for e in evs if e.kind == "tool_call" and e.call]
    reasoning = "".join(e.text or "" for e in evs if e.kind == "reasoning")
    answer = "".join(e.text or "" for e in evs if e.kind == "content")
    return calls, reasoning, answer


tot = {"turns": 0, "same": 0, "recovered": 0, "changed": 0, "width_mismatch": 0}
for d in sorted((WS / "logs/usability/turns").iterdir()):
    if not (d / "index.jsonl").exists() or d.name.split("-")[0] not in ("opencode", "codex", "dsh"):
        continue
    for e in (json.loads(l) for l in open(d / "index.jsonl")):
        if not e["path"].endswith(("/chat/completions", "/responses")) or e.get("status") != 200:
            continue
        rq, rs = d / f"{e['n']:04d}.req.json.gz", d / f"{e['n']:04d}.resp.gz"
        if not rq.exists() or not rs.exists():
            continue
        req = json.loads(gzip.open(rq).read())
        if not req.get("stream", True) or not req.get("tools"):
            continue
        text, tools, _ = rebuild(req, gzip.open(rs).read().decode())
        a, b = events(A, text, tools), events(B, text, tools)
        tot["turns"] += 1
        if any(events(B, text, tools, w) != b for w in (1, 100_000)):
            tot["width_mismatch"] += 1
            print(f"{d.name} #{e['n']}: B's events depend on the chunk width")
        if a == b:
            tot["same"] += 1
            continue
        kind = "recovered" if (not a[0] and b[0]) else "changed"
        tot[kind] += 1
        print(f"{d.name} #{e['n']}: A calls {[c[0] for c in a[0]]} reasoning {len(a[1])} answer {len(a[2])} | "
              f"B calls {[c[0] for c in b[0]]} reasoning {len(b[1])} answer {len(b[2])}  [{kind}]")
        # the split may move, the text may not: reasoning + answer of A and B hold the same characters
        if kind == "changed" or len(a[1]) + len(a[2]) < len(b[1]) + len(b[2]) - 8:
            print("    (check the text)")
print(json.dumps(tot))
