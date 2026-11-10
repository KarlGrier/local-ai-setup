#!/usr/bin/env python3
"""code-mcp.py - an MCP server (stdio) that gives Jan the read-only code tool (2026-10-28, Karl's backlog: "the code tool
in Jan, as already planned").

Jan starts it as: <deep-research venv python> -I <this file>. It loads LDR's deep/codetool.py straight from its file (the
module needs only the standard library; LDR's package is not imported), so Jan gets the same rules as the research
agents: shallow clones of public GitHub repos into a capped scratch folder (400 MB a clone), git with no credentials,
hooks, submodules or LFS, files read only as text, nothing built or run; the GitHub API without a token, at most 50 core
calls and 30 searches a session, 10 core calls always left for other programs.

Three tools, to keep Jan's tool list short: code_search (grep, or files by name), code_read (lines of a file, or a
folder's layout) and github (issues / PRs, or commit messages). Jan stops a tool call after 30 s: a clone that takes
longer keeps going in the background, and the call says to ask again. The clones are deleted when the server exits
(Jan closing) and any left over are swept after 12 h. Log: logs/code-mcp.log.
"""
from __future__ import annotations

import atexit
import concurrent.futures as cf
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
LOG = WS / "logs" / "code-mcp.log"
CODETOOL = WS / ".venv/lib/python3.12/site-packages/local_deep_research/deep/codetool.py"
WAIT_S = 22.0                         # Jan's limit is 30 s; leave room for the reply

_spec = importlib.util.spec_from_file_location("codetool", CODETOOL)
ctm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctm)

ctm.CodeTool.sweep(ctm.scratch_root())
CT = ctm.CodeTool(ctm.scratch_root(), f"jan-{os.getpid()}", log_path=WS / "logs" / "code-mcp.jsonl")
atexit.register(CT.close)
POOL = cf.ThreadPoolExecutor(max_workers=2)
PENDING: dict[str, cf.Future] = {}


def log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")
    except OSError:
        pass


class Busy(Exception):
    pass


def repo_of(spec: str):
    """The clone for owner/name[@ref]; a clone that is not ready within WAIT_S keeps going and the call says so."""
    spec = (spec or "").strip()
    fut = PENDING.get(spec)
    if fut is None or (fut.done() and fut.exception() is not None):
        fut = PENDING[spec] = POOL.submit(CT.open, spec)
    try:
        return fut.result(timeout=WAIT_S)
    except cf.TimeoutError:
        raise Busy(f"{spec} is still being cloned (large repo). Call the same tool again in about 20 seconds.") from None


def t_search(a: dict) -> str:
    r = repo_of(a.get("repo", ""))
    if a.get("name_glob"):
        f = r.files(str(a["name_glob"]), str(a.get("path") or "."))
        return (f"{f['total']} file(s) named {a['name_glob']} in {r.name}@{r.ref}:\n" + "\n".join(f["files"])
                + ("\n(more not shown)" if f["total"] > len(f["files"]) else ""))
    pattern = str(a.get("pattern") or "")
    if not pattern:
        return "Give `pattern` (what to grep for) or `name_glob` (file names to list)."
    g = r.grep(pattern, str(a.get("path") or "."), glob=a.get("file_glob") or None,
               ignore_case=bool(a.get("ignore_case")))
    if not g["total"]:
        return f"No hits for /{pattern}/ in {r.label}."
    more = f"\n({g['more']} more hits - narrow with path or file_glob.)" if g["more"] else ""
    return (f"{g['total']} hit(s) for /{pattern}/ in {r.label}:\n"
            + "\n".join(f"{h['file']}:{h['line']}: {h['text']}" for h in g["hits"]) + more
            + f"\nLinks: https://github.com/{r.name}/blob/{r.ref}/<file>#L<line>")


def t_read(a: dict) -> str:
    r = repo_of(a.get("repo", ""))
    path = str(a.get("path") or "").strip()
    target = r._path(path or ".")
    if target.is_dir():
        t = r.tree(path or ".", int(a.get("depth") or 2))
        return (f"{r.name}@{r.ref} {t['path']}:\n" + "\n".join(t["entries"])
                + ("\n(cut at 200 entries - give a deeper path)" if t["cut"] else ""))
    d = r.read(path, int(a.get("start_line") or 1), int(a["end_line"]) if a.get("end_line") else None)
    rest = f"\n({d['file']} has {d['lines_total']} lines.)" if d["end"] < d["lines_total"] or d["start"] > 1 else ""
    return f"{r.name}@{r.ref}: {d['file']} lines {d['start']}-{d['end']}\n{d['url']}\n\n{d['text']}{rest}"


