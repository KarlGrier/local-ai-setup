#!/usr/bin/env python3
"""conc_prompts.py - 2026-10-14 D (concurrency test): the two prompt sets, 8 different requests each.

  decode  short prompt, long answer (the decode screen's kind): the screen's three longreason prompts (math, code,
          puzzle) + five of the suite's coding items; max_tokens 4,096 (thinking counts), the user's sampling.
  agent   a coding agent's turn after it has read files: a ~1,900-token system prompt with seven tool definitions,
          the task, and several read_file / search rounds whose results are public Python 3.12 standard-library
          sources (/usr/lib/python3.12), cut so the rendered prompt is ~30K tokens; the model's next turn (a tool call
          or an answer), up to 4,096 tokens.  Eight different modules and tasks.
Every request gets a nonce line (the level and repetition) right after the shared prefix, so no request reuses
another's cached prompt; the decode prompts carry it as their first line, the agent prompts in the user turn.
Writes results/r20/conc/prompts.json (token counts by the model's own tokenizer, chat template included)."""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "suite"))
sys.path.insert(0, str(WS / "strata-cstar171" / "tools"))
from msuite import runner  # noqa: E402
import strata_tokenizer as ST  # noqa: E402

LIB = Path("/usr/lib/python3.12")
OUT = WS / "results/r20/conc"
TARGET = 30000


def load_tok(d):
    d = Path(d)
    v = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(v)
    for k, i in v.items():
        toks[i] = k
    return ST.Tokenizer(toks, (d / "merges.txt").read_text(encoding="utf-8").split("\n"),
                        json.loads((d / "token_type.json").read_text()))


TOOLS = [
    {"name": "read_file", "description": "Read a text file of the repository and return its content with line numbers. "
     "Use it before you edit a file; large files may be read in parts with offset and limit.",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Path relative to the repository root"},
         "offset": {"type": "integer", "description": "First line to return (1-based); default 1"},
         "limit": {"type": "integer", "description": "Number of lines to return; default: the whole file"}},
         "required": ["path"], "additionalProperties": False}},
    {"name": "edit_file", "description": "Replace one exact occurrence of old_string with new_string in a file. "
     "old_string must match the file exactly, including indentation, and be unique in the file; give more context if "
     "it is not. Use write_file to create a new file.",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Path relative to the repository root"},
         "old_string": {"type": "string", "description": "The exact text to replace"},
         "new_string": {"type": "string", "description": "The replacement text"}},
         "required": ["path", "old_string", "new_string"], "additionalProperties": False}},
    {"name": "write_file", "description": "Create a file or completely replace its content.",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Path relative to the repository root"},
         "content": {"type": "string", "description": "The complete new file content"}},
         "required": ["path", "content"], "additionalProperties": False}},
    {"name": "search", "description": "Search the repository with a regular expression (ripgrep syntax) and return "
     "matching lines as path:line:text, at most 200 matches.",
     "parameters": {"type": "object", "properties": {
         "pattern": {"type": "string", "description": "The regular expression"},
         "path": {"type": "string", "description": "A file or directory to search in; default the repository root"},
         "glob": {"type": "string", "description": "Only files matching this glob, e.g. *.py"}},
         "required": ["pattern"], "additionalProperties": False}},
    {"name": "list_dir", "description": "List a directory of the repository (names, sizes, a trailing / for folders).",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Directory relative to the repository root; default the root"}},
         "additionalProperties": False}},
    {"name": "run_tests", "description": "Run the repository's tests (python -m unittest) or the given test module, "
     "and return the output (the last 6,000 characters).",
     "parameters": {"type": "object", "properties": {
         "target": {"type": "string", "description": "A test module or test id, e.g. tests.test_parser; default all"}},
         "additionalProperties": False}},
    {"name": "run_shell", "description": "Run a shell command in the repository (no network, 120 s limit) and return "
     "its exit code, stdout and stderr (the last 6,000 characters of each).",
     "parameters": {"type": "object", "properties": {
         "command": {"type": "string", "description": "The command line"}},
         "required": ["command"], "additionalProperties": False}},
]

