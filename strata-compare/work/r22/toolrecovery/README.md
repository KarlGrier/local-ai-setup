# tool_call_recovery on our port (round 22, 10-29)

Strata v0.2.8 turns `tool_call_recovery` on by default (`serve/server.py` `tool_call_recovery_setting`; the config's
`"tool_call_recovery": false` turns it off). With it on, `OutputParser(recover=True)` in `serve/frontend.py` reads
these forms as calls, in the answer only and only for a declared tool:

- `<tool_call>` + `<parameter=NAME>` as the opener (instead of `<function=NAME>`)
- JSON `{"name": ..., "arguments" | "parameters": {...}}` inside `<tool_call>`, also in a ```` ```json ```` fence, also
  with the arguments as a JSON string
- a bare `<function=NAME>` at the start of a line outside code (a stray `</tool_call>` after it is dropped)
- a second call in the same `<tool_call>` (also opened with `<parameter=NAME>`)
- with recovery on, a call that still does not parse comes back as text instead of failing the request

0.2.8's other repairs run whatever the switch says: a missing `</function>` or `</tool_call>`, the #3441 loose opener
(`<function:NAME>`, `<=NAME>`), damaged JSON arguments, and the #4077 rule that drops a second `</think>` at a line
start in the answer.

The goal: real calls are recovered; text that only talks about or quotes calls never turns into a call.

## Files

| file | what |
|---|---|
| `tests/test_recovery_offline.py` | offline: the port's parser, no server, no GPU (runs in about a second) |
| `toolrecovery_live.py` | live, for a GPU gap: Jan's request shape and the coding harness's, on vs off |
| `results/` | `offline-*.json`, `live-*.jsonl` / `live-*.txt` |
| `configs/` | made by `toolrecovery_live.py offconfig` (the recovery-off copy of a config) |

## 1. Offline check

```
nice -n 19 /home/USER/ai-speed-testing/strata-compare/.venv/bin/python -B \
  /home/USER/ai-speed-testing/strata-compare/work/r22/toolrecovery/tests/test_recovery_offline.py [--tree DIR] [-v]
```

It feeds `strata-r22p028/serve/frontend.py`'s `OutputParser` the way the server builds it (`declared_only=True`,
`recover=True`) and the way upstream's `serve/test_tool_corpus.py` feeds it: whole, in pieces of 1, 3 and 7
characters, streaming of the arguments off and on, and cut in two at every character. Every specimen is also run
with `recover=False`, so each false call is marked "cause: recovery" (only with recovery on) or "cause: baseline"
(the parser makes it with recovery off too).

- **(a) 22 real calls**: each recovery form above, two repairs that are not gated (a missing `</function>`, the
  loose opener), the template's own form as controls (in the answer and at the end of the thinking), and real
  `write` calls whose content quotes the format (a pytest file with XML, bare and JSON call
  strings; a test with `</think>` lines; format docs). The pass rule: exactly the expected calls with exactly the
  expected arguments in every feed mode, streamed arguments equal to the final ones, no call announced
  (`tool_start`) and then dropped, and the prose kept.
- **(b) 36 texts with no call**: format explanations in prose, docs with and without fences, inline code, a
  ```` ```json ```` function-calling example, JSON without a wrapper, a pytest file fenced and unfenced, a 4-backtick
  doc with inner fences, indented code blocks, quotes of an earlier call (fenced, unfenced, blockquote, JSON), a bug
  report that quotes a drifted call, reasoning that drafts a call and decides not to make it, a whole example turn
  with `<think>`, and controls. The pass rule: no call and no announced call in every feed mode; content and
  reasoning equal to what was written (runs of whitespace collapsed).
