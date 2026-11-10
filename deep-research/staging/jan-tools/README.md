# Jan's tools - staged 10-28 (Karl's backlog item; all read-only; nothing installed yet)

What Jan has (mcp_config.json, 10-28): active = deep-research (research-mcp.py, 9 tools) and web-search (web-mcp.py:
web_search, fetch_page). Configured but OFF: Jan Browser MCP, browsermcp, fetch (mcp-server-fetch), serper, filesystem,
sequential-thinking - keep them off (filesystem is a file tool; mcp-server-fetch has no private-address guard).
Jan 0.8.6 settings: toolCallTimeoutSeconds 30, maxToolOutputChars 40000, smart tool routing on.

1. **Full-page reading** - tools/web-mcp.py's fetch_page, extended (staging/jan-tools/web-mcp.py): default 25,000
   characters, at most 30,000, `start` = "continue from" offset; the reply says "characters a-b of N; to read on, call
   fetch_page with start=b"; parts end at a paragraph / sentence break; the page text is cached 15 min (reading on does
   not load it again). Extraction unchanged (trafilatura without comments, tables kept; PDFs via pdftotext; scripts,
   styles and boilerplate stripped); the title and final URL head every reply; only public addresses (pinned IP,
   redirects checked). The bundle's reading.py is LDR's background reader (no extractor of its own), so it is not a
   better base for Jan. Test: tests/test_fetch_offset.py (13 parts cover a 306K-char page exactly, one load).
2. **Date** - both of Jan's assistants carry "Current date: {{current_date}}" in their instructions (Jan's own default
   text). Jan 0.8.6 is a Tauri app (the web code is inside the binary), so the substitution is checked with one chat:
   ask Jan "What is today's date? Do not use any tools." Add nothing unless that answer is wrong.
3. **Calculator** - calc-mcp.py, one tool `calculate`: own recursive-descent parser (no eval/exec), exact fractions,
   + - * / ^ %, sqrt/log/round/min/max, units with conversion (data, rates, time, Hz, MT/s, J/Wh/W, length, mass, $ /
   EUR, tokens). Sandbox: started as `unshare -rn` (no network at all), then RLIMIT_NOFILE (no new files), RLIMIT_FSIZE 0
   (no file writes), 512 MB, 2 s per calculation. Test: tests/test_calc.py (40 results, 15 refusals incl. 9^9^9,
   __import__, open(); MCP over stdio inside the sandbox; no network and no file opens inside).
4. **Code tool** - code-mcp.py, three tools (code_search, code_read, github) over LDR's deep/codetool.py (loaded from
   its file; same caps and git safety). Clones under $TMPDIR/code-tool/jan-<pid>, deleted at exit; a clone slower than
   22 s keeps going and the call says to ask again (Jan's 30 s limit). Test: tests/test_code_mcp.py (octocat/Hello-World;
   path escape, .git and a bad repo name refused).

Tool list after install: 15 tools, ~2,500 tokens of tool JSON (research 9: ~1,225; web 2: ~461; code 3: ~598; calc 1:
~185). No shell or file-writing tool.

**Install** (when Jan is closed): back up tools/web-mcp.py and Jan's mcp_config.json (*.before-jantools); copy
web-mcp.py, calc-mcp.py, code-mcp.py into tools/; add to mcp_config.json:
  "calculator": {"command": "/usr/bin/unshare", "args": ["-rn", "/usr/bin/python3", "-I", "<tools>/calc-mcp.py"], "env": {}, "active": true}
  "code": {"command": "<venv>/bin/python", "args": ["-I", "<tools>/code-mcp.py"], "env": {}, "active": true}

**Test chats** (GPU: a few minutes on 8080): staging/jan-tools/jan-tool-check.py (written 10-28; research tools listed but never run, web search without the paid fallback, 7 cases) sends Jan's instructions + the full
tool list to Strata the way Jan does, runs the tool calls through the servers, and records which tools were called:
should call - a long page read to its end (fetch_page with start), "138 GB at 1.8 GB/s, how long?" (calculate), "where
does Strata v0.2.7 parse --expert-cache?" (code_search -> code_read); should NOT call - "what is 2 + 2", "what is a GB",
"what's the capital of France", a plain explanation question. Plus Karl's one date question in Jan itself.

**INSTALLED 2026-10-28 ~11:10 (Jan was closed; Karl 10-28: "install them the next time Jan is closed").** Backups:
tools/web-mcp.py.before-jantools, ~/.local/share/Jan/data/mcp_config.json.before-jantools. tools/ now has web-mcp.py
(fetch_page with start), calc-mcp.py, code-mcp.py; mcp_config.json gained "calculator" (unshare -rn) and "code", both
active. Checked: each server starts with Jan's exact command and lists its tools (web 2, calc 1, code 3, research 9).
Test chats 10:56 (jan-tool-check.py on 8080): 7 of 7 as expected; the calculator's description now says "convert with
'to', never divide by 60 yourself" (retest: one clean call). Jan picks it all up at its next start. Open: Karl's one
date question in Jan itself. Rollback: copy the two .before-jantools files back.