SYSTEM = """You are a coding agent working in a local checkout of a Python project. You act through tools: read files, search the code, edit files, run the tests or a shell command. The user sees your final message and the diffs you make.

How to work:
- Understand before you change. Read the code that the task touches and the code that calls it; search for every use of a name before you rename or change it. Keep a short plan in mind and adjust it as you learn.
- Make the smallest change that solves the task completely. Match the surrounding style: naming, comments, docstrings, error messages, the way the module handles edge cases. Do not reformat code you do not otherwise change.
- Keep behaviour that callers rely on. When a change could break an existing caller, say so and prefer a backwards-compatible form (a new keyword argument with the old default, a new function beside the old one).
- Add or update tests for what you change, in the project's existing test style. Run the relevant tests after each meaningful change and read the output; fix failures you caused and say which ones were already failing.
- Use edit_file for focused changes (old_string must match exactly and be unique) and write_file only for new files or complete rewrites of small ones. Re-read a region after a complex edit.
- Several independent tool calls may go in one reply. Do not call a tool when you already have its result.
- Never invent file contents, test results or APIs. If something is unclear and you cannot find out from the code, state the assumption you make.
- Do not run commands that need the network, that delete data outside the repository, or that take minutes, unless the task says so.

When you are done, reply without a tool call: summarise what you changed and why (files and functions), the tests you ran and their result, and anything left open. Keep it short and concrete."""

TASKS = [
    ("argparse", ["argparse.py"], "In argparse.py, add a `deprecated` keyword to add_argument(): when an option marked "
     "deprecated=True is used on the command line, the parser prints `warning: option '--x' is deprecated` to stderr "
     "(once per option) and otherwise behaves as before. Include it in the help output as '(deprecated)'."),
    ("json", ["json/__init__.py", "json/decoder.py", "json/scanner.py", "json/encoder.py", "json/tool.py", "tokenize.py"], "Make the json decoder accept "
     "a trailing comma before ] and } when called with strict=False, both in the pure-Python scanner and in the "
     "decoder's error messages; strict=True must keep rejecting it with the same message as today."),
    ("textproc", ["shlex.py", "textwrap.py", "csv.py", "string.py", "re/_parser.py"], "Add a function shlex.join_lines(lines, *, posix=True) that "
     "quotes every argument of every line and joins them with ' \\\\\\n  ' continuations, and make textwrap.shorten "
     "accept a `break_long_words` argument like wrap() does."),
    ("configparser", ["configparser.py", "collections/__init__.py"], "Add an EnvironmentInterpolation class to configparser: ${env:NAME} expands to "
     "the environment variable NAME (KeyError-style InterpolationMissingOptionError when it is unset), and "
     "${section:option} keeps working as in ExtendedInterpolation."),
    ("httpclient", ["http/client.py", "socket.py"], "In http/client.py, give HTTPResponse.read() an optional `timeout` argument that "
     "applies to this read only (the socket's previous timeout is restored afterwards, also on errors), and document "
     "it in the docstring."),
    ("logging", ["logging/__init__.py"], "Add a logging.JSONFormatter that writes one JSON object per record with the "
     "keys time, level, logger, message and, when present, exc_info (formatted) and the record's `extra` fields; "
     "make it usable from dictConfig."),
    ("pathlib", ["pathlib.py", "fnmatch.py", "os.py"], "Add Path.walk_files(pattern='*', *, follow_symlinks=False) to pathlib: it yields the "
     "regular files below the path whose name matches the pattern, depth first and sorted by name in each directory, "
     "built on Path.walk()."),
    ("email", ["email/utils.py", "email/_parseaddr.py", "email/header.py", "email/_header_value_parser.py"], "email.utils.getaddresses() splits "
     "'\"Doe, John\" <john@example.com>, jane@example.com' wrongly in some cases with nested quotes; find where the "
     "address list is tokenised and make quoted commas never split an address. Keep the strict=True default behaviour."),
]