- **(c) 3 limits, reported, not graded**: recovery forms written as the last thing inside the thinking stay
  reasoning (only the template's form is rescued from the thinking, #804).

`--tree` points the test at another tree. Upstream's v0.2.8 `frontend.py` (from `git show`) gives the same results
except for the two think-fence specimens, which only our port passes. So everything below is v0.2.8's own behaviour.

### Results 10-29 (port r22-port028)

(a) 21 of 22 pass. Every recovery form comes out right in every feed mode. One failure:
- `write-doc-listing-closers` (baseline, not gated): a `write` whose file lists `</parameter>`, `</function>` and
  `</tool_call>` on lines of their own is cut at that `</parameter>`. The content keeps 141 of its 218 characters,
  and the rest of the file, plus the real closers, leaks into the visible answer.

(b) 19 of 36 pass. 15 make a false call and 2 lose text:
- **Caused by recovery (6):** a bare `<function=read>` block in an unfenced doc; `<tool_call>{"name": ...}</tool_call>`
  in a sentence; the same JSON on lines of its own; a bug report quoting `<tool_call>` + `<parameter=read>`; a quote
  of an earlier call in JSON form; a bare block in a 4-space indented code block. The indented case also depends on
  how the text is cut: 110 of 122 feed modes make the call, and pieces of 3 or 7 do not. In an unfenced pytest file,
  recovery adds 2 calls (the bare and JSON strings) to the 1 the baseline already makes.
- **Baseline (also with recovery off, 9):** a template-form call outside a fence is always a call (in a sentence, in
  an unfenced doc, an unfenced quote of an earlier call, an unfenced pytest file). A 4-backtick fence is closed by
  its inner ```` ``` ````. A 4-space indented code block is not treated as code. In a thinking turn, the #4077 rule
  drops a line-start `</think>` in the answer even inside a code fence, and it resets the fence tracking. So a fenced
  pytest file or example turn that shows `<think>…</think>` and then a call makes that call. Without thinking, the
  same text passes. The last one is an edge case: a call drafted as the last thing before `</think>` ("I decided not
  to… it would be:") is read as an act, which is #804 by design.
- **Text only (2):** the same #4077 rule deletes a line-start `</think>` from an answer that explains the think tags,
  fenced or not.
- Safe: every fenced form (```` ``` ````, `~~~`, ```` ```json ````), inline code, blockquotes, JSON without a
  wrapper, undeclared tool names, and reasoning that drafts a call in any form and then goes on.

## 2. Live check (for a GPU gap; not run yet)

`toolrecovery_live.py` sends Chat Completions requests, streamed, with T 1.0, top_p 0.95, top_k 20, min_p 0.05 and
effort medium. It never runs a tool and only reads the first response of each conversation.

- **jan**: Jan's assistant instructions (`~/.local/share/Jan/data/assistants/jan/assistant.json`, date filled in),
  plus the 15 tools of Jan's MCP servers, read from the source files in `~/ai/deep-research/tools` without starting
  them. This is jan-tool-check.py's approach. No max_tokens.
- **opencode**: OpenCode's recorded request (`logs/usability/turns/client-check-opencode-10171324`): its system
  prompt, its 10 tools, `max_completion_tokens` 32768 and `stream_options`.
- **dsh**: DeepSeek Harness Minimal's recorded request (a developer message and one `bash` tool).

There are 27 prompts. 11 must call a tool. 16 invite quoting or explaining calls and must make none: the raw call
text, an unfenced XML example, a JSON function-calling example, JSON in `<tool_call>` inside a sentence, a whole turn
with `<think>`, a pytest file (fenced and unfenced), a quote of the previous turn's call (written into the history),
a bug report quoting a drifted call, a 4-backtick doc, and a "should I call the calculator?" question. Examples carry
`EXAMPLE-ONLY-…` markers, so a quote that became a call is easy to recognise. Three of the should-call prompts are
`write` calls whose content quotes the format, including the usability round's lost-calls shape (`</think>` in a
test drafted while thinking). Each prompt runs 3 times by default: 81 requests per arm, about 1 to 2 hours per arm
at medium effort. Use `--reps 2` or `--only` in a short gap.

Each (prompt, repeat) gets the same `seed` in both arms. When the engine reproduces the text, the on and off answers
differ only by the parser. `compare` reports how many pairs have the same model output (same token count and
reasoning). `--no-seed` sends no seed, as the clients do.

Check first, without a server (this builds every request and prints its size):

```
/home/USER/ai-speed-testing/strata-compare/.venv/bin/python -B /home/USER/ai-speed-testing/strata-compare/work/r22/toolrecovery/toolrecovery_live.py --dry-run
```

In the gap (inside `work/r22/port_gap4.sh begin … end`, with 8080 stopped). `CFG` is the 0.2.8 port's test config,
whose `"server"` must be `strata-r22p028/serve/server.py` on port 8081 and must not set `tool_call_recovery`.
`with_server.sh` holds the gpu-test lock and runs the memory guard. Run the kernel check after each arm, as the gap
scripts do.

```
W=/home/USER/ai-speed-testing/strata-compare; T=$W/work/r22/toolrecovery; CFG=$W/configs/<the r28 config>.json
# recovery on (the 0.2.8 default)
$W/bringup/lib/with_server.sh tr-on $CFG -- "$W/.venv/bin/python -B $T/toolrecovery_live.py http://127.0.0.1:8081 --label on"
# recovery off: one line (offconfig writes $T/configs/<name>-norecovery.json with "tool_call_recovery": false and its own log)
$W/bringup/lib/with_server.sh tr-off "$($W/.venv/bin/python -B $T/toolrecovery_live.py offconfig $CFG)" -- "$W/.venv/bin/python -B $T/toolrecovery_live.py http://127.0.0.1:8081 --label off"
# the comparison (no server)
$W/.venv/bin/python -B $T/toolrecovery_live.py compare $T/results/live-on-<time>.jsonl $T/results/live-off-<time>.jsonl
```

`offconfig` warns when the config's server has no recovery switch (a pre-0.2.8 tree). The server logs what the
parser did (`tool calls inside the thinking`, `extra closing think tag(s) … dropped`, `argument(s) repaired`,
`<tool_call> block(s) … did not read as a call`). The live script also records the `/metrics` totals for each
response.

Each response gets a verdict:
- **Must call:** `OK`, `LOST` (call markup in the text and no call), `LOST?` (markup at the end of the thinking and
  no answer), `NO CALL` (the model answered without one: its choice, not the parser's), `WRONG TOOL` or `BAD ARGS`.
  Flags: `SPURIOUS EXTRA` (a second call carrying a quoted example's marker) and `LEAK` (closing tags left in the text
  after a call: an argument cut short).
- **Must not:** `OK`, `SPURIOUS (QUOTE)` (a call carrying the example's marker: a quote became a call) or `SPURIOUS`
  (a call the prompt said not to make). Each also says whether the quoting was exercised (markup or the marker in the
  text). A prompt the model answered without quoting tests nothing.
- **Any:** `FINISH` (finish_reason does not fit the calls), `CUT` (finish_reason length), `ERROR`.

### What counts as a pass

- Recovery on: no `LOST`, no `BAD ARGS`, no `SPURIOUS (QUOTE)`, no `SPURIOUS EXTRA`, no `LEAK`, no `FINISH`.
  A plain `SPURIOUS` needs its text read: did the model disobey, or did the parser make the call?
- `compare`: no "recovery MADE a spurious call" and no "recovery LOST a call" on a pair with the same model output.
  Any "recovery WON a call" is the gain recovery is meant to bring.
- Read the live result together with the offline findings. When the model fences its examples, the risky forms do
  not show up live, so check how many must-not responses were exercised before calling a clean run proof.
