#!/usr/bin/env python3
"""think_quote_replay.py - replay a recorded turn through Strata's OutputParser offline (no GPU).

    .venv/bin/python work/usability/think_quote_replay.py logs/usability/turns/opencode-rt_effort-r1 16 [strata-cstar18]

Rebuilds the model's text (reasoning + "</think>" + content, as the stream split it), feeds it to serve.frontend's
OutputParser as served, then again with every `</think>` except the last one turned into plain text, and prints the
events: shows whether a quoted `</think>` in the reasoning is what kept the turn's tool call from being parsed.
"""
import gzip
import json
import sys
from pathlib import Path

d, n = Path(sys.argv[1]), int(sys.argv[2])
sys.path.insert(0, str(Path(sys.argv[3] if len(sys.argv) > 3 else "strata-cstar18").resolve()))
from serve.frontend import OutputParser  # noqa: E402

req = json.loads(gzip.open(d / f"{n:04d}.req.json.gz").read())
tools = [{"name": t["function"]["name"], "parameters": t["function"].get("parameters")} for t in req.get("tools", [])]
reasoning = content = ""
for line in gzip.open(d / f"{n:04d}.resp.gz").read().decode().splitlines():
    if line.startswith("data: {"):
        for ch in json.loads(line[6:]).get("choices", []):
            delta = ch.get("delta", {})
            reasoning += delta.get("reasoning_content") or ""
            content += delta.get("content") or ""
text = reasoning + "</think>" + content
pos = [i for i in range(len(text)) if text.startswith("</think>", i)]


def run(t):
    p, evs = OutputParser(thinking=True, tools=tools), []
    for k in range(0, len(t), 7):
        evs += p.feed(t[k:k + 7])
    if hasattr(p, "finish"):
        evs += p.finish()
    kinds = {}
    for ev in evs:
        kinds[ev.kind] = kinds.get(ev.kind, 0) + 1
    return kinds


print(f"</think> at {pos} of {len(text)} characters")
for i in pos:
    print("   ", repr(text[max(0, i - 70):i + 20]))
print("as served:", run(text))
alt = text
for i in pos[:-1][::-1]:
    alt = alt[:i] + "</th1nk>" + alt[i + 8:]
print("quoted ones as text, the last one real:", run(alt))
