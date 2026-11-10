# C4 - the Anthropic API path for the Sonnet 5.5 experiment (staged 10-29, NOT installed, never started)

Plan: strata-compare/results/SONNET55-LDR-PLAN-1027.md (o03 only; arm (a) our build, arm (b) stock LDR, arm (c) the
web app; per-run caps; $60 total stop). Builds on staging/c3 (profiles, the loader, run-ldr.sh), which is not modified.

**Status:** code and offline tests only. No request has gone to Anthropic. The key file was never opened. The
`anthropic` SDK **is installed** in `.venv` (1.9.0), so nothing needs a pip install for arm (a).

**Karl's settings of 10-29 are in** (backups of the changed files: `*.before-karl1029`):

| # | setting | where |
|---|---|---|
| 1 | effort **high** on both arms (matched) | arms/*.env: `GUARD_DEFAULT_EFFORT=high`; ours also `agent=high` (was medium) |
| 2 | **report-stage reserve 22 %** of each run's cap (configurable per arm) | `GUARD_REPORT_RESERVE=0.22`; [Report reserve](#report-reserve-karl-10-29) |
| 3 | **no caching on one-shot calls**; only prefixes reused within a run | [Caching](#prompt-caching-karl-10-29) |
| 4 | **5 min lifetime**; 1 h for the lead's prefix only behind a switch, **off** | `GUARD_LEAD_CACHE_1H=0`; [lead gaps](#the-leads-gaps-the-1-h-decision) |

## Files

| file | what |
|---|---|
| tools/anthropic_guard.py | the guard: OpenAI-compatible endpoint on 127.0.0.1 -> Anthropic Messages API (official SDK); one process per arm |
| tools/lead_gaps.py | after the pilots: the gaps between the lead's calls, and what the lead's 1 h cache would have saved / cost |
| pricing.json | Sonnet 5.5 rates the guard prices with (re-check on the day) |
| arms/ours.env, arms/stock.env | per-arm settings: ports, run id, caps, reserve, efforts, cache, LDR flags - Karl's 10-29 values; the rest **draft, unmeasured** |
| c4-arm.sh | `plan / guard / start / stop / status <arm>`: the arm's guard + its LDR |
| run-ldr.sh | staged copy of staging/c3/run-ldr.sh + `LDR_BACKEND=guard` (base kept as run-ldr.sh.c3) |
| tests/mock_anthropic.py, tests/test_c4.py | the offline tests; results in tests/results/results.{md,json} |

The model profile is staging/c3/profiles/sonnet-5-5.env **as it is** (still a draft). Its header line "run-ldr.sh ...
cannot run C4 as it is" becomes stale once C4 is installed; edit it then (staging/c3 is not touched here).

## The guard (tools/anthropic_guard.py)

```
LDR (ChatOpenAI, /v1/chat/completions)  ->  127.0.0.1:8191 / 8192 (guard)  ->  api.anthropic.com, always streamed
```

**Translation.** System and developer messages at the start become `system`. A later one becomes user text. User
text and images, assistant text + `tool_calls`, and `tool` results become content blocks; tool results go first in
their user turn. Tools are sorted by name, so the cached prefix does not depend on the client's order.

- `tool_choice`: `none` is kept. `required` or a named tool becomes auto, since the model refuses forced tool use;
  the log notes it.
- Other fields: `parallel_tool_calls: false`, `stop`, `max_tokens` / `max_completion_tokens` (clamped to 64000) and
  a `json_schema` response format are mapped.
- Dropped and logged by name: `temperature`, `top_p`, `seed` and the other sampling fields (non-default values are
  refused), and Strata-only fields.
- The model is always `--model` (claude-sonnet-5-5), whatever the client names.

**Responses.** OpenAI JSON or SSE chunks: text, `tool_calls` with streamed arguments, `finish_reason`
(tool_use -> tool_calls, max_tokens -> length, refusal -> content_filter) and `usage` (with
`stream_options.include_usage`). Prompt tokens are input + cache writes + cache reads, and `cached_tokens` is the
cache reads. Upstream is always streamed, so long outputs never hit the SDK's 10-minute non-streaming guard.

**Effort -> `output_config.effort`**, thinking `{type: adaptive, display: omitted}`:

| request sends | sent |
|---|---|
| `reasoning_effort` low / medium / high / xhigh / max | the same level (`--effort-map` can rename, e.g. `xhigh=high`) |
| `reasoning_effort` minimal / none | low (there is no lower level; thinking cannot be switched off on Sonnet 5.5) |
| anything else | HTTP 400, nothing sent |
| nothing | `--class-efforts` for the call's class (agent / extract / compact / report / verify / synth / other, see [the classes](#how-calls-are-classified)), else `--default-effort`, else none (API default = high) |

Our deep package sends its own efforts (report / verify / compact / extract from the profile). LDR's agent loop and
stock LDR send none, so the arm files set them. This replaces strata-proxy's mode file.

**Efforts per arm (Karl 10-29: high, matched).**

- ours: `GUARD_DEFAULT_EFFORT=high`, `GUARD_CLASS_EFFORTS=agent=high,extract=low`. The lead and the subagents run at
  high, like stock. `extract=low` is our profile's own extraction effort (`LDR_DEEP_EXTRACT_EFFORT`); the deep package
  sends its report / verify (high) and compaction (medium) efforts itself. The c3 profile's
  `LDR_JOB_AGENT_EFFORT=medium` is not read by C4 (staging/c3 is not touched).
- stock: `GUARD_DEFAULT_EFFORT=high`, no class efforts. Stock sends no effort, so every stock call runs at high.

### How calls are classified

The guard has no request metadata to go on (LDR sends none, and the `strata_*` fields are dropped). It classifies each
request by its shape and by the first words of LDR's and the deep package's prompts. A test checks that every mark
below is in the sources the arms run (stock LDR 1.10.7 in baseline/site, the installed build's deep package).

| class | how it is recognised | stage |
|---|---|---|
| agent, role **lead** | tools, or tool calls in the history; the system prompt starts "You are a research assistant writing a research report." | research |
| agent, role **sub** | tools or tool calls; any other system prompt (subagents: "You are a focused research assistant ...") | research |
| extract | first user message starts with LDR's extraction prompt ("You are a content-extraction step ...") | research |
| compact | the deep package's compaction mark | research |
| report | the deep package's report mark (outline, sections, opening) | **report** |
| verify | the deep package's verification mark (claim checks, setup check, not-yet, critic, version, arithmetic, consistency) | **report** |
| synth | LDR's own report-stage prompts: the fallback synthesis ("Synthesize a comprehensive answer to: "), the citation pass ("Using the previous knowledge and new sources, answer the question.", also after an output-instruction prefix, within its first 4,000 characters) and its fact check (off by default) | **report** |
| other | none of the above | research (the fallback) |

**Our arm (a).** Research = the lead, the subagents (their wrap-up calls too), page extraction, compaction. Report
stage = the deep package's report writer and every check after it, plus LDR's fallback synthesis / citation pass
(only used when the deep report fails or the agent loop ends without an answer). One quirk: the tried-list's map /
merge calls carry the verification mark and run before the research. They count as report stage, but they spend at
the start, when the whole cap is still there, and the tried list is off in C4.

**Stock arm (b).** Research = the lead, the subagents, page extraction, anything unidentified. Report stage = the
citation pass after the agent loop (and its fact check, off by default) and the fallback synthesis. **Stock's own
report draft is the lead's last answer, and that call looks like every other lead call** (same system prompt, same
tools; whether the model answers or calls a tool is only known afterwards). So it counts as research. The fallback is
conservative: only positively identified report-stage prompts may use the reserve; nothing research-like can. What
it means for stock:

- Normal case: the lead answers before 78 % of the cap is spent. The citation pass then runs on the reserve.
- The lead is still researching at 78 %: its next call is refused (402). LDR 1.10.7 catches the agent error and, with
  sources collected, runs its fallback synthesis (report stage, allowed) and then the citation pass (allowed). The
  report comes from the collected sources instead of the lead's own answer. That is visible in the log (class
  `synth`).
- If a different LDR version changed those prompts, nothing in stock matches: every stock call is research, the run
  stops at 78 % and the reserve stays unspent. Money cannot be overspent either way; only stock's report could be
  lost. The marks test would catch such a change before a run.
- The plan expects stock to spend $5-12 against $12, and stock usually stops on its own step caps, so the
  research cap ($9.36) may or may not bind. The pilot shows it.

### Prompt caching (Karl 10-29)

Only prefixes that are reused within the run get a `cache_control` breakpoint. One-shot calls get none, so they pay
the plain input rate instead of the 1.25x write premium.

| breakpoint | placed when |
|---|---|
| **tail** (top-level automatic caching: the end of the growing transcript) | the request **will grow**: it carries tools (an agent loop: lead, subagent, or a wrap-up with its tools sent again, since the next call is this one + the answer + tool results), **or** it continues a conversation this guard answered (one of its assistant turns is an answer the guard stored, under an unchanged prefix, which is the same check the thinking replay uses) |
| **head** (last system block; the last tool if there is no system prompt) | on every request that gets a tail (so subagents share the system + tools prefix across conversations), **and** on a request whose system + tools prefix this guard already sent and got answered once in this run (a repeating system prompt; the second time it is written, from the third on it is read) |
| none | everything else: a single exchange with no tools, no earlier answer of ours and a new prefix. In LDR that is extraction, compaction, report sections, outline, opening, verification and checks, the citation pass and the fallback synthesis (all are one user message without a system prompt) |

Why this rule: it uses only what the guard can see and test, in the order things happen. An agent loop's next call
always extends the current one, so caching its tail is a sure reuse (on the loop's last call the write is only the
last tool results). A one-shot call's prompt is never sent again, so a write there is pure cost. Both facts are known
before the request is sent. A guard restart forgets the seen prefixes and answers, so agent calls (they have tools)
still cache; only the "seen before" cases wait one call.

- **Lifetime:** 5 minutes on every breakpoint (`--cache-ttl` accepts only `5m`).
- **`--lead-cache-1h 1`** (`GUARD_LEAD_CACHE_1H=1`, **off** by default): the lead's two breakpoints get `ttl: 1h`.
  Subagents and every other call stay at 5 minutes. One request never mixes lifetimes. Lead writes then cost $4/MTok
  instead of $2.50, and the guard prices and reserves them so.
- The cost log shows each request's decision: `cache: {ttl, marker, auto_tail, why: tools | continues | head-seen |
  one-shot, continues}`.

### The lead's gaps (the 1 h decision)

The lead waits while its subagents run. If it waits more than 5 minutes, its cached prefix is gone and its next call
writes it again. So the guard logs every lead call that was sent to `guard/lead-gaps-<run>.jsonl`, with times and
token counts only:

- `t`, `gap_s` (start to start, which is what the cache sees: every lead call reads and so refreshes the prefix),
  `idle_s` (previous end to this start), `duration_s`;
- `ttl`, `prompt_tokens`, `cache_read`, `cache_write`, `n_msgs`, `event`.

No prompt content goes in it; a test checks that. After the $3 pilots:

```
.venv/bin/python -I staging/c4/tools/lead_gaps.py <C4_ROOT>/ours-pilot/guard <C4_ROOT>/stock-pilot/guard
```

It prints per run: lead calls, gaps over 5 min / over 1 h, median / p90 / max gap, how many lead calls after a long
gap really found the cache cold (read < half their prompt), and an estimate on the pilot's own calls. A 1 h lead
would turn the re-writes after 5-60 min gaps into reads (saves write 5m minus read rate on the previous prompt), and
pay $4 instead of $2.50 on its other writes. Karl decides from that; `GUARD_LEAD_CACHE_1H=1` in the arm file turns it
on.

### Thinking, wrap-up, money

**Thinking blocks.** Sonnet 5.5 binds thinking blocks to the conversation, and OpenAI messages cannot carry them.

- The guard keeps each answer's blocks. Its key is the answer's tool-call ids, or a hash of its text.
- When the client sends that turn back, the guard sends the stored blocks verbatim (thinking included). This happens
  only if the turn's prefix (system, tools, earlier turns) is unchanged and the chain of earlier blocks is intact.
  That is an emulation of the API's history check.
- Our compaction (summary + the last turns kept) therefore strips thinking from the kept turns instead of drawing a
  400.
- Safety net: `thinking.block_binding.prefix_mismatch_behavior: drop_block` (beta
  `thinking-binding-controls-2026-08-01`). The API's drops are logged as `input_transformations`.
- On a 400 about a signature, the request is retried once without thinking. If the API refuses the beta itself, the
  guard switches to strip mode for the rest of its life. `--thinking-replay strip` never sends thinking back.

**Wrap-up without tools.** Our middleware drops the tools for the final wrap-up call while the history still holds
tool calls, and the API refuses tool blocks without tools. The guard sends the conversation's last tool list again
with `tool_choice: none`. That keeps the cache and the thinking blocks valid. With no list on record, the tool blocks
go as text.

**Money.**

- Every response's usage is priced from pricing.json: input $2, output $10, cache write 5m $2.50 / 1h $4, cache read
  $0.20 per MTok. The API's 5m / 1h split is used when given.
- Before a request is sent, its **worst case** is reserved:
  - input: the request's bytes x `--input-tokens-per-byte` (1.0 = a token per byte, an upper bound) + 2000, priced
    at the cache-write rate;
  - output: all of `max_tokens`.
  - Example: 200K-token input + 64K output = $1.14.
- A request is refused with **HTTP 402, nothing sent**, when settled spending + its worst case would pass a cap.
  - The caps: the research cap (research requests only, below), the run cap, the total cap (every run in the shared
    ledger), or the optional agent cap (requests with tools only; off, the reserve does its job).
  - The message names the cap and the numbers, e.g. "cap reached - the run cap of run o03-ours $40.00 would be passed -
    spent $39.12 + this request's worst case $1.07 ... Refused; nothing was sent to Anthropic."
- A request that would fit once the running requests settle waits for them (up to 900 s) instead.
- Usage that cannot be known is charged at the reserved worst case (or input + max_tokens of output once the stream
  had started). That covers a cut-off stream, a timeout, or a guard process that died with requests open (found at
  the next start).
- The ledger (one JSON file, flock) survives restarts. Restarting a guard does not reset a run.

### Report reserve (Karl 10-29)

- `--report-reserve` / `GUARD_REPORT_RESERVE`, default **0.22** (in the guard and in both arm files; 0 = off; the
  arms may differ). Karl's range is about 0.20-0.25.
- Research requests (every class except report / verify / synth, see [the classes](#how-calls-are-classified)) are
  held to the **research cap = (1 - reserve) x run cap**: ours $31.20 of $40, stock $9.36 of $12, pilots $2.34 of $3.
  It counts everything the run has spent so far, report-stage calls included. So when research stops, at least the
  reserve is left.
- Past it, a research request gets the usual 402 with code `research_cap`: "cap reached - the research cap of run
  ... (the run cap $40.00 less the 22 % kept for the report stage; this request is research: class agent) $31.20
  would be passed ... Refused; nothing was sent to Anthropic. Report-stage requests may still use the rest of the run
  cap."
- Report-stage requests may use the whole run cap (then the run cap refuses them, as before).
- What LDR does with the refusal: the openai client raises on 402 (no retry). For the lead, LDR's agent loop ends in
  an error and falls back to its synthesis (report stage). Our build then runs its report writer from the evidence;
  stock runs its citation pass. A refused subagent ends with "Research on '...' failed: ..." (the guard's message),
  which goes back to the lead. A refused compaction may be retried by the deep package's effort ladder; each retry
  is refused again at no cost. Real LDR behaviour on a 402 is still unmeasured (pilot).
- The summary and `/v1/guard/status` show `caps_usd.research`, `report_reserve` and `stage_spent_usd` (research /
  report).

### Logs and the key

**Logs** (in the arm's guard/ folder):

- `costs-<run>.jsonl`: one line per request. Class, role (lead / sub), stage, effort and its source, max_tokens, worst
  case, usage, cost, run and total spent, the cache decision, thinking replayed / stripped, notes, dropped fields,
  retries, refusal category, `input_transformations`. **No prompt text, no headers, no key.**
- `summary-<run>.json`: totals per token type, cache-read share of the prompt, spent (also per stage), refused, caps
  (also the research cap), rates. Written at start and after every request.
- `lead-gaps-<run>.jsonl`: one line per lead call (times and token counts, see above).

**The key.**

- It is read from `--key-file` inside each request and handed to that request's SDK client (`with_options`). The base
  client holds a placeholder.
- Every `ANTHROPIC_*` variable is deleted from the guard's environment at start. The tests set `ANTHROPIC_API_KEY`,
  `_BASE_URL`, `_CUSTOM_HEADERS` and `_LOG`, and none of them had any effect.
- The upstream must be `https://api.anthropic.com` or loopback (tests). Redirects are not followed.
- Anything shaped like `sk-ant-...`, and the request's own key verbatim, is masked in every error text and log line.
- At start the key file is only `stat()`ed: it must exist, and the guard warns if group/other can read it.

## Caps (arms/*.env; all draft)

| | run id | run cap | research stops at (reserve 22 %) | notes |
|---|---|---|---|---|
| pilot ours | o03-ours-pilot | $3 | $2.34 | `C4_RUN_SUFFIX=pilot GUARD_RUN_CAP_USD=3 ./c4-arm.sh start ours` |
| pilot stock | o03-stock-pilot | $3 | $2.34 | same with `stock` |
| ours | o03-ours | **$40** | $31.20 | agent cap off (the reserve replaces it) |
| stock | o03-stock | **$12** | $9.36 | |
| all | (ledger) | **$60 total** | | `GUARD_TOTAL_CAP_USD=60` in both arm files; one ledger: results/bench2/sonnet55/ledger.json |

The pilots count against the $60. $3 + $3 + $40 + $12 = $58, so the last run can be refused by the total cap before
its own cap.

## How to run it later

**Prerequisites:**

- The LDR fixes chain has ended.
- C3 is installed (the package's `deep/modelprofile.py` and `~/ai/deep-research/profiles/`).
- Karl's credits for the month are confirmed and the cost estimate is redone and sent to him (plan). The Opus 4.5
  hard set comes first in November.

**Steps:**

1. **Build the stock install** (arm b, not done here: it needs a pip install). Make a separate venv from the pinned
   LDR 1.10.7 wheel at `~/ai/deep-research/stock-ldr/.venv` (or set `STOCK_VENV`). Interim:
   `C4_STOCK_MODE=baseline-site` runs pristine LDR from the main venv with `baseline/site` first, which is how the
   baseline measurements ran.
2. **Install C4.** Copy the folder (tests optional) to e.g. `~/ai/deep-research/c4/`. c4-arm.sh uses the guard,
   pricing.json and run-ldr.sh of its own folder. The live run-ldr.sh needs no change for C4: the staged copy's strata
   path exports exactly C3's environment (tested), so replacing the live one is optional and can wait.
3. **Re-check prices** (Anthropic pricing page, Sonnet 5.5 incl. any long-context premium) -> pricing.json.
   `chmod 600` the key file.
4. **Review the arm files** with Karl, then set `GUARD_STATUS=measured` there or pass `C4_ALLOW_DRAFT=1`. The
   profile needs `LDR_ALLOW_DRAFT_PROFILE=1` while it is a draft; c4-arm.sh passes `C4_ALLOW_DRAFT` through.
5. **`./c4-arm.sh plan ours`** (and `stock`) shows the run id, folders, caps and the exact LDR environment. It starts
   nothing.
6. **Each arm's LDR has its own data folder**, so make its account in the web UI (127.0.0.1:5011 / 5012) and set the
   per-account settings `ldr-client.py setup` sets (llm.streaming, request_timeout, max_retries, the keyless engines
   off). ldr-client.py has 127.0.0.1:5000 hard-coded (open question 6).
7. **Pilots:** `C4_RUN_SUFFIX=pilot GUARD_RUN_CAP_USD=3 C4_ALLOW_DRAFT=1 ./c4-arm.sh start ours`, submit the frozen
   o03 text, let the cap or a 15-minute stop end it, then `./c4-arm.sh stop ours`. Same for stock. A $3 pilot stops
   its research at $2.34 (the reserve), so the pilot also shows how LDR takes a research refusal and whether its
   report stage then runs on the reserve. Read `guard/summary-*.json`:
   - tokens per minute;
   - cache-read share (should dominate on the agent loops);
   - one-shot calls: `cache.why = one-shot` and no cache-write tokens (per class in the JSONL);
   - `stage_spent_usd` and the `research_cap` refusals (what each arm did after its research stopped);
   - `input_transformations` (should be empty: else the thinking emulation is off);
   - refusals and 429s.
   - **The lead's gaps:** `tools/lead_gaps.py <arm folder>/guard` for both pilots ([above](#the-leads-gaps-the-1-h-decision)).
     Karl decides on `GUARD_LEAD_CACHE_1H`.
8. **Main runs:** the same without the suffix; ours $40, stock $12, the same day as Karl's web-app run (arm c).
9. **Grading** as the plan says (blind A/B/C, reference checklist, citation check on the local model).

Per-class cost of a run:

```
.venv/bin/python -I -c "import json,sys,collections; d=collections.Counter(); [d.update({r.get('cls'): r.get('cost_usd', 0)}) for r in map(json.loads, open(sys.argv[1]))]; print(d)" <arm>/guard/costs-o03-ours.jsonl
```

## Tests - result 10-29 (Karl's settings): 45 / 45 pass (11-12 s, nice 19, run twice)

Run: `nice -n 19 .venv/bin/python -I -B staging/c4/tests/test_c4.py`. It writes tests/results/results.{md,json}. The
upstream is `tests/mock_anthropic.py` on 127.0.0.1. It speaks the Messages API's SSE events and simulates the prefix
cache (breakpoints, 20-block lookback). Only fake keys are used, and no live service, model or GPU is involved.

**New for Karl's 10-29 settings** (9 tests; the earlier 36 all still pass):

- **Effort high on both arm files**, as the guard reads them (sourced like c4-arm.sh does); `plan` shows it.
- **Classification**: 14 call kinds -> class / role / stage (lead, the lead's last answer, a tool-less wrap-up,
  subagent, extraction, compaction, report, verification, fallback synthesis, citation pass with and without an
  output prefix, fact check, unidentified -> research, the citation words deep inside a page -> research). Every mark
  is found in stock LDR 1.10.7's and the installed build's sources (15 checks).
- **Reserve** (mock, default 0.22, run cap $0.50 -> research cap $0.39): 4 lead calls, then the 5th is refused with
  `research_cap` / "cap reached", nothing sent; an unidentified tool-less call is refused too (the fallback); report,
  verify, citation pass and fallback synthesis then go through on the reserve; research stays refused; the run cap
  finally refuses the report stage; per-stage spending in the summary. Ledger unit test: the research cap's edge,
  report stage up to the run cap, reserve 0 = off.
- **Caching** (unit + mock): one-shot extraction / compaction / report / verify / citation calls carry no
  `cache_control`; a system prompt gets its marker only once a request with it was answered (no tail); agent loops
  get both; a tool-less continuation of the guard's answer gets the tail; a client-edited answer does not count.
  Through the guard process: the lead and a subagent at 5m by default, one-shots without markers, no 1h writes.
- **1 h switch**: on -> the lead's two breakpoints `ttl: 1h`, the subagent stays 5m, one-shots none, 1h writes priced
  at $4; the CLI refuses a global `--cache-ttl 1h`; c4-arm.sh refuses `GUARD_CACHE_TTL=1h`, a bad reserve or a bad
  switch value.
- **Gap log**: only lead calls, the gap of a 1.2 s pause measured, idle time, only the listed keys, no prompt text;
  `lead_gaps.py` on it (`--ttl-s 1` for the test, `--json`) and on a made-up log (gaps over 5 min / 1 h, cold calls,
  the 1 h estimate's numbers).

**Existing tests changed on purpose** (the old behaviour was "caching on every request"):
`test_translate_plain` and `test_plain_nonstream` now expect no `cache_control` on a one-shot call (the latter also
sends the same system prompt again and expects its marker only); `test_cache_markers_tools_only_and_1h` expects 5m
by default and 1h only on the lead with the switch. `test_1_run_cap_and_total_cap` and
`test_3_waits_for_running_requests` start their guard with `--report-reserve 0`, since they test the run cap alone
(their plain calls are research and would otherwise stop at 78 %).

- **Translation round trips** through the real openai SDK and through LangChain `ChatOpenAI(streaming=True)
  .bind_tools()`, LDR's own client:
  - plain, streamed text with the usage chunk, tools -> tool_calls -> tool results;
  - the second call carries the first answer's thinking block verbatim;
  - the first call's prompt is a byte-identical prefix of the second's (mock: cache reads > 0).
- **Effort mapping**: precedence request > class > default > none, aliases, `--effort-map`, unknown -> 400 with
  nothing sent, class detection (extract / compact / report / verify marks).
- **cache_control placement**: system marker, tools-only marker, at most 4 (and the rule above).
- **Thinking replay**: replay; compaction strips the kept turns and keeps the new ones; an edit in the middle strips
  the rest; leading-run removal; client-edited turns; strip mode; tool-less wrap-up (tools again + `tool_choice:
  none`, or as text).
- **Cost accounting**: exact prices incl. 5m / 1h writes and reads, long-context multipliers, worst case, log and
  summary sums.
- **Caps**:
  - the run cap refuses exactly when spent + worst > cap (5 answers at $0.09 against $0.50);
  - a second arm on the same ledger is refused by the total cap;
  - the agent cap stops tool calls but not the report stage;
  - a request waits for a running one and then proceeds;
  - every refused request never reached the mock;
  - a dead process's reservation is charged; a corrupt ledger raises (the guard then answers 500 to every
    request).
- **Errors**:
  - 429 retried after retry-after; 529 twice -> 503 at $0;
  - refusal -> content_filter + category;
  - a stream cut mid-way -> error chunk, charged input + max_tokens;
  - signature 400 -> one retry without thinking; a refused beta latches strip mode.
- **Keys**:
  - the file's key is what reaches the mock; it is re-read per request; a missing file -> 500, nothing sent;
  - `ANTHROPIC_*` variables ignored;
  - an upstream error quoting the key is masked, for an `sk-ant-` key and for one of another shape;
  - the key never enters `os.environ`;
  - none of the 4 fake keys appears in any of the 85 files written or the 54 response bodies.
- **Launcher**:
  - `bash -n`;
  - **strata mode exports exactly C3's environment** (4 scenarios);
  - guard mode exports the guard URL, model, 1M context, 64000 max_tokens, 4 workers, and arm-local data / run /
    deep-runs / clock / next-job paths, and creates nothing;
  - refusals: live folders, port 5000, a non-loopback guard, the workspace itself, a draft profile;
  - `c4-arm.sh plan` for ours, pilot overrides, stock (refused without its venv; baseline-site works), draft refusal,
    run cap above the total.

## Not tested without a real call

1. **The real API's acceptance of the request shape:**
   - `thinking: {type: adaptive, display: omitted, block_binding: {...}}` with the beta header;
   - `output_config.effort` on `claude-sonnet-5-5`;
   - top-level `cache_control` + the system marker together;
   - our block order.
   - The SDK types accept all of them. The mock accepts anything.
2. **Whether the history-check emulation matches the API** (`input_transformations` should stay empty). Also whether
   the API wants thinking back on an in-flight tool round at all when it is stripped. The guidance says "should".
3. **Real cache behaviour:**
   - hit rates on LDR's agent loops;
   - the minimum cacheable prefix (a short system prompt marked "head-seen" may be below it: then nothing is cached
     and nothing is charged extra);
   - parallel subagents writing separate entries;
   - whether the lead's cache goes cold while it waits on long subagents (5m TTL): the gap log answers it;
   - the mock never expires entries, so the gap log's "cold" column is only meaningful on the real API.
4. **Real usage fields**: the `cache_creation` 5m/1h breakdown, `output_tokens_details`, refusal billing.
5. **Whether the byte-count worst case really bounds the billed input**, including replayed thinking, which is billed
   by its hidden thinking tokens, not its signature bytes.
6. **Rate limits** at 4 workers (Sonnet 5.5's own pool), and 429 / 529 behaviour beyond two retries.
7. **LDR end to end through the guard**: our middleware, stock LDR's calls, the web UI's model list
   (`/v1/models` is served), timeouts at LDR's 1800 s, and how both builds take a 402 (`research_cap`) mid-run.
8. **The launchers' `start` / `stop` paths** (only `plan` / `env` and the refusals ran).

## Open questions (for Karl)

Settled 10-29 (Karl): stock effort (high, matched), the agent cap (replaced by the 22 % report reserve), caching on
one-shot calls (none), the TTL (5m; the lead's 1 h after the pilots' gap check).

1. **Our arm's extraction effort.** `extract=low` stays (our profile's setting) while the agents and stock run at
   high. Matched would be `GUARD_CLASS_EFFORTS=agent=high` (extraction then at high too, at a higher cost per page).
2. **The reserve's size per arm.** 0.22 on both. Stock's report stage is one citation pass (smaller than ours), so
   stock could take e.g. 0.20, if Karl wants its research to go further.
3. **Arm (a)'s items.** The draft has the six fixes (`LDR_DEEP_FIX=all`) + the code tool. Add `,read,claims` (items
   5 + 6), setup or critic if they are in the build by then?
4. **ldr-client.py** has 127.0.0.1:5000 hard-coded. A URL option (a one-line change in a live tool, not made here) or
   set up each arm's account by hand?
5. **`--input-tokens-per-byte`.** 1.0 is a strict bound but holds back ~$1-2 per call near a cap. 0.5 (2 bytes per
   token) is realistic for English and JSON but not a proof.
6. **Prices / long-context premium.** pricing.json is from the 10-06 cache and the bundled reference. It assumes no
   premium above 200K input; check on the day.
7. **Fix 6's time plan** (Flash-Next seconds) and the profile's paper caps (compaction 200K, page 240K ch, evidence
   150K) stay as C3 left them, unmeasured on Sonnet.