def numbered(text):
    return "\n".join(f"{i:6d}\t{ln}" for i, ln in enumerate(text.split("\n"), 1))


def agent_messages(task, nonce, budget_chars):
    name, files, ask = task
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{nonce}\nRepository: cpython-lib-{name} (a checkout of the Python 3.12 "
                                        f"standard library's {', '.join(files)}).\n\nTask: {ask}"}]
    used = 0
    call = 0
    first = files[0]
    for f in files:
        text = (LIB / f).read_text(encoding="utf-8")
        left = budget_chars - used
        if left < 2000:
            break
        lines = text.split("\n")
        body = numbered(text)
        args = {"path": f}
        if len(body) > left:                      # read the first part of a big file, as an agent would
            n = 0
            acc = 0
            for ln in lines:
                acc += len(ln) + 8
                if acc > left:
                    break
                n += 1
            body = numbered("\n".join(lines[:n]))
            args = {"path": f, "offset": 1, "limit": n}
        call += 1
        cid = f"call_{call}"
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": cid, "type": "function", "function": {
            "name": "read_file", "arguments": json.dumps(args)}}]})
        msgs.append({"role": "tool", "tool_call_id": cid, "content": body})
        used += len(body)
    # a search round last (the agent looking for callers), from the first file
    word = {"argparse": "def add_argument", "json": "strict", "textproc": "def shorten", "configparser": "class ExtendedInterpolation",
            "httpclient": "def read", "logging": "class Formatter", "pathlib": "def walk", "email": "def getaddresses"}[name]
    hits = [f"{first}:{i}:{ln}" for i, ln in enumerate((LIB / first).read_text(encoding="utf-8").split("\n"), 1) if word in ln][:40]
    call += 1
    cid = f"call_{call}"
    msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": cid, "type": "function", "function": {
        "name": "search", "arguments": json.dumps({"pattern": word})}}]})
    msgs.append({"role": "tool", "tool_call_id": cid, "content": "\n".join(hits) or "(no matches)"})
    return msgs


def main():
    tok = load_tok(json.loads((WS / "configs/Cstar171.json").read_text())["tokenizer"])
    count = lambda msgs: len(tok.encode(json.dumps(msgs, ensure_ascii=False))) + 40 * len(msgs)   # noqa: E731
    tools_tokens = len(tok.encode(json.dumps(TOOLS)))
    agent = []
    for t in TASKS:
        lo, hi = 20000, 400000                    # chars of file content; bisect to ~TARGET tokens
        for _ in range(14):
            mid = (lo + hi) // 2
            n = count(agent_messages(t, "[session L0-R0]", mid)) + tools_tokens
            if n < TARGET:
                lo = mid
            else:
                hi = mid
        agent.append({"id": t[0], "budget_chars": lo, "est_tokens": count(agent_messages(t, "[session L0-R0]", lo)) + tools_tokens})
    items = {i["id"]: i for i in runner.load_items(["coding"])}
    lr = json.loads((WS / "prompts/longreason.json").read_text())
    decode = [{"id": "lr-" + p["id"], "messages": p["messages"] if "messages" in p else [{"role": "user", "content": p["prompt"]}]}
              for p in lr]
    for iid in ("coding/c05_wrap", "coding/c10_lru", "coding/c15_topo", "coding/c18_interval_set", "coding/c21_bugfix_lfu"):
        if iid not in items:
            iid = sorted(items)[len(decode)]
        msgs, _ = runner.messages_for(items[iid])
        decode.append({"id": iid.split("/")[1], "messages": msgs})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prompts.json").write_text(json.dumps({"tools": TOOLS, "agent": agent, "decode": decode[:8]}, indent=1))
    for a in agent:
        print("agent", a)
    for d in decode[:8]:
        print("decode", d["id"], count(d["messages"]))


if __name__ == "__main__":
    main()