def t_github(a: dict) -> str:
    name, ref = ctm.parse_repo(str(a.get("repo") or ""))
    if a.get("commits"):
        r2 = str(a.get("ref") or "") or ref
        c = (CT.api.commits(name, r2, a.get("path") or None) if r2 and ctm.SHA_RE.match(r2) and len(r2) == 40
             else CT.history(name, r2, a.get("path") or None))
        if not c["commits"]:
            return f"No commits found in {name}@{c.get('ref')}."
        url = f"https://github.com/{name}/commits/{c.get('ref') or 'HEAD'}" + (f"/{a['path']}" if a.get("path") else "")
        return f"{name} commits on {c.get('ref') or 'the default branch'}:\n{url}\n\n" + "\n".join(
            f"{x['date']} {x['sha']} {x['message']}" for x in c["commits"])
    if a.get("number"):
        i = CT.api.issue(name, int(a["number"]))
        return (f"{i['kind'].upper()} #{i['number']} ({i['state']}, {i['created']}): {i['title']}\n{i['url']}\n\n{i['body']}"
                + "".join(f"\n\n--- comment ({'maintainer, ' if c['by_maintainer'] else ''}{c['date']}):\n{c['text']}"
                          for c in i["comments"]))
    q = str(a.get("query") or "")
    if not q:
        return "Give `query` (search words), `number` (one issue / PR) or `commits: true`."
    kind = a.get("kind") if a.get("kind") in ("issue", "pr") else "any"
    s = CT.api.search(name, q, kind=kind)
    if not s["items"]:
        return f"No issues / PRs in {name} match {q!r}."
    return (f"{s['total']} issue(s) / PR(s) in {name} match {q!r} (open one with number):\n"
            + "\n".join(f"#{i['number']} [{i['kind']}, {i['state']}, {i['created']}] {i['title']}\n    "
                        f"{i['body'][:200].strip()}" for i in s["items"]))


REPO = {"type": "string", "description": "owner/name, or owner/name@tag for a version (e.g. 'Niko1221/Strata@v0.2.7'); "
                                         "without @tag: the default branch."}
TOOLS = [
    {"name": "code_search",
     "description": "Search a public GitHub project's source code (read-only): grep with a regular expression "
                    "(file:line hits), or list files by name with name_glob. For questions about what a program's code "
                    "does - a flag, setting, default or function - at a given version. Read around a hit with code_read.",
     "inputSchema": {"type": "object", "properties": {
         "repo": REPO,
         "pattern": {"type": "string", "description": "Extended regex, e.g. 'expert[-_]cache|getenv\\(\"STRATA_'."},
         "path": {"type": "string", "description": "A folder or file inside the repo (optional)."},
         "file_glob": {"type": "string", "description": "Only these files, e.g. '*.py' (optional)."},
         "name_glob": {"type": "string", "description": "List files whose name matches instead of grepping."},
         "ignore_case": {"type": "boolean"}}, "required": ["repo"]}},
    {"name": "code_read",
     "description": "Read lines of one file of a public GitHub project (up to 120, numbered, with the GitHub link), or "
                    "the layout of a folder when path is a folder or empty.",
     "inputSchema": {"type": "object", "properties": {
         "repo": REPO,
         "path": {"type": "string", "description": "File or folder inside the repo, as code_search shows it."},
         "start_line": {"type": "integer"}, "end_line": {"type": "integer"},
         "depth": {"type": "integer", "description": "Folder levels for a layout (1-4, default 2)."}},
         "required": ["repo"]}},
    {"name": "github",
     "description": "A public GitHub project's issues and pull requests (search with query, or open one with number), "
                    "or its commit messages (commits: true, optionally for a path or ref). No login; about 60 calls an "
                    "hour, so prefer code_search for what the code does.",
     "inputSchema": {"type": "object", "properties": {
         "repo": REPO,
         "query": {"type": "string"}, "number": {"type": "integer"},
         "kind": {"type": "string", "enum": ["any", "issue", "pr"]},
         "commits": {"type": "boolean"}, "path": {"type": "string"}, "ref": {"type": "string"}},
         "required": ["repo"]}},
]
HANDLERS = {"code_search": t_search, "code_read": t_read, "github": t_github}
INSTRUCTIONS = ("Read-only access to public GitHub source code, issues and commits. Use it when the user asks what a "
                "specific open-source program's code does at a version; not for general questions.")


def reply(msg_id, result=None, error=None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(msg: dict) -> None:
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        pv = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return reply(mid, {"protocolVersion": pv, "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "code", "version": "1.0"}, "instructions": INSTRUCTIONS})
    if method in ("notifications/initialized", "notifications/cancelled") or (mid is None and method):
        return None
    if method == "ping":
        return reply(mid, {})
    if method == "tools/list":
        return reply(mid, {"tools": TOOLS})
    if method == "tools/call":
        p = msg.get("params") or {}
        name, args = p.get("name"), p.get("arguments") or {}
        fn = HANDLERS.get(name)
        if not fn:
            return reply(mid, {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True})
        try:
            text, err = fn(args), False
        except Busy as e:
            text, err = str(e), False
        except ctm.CodeToolError as e:
            text, err = f"CODE TOOL: {e}", True
        except Exception as e:  # noqa: BLE001
            log(f"{name} error:\n" + traceback.format_exc())
            text, err = f"CODE TOOL: failed ({type(e).__name__}: {e})", True
        log(f"{name} {json.dumps(args)[:300]} -> {'error' if err else 'ok'} ({len(text)} chars)")
        return reply(mid, {"content": [{"type": "text", "text": text}], "isError": err})
    if mid is not None:
        return reply(mid, error={"code": -32601, "message": f"Method not found: {method}"})
    return None


def main() -> None:
    log(f"started (pid {os.getpid()})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            handle(m)


if __name__ == "__main__":
    main()
