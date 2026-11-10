#!/usr/bin/env python3
"""toolrecovery_live.py - round 22 (10-29): v0.2.8's tool_call_recovery on our port, live, for a GPU gap.
NOT run when written: it needs a Strata server; run it only inside a gap (see README.md).

    toolrecovery_live.py BASE [--label on] [--reps 3] [--shapes jan,opencode,dsh] [--only ID,...] [--stream 1|0]
                              [--max-tokens N] [--no-seed] [--seed-base N] [--out-dir DIR] [--dry-run]
    toolrecovery_live.py offconfig CONFIG.json [OUT.json]   a copy of CONFIG with "tool_call_recovery": false (own log);
                                                             prints the new file's path (for with_server.sh)
    toolrecovery_live.py compare ON.jsonl OFF.jsonl          per prompt: calls, spurious and lost calls, on vs off

BASE: an OpenAI-compatible endpoint, e.g. http://127.0.0.1:8081 (a trailing /v1 is fine).

Request shapes (OpenAI Chat Completions, streamed as the clients stream them; sampling T 1.0, top_p 0.95, top_k 20,
min_p 0.05 on every request; reasoning effort medium):
  jan       Jan's own assistant instructions (~/.local/share/Jan/data/assistants/jan/assistant.json, {{current_date}}
            filled in as Jan does) and the 15 tools of the MCP servers Jan runs (research 9, web 2, calculator 1,
            code 3), read from their source files without starting them - the approach of
            ~/ai/deep-research/staging/jan-tools/jan-tool-check.py.  No max_tokens (Jan sends none).
  opencode  the coding harness: OpenCode's recorded first request of the usability round (logs/usability/turns/
            client-check-opencode-10171324: its 8.4K-char system prompt, its 10 tools, max_completion_tokens 32768,
            store false, stream_options) - fallback prompts/agentturn.json's system prompt and six tools.
  dsh       DeepSeek Harness Minimal's recorded request (developer message + one bash tool).
Prompts: some must call a tool; the others invite talking about or quoting tool calls (format explanations, a JSON
function-calling example, a pytest file holding call strings, a quote of the previous turn's call, a bug report quoting
a drifted call, reasoning about a call it should not make) and must make NO call.  Their example values carry
markers (EXAMPLE-ONLY-...), so a call made from a quoted example is recognisable.  No tool is ever run: only the first
response of each conversation is read (the "previous call" of the quote prompts is written into the history).

Per response: the calls (name, arguments, valid JSON, required keys), finish_reason, the visible text and reasoning,
and the server's /metrics totals before and after (tool_calls_unread, tool_args_repaired, tool_calls_from_reasoning,
stray_think_closers).  Verdicts:
  must call:  OK | LOST (call markup left in the text, no call) | LOST? (markup at the end of the thinking, no answer)
              | NO CALL (the model answered without one) | WRONG TOOL | BAD ARGS | + SPURIOUS EXTRA (a call made from
              a quoted sample) | + LEAK (closing tags in the text after the call: an argument cut short?)
  must not:   OK | SPURIOUS (QUOTE) (a call carrying the example's marker: a quote became a call) | SPURIOUS (a call
              the prompt said not to make; the model's choice or the parser - compare with recovery off)
  any:        FINISH (finish_reason does not fit the calls) | CUT (finish_reason length) | ERROR
Seeds: by default each (prompt, repeat) gets the same seed in every arm, so the recovery-on and -off arms read the
same model text when the engine reproduces it (compare reports how many responses match); --no-seed sends none, as
the clients do.
Output: OUT_DIR/live-LABEL-<time>.jsonl (one line per response) and .txt (the printed lines and the summary).
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
HERE = WS / "work/r22/toolrecovery"
DR = Path("/home/USER/ai/deep-research")
JAN_ASSISTANT = Path.home() / ".local/share/Jan/data/assistants/jan/assistant.json"
JAN_TOOL_DIRS = [DR / "tools", DR / "staging/jan-tools"]          # installed first (10-28), staged copy as fallback
JAN_SERVERS = ["research-mcp.py", "web-mcp.py", "calc-mcp.py", "code-mcp.py"]   # jan-tool-check.py's order
OPENCODE_REQ = WS / "logs/usability/turns/client-check-opencode-10171324/0001.req.json.gz"
DSH_REQ = WS / "logs/usability/turns/client-check-dsh-minimal-10171324/0001.req.json.gz"
AGENTTURN = WS / "prompts/agentturn.json"
NORMAL = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
METRIC_KEYS = ("tool_calls_unread", "tool_args_repaired", "tool_calls_from_reasoning", "stray_think_closers")
TIMEOUT_S = 1800


# ------------------------------------------------------------------------------------------------ request shapes
def _assigns(path: Path) -> list[ast.Assign]:
    return [n for n in ast.parse(path.read_text()).body
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)]


def _static_value(path: Path, name: str, ns: dict):
    """The module-level `name` of a source file, evaluated from its own assignments only (the module is not imported,
    so no server starts and nothing is opened): the assignments `name` depends on run in file order in `ns`."""
    nodes = _assigns(path)
    by = {n.targets[0].id: n for n in nodes}
    need, stack = set(), [name]
    while stack:
        k = stack.pop()
        if k in need or k not in by:
            continue
        need.add(k)
        stack += [s.id for s in ast.walk(by[k].value) if isinstance(s, ast.Name)]
    for n in nodes:
        if n.targets[0].id in need:
            exec(compile(ast.Module(body=[n], type_ignores=[]), str(path), "exec"), ns)     # noqa: S102 - Karl's files
    return ns[name]


def jan_shape(today: dt.date):
    system = json.loads(JAN_ASSISTANT.read_text())["instructions"].replace(
        "{{current_date}}", today.strftime("%A, %B %-d, %Y"))
    tools = []
    for fname in JAN_SERVERS:
        src = next((d / fname for d in JAN_TOOL_DIRS if (d / fname).exists()), None)
        if src is None:
            raise SystemExit(f"jan shape: {fname} not found in {[str(d) for d in JAN_TOOL_DIRS]}")
        ns: dict = {}
        tc = src.parent / "tool_choice.py"
        if tc.exists():
            for n in _assigns(tc):
                exec(compile(ast.Module(body=[n], type_ignores=[]), str(tc), "exec"), ns)    # noqa: S102
        for t in _static_value(src, "TOOLS", ns):
            tools.append({"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                                           "parameters": t.get("inputSchema") or {"type": "object"}}})
    return [{"role": "system", "content": system}], tools, {"reasoning_effort": "medium"}


def _recorded(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def opencode_shape(today: dt.date):
    if OPENCODE_REQ.exists():
        b = _recorded(OPENCODE_REQ)
        sys_msgs = [m for m in b["messages"] if m["role"] in ("system", "developer")]
        for m in sys_msgs:
            if isinstance(m.get("content"), str):
                m["content"] = re.sub(r"Today's date: .*", f"Today's date: {today.strftime('%a %b %d %Y')}", m["content"])
        extra = {k: b[k] for k in ("stream_options", "max_completion_tokens", "store") if k in b}
        extra["reasoning_effort"] = "medium"
        return sys_msgs, b["tools"], extra
    w = json.loads(AGENTTURN.read_text())[0]
    return [w["messages"][0]], w["tools"], {"max_tokens": w["max_tokens"], "reasoning_effort": "medium"}


def dsh_shape(today: dt.date):
    b = _recorded(DSH_REQ)
    sys_msgs = [m for m in b["messages"] if m["role"] in ("system", "developer")]
    extra = {k: b[k] for k in ("stream_options", "max_completion_tokens", "store") if k in b}
    extra["reasoning_effort"] = "medium"
    return sys_msgs, b["tools"], extra


SHAPES = {"jan": jan_shape, "opencode": opencode_shape, "dsh": dsh_shape}


# ------------------------------------------------------------------------------------------------ prompts
def prev_call(call_id, name, args, result, said):
    """History: the user's earlier question, the assistant's call, the tool's result, the assistant's answer."""
    def h(question):
        return [{"role": "user", "content": question},
                {"role": "assistant", "content": "", "tool_calls": [{"id": call_id, "type": "function",
                                                                     "function": {"name": name, "arguments": json.dumps(args)}}]},
                {"role": "tool", "tool_call_id": call_id, "content": result},
                {"role": "assistant", "content": said}]
    return h


P = []


def prompt(shape, pid, expect, text, want=(), markers=(), marker_ok=(), history=None, why=""):
    P.append(dict(shape=shape, id=pid, expect=expect, text=text, want=list(want), markers=list(markers),
                  marker_ok=list(marker_ok), history=history, why=why))


# ---- Jan
prompt("jan", "j-calc", "call", "A model file is 138 GB and my SSD reads 1.8 GB/s. How many minutes does loading it take?",
       want=["calculate"], why="jan-tool-check's calculator case")
prompt("jan", "j-search", "call", "What is the newest stable Linux kernel release right now, and when did it come out? "
       "Look it up, don't answer from memory.", want=["web_search", "fetch_page", "research_quick"])
prompt("jan", "j-fetch", "call", "Open https://www.kernel.org/ and tell me which version it lists as latest stable.",
       want=["fetch_page", "web_search"])
prompt("jan", "j-code", "call", "In the GitHub project Niko1221/Strata at tag v0.2.7, which source file parses the "
       "--expert-cache command-line option?", want=["code_search", "code_read", "github"], why="jan-tool-check's code case")
prompt("jan", "j-explain-raw", "none", "Do not use any tools for this one. How do you call a tool in this chat, exactly? "
       "Write out in your reply the exact raw text you produce to call web_search with the query EXAMPLE-ONLY-7731, then "
       "explain each tag.", markers=["EXAMPLE-ONLY-7731"], why="explaining the format with the raw call text")
prompt("jan", "j-explain-unfenced", "none", "No tools please - just explain. In plain prose, describe how a model writes a "
       "tool call in the Qwen XML format: the <tool_call> wrapper, the <function=NAME> tag and the <parameter=NAME> tags. "
       "Give one example, a call of calculate with the expression 6*7-EXAMPLE-ONLY, written out on lines of its own and "
       "not in a code block.", markers=["EXAMPLE-ONLY"], why="the example outside a code fence (offline: a call)")
prompt("jan", "j-json-example", "none", "I'm writing documentation about OpenAI-style function calling. Without calling "
       "any tool, give me a JSON example of the model's function call to fetch_page for https://example.invalid/"
       "EXAMPLE-ONLY-8812, and explain each field.", markers=["EXAMPLE-ONLY-8812"], why="a JSON function-calling example")
prompt("jan", "j-hermes-inline", "none", "Some models write their tool calls as JSON inside <tool_call> tags instead of "
       "XML. Without calling anything, show me what that would look like for web_search with the query EXAMPLE-ONLY-5520 "
       "- inline, inside a sentence, not in a code block - and say how it differs from the XML form.",
       markers=["EXAMPLE-ONLY-5520"], why="JSON in <tool_call> in prose (offline: a call with recovery on)")
prompt("jan", "j-decide-not", "none", "What is 17 + 25? Think about whether calling the calculate tool is worth it here "
       "and mention what that call would look like, but answer without calling any tool.",
       why="reasoning about a call it should not make")
prompt("jan", "j-quote-previous", "none", "Quote, word for word, the exact raw tool call you wrote in your previous turn - "
       "the full text with its tags - and then explain it. Do not call any tool now.", markers=["EXAMPLE-PREV-3391"],
       history=prev_call("call_prev1", "web_search", {"query": "EXAMPLE-PREV-3391 Strata v0.2.8 release notes"},
                         "1. Strata v0.2.8 release notes (example result)\n   https://example.invalid/strata/v0.2.8",
                         "I found the release notes page for Strata v0.2.8."),
       why="an answer quoting a previous call")
prompt("jan", "j-python-test", "none", "Write a pytest test in your reply (not as a file) for a function "
       "parse_calls(text) that finds tool calls in model output: the XML form <tool_call><function=calculate><parameter="
       "expression>EXAMPLE-ONLY-2+2</parameter></function></tool_call> and the JSON form {\"name\": \"calculate\", "
       "\"arguments\": {\"expression\": \"EXAMPLE-ONLY-2+2\"}}. Don't call any tools.", markers=["EXAMPLE-ONLY-2+2"],
       why="a Python test holding call strings")
prompt("jan", "j-template-turn", "none", "Without using tools: show me what one whole assistant turn of yours looks like "
       "as raw text - the <think> block with one line of reasoning, then a call of web_search for EXAMPLE-ONLY-4410 - "
       "and explain the parts.", markers=["EXAMPLE-ONLY-4410"],
       why="a whole example turn with </think> (offline: the stray-</think> rule turns a fenced one into a call)")
# ---- the coding harness (OpenCode)
prompt("opencode", "o-read", "call", "Read README.md and tell me its first line.", want=["read"])
prompt("opencode", "o-shell", "call", "Run `git status --short` and tell me what it shows.", want=["shell"])
prompt("opencode", "o-write-test", "call", "Create tests/test_toolparse.py: a pytest file for a function parse_calls(text) "
       "in toolparse.py (not written yet). Its sample strings must hold a Qwen-style tool call (<tool_call>, "
       "<function=read>, <parameter=path>, EXAMPLE-ONLY.txt, </parameter>, </function>, </tool_call>, each on a line of "
       "its own in a triple-quoted string), the same call without the <tool_call> wrapper, and a JSON call "
       "{\"name\": \"read\", \"arguments\": {\"path\": \"EXAMPLE-ONLY.txt\"}}. Write the file with the write tool now; "
       "don't read or run anything.", want=["write"], markers=["EXAMPLE-ONLY"], marker_ok=["write"],
       why="a real write whose content quotes calls in every form")
prompt("opencode", "o-write-template-test", "call", "Create tests/test_template.py: a pytest test that renders a chat turn "
       "and checks that the reasoning sits between <think> and </think> (each tag on a line of its own in a "
       "triple-quoted string) before a <tool_call> block that calls read on EXAMPLE-ONLY.txt. Write it with the write "
       "tool now, without reading anything first.", want=["write"], markers=["EXAMPLE-ONLY"], marker_ok=["write"],
       why="the usability round's lost-calls shape: </think> in a test the model drafts while thinking")
prompt("opencode", "o-write-doc", "call", "Write docs/TOOL_FORMAT.md documenting our tool-call format: the XML form, the "
       "JSON form inside <tool_call>, and the bare <function=...> form, each with an example that calls read on "
       "EXAMPLE-ONLY.txt, and then the closing tags listed in order, one per line. Use the write tool now.",
       want=["write"], markers=["EXAMPLE-ONLY"], marker_ok=["write"],
       why="a real write of a format doc (offline: closers on lines of their own cut the value short)")
prompt("opencode", "o-explain-raw", "none", "Don't call any tools. In your answer, show me the exact raw text you emit to "
       "call the read tool on EXAMPLE-ONLY.txt, then explain it.", markers=["EXAMPLE-ONLY"])
prompt("opencode", "o-test-in-answer", "none", "Don't use tools and don't write files: paste in your answer a pytest file "
       "that tests parse_calls(text) with sample strings containing <tool_call>, <function=read> and <parameter=path> "
       "for EXAMPLE-ONLY.txt, plus the JSON form.", markers=["EXAMPLE-ONLY"])
prompt("opencode", "o-test-unfenced", "none", "Without tools: give me the contents of a pytest file testing "
       "parse_calls(text) with a sample Qwen tool call (read, path EXAMPLE-ONLY.txt) in a triple-quoted string. Print "
       "the file as plain text, NOT inside a Markdown code block.", markers=["EXAMPLE-ONLY"],
       why="file content outside a fence (offline: calls, baseline and recovery)")
prompt("opencode", "o-quote-previous", "none", "Show me, verbatim, the raw tool call you emitted in your last turn. Don't "
       "call any tool.", markers=["EXAMPLE-PREV-3391"],
       history=prev_call("call_prev2", "read", {"path": "EXAMPLE-PREV-3391.txt"}, "1\tfirst line of the example file\n",
                         "The file's first line is: first line of the example file."))
prompt("opencode", "o-bug-report", "none", "Write a short bug report (in your answer, no tools) about a model that wrote "
       "its tool call as <tool_call> followed by <parameter=read> instead of <function=read>. Quote the broken output "
       "exactly, with path EXAMPLE-ONLY.txt, on lines of their own.", markers=["EXAMPLE-ONLY"],
       why="quoting a drifted call (offline: a call with recovery on when unfenced)")
prompt("opencode", "o-nested-doc", "none", "Without tools: give me the full text of a docs/TOOLS.md file, inside a "
       "four-backtick ````markdown block so its inner code blocks survive, with an XML example and a JSON example of a "
       "call to read on EXAMPLE-ONLY.txt.", markers=["EXAMPLE-ONLY"],
       why="nested fences (offline: the inner ``` closes the outer fence)")
# ---- DeepSeek Harness Minimal (one bash tool)
prompt("dsh", "d-ls", "call", "List the files in the repository root and tell me how many there are.", want=["bash"])
prompt("dsh", "d-write-test", "call", "Create tests/test_toolparse.py with a heredoc: a pytest file whose sample strings "
       "hold a Qwen tool call (<tool_call>, <function=read>, <parameter=path>, EXAMPLE-ONLY.txt and the closing tags) on "
       "lines of their own. Do it now with one bash command.", want=["bash"], markers=["EXAMPLE-ONLY"], marker_ok=["bash"])
prompt("dsh", "d-explain-raw", "none", "Don't run any commands. Show me the exact raw text you emit to call bash with the "
       "command echo EXAMPLE-ONLY-6620, and explain it.", markers=["EXAMPLE-ONLY-6620"])
prompt("dsh", "d-json-example", "none", "No commands: show a JSON example of a function call to bash running "
       "`echo EXAMPLE-ONLY-6621`, in the OpenAI function-calling format, and explain the fields.",
       markers=["EXAMPLE-ONLY-6621"])


# ------------------------------------------------------------------------------------------------ HTTP
def _open(req, timeout):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout)


def v1(base: str) -> str:
    base = base.rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def root(base: str) -> str:
    return re.sub(r"/v1/?$", "", base.rstrip("/"))


def metrics(base: str) -> dict | None:
    try:
        with _open(urllib.request.Request(root(base) + "/metrics"), 20) as r:
            t = json.loads(r.read()).get("totals") or {}
        return {k: t.get(k, 0) for k in METRIC_KEYS}
    except Exception:       # noqa: BLE001 - another server may have no /metrics; the counters are extra
        return None


def ask(base: str, body: dict) -> dict:
    req = urllib.request.Request(v1(base) + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    calls, content, reasoning, finish, err, usage, extra = {}, [], [], None, None, None, {}
    t0 = time.monotonic()
    try:
        with _open(req, TIMEOUT_S) as r:
            if not body.get("stream"):
                d = json.loads(r.read())
                ch = (d.get("choices") or [{}])[0]
                m = ch.get("message") or {}
                content.append(m.get("content") or "")
                reasoning.append(m.get("reasoning_content") or "")
                finish, usage = ch.get("finish_reason"), d.get("usage")
                for i, tc in enumerate(m.get("tool_calls") or []):
                    f = tc.get("function") or {}
                    calls[i] = {"id": tc.get("id"), "name": f.get("name") or "", "args": f.get("arguments") or ""}
                extra = {k: v for k, v in d.items() if k.startswith("strata_")}
            else:
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
                        err = str(ev["error"])[:300]
                    extra.update({k: v for k, v in ev.items() if k.startswith("strata_")})
                    usage = ev.get("usage") or usage
                    for ch in ev.get("choices") or []:
                        d = ch.get("delta") or {}
                        content.append(d.get("content") or "")
                        reasoning.append(d.get("reasoning_content") or "")
                        for tc in d.get("tool_calls") or []:
                            c = calls.setdefault(tc.get("index", 0), {"id": None, "name": "", "args": ""})
                            c["id"] = tc.get("id") or c["id"]
                            f = tc.get("function") or {}
                            c["name"] += f.get("name") or ""
                            c["args"] += f.get("arguments") or ""
                        if ch.get("finish_reason"):
                            finish = ch["finish_reason"]
    except urllib.error.HTTPError as e:
        err = f"HTTP {e.code}: {e.read()[:300]!r}"
    except Exception as e:                      # noqa: BLE001 - an HTTP failure is a result here
        err = f"{type(e).__name__}: {e}"[:300]
    return {"calls": [calls[k] for k in sorted(calls)], "content": "".join(content), "reasoning": "".join(reasoning),
            "finish": finish, "error": err, "usage": usage, "extra": extra, "secs": round(time.monotonic() - t0, 1)}


# ------------------------------------------------------------------------------------------------ verdicts
def markup_re(names):
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) or "(?!)"
    return re.compile(r"<tool_call>|</tool_call>|<function\s*[=:]|<parameter=|</function>|"
                      r"\{\s*\"name\"\s*:\s*\"(?:" + alt + r")\"\s*,\s*\"(?:arguments|parameters)\"")


CLOSERS_LEFT = re.compile(r"</parameter>\s*</function>\s*(?:</tool_call>)?\s*$")


def judge(p, res, tools) -> tuple[str, list[str], list[dict]]:
    """(verdict, flags, parsed calls) for one response."""
    schema = {t["function"]["name"]: t["function"].get("parameters") or {} for t in tools}
    mk = markup_re(schema)
    flags, parsed = [], []
    for c in res["calls"]:
        try:
            a = json.loads(c["args"] or "{}")
            ok_json = isinstance(a, dict)
        except ValueError:
            a, ok_json = None, False
        req = (schema.get(c["name"]) or {}).get("required") or []
        missing = [k for k in req if not (isinstance(a, dict) and k in a)]
        blob = c["args"] or ""
        parsed.append({"name": c["name"], "declared": c["name"] in schema, "json_ok": ok_json, "missing": missing,
                       "marker": any(m in blob for m in p["markers"]), "markup_in_args": bool(mk.search(blob)),
                       "args_chars": len(blob), "args": blob[:4000]})
    text_markup = bool(mk.search(res["content"]))
    tail_markup = not res["content"].strip() and bool(mk.search(res["reasoning"][-1500:]))
    if res["error"]:
        return "ERROR", [res["error"]], parsed
    if p["expect"] == "call":
        good = [c for c in parsed if c["name"] in p["want"]]
        extra_quote = [c for c in parsed if c["marker"] and c["name"] not in p["marker_ok"]]
        if good and all(c["json_ok"] and not c["missing"] for c in good):
            verdict = "OK"
        elif good:
            verdict = "BAD ARGS"
        elif parsed:
            verdict = "WRONG TOOL"
        elif text_markup:
            verdict = "LOST"
        elif tail_markup:
            verdict = "LOST?"
        else:
            verdict = "NO CALL"
        if extra_quote:
            flags.append(f"SPURIOUS EXTRA: {[c['name'] for c in extra_quote]} carry the quoted example's marker")
        if parsed and CLOSERS_LEFT.search(res["content"].strip()):
            flags.append("LEAK: closing tags left in the text after the call (an argument cut short?)")
        if p["marker_ok"] and good and not any(c["markup_in_args"] for c in good):
            flags.append("the written content holds no call markup (asked for; cut short?)")
    else:
        if not parsed:
            verdict = "OK"
        elif any(c["marker"] for c in parsed):
            verdict = "SPURIOUS (QUOTE)"
        else:
            verdict = "SPURIOUS"
        flags.append("exercised: the text quotes markup or the marker (or a call carries it)" if text_markup or
                     any(m in res["content"] for m in p["markers"]) or any(c["marker"] for c in parsed)
                     else "not exercised: no markup/marker in the text")
    if parsed and res["finish"] != "tool_calls":
        flags.append(f"FINISH {res['finish']!r} with {len(parsed)} call(s)")
    if not parsed and res["finish"] == "tool_calls":
        flags.append("FINISH 'tool_calls' without a call")
    if res["finish"] == "length":
        flags.append("CUT at max_tokens")
    if res["extra"].get("strata_rejected_tool_calls"):
        flags.append(f"server rejected calls: {res['extra']['strata_rejected_tool_calls']}")
    return verdict, flags, parsed


# ------------------------------------------------------------------------------------------------ run
def build_body(p, shape_cache, args, rep):
    sys_msgs, tools, extra = shape_cache[p["shape"]]
    msgs = [dict(m) for m in sys_msgs]
    if p["history"]:
        msgs += p["history"]("Find the release notes." if p["shape"] == "jan" else "What does the example file say?")
    msgs.append({"role": "user", "content": p["text"]})
    body = {"model": args.model, "messages": msgs, "tools": tools, "stream": bool(args.stream), **NORMAL, **extra}
    if not args.stream:
        body.pop("stream_options", None)
    if args.max_tokens:
        body.pop("max_completion_tokens", None)
        body["max_tokens"] = args.max_tokens
    if not args.no_seed:
        body["seed"] = args.seed_base + (zlib.crc32(p["id"].encode()) % 100000) * 16 + rep
    return body


def summary_lines(rows):
    out = []
    for shape in dict.fromkeys(r["shape"] for r in rows):
        for expect in ("call", "none"):
            rs = [r for r in rows if r["shape"] == shape and r["expect"] == expect]
            if not rs:
                continue
            cnt: dict = {}
            for r in rs:
                cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
            fl = sum(1 for r in rs for f in r["flags"] if f.startswith(("SPURIOUS EXTRA", "LEAK", "FINISH", "CUT")))
            ex = sum(1 for r in rs if any(f.startswith("exercised") for f in r["flags"]))
            out.append(f"  {shape:8} {'must call' if expect == 'call' else 'must not ':9} {len(rs):3} responses: " +
                       ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())) +
                       (f"; quoting exercised in {ex}" if expect == "none" else "") + (f"; {fl} flag(s)" if fl else ""))
    spur = sum(1 for r in rows if r["verdict"].startswith("SPURIOUS") or any(f.startswith("SPURIOUS") for f in r["flags"]))
    lost = sum(1 for r in rows if r["verdict"].startswith("LOST"))
    out.append(f"  TOTAL {len(rows)} responses: {spur} with a spurious call, {lost} with a lost call, "
               f"{sum(1 for r in rows if r['verdict'] == 'ERROR')} errors")
    return out


def run(args) -> int:
    today = dt.date.today()
    shapes = [s for s in args.shapes.split(",") if s]
    cache = {s: SHAPES[s](today) for s in shapes}
    sel = [p for p in P if p["shape"] in shapes and (not args.only or p["id"] in args.only.split(","))]
    if args.dry_run:
        for s in shapes:
            sm, tools, extra = cache[s]
            print(f"{s}: {len(sm)} system/developer message(s), {sum(len(m['content']) for m in sm if isinstance(m['content'], str))}"
                  f" chars; {len(tools)} tools {[t['function']['name'] for t in tools]}; {len(json.dumps(tools))} chars of "
                  f"tool JSON; extra {extra}")
        for p in sel:
            b = build_body(p, cache, args, 0)
            print(f"  {p['shape']:8} {p['id']:24} {p['expect']:4} {len(json.dumps(b)):6} chars, {len(b['messages'])} msgs, "
                  f"seed {b.get('seed')}")
        print(f"{len(sel)} prompts x {args.reps} repeats = {len(sel) * args.reps} requests (dry run: nothing sent)")
        return 0
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    jl, tx = out_dir / f"live-{args.label}-{stamp}.jsonl", out_dir / f"live-{args.label}-{stamp}.txt"

    def say(s):
        print(s, flush=True)
        with open(tx, "a") as f:
            f.write(s + "\n")
    say(f"toolrecovery_live {args.label}: {base_desc(args)}; {len(sel)} prompts x {args.reps} = {len(sel) * args.reps} "
        f"requests; shapes {shapes}; stream {int(args.stream)}; seeds {'off' if args.no_seed else args.seed_base}")
    rows = []
    for p in sel:
        for rep in range(args.reps):
            body = build_body(p, cache, args, rep)
            m0 = metrics(args.base)
            res = ask(args.base, body)
            m1 = metrics(args.base)
            md = {k: m1[k] - m0[k] for k in METRIC_KEYS if m1[k] != m0[k]} if m0 and m1 else None
            verdict, flags, parsed = judge(p, res, cache[p["shape"]][1])
            row = {"label": args.label, "shape": p["shape"], "id": p["id"], "expect": p["expect"], "rep": rep,
                   "seed": body.get("seed"), "verdict": verdict, "flags": flags, "calls": parsed,
                   "finish": res["finish"], "secs": res["secs"], "usage": res["usage"], "metrics_delta": md,
                   "error": res["error"], "content": res["content"], "reasoning": res["reasoning"][-20000:],
                   "reasoning_chars": len(res["reasoning"]), "extra": res["extra"]}
            rows.append(row)
            with open(jl, "a") as f:
                f.write(json.dumps(row) + "\n")
            say(f"{args.label} {p['shape']:8} {p['id']:22} r{rep} {verdict:16} calls {[c['name'] for c in parsed]} "
                f"finish {res['finish']} {res['secs']:6.1f} s" + (f" server {md}" if md else "") +
                (" | " + "; ".join(flags) if flags else ""))
    say("SUMMARY " + args.label)
    for line in summary_lines(rows):
        say(line)
    say(f"results: {jl}")
    return 0


def base_desc(args):
    return f"{args.base} (model {args.model})"


# ------------------------------------------------------------------------------------------------ offconfig / compare
def offconfig(src: str, dst: str | None) -> int:
    s = Path(src).resolve()
    cfg = json.loads(s.read_text())
    was = cfg.get("tool_call_recovery", "absent (= on since 0.2.8)")
    srv = Path(cfg.get("server") or "")
    if not srv.is_file() or "tool_call_recovery_setting" not in srv.read_text():
        print(f"WARNING: the config's server {srv} has no tool_call_recovery switch (a pre-0.2.8 tree?)", file=sys.stderr)
    cfg["tool_call_recovery"] = False
    if cfg.get("log"):
        lp = Path(cfg["log"])
        cfg["log"] = str(lp.with_name(lp.stem + "-norecovery" + lp.suffix))
    cfg["_comment"] = (cfg.get("_comment", "") + f" | toolrecovery (10-29): copy of {s.name} with tool_call_recovery false "
                       "(the comparison arm)").lstrip(" |")
    out = Path(dst) if dst else HERE / "configs" / (s.stem + "-norecovery.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cfg, indent=1) + "\n")
    print(f"source {s.name}: tool_call_recovery {was}", file=sys.stderr)
    print(out)
    return 0


def load(path):
    return [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]


def compare(on_path: str, off_path: str) -> int:
    on, off = load(on_path), load(off_path)
    key = lambda r: (r["shape"], r["id"], r["rep"])     # noqa: E731
    offk = {key(r): r for r in off}
    def same_output(a, b):
        """The model wrote the same text in both arms (same seed): the same token count and the same reasoning.  The
        visible text may still differ - that is the parser's doing (markup read as a call on one side only)."""
        return ((a.get("usage") or {}).get("completion_tokens") == (b.get("usage") or {}).get("completion_tokens")
                and a.get("reasoning") == b.get("reasoning"))
    paired = sum(1 for r in on if key(r) in offk)
    same = sum(1 for r in on if key(r) in offk and same_output(r, offk[key(r)]))
    print(f"on: {on_path}\noff: {off_path}\n{paired} paired responses; {same} with the same model output in both arms "
          "(same seed: the differences there are the parser's)\n")
    print(f"| shape | prompt | expect | on: verdicts | off: verdicts | on calls / off calls |")
    print("|---|---|---|---|---|---|")
    ids = list(dict.fromkeys((r["shape"], r["id"], r["expect"]) for r in on + off))
    for shape, pid, expect in ids:
        a = [r for r in on if (r["shape"], r["id"]) == (shape, pid)]
        b = [r for r in off if (r["shape"], r["id"]) == (shape, pid)]
        va = ", ".join(r["verdict"] for r in a) or "-"
        vb = ", ".join(r["verdict"] for r in b) or "-"
        print(f"| {shape} | {pid} | {expect} | {va} | {vb} | {sum(len(r['calls']) for r in a)} / "
              f"{sum(len(r['calls']) for r in b)} |")
    print()
    # the paired cases where recovery made the difference: same seed, a call on one side only
    for r in on:
        o = offk.get(key(r))
        if not o:
            continue
        n_on, n_off = len(r["calls"]), len(o["calls"])
        if n_on != n_off:
            kind = ("recovery WON a call" if r["expect"] == "call" else "recovery MADE a spurious call") if n_on > n_off \
                else ("recovery LOST a call" if r["expect"] == "call" else "recovery removed a call")
            print(f"{r['shape']} {r['id']} r{r['rep']}: on {[c['name'] for c in r['calls']]} vs off "
                  f"{[c['name'] for c in o['calls']]} - {kind} "
                  f"({'same model output' if same_output(r, o) else 'the model output differs: not a clean pair'})")
    for lab, rows in (("on", on), ("off", off)):
        print(f"\nSUMMARY {lab}")
        for line in summary_lines(rows):
            print(line)
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["offconfig"]:
        if len(argv) not in (2, 3):
            raise SystemExit("offconfig CONFIG.json [OUT.json]")
        return offconfig(argv[1], argv[2] if len(argv) > 2 else None)
    if argv[:1] == ["compare"]:
        if len(argv) != 3:
            raise SystemExit("compare ON.jsonl OFF.jsonl")
        return compare(argv[1], argv[2])
    ap = argparse.ArgumentParser(description="v0.2.8 tool_call_recovery, live (see the module docstring)")
    ap.add_argument("base", nargs="?", default="http://127.0.0.1:8081")
    ap.add_argument("--label", default="on")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--shapes", default="jan,opencode,dsh")
    ap.add_argument("--only", default="")
    ap.add_argument("--stream", type=int, default=1, choices=(0, 1))
    ap.add_argument("--max-tokens", type=int, default=0, help="override the shape's own cap (0: the client's own)")
    ap.add_argument("--model", default="strata-qwen3.8-flash-next-iq3s")
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--seed-base", type=int, default=2810000)
    ap.add_argument("--out-dir", default=str(HERE / "results"))
    ap.add_argument("--dry-run", action="store_true", help="build every request and print its size; send nothing")
    a = ap.parse_args(argv)
    bad = [s for s in a.shapes.split(",") if s and s not in SHAPES]
    if bad:
        raise SystemExit(f"unknown shape(s) {bad}; known: {list(SHAPES)}")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
