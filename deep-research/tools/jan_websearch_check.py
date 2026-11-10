#!/usr/bin/env python3
"""jan_websearch_check.py [CASE ...] - the Jan web-search cases through Strata (2026-10-19, the user: "a normal search,
a forced 'search with Exa', and a query where SearXNG comes back empty").

Plays Jan's part without Jan: starts both of Jan's MCP servers the way mcp_config.json does (web-search and
deep-research), offers every tool they list to Strata on 127.0.0.1:8080 (Jan's provider), with Jan's default assistant
instructions as the system message, the user's sampling (1.0 / 0.95 / 20 / min-p 0.05) and reasoning effort medium,
and runs the tool calls the model makes (up to 8 rounds). research_* calls are NOT run here - the test records them
as a wrong tool choice (ask-only) and answers "not run in this test" - so no research job can start.

Case "empty": SearXNG coming back empty cannot be produced by a query (8888's Bing / Yahoo answer even made-up
phrases), so that case's web-search server reads a stand-in on 127.0.0.1:8899 that returns no results
(WEB_MCP_SEARXNG), which takes web_search's "fewer than 5 results" path to Exa, then Tavily.

Per case: the tools called (and arguments), "Answered by" of every search, seconds, the answer -> results/
jan-websearch-check-<date>/<case>.json + .md. Must run in a gap between queue runs (it uses Strata).
"""
from __future__ import annotations

import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
JAN = Path.home() / ".local/share/Jan/data"
STRATA = "http://127.0.0.1:8080/v1/chat/completions"
OUT = WS / "results" / f"jan-websearch-check-{time.strftime('%Y-%m-%d')}"
CASES = {
    "normal": ("What is the latest stable version of the Linux kernel, and when was it released?", {}),
    "exa": ("Search with Exa: what's new in Python 3.14?", {}),
    "empty": ("What are the main findings of the most recent IPCC synthesis report?",
              {"WEB_MCP_SEARXNG": "http://127.0.0.1:8899"}),
    "tavily": ("Search with Tavily: how high is Mount Kilimanjaro?", {}),
}
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}


class Mcp:
    def __init__(self, name: str, env_extra: dict):
        s = json.loads((JAN / "mcp_config.json").read_text())["mcpServers"][name]
        env = {**os.environ, **(s.get("env") or {}), **env_extra}
        self.p = subprocess.Popen([s["command"], *s.get("args", [])], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, env=env, bufsize=1)
        self.n = 0
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "jan-websearch-check", "version": "1"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.tools = self.call("tools/list", {})["tools"]

    def call(self, method: str, params: dict) -> dict:
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        while True:
            m = json.loads(self.p.stdout.readline())
            if m.get("id") == self.n:
                return m.get("result") or {"error": m.get("error")}

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


class EmptySearx(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"query": "", "results": [], "unresponsive_engines": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def chat(messages: list, tools: list) -> dict:
    body = {"model": "strata", "messages": messages, "tools": tools, "tool_choice": "auto", "stream": False,
            "reasoning_effort": "medium", "max_tokens": 4096, **SAMPLING}
    req = urllib.request.Request(STRATA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=900) as r:
        return json.loads(r.read())["choices"][0]["message"]


def run_case(case: str) -> dict:
    ask, env = CASES[case]
    web, res = Mcp("web-search", env), Mcp("deep-research", {})
    owner = {t["name"]: web for t in web.tools} | {t["name"]: res for t in res.tools}
    tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                               "parameters": t.get("inputSchema") or {"type": "object"}}}
             for t in web.tools + res.tools]
    system = json.loads((JAN / "assistants" / "jan" / "assistant.json").read_text()).get("instructions") or ""
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": ask}]
    calls, answered, t0 = [], [], time.time()
    answer = ""
    try:
        for _ in range(8):
            m = chat(messages, tools)
            tc = m.get("tool_calls") or []
            messages.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": tc} if tc
                            else {"role": "assistant", "content": m.get("content") or ""})
            if not tc:
                answer = m.get("content") or ""
                break
            for c in tc:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except ValueError:
                    args = {}
                calls.append({"tool": name, "args": args, "t": round(time.time() - t0, 1)})
                if name.startswith("research_"):
                    text = "Not run in this test (research tools are ask-only)."
                    calls[-1]["wrong_tool"] = True
                else:
                    r = owner[name].call("tools/call", {"name": name, "arguments": args})
                    text = "".join(x.get("text", "") for x in (r.get("content") or []))
                    if name == "web_search":
                        a = re.search(r"^Answered by: (.*)$", text, re.M)
                        answered.append(a.group(1) if a else "?")
                        calls[-1]["answered_by"] = answered[-1]
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": text[:30000]})
    finally:
        web.close()
        res.close()
    return {"case": case, "ask": ask, "seconds": round(time.time() - t0, 1), "tool_calls": calls,
            "answered_by": answered, "wrong_tool": any(c.get("wrong_tool") for c in calls), "answer": answer}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    srv = http.server.HTTPServer(("127.0.0.1", 8899), EmptySearx)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for case in sys.argv[1:] or list(CASES):
        r = run_case(case)
        (OUT / f"{case}.json").write_text(json.dumps(r, indent=1))
        (OUT / f"{case}.md").write_text(f"# {case}: {r['ask']}\n\n{r['answer']}\n")
        tools = ", ".join(f"{c['tool']}({json.dumps(c['args'])[:80]})" for c in r["tool_calls"])
        print(f"{case}: {r['seconds']} s | tools: {tools or 'none'} | answered by: {r['answered_by'] or '-'}"
              f"{' | WRONG TOOL (research_*)' if r['wrong_tool'] else ''} | answer {len(r['answer'])} chars", flush=True)
    srv.shutdown()


if __name__ == "__main__":
    main()
