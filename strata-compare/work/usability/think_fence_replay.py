#!/usr/bin/env python3
"""think_fence_replay.py - replay every recorded chat turn of the usability round through Strata's OutputParser offline
(no GPU): as served, and with a candidate fix - a `</think>` inside a code fence or inline code in the reasoning is
quoted text, like the `<tool_call>` rule of #804/#1058 (today only #537's "right after a quote or backtick" applies).

    .venv/bin/python work/usability/think_fence_replay.py [strata-cstar18] [A|B|C]   (A: fence or inline code, B: no line break after, C: fence only)

Each turn's model text is rebuilt as reasoning + "</think>" + content + its parsed tool calls in the template's form
(<tool_call><function=...><parameter=...>), so turns that parsed fine are in the set too (the regression check).
Responses-API turns (Codex) are rebuilt the same way from their reasoning/output_text/function_call items.
Prints, per run, the turns whose events differ between the two parsers, and the totals.
"""
import gzip
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str((WS / (sys.argv[1] if len(sys.argv) > 1 else "strata-cstar18")).resolve()))
from serve.frontend import OutputParser  # noqa: E402


class NoBreakAfter(OutputParser):
    """Rule B: a `</think>` followed by anything but a line break is quoted, whatever comes before it (#537 asks for
    a quote or backtick before it too)."""
    def _quoted_think_end(self, i):
        after = self.buf[i + 8:]
        if not after:
            return None
        return after[0] not in "\r\n"


class FenceOnly(OutputParser):
    """Rule C: a `</think>` inside a code fence (``` or ~~~) of the reasoning is quoted; inline code does not count."""
    def _quoted_think_end(self, i):
        r = super()._quoted_think_end(i)
        if r is not False:
            return r
        snap = (self.fence, self.line, self.ticks)
        self._track(self.buf[:i])
        inside = bool(self.fence)
        self.fence, self.line, self.ticks = snap
        return inside


class FenceAware(OutputParser):
    def _quoted_think_end(self, i):
        r = super()._quoted_think_end(i)
        if r is not False:
            return r
        snap = (self.fence, self.line, self.ticks)
        self._track(self.buf[:i])
        inside = self._in_code()
        self.fence, self.line, self.ticks = snap
        return inside


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


def events(cls, text, tools):
    p, evs = cls(thinking=True, tools=tools), []
    for k in range(0, len(text), 7):
        evs += p.feed(text[k:k + 7])
    if hasattr(p, "finish"):
        evs += p.finish()
    calls = [(e.call.name if e.call else None) for e in evs if e.kind == "tool_call"]
    reasoning = "".join(e.text or "" for e in evs if e.kind == "reasoning")
    answer = "".join(e.text or "" for e in evs if e.kind == "content")
    return calls, len(reasoning), len(answer)


RULE = {"A": FenceAware, "B": NoBreakAfter, "C": FenceOnly}[sys.argv[2] if len(sys.argv) > 2 else "A"]
tot = {"turns": 0, "same": 0, "fixed": 0, "changed": 0}
for d in sorted((WS / "logs/usability/turns").iterdir()):
    if not (d / "index.jsonl").exists() or not d.name.split("-")[0] in ("opencode", "codex", "dsh"):
        continue
    idx = [json.loads(l) for l in open(d / "index.jsonl")]
    for e in idx:
        if not e["path"].endswith(("/chat/completions", "/responses")) or e.get("status") != 200:
            continue
        rq, rs = d / f"{e['n']:04d}.req.json.gz", d / f"{e['n']:04d}.resp.gz"
        if not rq.exists() or not rs.exists():
            continue
        req = json.loads(gzip.open(rq).read())
        if not req.get("stream", True) or not req.get("tools"):
            continue
        text, tools, ncalls = rebuild(req, gzip.open(rs).read().decode())
        a = events(OutputParser, text, tools)
        b = events(RULE, text, tools)
        tot["turns"] += 1
        if a == b:
            tot["same"] += 1
            continue
        kind = "fixed" if (not a[0] and b[0]) else "changed"
        tot[kind] += 1
        print(f"{d.name} #{e['n']}: served calls {a[0]} reasoning {a[1]} answer {a[2]} | rule calls {b[0]} "
              f"reasoning {b[1]} answer {b[2]}  [{kind}]")
print(json.dumps(tot))
