#!/usr/bin/env python3
"""jan-tool-check.py - test chats for Jan's tools (Karl's backlog item, 2026-10-28): is each tool called when it should
be, and not when it should not?

It sends Jan's own assistant instructions (assistants/jan/assistant.json, {{current_date}} filled in as Jan does) and
the full tool list of the MCP servers Jan will run (research, web search, calculator, code) to Strata on 8080 the way Jan
does (OpenAI chat completions with tools), runs the tool calls through the servers, and records which tools the model
called. Safety: the research tools are listed but NEVER run (a stub answers: no research job can start); web search runs
with HOME pointed at an empty folder, so the paid Exa/Tavily fallback finds no key and spends nothing; the calculator runs
in its sandbox; the code tool clones into its own scratch folder. Sampling: T 1.0, top_p 0.95, top_k 20, min_p 0.05,
reasoning effort medium (Jan's "Jan" assistant). Nothing in Jan's own files is changed; no chat is read.

  jan-tool-check.py [--tools-dir DIR] [--only NAME,...]     DIR: where web-mcp.py, calc-mcp.py, code-mcp.py are
Output: results/jan-tools/check-<time>.json and a table on stdout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
VENV_PY = str(WS / ".venv/bin/python")
JAN_ASSISTANT = Path.home() / ".local/share/Jan/data/assistants/jan/assistant.json"
STRATA = "http://127.0.0.1:8080/v1"
OUT = WS / "results" / "jan-tools"
MAX_ROUNDS = 6

CASES = [  # (name, prompt, tools that must be called (any of each group), tools that must NOT be called)
    ("long-page", "Read https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture) to the end and tell me "
                  "the title of the article's last section before the references.", [["fetch_page"]], []),
    ("calc-load", "A model file is 138 GB and my SSD reads 1.8 GB/s. How many minutes does loading it take?",
     [["calculate"]], []),
    ("code-flag", "In the GitHub project Niko1221/Strata at tag v0.2.7, which source file parses the --expert-cache "
                  "command-line option?", [["code_search", "code_read"]], []),
    ("no-2plus2", "What is 2 + 2?", [], ["*"]),
    ("no-define", "In one short paragraph, what is a gigabyte?", [], ["*"]),
    ("no-haiku", "Write a haiku about autumn.", [], ["*"]),
    ("no-date", "What is today's date?", [], ["*"]),
]
RESEARCH_TOOLS_STUB = "(test chat: research tools are not run here)"


class MCP:
    """One MCP server over stdio."""

    def __init__(self, name, cmd, env=None):
        self.name = name
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, env=env)
        self.i = 0
        self.rpc("initialize", {"protocolVersion": "2025-06-18"})
        self.tools = self.rpc("tools/list", {})["tools"]

    def rpc(self, method, params):
        self.i += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.i, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"{self.name} closed")
            msg = json.loads(line)
            if msg.get("id") == self.i:
                return msg.get("result") or {}

    def call(self, tool, args):
        r = self.rpc("tools/call", {"name": tool, "arguments": args})
        return "\n".join(c.get("text", "") for c in r.get("content", []))

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:  # noqa: BLE001
            self.p.kill()


def servers(tools_dir: Path) -> list[MCP]:
    nokeys = tempfile.mkdtemp(prefix="jan-check-home-")      # no exa.key / tavily.key here: no paid search
    env_web = {"HOME": nokeys, "PATH": "/usr/bin:/bin"}
    return [MCP("research", ["/usr/bin/python3", "-I", str(WS / "tools/research-mcp.py")]),
            MCP("web", [VENV_PY, "-I", str(tools_dir / "web-mcp.py")], env=env_web),
            MCP("calc", ["/usr/bin/unshare", "-rn", "/usr/bin/python3", "-I", str(tools_dir / "calc-mcp.py")]),
            MCP("code", [VENV_PY, "-I", str(tools_dir / "code-mcp.py")])]


def chat(model, messages, tools):
    body = {"model": model, "messages": messages, "tools": tools, "temperature": 1.0, "top_p": 0.95, "top_k": 20,
            "min_p": 0.05, "reasoning_effort": "medium", "stream": False}
    req = urllib.request.Request(f"{STRATA}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=900) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools-dir", default=str(WS / "staging/jan-tools"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f"{STRATA}/models", timeout=10) as r:
        model = json.loads(r.read())["data"][0]["id"]
    today = dt.date.today()
    system = json.loads(JAN_ASSISTANT.read_text())["instructions"].replace(
        "{{current_date}}", today.strftime("%A, %B %-d, %Y"))
    srv = servers(Path(a.tools_dir))
    owner, tools = {}, []
    for s in srv:
        for t in s.tools:
            owner[t["name"]] = s
            tools.append({"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                                           "parameters": t.get("inputSchema") or {"type": "object"}}})
    results = []
    try:
        for name, prompt, must, mustnot in CASES:
            if a.only and name not in a.only.split(","):
                continue
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            called, t0, answer = [], time.time(), ""
            for _ in range(MAX_ROUNDS):
                m = chat(model, msgs, tools)["choices"][0]["message"]
                calls = m.get("tool_calls") or []
                if not calls:
                    answer = m.get("content") or ""
                    break
                msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})
                for c in calls:
                    fn = c["function"]["name"]
                    try:
                        args = json.loads(c["function"].get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    called.append({"tool": fn, "args": args})
                    s = owner.get(fn)
                    out = (RESEARCH_TOOLS_STUB if s is None or s.name == "research"
                           else s.call(fn, args))
                    msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": out[:40000]})
            names = [c["tool"] for c in called]
            ok = all(any(g in names for g in grp) for grp in must) and not (
                ("*" in mustnot and names) or any(n in names for n in mustnot if n != "*"))
            results.append({"case": name, "ok": ok, "tools": names, "calls": called, "seconds": round(time.time() - t0),
                            "answer": answer[:1500]})
            print(f"{'OK ' if ok else 'BAD'} {name:10s} {round(time.time() - t0):4d} s  tools: {names or '-'}")
    finally:
        for s in srv:
            s.close()
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"check-{time.strftime('%Y%m%d-%H%M')}.json"
    f.write_text(json.dumps({"model": model, "date_given": str(today), "results": results}, indent=1))
    print(f"{sum(r['ok'] for r in results)} of {len(results)} as expected -> {f}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
