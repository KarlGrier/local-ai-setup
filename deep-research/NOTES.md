# Local Deep Research on Strata — running log

Workspace `/home/USER/ai/deep-research` (venv, caches, LDR data dir all here). 127.0.0.1 only, no sudo,
nothing changed in `~/ai-speed-testing/strata-compare` (read only: REPORT.md, configs, logs, /metrics).

## 2026-09-29

**18:00 — state found**
* 8080 serves **C\*6**, not C\*5: `server.py --config configs/Cstar6.json` started 17:42 (run log
  `logs/run/strata_20260929T174209_8080.log`, engine log `logs/engine-Cstar6.log`), both GPUs
  (`--expert-cache-device1 3300`), `--chat-cache 6 --chat-cache-mib 16384`, model id
  `strata-qwen3.8-flash-next-iq3s`, n_ctx 131072. SearXNG on 127.0.0.1:8888 answers JSON.
  → Tested against this as found; not switched to C\*5 ("leave Strata as you found it").
* Shared settings in use: `configs/Cstar6.shared-settings.json` = reasoning_effort "high", temperature 0.6,
  top_p 0.95, top_k 20 (C\*5's copy has temperature 1.0). Not touched.
* MemAvailable 33 GB, 32 cores, 955 GB disk free.
* Someone used Strata until ~17:53 (last /metrics entry) — tests could overlap with the user's own use;
  I check `/metrics` `live.state` before each run.

**How Strata handles effort (server.py `with_shared`, chat_template.jinja):** the shared file's
`reasoning_effort` is filled in only when an OpenAI request has no `reasoning_effort`, no `reasoning`, and no
`enable_thinking`/`reasoning_effort` in `chat_template_kwargs`. The template maps `high` → `xhigh` (and defaults to
xhigh); it accepts xhigh / medium / low; `enable_thinking: false` in `chat_template_kwargs` turns thinking off. So a
client that sends its own `reasoning_effort` per call overrides the shared default without touching the file.

**Measurement sources (all passive):** `GET /metrics?requests=all` (last 500 requests: prompt_tokens, reused,
output_tokens, prompt_ms, decode_ms, finish), engine log lines `chat cache: parked / restored / dropped`
(counted by line offset before/after each run), `GET /status`.

**18:05–18:30 — Step 1: review of LDR's latest release (v1.10.7) before installing**
* Latest release: **v1.10.7** (GitHub release 2026-08-28, "Security hardening for notification URLs and the news
  subscription API"; PyPI upload 2026-08-28 21:35). Nothing newer on PyPI. Pinned: `local-deep-research==1.10.7`,
  wheel sha256 `b8d96c74ae43432744a400ddb3a53df624956e827d1f4db0ac025b7ae3217284` (matches PyPI), sdist
  `47e685d5…`. Copies in `src/`, unpacked wheel in `src/whl/` (597 .py files) — the review below is of that code.
* **What it installs:** 84 direct deps → **299 packages** (dry-run report `tmp/pip-report.json`), all from
  files.pythonhosted.org. The heavy part is `sentence-transformers` → torch 2.14 + CUDA 13 wheels (nvidia-*,
  triton, several GB, only in the venv); also spacy, crawl4ai (+ patchright/playwright Python packages, no
  browsers are downloaded unless `playwright install` is run), weasyprint, pandas/pyarrow, datasets,
  sqlcipher3-binary (encrypted per-user DB), langchain 1.4 / langgraph 1.2 / langchain-openai 1.6 / openai 3.22.
  Console scripts: `ldr-web`, `ldr-mcp`. No post-install hooks (a wheel runs no code at install).
* **What it listens on:** Flask-SocketIO, **default host 0.0.0.0**, port 5000 (`web/server_config.py`) →
  must set `LDR_WEB_HOST=127.0.0.1`. Login required; each user's data is a SQLCipher DB keyed by that user's
  password (`<data>/encrypted_databases/ldr_user_<sha16>.db`). Registration open by default.
* **Where it writes:** everything under `LDR_DATA_DIR` if set (research_outputs, cache, logs,
  encrypted_databases, library, journal_data, models, config), otherwise `~/.local/share/local-deep-research`.
  Third-party libs have their own caches (HF, torch, nltk, tiktoken, crawl4ai `~/.crawl4ai`, matplotlib) → the
  launcher points all of them into the workspace.
* **What it connects to by itself:** no telemetry, no update check (grepped for update/telemetry/analytics/sentry/
  posthog: nothing). Web assets are bundled (no CDN). Outbound traffic happens only through what a research
  uses: the chosen search engine(s), the fetch tool (downloads result pages; SSRF-guarded: private/loopback
  addresses refused unless allowed, DNS pinned), and the LLM endpoint. Conditional downloads: journal-quality
  data (OpenAlex S3, DOAJ, GitHub raw) only when an academic engine's journal filter runs; HF models only for
  local embeddings (library/RAG); benchmark datasets only from the benchmark page. A news-subscription scheduler
  runs only for subscriptions you create. Default `search.tool`/primary is `searxng` with instance
  `http://localhost:8080` — i.e. it would point at **Strata** unless changed; SearXNG URL is refused for
  private/loopback unless env-locked (`LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_INSTANCE_URL`), allow-listed,
  or `LDR_SEARCH_ALLOW_PRIVATE_ENGINE_URLS=true`. Env-lock is the narrowest; using it.
* **LLM path (openai_endpoint provider):** `ChatOpenAI(model, api_key, base_url, temperature, max_tokens,
  [streaming], [max_retries], [request_timeout])`. `llm.streaming`, `llm.max_retries`, `llm.request_timeout` are
  read only if present — they are NOT in default_settings.json, and env overrides only apply to keys that exist in
  the defaults or the user's DB → they must be created per user (settings API allows new `llm.*` keys).
  Defaults otherwise: openai client read timeout 600 s, 2 retries. `max_tokens` = min(`llm.max_tokens` 30000,
  0.8 × context window). **No `reasoning_effort` / `extra_body` / `model_kwargs` anywhere** (only Ollama gets a
  thinking switch) → LDR cannot send reasoning_effort, per call or at all.
* **Context window:** `llm.local_context_window_size` applies only to providers ollama/llamacpp/lmstudio. For
  `openai_endpoint` the window is `llm.context_window_size` when `llm.context_window_unrestricted` is false
  (default true = unlimited). → set both (local 131072 as asked, and unrestricted=false + 131072 so it
  actually applies to this provider).
* **langgraph-agent strategy:** a lead tool-calling agent (`create_agent`, up to `max_iterations` 50) with tools
  `web_search`, `fetch_content` and `research_subtopic`; the latter runs 2–5 (≤10) subagents in a thread pool of
  `langgraph_agent.max_subagent_workers` (default **4**), each its own agent with up to 8 sub-iterations and a
  hard 1800 s per-subagent timeout (constant). `fetch_content` (default mode `summary_focus_query`) downloads a
  page (≤10,000 chars) and makes one **extraction LLM call** per page without tools (prompt starts "You are a
  content-extraction step inside a multi-step research agent.") — these are the "small steps".
* **Strata side that matters:** non-streamed requests get no disconnect watcher (server.py `_openai`: only the
  SSE path calls `watch_disconnect`), so if LDR times out or cancels a non-streamed call, Strata keeps generating
  it and the retry queues behind it. Streamed requests stop within a chunk on disconnect and get `: keep-alive`
  every 10 s while a long prompt is read (but nothing while waiting in the queue). → use `llm.streaming=true`.
* Prompt + max_tokens > 131072 − slack → Strata answers HTTP 400 (no `--fit-max-tokens` on this server). With
  max_tokens 30000 that is prompts over ~101K tokens.

**18:30–18:50 — install + client checks**
* `pip install src/local_deep_research-1.10.7-py3-none-any.whl` into `.venv` (86 s; `PIP_CACHE_DIR`,
  `XDG_CACHE_HOME`, `TMPDIR` in the workspace): 299 packages, venv 7.7 GB, pip cache 3.4 GB. Frozen list:
  `requirements.lock.txt`. `find ~ -newer` after install: nothing written outside the workspace (only Chrome's own
  files changed). pip warns urllib3 2.8 / chardet 7.6 "doesn't match a supported version" for `requests` — cosmetic.
* `tests/lc_smoke.py` — LangChain `ChatOpenAI` exactly as LDR builds it, `bind_tools` + invoke, against Strata:
  tool call parsed correctly both non-streamed and streamed; streamed responses also carry usage (Strata sends
  `usage` with `cached_tokens` = reused prompt tokens). langchain-openai 1.6 sends `max_tokens` as
  `max_completion_tokens` (Strata reads both).
* **tools/strata-proxy.py** (stdlib, 127.0.0.1:8090 → 8080): logs every LLM call as JSONL (class agent/extract/
  other, conversation id = hash of the first two messages, usage incl. cached tokens, timings, finish) and, per a
  mode file re-read per request, adds `reasoning_effort` (or `enable_thinking: false`) to LDR's extraction calls
  only. Needed because LDR cannot send reasoning_effort (step 1); it is also the measurement tap.
* **Disconnect test** (streamed, 3000-token essay, client leaves at 6 s): via proxy Strata idle **0.28 s** later
  (finish "disconnect"), direct 0.28 s (finish "cancel"). **Non-streamed**, client leaves at 4 s: Strata kept
  generating to the end — idle **12.4 s** later, finish "length", 1500 tokens. ⇒ `llm.streaming=true` is required
  for LDR cancel / timeouts to free Strata.

**18:55 — first research run, and two problems**
* Account `karl` created via the API (`tools/ldr-client.py setup`, password in `run/ldr-credentials`, mode 600); per-
  account settings applied: llm.streaming=true, llm.request_timeout=1800, llm.max_retries=1,
  search.search_strategy=langgraph-agent. Env-locked settings confirmed effective (provider/url/model/temperature
  0.6/max_tokens 30000/context 131072 both keys/workers 1/SearXNG URL + json).
* **t0 (results/t0-default-engines) — test 1 as configured so far, terminated at 31 min, no report.** 158 LLM calls:
  the langgraph agent had, besides `web_search` (SearXNG), 12 more tools = every keyless engine (arxiv, pubmed,
  wayback, wikipedia, wikinews, gutenberg, openalex, openlibrary, pubchem, semantic_scholar, stackexchange, zenodo),
  queried **directly** (not through SearXNG). Those engines have `needs_llm_relevance_filter=True`: each search fires
  ~10 **parallel** relevance-filter LLM calls (ThreadPoolExecutor) → they queue on Strata; at xhigh each thought
  200–2,600 tokens to return a few characters. 76 such calls = 64K generated tokens, 3,326 s of summed call time
  (incl. queueing). Wikipedia rate-limited us ("non-JSON response"). Strata chat cache during the run: parked 114,
  restored 27, dropped 84 — every burst of ~10 unrelated prompts pushed the agents' conversations out.
  Extraction calls: 17, ~40K generated tokens (one: 8,156 tokens / 78 s for a ≤1500-char quote list).
  **Fix:** agent tools = SearXNG + fetch + subtopics only: `agent_enabled=false` for the 17 other engines (13 via
  LDR_* env in run-ldr.sh, 5 unregistered ones per account in ldr-client setup). `policy.egress_scope=strict`
  was considered and rejected: it also denies public hosts to the page fetcher.
* **Terminate (first data point):** Strata idle **22.6 s** after LDR's terminate returned — LDR stops
  cooperatively between steps; the in-flight streamed calls ran to their end (no disconnect).
* **SearXNG crashed at 18:45:00** — kernel: `tokio-rt-worker: segfault … in python3.12` (granian's Rust runtime),
  then "Unexpected exit from worker-1", granian shut down. Not memory (MemAvailable ≥ 29 GB). Strata unaffected.
  Restarted with its own script `websearch/searxng.sh start` (same as switch-model.sh does; not edited).
  The driver now checks SearXNG before each run.

**19:00–19:45 — t1 (SearXNG only), wrap-up**
* t1-checkable (results/t1-checkable): **completed in 1529.5 s (25.5 min)**, 178 LLM calls (123 agent / 53
  extract / 2 other), 0 errors, prompt 687K tokens of which 520K reused from Strata's cache, 126K generated,
  largest context 17.7K. Extraction = 1,113 s of 1,551 s LLM time, 92K generated tokens, thinking:answer ≈ 10:1.
  Lead conversation: 51 calls, re-read 4× (17K tokens). Chat cache: parked 105 (median 2.8K tokens / 156 MiB, max
  929 MiB), restored 41, dropped 64 (median 2.7K tokens = mostly extraction prompts). Answer correct (5 Aug 1858 /
  16 Aug first messages / 3 Sep failure / Cyrus W. Field). 30/32 cited URLs resolve (gutenberg search URL 404; one
  Wikipedia URL truncated by my regex at "(" — checker bug, not LDR). MemAvailable min 29.4 GB.
  The terminate I sent at the end arrived just after completion (Strata already idle).
* **User asked to stop testing and wrap up** (19:40). Not run: t2 current events, t3 long open-ended, workers=2,
  extract-effort comparison, timed mid-run cancel. Tooling for them is in `tools/ldr-client.py`.
* Chat-cache proposal (not applied): `--chat-cache 16 --chat-cache-mib 16384`; the slot count, not the budget,
  limits it for LDR's small conversations; expected gain ~1 % (agent re-reads ~53K tokens ≈ 15–20 s per 25 min).
* **State left:** Strata C\*6 on 8080 untouched (still the process started 17:42); SearXNG on 8888 restarted by me at
  18:5x after its crash (its own script); LDR (127.0.0.1:5000) + strata-proxy (127.0.0.1:8090, pass-through) left
  running for you; no test scripts running. README.md has start/use/stop.
* **Correction (19:50):** SearXNG crashed **again at 18:54:53** during t1 — same segfault (`tokio-rt-worker …
  ip 5d9c24 … in python3.12`), ~4 min after my restart. LDR log: 69 SearXNG errors after that; the agent carried on
  by fetching pages directly (Wikipedia, history.com). So t1's correct answer came from direct fetches + model
  knowledge, not a working search. Both crashes happened under LDR traffic (the chat page's search ran 2 h in
  round 5 without one); LDR GETs SearXNG's HTML root page then /search with browser-style headers for every
  search. Restarted SearXNG again with `websearch/searxng.sh start`. Not fixed (strata-compare is off limits);
  options in README "What happened" item 5.

## 2026-09-30 — tuning for depth (task: deepest research; run time doesn't matter)

Rules for this round: no sudo, 127.0.0.1 only, everything in this folder, MemAvailable ≥ 20 GB, this log. New: LDR may
be patched in the workspace (patches kept as files), LDR gets its own SearXNG here. strata-compare stays read-only;
Strata config changes are proposals only. **Strata C\*7 runs on 8080 under a 48-hour passive uptime monitor until
~04:10 Thu Oct 2: no stop/restart before then.** Long jobs run as background queue scripts writing to files.

**07:16 — state found:** Strata C\*7 (`configs/Cstar7.json`, started 04:09, idle), strata-compare's SearXNG on 8888
(granian, restarted 04:09 by switch-model.sh), round 7's `work/r7/uptime_monitor.py --hours 48`. LDR and
strata-proxy stopped. MemAvailable 34 GB. PyPI: LDR 1.10.7 and granian 2.8.3 are still the latest releases.

**07:17–07:30 — why SearXNG's granian segfaults under LDR (root cause found and reproduced)**
* Kernel log, both crashes: `tokio-rt-worker: segfault … ip 5d9c24 … error 6 in python3.12`. 0x5d9c24 is inside
  `_PyEval_EvalFrameDefault` (`mov %r14,-0x10(%rax)`: a write to a frame's value stack) → Python bytecode wrote into
  a freed frame stack. The thread name is inherited: granian's extra pool threads are plain Rust threads spawned from
  a tokio worker.
* Timing: each crash came **29.4 s and 30.0 s after LDR's last SearXNG request**, and the requests before it were
  concurrent pairs (LDR runs parallel searches). 30 s = granian's `--blocking-threads-idle-timeout` default.
* granian 2.8.3 `src/blocking.rs`: with `--blocking-threads 8` the pool keeps one thread forever and **spawns extra
  threads only when requests overlap**; an extra thread exits after 30 s idle, and PyO3 then releases its GIL guard
  → `PyGILState_Release` → `PyThreadState_Clear` → the thread's `threading.local` data is freed.
* SearXNG keeps a per-thread SQLite session (`searx/sqlitedb.py` `DBSession`, used by the engines' cache) whose
  `__del__` closes a connection that has a user-defined SQL function (`regexp`). Closing it makes sqlite call the
  function's destructor, which does **`PyGILState_Ensure/Release` inside the outer `PyThreadState_Clear`**.
* That is CPython bug **gh-119585** (fixed in 3.12.4 by PR #119861: keep `gilstate_counter` > 0 while clearing).
  Ubuntu's python3.12 **3.12.3-1ubuntu0.17** does not have it (changelog; disassembly of `PyGILState_Release` calls
  `PyThreadState_Clear` with the counter at 0). The nested release deletes the thread state (frees the frame stack)
  while `DBSession.__del__` is still running → write into freed memory → SIGSEGV.
* Why the chat page never crashed it: it sends one search at a time, so granian never spawns (or reaps) an extra
  thread. LDR sends 2–3 at once.
* **Reproduction without SearXNG or network** (`searxng/tests/min_app.py` + `burst.py`, granian 2.8.3, bursts of 4
  concurrent requests, idle timeout 5 s): system Python 3.12.3 **crashed 3/3 on the first idle period**,
  faulthandler: `min_app.py line 16 in __del__` (the `conn.close()`). Controls in `searxng/logs/repro-matrix.txt`.
* Controls (same app/pattern): B no user function 0/30 cycles crashed; **C Python 3.12.13 (uv's standalone build,
  in `searxng/python/`) 0/30**; D 3.12.3 with `--blocking-threads 1` 0/30 (one thread never exits).
* **But on real SearXNG the SQLite session is not the trigger**: a tracing wrapper (`tests/sx_trace.py`) shows
  SearXNG's `DBSession`s are created and destroyed only in SearXNG's *own* engine threads (Python-created threads
  start with `gilstate_counter = 1`, so a nested Ensure/Release cannot delete them). Their OS name is inherited from
  the granian thread that started them, so "tokio-rt-worker" in the kernel log does not tell which kind crashed.
  Replays of LDR's pattern against real SearXNG on 3.12.3 (urllib; LDR's own `SearXNGSearchEngine` class in t1's burst
  shape, 2 and 3 concurrent; LDR's 95 real queries from yesterday) have **not** crashed so far (runs continue in the
  background, faulthandler on). What is proven: the crash class (a destructor re-entering the GIL API while a
  PyGILState-created thread state is cleared, write into the freed frame stack) is CPython 3.12.3's gh-119585, it
  fits the kernel signature and the 30 s timing, and 3.12.13 removes it. Which SearXNG object carries it: open.

**07:30–07:50 — LDR's own SearXNG (`searxng/`, 127.0.0.1:8889)**
* git clone of searxng master (`a9d9900`, 2026-09-30), granian 2.8.3, **CPython 3.12.13** venv; `searxng/searxng.sh
  start|stop|status` with a keeper loop (restarts granian if it exits, logs it) and faulthandler on. A second
  instance "baseline" (127.0.0.1:8890) has the chat page's engine choices, for baseline measurements only.
* **Why yesterday's searches came back empty:** current SearXNG enables only Brave and "google cse" as general web
  engines (Google, Bing, DuckDuckGo are off by default), and both are suspended from this address ("too many
  requests"). Engine survey (each engine alone, 3 queries, `logs/engine-survey.json`): works — google (2/3), bing,
  duckduckgo, startpage, yahoo, yandex, yep, seznam, mwmbl, and academic arxiv, semantic scholar, pubmed, europepmc,
  crossref, google scholar; fails — brave, google cse (suspended), mojeek (denied), qwant (CAPTCHA), openalex (HTTP
  error). Bing sometimes returns off-topic pages (weight 0.5).
* New config (`searxng/settings.yml`): the working web engines + the academic ones (category "science"). LDR queries
  `general,science` → 90–160 merged results per query (was 0); the web consensus ranks first, academic results
  fill the rest of LDR's 50. Bangs work inside the one tool: `!science`, `!arxiv`, `!pubmed`, `!gos`, `!se`.
  PubMed's keyless API allows 3 requests/s; SearXNG's suspension after "too many requests" cut from 3600 to 120 s.
* Soak started 07:53 (`tests/soak.py`, 4 h): LDR's request pattern in bursts of 2–6 concurrent searches every
  31–45 s (so every burst's extra threads are reaped), Wikipedia/Wikidata only so the web engines LDR needs are not
  burned; worker RSS/fds/threads every 10 min (`logs/soak-main.jsonl`). The real LDR runs today and tonight use
  the same instance with the real engines.

**07:40–08:00 — the deep-research patch (`patches/ldr/`, active only with `LDR_DEEP=1`)**
* New package `local_deep_research/deep/` + hooks in the langgraph strategy and the fetch tool (3 patch files,
  `patches/ldr/apply.sh apply|revert|status`, `make-patches.sh` regenerates them from the install):
  - caps: lead 200 model calls (was 50), subagent 30 (was 8), 8 subtopics per call (was 5; hard limit 12), page
    text 120,000 chars (was 10,000), extraction output 4,000 chars (was 1,500), 50 results per search with
    snippets shown to the agents cut at 300 chars (a 50-result search cost ~11K tokens of context uncut);
  - a time budget for the research phase (default 3 h; subagents 1 h each): then agents are told to wrap up and
    lose their tools (no more hard 1,800 s kill that threw a subagent's work away; the thread-abandon backstop is 2 h);
  - evidence store: every search result, every fetched page's full text + extraction, every subagent report
    (`results/deep-runs/research-<id>/evidence.jsonl`); a page cache so a page is downloaded once per research;
  - context management (middleware on the lead and every subagent): at 56K prompt tokens (exact count with the
    model's own BPE vocabulary, copied to `deep/tokenizer/`) older steps are replaced by running research notes
    (model-written; every finding with its [N]) plus a deterministic list of the sources and searches involved;
    before every call, if system + history + tools + max_tokens would exceed 131,072, the largest tool results of
    that request are shortened; strata-proxy retries a context-400 with max_tokens cut to fit (tested: 131,072
    requested → clamped to 130,981, answered);
  - report stage: outline from all evidence → one call per section with that section's extractions and the most
    relevant passages of the stored pages → answer/key findings/limitations (keeps a format the question
    prescribes) → citation check: every sentence with [N] is checked against the cited page's stored text (or its
    snippet if never read); unsupported / partial claims are flagged inline and tabled.
* LDR's detailed-report mode is not used: issue #6640 is open; in 1.10.7 it passes only 1,000 chars of the research
  to the outline planner (#6711 fixed that on main, unreleased) and drops the initial synthesis from the report.
* `run-ldr.sh`: `LDR_PROFILE=deep` (default) or `baseline` (pristine 1.10.7 from `baseline/site/` first on
  PYTHONPATH + the baseline SearXNG). `tools/ldr-client.py` knows both and copies a deep run's files.

**07:51–08:15 — smoke test 1 (deep profile, 10-min research budget, compaction forced at 12K; the code as of 07:50)**
* Works end to end so far: 50 results per search, the evidence store (searches, full page texts, extractions),
  a subagent with its own budget found the primary source (the 1861 Joint Committee report, 80K chars), compaction
  and wrap-up fire. strata-proxy classifies the new call types (compact / report / verify).
* **xhigh thinking runs away on some calls:** a page extraction of a 29K-token page took 241 s and 26,825 generated
  tokens (4,135 chars of quotes); another extraction 18K+ tokens; a history-compaction call (4.5K-token prompt)
  thought for **30,000 tokens / 249 s and answered nothing** (finish = length), twice, so a compaction took 494 s
  and fell back to a truncated verbatim history. Fixes (in the code now, not in smoke 1): every deep call goes
  through `deep/llm.py` with an explicit effort per call type and, on an answer-less "length" finish, a retry one
  effort lower (xhigh → medium → low); compaction at medium; extraction effort `LDR_DEEP_EXTRACT_EFFORT` (the test
  below decides); compaction keeps a token-based recent window and only re-compacts after real growth; a subagent is
  not started when the research budget is used up.
* Per-call `reasoning_effort` from LangChain reaches Strata (`invoke(..., reasoning_effort=...)`, verified via the
  proxy log), so LDR itself can now set the effort per call type.
* Strata idle share with one worker (upper bound of what a second worker can win back): yesterday's t1 **8.8 %**.

**08:05 — the crash reproduced on real SearXNG** (old Python, LDR's own `SearXNGSearchEngine`, LDR's 95 recorded
queries from yesterday): granian's worker died in the idle period after the 4th burst (~30 s after the last
request), `Fatal Python error: Segmentation fault`; no thread is marked "Current thread" — the crashing thread had
lost its thread state while still running (the gh-119585 pattern). Replays with only telegraph queries survived 8 and
11+ cycles, so the trigger depends on what the queries make SearXNG do. A thread-state probe (ctypes
`PyThreadState_GetDict` + contextvars after each request) shows SearXNG leaves **no thread-locals and no context
variables** in granian's threads; the object whose destructor re-enters the GIL API is elsewhere (granian iterates
responses from Rust and drops Python objects without the GIL; PyO3 decrefs those later from whichever thread
attaches next — a candidate, not proven). Controls running: the same query set on 3.12.3 again and on 3.12.13.

**08:10 — extraction-effort test started** (`tools/extract-effort-test.py`, queue `tools/run-extract-test.sh`):
36 real extraction tasks (focus + question from yesterday's LDR runs, pages re-downloaded with LDR's fetcher: 16
short at the old 10,000-char cap, 20 long at 120,000 — incl. 12 from four other domains: GLP-1 trials, the EU AI Act,
the 2003 blackout report, PostgreSQL MVCC), each at low / medium / xhigh in random order, the deep prompt (4,000-char
limit). Scored by quality: verbatim rate (quotes found in the page), NOT RELEVANT agreement, and a blind listwise
ranking by the model at xhigh with the page in view; time and tokens reported only.

**08:15–08:25 — fixes after smoke 1; smoke 2 started (08:19, current code, 15-min budget, extraction at medium)**
* **My mistake:** `run-ldr.sh restart` also restarted strata-proxy, which cut the extraction test's in-flight call;
  the test then recorded ~107 connection errors as results within seconds. Fixed: `restart` restarts LDR only (the
  proxy has no LDR state; `stop` still stops both); the test now calls Strata directly and retries connection errors
  instead of recording them; the error records were removed and the test restarted (1 good result kept).
* Smoke 1 terminated (it had shown what it could; its remaining subagents started after the budget and wrote from
  memory). Also fixed: report calls may use up to 60K output tokens (within the context; per-call `max_tokens`
  verified through the proxy), subagents that would start after the budget are skipped and kept out of the report,
  the flag placement of the citation check (an anchor bug found with an offline run on a fake model). The three
  patch files applied to a pristine copy reproduce the installed code exactly.
* Compaction at medium: 38 s (the xhigh attempts took 250–494 s).
* Second crash reproduction with LDR's recorded queries on 3.12.3: crashed again (3rd idle period). So 2/2 runs with
  LDR's queries crashed within 3–4 idle periods, 0 crashes in 34 idle periods with telegraph-only queries; the same
  query replay on 3.12.13 continues (no crash so far).

**08:52 — workers test plan changed (your instruction):** open1 with 1, 2 and **4** workers (4 regardless of how 2
does; no 3), same settings. Reported per run: wall time, Strata busy share, generated tokens per wall second,
subagents finished, pages read, chat-cache parked/restored/dropped and re-read prompt tokens, report quality and
citation-check counts. Before the test, with one worker, Strata was idle 0.8 % of smoke 1 (deep settings, xhigh
extraction) and 8.8 % of yesterday's t1 — the most a second worker could win back by filling idle time alone.

**10:19 — smoke 2 finished** (`results/smoke2-deep/`; 15-min research budget, extraction at medium; shared Strata
with the extraction test all along, so its times are inflated): completed, 115 LLM calls, 0 errors except one
length finish, largest prompt 36K / context 47K tokens (the context guard never had to act), report 8 sections,
**70 sources cited, 260 claims checked** (132 supported, 104 partly, 9 not, 15 no answer). The report reads well
(specific, weighs the voltage account against manufacturing defects, cites the 1861 Joint Committee report).
* **Scheduling bug found:** with 1 worker the subagents of a batch ran one after another, each with its full budget;
  only 2 of 6 subtopics ran before the research budget ended and the lead made only 2 model calls. Fixed: each
  subagent's budget is 75 % of the remaining research time divided by the batch's waves still to run (capped by the
  per-subagent budget), so a batch shares the time and the lead keeps a quarter to follow up.
* **The citation check dominated:** 75 calls, 300K generated tokens, 80 min (two thirds of all generation). And the
  per-source design inflated "partial": 81/122 (66 %) of multi-source sentences vs 23/138 (17 %) single-source —
  a sentence citing two sources that each state half of it was "partial" twice. Redesigned (now the default): each
  claim is checked against all its cited sources together (the most relevant 2K tokens of each), 8 claims per call:
  260 claims → 33 calls with ~9K-token prompts (offline run with a fake model). The old design is kept as
  `verify_per_source` for comparisons. Its xhigh-vs-medium agreement is being measured on smoke 2's claims
  (`tools/verify-effort-compare.py`).
* About 60 of the 70 cited sources were never read (search snippets the subagents cited); the check verifies those
  against their snippets, and the results table reports cited sources and how many of them were read.

**10:05 — extraction-effort test, objective scores on all 108 outputs** (the judge is running): NOT RELEVANT 3/3/3
with no disagreements; sentences found word for word in the page (reference markers and markdown ignored):
**low 88.5 %, medium 88.6 %, xhigh 95.2 %**; median generated tokens 617 / 787 / 3,018. The non-verbatim sentences
at all levels are mostly page text with extraction artifacts (PDF hyphenation, stitched neighbouring sentences); no
invented facts in the samples read.

**11:25 — decisions from the two effort tests**
* **Extraction: xhigh** (by quality, as asked). Final, 36 tasks × 3 efforts, blind listwise judge (the served
  model at xhigh with the page in view): ranked first — xhigh 22, low 7, medium 7; mean rank 1.67 / 2.08 / 2.25;
  pairwise xhigh beats low 24–12 and medium 24–12; verbatim 95.6 % vs 87.9 % / 88.4 %; NOT RELEVANT identical.
  Cost: median generated tokens 3,053 vs 642 / 799 (≈4×). The judge's reasons are about coverage of specific facts
  (e.g. the 2003 blackout report, 120K chars: xhigh kept the timed 13:31 / 14:02 / 15:05 EDT sequence, low and medium
  lost it); medium's outputs were the longest and ranked worst, so this is not a length preference. Runaway guard:
  an answer-less "length" finish is retried at medium, then low. Results: `results/extract-effort/summary.md`.
* **Citation check: xhigh, joint design** (each sentence against all its cited sources at once), plus one prompt
  rule: framing words do not make a claim partial, a missing or different fact does. Medium vs xhigh on smoke 2's
  260 claims (per-source design): 80 % same verdict, 88 % same flag/no-flag. In a hand-checked sample of the
  disagreements, medium twice called a claim "unsupported" while the snippet stated it word for word (the worst
  kind of error for a checker); xhigh's errors were over-strict "partial" on framing words, half of them per-source
  artefacts the joint design removes.
* **11:27 — the measurement queue started** (`tools/queue-measure.sh workers1 workers2 workers4 baseline`,
  log `logs/queue-measure.log`): open1 with 1, 2, 4 workers (research budget 3,600 s each, the tuned settings),
  then the baseline benchmark (8 questions). The tuned phase follows once the worker count is chosen.
* 12:32 w1 (1 worker): the lead made only 1 model call before its wrap-up: its first step sent one batch of 8
  subtopics, which took the whole hour. The fair share keeps 25 % of the remaining time at each subagent start, but
  every subagent overran its share by 1.5–5 min (an xhigh extraction in flight at the deadline + the wrap-up answer),
  which ate the lead's reserve. Not changed during the worker comparison (identical code for all three runs); to
  adjust before the tuned phase: budget the expected overrun into each share.
* 13:17 w1's report: 8 sections, then a joint citation check of **51 batches ≈ 400 claims** (~1.5 h at xhigh). Too
  long for the overnight plan, and the task asks for key claims: from w2 on, at most 120 claims are checked per
  report (`LDR_DEEP_VERIFY_MAX_CLAIMS`, 0 = all): all of Answer + Key findings, then sentences with figures, dates,
  quotations or several names, then the rest; the check section says how many of all cited sentences were checked.
  w1 keeps its full check (a measured cost of a complete check). This changes only the report stage, so the worker
  comparison (the research hour) stays fair. Research code is left alone until w4's research has started.

**15:00 — PAUSED at your request** (you have Strata optimizations to run first; to be resumed later)
* Stopped: the measurement queue (before w4), the w2 research (terminated during its report stage), LDR, strata-proxy,
  LDR's SearXNG instances (8889, 8890) and a leftover engine-survey instance on 8896 (my earlier kill of it had matched
  its own command line and never ran). Not touched: Strata C\*7 on 8080 (idle), strata-compare's SearXNG on 8888, the
  48-hour uptime monitor. No test processes of mine are running.
* **Worker test, research hour only (1 run each, `results/workers-compare.md`):** w2 vs w1 — generated 104.6 vs 101.5
  tok/s (+3 %), Strata busy 99.9 % vs 96.6 %, pages with findings 30 vs 23, searches 41 vs 35, but subagents finished
  6 vs 8, findings text 87K vs 132K chars, agent prompt tokens re-read 224K vs 160K (more chat-cache evictions with two
  conversations interleaved). Answer quality not compared: w1 was terminated during its full citation check (~400
  claims, would have run to ~16:10) and w2 during its report writing; files were only written after the check, which
  is now fixed (`report-unverified.md` is written before the check, and a failed check keeps the report). w4 not run.
* **Measured costs (research-hour runs, 60-min budget):** a run processes ~2.2–2.5M tokens; generation ~101–105 tok/s
  (Strata saturated); two thirds of it is xhigh page extraction. Report stage: ~4 min per section at xhigh; the joint
  citation check ~3.5 min per 8 claims (a full check of a long report ~3 h; benchmark cap 40 claims, default 120).
  Decode speed is flat from 1K to 93K-token prompts (~100–120 tok/s); prompt reading ~3,000–3,500 new tok/s.
* **Memory:** Strata's RSS swings 53–59 GB while report stages park large conversations (chat cache: 6 slots, up to
  1.9 GB each); MemAvailable lowest today 24.7 GB. Proposal (not applied): `--chat-cache-mib 12288`, or a per-request
  "don't park" flag, since LDR's one-shot report calls are never reused.
* **Not done:** w4, the baseline and tuned benchmark (questions ready in `results/bench/questions.jsonl`), grading.
  Pending before the tuned phase: budget the subagents' wrap-up overrun into the fair share (the lead got only 1
  model call in both 60-min runs). To resume: README "Resume the measurements".

## 2026-10-17 — deep research round (the user's plan: phases 1-5; LDR/SearXNG 8889/8890 rule lifted for this folder)

**20:00 — state found:** LDR 1.10.7 + the 3 deep patches (`apply.sh status`: patched), venv intact; LDR, strata-proxy,
SearXNG 8889/8890 stopped since 09-30. SearXNG venv on CPython 3.12.13 present. Strata on 8080 is now **C\*18t**
(model id unchanged, `--max-context 131072`, chat cache 16 slots / 12 GiB). Two things changed under LDR since 09-30:
* Strata's default effort is now **medium** (user's call 10-17 13:24). LDR's agent and extraction calls send none, so
  they would have run at medium. Restored the deep settings LDR-side: `run/proxy-mode.json` = agent + extract xhigh
  (the proxy adds them); `tools/ldr-client.py` now writes that mode for deep runs (`DEEP_EFFORTS`, `--effort-agent`).
* The user's sampling rule (T 1.0 / 0.95 / 20 / 0.05 everywhere): LDR sent T 0.6. `run-ldr.sh` now sends 1.0
  (`LDR_TEMPERATURE` overrides); top-p/top-k/min-p come from Strata's config. Checked in LDR's environment.
**LDR releases:** PyPI and GitHub: 1.10.7 (08-28) is still the latest. Advisories published since the install
(09-12/13): GHSA-q48m (low, < 1.10.6), GHSA-6hgg / -qfmp / -2vpc / -p5mc (< 1.10.3), GHSA-fjvm (critical, < 1.10.4) -
all fixed in 1.10.7. main is 724 commits ahead (unreleased): langgraph #6930 "prevent premature cooldown and subagent
cutoffs" (10-17), #6759 one shared content cache across subagents, #6379 per-topic fetch budget cap, #6711 full
synthesized content for detailed outline planning, #4754 keep the agent's final_answer when citation handling returns
empty; security on main: #7145 consistent egress checks across provider paths, #7106 fail closed on fake-IP DNS,
#6883 realpath containment in validate_safe_path (GHSA-gv87-qcw7-gjr8, not published yet), #7016 response cap
before buffering, #6990 credentials stripped from citation links. No upgrade (needs the user's OK).
**20:05 smoke3-c18t** (15-min budget, verify cap 40, same question as smoke 2): running; see below.
**Phase 2 build (while it runs):**
* `tools/strata-proxy.py` research gate (holds calls between model calls: control-file pause / night / abort, test
  lock, yield to other clients seen in /metrics, Strata down -> strata-ensure.sh; keep-alive SSE comments while held;
  research clock in run/research-clock.json; `/_research/status`, `/_research/wait-idle`; "tooltag" log field).
  Offline tests `tests/gate/test_gate.py` 15/15 PASS (fake Strata); LangChain streaming client survives a 35 s hold
  with a 15 s read timeout, abort -> APIError in 4 s. Note: research measurement runs must NOT take strata-compare's
  gpu-test.lock (the gate would hold them).
* `tools/research_common.py`, `tools/research-runner.py` (+ `systemd/deep-research-runner.service`),
  `tools/research-mcp.py` (stdio MCP, stdlib; protocol + tools tested with a scripted session), `research.conf`.
* deep patch, new modules: `deep/control.py` (research clock, per-job settings), `deep/files.py` (read_file tool:
  pieces of 120K chars, same extraction step, file://...#part=N sources), `deep/seed.py` (continue from earlier runs'
  evidence: collector seeded with the old [N], store + page cache filled, lead told what was done). Offline: REPORT.md
  = 551K chars -> 5 parts; smoke2's evidence -> 443 sources seeded, indices kept. Wiring into middleware/strategy:
  `tmp/apply-jobs-patch.py`, applied after the smoke test (LDR imports these lazily).
* strata-compare: `bringup/lib/research_wait.sh` (after taking a test lock: wait for the research's call in progress),
  called by `with_server.sh`.
* Jan attachments: Jan 0.8.6 sends attachments to its own RAG extension (embedding model - never downloaded here;
  `data/db` empty) and shows the model only `file_id, name, type, size`; MCP tools get only what the model writes.
  So research_start takes paths. Live check with a Project attachment still to do.
**20:55 smoke3-c18t done** (results/smoke3-c18t/): completed, 2,934 s wall (15-min research budget; report 1,953 s
incl. a 40-claim check), 54 calls, **0 errors**, every finish "stop", generated 364K tokens = 124 tok/s of wall time
(decode 137 tok/s), Strata busy 98.4 %; 9 sections, 106 sources cited (8 of them read), 40 of 308 cited sentences
checked: 32 supported, 8 partial, 0 unsupported. Effort: agent / extract xhigh (proxy), report / verify xhigh.
**MemAvailable lowest 20.0 GB** (client sample; my 10 s sampler 20.26): Strata's chat cache (C\*18t: 16 slots,
12 GiB) parks every report-section call (~1.2 GiB each) until the budget is full -> Strata RSS 63.4 GB. No Strata API
empties it (only /slots save|restore) -> the runner restarts Strata (same config) between model calls when
MemAvailable < 21 GB and no other client used it in the yield window ("memory relief"), and before a job starts when
< 22 GB. Proposal (Strata, not applied): a per-request "don't park" flag for one-shot calls, or chat-cache-mib 8192.
**21:00-21:10 live tests (runner + gate + MCP, Strata C\*18t):**
* import bug in my wiring (`..deep` instead of `...deep` in two helpers) failed the first job at once; fixed, LDR
  restarted, job requeued.
* job A (5-min budget, notes file): read_file used by the lead (file = source [1]); MCP pause -> next call held, Strata
  idle, research clock stood still (status: 0 of 5 min used while paused 77 s); resume -> continues.
* false "another client": phase_end.sh's warm-up + test requests come after strata-ensure returns -> counted as
  foreign. Fixed: 90 s grace window after any Strata start (re-based each poll; PROXY_GRACE_S) + "rebase_at" from
  the runner after its own restarts. Offline tests 15/15 still pass.
* first restart_strata: ensure said "busy" because the old server was still exiting -> the runner now waits for it.
* interruption: `run-ldr.sh stop` at 195 s of research -> runner noticed in 1 s, requeued, seeded run started 6 s
  later with 99 s left: 398 sources (4 read) + 5 subagent reports seeded, file still attached.
* yield: a direct request to 8080 -> gate "yielding to another client"; the research call in flight was not cut.
  Detection of a request that overlaps a research call comes when that call ends (here +34 s): the yield runs that
  much longer than set.
* test lock taken in a shell -> gate "a test holds the GPUs"; research_wait.sh returned at once (nothing in flight).
* Jan: `deep-research` added to ~/.local/share/Jan/data/mcp_config.json (backup in strata-compare
  work/r21/usability3-backup/), Jan closed and reopened: it starts the server (pid seen), config kept.
**21:22 test job A finished** (5-min budget, interrupted once, 2 runs): reports/2026-10-17-REPORT +
.html, 24 min wall (pauses not counted), MemAvailable lowest 26.4 GB. Correct and careful: Whitehouse; "up to about
2,000 volts" (600 V first, larger claims flagged); the 16-hour note "defensible as a rounded figure" with the timed
record 17 h 40 min; the notes file cited as [1] and checked by the citation check like a page. Notifications reach the
desktop from the service (DBUS/DISPLAY in its environment). Test settings restored (yield 5, verify 120).
**21:25-21:40 — phase 3 tooling (no runs yet):** strata-proxy capture mode ("capture_dir" in the mode file: every
call's messages + answer -> calls.jsonl; offline test 16/16); `tools/ldr-client.py` --budget-s / --files (deep:
next-research.json) / --capture-dir / --effort-report|verify; `tools/bench2.py` run (one question at a time, capture
on, daytime guard: a question starts only if it should end before 23:00; holds run/bench.lock - the runner then starts
no Jan job and does not stop LDR) / grade (Answer section vs stored answer + variants, numbers with tolerance) / sort
(never found / found but not read / read but dropped / in the notes but wrong); unit-tested on synthetic runs.
`results/bench2/PLAN.md` = the draft protocol. The test set itself waits for the user's OK (it costs a lot of Claude
usage: ~150 searches + 60-100 page reads for 30 verified checkable questions).
**21:40-22:20 — phase 3 test set built and frozen (user's OK for the Claude usage):** `results/bench2/`
* 30 checkable questions about July-October 2026 events (sport, Nobel/Fields, film/TV/books, elections, software,
  space, AI business/models, weather), each answer confirmed on two fetched pages (`tools/verify.py`, page texts kept
  in `sources/`, quotes in `answers/answers.jsonl`): screen c01 c02 c05 c07 c09 c11 c14 c16 c17 c20 c22 c24 c25 c27 c29,
  holdout the other 15. Six open-ended: screen o01 MoE experts from RAM (files: frozen copies of strata-compare
  REPORT.md + NOTES.md in `files/`), o02 16 GB third GPU, o03 EU AI Act 2026 changes (my general topic); holdout o04
  projects like Strata, o05 Qwen4 Flash, o06 a UPS for the workstation (my product search). Dropped while building:
  NextEra-Dominion (announced May 2026), Brazil vote shares (snapshots disagree), Commonwealth Games totals
  (sources disagree), a Python date question (PEP 790 was edited to the new date). Bare-number answers became phrases
  ("99 seats") and the grader drops [N] markers before matching (a citation [10] is not "10 goals").
* `FROZEN.txt` = sha256 of the question files, answers and the two Strata files (frozen 22:17); files read-only.
* Baseline LDR cannot take files: o01 runs there without them (that is the baseline's capability).
**22:20 — `tools/bench2-queue.sh` started (pid in logs/bench2-queue.log):** waits for 09:00; screen set on baseline,
then on deep; new work only 09:00-22:00 and a question must be expected to end by 22:30; stops between questions if
the Strata tag watch sees a release newer than v0.1.45, or if tmp/bench2.stop exists. Strata up on demand and its
chat cache emptied (restart, same config) before LDR starts when MemAvailable < 22 GB; during runs the research runner
does the same at < 21 GB (bench lock). First attempt started at 22:18 (my "day" check let 22:xx through) and was
stopped before any question ran.
**22:20-22:25 — baseline profile fixed and dry-run:**
* its SearXNG (8890, Brave + google cse) returns **0 results** from this address (both suspended) -> run-ldr.sh's
  baseline profile now searches the main instance (8889) with LDR's own default search settings
  (`LDR_BASELINE_SEARXNG=baseline` brings 8890 back); ldr-client's health check follows LDR's instance URL.
* run-ldr.sh could never start the baseline profile: with no LDR_DEEP_* variables the log-header `grep` failed and
  `set -e -o pipefail` ended the start silently. Fixed (`|| true`).
* dry run (2 min, a Wimbledon question): pristine code (PYTHONPATH baseline/site, no deep lines), T 1.0, search 8889,
  capture works, answer correct. Pristine LDR sends no reasoning effort -> Strata's default (medium since 10-17); the
  deep profile runs agent/extract/report/verify at xhigh. The per-step level tests separate that effect.
* the queue was stopped while its script was edited and restarted (22:19, waits for 09:00).
**22:30-22:55 — my own work for phase 3 (no runs):**
* My reference research for the three open-ended screen questions, written before any run exists:
  `results/bench2/my-research/o01-moe-from-ram.md`, `o02-third-gpu.md`, `o03-eu-ai-act.md` (facts with sources and a
  grading checklist each). Key points: o01 - llama.cpp's 2026 expert cache, KTransformers v0.6 (AMX: not on a Ryzen),
  learned expert-prefetch papers (SPICE 2608.21240, SpecPrefetch 2607.24787, DraftExpert 2607.24434, SeqMoE
  2609.12978, MoE-CORE 2610.01950) as the predictor Strata never built after its Round 7 oracle, mixed-precision
  fallbacks (HOBBIT, DynaExq, DyMoE - lossy); o02 - Strata needs NVIDIA/CUDA, the 4060 Ti is on a Gen4 x4 chipset slot
  (6.4 GB/s), US prices mid-Oct 2026 inflated (5060 Ti 16 GB ~$430-500, 5070 Ti ~$1,190-1,250, RX 9070 XT ~$790-900);
  o03 - Regulation (EU) 2026/1744 (OJ 24 Jul, in force 27 Jul 2026): Annex III high-risk -> 2 Dec 2027, Annex I -> 2 Aug
  2028, Art. 50 unchanged (2 Aug 2026; marking grace to 2 Dec 2026), GPAI duties unchanged but AI Office enforcement and
  fines from 2 Aug 2026, new NCII/CSAM prohibition.
* **Blind re-judging of the 36 old extraction tasks** (`results/bench2/rejudge-extract/`: packets with A/B/C in a new
  random order, the key opened only after all 36 rankings were written; I compared what each output has that the
  others lack, on-focus vs off-focus, and lines not found verbatim in the page): 3 ties (all NOT RELEVANT), 33 ranked.
  First place low 11 / medium 8 / xhigh 14; mean rank 1.97 / 2.03 / 2.00; pairwise xhigh-low 17-16, xhigh-medium 16-17,
  low-medium 18-15. **No meaningful difference** - unlike the 09-30 model judge (xhigh first 22/36); same first place as
  that judge in 19/33. The old verbatim rates (xhigh 95.6 % vs 88 %) stand; most of the non-verbatim lines I saw were
  reformatted page text, not invented facts. Extraction is ~2/3 of all generation and xhigh costs ~4x the tokens, so
  this is a candidate saving; the replay on the screen runs' pages (phase 3) decides.
**State at 22:55 (PC goes off for the night later):** `deep-research-bench.service` (enabled) waits for 09:00 and then
runs the screen set on baseline, then deep (logs/bench2-queue.log); `deep-research-runner.service` enabled (Jan jobs;
none queued); LDR stopped; Strata stops itself when idle. Nothing runs at night.
**22:45-22:56 — more prep (no runs):** `tools/level-replay.py` (extract: N captured extraction calls re-sent at
low/medium/xhigh + blinded packets; report: a finished deep run's evidence rebuilt into a store and the report written
at medium/xhigh; verify: the citation check on the run's own unverified report at each level, same claims) - loader
tested on smoke3 (679 sources, 308 claims, the same 40 selected); runs are daytime-only and hold run/bench.lock.
`bench2-queue.sh` now checks Strata's tags itself (ls-remote at most hourly, cached in run/strata-newest-tag, logged to
strata-compare's tagwatch.log) - the session's tag watch does not survive the PC being off. Service restarted 22:55.
**23:47 — first real Jan call:** the user sent a short prompt in Jan; Jan's model called research_start (logged in
logs/research-mcp.log) with its own, much longer rewording of the question and time_budget_minutes 30; job
20261017-234706-what-changed-in-the-eu-ai-act-in-2026... queued, "waiting: night pause until 09:00". Found a 09:00
conflict (runner and bench queue both wanting LDR; the queue would restart LDR in the baseline profile under a job).
Fixed: bench2-queue.sh waits while a Jan job is queued or active (user_jobs); the runner restarts LDR in the deep
profile when it finds it in baseline and no measurement holds the bench lock. Both services restarted 23:5x.
**00:03 (10-18) — the user allowed research jobs at any time** ("Can you allow it to run at anytime? I just wanna test it out."): research.conf night_pause = off (the bench queue stays daytime-only). The EU AI Act test job started 00:03:33 (research 0b5a01cb..., 30-min budget).
**00:53-01:00 (10-18) — test job, live:** research phase done (30 min: 31 searches, 24 pages read, 8 subtopics);
report stage. **Memory relief worked live**: MemAvailable 20.8 GB at 00:53 -> gate held, Strata restarted, 33.1 GB;
the job continued. Flaw: phase_end.sh's two tiny start-up checks queued behind the held report call (115 s) and
finished at 00:55:37, after the 90 s grace -> counted as another client -> a needless 5-min yield. Fixed in the proxy
(not yet running: it is holding the job's next call): finished requests under 64 prompt tokens (probes; a Jan chat is
far larger) do not count as foreign. Gate tests 16/16 PASS. Applies at the next proxy start (LDR stop/start).
The user's login to LDR's UI: 4 failed tries + the runner's login hit LDR's "5 per 15 minutes" login rate limit
(not the 10-failure account lockout); clears by itself.
**~02:00 (10-18) — fact check of the Jan test report at the user's request:** results/factcheck-eu/FACTCHECK.md - ~25 claims checked against the regulation's EUR-Lex text and Parliament's Legislative Train page plus secondary sources: all confirmed; one nuance (Art. 112 review); reactions/standards not checked. o03 grading no longer blind for me (noted).
**07:50-08:05 (10-18) — PC back on (boot 07:48); holdout own research written.** The previous boot's kernel log has no
errors (only boot-time X.509 and a Bluetooth vendor event); the kernel-log watcher and the hourly tag check were
restarted (newest Strata tag still v0.1.45). The user's 210-min Jan job (started 02:18) was cut by the PC going off at
02:51 and the runner continued it as a seeded run at 07:49 (176 min left) - the first real PC-off continuation. The
bench queue waits for it. Proxy restarted 07:49, so the probe filter (under 64 prompt tokens) is live now.
My own research for the holdout open questions, done before any holdout run (results/bench2/my-research/, sha256):
o04-moe-projects.md de601c28..., o05-qwen4-flash.md 297299d5..., o06-ups.md 2112d416...; fetched pages in
my-research/sources/. Key points: o04 - Strata, llama.cpp (+2026 expert cache), ik_llama.cpp, KTransformers (v0.7.2),
FreeToken, Edge0 (SSD + trained prerouter, lossy), SGLang SSD pack; flash-moe stale since 03-19, Fiddler dead. o05 -
no Qwen4 / Qwen4 Flash release as of 10-18 (HF org checked); Apsara 09-22 said "in training"; tier names are an X post;
Qwen3.8-Flash-Next (125B/6B + 51B n-gram + 4B MTP, 262K/1M, Qwen Community License 1.0) is the official preview.
o06 - 900 W peak needs ~1100 W+; CyberPower PR1500LCD (1500 W, ~$701) best fit, CP1500PFCLCD ($239.95) tight at 1000 W,
Eaton 5SC1500 (~$520-580), APC SMT1500C (~$700, fan always on).
**12:00-12:10 (10-18) — phase 3 started; LDR login limit hit.** The user's Jan job finished 12:00:25 (memory relief
once at 11:04, min 20.5 GB; kcheck ok). The queue started the baseline screen set at 12:02. Pristine LDR (quick mode,
langgraph agent, defaults) makes only 3-4 model calls per question (~25 s). After 5 runs, LDR's login rate limit
(5 per 15 min) refused ldr-client's login (HTTP 429), and the other 13 runs failed at once. The queue counted them as
done because every run wrote bench.json. Fixes:
- ldr-client reuses its session (run/ldr-session.json, mode 600; checked with GET /settings/api);
- on 429 it waits 60 s and retries, for up to 20 min;
- bench2 writes bench.json only for a completed run (else bench-fail.json);
- the 13 failed runs were requeued.
Backups in tmp/backup-2026-10-17/*.before-*. The queue was stopped while it slept and restarted at 12:07.
Also new: research-status prints a "Stage:" line, LDR's last milestone, since "researching" covered the report and
citation check too. New tools/blind-open.py relabels open-ended reports A/B and strips setup cues, with a separate key
for blind grading.

**13:53-14:00 (10-18) — baseline screen set done; deep runs open-ended first.** The 13 requeued runs went through on
one saved login (c11 waited out the 429 window: 11 min wall; the others ~1 min, 3-5 model calls each; open-ended
o01/o02/o03 took 42/30/17 min). `bench2.py grade screen baseline`: **15 of 15 checkable correct**. Baseline reports
have no "## Answer" heading the grader's regex takes ("## Answer: X" or none), so it matched the first 4,000 chars;
I read the opening of all 15 by hand: each states the right answer outright, no near-misses. The checkable set
(single news facts from Jul-Oct 2026, answer on two pages) is therefore at the ceiling for pristine LDR: the deep
profile can only tie or lose on it, and the holdout's 15 checkable questions are built the same way. Not read: the
baseline's open-ended reports (kept unseen for blind grading). The queue's done check (`all_done`) was false right
after o03 for a reason I could not reproduce (true when run by hand a minute later), so it slept 10 min before deep.
Change, with the deep phase not yet started (backup tmp/backup-2026-10-17/bench2.py.before-open-first): bench2.py
runs open-ended questions first, and a question that would end after 22:30 is skipped (not the end of the day's
run), so a shorter one can still fill the evening.

**14:05-14:47 (10-18) — queue fixed, deep runs started, hard checkable set built and frozen (the user's rules).**
- Queue bug: `all_done` was never true. `local set=$1 prof=$2 n=$(... questions-$set ...)` expands every word before
  assigning, so `$set` was empty. The queue re-ran the finished baseline every 10 min and would never have reached deep.
  Stopped while sleeping (orphan `sleep` killed by PID). Replaced by a one-question-at-a-time queue (backup
  tmp/backup-2026-10-17/bench2-queue.sh.before-hard-set): `bench2.py next` picks the first question in
  results/bench2/queue-plan.json that is not done and fits before 22:30. Plan order:
  1. hard-screen / baseline (waits for FROZEN-hard.txt);
  2. screen / deep o01-o03;
  3. hard-screen / deep;
  4. screen / deep, 5 easy questions picked with SystemRandom before any deep run: c02 c22 c24 c27 c29 (the user:
     "run only 5 of them").
  bench2.py: sets hard-screen / hard-holdout, answers-hard.jsonl loaded with answers.jsonl, `next`
  (backup bench2.py.before-hard-set). Deep o01 started 14:09.
- Hard set rules (the user's): about 20 questions, split at random 10 screen / 10 holdout, frozen before any run. Keep
  only if the answer is in none of the top-10 snippets of one plain web search for the question (never selected on
  LDR results). Types: multi-hop, numbers inside pages/PDFs/tables, obscure but stable; newer than mid-2026 or
  obscure; two confirming pages; answers apart from the questions.
- Filter: results/bench2/tools/snippet-check.py. The question text is the query, SearXNG 127.0.0.1:8889 (the instance
  both profiles search), top 10 titles + snippets, matched with bench2's grader. 82 drafts checked, 24 passed. Two
  number hits were coincidences and were kept by hand: d02 "27" was the date "Jul 27, 2026"; d62 "13th" sat inside
  "113th edition".
- What passed and what failed. Headline numbers from release notes, model cards and news fail almost always, because
  aggregators copy them: Kubernetes counts, vLLM/SGLang contributor counts, Hy4/DeepSeek specs, Booker submissions,
  Venice juries, Node.js credits. What passed: deep statistics tables (LWN), contributor credits, paper table details,
  datasheet table rows, questions that need one reasoning step over a results table, and 2-step history.
- Confirmation: results/bench2/tools/find-sources.py + add-candidate.py fetch both pages (PDFs via pypdf) and store
  the quote and the page text (sources-hard/). Dropped at this stage:
  - d25 (csv speed-up credit): the full name is on one page only; GitHub shows a username;
  - hockey d72/d77 and basketball d73: only Wikipedia had them, and the other pages refuse automated fetches.
  Accept lists tightened against substring hits: no bare "Seo", "Vargas" or "13". "Vainio" alone is not accepted,
  because Alisa Vainio won the 2026 women's marathon in a championship record.
- Frozen 14:46 (FROZEN-hard.txt, read-only): questions-hard-screen.jsonl (h01-h10), questions-hard-holdout.jsonl
  (h11-h20), answers/answers-hard.jsonl (with draft ids, types, sources, notes).
  - Mix: LWN 7.2 statistics 4 (3 in holdout), Kimi K3 paper 2, Python 3.15 credit 1, Sandisk datasheets 2, Swedish
    election 2, and sport tables/history 9.
  - Grading: the grader's number and substring matching is loose (a date "27", a country named in passing), so every
    hard-set grade is checked by hand against the answer statement.
- Phase 4 list (the user's): an early stop once the answer is confirmed in two sources. Deep spends its whole budget
  on questions the baseline answers in a minute.

**15:20 (10-18) — research vs chat waits (the user's item 2; no new runs).**
- Source: strata-proxy's call log (logs/llm-calls.jsonl, duration and class per call). Only my deep-profile runs at
  the current levels were used: 10-17 20:00-23:40 (test job A) and 10-18 14:09 onward (bench o01). The two Jan jobs
  that may be the user's were left out (timing only would be enough, but I did not use them).
- Duration p50 / p90 / max (n):
  - agent step, xhigh: 4.9 / 9.3 / 240 s (66);
  - extraction, xhigh: 87 / 202 / 296 s (69);
  - report section, xhigh: 88 / 140 / 165 s (20);
  - citation check, xhigh: 111 / 157 / 186 s (9);
  - other LDR calls, medium: 34 / 75 / 85 s (13).
- A chat message arriving at a random moment of research waits for the rest of the call in flight: p50 55 s,
  p90 152 s, over 60 s 47% of the time. Extraction calls take most of the research time.
- After the first message, the gate's yield window holds new research calls, so follow-up messages do not wait.
- So waits over a minute are common. Proposed smallest fix (not built; needs the user's OK): preempt and replay in
  strata-proxy. When a foreign request queues at Strata, the proxy cancels the research call in flight; it was
  buffered, so nothing reached LDR yet. The proxy re-sends that call when the gate reopens. Cost: the cancelled
  call's work (about half a call). Every call streams today, so the proxy would have to buffer research responses.
- Redo the numbers after o01-o03 (more report and citation-check calls) and after the Phase 3 thinking-level
  decision.

**15:05-15:23 (10-18) — medium pass added (the user's request).** The plan had no medium deep runs: every deep run
used the deep profile, all xhigh except compaction. Now (results/bench2/queue-plan.json), in order:
1. hard-screen / baseline (10);
2. deep at medium: o01-o03, then the 10 hard screen questions (runs folders `*-deep-medium`);
3. xhigh as the confirming subset: o01-o03 (o01 was already running at xhigh since 14:09) plus 5 hard screen
   questions picked with SystemRandom before any hard deep run: h02 h04 h05 h06 h08;
4. the 5 easy questions (c02 c22 c24 c27 c29) at medium.
How "medium" is set: agent and extraction through the proxy mode (ldr-client), report and citation check through
LDR's environment at start (LDR_DEEP_REPORT_EFFORT / LDR_DEEP_VERIFY_EFFORT: the deep package reads them once, at
import). Compaction stays medium and "other" calls stay at Strata's default, medium.
- run-ldr.sh writes run/ldr.efforts.
- `bench2.py run --effort-all medium` refuses to run unless LDR was started at that level; an xhigh deep run needs
  "default".
- `next` prints effort + label.
- The queue restarts LDR when the profile or the efforts change, and waits while run/bench.lock is held.
- Backups *.before-efforts / *.before-medium.
Queue swapped at 15:22 (stop: KillMode=process left the o01 bench2 run going; the new queue waits for its lock).
Dry run of `next` on a scratch copy picked the expected order.
**15:30 (10-18) — the user's decisions:**
- The xhigh subset is 5 of the hard screen questions (h02 h04 h05 h06 h08), as queued, so both levels are compared on
  the same questions.
- Pre-empt-and-replay is on hold. Redo the wait table after the Phase 3 thinking-level decision. Propose building
  the fix only if a first chat message still often waits over a minute.

**17:19 (10-18) — o01 deep (xhigh) done:** rc 0, 190 min wall (7 min held; budget 120 min + report 66 min), 184 LLM calls,
lowest MemAvailable 20.8 GB (floor 20 held), kcheck clean (kernel errors 2 -> 2). Queue went on to the hard-screen
baseline (LDR baseline profile, proxy pass-through, run/ldr.efforts "report=default verify=default").
**17:25 — citation metric fixed (summary only, not grading):** ldr-client.py `check_citations` missed LDR's two-line
source entries ("[n] title" + "   URL: ...") and inline-linked citations ("[[6]](url)"), so every run showed all cited
numbers as "not listed". Fixed (backup tmp/backup-2026-10-17/ldr-client.py.before-citefix); runs from h02 on get the
right number; earlier runs recounted in results/bench2/citations-recount.json (baseline checkable 0 missing; baseline o03
78 and deep o01 9 still missing - deep's [1]/[2] are the attached files, which have no URL; not read further before
blind grading).

**18:30 (10-18) — hard-screen baseline: 10/10 correct**, 1-2 min each (17:19-17:32), every answer hand-checked against
the frozen answers (h01 27 layers; h02 Kazakhstan 48 bronze; h03 Chinese Taipei 55; h04 Örebro Party 39,644 votes;
h05 SiTU-GLU; h06 Martti Vainio 27:30.99; h07 Belgium; h08 Bryam Vargas 43 commits; h09 1.75M h from the datasheet PDF;
h10 2869 Abdusattorov). The snippet filter (one search, top-10 snippets) was weaker than LDR's pipeline: LDR runs several
queries and reads full pages (summary_focus fetch), tables and PDFs included. So the hard set is at the ceiling for
plain LDR too, and the checkable deep runs can only show time and regressions, not accuracy gains. Reported to the user
with a proposal (cut the hard medium step to the 5 xhigh-subset questions); the queue stays as approved until they answer.
Medium o01 start lines checked: run/ldr.efforts "report=medium verify=medium", LDR header LDR_DEEP_*_EFFORT=medium, proxy
agent/extract medium (127 calls so far, all medium), LDR_LLM_TEMPERATURE=1.0, Strata defaults 0.95/20/0.05.

**18:43-18:55 (10-18) — the user's decisions after the 10/10 baseline** (PLAN.md revision 18:43): queue-plan.json now
(backup tmp/backup-2026-10-17/queue-plan.json.before-cut): medium o01-o03 -> screen-extra baseline -> screen-extra
deep medium -> hard medium h02 h04 h05 h06 h08 -> xhigh o01-o03 (o01 done) -> screen-extra xhigh -> hard xhigh (same 5).
Easy 5 dropped. bench2.py SETS += "screen-extra". o07/o08 frozen 18:49 (FROZEN-extra.txt, sha256 8854cc32...).
**Quick mode for Jan:** research-mcp.py `research_quick(question)` (job mode "quick"; waits `quick_wait_seconds` = 25
for the answer - Jan's MCP toolCallTimeoutSeconds is 30 - else returns the job id); research-runner.py runs it as
plain LDR's quick summary (LDR restarted in the baseline profile, proxy pass-through = Strata's default effort), ahead
of queued deep jobs, no yield to chats, 15-min cap, LDR's own report from /api/report -> reports/ .md + .html. The
next deep job switches LDR back (generalised profile check). Backups *.before-quick in tmp/backup-2026-10-17/. Runner
restarted 18:48 (no jobs active). End-to-end test pending: needs LDR free of measurement runs (after tonight's last).

**20:14 (10-18) — medium o01 done; then a kernel-log error stopped things.** Medium o01: rc 0, 162 min wall (18 min
held), 434 calls, report 26 min (xhigh: 66), lowest MemAvailable 20.0 GB (the client's floor check is unrounded and did
not fire, so 20.00-20.05; ~19:48, report stage, while a relief restart waited for a gap) - runner MEM_RELIEF_GB 21 -> 22.
At 20:14:31, 16 s into the o07 baseline run (LDR just restarted in the baseline profile, two pages being fetched in
parallel), the kernel logged `traps: ldr-web[607718] general protection fault ... in libc.so.6[ab0a5,...]`: a user-space
crash inside glibc's malloc code (nearest symbol __default_morecore+0x5b5, i.e. heap corruption), LDR gone. No Oops /
MCE / EDAC / bad page; the only other user-space crash in the kernel log since 10-01 is membw on 10-10 (the RAM day).
kwatch did its job: logged it, put STOP at the head of strata-compare's queue.txt, killed Strata (pid 599259), exited.
I: killed the stuck o07 client (it polls a dead LDR until its 135-min cutoff; it now gives up after ~5 min of LDR
unreachable), moved the partial run to results/bench2/runs-failed/, created tmp/bench2.stop (the queue exits at its next
check, ~20:27), restarted kwatch (20:18). Waiting for the user's call (stop-at-first-error rule).

**20:25-21:20 (10-18) — the crash explained; LDR on 3.12.13; one page at a time** (the user's go 20:2x: resume at 09:00,
no memtest; move LDR to 3.12.13 if < 1 h; then, both Pythons crashing: test one fetch at a time, and if clean make LDR
fetch one page at a time).
* LDR's venv was Ubuntu's 3.12.3. Reproducer (scratchpad threads.py: LDR's ContentFetcher, 4 real pages, 2 threads):
  parallel 2/20 crashed on 3.12.3, 1/20 on a 3.12.13 venv with the identical package set -> not gh-119585. Every crash:
  "double free or corruption (out|!prev)", faulthandler: thread A in lxml.html.document_fromstring (trafilatura
  load_html), thread B in copy.copy of a tree (trafilatura_sequence) - two pages' trafilatura at once. One at a time:
  0/20 on each. lxml 6.1.3 / libxml2 2.14.6, trafilatura 2.2.0. LDR's own pipeline.py already runs its extractors
  one after another because lxml "is not safe to share across threads"; it did not across pages.
* Native threads in the fetch path (none call into Python): numpy + scipy OpenBLAS pools (~31 each), sklearn's
  libgomp, pyarrow's jemalloc background thread - pulled in by newspaper / nltk / pandas.
* Patch 0004 (`patches/ldr/0004-fetch-one-page-at-a-time.patch`): an RLock around ContentFetcher.fetch; applied to the
  venv (apply.sh now lists it) and to baseline/site (pristine copy saved in tmp/backup-2026-10-17/). Parallel
  reproducer on the new venv with the lock: 0/10.
* Venv moved: `.venv` -> `.venv-py3.12.3` (kept), new `.venv` = uv venv on searxng/python's CPython 3.12.13 with the
  same 300 packages (`tmp/venv-py3123-freeze.txt`; identical `uv pip freeze`), patches 0001-0004 applied; LDR tree
  identical to the old venv's except fetcher.py (0004) and the generated themes.css; deep/, the strategy and the
  fetch tool byte-identical. ~10 min. run-ldr.sh: ldr-web with PYTHONFAULTHANDLER=1.
* **Measurement note:** runs from 10-19 on fetch one page at a time (both profiles); earlier runs (screen baseline,
  hard baseline, o01 xhigh, o01 medium) fetched in parallel. Affects time comparisons, not what is read.
* kwatch killed the engine but left Strata's server wrapper listening on 8080, so strata-ensure waited for a ready
  that never came ("Not ready after 3 minutes", twice); `run-strata.sh stop` cleared it. (Proposal for strata-compare:
  after a kwatch kill, also stop the wrapper - not done.)
* Jan quick mode end-to-end (research_quick over stdio, as Jan calls it): returned the job id at 25 s; Strata cold
  start 21 s; LDR baseline profile on 3.12.13, answer in 54 s (Halzen / IceCube, correct, 130 sources);
  research_report gives it in 3 parts. Report: reports/2026-10-18-REPORT
* kcheck: flag archived as tmp/r19/KERNEL_ERROR.2026-10-18T2014-explained-ldr-lxml, queue.txt back to its saved state
  (one STOP, as before the error), kcheck ok. Research queue re-armed 21:13 (nothing fits before 22:30; medium o02 at 09:00).
* **21:15-21:30 — library identified: lxml itself** (lxml 6.1.3, libxml2 2.14.6; .venv 3.12.13; offline, saved pages,
  Strata off; scripts in this session's scratchpad libid/). Two threads, each with its own documents:
  lxml.html.fromstring + copy.copy 5/30 processes crashed ("double free or corruption", one segfault; faulthandler:
  document_fromstring in one thread, copy.copy in the other); trafilatura.extract alone 5/30; parse only 0/30; copy
  only (trees parsed once per thread, then copied) 1/30. So copying an element tree (lxml __copy__) while another
  thread parses or copies its own document corrupts the heap. Possible upstream report (lxml) later - nothing posted
  this round. A later fix could be an lxml/libxml2 version without it (would allow parallel fetches again); 0004 stays.

**21:40-21:55 (10-18) — the watcher/launcher snag fixed (the user's request)** (strata-compare; backups
work/r19/kwatch.sh.before-wrapper, work/r19/strata-ensure.sh.before-stale):
* bringup/lib/kwatch.sh: the stop now also ends Strata's server wrappers (engines' parents + run-strata pid files,
  checked to be serve/server.py; TERM = the wrapper's clean stop, KILL after 15 s); `--simulate` runs the same stop
  once (logged "SIMULATED STOP"; it writes the flag and the queue STOP like a real one). Watcher restarted on the new
  script (old one stopped by its process group: bash reads scripts as it runs them).
* configs/usability/bin/strata-ensure.sh: 8080 taken and not ready after the wait -> unless a test lock is held,
  `run-strata.sh stop`, then one more start + wait; if 8080 is still taken, a notification names it. Our own slow start
  still just times out. research-runner.py: strata-ensure timeout 400 -> 600 s (two waits + the stop).
* Test 1: Strata up -> `kwatch.sh --simulate` -> engine and wrapper ended, 8080 free, watcher still running -> Jan from
  its icon (gtk-launch jan-strata): "starting the promoted config", ready after 12.1 s, Jan opened.
* Test 2 (the old snag): engine killed by PID, wrapper left listening ("loaded": false) -> Jan icon: waited 180 s,
  stopped the stale wrapper (33 s), started once more, ready after 14.1 s (3 min 48 s in all); one Jan window.
* Cleanup: simulated flag archived (tmp/r19/KERNEL_ERROR.2026-10-18T2147-simulated-test), queue.txt back to one STOP,
  kcheck ok, no kernel errors. Jan left open; Strata stops itself after 45 idle min.

**07:09-07:27 (10-19) — after the PC restart:** services came back (bench queue waiting for 09:00, runner, idle stop);
kwatch started by hand 07:20 (no boot service yet - offered to the user); tag watch restarted (v0.1.45 still newest);
boot kernel log clean. My own research for o07 and o08 written before any o07/o08 run:
results/bench2/my-research/o07-new-models.md, o08-deep-research-agents.md (0444; hashes in WRITTEN-o07-o08.txt).
**o01 blind grading (10-19 07:29; tools/blind-open.py, now cutting source lists to cited entries - plain LDR lists
every source it saw, ~5,000, which gave it away; grades in results/bench2/blind/grades.jsonl before the reveal):**
deep xhigh 10/10, deep medium 9.5/10, plain LDR 2.5/10 (checklist of my-research/o01).
* Both deep reports used the attached files closely (oracle ceilings, spec-split, pcie-frac, NVFP4 floor run) and put
  KTransformers expert deferral first.
* Medium found more new items (adaptive speculative expansion AcceptMoE/SpecFit/S2-MoE, FreeToken q*, Least-Stale +
  the replay-semantics warning) but made more slips (CPU called a 9800X3D, inconsistent PCIe figures, odd model name).
* xhigh was the most precise (byte arithmetic for NVFP4 + SSD, ranked list + one-day triage plan).
* Time: medium 162 min (report 26 min) vs xhigh 190 min (report 66 min).
* Plain LDR never saw the files: pristine LDR has no file input, so it can't do the "what haven't we tried" part.

**07:3x-08:01 (10-19) — night rule lifted while the user is away** ("The night rule doesn't matter here im not at home"):
run/night-ok makes bench2.py's end-by-22:30 cut and the queue's 09:00-22:00 window no-ops (backups *.before-nightok);
remove it when the user is back. Queue service restarted 07:59 (idle, no run). First start failed: the Jan runner's
idle stop (15 min since its 07:09 boot start) stopped LDR 1 s after the queue started it, in the gap before bench2 takes
the bench lock. Fixed: the idle stop spares an LDR whose run/ldr.pid is younger than the idle time (backup
research-runner.py.before-idlerace); runner restarted; queue retry sleep ended by PID. Medium o02 running since 08:00:57:
ldr.efforts medium, proxy agent/extract medium, LDR on CPython 3.12.13 with PYTHONFAULTHANDLER=1, patches 0001-0004
applied, sampling 1.0/0.95/20/0.05.

**08:20 (10-19) — the user's items:** (1) run/night-ok stays on through tonight; the user decides on 10-20 whether
nights stay on. (2) kwatch is now a systemd user service (~/.config/systemd/user/kwatch.service, enabled, Restart=no so
it stays stopped after a kernel error until that is looked at). It starts with the session, like the other user
services (Linger=no; the desktop logs in at boot). The hand-started instance was replaced; its journalctl child has the
adm group; kcheck ok. (3) Phase 4 list (PLAN.md): a fixed hardware/setup profile from the user's files for the report
writer, plus checking self-setup claims against the files (o01 medium: "9800X3D").

**08:29 (10-19) — the 4060 Ti is the 8 GB card** (nvidia-smi 8188 MiB; the user's "24 GB VRAM"). I had written 16 GB:
* o01's question (frozen, run on all three setups) says "RTX 4060 Ti 16 GB" - a known error in the test set, left as is.
  Both deep reports took the 8 GB from the attached files anyway.
* o07's question corrected to "(8 GB)" and re-frozen as v2 (FROZEN-extra.txt; v1 kept). No o07 run had completed.
* my-research/o07 v2 (fit math for 96 + 24 GB; v1 kept, hashes in WRITTEN-o07-o08.txt).
* PLAN.md Phase 4 profile fixed.
* my-research/o02 ("a second 4060 Ti 16 GB") reads as a product option; noted, unchanged.

**09:0x (10-19) — Strata v0.2.0-beta (engine 0.1.45.3) is out; the user's plan:** no pause; port after the phase 3
checkpoint or at 0.2.0 final if sooner (queue between runs); concurrency screen skipped. The queue's tag check
(bench2-queue.sh newtag) would have paused at the next gap: it now ignores pre-release tags (backup
*.before-prerelease; ugrep in the interactive shell needs `grep -v -e '-'`); the queue service was restarted 09:04
while o02 kept running (KillMode=process). The session tag watch has the same filter.

**10:0x-10:25 (10-19) — Jan files and progress (the user's two questions; nothing touched the queue):**
* Files, from Jan v0.8.6's source (not from the user's Jan data):
  - A chat attachment is ingested by its original path into Jan's own vector DB, or inlined into the message
    (rag-extension parseMode auto). Jan keeps no copy; the model sees file_id/name/type/size and no path.
  - Only "Cowork" agent sessions copy attachments into <workspace>/attachments (tauri-plugin-agent-tools).
  - So neither hand-over nor attach-by-name works -> **inbox**: ~/ai/deep-research/inbox; research_start `use_inbox`
    copies its readable files into jobs/<id>/inbox when queued; new tool `research_inbox` lists it; INSTRUCTIONS tell
    the model to use it on "use my inbox".
* research_status: stage (researching with time left / writing the report + LDR's "Writing section i of N" /
  checking citations / finishing), research time used and left, counts, "Now:" (LDR's last "Investigating subtopic"),
  "Latest findings" (last 4 subagent topics + their first real sentence). Read from the job's own evidence file and
  LDR's log only.
* Runner: notifications "Research: writing the report" (the lead's lead_answer note, read incrementally) and
  "Research: checking citations" (report-unverified.md appears), once per run (job milestones_seen). Tested on the
  bench o02 run with notify stubbed: both once, then silent.
* Jan v0.8.6 display:
  - It shows an MCP tool's text as raw markdown source in a code box ~10 lines tall (CodeBlock language markdown),
    not rendered, so there is no HTML card. It does render image content items.
  - It shows MCP `notifications/progress` (progress.rs + useMcpToolProgress -> tool runtime, % and message), but only
    on a tool call that is still running (Jan's tool timeout is 30 s); our jobs run after research_start returns.
    Reported only, not built on.
* Backups *.before-inbox-status / *.before-milestones. Runner restarted 10:21. Jan picks up the MCP server change at
  its next start of the server (restart Jan, or switch the server off and on). Test job
  20261019-102149-test-only-... queued + cancelled (closed by the runner once the bench lock frees).

**10:3x-11:00 (10-19) — the user's follow-ups (nothing touched the queue):**
* Jan Cowork (v0.8.6 source):
  - (a) MCP tools: the chat transport loads MCP tools for every chat, with no agent-mode exception seen, so Cowork
    very likely can use ours (not checked in the app).
  - (b) Attachments go to `ensure_session_workspace(data_folder, session_id)` = agent-workspace/sessions/<id>/attachments
    in Jan's data folder, whatever folder is attached (attaching a folder only grants read/write to it). So it cannot
    land files in the inbox.
* Built: Nautilus script `~/.local/share/nautilus/scripts/Send to research inbox` (copies the selection, -2/-3 on a
  name clash, a notification; tested with args and NAUTILUS_SCRIPT_SELECTED_FILE_PATHS) and the "Research inbox"
  launcher (~/.local/share/applications/research-inbox.desktop + ~/Desktop, trusted; xdg-open the inbox).
* Tavily fallback, built and dormant until ~/.config/deep-research/tavily.key exists (a watcher waits for it, existence
  only):
  - tools/tavily_fallback.py: stdlib; key read at request time only, never logged; monthly cap 950 (usage file,
    file-locked; failed requests count); log logs/tavily-fallback.jsonl.
  - LDR patch 0005 (both copies, apply.sh lists it): in SearXNG's _get_previews, fewer than 5 results ->
    Tavily, only with LDR_SEARCH_FALLBACK=1.
  - Gating: run-ldr.sh writes run/ldr.fallback; the runner starts LDR with it once the key exists (and restarts LDR
    when the state differs); bench2.py refuses to measure on an LDR with it on; bench2-queue.sh restarts LDR without
    it.
  - Chat page: strata-r21think serve/websearch.py (local commit 9455a366): on a SearXNG error or fewer than 3 results,
    Tavily, and the answer says so; it loads at the next Strata restart.
  - Offline tests against a mock: module, cap, LDR flag on/off, chat; key not in the log.
  - Queue and runner services restarted 10:55 (o03 kept running).
  - Live check (1 credit) when the key appears.
  - The port to 0.2.0 must carry websearch.py's hook.
* Academic search proposal:
  - SearXNG's pubmed engine sends no key (keyless NCBI limit 3 req/s, hence "too many requests" 38 %).
  - SearXNG's semantic scholar engine scrapes www.semanticscholar.org/api/1/search, hence "parsing error" 37 %; a key
    would not fix that.
  - LDR's own engines take keys: search.engine.web.pubmed.api_key (eutils) and
    search.engine.web.semantic_scholar.api_key (official Graph API).

**11:00-11:10 (10-19) — academic search, the user's decision:** no NCBI key (their research is mostly tech).
* **Semantic Scholar's own LDR engine** (official Graph API, no key) for the user's research only:
  - run-ldr.sh with LDR_RESEARCH_S2=1 (the Jan runner sets it always) exports ..._SEMANTIC_SCHOLAR_AGENT_ENABLED=true
    and ..._JOURNAL_REPUTATION_ENABLED=false (the journal-quality filter is an LLM call per new journal), and
    writes run/ldr.s2.
  - LLM relevance filter OFF: the class has needs_llm_relevance_filter=True and the per-engine key is not in LDR's
    defaults, so an env value would be ignored. It is stored in the account (PUT, HTTP 201; ldr-client.py
    ACCOUNT_SETTINGS has it for a fresh setup), and the factory then decides False (checked).
  - In measurements the engine is not an agent tool, so the setting is inert there.
  - The query rewrite (optimize_queries, one LLM call per S2 search) stays on.
  - Gating as for Tavily: bench2.py refuses on run/ldr.s2=on; the queue restarts LDR without it; the runner restarts
    LDR when S2 is off. Services restarted 11:06 (o03 kept running). Backups *.before-s2.
  - Checked: run-ldr's block exports true/false correctly for LDR_RESEARCH_S2=1/0.
* Phase 4 list: Semantic Scholar A/B next to Tavily.
* The SearXNG semantic scholar engine (scraping, parsing errors) stays in LDR's 8889 set unchanged (measurements as
  they are).

**11:20-12:10 (10-19) — memory floor 20 -> 16 GB (the user):** for all runs and daily use; relief restart 22 -> 18 GB.
* strata-compare: guard.py default GUARD_MEM_GIB 16; phase_end/rollback_test 16384 MiB; memguard/server-L 16384;
  api_jobs sends at >= 17. Backups work/r21/floor16-backup/. The 8080 guard was restarted (pid 188542, default 16).
* deep-research: runner MEM_FLOOR_GB 16 / MEM_RELIEF_GB 18; ldr-client MIN_AVAIL_GB 16; run-ldr.sh starts at >= 18;
  bench2-queue relief < 18; queue-measure.sh 18. Backups tmp/backup-2026-10-17/*.before-floor16.
  - The runner's relief stays at 22 until o03 ends: its ldr-client was started with the old 20 GB floor, so relief at
    18 could let o03 be terminated at 20. Switch to 18 when o03 is done.
* NVFP4's 6 GiB exception unchanged. Memory file renamed memavailable-floor.md.
* RAM at the report-stage low point: tools/ram_lowpoint.py samples o03 (results/ram-lowpoint-2026-10-19-o03.json).
* Chat-cache proposal (not built): results/proposal-chat-cache-research-2026-10-19.md - the one-off research classes
  (extract/compact/report/verify/other) made 1,755 parks since 10-16 and none was ever restored; the 12 GiB high point
  was all report + verify; tools/chatcache_park_analysis.py + chatcache_park_sim.py.

**12:35-13:05 (10-19) — Exa (3.0, released 10-19) next to Tavily, and web search in Jan (the user):**
* Exa 3.0, checked on exa.ai (blog, pricing, API reference, changelog): same /search endpoint and auth; new type
  "lite" ($4/1k, up to 10 results, cached pages only, rejects unsupported parameters with HTTP 400); fast/instant ->
  lite, deep-reasoning -> deep; auto $7/1k; +$1/1k per result past 10; deep-lite/deep $12, deep-reasoning $15; Dynamic
  Highlights GA per the blog (the reference still wants header Exa-Beta: dynamic-highlights-2026-08-28); index adds
  1.27B shopping listings etc. Free: $10 credit, reset to $10 on the 1st of each month, no payment method, one-time
  $10 onboarding bonus; out of credit = HTTP 402 (rejected, not billed).
* tools/exa_fallback.py: Lite + highlights; counter in dollars, cap $9.00/month (2,250 Lite searches; the bonus is not
  counted); reserve before sending, corrected to costDollars.total; 402 closes the month. tools/search_fallback.py:
  Exa, then Tavily. Patch 0005 renamed 0005-search-fallback.patch (both LDR copies; apply.sh status: patched); the
  chat page's websearch.py uses the chain (local commit a2ec5ac1; picked up at the next Strata start). Runner: fallback
  on when either key exists (restarted). Mock tests: all pass (order, body, counter, 402, month reset, no key in files,
  chat page, LDR). Watcher for exa.key started.
* Phase 4 list (PLAN.md): (a) Exa Lite as an extra source; (b) Dynamic Highlights instead of local extraction on
  some pages (time, quality, verbatim enough for the citation check); (c) shopping index on product questions.
* Jan: tools/web-mcp.py (web_search + fetch_page) registered in Jan's mcp_config.json ("web-search", LDR venv python);
  Jan's built-in web search (8888) switched off (settings.json setting-web-search webSearchEnabled false). Backups in
  tmp/backup-2026-10-17/exa/. In-process tests 15/15 pass (SearXNG few/empty/down/many, forced sources, Exa
  highlights, local/LAN/file addresses refused, no key in logs); stdio: live 8889 search 3.5 s, a page 0.4 s, a PDF.
* Still open: the three tests from Jan itself (normal; "search with Exa"; SearXNG empty) - need exa.key and a Strata
  gap in the queue; no GUI automation here (no xdotool), so they are the user's three prompts or a model-level run.

**12:54 (10-19) — o03 medium done (rc 0, 143 min); RAM at the report-stage low point (the user's item 2):**
* Lowest MemAvailable in the report/citation stage: 20.74 GiB at 12:43:59 (citation check), of 91.96 GiB visible.
  Strata engine 62.4 GiB RSS = expert arena 46.8 (pinned) + chat cache 11.6 (11 parked conversations; budget 12) +
  KV streaming host K/V 1.55 (pinned) + ~2.4 other (CUDA runtime/driver mappings, staging rows). Strata server 0.2;
  LDR 2.9; SearXNG 8889 0.9, 8888 0.1; Jan not running; proxy/runner/client 0.1; everything else 4.3 (desktop 1.2,
  this Claude Code session 0.5, ...). Page cache 21.4 GiB (counted as available already).
* Two relief restarts in o03's report stage (12:36, 12:44, at the temporary 22 GB trigger), each back to ~33 GB; the
  chat cache refilled 0 -> 11.6 GiB in about 6 min of report/citation-check calls. Relief now 18 (runner restarted
  12:55); at 18 neither would have fired. The guard after the 12:46 restart runs with the default 16 GiB.
* Next run started 12:55: screen-extra baseline o07 (LDR baseline, fallback off, S2 off; T 1.0/0.95/20/0.05).
  kcheck clean.

**13:00-13:30 (10-19) — the user's follow-ups:**
* Jan: one wording for which tool to use (tools/tool_choice.py) in both servers' instructions and the web_search /
  research_quick / research_start descriptions: plain lookups -> web_search + fetch_page; research_quick = a few
  sources compared; research_start only on request. web_search now uses the chat page's SearXNG (8888) and refuses
  8889/8890 (research and measurements only). Tests: 15/15 mock; both servers carry the wording; live 8888 search 5 s.
* Memory proposal A, user OK with changes: proxy part built and OFF (run/chat-cache-policy.json; apply_chat_cache_policy:
  strata_owner on every research call, strata_checkpoint=false on extract/compact/report/verify/other = upstream #830,
  nothing to park; strata_chat_drop on report/verify). Engine/server owner tag + drop: on the ported build at the switch
  point. Switch between phase 3 and 4 (PLAN.md "Switch point"). Earlier rounds' round trips (park -> resume vs direct:
  NLL identical, same state hashes) to be repeated on the phase 4 build first.
* The user asked not to park LDR's calls at all; o03's data: the agent class resumed parked conversations on 213 of
  318 calls (6.16M tokens, ~24 min of re-reading at 4,236 tok/s on a 143-min run). Asked the user before including it.
* 13:40 (10-19) the user decided: keep parking the research agent's conversation; skip parking only for the one-off
  calls (run/chat-cache-policy.json as built: extract, compact, report, verify, other); drop at report start.
* Phase 4 vs phase 3 (the user's rule): no minutes across builds. Chosen: compare by work (tools/run_work.py: calls per
  class, prompt / fresh / generated tokens, searches, fetches; free, from logs/llm-calls.jsonl + the run's capture);
  minutes only within phase 4 (same build). Not chosen: re-timing a phase 3 run (~2.5 h). PLAN.md has the rule.
  Phase 3 so far (medium deep): o01 434 calls / 11.5M prompt / 8.0M fresh / 0.98M generated; o02 664 / 13.7M /
  6.2M / 0.88M; o03 696 / 14.3M / 6.2M / 0.92M.
* 14:00-15:00 (10-19) queue: hard xhigh five moved before the open xhigh runs; o02/o03/o07/o08 xhigh run only if xhigh
  beats medium on the hard five, graded BLIND against the frozen answers (bench2.py xhigh-blind -> my grades in
  blind/grades.jsonl -> bench2.py xhigh-decide writes xhigh-decision.json with the method); the queue waits for that
  file, nothing decides by itself. tools/bench2-queue.sh: tmp/bench2.hold = a gap (no new run) for the 0.2.0 port; after
  each gap strata-compare work/r22/port_gap.sh end switches back to C*18t (checked) with the parking policy off and logs
  it here.

**15:00-15:40 (10-19) — "a new Jan chat looked at an earlier LDR report" (checked from tool names, settings, code and
logs only; no chat or report text read):**
* The chat: Jan's last session was 10-18 evening (app.log ends 22:57; Jan's log is UTC). Its only tool calls through
  our servers: research_quick at 22:24:33 (a new quick job, 20261018-222433-best-local-llm-...) and research_report x5
  on that same job at 22:25-22:26. The job never had a report (report_md empty; LDR's quick run hit the 15-min cap and
  was stopped at 22:39), so each research_report returned only "not ready yet" + status. No report text reached Jan
  through our tools in that chat; Jan's built-in web search (on then, 8888) does not log tool names.
* LDR's library is not a source anywhere: search.tool = searxng (also exported by run-ldr.sh), the LDR agent's tools
  since 09-29 18:51 were only web_search / fetch_content / research_subtopic (+ read_file for jobs with files); the
  library engine (search.engine.library.enabled, default true) is registered but was never offered. The quick job's
  first call was 942 tokens (nothing injected). Nothing changed in LDR.
* Measurement runs (34 phase 3 runs): only those three tools, plus read_file in o01 (deep xhigh, deep medium) - it
  opens only o01's two frozen input files (strata-REPORT.md, strata-NOTES.md, FROZEN.txt, 10-17). No earlier report.
* The path that does make old reports reachable: the research server (research_list + research_report; research_report
  without a job id returned the newest finished report, whatever its question).
* Changed (backups *.before-pastreports): tools/tool_choice.py PAST_REPORTS - an earlier report is a starting point,
  not a source: say so with its date, re-check anything that changes over time with a fresh web_search, mark each
  point re-checked or carried over unchecked from the <date> report, never state unchecked points as current fact,
  call out changes ("your <date> report said X; now Y"). In both servers' instructions and research_report's
  description. research_report: every report is dated; a job created before this server process (an earlier Jan
  session) is headed "EARLIER REPORT - finished <date>, question ..." + the rule; without a job id it lists the
  finished reports (dated) instead of returning one. Tests 6/6 (stand-in jobs). Jan picks it up at its next start.

**15:45-16:30 (10-19) — failed research never looks like research; why the 10-18 quick answer overran:**
* research-mcp.py outcome_line(): a job that ended without a report is said plainly first in research_status,
  research_report, research_quick and research_list - "FAILED: stopped at 15 min (the quick answer took over 15 min),
  no report - nothing was researched", "FAILED after N min: <reason>", "CANCELLED by you"; a quick answer blocked by a
  measurement run / the night pause / a job ahead: "NOT STARTED", and research_quick withdraws it. Shared rule
  tool_choice.py RESEARCH_FAILED in both servers: stop asking about that job, tell the user the answer was not
  researched and why, answer with web_search + fetch_page and say so. Tests 9/9 (stand-in jobs). Backups
  *.before-failed. Jan picks it up at its next start.
* 10-18 22:24 quick answer: nothing ahead of it, no gate holds, searches 3.4 of 15.2 min, thinking normal; plain LDR's
  agent ran the lead + 7 subtopic agents (104 calls, 8.8 min of Strata) while another client (by its shape Jan's own
  model with Jan's built-in web search) took 3.9 min of Strata in 36 requests. Quick answers do wait behind
  measurement runs (runner: no job while bench runs). Proposal (not built): results/proposal-quick-answers-2026-10-19.md.

**16:30-17:00 (10-19) — the user's decisions on quick answers:**
* Option 2 BUILT: quick answers only (the runner starts LDR in the baseline profile for a quick job with
  LDR_QUICK_LIMITS=1): LDR_LANGGRAPH_AGENT_INCLUDE_SUB_RESEARCH=false + LDR_LANGGRAPH_AGENT_MAX_ITERATIONS=12 (LDR reads
  env first and reapplies it to every research's snapshot). run-ldr.sh writes run/ldr.quicklimits; bench2.py refuses
  to measure while it is on; bench2-queue.sh restarts LDR without it (env -u LDR_QUICK_LIMITS); the runner restarts LDR
  when a quick / deep job needs the other state. Phase 3's baseline arms never see it. Tests: run-ldr exports only with
  =1; bench2 refuses on / goes on off (sandbox); runner sets it for baseline only. Runner + queue restarted 14:50
  (o07 kept running). Live check of a quick answer's length: at the next quick request (not started by me).
* Option 1 skipped: while a measurement holds LDR, quick answers say NOT STARTED and the model uses web_search.
  Revisit after phase 5 if quick answers are still often blocked (PLAN.md).
* Ask-only: tool_choice.py TOOL_CHOICE - by default web_search + fetch_page (also when sources need comparing);
  research_quick only when the user asks ("quick research on ..."), research_start only for deep research on request;
  never start either on your own. In both servers' instructions and the tools' descriptions. Backups
  *.before-quicklimits. I do not start research_quick myself either (my Jan tests use web_search only).

**16:11 (10-19) — o07 deep medium done; o08 deep medium started.**
* screen-extra deep medium o07: rc 0, 143 min wall (2 min held by the proxy gate). One relief restart at 15:55
  (MemAvailable 17.6 GB < the new 18 trigger), back to 32.8 GB at 15:57; the first relief at 18 since the change.
  kcheck clean (16:12).
* o08 started 16:11:40 on the same LDR (deep profile, started 13:47, before the quick-limits change: no
  ldr.quicklimits file = off; fallback off, S2 off); LDR creates its LLM with temperature 1, top-p/top-k/min-p from
  C*18t's config. Then port gap 1.

* 2026-10-19 18:44 0.2.0 port gap BEGIN (gap 1: build, quality checks, chat-cache checks, A B B A, unit tests): queue held after its run, test lock taken, C*18t on 8080 stopped.

**18:43-18:50 (10-19) — o08 done; relief trigger 18 -> 20 GB (the user); gap 1 open.**
* screen-extra deep medium o08: rc 0, 152 min wall (11 min held). Relief restarts at 18:07 (MemAvailable 16.7 GB when
  the restart could start - free memory kept falling after the 18 GB trigger, waiting for a gap between calls; 0.7 above
  the floor) and 18:38 (17.9 GB), each back to ~32 GB.
* The user: relief trigger 20 GB until proposal A is in (phase 4). tools/research-runner.py MEM_RELIEF_GB 18 -> 20,
  tools/bench2-queue.sh relief < 20 (backups tmp/backup-2026-10-17/*.before-relief20); runner + queue restarted 18:44
  (queue held for gap 1). The floor stays 16; run-ldr.sh's start check (18) unchanged.
* tools/ram_dip.py (daemon, started 18:47, log logs/ram-dip.log): at the next MemAvailable dip below 20 GiB, the o03
  breakdown at the dip's lowest point (+ browser, other desktop apps, the Claude Code session and its shells, the run
  and stage in progress) -> results/ram-dip-<start>.json.
* Port gap 1 opened 18:44 (BEGIN line above). The build runs with Strata stopped; from now on at most 16 compile jobs
  and strata-compare work/r22/build_memguard.sh (pause below 24 GB free, stop below 18). The first build (24 jobs,
  18:44:02-18:45:43, before the cap): 83 GB free at 18:44:20, and the watchdog (from 18:44:34) saw nothing below 24.
* 19:41 gap 1 stall fixed: port_gap.sh held tmp/gpu-test.lock exclusively, and with_server.sh (the gap's own test
  servers) waits for a shared hold - the needles step waited 18:52-19:41. The hold was switched to shared without a
  free moment (new shared holder queued, then the old one stopped by PID); the launchers' exclusive try is still
  refused. port_gap.sh now takes it shared. Gap 1 ends ~50 min later than planned (~23:00-23:15).
* 2026-10-19 20:12 0.2.0 port gap END: switched back to C*18t on 8080 (engine sha e428a826c5fb), chat-cache parking policy off; queue resumes.
* Gap 1 ran 18:44-20:12 (not ~23:00 as estimated at 19:41: the steps were quick once the lock was fixed). Results in
  strata-compare results/r22/port-020-beta.md: quality as C*18t (needles 72/72, Stop at 120K, follow-ups, copy /
  injection, repeat3); chat-cache checks ALL PASS (resumed = fresh); decode -2.6 % vs C*18t, TTFT 32K -0.8 %;
  Python tests all OK; C++ 139/147 (the 8 failures are test data / the ggml fork / upstream scripts, none in our
  changes; gap 2 reruns them on pristine 0.2.0-beta).
* 20:12:55 h02 (hard-screen deep medium) started on C*18t, relief at 20, policy off.

* 2026-10-19 21:15 0.2.0 port gap BEGIN (gap 2: tuner, GR_FORK / QSA_SPLIT_ATTN A B B A, full screen, pristine ctest, pictures): queue held after its run, test lock taken, C*18t on 8080 stopped.
* Hard-screen deep medium done on C*18t: h02 12 min, h04 18, h05 13, h06 11, h08 8 (rc 0 each, nothing held, no
  relief restart, MemAvailable never under 20 GiB - tools/ram_dip.py captured no dip). kcheck clean after each.
* 21:06-21:15 port gap 2 BEGIN (above, now a shared hold): strata-compare work/r22/gap2.sh - pristine ctest, GR_FORK /
  QSA_SPLIT_ATTN A B B A, full screen vs C*18t, strata tune auto (thorough, 2 h), the pictures step; then the
  switch-back. Hard xhigh x5 follow.
* 2026-10-19 22:45 0.2.0 port gap END: switched back to C*18t on 8080 (engine sha e428a826c5fb), chat-cache parking policy off; queue resumes.
* Gap 2 (21:15-22:45), strata-compare results/r22/port-020-beta.md: unmodified 0.2.0-beta has the same 8 C++ test
  failures; our GR_FORK / QSA_SPLIT_ATTN stay (0.2.0's defaults -4.0 % / -1.0 % decode); full screen vs C*18t level
  (decode -0.1 %, prompts -0.7 %); tuner: "already fastest", nothing changed; pictures: reader ~1 GB RAM, no speed
  cost, 8/11 identical text replies (2 fewer expert-cache slots with --vision - to confirm), screenshot answered in
  4.5 s / 7.8 s with a few misread digits. 22:45 switched back to C*18t; hard xhigh h02 started 22:45:58.

**23:14-23:17 (10-19) — memory floor 16 -> 12 GB (the user: "We can do a limit of 12gb for the lowest").**
* strata-compare: guard.py default GUARD_MEM_GIB 12; memguard.sh / server-L.sh 12288; phase_end.sh / rollback_test.sh
  pre-load check 12288; work/suite/api_jobs.py sends at >= 13; work/r22/floor_watch.sh stops at 13, build_memguard.sh
  at 14 (backups strata-compare work/r22/floor12-backup/). The standing 8080 guard (follows engine restarts, keeps the
  floor it started with) replaced at 23:16 by work/r22/restart_8080_guard.sh (new one started, then the old one
  stopped by PID).
* deep-research: research-runner.py MEM_FLOOR_GB 12 (start checks floor + 2 = 14), ldr-client.py MIN_AVAIL_GB 12,
  run-ldr.sh start check 18 -> 14, queue-measure.sh 18 -> 14 (backups tmp/backup-2026-10-17/*.before-floor12);
  runner restarted 23:16. Unchanged: relief trigger 20 (until proposal A), NVFP4's 6 GiB exception, the dip capture
  at 20. h02 xhigh's bench client (started 22:45) keeps 16 until it ends.

**23:14-23:20 (10-19) — both fallback keys present (the user); live checks.**
* exa.key and tavily.key exist (mode 600; contents never read or printed). Exa live check 23:17:06: one Lite search
  with highlights, 10 results in 0.6 s, costDollars $0.004 -> month counter $0.004 of the $9.00 cap. Tavily live
  check 23:17:12: one basic search, 5 results in 1.7 s -> counter 1 of 950. No key text in exa-fallback.jsonl,
  tavily-fallback.jsonl or web-mcp.log (compared against the key files without printing them).
* The Jan web_search cases through Strata: tools/jan_websearch_check.py (plays Jan: both of Jan's MCP servers as
  mcp_config.json starts them, all their tools offered, Jan's default assistant instructions, 8080, the user's
  sampling, effort medium; research_* calls are recorded as a wrong choice and NOT run). Cases: normal, "Search with
  Exa", SearXNG empty (a stand-in on 127.0.0.1:8899 returning no results - 8888's Bing / Yahoo answer even made-up
  phrases, so no query produces it), "Search with Tavily". Runs in the gap after h02 xhigh (hold file 23:19).
* 23:37-23:38 the Jan web_search cases through Strata (C*18t on 8080; results/jan-websearch-check-2026-10-19/), all
  as expected, no research_* call: normal - web_search auto, "Answered by: SearXNG (8)", 2 fetch_page, 12.6 s;
  "Search with Exa" - source exa, Exa (8), 2 fetch_page, 10.1 s; SearXNG empty (stand-in) - 4 web_search auto, each
  answered by Exa (8/8/6/6), 2 fetch_page, 25.6 s; "Search with Tavily" - source tavily, Tavily (5), 6.9 s. Counters
  after: Exa $0.024 (6 searches), Tavily 2. Hold removed 23:38:30. h02 xhigh: rc 0, 51 min (medium 12).
* 01:10 (10-20) first dip below 20 GiB since tools/ram_dip.py started: h05 xhigh, report call (proxy class report),
  lowest MemAvailable 20.00 GiB at 01:10:24 (results/ram-dip-20261020T011024.json); relief restart 01:10:25-01:11:29
  -> 34.4 GB, no further fall. Against o03's 20.74 GiB low: Strata engine RSS 64.15 vs 62.39 (anon +1.7: arena equal
  46.8, parked chat cache 11.3 vs 11.6 GiB / 11 conversations each, the rest of the engine +2.0 GiB - most likely the
  live report conversation's own state; unconfirmed); Chrome 3.08 GiB RSS (1.03 private), not running at o03 (started
  23:11); other desktop apps 3.05 (Open WebUI 0.79, gnome-software 0.44, gnome-shell 0.31, Xorg 0.21) ~ o03's;
  this Claude Code session 0.43 (0.47); smaller: LDR 1.23 (2.89), SearXNG 8889 0.44 (0.94). h04 xhigh: rc 0, 49 min
  (5 held: the gate's yield after the Jan cases).
* h05 xhigh: rc 0, 80 min wall, 534 s held (research clock 71 min): 49 s at 01:10:41 while the relief restart ran,
  308 s at 01:15:50 (the gate's yield - another client used Strata then), the rest in short waits. kcheck clean.
  h06 xhigh started 01:47:47.

* 2026-10-20 03:09 0.2.0 port gap BEGIN (gap 3: the 0.2.1 port - build, quality, chat cache, speed, pictures, unit tests): queue held after its run, test lock taken, C*18t on 8080 stopped.

**03:04-03:14 (10-20) — v0.2.1 tagged; xhigh decision; open-ended blind grades.**
* v0.2.1 (final; 107 commits on v0.2.0-beta, engine 0.1.46) tagged 03:04; the queue stopped itself at 03:07 after h08
  xhigh ("the port comes first"). Our 26 commits cherry-picked onto v0.2.1 without conflicts (branch r22-port021,
  worktree strata-compare/strata-r22p021; 644 Python files compile, app.js parses; same pinned ggml). Gap 3 (the 0.2.1
  port's build and tests, strata-compare work/r22/gap3.sh) started 03:08.
* Hard xhigh: h02 51 min, h04 49 (5 held), h05 80 (9 held), h06 45, h08 35; all rc 0. Medium took 8-18 min each.
* xhigh decision (results/bench2/xhigh-decision.json, blind): medium 5/5, xhigh 5/5 -> tie, run_xhigh_open false; the
  open xhigh runs (o02/o03/o07/o08) are skipped. bench2.py next: done - phase 3's queue is complete.
* Open-ended, graded blind against my-research (blind/grades.jsonl, key revealed after): o02 deep medium 11 / baseline
  6.5 (of 12); o03 11.5 / 11.5 (of 12, tie); o07 deep medium 7.5 / baseline 11.5 (of 14 - deep medium assumed a
  21-23 GB file ceiling and offered only 35B models); o08 deep medium 10.5 / baseline 4 (of 14). With o01 (deep xhigh
  10, deep medium 9.5, baseline 2.5 of 10): deep medium wins 3, ties 1, loses 1 of 5.
* One fact checked by web search while grading o03: EN 18286:2026 was cited in the OJ by Implementing Decision (EU)
  2026/2274, 14 Oct 2026.
* Next: the level replays (tools/level-replay.py extract / report / verify; daytime only, from 09:00) on C*18t after
  gap 3, then the checkpoint report.
* Wait table again at the chosen level (results/bench2/wait-table-2026-10-20.md, tools/wait_table.py; deep medium runs,
  13.5 h): a chat message waits p50 11 s, p90 65 s, over 60 s 11 % of the time (xhigh runs: p50 50 s, p90 147 s, 43 %;
  10-18's xhigh table: 55 / 152 s, 47 %). Longest medium calls: compaction p50 64 s, p90 119 s (125 calls); extraction
  p50 9 s. By the user's rule (propose pre-empt-and-replay only if a first message still often waits over a minute):
  not proposed.
* 2026-10-20 04:19 0.2.0 port gap END: switched back to C*18t on 8080 (engine sha e428a826c5fb), chat-cache parking policy off; queue resumes.

**04:19-04:35 (10-20) — gap 3 (0.2.1 port) done; replays armed.**
* 0.2.1 port, gap 3 (strata-compare results/r22/port-020-beta.md "0.2.1 port"): quality identical to the 0.2.0 port
  (exact7 7/7 vs r22p-e7, repeat3 same hash, needles 72/72, all probes as before), chat cache ALL PASS, speed vs C*18t
  decode -1.7 / -2.0 %, prompts -0.7 to -0.9 %; pictures: identity 11/11 with the expert cache pinned (gap 2's 8/11 was
  the 2-slot difference), the elastic reader needs "vram_elastic" in 0.2.1 (not engaged); unit tests as before.
  04:19:52 switched back to C*18t (SHA checked), policy off; kcheck clean.
* bench2-queue.sh: its release pause now compares with v0.2.1 (was v0.1.45; backup *.before-tag021). The queue
  service stays stopped (phase 3 done; phase 4 waits for the go). Tag watch restarted with KNOWN=v0.2.1.
* tmp/replays-0900.sh started (waits for 09:00): extraction replay (30 tasks, low / medium / xhigh), citation-check
  and report replays on screen-deep-medium o01-o03 (medium vs xhigh), through the proxy, C*18t checked; the user's
  Jan research goes first. Log logs/replays-2026-10-20.log.
* 10-20 05:21 Strata v0.2.1.1 tagged (final): a Windows long-path and Docker hotfix - packaging, updater, CLI, tests;
  src/ and serve/ unchanged, CMake only the version string (0.1.46.1). Nothing to port: the 0.2.1 port stands.
  bench2-queue.sh's release pause now compares with v0.2.1.1 (backup *.before-tag0211); tag watch restarted with
  KNOWN=v0.2.1.1 (strata-compare logs/r21/tagwatch-0211.out).
* 10-20 07:1x the user's morning decisions: (1) long runs allowed at night for good (run/night-ok kept, text updated;
  tools/level-replay.py's daytime check now honours it, backup *.before-nights); (2) pictures: the reader always on at
  the switch point, no load-on-demand patch; (3) before 0.2.1 is promoted: find gap 3's 1.7-2.0 % decode loss in a
  1 h gap after the replays (strata-compare work/r22/gap4.sh, started by work/r22/gap4-after-replays.sh); (4) watchers
  as user services: strata-tagwatch, strata-gyrol-watch, ram-dip (~/.config/systemd/user; kwatch already was one);
  (5) phase 4: the o07 frame error goes near the top (hardware profile + setup-claim check); go and order after the
  checkpoint.
* 0.2.1's server closes thinking at 3/4 of max_tokens when a request sets max_tokens >= 1024 ("answer_room", new since
  0.1.45; "answer_room": false turns it off). LDR sends 30000 / 60000: in logs/llm-calls.jsonl 30 of 6,870 calls
  reached 3/4 of their cap and 12 ended on length with no answer - those would get an answer. Jan's assistant sets no
  max_tokens. A decision for the switch point.
* 10-20 PHASE 3 -> 4 DIFFERENCE: answer_room. The user keeps 0.2.1's answer_room ON at the promotion (phase 3 ran on
  C*18t without it). With a request's max_tokens >= 1024 (or, with none, the context room left), thinking is closed at
  3/4 of the cap so the reply always has an answer. In phase 1-3's call log 30 of 6,870 LDR calls reached 3/4 of their
  cap (12 of them ended on length with no answer); in phase 4 those think less and answer. Account for it when phase 4
  is compared with phase 3 by calls and tokens.
  Caps per client (configs, code, Strata's logs - numbers only): OpenCode 32,768 (our opencode.jsonc limit.output;
  harness tests 332 of 335 turns, the rest 31-32K) -> thinking up to 24,576; DeepSeek Harness 32,768 (our profile
  patch; 65,536 in 6 test turns; its 64-token title request is under 1,024, untouched) -> 24,576; Codex none
  (Responses API, no output setting; 80 of 80 test turns); Jan none (Max Output Tokens unset in both assistants; no
  2,048 in any 8080 log; its 100K context budget leaves >= ~31K room -> thinking >= ~23K); the chat page none unless a
  value is typed into its settings (default empty); LDR 30,000 / 60,000, the proxy's context guard shortens long
  prompts' caps (lowest seen 26,593 -> 19,945). No client sets a cap under 16K; the round 4,096 / 512 / 81,920 / 16,384
  caps in the 8080 logs are our own tests. The only way under 16K: a conversation that leaves under ~21K of the
  131K context (no-cap clients) - the context is the limit there, nothing to raise; C*18t ran out mid-thought then.
  Harness tests: no reply ended on length; the longest was 15,226 tokens.

10-20 08:42: level replays started early (the user: "You can continue with everything right now."); tmp/replays-0900.sh without its 09:00 wait (copy *.before-now); gap 4 still follows the replays.

10-20 09:2x EXTRACTION REPLAY graded blind (30 tasks x low/medium/xhigh): first 10 / 12.5 / 5.5, mean rank 1.91 / 1.88 / 2.21; xhigh 6.3x the tokens of medium, not better (low beats xhigh 17-9, p 0.17). results/bench2/replays/extract/summary.md. The Jan deep profile still extracts at xhigh (research-runner.py DEEP_EFFORTS): proposal medium, for the user to decide.

10-20 10:2x CITATION-CHECK REPLAY (o01-o03, 40 claims each, medium vs xhigh): same verdict 96/120; the 24 differences judged blind: xhigh matched 14, medium 10; medium too lenient 10 (xhigh 1), xhigh too strict 9 (medium 3); xhigh 2.8x the time (35 vs 13 min per 120 claims). Proposal: citation check stays xhigh (the deep profile default; the bench deep-medium runs used medium). results/bench2/replays/verify/summary.md.

10-20 11:4x REPORT-WRITING REPLAY (o01-o03 evidence, medium vs xhigh; o02/o03 graded blind, o01 not): medium 31, xhigh 31.5 of 34; o01 medium 9.5-8.5, o02 xhigh 11.5-10, o03 tie 11.5; xhigh 3.0x the time (76 vs 25 min for 3 reports), same output size; one xhigh outline hit the 30K cap and was retried. Proposal: report writing at medium (the Jan deep profile writes at xhigh, package default). Full proposal: medium everywhere except the citation check (xhigh), for the user to decide. results/bench2/replays/report/summary.md.

10-20 11:45 gap 4 started 4 min late: the 08:42 launcher shell had the replay script name in its own command line (inside the NOTES printf), so the starter's pgrep kept matching it after the replays ended; killed that idle shell by PID. Rule kept: no watched pattern text anywhere on a launching command line.

* 2026-10-20 11:46 0.2.0 port gap BEGIN (gap 4: the 0.2.1 decode loss (answer_room, RTX 50 defaults; 1 h box)): queue held after its run, test lock taken, C*18t on 8080 stopped.

10-20 11:55 DEEP PROFILE EFFORTS CHANGED (the user: "go with your recommendation"): agent medium, extraction medium, report writing medium; citation check stays xhigh. tools/research-runner.py: DEEP_EFFORTS (proxy mode file) agent/extract medium; new DEEP_LDR_EFFORTS = LDR_DEEP_REPORT_EFFORT=medium + LDR_DEEP_VERIFY_EFFORT=xhigh in run_ldr (deep profile only); the runner restarts LDR when run/ldr.efforts is not "report=medium verify=xhigh". Runner service restarted 11:55 (no Jan job queued or running); LDR (up since the replays, report=default verify=default) gets the new settings at the next Jan deep job. Not touched: bench2.py / bench2-queue.sh / ldr-client.py (measurements set their own efforts), gap 4 (running). README "Thinking effort" updated.

10-20 12:0x PHASE 4 LIST (CHECKPOINT-phase3.md section 8), the user's additions: new item 2 = a dated fresh search for every "not yet published/released/available/supported" claim before it goes in a report (test: o03 EN 18286, OJ 14 Oct); item 1 (hardware profile) gets o02's replay mistakes as test cases (x16 card in a chipset x4 slot; the 5090 ratio given for the 5080) next to o07's "24 GB VRAM". Later items renumbered 3-9; order still the user's.

10-20 12:04 Strata v0.2.1.2 tagged (final): one commit, a Windows/AMD hotfix (Strix Halo gfx1151 keeps the expert arena unregistered on Windows; strata.exe finds rocm\bin for --version; delay-loaded ROCm DLLs). Nothing reaches our CUDA/Linux build (igpu_uma_arena_default still false for a discrete GPU), so the 0.2.1 port stands. bench2-queue.sh release pause now compares with v0.2.1.2 (backup *.before-tag0212); tag watch unit KNOWN=v0.2.1.2 (backup .before-tag0212), restarted 12:06.
* 2026-10-20 12:13 0.2.0 port gap END: switched back to C*18t on 8080 (engine sha e428a826c5fb), chat-cache parking policy off; queue resumes.

10-20 12:2x PHASE 4 TESTING ORDER (the user): replay first (planning-step replays for the hardware profile on o07, report-stage replays on o02, the "not yet" check on the saved o03 reports); only items that fix their test case on replay get full deep runs with/without on the new build; only those that pass go to the screen set; items that change what gets searched start at full runs. Pass rule proposed: fixed in 3/3 replays with, error in >= 2/3 without. Written into CHECKPOINT-phase3.md section 8 with the estimate (items 1, 2, 5 through all stages ~34 GPU h / ~3 days; everything ~130 h / ~1.5-2 weeks) and PLAN.md; item 10 = the "tried / ruled out" list (round brief) added. Correction to my 12:05 estimate: phase 3 deep screen = o01-o03 + hard five, ~8.5 h per side, not 20+.

10-20 12:14 GAP 4 (strata-compare results/r22/port-020-beta.md "Gap 4"): 0.2.1 with answer_room off decodes at parity with C*18t (154.6 vs 153.2 tok/s, +0.9 %, inside the 150-156 spread); gap 3's -1.7/-2.0 % was answer_room doing different work. RTX 50 defaults off: -0.5 % (no effect; keep them on); step 2 skipped. Started 11:45 (4 min late, see 11:45), done 12:13 after 28 min. 12:13:52 switched back to C*18t (e428a826c5fb), policy off, queue released; kcheck clean; 8080 serves C*18t (0.1.44.1). 0.2.1 ready to promote with answer_room on, after the user's OK.

10-20 13:05 Strata v0.2.1.3 tagged (final; Control 0.1.46.2): engine unchanged (CMake version string only), a Terminal/Control/installer update plus small server fixes (serve/server.py): thinking_budget_tokens read as reasoning_budget_tokens (#2141); Anthropic usage reports cache_creation_input_tokens (#2289); an engine that cannot be started answers 503 instead of a dropped connection (#2496); the picture reader's work folder is made again if a temp cleaner removed it (#3370); a non-loopback bind no longer requires an API key (we bind 127.0.0.1 only); the reader path follows an updated engine package. git merge-tree r22-port021 + v0.2.1.3: no conflicts. Proposal for the switch point: fold v0.2.1.3 into the port (no rebuild of the engine needed; server smoke test only) - the user's call with the promotion OK. bench2-queue.sh pause and tag watch KNOWN raised to v0.2.1.3 (backups *.before-tag0213); watcher restarted.

10-20 SWITCH POINT 13:19: 0.2.1 (P021, engine c9fe314316c4) promoted on 8080 - answer_room on, pictures on (CPU reader), C*18t kept as rollback (STRATA_CONFIG=configs/Cstar18t.json; switch-model.sh / run-strata.sh *.before-p021). Chat-cache checks on r22p021RTpin-vision: ALL PASS. run/chat-cache-policy.json enabled at 2026-10-20 13:19:34. Phase 4 runs on this build from here.

10-20 13:2x switch point notes: the first start (13:18:23) was refused because strata-ensure.sh saw tmp/gpu-test.lock a moment after the script released it (the flock process exits after its child) - switch021.sh now waits for the lock to be free; rerun "start" 13:18:53 OK. 8080 = P021 (engine c9fe314316c4, 0.1.46), images on (reader RSS ~1.0-1.1 GB; a screenshot 4.6 s / 2.3 s to the first answer token), standing guard pid 1261256, kcheck clean. answer_room verified: server log "thinking limited to 588 of max_tokens 1100 so the answer has room", the request ended stop with an answer. Results: strata-compare results/r22/switch/. Relief restart trigger stays 20 GB; review after the first phase 4 run (lowest MemAvailable, any relief restart).

10-20 13:20 PHASE 4 QUEUE STARTED (the user's go): deep-research-bench.service with BENCH2_PLAN=queue-plan-p4.json (unit backup .before-p4) - the new-build baselines, label p4base: o07, o01-o03, the hard five; deep at the Jan profile (agent / extraction / report medium, citation check xhigh; fallback and S2 off as in phase 3), capture on, on P021 with the chat-cache policy on (research calls tagged owner). bench2.py: $BENCH2_PLAN and a step's "verify_effort" (next prints a 6th field), run --effort-verify; bench2-queue.sh passes them (backup *.before-p4); phase 3's plan and grading untouched. ~11 h, nights allowed. The user's build order is in CHECKPOINT-phase3.md section 8 (the frame check rides along with item 1, flagged).

* 10-20 14:3x PHASE 4 STAGE 1 TOOLING (build order items 1 and 2; no GPU used to build):
  - user-setup.md: the user's setup as facts, read from the PC (nvidia-smi, lspci, lscpu, meminfo): 9950X3D, 96 GB
    DDR5-6000, RTX 5080 16 GB on CPU lanes at PCIe 5.0 x16, RTX 4060 Ti **8 GB** behind the chipset at PCIe 4.0 x4,
    the 83.6 GB Flash-Next IQ3_S served from RAM ("VRAM is not a ceiling on model size here"). Editable by the user.
  - o07's frame is NOT from the opening plan: call 5's subtopics say "30B-130B ... 96 GB RAM + 24 GB VRAM"; the
    "tier 1 = 21-23 GB files" frame first appears in the lead agent's wrap-up answer (captured call 650), and the
    report outline (651) turned it into "acceptance criteria: ... 21-23 GB Q4_K_M target". So the planning-step
    replay replays call 650, then the report from its answer. A frame check right after planning (#5) would not have
    seen it; the setup check on the report covers it.
  - tools/level-replay.py (backup .before-p4item1): `lead` (one captured lead call again, +/- the <user_setup> block
    in its system prompt), `report --setup --lead --n --label` (the block in the outline/section/opening prompts;
    the lead answer swapped), `setupcheck` (verify-class pass: statements about the user's machine vs the facts:
    contradicts / consistent / unsupported + fix).
  - tools/notyet-check.py (item 2): find "not yet / pending / expected" claims -> LDR's SearXNG (8889) + the first 3
    pages (trafilatura) -> judge outdated / still true / unclear with dates. Offline check: the search finds the OJ
    citation of EN 18286.
  - tools/p4-stage1.sh started 14:33 (pid 1316941): waits for "queue finished (queue-plan-p4.json)", then 1a
    setupcheck on saved reports, 2f notyet on the o03 reports, 1b-1e o07 lead+report replays and o02 report replays
    (3 with / 3 without), 2g false-alarm notyet on o01/o02/o07. ~3.5-4 h GPU. Log logs/p4-stage1.log.
  - 14:35 item 3 stage-1 tools added to level-replay.py: `critic` (fresh-context review: reasoning / unsupported /
    contradiction / stale / gap, each with a fix or a search query) and `verify2` (key claims vs the cited sources
    plus up to 4 uncited stored sources sharing the most words; supporting / contradicting, independent sites by
    domain). Dry-run with a fake model: o03's 40 key claims include the "EN 18286 ... not yet OJ-cited" key finding.
    p4-stage1.sh restarted with item 3's steps at the end (pid 1318932; the first start, 1316941, stopped by PID).

* 2026-10-20 16:03 PAUSE (the user: "Pause and save everything after the concurrency test", Windows boot): tmp/bench2.stop set, so the queue exits after o07 and stays stopped at login; p4-stage1.sh (only waiting) stopped by PID. Resume steps: strata-compare HANDOFF.md, STATUS 2026-10-20 block. Left: o01-o03, h02 h04 h05 h06 h08 (p4base), then stage 1.

* 2026-10-20 16:08 0.2.1 concurrency test GAP BEGIN (the user, 10-20): queue held after its run, test lock taken, 8080 (P021) stopped; arms on 8081.
* 2026-10-20 16:23 0.2.1 concurrency test GAP END: 8080 back on P021 (engine sha c9fe314316c4), chat-cache policy still on; queue released. Results: strata-compare results/r22/conc/summary.txt.

* 2026-10-20 21:10 RESUMED after the user's Windows boot ("continue"): kcheck clean, services active. The user on v0.2.1.3: not folded in (Terminal/Control app + the 0.2.1.2 Strix Halo/Windows memory fix; nothing for Linux/NVIDIA/server/output) - reviewed; fold it in with the next release that touches our path. v0.2.1.4 (tagged 10-20 23:56 +02:00) paused the queue at its restart: Terminal/Control only (download SHA repair, progress words, AMD gfx choice on Windows), CMake version string only, src/serve unchanged since v0.2.1.3 -> no port; baseline raised to v0.2.1.4 (tag watch unit KNOWN, bench2-queue.sh; backups *.before-tag0214). Queue resumed 21:10 with o01; p4-stage1.sh restarted 21:09 (waits for the queue).
* 10-20 21:3x the user: (1) frame check #5 DROPPED from phase 4, parked as an idea (revisit if a screen run shows a
  wrong non-hardware assumption in a plan); (2) correct o07's origin and make item 1's replays hit the step where each
  error starts. Checked in the captures: o07 - plan right (call 5: 30B-130B "on 96GB RAM + 24GB VRAM"), notes right up
  to call 649; the lead's final answer (650) put Flash-Next here at "15-25 tok/s" and named 35B models with 21-23 GB
  files tier 1; outline 651 made it the target. o02 - the plan (call 1) only priced a 4060 Ti 16 GB as a candidate; the
  user's 4060 Ti first becomes "16 GB" in the lead's final answer (635); the x16-avoids-throttling and 5080-for-5090
  ratio slips are the report writer's, in the medium replay only. CHECKPOINT-phase3.md sections 4 + 8 and PLAN.md
  corrected (backups *.before-o07fix). tools/p4-stage1.sh (backup .before-leadsteps; restarted 21:28, pid 19622) adds:
  1c-orig (o07 reports from the ORIGINAL 650 answer, 3 with / 3 without the profile: the report step alone, its
  without side carries the error), 1b2 + 1c2 (o02 call 635 3/3 +/- the profile and the reports from each), 1e checks the
  new with-side reports. About +2.3 h of GPU. No separate planner exists in deep/ (the plan is the lead agent's first
  turn under the same system prompt), so the profile in the lead's system prompt covers planning too.
  Slip: a grep over the whole folder printed one line each from two results/deep-runs/ subagents.md files (the user's
  own research); that folder is excluded from searches from now on.
* 2026-10-21 06:3x Strata v0.2.2 (final, tagged 10-21 11:07 +02:00; engine 0.1.47) paused the phase 4 queue at 06:27 after h04 (done: o01-o03, h02, h04; left h05 h06 h08, then stage 1). Reviewed: src/serve changed (238 commits) -> summary to the user, waiting for the go. On our path: IQ3_S CUDA kernels untouched (trellis/Gyro types 144-146 only), verify early-PLE flag HIP-only (CUDA order unchanged), NUMA pool split off on one node (ours), UMA cache HIP-integrated only, thread names; server: gpu_roles ignored without a "gpu_roles" key (P021 has none), drifted tool-call openers read as calls + undeclared/no-tools calls stay text (#3441/#3075), one tok/s definition (done line + timings from engine decode time), API key optional, thinking_budget_tokens read. Our 26 port commits: git merge-tree onto v0.2.2 = one conflict (src/program/generate.cpp). kcheck clean. Basalt pack: sha256 OK 10-20 23:20 (builds not started: no gap yet).
* 2026-10-21 06:4x the user on v0.2.2: stay on P021 for ALL of phase 4 (its baselines are the "without" arm of stages 2-3; a mid-phase switch = ~11 h of re-runs); only if a later release brings something needed (e.g. Friday's 763B model) - cost first. Baselines raised to v0.2.2 (tag watch KNOWN, bench2-queue.sh; backups *.before-tag022); queue resumed 06:48 (h05). Port: branch r22-port022 (worktree strata-r22p022) = v0.2.2 + our 26 commits (one conflict, generate.cpp: 0.2.2's adapt thread name beside our commit-window change; same diff as on 0.2.1; 8 old Claude trailers stripped on this branch, trees identical). Gap 5 after h08 (work/r22/gap5-wait.sh holds the queue, port_gap4.sh = phase 4 gap helper, back to P021 with the policy on): work/r22/gap5.sh = builds (0.2.2 port, Basalt offline in a no-network namespace, picture reader CUDA sm_89) + the port's checks (exact7, needles, stop120k, probes, repeat3, chat cache, decode/full A B B A vs the 0.2.1 port, unit tests). At any later switch: tool-call check with OpenCode, Jan and the research tools (drifted openers now read as calls).
* 2026-10-21 07:3x the user: Basalt GPU tests at the END of gap 5 (~09:45), then P021 back and stage 1; results to the user as soon as they are in. Prepared (no GPU): work/r22/gap5b.sh (our arms a a1 b4 b5 b7 b7v a1s7, pictures vcpu/vgpu, our logit dumps) + basalt-ab/scripts/basalt_block.sh (c1 c0 bench hc ppl, each in unshare -rn = no network; dry run with a dummy server: 8080 unreachable inside, clean stop). Basalt code notes basalt-ab/notes-code.md (agent): spec sampling exact by construction (seeded per position); two-stage head samples from exactly rescored rows only; --dump-logits dead -> debug patch ppl_top (top-64 per teacher-forced row) + HEADCHECK + exact_head on branch headcheck (basalt-ab/src-headcheck, local commit c0e8f643). Pack: mtp/dense == published tuned dense.bin (our own reader scripts/packsec.py); our dense.bin == their dense-original, experts identical; draft vocab differs (40,525 vs 106,299). Chain: gap5-wait.sh (holds the queue at h08) -> gap5.sh (builds, 0.2.2 checks, gap5b) -> port_gap4.sh end.

* 2026-10-21 08:15 phase 4 gap BEGIN (builds: 0.2.2 port, Basalt, strata-vision CUDA): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-21 10:04 phase 4 gap END: P021 back on 8080 (engine sha c9fe314316c4), chat-cache parking policy on; queue resumes.
* 2026-10-21 10:04 Basalt A/B done in gap 5 (basalt-ab/PLAN.md '10-21 results'): Basalt on the 5080 alone decodes +2 % vs ours (15 % rule not met), reads prompts +14-16 %; two-stage head lossy where its 65,536-row cap binds (2.2 % of verify rows); tuned MTP layer a wash on ours. 0.2.2 port checked (not switched): speed level, 4/7 self-repeat, tool-tag probe 0/6, upstream HIP test fails on v0.2.2 too.
* 2026-10-21 10:08 STAGE 1 FALSE START: the queue service (deep-research-bench) ended at 10:04 and systemd stopped its whole cgroup - strata-proxy, LDR and SearXNG, which bench2-queue.sh had started inside it. Stage 1's replay steps all failed at once (8090 refused; empty reports in ~5 s). Runner stopped by PID 10:09; the 14 bad files moved to tmp/p4-stage1-failed-1008/; run-ldr.sh got a 'proxy' command (proxy only; backup tmp/run-ldr.sh.before-proxycmd); p4-stage1.sh checks 8090 before every step and starts the proxy if needed, P4S1_NOWAIT=1 skips the queue wait (backup tmp/p4-stage1.sh.before-proxycheck). Proxy started 10:11 (pid 675446, outside any service), stage 1 restarted 10:11:56 (pid 675534) from the top.
* 2026-10-21 10:18 stage 1 PAUSED (the user: 'Don't start stage one yet. Or pause it cause it's early.'): runner 675534 and its step stopped by PID during 1a; 1a's one finished setup check moved to tmp/p4-stage1-paused-1018/; bench.lock free, 8080 idle (P021), proxy left running (pass-through). Resume: P4S1_NOWAIT=1 setsid nohup bash tools/p4-stage1.sh (starts from the top).

* 2026-10-21 10:36 phase 4 gap BEGIN (Basalt round 2: tuning + stock arm): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-21 11:10 phase 4 gap END: P021 back on 8080 (engine sha c9fe314316c4), chat-cache parking policy on; queue resumes.

* 2026-10-21 11:11 phase 4 gap BEGIN (Basalt round 2: the stock-defaults arm again): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-21 11:17 phase 4 gap END: P021 back on 8080 (engine sha c9fe314316c4), chat-cache parking policy on; queue resumes.
* 2026-10-21 11:17 stage 1 RESUMED (the user, after Basalt round 2): P4S1_NOWAIT=1, from the top.

* 2026-10-21 19:22 phase 4 gap BEGIN (gap 7: next port build + checks, draft length, v2 prompt kernels, one-flag tests, pictures, profile): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-21 19:21 STAGE 1 DONE (kcheck clean). Graded 19:2x-19:4x: replays BLIND (anonymous shuffled copies, key in results/bench2/replays/grades-stage1/key.json), tools openly; results/bench2/replays/grades-stage1/SUMMARY.md. Item 1 (setup profile + check): o07 frame - reports with the profile 0/3 vs 3/3 and 0/3 vs 2/3 without (PASS), lead answer 0/3 vs 1/3 (can't decide); o02 4060 Ti 16 GB - report from the original lead answer 0/3 vs 3/3 (PASS), from fresh lead answers 1/3 (one heading) vs 3/3, lead answer 2/3 vs 3/3 (the profile in the lead prompt does not stop it); x16 and 5090-ratio slips don't reproduce without (0-3/9). Setup check on saved reports caught o02's three errors 3/3 and o07's frame, <= 2 borderline false alarms of 52. -> item 1 meets its pass (profile or check fixes each) - stage 2 candidate. Item 2 ("not yet"): NO RESULT - LDR's SearXNG (8889) was down all of stage 1 (died with the queue cgroup at 10:04; the runner's check covered only 8090), every search ConnectionError; rerun 2f/2g with 8889 up. Item 3: verify2 contradicted the EN 18286 "pending" claim 3/3 on o03 (critic 2/3); on o02 neither tool catches all three (critic E2 3/3), verify2's contradicted verdicts ~50 % false alarms on o02 (prices, MSRP vs street, a wrong spec source).
* 2026-10-21 19:4x stage 1 tooling fixes (no GPU): level-replay.py setupcheck names outputs <run folder>-<stem> (o01/o07/o03 saved reports were all report.md: o01's 3 checks and o07's run 1 were overwritten) and takes --max-tokens (default 60000; 9 of 18 runs hit 30,000 and saved no claims). Backup tools/level-replay.py.before-s1fix. Reruns needed (GPU): 1a on o01/o07 saved reports, 1e on the with-profile reports, 2f/2g with SearXNG 8889 checked first.

10-21 21:5x PLAN CHANGE (the user): if both checks pass in the next strata-compare gap (40-prompt kernel check, C vs A with rebuilt tool-call turns), 8080 switches mid-phase-4 from P021 to P021 + two lossless ports (the adaptive draft-length rule at spec 7, Basalt's v2 prompt kernels; engine-r22p021n), not to 0.2.2. Phase 4 stays comparable: compare by quality, calls and tokens, not minutes. The phase 4 checkpoint must list which runs ran on which build (switch time logged here when it happens). P021 stays the rollback.
* 2026-10-21 22:30 phase 4 gap END: P021 back on 8080 (engine sha c9fe314316c4), chat-cache parking policy on; queue resumes.

10-21 23:15 8080 (P021) restarted while idle for the user's picture decision: CPU picture reader budget 300 -> 1000 (configs/P021.json vision.max_tokens; backup .before-pv1000). Research runs send no pictures, so phase 4 is unaffected. SearXNG 8889 and 8890 are DOWN (stage 1 follow-up 1 makes them their own services).

10-21 23:1x-23:4x STAGE 1 FOLLOW-UPS 1-2 (the user):
1. SearXNG as its own services: searxng-ldr.service (8889), searxng-ldr-baseline.service (8890) and searxng-chat.service
   (8888, strata-compare websearch/) - systemd user units (copies in systemd/ and strata-compare configs/systemd/),
   `searxng.sh run` = granian in the foreground, Restart=always (kill test: 8889 back in 3 s). Both searxng.sh scripts
   hand start/status to the unit and leave it running on `stop` (SEARXNG_FORCE_STOP=1 really stops); backups
   *.before-units. research-runner.py's idle stop no longer stops SearXNG (it took 8889 down at 08:29:32 - the real
   start of the outage; up again 23:18 as a service); run-strata.sh's stop message says so (backup
   run-strata.sh.before-searxng-units). Pre-flight: tools/services_check.py (SearXNG x3, a stopped unit started once;
   --proxy, --ldr; 8889 required, 8890/8888 warnings) before every run in bench2-queue.sh and every step in
   p4-stage1.sh; the research runner keeps a job queued while 8889 does not answer (research_common.searxng_problems).
   Watcher: searxng-watch.service (tools/searxng_watch.py, every 60 s, critical notify-send after 2 failed checks, again
   when back; log logs/searxng-watch.log; tested on 8890 23:20-23:23). The user's own research after 08:29: NONE (newest
   job 10-19 10:21); Jan's web_search (8889 -> Exa -> Tavily) was not used either (fallback logs unchanged since 10-19).
2. Search-failure guard: LDR's SearXNG engine logs one line per search to logs/search-events.jsonl (n after any
   fallback, SearXNG's own count, error; never the query) - folded into patches/ldr/0005-search-fallback.patch (backup
   .before-events), applied to both the deep install and baseline/site (logging only). research_common.search_health:
   bad = more than half of >= 6 searches failed, or the latest 6 in a row; at the end more than half of >= 3. Research
   runner: stops the run (terminate), job FAILED with the reason, no report handed out (also when LDR finished first).
   ldr-client.py (measurements): terminate, search-failed.json, exit before the analysis (no summary.json ->
   bench-fail.json); bench2-queue.sh stops with an alert after 3 such runs in a row; bench2.py moves a failed attempt's
   files to failed-attempt-<time>/ before a retry (they used to hide the new attempt's files). notyet-check.py: FAILED
   after > half of >= 3 searches fail, and refuses to start while 8889 is down.

10-21 23:2x-23:5x STAGE 1 FOLLOW-UPS 3-5 + STAGE 2 (the user):
3. Reruns: tools/p4-stage1-reruns.sh (started 23:27, pid 1271678; log logs/p4-stage1-reruns.log; Jan first, every
   service checked before each step): item 2 f (o03 deep medium + both report replays) and g (o01, o02, o07: false
   alarms) with 8889 up, label s1r- (stage 1's s1- files kept); setup checks o01 x3 and o07 run 1 under distinct names
   (o01-report.setupcheck-k.json). The setup check cannot lose its output to the cap any more: 60,000 tokens, and on
   finish=length or no JSON it runs again listing only contradicted / unsupported statements (mode "flagged-only";
   level-replay.py backup .before-flagged).
4. Item 1 -> stage 2: LDR_DEEP_SETUP_PROFILE=<user-setup.md> (new deep/setup.py, in patch 0001): the setup block in the
   lead's system prompt (patch 0002) and after </task> in the outline / section / opening prompts (as stage 1's "with"
   replays), and the setup check after the citation check as the safety net: each contradicted statement gets
   "**[Setup check: <fix>]**" after it (end of its sentence, before its citations) and a short "Setup check" section;
   nothing deleted or rewritten; setupcheck.json in the run folder. Effort = the citation check's.
5. Item 3: LDR_DEEP_CRITIC=1 (the stage 1 critic prompt) and LDR_DEEP_VERIFY2=flag (the stage 1 two-source method on
   the run's own evidence store) only add a "Check these" list (at most 8 lines, reasoning / disagreements first; the
   rest in advisory.json); the report text is never changed; both read the report as written (before the setup marks).
   Stub-model test on o02 p4base's evidence (scratchpad s2test/t.py): every new path runs, sections in place.
   Switches: run-ldr.sh writes run/ldr.items (setup / critic / verify2, or off; replaces run/ldr.setup); bench2.py
   --items must match it (every other run needs off); queue plan steps take "items"; the research runner restarts an
   LDR left with items on (the user's research gets none of them for now).
Stage 2: results/bench2/queue-plan-p4s2.json = o07, o02, o03 deep medium (citation check xhigh) with items 1 + 3, label
p4s2, against the p4base runs (same build, P021, so minutes compare too). deep-research-bench.service now runs that plan
(backup systemd/deep-research-bench.service.before-p4s2); tools/p4s2-start.sh starts it when the reruns end cleanly.
Item 2 waits for the reruns' result (its deep-run step is not written yet).

## 2026-10-22 07:2x - stage 1 reruns done, stage 2 two of three
Reruns (00:08, kcheck clean; files under distinct names): 2f EN 18286 caught in o03 report.md (3 outdated) and the
xhigh replay (4), missed in the medium replay (first 15 of 39 claims checked). 2g (should find nothing): o01 0, o02 1
(the report says a llama.cpp issue is "still open"; it was closed by the inactivity bot 08-27, bug not stated fixed: debatable), o07 2 (K2 Horizon released
09-03 and its model card's agentic rows: sourced, dated before the report, so wrong when written, not "not yet").
Setup check: o01 8 / 10 / 12 contradictions in 3 runs (of run 3's 12, 5 recur in all three runs and 5 in one other); o07 (medium report) 38 of 57,
nearly all real (5080 "24 GB", DDR5-4800, 21 GB files "fit" the 16 GB card, the 4060 Ti "contributes nothing").
Stage 2 (started 00:09): o07 201 min (p4base 167), o02 190 min (162). Report stage +36 / +27 min: setup check ~6 min,
critic ~3-4 min, verify2 ~22 min (7-8 calls at xhigh) - verify2 is most of the cost. Setup check in the p4s2 reports:
o07 3 contradictions (vs 38 in the medium report without the profile), o02 2. Check these: 8 lines each, mostly
real arithmetic / unit errors. Watch: o02 p4s2's outline call was the shortest seen (6.4K chars, 111 sources assigned vs
459 / 599 in p4base / medium) -> 88 distinct sources cited (vs 225 / 222); o07 normal (458 assigned, 182 cited). One run:
o03 decides whether it repeats. 4 relief restarts at 20 GB (2 per run; p4base ~1). Searches: 537, none failed.

## 2026-10-22 08:5x - the user's answers before gap 8
- Item 2 (tools/notyet-check.py, backup .before-statusfirst): up to --max-claims (15) are checked, status claims first:
  the report's own words (the quote) say "not yet", "not <one or two words> yet", "pending", "still open" or
  "unreleased"; then the rest in the find step's order. The find step's status line says "not yet" for nearly every
  claim, so it is not used. Each checked claim records found_index / status_first; the result keeps every found claim
  ("found"). Offline test (stub model): o03 medium's EN 18286 sentence ("its OJ citation remains pending") at index 30
  of 39 is picked. Not run on the model yet (no GPU during stage 2 / the gap).
- Verifier: unchanged during stage 2; after it, the critic / verifier split of the "Check these" lines. So far (o07,
  o02): all 8 shown lines are the critic's; the verifier's 10 / 7 flags (4 / 2 on claims the critic also raised) never
  reach the list (critic reasoning lines rank first, critic lines win ties).
- Relief restarts: the setup check, critic and verifier calls are already one-off (chat_cache owner+no-park+drop, as
  the citation check); all 6 stage 2 restarts came during the research phase (55-112 min into each run), none in the
  report stage. Nothing added. The dips look like p4base's (engine ~62.5 GB, ~12 GB parked); stage 2's o02 ran 24
  subagents (p4base 16); p4base o07 had 2 restarts too. LDR (up since 00:09) and SearXNG 8889 (since 23:18) grew over
  the night (1.4 -> 2.1 GB, 0.8 -> 1.3 GB at the dips; p4base's dips: 1.2-1.6 / 0.4-1.0) - about 1 GB of the margin.

* 2026-10-22 10:03 phase 4 gap BEGIN (gap 8: the P021 backport (draft rule + v2 kernels), its checks, the switch if they pass): queue held after its run, test lock taken, P021 on 8080 stopped.

## 2026-10-22 10:1x - stage 2 done (o03 10:01, 201 min); the verifier dropped from the default pipeline
Stage 2 vs p4base (both on P021): o07 201 / 167 min, o02 190 / 162, o03 200 / 162 = +100 min over three runs (+20 %).
Report stage per run: citation check (unchanged) 26-36 min; setup check ~6 min (10 s on o03: nothing about the user's
machine in it); critic 3-4 min; two-source verifier 22-24 min (7-9 calls at xhigh).
o03 (item 5 check): 275 distinct sources cited (p4base 198, medium 241), outline 604 sources assigned - o02's low
(88) did not repeat, so the profile in the outline prompt was not looked into. o03 setup check: no statements about
the user's machine (an EU AI Act question), no section.
Critic vs verifier ("Check these", 8 lines shown per report): all 24 shown lines came from the critic. The verifier's
flags: o07 10 (4 on claims the critic also raised), o02 7 (2), o03 4 (0) - 15 of its own over three runs, none shown
(critic "reasoning" lines rank first and fill the list; critic lines win ties). Its own flags are small date / number /
label mismatches (trilogue 6 vs 7 May, "point 43" vs 33, 427 B vs 428 B, slot width, used prices) plus one or two
substantive (a "no published fix" claim where sources give workarounds).
Decision (the user, 10-22: "my lean is to drop it ... if o03 also shows nothing unique reaching the list ... Your
proposal after stage 2 decides"): DROP the verifier from the default pipeline - stage 3's "with" side and later runs use
items setup + critic (LDR_DEEP_VERIFY2 stays off; the code stays for re-use). Saves 22-24 min per run (~11 % of
stage 2's wall time). A medium-effort dates-and-numbers version was not chosen: it would need reserved list places to
show anything, and its value is unmeasured.
Runs on which build: p4base, the stage 1 reruns and all of stage 2 ran on P021 (engine c9fe314316c4); gap 8 opened
10:03 and may switch 8080 to P021n.

## 2026-10-22 10:3x - stage 3 armed (the user: after gap 8, on whichever build is live; setup + check + critic)
results/bench2/queue-plan-p4s3.json = the screen set (o01-o03 + h02 h04 h05 h06 h08), deep medium, citation check
xhigh, label p4s3, items setup + critic (verifier off: dropped 10-22). deep-research-bench.service now runs that plan
(backups systemd/deep-research-bench.service.before-p4s3 and the installed copy). tools/p4s3-start.sh (pid 1826157,
log logs/p4-stage3-start.log) waits for gap 8 (strata-compare pid 1776002) and starts the service only when gap 8 ended
normally (no exactness stop, no kernel-check failure) and 8080 answers; it logs which build is live (P021n after a
switch, else P021). ~8.5 h + ~10 min per run for setup + critic. Comparisons with p4base by quality, calls and tokens
(minutes too only if 8080 stays on P021).
* 2026-10-22 13:24 phase 4 gap END: P021n (the switch) on 8080 (engine sha 68befe4e03bf), chat-cache parking policy on; queue resumes.

10-22 SWITCH 2026-10-22 13:24:10: 8080 runs P021n (the P021 backport: arm C + STRATA_PREFILL_V2=1 + STRATA_DEQUANT_WIDE=1; engine 68befe4e03bf; configs/P021n.json). Phase 4 runs from here are on P021n; earlier phase 4 runs (p4base, stage 1, stage 2) on P021 (c9fe314316c4). Rollback: STRATA_CONFIG=configs/P021.json (or switch-model.sh / run-strata.sh *.before-p021n and work/r22/port_gap4.sh.before-p021n). Checks: results/r22/gap8/summary.txt.

## 2026-10-23 07:1x - stage 3 done (queue finished 00:53:59; all on P021n, engine 68befe4e03bf)
| run | p4s3 (P021n, setup + critic) | p4base (P021, no items) |
|---|---|---|
| o01 | 174 min, 441 calls, 11.83M prompt / 1.29M generated | 170 min, 419 calls, 11.59M / 1.16M |
| o02 | 175 min, 599 calls, 14.27M / 1.23M, 2 failed calls (VRAM guard) | 162 min, 660 calls, 14.30M / 1.06M |
| o03 | 172 min, 704 calls, 15.05M / 1.13M | 162 min, 660 calls, 13.80M / 1.03M |
| hard five | 5 of 5 correct; 165 min, 160 calls, 2.72M / 1.31M | 5 of 5 correct; 146 min, 156 calls, 2.34M / 1.10M |
- Two VRAM guard stops in o02 (17:27:27 and 17:32:15, the 5080 under 300 MiB free for 60 s): the desktop's own VRAM
  use grew (the monitor is on the 5080). Each time one "compact" call failed and the client's retry finished it.
  Relief restarts (MemAvailable 20 GB): 17:20, 20:06, 20:46. Kernel log clean at the end.
- Minutes are not comparable with p4base (another build); by calls and tokens stage 3 is within -9 % to +9 % calls and
  +0 % to +9 % prompt tokens of p4base per open question; the quality of the open reports is for the checkpoint.

## 2026-10-23 07:5x - phase 4 checkpoint: open questions graded blind (results/bench2/blind-p4/SUMMARY.md)
With items (setup + critic) vs p4base: o01 8.5 vs 6.5 /10, o02 9.5 (p4s2 and p4s3) vs 5.5 /12, o03 11.5 all /12,
o07 10.0 (p4s2) vs 6.5 /14; verifier (p4s2) vs none (p4s3): level on o02 / o03. Hard five 5/5 both. Graders = fresh
subagents (stricter than my phase 3 grading: anchors 3-5 points lower), blinding partial (inline setup-check notes);
tools/blind-open.py takes BLIND_OUT / BLIND_DROP (backup .before-p4).

* 2026-10-23 07:46 phase 4 gap BEGIN (gap 9: pcie-frac on research-call replays, the IMMA retest (120 prompts), the continuation fix): queue held after its run, test lock taken, P021 on 8080 stopped.

* 2026-10-23 09:5x the user, after the phase 4 checkpoint grading: (1) keep the setup profile + setup check + critic
  as the DEFAULT for the user's own deep research - tools/research-runner.py run_ldr now starts LDR's deep profile with
  LDR_DEEP_SETUP_PROFILE=user-setup.md and LDR_DEEP_CRITIC=1 (no LDR_DEEP_VERIFY2; quick answers get none), and
  restarts LDR before a Jan job unless run/ldr.items = "setup critic" (deep) / "off" (quick); backup
  research-runner.py.before-items; deep-research-runner.service restarted 09:51 (idle, no job since the reboot).
  Measurement runs are unchanged: bench2-queue.sh sets its own items and bench2.py checks run/ldr.items.
  (2) Future blind grading strips the inline "**[Setup check: ...]**" notes: tools/blind-open.py clean() (backup
  .before-inline). Checked on the 14 phase 4 packets: the 12 notes in 4 reports are gone, every other character is
  the same as the graded packets. (3) The Saturday check is a cloud scheduled task from the user's chat (public sources
  only); nothing on this PC.
* 2026-10-23 10:25 phase 4 gap END: the served build (configs default, P021n since 10-22) back on 8080 (engine sha 68befe4e03bf), chat-cache parking policy on; queue resumes.

10-23 PCIE 2026-10-23 10:25:25: 8080 runs P021n without the forced --pcie-frac 0 (configs/P021n.json, backup .before-pcie; engine 68befe4e03bf unchanged). Checks: results/r22/gap9/summary.txt.

* 2026-10-23 10:36 phase 4 gap BEGIN (gap 10: the continuation fix's remaining checks, then the switch if they all pass): queue held after its run, test lock taken, P021 on 8080 stopped.

## 2026-10-23 10:4x - the user: item 2 bundled into item 4; early stop dropped from deep; item 4 next
- Plan (CHECKPOINT-phase3.md section 8 and PLAN.md, backups *.before-1023): item 2 ("not yet" check) gets no separate
  stage 2-3 runs - it runs inside item 4's ("tried / ruled out" list); early stop is DROPPED from deep research and
  parked as a quick-research idea only.
- Item 4 built (deep/tried.py, LDR_DEEP_TRIED=1): with files on the job, a list of what the user's project already
  tried / adopted / rejected / ruled out / planned is extracted once per file set (one medium call per ~60K-character
  part, then one merge call; JSON; fallback dedupe by name), cached by content in run/tried/<key>.json + .md (the .md
  is for the user to check; a copy goes into the run folder as tried-list.md). The lead's system prompt gets a
  <tried_list> block (<= 24K chars, rejected / ruled out first) after the setup block; the outline / section / opening
  prompts get it after </task> with a note to separate new from already tried. Built in-run only when not cached (that
  time is added back to the research deadline); tools/tried-list.py builds it before a measured run through 8090 so its
  calls stay out of the run's calls and tokens (calls logged in run/tried/<key>.calls.json).
- Item 2 in-run (deep/notyet.py, LDR_DEEP_NOTYET=1): tools/notyet-check.py's find / judge prompts and status-first pick
  (max 15, LDR_DEEP_NOTYET_MAX), after the setup check: each outdated statement gets " **[Fresh check <date>: update
  (source)]**" after it, and a "## Fresh check" section lists every checked claim with the check's date. Searches
  mostly failing (>= half of >= 3, or of all when fewer) -> no verdicts, says so. notyet.json in the run folder.
- Wiring: report.py (backup tmp/backup-2026-10-23/report.py.before-items24), langgraph_agent_strategy.py (same folder);
  run-ldr.sh items "tried" / "notyet"; bench2-queue.sh ITEMENV; patches regenerated (0001 + 0002; 0003 unchanged);
  blind-open.py also strips "**[Fresh check ...]**" (BLIND_DROP for the sections: "Setup check,Check these,Fresh check").
  Offline tests with a stub model: list built / cached / grouped, all three report prompts format with setup + tried,
  fresh check orders status claims first, marks the outdated EN 18286 sentence before its citation, stops on failing
  searches.
- Stage 2 = results/bench2/queue-plan-p4s4.json: o01 (item 4's test case) + o03 (item 2's), deep medium, citation check
  xhigh, items setup + critic + tried + notyet, label p4s4; the "without" side is stage 3 (p4s3, setup + critic).
  deep-research-bench.service now runs that plan (backups systemd/*.before-p4s4 and tmp/backup-2026-10-23/). Armed:
  tools/p4s4-start.sh (log logs/p4-stage4-start.log) waits for strata-compare's gap 10, builds o01's tried list, runs a
  smoke test of the in-run fresh check on stage 3's o03 report, then starts the service. ~6 h for the two runs.
* 2026-10-23 11:03 phase 4 gap END: the served build (configs default, P021n since 10-22) back on 8080 (engine sha 68befe4e03bf), chat-cache parking policy on; queue resumes.

* 2026-10-23 11:08 phase 4 gap BEGIN (the switch to P021m (the continuation fix), the user after gap 10): queue held after its run, test lock taken, P021 on 8080 stopped.

10-23 SWITCH 2026-10-23 11:08:54: 8080 runs P021m (P021n as served since gap 9, no forced --pcie-frac 0, + the answer_room continuation fix in its minimal form: branch r22-port021-cont2 = P021n + a653ae6c; engine 68befe4e03bf; configs/P021m.json). Phase 4 runs from here are on P021m (item 4 stage 2 onward); stage 3 and earlier ran on P021n / P021. Rollback: STRATA_CONFIG=configs/P021n.json (engine-r22p021n 68befe4e03bf; or switch-model.sh / run-strata.sh *.before-p021m). Checks: strata-compare results/r22/gap10/summary.txt (the tool-call rule re-judged: both builds 21 valid, 3 cut off at max_tokens, 0 malformed).
* 2026-10-23 11:08 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.
  (Correction 11:1x: the switch gap's first start at 11:08:13 was refused - strata-ensure saw the old server's guard process (pid 189131) still exiting a second after the stop - and work/r22/switch-gap10b.sh logged the switch anyway; port_gap4.sh end run again by hand started P021m at 11:08:54 (engine 7b38796237f5, pcie 0.55, 4,585 + 3,300 slots, policy on, hold released). 8080 was down ~11:07:40-11:08:54.)
* 2026-10-23 11:0x-11:1x item 4 tried list, first build stopped by hand: o01's files cut into 25 parts of ~22K tokens;
  part 1 (medium, uncapped list) ran into the 16K output cap (96 s, no list), and 25 uncapped lists would not fit one
  merge call. deep/tried.py reworked (backup tmp/backup-2026-10-23/tried.py.v1): at most 30 entries per part (names <= 8
  words, results <= 25 words), low effort, 32K cap; a dedupe by name; merge calls at medium in batches of <= 100K
  characters, then a final merge (<= 200 entries). Offline test: 22 parts -> 5 batches + final. Patches regenerated.
  tools/p4s4-start.sh restarted 11:09 (8080 = P021m): part 1 now 30 s, 4.4K tokens, finish stop.
* 2026-10-23 11:34 the tried list for o01's files: 354 entries (rejected 88, ruled out 37, inconclusive 56, adopted 141,
  planned 32) from 27 parts, 0 failed; 32 calls, 696K prompt / 223K generated tokens, 23.7 min (run/tried/
  2942694699ddeef7.*; the final merge kept 354 although asked for <= 200). Specific and sourced (e.g. "Eddoursul fork
  second-gpu Gen4x4 - 3x slower", "--remote-expert-opt #578 - all variants -17.9 %"). The smoke test then STOPPED the
  start correctly: all 3 of its searches failed - SearXNG 8889's log shows every engine timing out at 11:34 (google,
  bing, duckduckgo, wikipedia, ... at once: an outbound network stall); the same searches worked at 11:37.
  Prompt block reworked (backup tmp/backup-2026-10-23/tried.py.v2): the first form cut at 24K characters in status order
  and dropped most adopted and all planned entries - the ones that say what is NOT new. Now rejected / ruled out /
  inconclusive entries with results (shortened to fit), adopted and planned as compact name lists; o01's block 28.3K
  characters (~7K tokens) with all 354. Starter rerun 11:4x (list cached).

10-23 14:16 v0.2.3.1 (tagged 08:27) paused the p4s4 queue at its start (11:41:27, before o01) and ended the tag watch (08:27, not noticed until 14:14 - ~2.5 h lost). v0.2.3.1 = Control 0.1.48.1 / Terminal 0.2.3.1 setup hotfix (#3810: BUILD.json archs as a list or string, HIP arch names); src/ and serve/ unchanged vs v0.2.3, engine packages stay 0.1.48. Point-release rule: baselines raised to v0.2.3.1 (bench2-queue.sh newtag, strata-tagwatch.service KNOWN; backups *.before-tag0231), tag watch restarted, queue restarted 14:15: o01 p4s4 running on P021m (7b38796237f5) with LDR_DEEP_SETUP_PROFILE + CRITIC + TRIED + NOTYET; gap 11 waiter saw it (14:16). Starter smoke (11:41): fresh check on p4s3 o03 = 41 claims, 15 checked, 0 outdated, 14 still true, 1 unclear, EN 18286 not among the 15; 238 s.

10-23 14:30 Release pauses decide by what changed (the user, 10-23). New work/r22/tagcheck.sh, shared by the research queue (bench2-queue.sh newtag, before each question, ls-remote at most hourly) and the tag watch (work/r21/tagwatch.sh, hourly): one baseline file ~/ai/deep-research/run/strata-baseline-tag (v0.2.3.1; replaces the unit's KNOWN and the queue's hard-coded tag). A newer final tag with nothing changed on the engine/server path - src/ serve/ (the user's rule) plus include/ third_party/ (ggml) cmake/ and CMakeLists.txt apart from its project() version line - raises the baseline itself, logs it here and in tagwatch.log, and everything carries on. A tag that changes that path pauses the queue at its next clean point and ends the watch, each with a critical desktop alert (stays on screen until dismissed); after the review: work/r22/tagcheck.sh --accept <tag>, then start the queue / watch again. Tested on scratch copies: v0.2.3 -> v0.2.3.1 raised; v0.2.2 / v0.2.1.3 -> v0.2.3.1 paused (47 / 78 engine files); --accept refuses to go backwards. The running queue instance (o01/o03) keeps its old check (the script was replaced by rename, not edited); work/r22/p4s4-watch.sh replaces gap11-wait.sh (killed by PID): it restarts the queue if that old check pauses on a tag with no engine/server change (alert otherwise), and runs gap 11 only after "queue finished" (gap11-wait would have run it at any stop). Backups: bench2-queue.sh.before-tagcheck, tagwatch.sh.before-tagcheck, strata-tagwatch.service.before-tagcheck.

10-23 18:58 A 35 MB/s model download (DeepSeek-V4.1-Flash, ~249 GB, ~2 h, kept out of the page cache) runs during p4s4's o03 (started 17:07): its web searches share the line. If o03's search/fetch times look slow, this is why.

* 2026-10-23 20:04 phase 4 gap BEGIN (gap 11: the corrected tool-call check on P021m, for the record): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-23 20:08 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-23 21:52 phase 4 gap BEGIN (DS4.1 speed test (v0.2.4 stock, IQ2_XXS)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-23 21:56 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-23 21:57 phase 4 gap BEGIN (DS4.1 speed test (v0.2.4 stock, IQ2_XXS)): queue held after its run, test lock taken, P021 on 8080 stopped.

10-23 22:11 Strata release baseline v0.2.3.1 -> v0.2.4 after review (the user, 10-23: Qwen engine byte-identical to 0.2.3, only Control and the separate DeepSeek engine changed) (work/r22/tagcheck.sh --accept).
* 2026-10-23 22:20 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-23 22:21 phase 4 gap BEGIN (DS4.1 arms (RAM store 60 / 70 GB, DSpark on)): queue held after its run, test lock taken, P021 on 8080 stopped.

10-23 23:11 Strata v0.2.4.1 (found by the tag watch): nothing on the engine/server path changed since v0.2.4 (src/ serve/ include/ third_party/ cmake/, CMakeLists.txt apart from its version line; changed: tests (4), strata_cli (1), packaging (1), docs (1), CMakeLists.txt (1)). Baseline raised to v0.2.4.1 automatically; measurements carry on (work/r22/tagcheck.sh).
* 2026-10-23 23:38 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-23 23:40 phase 4 gap BEGIN (DS4.1 arms rerun (RAM store 70 GB, DSpark on)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-24 00:23 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

10-24 00:35 Phase 4 item 4 stage 2 graded blind (results/bench2/blind-p4s4/SUMMARY.md; tools/blind-open.py now turns the tried list's prompt tag "tried_list" into "project notes", backup tmp/backup-2026-10-23/blind-open.py.before-triedtag): o01 p4s4 8.5 / p4s3 7.5 / p4base 6.5 of 10 (checklist 1 "separates new from tried": 1.5 / 1.0 / 1.5 - p4s3's top "untried" idea was already tried); o03 11.5 / 11.0 / 10.5 of 12; the fresh check annotated Recital 40's "harmonised standards not yet available" with EN 18286:2026 in the OJ (minor: the sentence reports the recital; no report fell in the trap). Cost: o01 +8 % calls, prompt +4.4 %, generated level (+ tried list once, 32 calls); o03 +16 % calls, prompt +8.8 %, generated +12.6 %. Both checks pass -> stage 3 started 00:34 on P021m: queue-plan-p4s5.json (o02 + h02 h04 h05 h06 h08; setup + critic + tried + notyet; label p4s5; unit backups *.before-p4s5). o02 and the hard five have no files, so the tried list stays idle there (stage 3 tests the fresh check and that the tried item does no harm without files).

10-24 08:36 Strata release baseline v0.2.4.1 -> v0.2.4.2 after review (the user's review 10-24 08:36: only the DeepSeek engine (src/dsv41 IQ1_M CPU rows from one token, bit-identical), its BMI2-off build flag, two DeepSeek-only server defaults (slot keep, auto pin), installer/launcher/docs/tests; the Qwen engine and P021m untouched) (work/r22/tagcheck.sh --accept).

10-24 08:47 Release pause rule narrowed (the user, 10-24: "only pause for changes in the code our served Qwen build uses (the Qwen engine sources and the server paths P021m runs). DeepSeek-only changes (src/dsv41/, DeepSeek-only server defaults, its build flags), installer, launcher, docs and test changes: raise the baseline automatically, log it, and keep running"). New strata-compare work/r22/qwenpath.py, called by work/r22/tagcheck.sh (backup .before-qwenpath) when a newer tag exists. It works out the served build fresh each time from run-strata.sh's default config (P021m): engine = the files the build folder with the served engine's sha256 compiled (strata-r22p021m/build: ninja -t deps, -t inputs, compile_commands.json, what configure read) plus the vision binary's build (strata-r22p021/build-vision) - 759 files; CMake files count only where a changed line sits in a block our build configures (blocks under a false option of its CMakeCache, or under a DeepSeek switch such as STRATA_BUILD_DSV41, don't count; comments, the project() version line and DeepSeek option/set lines don't either); server = P021m's server.py and the 44 modules it imports (serve/, strata_control/, strata_cli/), compared definition by definition (docstrings, comments, version strings, DeepSeek-named definitions and ones our server lacks don't count), plus serve/chat_template.jinja. Pause -> as before (desktop alert, `tagcheck.sh --accept`); raise -> baseline raised and a NOTES line with what changed. qwenpath.py failing -> the 10-23 rule decides. Report per check: logs/r21/tagcheck-<base>-<tag>.json. Checked on past releases: v0.2.3.1, v0.2.4.1, v0.2.4.2 would raise; v0.2.2, v0.2.3, v0.2.4 pause (v0.2.4: the Qwen CPU expert kernels src/kernels/cpu/*, their AVX-512 build flags, serve/frontend.py effort and Service changes). Tested on scratch copies (raise, pause, fallback). Queue and tag-watch alert wording updated by rename (backups .before-qwenpath; the queue picks it up at its next start); tag watch restarted. Keep strata-r22p021m/build and strata-r22p021/build-vision while P021m is served: without them the check falls back to pausing on src/ include/ cmake/ third_party/.

10-24 13:20 Phase 4 plan (the user): a new item after the DeepSeek tuning round and the stage 3 grading - a read-only code tool for the research agent (shallow clone of a GitHub repo/tag into a capped scratch folder, deleted after the run; grep-style search with file:line, tree, line-range reads - search first, never whole files; GitHub issues/PRs/commit messages through the public API unauthenticated, never the user's gh login or a key; never build, run or install from a clone). Test: rerun the user's 10-24 DeepSeek speed-ideas question with it (does it find that the two-GPU split disables lm_begin()'s layer-major reuse and the yoco_layer() prompt mode?). Grading: an answer key from the findings Fable, Pro and Astra agreed on, each verified against Strata v0.2.4's source first; blind grade of the 10-24 report vs the rerun; every code reference in both reports checked against the repo at that tag (real vs made up). Stage 3: o02 graded (results/bench2/blind-p4s5/SUMMARY.md); h08 runs after the user's Jan research (hold file until it finishes), then the hard five are graded.

10-24 14:40 Phase 4 backlog from the user's DeepSeek LDR run (the user; after the DeepSeek round, each fix through the usual stages before adoption): code-reading tool (planned); engine/version check for every flag in an action plan ("other engine, unverified" otherwise); checker findings marked inline on the lines they concern (like the setup check); arithmetic in code (~250x off on Engram row counts); no citations to sources outside the evidence (a [0] reached the headline); gains against the user's measured baselines from the setup profile (it compared prompt speed to decode speed); enforce the time budget (5 h 06 m on 4 h). That run: started 09:19 (waited for h06), research done 13:38, report 13:50, finished 14:25.

* 2026-10-24 15:03 phase 4 gap BEGIN (DS4.1 tuning round (the user, 10-24)): queue held after its run, test lock taken, P021 on 8080 stopped.

* 2026-10-24 15:13 phase 4 gap BEGIN (DS4.1 tuning round (lock re-taken after a driver restart, 10-24 15:3x)): queue held after its run, test lock taken, P021 on 8080 stopped.

* 2026-10-24 15:13 phase 4 gap BEGIN (DS4.1 tuning round (lock in its own scope, 10-24)): queue held after its run, test lock taken, P021 on 8080 stopped.

## 2026-10-24 21:40 - Phase 4 item 4 closed: tried list + fresh check stay off
The user: keep the tried list (LDR_DEEP_TRIED) and the "not yet" fresh check (LDR_DEEP_NOTYET) off by default (stage 3:
o02 below p4s3, hard five level, +8-33 % calls). Checked: only tools/bench2-queue.sh sets them; run-ldr.sh defaults both to
0 and the Jan runner never sets them - Jan's deep research is setup + critic, unchanged. Next Phase 4 item: the read-only
code tool, after the DeepSeek round.

## 2026-10-24 21:58 - relief restart at 13 GB when DeepSeek is on 8080
The user: when DeepSeek is the model on 8080 the runner's relief restart fires below 13 GB free; Qwen keeps 20; the 12 GB
floor stays. tools/research-runner.py: MEM_RELIEF_DS_GB = 13.0, relief_gb() (8080's /v1/models id containing "deepseek",
asked at most once a minute, only on the job / measurement paths) in both relief checks. Backup
tools/research-runner.py.before-dsrelief. Runner restarted with no job active.
* 2026-10-26 06:07 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 06:44 phase 4 gap BEGIN (Maya head-to-head (the user, 10-25; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 08:03 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 08:15 phase 4 gap BEGIN (Maya head-to-head (the user, 10-25; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 08:18 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 08:24 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 09:31 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 09:35 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 10:04 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 10:14 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 11:59 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 12:05 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 13:47 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 13:48 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 13:49 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 13:50 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 13:59 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 14:01 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 14:10 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 14:15 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-26 20:30 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-26 20:31 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-27 01:33 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-27 01:34 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-27 01:46 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-27 01:47 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-27 02:02 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-27 02:03 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-27 02:06 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-27 02:10 phase 4 gap BEGIN (DeepSeek follow-ups (the user, 10-26; lock in its own scope)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-27 02:13 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

## 2026-10-27 07:00-07:45 - Phase 4: the read-only code tool built (LDR_DEEP_CODE=1); test started
Karl (10-27): start building the code tool now (code only, 8080 up; GPU only for the test run); a blind grader may read his
10-24 DeepSeek-tuning LDR report, for this test only.
- deep/codetool.py (new; in 0001-deep-package.patch, regenerated): five agent tools - code_search (grep -rnIH over a shallow
  clone, up to 40 file:line hits + the total), code_read (<= 120 numbered lines; a citable source [N] with the GitHub
  blob#Lx-Ly link, its text in the evidence store so the citation check works), code_tree (layout, or files by name),
  github_issues (search, or one issue / PR with its first comments as a source), github_commits (messages on a ref /
  path, as a source). Clones: git clone --depth 1 --single-branch --no-tags --no-recurse-submodules, HOME/XDG in the
  scratch folder, GIT_CONFIG_GLOBAL=/dev/null, no system config, credential.helper empty, hooks /dev/null,
  core.symlinks=false, https only, LFS smudge off; size watched during the clone (cap LDR_DEEP_CODE_MAX_MB, 400 MB) and
  timed out at 300 s; repo / ref names validated; every path resolved inside the clone (.git hidden, binaries and files
  over 2 MB refused). API: urllib, no Authorization header, no proxy, answers cached per run, stops before the
  unauthenticated limit. Scratch $TMPDIR/code-tool/<research id>, deleted when the research ends (strategy, after the
  report); leftovers older than 12 h swept at the next start. Every call logged to the research folder's code-tool.jsonl.
- Strategy (0002, regenerated): the tools join deep_extra_tools (lead + subagents) when LDR_DEEP_CODE=1, a short CODE TOOL
  note in the lead's prompt, close after the report. run-ldr.sh: item "code"; bench2-queue.sh: items "code". Backups:
  tmp/backup-2026-10-27/ (*.before-code), patches/ldr/*.before-code. The Jan runner is unchanged (deep jobs still need
  exactly setup + critic: the code tool is not in Jan's default).
- Tests: 27 offline checks of the core (escapes, symlinks, binaries, caps, name parsing) and 23 end-to-end checks with
  LDR's own collector and evidence store against github.com/Niko1221/Strata at v0.2.4 (clone 2.3 s, 107 MB; lm_begin found
  at src/dsv41/ds4_model.cu:7791; citable read stored; clone deleted at close) - all pass.
- Answer key (results/bench2/codetool/answer-key.md): the 7 agreed findings checked against the v0.2.4 source - 6
  confirmed, DS4_AHEAD partly (off by default with the store, an explicit DS4_AHEAD=1 still honoured).
- tools/coderefs-check.py (grading step 3): every flag / variable / function / file reference in a report looked up in
  the v0.2.4 checkout - in the DeepSeek engine (src/dsv41), elsewhere in Strata, docs only, or missing. The 10-24
  report: 43 flags (3 in the DeepSeek engine, 19 only elsewhere in Strata, 1 docs, 20 not in Strata), 18 variables (2 /
  14 / 0 / 2).
- tools/codetool-test.py: the rerun on the 10-24 job's pipeline (deep; setup + critic + code; S2 on; agent / extract /
  report medium, verify xhigh; 240 min; paid fallback off) under run/bench.lock; smoke first (unit ldr-codetool-smoke,
  07:26, 8 min budget).
- 07:26-07:58 smoke (results/bench2/codetool/run-smoke; 8 min budget, 32 min wall, exit 0, kernel clean): the agents made
  ~40 tool calls (clone 2.0 s / 107 MB, grep lm_begin -> reads of ds4_model.cu around 7740-7859, issue #3976 opened via
  the API) and the answer is right: lm_begin is off on two GPUs, guard quoted from src/dsv41/ds4_model.cu:7793 and cited
  with blob#L links (answer key K1). Citation check: 41 supported / 54 partial / 1 unsupported - the partials are broad
  negative claims ("no flag can bypass it") that a cited excerpt cannot prove, i.e. the check working. Clone folder
  deleted at the end. One bug: a read with end_line before start_line (8060-1990) returned no lines -> fixed (full
  window; start past the end is refused with the line count); backup tmp/backup-2026-10-27/codetool.py.before-rangefix;
  0001 regenerated; e2e checks pass again.
- 08:00 full rerun started (unit ldr-codetool-full; the 10-24 question from its job file, 240 min budget; expected end
  ~13:30). Jan deep jobs wait while it holds run/bench.lock.

10-27 08:22 Strata release baseline v0.2.4.2 -> v0.2.5 after review (the user 10-25 10:35: no pause needed - new AVX-512 gather rows default off on AMD, exact by construction; a --spec-split comment; re-armed 10-27 after the watch was left stopped) (work/r22/tagcheck.sh --accept).

10-27 08:50 Strata release baseline v0.2.5 -> v0.2.6 after review (the user 10-27: accept; on our path only a generate.cpp comment (--spec-split) and two small server fixes (no tok/s for a one-token reply, empty messages -> 400)) (work/r22/tagcheck.sh --accept).

## 2026-10-27 ~08:50 - Karl's decisions on the backlog (results: strata-compare/results/BACKLOG-1027.md)
- The six fixes come after the code-tool grading. Fix 1 (engine/version check): yes, reuse his 10-24 report as the test
  case. Fix 5 (gains vs measured baselines): add DeepSeek's measured numbers to user-setup.md myself, from the round
  report, marked as measured with the date - AFTER the code-tool rerun ends (the running rerun's report stage reads the
  setup profile; editing it now would change the test). Fix 6: the budget covers the WHOLE run (wall clock, writing and
  checks included) - the report must be out by the budget; reserve the report stage's time from the start. Testing
  bundled: replays per fix, then one combined full rerun and one stage 3.
- Phase 5 holdout after the final setup is chosen, as planned. Build items 5-8 and the long-context question: decided
  after this week; they stay in the backlog.
- 10-27 ~09:10 Karl: Phase 5 holdout runs on Flash-Next once the code tool and the six fixes are settled; when Qwen4
  Flash comes out (probably after Thursday's news), a shorter re-check on it instead of a full holdout.

10-27 11:04 Strata release baseline v0.2.6 -> v0.2.7 after review (the user 10-27: treat v0.2.7 as reviewed, nothing urgent; port target is now v0.2.7 (after the LDR week, repeat-run gate first); new lossy defaults (int8 prompt attention, route prior) to be pinned off in the port) (work/r22/tagcheck.sh --accept).

## 10-27 13:20 Code-tool test graded (results/bench2/codetool/SUMMARY-1027.md)
- Rerun of the 10-24 DeepSeek-tuning question with LDR_DEEP_CODE=1 (deep; setup + critic + code): 08:00-12:51, 291 min
  vs the 240-min budget (Fix 6), rc 0, kernel check clean. Code tool: 508 calls, ~97 s, 0 errors, 18 shallow clones
  (1.68 GB, deleted after the report), 167 code sources; GitHub's unauthenticated API down to 6 of 60 an hour.
- One fresh grader, blind, three stages (overall; then the answer key; then the references outside the DeepSeek engine);
  key revealed after: A = rerun, B = 10-24. Overall 3.75 vs 3.5 /10; key K1-K7 4.0 vs -2.0 /7; names wrongly presented
  as this engine's 6 vs 30. coderefs-check: engine env vars 11 vs 2, engine flags 12 vs 3.
- The rerun still misread the baseline (its headline wins are already set), mixed versions (--experts 6 from main-branch
  docs; not in v0.2.4) and contradicted itself between sections (K1, K4). Inputs for Fix 1 (pin code claims to the
  question's tag), the setup check (already-set values are not wins) and a consistency pass.
- After the rerun: tmp/ and cache/ deletions done (11.2 GB; the six sxng_cache files kept - open by
  searxng-ldr-baseline). cache/ held only third-party library caches (no Playwright browsers were ever installed); LDR
  starts clean (UI HTTP 200); the caches refill on first use - watch the first replay for download errors.

## 10-27 ~17:00 The six fixes + the consistency pass: built, replayed, smoke-tested (results/bench2/fixes/REPLAYS-1027.md)
- Code: deep/checks.py (new) + report.py / setup.py / advisory.py / codetool.py / llm.py / the strategy; all behind
  LDR_DEEP_FIX (all, or version,inline,arith,cite,baseline,budget,consist); run-ldr.sh writes the item "fixes" (or
  "fix:<list>"); bench2-queue.sh item "fixes" -> LDR_DEEP_FIX=all; codetool-test.py --fixes. Without the variable a run
  is unchanged (Jan unchanged). Backups tmp/backup-2026-10-27/*.before-fixes / -round2 / -round3; patches regenerated
  (0001-0003, *.before-fixes).
- Fix 1 version (+ the code tool pinned to the question's version, OTHER VERSION labels, GitHub API spared: git for
  default branch + commit lists, per-run caps, core vs search limits tracked apart); Fix 2 inline marks (critic + noted
  citation flags; blind-open.py strips all marks); Fix 3 arithmetic in code (written-out equations with no model + the
  model's list of other calculations; `calculate` tool for the agents); Fix 4 citations outside the evidence; Fix 5 the
  setup check judges recommendations ("already set") and gains (like with like), the task's own setup first; Fix 6 the
  budget covers the whole run (report reserve 25 %, 10-75 min; wrap-up 8 min; the report stage plans its checks by
  priority and length, caps outputs near the deadline, keeps the complete items of a cut JSON reply); the consistency
  pass. Karl's effort-drop logging: deep/llm.py logs "EFFORT LOWERED" and counts it in stats.json / summary.json.
- Replays (4 rounds on the rerun report, Karl's 10-24 report for Fix 1, a planted-error copy for Fix 3): see
  REPLAYS-1027.md. Fix 4 offline over 44 saved reports: 1 real case. Kernel checks clean after every round.
- Smoke with all fixes (8-min budget, the whole run): 1st 5.0 min (the plan skipped every check - estimates sized for
  45K-token reports), 2nd 6.0 min (citation check 9 claims, critic 4 marks from a cut reply). Then: estimates scale with
  the report's length, the citation check's reserve is at most 1/5 of what is left, the outline not counted twice.
- Next (Karl's bundled testing): the combined full rerun (10-24 question, code + all fixes; run-full-fixes) and then
  stage 3 (queue-plan-p4s6.json: o01-o03 + the hard five, setup + critic + code + fixes, label p4s6; vs p4s3), chained
  by results/bench2/fixes/chain-full-then-s3.sh (stage 3 starts only after a clean rerun).

10-27 20:28 STAGE 3 p4s6 BUDGETS MATCHED TO p4s3 (the user's OK): under Fix 6 the bench budget (--budget-s) is the whole
run, so bench2's 120 / 30 min would leave ~82 / ~17 min of research (p4s3: 120 / 30 min of research, the report after).
A plan step may now carry "open_min" / "checkable_min" (tools/bench2.py cmd_run; backup bench2.py.before-p4s6budget);
queue-plan-p4s6.json sets 171 / 47 (backup .before-budget): research ~120 / ~31 min, every run still has to end by its
budget. Stage 3 then ends ~09:00-09:30 10-28. The combined rerun (240 min whole run) could not be changed: its research
was ~172 min vs run-full's ~240 + report - say so in its grading.

10-28 05:31 Strata release baseline v0.2.7 -> v0.2.7.1 after review (Claude's review 10-28 05:3x under Karl's 10-27 rule (pause only for Jan jobs or Karl): every change on the Qwen path is DGX Spark / Metal only - an sm_121 (cc 12.1) defaults table and fused-prompt tile rule, linux-aarch64 in targets.py, a Metal-only ggml table guard, arm64-only CMake branches, a version bump and a test target; our cards are cc 12.0 + 8.9, so nothing changes for P021m or the v0.2.7 port's pins; Karl to confirm) (work/r22/tagcheck.sh --accept).

* 2026-10-28 08:45 phase 4 gap BEGIN (gap 12: the v0.2.7 port's first build, repeat-run gate, lossless, KL and speed screen): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-28 10:51 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-29 12:38 phase 4 gap BEGIN (gap 13: the hand-ported v0.2.7 port's gates (build, tests, repeat, lossless, KL, speed, distribution)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-29 14:27 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

10-29 19:17 Strata release baseline v0.2.7.1 -> v0.2.8 after review (Karl 10-29: new baseline (the server's tool-call fixes); the port's next target) (work/r22/tagcheck.sh --accept).

* 2026-10-29 20:30 phase 4 gap BEGIN (gap 14: the per-switch check of the hand-ported port (KL + distribution check 2 without PREFILL_V2 / GR_FORK / both)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-29 23:26 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-30 07:53 phase 4 gap BEGIN (gap 15: the v0.2.8 port's gates (build, tests, repeat, lossless, KL, speed, distribution, tool-call recovery)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-30 09:53 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-30 09:54 phase 4 gap BEGIN (Basalt PR #90 check: Basalt's community-1 prompts on P021m and the v0.2.8 port (cold + warm)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-10-30 10:27 phase 4 gap END: the served build (configs default, P021m since 10-23) back on 8080 (engine sha 7b38796237f5), chat-cache parking policy on; queue resumes.

* 2026-10-30 11:48 phase 4 gap BEGIN (gap 16: both switches back on the v0.2.8 port (exact v2, GR_FORK; Karl's conditions 1-5)): queue held after its run, test lock taken, P021 on 8080 stopped.

2026-10-30 16:55:54 SWITCH (Karl 10-30, gap 16 rule): 8080 runs P028x = the v0.2.8 port (branch r22-port028x = v0.2.8 + 28: GR_FORK and PREFILL_V2 back, v2 bit-identical; 0.2.7 defaults pinned off, conversation cache off, tool_call_recovery false; engine f4c4f654fb24 [corrected 10-30: the script logged 7b38796237f5, an older log line read before the new one landed; /proc/PID/exe of the 8080 engine = f4c4f654fb24]; configs/P028x.json). Rollback: STRATA_CONFIG=configs/P021m.json (engine-r22p021m 7b38796237f5; or switch-model.sh / run-strata.sh / work/r22/port_gap4.sh *.before-p028x). Checks: strata-compare results/r22/gap16/ (summary.txt, decision.txt).
* 2026-10-30 16:57 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

2026-10-30 17:16 p4s8 STARTED (Karl 10-30: item 7 baseline, option 1 - a new stage 3 baseline on P028x, then item 7's parts on P028x): queue-plan-p4s8.json = queue-plan-p4s7.json with the label p4s8 (o01-o03 + the hard five, items setup critic code fixes read claims); 8080 = P028x (engine f4c4f654fb24). Differs from p4s7 (P021m, 10-28 19:44 - 10-29 07:47) by the engine and by the 10-29 07:48 install (codetool.py + report.py version labels on repo pages). No paid search (bench runs unset LDR_SEARCH_FALLBACK). Unit backup deep-research-bench.service.before-p4s8. Next behind it: the item 7 install (c3 -> runner-bench -> item7, routing and cache off) and the item 7 parts.

10-31 09:56 Strata release baseline v0.2.8 -> v0.2.9 after review (Karl 10-31: accepted for now, served build stays P028x; port later as gap 17 after item 7's parts) (work/r22/tagcheck.sh --accept).

10-31 10:08 RELEASE RULE CHANGED (Karl 10-31): "A new Strata release doesn't pause work on the served build. Keep the queue running, review the release read-only in parallel, and flag it for my decision. Only installing or switching engines waits for me." work/r22/tagcheck.sh now answers FLAG instead of PAUSE (alert + NOTES line once per tag, run/strata-flagged-tag); the queue ignores FLAG and carries on, work/r21/tagwatch.sh logs FLAGGED and keeps watching (*.before-flag; unit strata-tagwatch.service Description, .before-flag). The tag watch had been stopped since v0.2.8's alert on 10-29 17:31 and was not started again after that accept; running again since 10-31 09:59. v0.2.9 (paused p4s8 03:10-09:56) accepted for now; port later as gap 17 after item 7's parts, gating and pricing its two new GDN prompt defaults (GDN_TC, GDN_CONVL2=2) on the 16K/64K cold prompts.

10-31 10:08 DST 11-01 (Karl: check the run budget and timers): audited read-only. Budgets, deadlines and watchers use epoch/monotonic time or sleep (bench2.py wall/held, ldr-client --max-minutes, LDR deep budget clock, runner, proxy, tagcheck, idle stop, guard); night gates are lifted (run/night-ok, night_pause off); no timer in 01:00-02:59. One fix: bench.json "ended" was naive local time, which run_work.py / wait_table.py turn into an epoch - an end in the repeated hour would shift that run's call window 1 h. Staged runner-bench/tools/bench2.py and bench2-merged/bench2.py now write it with its UTC offset (*.before-dst); runner-bench tests rerun 62/44/47 pass. Installed with item 7 by tools/item7-start.sh. p4s8 ends before the change and keeps the old form.

10-31 10:08 p4s8 resumed at h05 09:56 (5/8 done before the v0.2.9 pause). Item 7 install prepared: lineage c3 (install.sh --diff installable), runner-bench (.c3 = c3's staged, .orig = live), item7 hook (only patch 0005's block differs; sha recorded); tests c3 equivalence 84/84, runner-bench 62/44/47 + item7 suites + dry check, item7 suites all pass. tools/item7-start.sh runs as transient user unit item7-start.service (started 10:07, C3_TESTED=1): waits for 'queue finished (queue-plan-p4s8.json)', kcheck, all checks before any copy, waits out Jan jobs, stops runner + LDR, installs c3 -> runner-bench (bench2.py from runner-bench; bench2-merged at Phase 5) -> item7 (routing/cache off; patches/ldr/0005 regenerated), paid_tracker to results/bench2/item7/, starts runner, switches deep-research-bench.service to results/bench2/queue-plan-item7.json (p7b -> p7c -> p7a, 8 questions each, paid_route 7b/7c/7a, cache off). Log logs/item7-start.log.

10-31 11:5x DECISIONS (Karl 10-31, recorded after the suspend): (1) after setting up any waiter or queue step, confirm it is actually running (unit active, pid, its first log line) and say so in the report. (2) The NLL many-positions scoring gap runs after item 7's parts, on a free night; tell Karl before it starts. (Already recorded 10:08: the release rule - flag, never pause; v0.2.9 accepted for later as gap 17 after item 7's parts, gating and pricing its GDN_TC / GDN_CONVL2 default prompt paths on the 16K/64K cold prompts; the DST audit for 11-01 in deep-research NOTES.md.)

10-31 11:5x SUSPEND, not a power loss (uptime 8 days): the power key suspended the PC at 11:40:40. nvidia-suspend failed to save VRAM (NVRM NV_ERR_NO_MEMORY, 11:40:44) -> kwatch stopped the P028x engine and exited (flag tmp/r19/KERNEL_ERROR); the first suspend aborted (the dying engine would not freeze), the second held 11:41:21-11:45:39. After the resume the iGPU display driver logged flip_done timeouts and two WARNING splats (amdgpu_dm.c:10218 / 9595, 11:46:07 and 11:46:38): taint now 4608 (O + W), until a reboot. No Xid, MCE, oops, filesystem, NVMe or I/O errors. The on-demand launcher started a fresh P028x (f4c4f654fb24) at 11:47:01. p4s8 h08 (started 11:21:14) was cut off and then continued on the new engine - spliced: stopped 11:51 (client + bench2 by PID, LDR stopped), rerun from its start (bench2.py moves the old files to h08/failed-attempt-*). o01-o03, h02, h04-h06 intact. kwatch.sh now also matches the 7.0 kernel WARN splat ("WARNING: <file>:<line> at", "[ cut here ]"; *.before-warnfmt; tested on this boot: only today's 8 splat lines added) and was restarted 11:55:52. kcheck still fails (KERNEL_ERROR flag + W taint): item7-start's pre-install check will refuse until Karl decides (archive the flag + acknowledge W for this boot, or reboot).

10-31 12:0x KARL'S DECISIONS on the kernel gate: (1) "Reboot after h08" - a reboot clears the W taint (no boot-scoped acknowledgement in kcheck). (2) After the reboot, archive kwatch's flag: tmp/r19/KERNEL_ERROR -> KERNEL_ERROR.2026-10-31T1140-explained-suspend-vram-save (as on 10-18 / 10-25). item7-start.service stopped 12:04:15 before its kcheck (nothing installed; logs/item7-start.log). Waiter for h08's end running since 12:05:53 (Claude's background task). When h08 ends: check it, run-ldr.sh stop, 8080 stop (run-strata.sh stop), then Karl reboots.
POST-REBOOT STEPS: (a) new boot's kernel log: no MCE / Xid / oops / WARN splat, /proc/sys/kernel/tainted = 4096; (b) kwatch, ram-dip, strata-tagwatch, deep-research-runner, strata-idle-stop, searxng-* active (all enabled; they start at login); (c) archive the flag (Karl OK 10-31), then bringup/lib/kcheck.sh -> ok; (d) deep-research-bench starts at login on the p4s8 plan, finds everything done and exits ("queue finished (queue-plan-p4s8.json)") - confirm inactive; (e) relaunch the install chain: systemd-run --user --unit=item7-start --description="item 7 install chain" --setenv=C3_TESTED=1 /bin/bash /home/USER/ai/deep-research/tools/item7-start.sh (it finds the p4s8 line at once: checks, c3 -> runner-bench -> item7, runner back, bench unit on queue-plan-item7.json); (f) confirm item7-start active, then "p7b / o01: running" in logs/bench2-queue.log, run/ldr.fallback, 8080 = P028x f4c4f654fb24 with its guard; report to Karl.

10-31 12:3x p4s8 END: h08 rerun rc 0 (12:01-12:32, 32 min; the spliced first attempt kept in h08/failed-attempt-1031-120106); all 8 questions done, queue finished 12:32:56. Kernel log quiet since 11:46:38 (taint still 4608 from the resume), kwatch active. LDR + proxy and 8080 stopped cleanly 12:3x for Karl's reboot; GPUs empty. Next: the POST-REBOOT STEPS above.

10-31 12:52 Item 7 INSTALLED: c3 (*.before-c3) and runner-bench (*.before-runnerbench; bench2.py from staging/runner-bench, bench2-merged waits for Phase 5) by tools/item7-start.sh at 12:49:29 after the reboot; it stopped at its own mp-check call (no --want; files fine), and tools/item7-resume.sh checked that state and installed item7 (*.before-item7; routing and cache off; patches/ldr/0005 regenerated). Queue on queue-plan-item7.json: p7b (Tavily) -> p7c (Exa) -> p7a (S2), each o01-o03 + h02 h04 h05 h06 h08 against p4s8. Log logs/item7-start.log.

10-31 19:43 PAID CAP BREACH (my bug): p7b o03 (started 18:30:54) sent 60 Tavily searches against the test cap of 30 - 30 in October, then tools/paid_budget.py's _runs_update() cleared the per-run counts at the UTC month change (19:00 local) and o03 got 30 more. It is at 30 again for 2026-11, so further sends are refused; month totals fine (Tavily Oct 122/1000, Nov 30/1000). Also paid_tracker.py --month files log 't' (local time) by local date: Oct shows o03 60, Nov 0 from logs. o03 left running (stopping saves nothing now); its result is not comparable with o01/o02 (30 each). Asked Karl: rerun o03 after p7b's hard five or keep it flagged; fix = run counts survive the month change, installed only with no LDR run live. Next month change 12-01, after item 7.

10-31 22:12 o03 RERUN SET UP (Karl 10-31: option 1; delete nothing; paid_budget/paid_tracker fix after item 7's parts). o03's attempt ended 21:24 (rc 0) before the decision, so: (1) results/bench2/queue-plan-item7.json (backup .before-o03rerun): step 1 is now p7b o01 o02 only, and a copy of step 1 with ids [o03] sits after p7b's hard five, so the queue runs h04 (live) h05 h06 h08 -> o03 -> p7c (bench2.py next --wide checked: h04). (2) The attempt's 14 files are in runs/screen-deep-p7b/o03/failed-attempt-1031-220945/ with MOVED-ASIDE.txt. (3) ~/.config/deep-research/paid-runs.json (backup .before-o03rerun, under paid-runs.lock): the attempt's November count 30 renamed to "screen-deep-p7b/o03@failed-attempt-1031-220945", so the rerun (same run id) gets its own 30 - without it the rerun would have had 0 Tavily searches. The rerun starts ~01:00 and crosses the 02:00 clock change.
10-31 22:12 7b CAP REFUSAL = SearXNG ONLY, not nothing: the hook (patch 0005 item 7) always takes SearXNG's results first; route 7b then asks Tavily on every search and adds only new URLs; a refused search adds nothing and SearXNG's results stand, i.e. exactly p4s8's search. paid-route.jsonl per question (searches / Tavily sent / refused; SearXNG results on refused searches): o01 190/30/160 (7,497; 0 empty), o02 201/30/171 (8,094; 0 empty), o03 attempt 1 232/60/172 (8,174; 4 searches empty on SearXNG too), h02 3/3/0, h04 (part) 4/4/0. First come, first served: on the open questions only the first ~15 % of searches reached Tavily. For the 7b report: wanted vs made per question, and a null result at cap 30 says little about Karl's research cap of 100.
10-31 22:12 7d DESIGN NOTE (Karl 10-31; 7b/7c unchanged): consider spending the paid searches on the specific follow-up queries instead of first come, first served (the open questions' first ~30 searches are the broad opening ones).
10-31 22:12 DST AUDIT, second pass (Karl: confirm; check for paid_tracker's kind of mistake). Confirmed: research budgets and deadlines are epoch or monotonic (deep/control.py clock() = time.time() - pauses, mono() = time.monotonic(); ldr-client.py and bench2.py wall/held time.time(); the guard, proxy and runner as at 10:08); waiters/timers: only launchpadlib-cache-clean (11:51) and suite-opus45-hard (11-02..24 09:00) - none in 01:00-02:59; the night gates are lifted (run/night-ok), and bench2.py's naive night_cut() returns now + 7 days with it. NOT UTC: most logs are stamped in naive local time (bench2-queue.log, item7-start.log, research-runner.log, the 't' of tavily-/exa-fallback.jsonl and paid-route.jsonl), so 01:00-01:59 on 11-01 appears twice; kwatch/kcheck use date -Is (offset). Same kind of mistake as paid_tracker (parsing those stamps): paid_tracker.py:89 (exa/tavily rows by local t[:7]; :111 uses the route log's UTC "month" first - fine); the waiters item7-start.sh:145, item7-resume.sh:116, p4-stage1.sh:56 (awk local-time string compare on the queue log; all finished, none running). ram_dip.py:191 only copies the last "running" line as text. run_work.py / wait_table.py read bench.json "ended", fixed 10:08 (UTC offset; live in bench2.py). Fix with the paid_budget one after item 7: the fallback logs write 't' with its UTC offset plus a UTC "month"; paid_tracker uses "month", else converts t; future waiters key on file state or a line offset, not on log time strings. The p7b report is unaffected (o03's attempts split by run id and date).

11-01 10:11 p7b DONE 02:47 (o03 rerun 00:54-02:47 rc 0, 173 min wall, 4 held; o01/o02 + hard five rc 0). Hard five (bench2.py grade, answer key): p7b 5/5 (mean 42 min), p4s8 5/5 (40 min) - a tie at the ceiling; grades-hard-screen-deep-p4s8.json / -p7b.json written. Searches wanted / Tavily sent / refused (first refusal at search #): o01 190/30/160 (#31), o02 201/30/171 (#31), o03 rerun 202/30/172 (#30), h02 3/3/0, h04 4/4/0, h05 17/17/0, h06 3/3/0, h08 5/5/0; Tavily added 187 / 209 / 247 new URLs on the open questions; no refused search was empty on SearXNG except 4 in o03's discarded attempt. Open questions still to judge (blind, p4s8 vs p7b; method question to Karl). MEMORY: the runner's relief restarts of 8080 (MemAvailable < 20 GB) were 1-7 a day 10-28..10-31, 14 on 11-01 by 10:10; ldr-web RSS grew 301 MiB (10-31 12:52) -> 4.7 GB, so the engine's chat-cache headroom shrinks and restarts come faster (o02 of p7c held 10 min). LDR is not restarted between item 7 questions (same stamp). Proposed to Karl: stop LDR at a question boundary so the queue starts it fresh.

11-01 11:27 TEST CONDITION (Karl 11-01): a fresh LDR before every bench question, same settings, from p7c h02 on (p4s8, p7b and p7c o01-o03 ran on one long-lived LDR each part). tools/bench2-queue.sh (backup .before-freshldr): when ldr_restart_why finds every stamp fits, WHY="a fresh LDR for every question", so the usual stop + start path runs (proxy too) - logged per question as "LDR -> ... (a fresh LDR for every question)". Installed 11:26 by new file + mv; the hold placed 11:25 stops the queue after p7c o03, and unit freshldr-switch (tools/freshldr-switch.sh, log logs/freshldr-switch.log) restarts the bench unit once there (KillMode=process: LDR and 8080 untouched), then releases the hold and checks the first fresh-LDR line. Backlog C5 (strata-compare results/BACKLOG-1027.md, backup .before-c5): ldr-web growth 0.3 -> 4.7 GB a day as a likely leak; Karl's Jan research hits it too. GRADING (Karl 11-01): item 7's parts and the p4s8 baseline graded blind as p4s4-p4s7 / item 8 (one fresh Claude grader per question against my-research/ checklists; the suite's no-model-grading rule is for the frontier comparison only, both arms here are the same Qwen build); blind pages to Karl only for answers the checklists can't decide; each question's memory-relief restart count beside its grade, pairs with many more restarts on one side flagged.

11-01 11:33 FRESH LDR LIVE: p7c o03 ended 11:29 (rc 0, 171 min, 4 held); freshldr-switch restarted the bench unit at the hold (new queue pid 1088486, 11:29:37), released it, and p7c h02 started 11:30:10 on a fresh LDR (pid 1088793, 11:30:09, RSS 590 MB; stamps deep / medium-xhigh / setup critic code fixes read claims / fallback on / s2 off / flash-next 28732eeb029b - unchanged). Old LDR 8220 (4.7 GB) gone. Hold file renamed *.released-*-freshldr. Relief restarts per question: tools/relief_counts.py LABEL... (p4s8 o01-o03 1/0/1, p7b 0/2/4 - o03 flagged; hard five 0; p7c o01/o02 3/4). TO-RATE (Karl 11-01): ~/Desktop/To-rate/ (Karl's OK to write there only) holds links to the four frontier suite pages + README.txt (pages, 1-5 guide, saving: Copy my picks -> To-rate/ratings/<page>.json or chat -> suite/run.sh ratings import, then the page moves to To-rate/done/); new blind pages that need Karl (item 7's undecided points) go there too, with a message to Karl.

11-01 11:36 7b GRADED BLIND (results/bench2/blind-p7b/SUMMARY.md): open total p4s8 27.5 / p7b 30.0 of 34 (o01 9.0 / 8.0, o02 7.5 / 10.5, o03 11.0 / 11.5), wrong claims 19 / 15 (o01 p4s8 +1: the expert count settled from the served pack, 24,576), relief restarts 2 / 6 (o03 1 / 4 flagged - against p7b, which still won it); hard five 5/5 both. Six undecided points -> Karl's page ~/Desktop/To-rate/blind-item7-7b-undecided.html (tools/undecided-page.py; settled.json leaves out o01#2). Reading: a gain for 7b, carried by o02 (+3); not adopted or dropped before Karl's picks; 7c and 7a run on.

11-01 12:16 7b VERDICT: a gain on the blind graders' scores (blind-p7b/SUMMARY.md); Karl did not rate the six undecided points (he can't tell right from wrong on them), page removed from the desktop (results/bench2/blind-p7b/undecided-page-not-rated.html). From 7c on: no undecided pages; ask Karl a plain question in chat only if a part's verdict depends on his preference.

11-01 14:58 7c GRADED BLIND (results/bench2/blind-p7c/SUMMARY.md): open total p4s8 27.0 / p7c 27.0 of 34 (o01 9.0 / 6.5, o02 7.0 / 9.5, o03 11.0 / 11.0), wrong claims 19 / 25, relief restarts 2 / 11 (3 / 4 / 4 vs 1 / 0 / 1: every pair flagged, all against p7c; p7c's open questions ran on the long-lived LDR); hard five 5/5 (p4s8, p7b, p7c all 5/5). Searches wanted / Exa sent / refused: o01 145/30/115, o02 273/30/243, o03 244/30/214 (first refusal #31 each), hard five 19/19/0. p4s8 re-graded in this round 27.0 (7b round 27.5): graders consistent. Reading: no gain, a mixed result (questions split, more wrong claims) with the restart confound -> asked Karl. 7a (route 7a, Semantic Scholar) started 14:53 on a fresh LDR per question and runs on (independent of 7c's verdict). grader.md without "undecided" (Karl 11-01).
11-01 15:0x 7c VERDICT (Karl 11-01, option 1): NO GAIN - route 7c not adopted, no rerun. Caveat in blind-p7c/SUMMARY.md: the restart difference (11 vs 2, all against p7c, long-lived LDR) may hide a small effect. Exa stays one of the options when 7d is designed (Karl).

* 2026-11-02 02:52 phase 4 gap BEGIN (Basalt 0.2.0 settings test (Karl 11-01; basalt-020/scripts/gap.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
11-02 03:0x 7a GRADED BLIND (results/bench2/blind-p7a/SUMMARY.md): open total p4s8 28.5 / p7a 28.5 of 34 (o01 9.5 / 7.0, o02 8.5 / 10.0, o03 10.5 / 11.5), wrong claims 15 / 16, relief restarts 2 / 6 (1 / 0 / 1 vs 2 / 2 / 2: every pair flagged, all against p7a, by 1-2; p7a ran on a fresh LDR per question); hard five 5/5 (all four arms 5/5). p4s8 in this round 28.5 (7c round 27.0, 7b 27.5). Reading: no gain, a mixed result (tie, questions split) -> asked Karl, "no gain" proposed (same shape as 7c). Grades by 3 fresh graders (o02's grader left web downloads in /tmp/grade-o02-web - not deleted).
* 2026-11-02 03:13 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-02 03:18 phase 4 gap BEGIN (Basalt 0.2.0 speed screen, second short gap (basalt-020/scripts/gap2.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-02 03:26 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
11-02 03:5x 7a VERDICT (Karl 11-02, his rule): wrong claims p7a 16 vs p4s8 15 (o01 8/2, o02 5/8, o03 3/5) -> "no gain", route 7a (Semantic Scholar) DROPPED, also as a 7d route. Not longer: open questions at the 171-min budget (research clock ~508 min each; p7a's +14 min wall = held time in relief restarts), hard five 194 vs 202 min.
11-02 07:03 ITEM 7e STARTED (Karl 11-02: "Bring me 7e's questions now so 7e can run first" - the questions are his 10-28 picks s1-s4, frozen, keys hashed; GPU otherwise idle). Wiring: bench2.py SETS + "shop-7e" (.before-7e); bench2-queue.sh reads user-setup-7e.md for set shop-7e (.before-7e; replaced by mv); results/bench2/queue-plan-7e.json = s1..s4, each "without" (p7ew: p4s8's settings, SearXNG only) then "with" (p7ex: + route 7c, Exa on every search, <= 30 per run); deep-research-bench.service on BENCH2_PLAN=queue-plan-7e.json (unit backup tools/deep-research-bench.service.before-7e). Fresh LDR per question. First: s1 p7ew 07:03 (LDR_DEEP_SETUP_PROFILE=user-setup-7e.md, no search fallback, items setup critic code fixes read claims). 8 runs x ~171 min -> ends ~07:00 11-03. Exa: <= 120 of November ($0.436 of $10 used). Keys are 10-28's; prices may have moved since (graders may web-check, the question's date = the run date).
11-02 07:1x 7e PAID ARM -> TAVILY (Karl 11-02: "switch the paid arm from Exa to Tavily for all four questions, before s1's paid run starts ... If 7e was designed specifically to test Exa on shopping, tell me why before switching"). It was: PLAN.md phase 4 list (c) - Exa 3.0 added a shopping index (1.27B listings with prices and availability, the same index for Lite and Auto); 7c's no-gain was on research questions, where that index plays no part. Told Karl; plan reordered so no paid run starts before ~16:40: s1-s4 p7ew (without) first, then s1-s4 p7et (route 7b, Tavily <= 30 per run; <= 120 of November's 658 to go). Backup queue-plan-7e.json.before-tavily. Karl can still keep Exa (or add an Exa arm) before ~16:40.
11-02 07:2x 7a VERDICT REVISED (Karl 11-02, o01 check): o01's 8 wrong claims - 2 paper-sourced (SOSP deferral defaults misquoted; deferral / AcceptMoE recommended without the papers' output-changing caveat), 6 not (L2 sizes, colibri credited to Strata, M.2 x8 caveat, own-baseline misreads x2, expert count) -> 7a NO WORSE (no gain on this set), Semantic Scholar KEPT as a possible 7d route for paper-type queries. FINDING: 7a never really used S2 - 616 of 650 S2 calls failed (HTTP 429, unauthenticated pool; s2_search.py swallows the error), 5 results added in all (o03), so p7a ~ SearXNG only. A 7d S2 route needs working access first (free S2 API key = Karl's call); s2_search.py should log the HTTP status (tools change only with no LDR run live). The two paper errors came via SearXNG (as 7c's o01 misread).
11-02 08:0x KARL: (1) 7e paid arm BACK TO EXA (route 7c) as designed - the shopping index is 7e's point, 7c's research questions did not test it, Tavily's general value is shown by 7b; no third arm. queue-plan-7e.json: s1-s4 p7ew, then s1-s4 p7ex (route 7c) (backup .before-exa-back); Exa runs from ~16:40. (2) 7a FINAL: "NOT TESTED (rate-limited)" (616/650 S2 calls HTTP 429). Karl requests a free S2 API key -> ~/.config/deep-research/semanticscholar.key (he saves it; read from the file only, never printed/logged). When it exists AND no LDR run is live: s2_search.py reads the key + logs HTTP status per call; then plan a 7a rerun or fold it into 7d - cost to Karl first. (3) Backlog C6 "LDR misreads papers" (7a o01 x2, 7c o01 - all via ordinary search results; the problem is LDR's, not the source's).

11-02 17:46 Strata v0.2.10 (found by the tag watch) changes our Qwen build's path: 68 files since v0.2.9 (CMakeLists.txt (build: +98: option(STRATA_AMD_COMMUNITY_TUNING "Compile the community-made gfx1010 SDWA dot ; -102: set(STRATA_WINDOW_MAX_T "auto" CACHE STRING "rows of a verify / batch window: 8,; -103: set_property(CACHE STRATA_WINDOW_MAX_T PROPERTY STRINGS auto 8 16) ...); include/strata/core/arch_defaults.hpp (engine); include/strata/core/dflash2.hpp (engine); include/strata/core/expert_source; /home/USER/ai-speed-testing/strata-compare/logs/r21/tagcheck-v0.2.9-v0.2.10.json). FLAGGED for Karl's decision; measurements carry on on the served build (Karl 10-31: only installing or switching engines waits for him). Review read-only; after his decision: work/r22/tagcheck.sh --accept v0.2.10.

* 2026-11-03 05:03 phase 4 gap BEGIN (Basalt follow-up: exact head + helper value (Karl 11-02; basalt-020/scripts/gap3.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
11-03 05:01 7e FINISHED (queue-plan-7e.json: s1-s4 p7ew SearXNG only, then s1-s4 p7ex route 7c Exa; all rc 0; p7ew s1 121 min, the rest ~169-176 min). 05:2x blind packets results/bench2/blind-p7e (blind-open.py, same BLIND_DROP), grader.md (the keys' own 10-point checklists, prices checked on the reports' dates, US/USD, user-setup-7e.md), keys' sha256 match WRITTEN-7e.txt; 4 fresh graders running.
11-03 05:3x 7e GRADED BLIND (results/bench2/blind-p7e/SUMMARY.md): without (p7ew) 26.0 / Exa (p7ex) 29.0 of 40 (s1 5.5 / 8.5, s2 6.5 / 5.5, s3 7.0 / 6.5, s4 7.0 / 8.5), wrong claims 25 / 26, relief restarts 6 / 6 (s1 0 / 2 flagged; s1 without ended at 121 min). Exa 30 sent per run (cap), 242-276 new URLs; November Exa $0.916 of $10. Reading: small gain (+3.0, +11.5 %), questions split 2-2 = mixed -> asked Karl.
* 2026-11-03 06:18 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-03 06:40 phase 4 gap BEGIN (upgrade-pricing sweep: DeepSeek daily + the splice, VRAM 50/75/100 %, 4060 Ti on/off (Karl 11-02; work/sweep/sweep-gap.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
11-03 06:5x 7e VERDICT (Karl 11-03): s1 p7ew's 121 min = the lead's own decision (completed, no errors, 3,023 s left; synthesis after 50 min; no limit reached) -> 7e = SMALL GAIN for Exa on product questions (29.0 / 26.0; without s1 a tie 20.5 / 20.5). Exa carried into 7d for product-type searches only, as a test arm (a second read).
* 2026-11-03 08:01 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-03 08:30 phase 4 gap BEGIN (upgrade-pricing sweep, the splice again at 58 GiB RAM (Karl 11-02; work/sweep/sweep-splice58.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
11-03 09:0x ITEM 7d DESIGNED, INSTALLED, STARTED (helper staged it; results/bench2/PLAN-7D.md, staging/item7d/). The rule (from the route logs of 7b/7c/7e: first-come spent the 30 on the lead's 1-2 opening searches + the first 1-3 subtopics; the lead's first follow-up after its first subagent wave came at search 66-156, median 97): no paid search before the lead's first follow-up (>= 15 min in) or search 101; then each subagent's first 3 searches and the lead's first 10 get the paid source, cap 30 (agent label from LDR deep mode's current_agent ContextVar - verified it exists; LDR package unchanged). Replay over 20 past runs: 26.9 paid / run, 86 % in the follow-up phase, 7.7 agents reached (vs 3.6). Arms: p7d = Tavily under the rule (o01-o03 vs p4s8; s1-s4 vs p7ew), p7dx = Exa instead of Tavily on product-tagged picks (s1-s4, vs p7d); hard five not run (the rule gives them 0 paid). 11 runs ~32 GPU h; worst case 330 Tavily (422 / 1000 Nov), 120 Exa ($1.40). S2: key from the file when it exists + HTTP status per call (7d does not use S2). check.sh pre green (97 tests), install.sh: 4 tools files (backups *.before-7d), queue-plan-7d.json; one post-install test line ("the staged table only adds 7d and 7dx") fails by design after install (staged == live). Bench unit -> BENCH2_PLAN=queue-plan-7d.json (backup tools/deep-research-bench.service.before-7d), started 09:01 (pid 3264439); waits for the splice rerun's hold, then s1 p7d. Open choices for Karl: the hard five, o02 in p7dx, grading round 4 (p7b vs p7d), the rule's numbers.
* 2026-11-03 09:22 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-03 12:13 phase 4 gap BEGIN (gap 18: P028x timing logs on the 5080 alone + the bitwise-switch screen (measurements only; Karl 11-03)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-03 13:54 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
11-03 14:3x (Karl) 7d: keep the defaults (hard five not run; no o02 in p7dx; grading round 4 p7b vs p7d kept; the rule's numbers 3 / 10 / search 101 / 15 min). The Semantic Scholar key is optional, on Karl; nothing waits on it.

* 2026-11-03 16:45 phase 4 gap BEGIN (DeepSeek gate A / B / C: daily vs the 5080 alone vs + Lucebox DSpark on the 4060 Ti, ~2 h 40 min (Karl 11-03; work/ds41/gate/gate.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-03 17:48 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-03 22:36 phase 4 gap BEGIN (gap 17 part a: the v0.2.10 port's gates and pricing (a test; P028x stays served, nothing switches - Karl 11-02)): queue held after its run, test lock taken, P021 on 8080 stopped.
11-03 23:08 STUCK-RUN WATCHDOG INSTALLED (Karl 11-03 OK; staging/watchdog/, helper): ldr-client.py --watchdog-min (bench2.py passes $WATCHDOG_MIN, default 30): idle = no growth of the run's capture/calls.jsonl and no call in flight / held in run/research-clock.json; gate pauses, test locks and yields are not idle; "Strata not answering" with no call waiting IS idle (the 45-min idle stop). On firing: an LDR /proc snapshot (RSS, busiest threads), LDR's terminate API, faulted.json, rc 86. bench2.py passes 86 on; bench2-queue.sh: run-ldr.sh stop, RUNDIR -> RUNDIR.faulted-HHMMSS, a line in results/bench2/watchdog-faults.tsv, requeue ONCE on a fresh LDR; a second hang of the same run: NOTES line + desktop alert + exit 0 (no systemd restart), and a later start refuses that run. check.sh pre green (31 offline tests); install.sh --restart-unit at 23:08 inside gap 17a (queue held, no LDR run / Jan job / call live): backups *.before-watchdog; the bench unit restarted (pid 3838623), waiting on the hold. Open for Karl: the rerun's paid cap (s2 p7dx used 13 of 30 under its run name -> its rerun gets <= 17 unless renamed); the old search-failure stop exits 1, so systemd restarts the queue and the failure count resets.
11-03 23:2x THE s2 STALL EXPLAINED + FETCH GUARD STAGED (staging/fetchguard/REPORT.md, INSTALL.md; helper; not installed): the page was Team Group's compatibility "result" page with no product chosen - 263.7 MB of HTML (5.5 MB gzip), one table of 165,933 rows - not G.Skill's (66.6 KB). sub6's fetch_content thread ran LDR's extraction pipeline (BeautifulSoup html.parser ~3.5 GB + trafilatura ~12 GB + newspaper4k ~quadratic, >= 3 h - cProfile: lxml drop_tag / get_tags / get_level) on the whole page while holding patch 0004's _FETCH_LOCK; the one subagent worker was taken; the 7,200-s per-subagent backstop counts research-clock time, which stops while the GPU gate is held. Guard = patch 0006: a 16 MiB decompressed download cap (streamed; Content-Length above it refused), a 400,000-`<` tag cap before any parser, each skip logged "[FETCH-GUARD] skipped", in logs/fetch-guard.jsonl and summary.json["fetch_guard"]; a 60-s watchdog logs / counts slow pages (cannot kill a parse; a real time limit needs a killable worker process - not staged). 7/7 offline tests; normal pages byte-identical to stock. Past 13,564 extractions since 10-18: one page never finished (Team Group); the 60-s watchdog would have fired 4 times; skips est. 0-4 + Team Group. DOC_SCHEDULER: copies the newest researches' sources' text into karl's encrypted LDR library DB (no embeddings, no LLM / search calls); nothing we measure or use reads it; ~6-7 % of a core, ~0.7-2 GB downloads, many 403s per LDR lifetime; off cleanly via LDR_DOCUMENT_SCHEDULER_ENABLED=false in run-ldr.sh (asked Karl).
11-03 23:3x FETCH GUARD (LDR patch 0006) INSTALLED (Karl 11-03: "add a guard ... so a pathological page gets skipped, logged and counted"): staging/fetchguard/install.sh at 23:22 with no LDR / Jan job / call live (queue held by gap 17a); apply.sh status "patched"; offline tests pass; NOT given to the baseline profile (no --baseline). Undo: tmp/backup-fetchguard-20261103-232220/UNDO.sh. Takes effect at the next ./run-ldr.sh start (the queue's fresh LDR for s3). Check after s3: logs/fetch-guard.jsonl page records + summary.json "fetch_guard". MY SLIP, FIXED: the guard's staged tools/ldr-client.py was based on the pre-watchdog client, so its install dropped the watchdog's --watchdog-min (bench2.py passes it -> the next run would have failed on the unknown option). Fixed before any run: the guard's 3-hunk diff (tools/ldr-client.patch) applied onto the watchdog client (clean, offsets only) -> tools/ldr-client.py (the guard-only copy kept as ldr-client.py.fetchguard-only); both stagings' tools/ldr-client.py = the merged file (old ones .pre-merge); watchdog check.sh post green (31 tests, --watchdog-min present, bench2.py next answers); the guard counter smoke-tested on the merged file. Note: the watchdog's .before-watchdog backup predates the guard counter - undoing the watchdog alone would drop "fetch_guard" from summary.json.
* 2026-11-04 01:39 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-04 04:29 phase 4 gap BEGIN (gap 17 part b: the v0.2.10 port's gates and pricing (a test; P028x stays served, nothing switches - Karl 11-02)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-04 06:39 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
11-04 07:3x KARL'S ANSWERS (11-04): (1) DOC_SCHEDULER OFF: run-ldr.sh (backup .before-docsched, new file + mv) exports LDR_DOCUMENT_SCHEDULER_ENABLED=false next to LDR_WEB_HOST (LDR maps document_scheduler.enabled -> LDR_DOCUMENT_SCHEDULER_ENABLED, settings/manager.py:427); takes effect at the next LDR start = s4 p7dx (the s3 pair ran with it on; the whole s4 pair and everything after with it off) - for the bench, the runner and Jan's research; the LDR library stops collecting the researches' sources. (2) s2 p7dx rerun = a fresh 30 paid searches (as o03 10-31): ~/.config/deep-research/paid-runs.json (backup .before-s2rerun, under paid-runs.lock) "shop-7e-deep-p7dx/s2" 13 -> renamed "shop-7e-deep-p7dx/s2@stuck-1103" (kept on record; note in runs/.../s2.stuck-1103/PAID-COUNT.txt). (3) The three-search-failures stop: tools/bench2-queue.sh (backup .before-sfailexit, new file + mv) exits 0 instead of 1 (Restart=on-failure had restarted it after 60 s with the count reset); staging/watchdog/tools copy synced, check.sh post green; LIVE AT THE BENCH UNIT'S NEXT START (planned inside the DeepSeek gap while the queue is held). (4) The fetch guard keeps the 16 MiB cap. Live since s3 p7dx's LDR (06:39): 403 page records by 07:3x, 0 skips, largest page 2.7 MiB.

* 2026-11-04 09:28 phase 4 gap BEGIN (DeepSeek gate, second gap: the KL noise band (A vs two placement variants), the long-prompt memory arms, C (Lucebox DSpark), ~1 h 50 min (Karl 11-04; work/ds41/gate/gap-next.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
11-04 10:0x POST-7d STAGED (helper; staging/post7d/README.md, switch.sh, chain.sh, plan_check.py; results/bench2/queue-plan-item8.json, queue-plan-c3c.json, queue-plan-p5-holdout.json (by p5.py); nothing switched / installed / started; live files = LIVE-SHA256-AT-STAGING.txt): 7d has 7 of 11 runs left (~20 GPU h) -> ends ~07:30 11-05. (1) item 8 stage 2: 3 x 62-min runs each for o01 and o03, SearXNG only, ~6.4 h (Fix 6: 120.9 research min = one 171-min run); then replays.sh with the queue stopped (6-8 h): merges each question's runs into one report vs p4s8's evidence, + C3c's report-size replays + item 8's retry at C3c sizes; no install. (2) C3c: o01-o03 on a new flash-next-c3c profile (the 4 bigger sizes) vs p4s8, ~8.6 h; the switch installs the profile. (3) Phase 5 holdout: 64 runs, ~35 h; needs Karl's adoption calls, a GO-p5 file with the plan's sha256 and a bench2.py that knows the p5 sets (staged). Paid this month: Tavily 201 / 1,000, Exa $1.01 / $10; 7d adds <= 210 -> <= 411 Tavily, $1.25 Exa; item 8 + C3c none; Phase 5 none as staged (<= 90 with route 7d, ~275 with 7b) - all under the 750 / $7.50 test limits. Holdout sets: only ids / counts read. Between 7d and item 8: 7d's 4 blind grading rounds (staging/item7d/tools/relief_counts.py covers shop-7e), paid_tracker.py, kcheck. Helper slip: two read-only cd. Decisions asked of Karl (chain.sh start; item 8 3x62 vs 2x91, o02, p4s8 as the long side; C3c retry / hard five; Phase 5 setup; 8080 on P028x until C3c ends).
* 2026-11-04 10:00 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
11-04 10:2x LDR STUDY DONE (helper; staging/ldr-study/MEMORY.md, PAPERS.md, patches 0007-0009 + runner-fresh-ldr.patch, tests 15/15; nothing installed). (A) MEMORY: no large object leak - ldr-web keeps the memory of its biggest transient peak (glibc does not return freed memory): the 10-31 LDR jumped to 4.19 GB then sat 4.15-4.48 GB for 14 h over 5 questions; the idle LDR after s3 holds 1.75 GB (peak 2.73), 795 MB in 28 fully resident glibc arena heaps; offline no Python-object growth over 220 extractions, malloc_trim frees 26-58 %; a research's evidence is ~60-75 MB. Peaks: heavy pages (now capped by 0006), the report stage (the +3 GB jump on 11-01), probably the DOC_SCHEDULER's PDF parsing (off since s4's LDR 10:01 - compare s4's LDR RSS near 11:01 with 1.18-1.32 GB for scheduler-on runs at that age). Staged: 0007-memwatch (logs/ldr-mem.jsonl records; malloc_trim 30 s after each research and after big pages / PDFs; clears a small user-file cache); runner-fresh-ldr.patch (a fresh LDR before each Jan job when the running one holds >= 1 GB). (B) PAPERS: the PDFs were read correctly (full text 45-80 k chars reached the store); errors come later. BUG: deep subagents run with recursion_limit = 2 x 30 + 10 = 70 (langgraph_agent_strategy.py:1722), but with our deep middleware every round is THREE graph steps, so LangGraph stops them at their 23rd model call (GraphRecursionError) - before the middleware's step-limit wrap-up at call 29 - and the findings become "Research on '...' reached iteration limit." 148 of 217 deep subagents since 11-01 (all at exactly 23 calls); 7a o01 6/11, 7c o01 9/16, p4s8 o01 13/17 (incl. the subagent that read the KTransformers paper in 7a o01). Verified by me: the code at :1722 / :1732, "recursion_limit" in 48 runs' research-logs.json, "reached iteration limit" 9 x in shop-7e-deep-p7dx/s1's evidence. Every arm since p4s8 has it equally. Also: extractions cut qualifiers (AcceptMoE "changes the model distribution") or miss a paper's setup (DALI's 16-core cap); writers labelled their own derived figures as the paper's; fMoE cited from snippets only and mixed with another paper; our consistency check flagged 4 of 6 errors, nothing rewrites. 10.7 % of verbatim quote lines start mid-sentence (704 drop a qualifier); 25.7 % of "quote" lines are not verbatim on the page. Staged, each off until named in LDR_DEEP_FIX: 0008 "steps" (_deep_recursion_limit = 3 x calls + 10; a cut-off subagent's quotes passed to the lead), 0009 "papers" (complete cut quotes, add caveat / setup sentences, prompt rules; the deterministic part replayed over 5,137 extractions, +10 % text; the prompt rules need a GPU replay). Designed, not coded: a pass rewriting flagged sentences. Install order 0007 -> 0008 -> 0009, then make-patches.sh. Helper slip: two cd in scratch.
11-04 10:43 POST-7d CHAIN STARTED (Karl 11-04 OK): user unit post7d-chain (pid 181246; staging/post7d/chain.sh; log logs/post7d-switch.log): step 1 waits for 'queue finished (queue-plan-7d.json)' (polls 2 min, waits while tmp/bench2.hold exists), then install-ldr-fixes.sh (0007 memwatch + 0008 steps + runner-fresh-ldr + the queue's fix:steps support; NOT 0009; only with no hold, no Jan job, nothing on run/bench.lock; stop runner + LDR, backups, apply, make-patches.sh, apply.sh 'patched', 9 tests, runner back; any failure restores and stops) -> queue-plan-p4s9.json (fresh baseline: o01-o03, 171 min, p4s8's setup + fix:steps) -> item 8 (3 x 62 min, o02 later) -> replays.sh (vs p4s9) -> C3c (retry on, no hard five) -> Phase 5 only with GO-p5 (baseline arm pristine LDR). First lines: 'waiting for queue-plan-7d.json to finish'. Note: install refuses if staging/ldr-study patches change after the 10:05 snapshot (re-stage). Phase 5 picks (helper's, adopted): o01 with the 8 GB text on its own line (+3.4 h; Karl's real question, outside the holdout totals), checkables at 47 min (= 30 research min under Fix 6). Step-bug line in results/bench2/PLAN-7D.md section 9 for each 7d SUMMARY.md. Open for Karl: Jan's research jobs use 'steps' only if turned on for them too.

* 2026-11-04 12:51 phase 4 gap BEGIN (gap 19: stock v0.2.10 diagnostic - GDN paths and PF_HC_REGION on vs off (measurements only; P028x stays served, nothing switches - Karl 11-04)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-04 13:30 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-04 16:20 phase 4 gap BEGIN (r23 NLL many-positions gap (item 6: score.py, 8 arms + 2 optional; measurements only, P028x stays served, nothing switches - Karl 11-04)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-04 17:05 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-04 19:55 phase 4 gap BEGIN (r23 GDN prompt paths on vs off on stock v0.2.10 at many positions (score.py; 2 arms + 2 optional; measurements only, P028x stays served, nothing switches - Karl 11-04)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-04 20:13 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-04 23:02 phase 4 gap BEGIN (r23 decode items gap a: build + tests + exact7 + pf_yardstick + timing (measurements only; P028x stays served, nothing switches - Karl 11-04)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-05 00:14 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-05 03:03 phase 4 gap BEGIN (DeepSeek gate, C only: the drafter's greedy divergence (top-2 gap), then C's speed under sampling if within rounding (Karl 11-04; work/ds41/gate/gap-csample.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-05 03:04 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-05 05:54 phase 4 gap BEGIN (r23 decode items gap b: the 9-workload screen + bp90 (measurements only; P028x stays served, nothing switches - Karl 11-04)): queue held after its run, test lock taken, P021 on 8080 stopped.

11-05 06:47 Strata v0.2.11 (found by the tag watch) changes our Qwen build's path: 76 files since v0.2.9 (CMakeLists.txt (build: +98: option(STRATA_AMD_COMMUNITY_TUNING "Compile the community-made gfx1010 SDWA dot ; -102: set(STRATA_WINDOW_MAX_T "auto" CACHE STRING "rows of a verify / batch window: 8,; -103: set_property(CACHE STRATA_WINDOW_MAX_T PROPERTY STRINGS auto 8 16) ...); include/strata/core/arch_defaults.hpp (engine); include/strata/core/dflash2.hpp (engine); include/strata/core/expert_source; /home/USER/ai-speed-testing/strata-compare/logs/r21/tagcheck-v0.2.9-v0.2.11.json). FLAGGED for Karl's decision; measurements carry on on the served build (Karl 10-31: only installing or switching engines waits for him). Review read-only; after his decision: work/r22/tagcheck.sh --accept v0.2.11.
* 2026-11-05 07:04 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-05 09:54 phase 4 gap BEGIN (r23 decode-path check (Karl 11-05: the prompt variants against the decode path, + prompt speed; measurements only, P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-05 11:12 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
* 2026-11-05 11:14 PILLOW (Karl 11-05; staging/post7d/install-ldr-fixes.sh, after the LDR fixes, before the first post-7d run): 12.3.0 -> 13.0.0 (python -I -m pip install pillow==13.0.0; pip freeze: only pillow changed (12.3.0 -> 13.0.0); requirements.lock.txt updated, backup .before-pillow13). Smoke before the first post-7d run, LDR's ContentFetcher, 12.3.0 then 13.0.0 on the same pages: ok (pdf https://arxiv.org/pdf/1706.03762 41027 chars; html https://en.wikipedia.org/wiki/Mixture_of_experts 32131 chars). Log staging/post7d/logs/pillow-smoke.txt; rollback: pip install pillow==12.3.0 + the lock backup.
* 2026-11-05 11:14 LDR FIXES INSTALLED (Karl 11-04; staging/post7d/install-ldr-fixes.sh, after 7d): patch 0007 memwatch + 0008 subagent steps (item "steps", plans name it fix:steps) from staging/ldr-study (NOT 0009), runner-fresh-ldr + runner-steps (Karl 11-04: Jan's deep research jobs now start LDR with LDR_DEEP_FIX=steps, stamp setup critic fix:steps; runner restarted, pid 1320657), tools/bench2-queue.sh fix:steps; backups *.before-ldrfix, undo staging/post7d/ldr-fixes/UNDO.sh; patches/ldr regenerated (apply.sh: patched); tests 9/9 on the installed package + the Jan-job check (tests/test_runner_steps.py). Every bench plan and Jan deep job from here on runs with "steps". Then: pillow 13.0.0 (smoke ok).
* 2026-11-05 11:14 BENCH PLAN SWITCH (staging/post7d/switch.sh, Karl's OK): queue-plan-7d.json finished -> deep-research-bench.service on queue-plan-p4s9.json (unit backup tools/deep-research-bench.service.before-p4s9); queue pid 1320700; first run rofile, model profile flash-next 28732eeb029b): running (pid 1320816, RSS 303 MiB), UI http://127.0.0.1:5000 -> HTTP 200, log /home/USER/ai/deep-resea.
11-05 12:3x 7d BLIND GRADING DONE (helper; one fresh grader per round, grades written before each KEY was opened; SUMMARY.md x4 + blind-p7d-OVERALL.md saved by me - the helper's writes were refused): round 1 p4s8 / p7d 28.0 / 31.0 of 34, wrong claims 8 / 11, restarts 2 / 2 (mixed); round 2 p7d / p7dx 28.0 / 25.5 of 40, 22 / 19, 2 / 3 (no gain for Exa on product follow-ups); round 3 p7ew / p7d 27.0 / 28.0 of 40, 17 / 22, 6 / 2 (not a gain; rests on s1); round 4 p7b / p7d 30.0 / 27.5 of 34, 12 / 15, 6 / 2 (no gain for 7d over first come). The 7d rule worked as designed (paid searches at the lead's follow-up, 6-10 agents vs 3-4) but the paid results were not used more (open questions used 9.0 % vs 9.7 %, cited 3.8 % vs 6.7 %); Exa product URLs used ~4x Tavily's (23 % vs 5 %) without moving the grades. Spend 273 Tavily + 63 Exa. Grader noise: the same p7d o02 report got 10.5 and 8.0 (compare within a round only). For Phase 5: 7b still the only route with a clean gain (one round, rests on o02); options (a) 7b, (b) none, (c) settle on the fixed build vs p4s9. Write-ups helper started (item 7 + frontier 11-05).
11-05 12:4x POST-7d WEEKEND REVIEW (helper; desk work; nothing started / stopped / switched; chain.sh + switch.sh untouched): staging/post7d/WEEKEND-READY.md. FIXED staging/post7d/replays.sh (not started; new file + mv, old copy scratch/weekend/replays.sh.before-weekend; sandbox test 18/18): a gap's hold set after the hold check but before fix-replay takes run/bench.lock could stop 8080 under a starting replay (now: wait while hold or open gap, re-check before start, a replay a gap overlapped is VOID -> aside + rerun once); per-replay time limit 180 min (fix-replay has no watchdog); kcheck after each replay; optional REPLAYS-GO-ON (a failed replay set aside, C3c still starts). FOUND: the o01 8 GB line adopted 11-04 is not in queue-plan-p5-holdout.json -> staged staging/post7d/phase5/apply-p5.sh ROUTE [--no-o01] [--c3c] [--check] (freezes FROZEN-p5-o01.txt only when run; never writes GO-p5; all variants pass --check). Staged tools/relief_counts.py reading Phase 5 folders. RULES-item8.md, RULES-c3c.md, RULES-p5.md frozen (before any result). Timeline: item 8 ~Fri 00:15-13:50, replays to ~Fri 16:00-23:15, C3c to ~Sat 00:30-08:00, Phase 5 to ~Sun 12:30-22:00 if GO-p5 is in by Fri ~23:00. Decisions for Karl D1-D9 (WEEKEND-READY.md section 9). Helper slip: three read-only cd.
11-05 12:4x WEEKEND-READY (helper; staging/post7d/WEEKEND-READY.md; RULES-item8.md / RULES-c3c.md / RULES-p5.md frozen 11-05 before any result; chain.sh / switch.sh untouched): replays.sh FIXED (new file + mv; old in scratch/weekend/): replays wait while a hold or open gap exists and re-check just before starting; a replay a gap overlapped is void and reruns once; 180-min limit per replay + a kernel check after; sandbox 18/18. FOUND: the o01 8 GB line Karl adopted 11-04 was missing from the Phase 5 plan -> staging/post7d/phase5/apply-p5.sh <route> adds it (never writes GO-p5; sandbox install ok). Decisions D1-D9 (GO-p5 by Fri ~23:00 else the GPU idles after C3c; route by 7d's outcome - per its rule blind-p7d is mixed (+3.0 score, +3 wrong claims) -> none; o01 line in; profile flash-next; engine P028x; items as staged; item 8 not in Phase 5; REPLAYS-GO-ON yes; the open rule points as recommended, unconfirmed). Timeline: item 8 ~Fri 00:15-13:50, replays to ~16:00-23:15, C3c to ~Sat 00:30-08:00, Phase 5 to ~Sun 12:30-22:00. Disk 180 GB free (~117 after the UD3.1 gap); chain < 2 GB. November paid: Tavily 365 / 1000, Exa $1.17 / $10; steps 1-3 none. Helper slip: three read-only cd.
11-05 12:5x Phase 5 ARMED: route none (PLAN-7D's rule: blind-p7d mixed), GO-p5 3e1d0589fcc7... = the plan's sha256 (66 runs, ~38.5 GPU h, paid cap 0, o01 line in, fix:steps, no papers fix).

* 2026-11-05 14:03 phase 4 gap BEGIN (r23 decode b screen rerun: LO3 Bs3 L3 (measurements only; P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-05 14:15 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-05 14:15 phase 4 gap BEGIN (Basalt prompt-path gate part a: build + correctness (a test; P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
11-05 14:5x POST-7d D8 + D9 (Karl 11-05; helper; nothing started): staging/post7d/REPLAYS-GO-ON written; replays.sh replaced (not started; new file + mv): one failed replay set aside and C3c starts anyway, a second failed replay stops the chain with a NOTES line + critical alert; each failure recorded in staging/post7d/item8/failed-replays.tsv (why, folder, retry needs a decision?, code/evidence sha256). Staged one-shot staging/post7d/retry-failed-replay.sh (NOT started; command in WEEKEND-READY.md section 11): after the chain and the bench queue are inactive it retries each recorded replay once unless a decision is needed (evidence/code changed, engine not P028x, kernel), else RETRY-NEEDS-DECISION.txt + alert. Sandbox tests 24/24 + 15/15. RULES-item8/c3c/p5.md: the 7 OPEN (D9) points each marked '11-05 Karl: ... confirmed as recommended (set before any result)' (files written 12:21-12:22, before any item 8 / C3c / Phase 5 run).
11-05 15:1x D8 DONE (weekend helper + me): staging/post7d/REPLAYS-GO-ON exists; the new replays.sh (not started) sets a first failure aside and goes on (C3c starts), a SECOND failure stops the chain with a NOTES line + critical alert; failures recorded in staging/post7d/item8/failed-replays.tsv. The end-of-chain retry staging/post7d/retry-failed-replay.sh - my change (Karl: a second failure = stop and alert): it retries only at the chain's NORMAL end ('queue finished (queue-plan-p5-holdout.json)' in the queue log); after an early stop it writes RETRY-NEEDS-DECISION.txt and alerts instead; its sandbox test fixed (it pointed at the pre-mv replays.sh.new) + a new early-stop case: 16/16. Started as user unit post7d-retry (waiting for the chain to end). D9: all 7 OPEN (D9) points in RULES-item8 / -c3c / -p5 carry the dated confirmation line.
* 2026-11-05 16:46 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
11-05 19:0x REVIEWS (Karl's three): (1) fresh weekend audit staging/post7d/AUDIT-1105.md - FIXED by Claude (no rule changed): #6 gap-series started_after_gap counted an untimestamped 'LDR (...): running' status line (csample would have run straight after Basalt b; csample->ud31 back to back) -> timestamped lines only, deployed by the one-shot series-restart-after-bb (csample's .ready held until then; sandbox-tested 3 cases); #1 an exit 1 with the gap still open now stops the series with an alert (was: skipped -> stall); #12 no blind launch after 4 h (waits, notice every 4 h); #7 port_gap4 end releases the test lock only after the engines exited + memory came back; #6b port_gap4 begin needs bench.lock free at two looks 45 s apart; #10 engine_sha = the 8080 listener's engine child (checked live: f4c4f654fb24); #13 kwatch also stops strata-vision + strata-dsv41 (restarted, kcheck ok); #5 the retry's chain-end check ignores the 60-s auto-restart (both units inactive/failed twice 2 min apart; test 16/16; unit restarted); new unit weekend-watch (alerts only: stale hold / dead lock holder, a run not completed 3x, disk < 105/100 GB, KERNEL_ERROR; RULES-p5 Q6 kcheck when Phase 5's queue finishes; sandbox-tested). FOR KARL: #3 kwatch one-shot on benign page-allocation/WARN, #4 linger + power key + boot alert, #8 gaps do not wait for Jan jobs, #9 wall-clock limits count gate-held time, #15 a transient refusal skips a driver for good, #2 stop (not only alert) after 3 failures. (2) Basalt switches: results/r23/basalt-prompt/FIX-1105.md - the one-slot yardstick read at 1024 chunks, so none could fire; 3 fix commits on r23-basalt-prompt (b8128327d), build engine-r23basalt-fix running under nogap-run (unit build-basalt-fix); carry-over to r23-port0211 clean (all six commits). Rerun driver gap-basalt-fix.sh reviewed: NOT .ready - T's long40 arm runs at the yardstick's bare auto (1024), where T cannot fire, so half of T's KL rule is vacuous; in the series as the last step, gated by .ready (Karl decides the fix). (3) port review results/r23/port-0211/REVIEW-1105.md: 2 bugs fixed in r23-port0211 5f5aebcc2 (web search kept the lost-answer guard from firing; iq_pack vs upstream's new test) - test_mcp 30/30, test_mcp_media ok, test_iq_pack ok, test_server 373/374 (test_hip_ordinal); gap-port0211.sh's head check widened to that descendant (re-reviewed, .ready sha fe792cad413c); BASE_ABSENT + the two v0.2.11 NV-default lines (selftest 0 failures).

* 2026-11-05 19:35 phase 4 gap BEGIN (Basalt prompt-path gate part b: speed (a test; P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-05 20:31 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
* 2026-11-05 21:23 QUEUE-FAILURE RULE INSTALLED (Karl 11-05 decision 3; helper + Claude's review): tools/bench2-queue.sh + tools/bench2.py (+ the Phase 5 copy staging/post7d/tools/bench2.py, .orig refreshed) - a run that fails 3 times (attempts that ran and did not finish, watchdog stops included; results/bench2/queue-failures.tsv) is dropped (folder -> results/bench2/runs-failed/, NOTES line, critical alert, next run) only where its frozen rules judge it missing (results/bench2/queue-droppable.json from QUEUE-DROPPABLE-1105.md: item8 none, c3c none, p5-holdout the 50 checkables), else the queue stops (exit 0) with an alert; a second run at 3 failures stops it. Sandbox 9/9; backups *.before-queuefail. Takes effect when the item 8 switch starts the queue. Open for Karl: a dropped Phase 5 checkable is 'not run' on one arm only (RULES-p5 3) - p5.py packets needs --allow-missing at grading.
* 2026-11-05 21:26 RULES-p5 3 AMENDED (Karl 11-05, before any Phase 5 result): a checkable dropped on one arm is left out of both arms; dropped pairs reported next to the result; > 3 of 25 dropped -> the Phase 5 comparison marked WEAKENED in the write-up.
* 2026-11-05 21:41 BOOT RESUME ENABLED (Karl 11-05 decision 5, after Claude's review; sandbox 58/58): ~/.config/systemd/user/boot-resume.service (staging/post7d/boot-resume.sh, BOOT-RESUME.md) - records the transient units every 30 s (run/boot-resume/units.txt: gap-series, post7d-chain, post7d-retry, weekend-watch); after a reboot: alert (NOTES + desktop), kernel check (+ the previous boot's kernel log), interrupted-gap cleanup only with no driver alive, 8080 back (sha + cache policy checked), then the chain at the bench unit's plan, the series (interrupted gap first, after a question that began after the boot), retry and watcher - each once. Not covered: the series-restart-after-* waiters (a held .ready must be restored by hand), a reboot mid-replays after a failure (fix being staged).
* 2026-11-05 21:46 replays.sh: a rerun after a reboot keeps D8's count (seed_fails from item8/failed-replays.tsv; failed / void-twice labels not rerun in line - the end-of-chain retry's job); the 10-29 verify backup is not overwritten; boot-resume.sh resumes that case now. Tests: replays 36/36, retry 16/16, boot-resume 58/58. Backups *.before-seed.
* 2026-11-05 22:31 BOOT CHECK INSTALLED (Karl 11-05 reboot decisions 1+2 + held ready marks; helper + Claude's review): boot-check.service (oneshot, After=kwatch, Before=deep-research-bench + boot-resume; enabled, acts only at boot) writes tmp/bench2.hold first (fail closed), runs kcheck + the previous boot's kernel log + its clean-shutdown test (the 10-31 boot ended 'Reached target reboot.target' - matched); pass -> the pre-boot hold restored / removed; fail -> nothing resumes, the queue stays held, NOTES (both repos) + a critical notice with the journal facts and the one resume command: bash ~/ai/deep-research/staging/post7d/boot-resume.sh resume (re-runs kcheck first). boot-resume.sh: a recorded series-restart-after-* waiter is applied (its held .ready restored, steps computed its way) instead of restarted; the resume lock no longer blocks 'resume'. Tests 23/23 + 58/58; backups *.before-bootcheck.

* 2026-11-05 23:24 phase 4 gap BEGIN (DeepSeek gate, C only: the drafter's greedy divergence (top-2 gap), then C's speed under sampling if within rounding (Karl 11-04; work/ds41/gate/gap-csample.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-05 23:26 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
* 2026-11-06 02:24 BENCH PLAN SWITCH (staging/post7d/switch.sh, Karl's OK): queue-plan-p4s9.json finished -> deep-research-bench.service on queue-plan-item8.json (unit backup tools/deep-research-bench.service.before-item8); queue pid 2475737; first run rofile, model profile flash-next 28732eeb029b): running (pid 2475874, RSS 301 MiB), UI http://127.0.0.1:5000 -> HTTP 200, log /home/USER/ai/deep-resea.
* 2026-11-06 06:58 GAP SERIES STALL FIXED (Claude): gap-ud31.sh waited 23:26 -> 06:58 beside running item-8 questions - the boundary needed the queue's 'hold released' line, which the queue logs only while it waits at the hold (csample's gap ended during o03's 10-min retry sleep, then the queue restarted on item 8). gap-series.sh now waits for a timestamped question line at or after the previous gap's END (t_end; SERIES_T_END for a restarted series; a refusal keeps the previous end; sandbox-tested with no 'hold released' lines + the refuse-once case); boot-resume.sh passes SERIES_T_END (suites: test3 23/23, test2 unchanged vs installed, test.sh only the 2 expected anchor changes). Series restarted 06:58 (SERIES_T_END 23:26:19); ud31 preflight passed, hold set, waiting for p8b o03. Overnight: o03 (p4s9) attempt 1 failed at 98 % (6 empty web searches in a row), rerun ok 02:22; csample 23:24-23:26: TIE exit 2 (the CLI path does not diverge within 512 tokens; the served one did at char 126) -> C0-C2 skipped (Karl decides); item 8 since 02:24.

* 2026-11-06 07:28 phase 4 gap BEGIN (r23 Unsloth v3.1 test gap (P / U / S / R: packs + splice, exact7, score.py NLL + KL, speed screen x3; measurements only, P028x stays served, nothing switches - Karl 11-04)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-06 07:45 ALERT PUSH (Karl 11-06: ntfy.sh, a long random topic, short path-free messages, alerts only): user unit alert-push.service (enabled, Restart=always; tools/alert-push.py) monitors the session bus for Notify calls and forwards only CRITICAL ones from our own app names (18: Strata gaps, Deep research, Weekend watch, Kernel watch, Boot resume, ...) to ntfy.sh; text cut to a title + one line with paths, ~, @, IPs (127.0.0.1 kept), UUIDs, long hex, user and host name removed; duplicates within 15 min dropped, max 20/h. Topic in ~/.config/alert-push/topic (600), never logged. Test 07:44: one message, on the server (priority high). Log: logs/alert-push.log (titles only). Also: RULES - Basalt rerun C40 now judged against the 16384 references, 1024 comparison INFO only (re-reviewed, .ready rewritten); U parked in strata-compare results/BACKLOG-1027.md H.
* 2026-11-06 08:47 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-06 09:48 phase 4 gap BEGIN (r23 v3.1 follow-up: U's decode-path teacher-forced score with STRATA_HC_Q8=1 (Karl 11-05; measurements only, P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-06 10:35 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
* 2026-11-06 15:34 REBOOT PREP (Karl 11-06: he reboots into Windows ~18:00, back ~23:00): run/pause-window 17:30-23:00 in tools/bench2.py's night cut (both copies + .orig; the queue starts no question that would not end by 17:30 -> C3c waits until 23:00; tested); one-shot reboot-prep-1106 (17:00 hold if the replays are not done; 17:40 ready alert to the phone). The quiet window (no gap 14:50-23:00) stays.
* 2026-11-06 16:41 BENCH PLAN SWITCH (staging/post7d/switch.sh, Karl's OK): queue-plan-item8.json finished -> deep-research-bench.service on queue-plan-c3c.json (unit backup tools/deep-research-bench.service.before-c3c); queue pid 3438634; active, waiting (see logs/bench2-queue.log).
* 2026-11-06 17:40 REBOOT PREP (staging/post7d/reboot-prep-1106.sh): 17:40: Ready to reboot: no question, replay or gap is running (the queue waits until 23:00; the chain resumes after the reboot).
* 2026-11-06 18:01 REBOOT (staging/post7d/boot-resume.sh): the PC rebooted (boot 2026-11-06 18:01:36). Interrupted: question: none running (the last one, screen / deep / p8c / o03: running, ended); bench unit on queue-plan-c3c.json; was active: gap-series; was active: post7d-chain; was active: post7d-retry; was active: series-append-ctie; was active: weekend-watch; the previous boot shut down cleanly (last journal entry 2026-11-06 18:01:43). Resuming at the next clean boundary after the kernel check (Karl 11-05).
* 2026-11-06 18:01 REBOOT (staging/post7d/boot-resume.sh): outcome - NOT resumed: boot-check.service is installed but left no verdict (crashed or timed out - its hold stays) - nothing resumed; after Karl's check: bash ~/ai/deep-research/staging/post7d/boot-resume.sh resume
* 2026-11-06 22:06 DEEPSEEK LAUNCHERS BUILT (Karl 11-06; not switched, first real switch = his click): configs/usability/bin/deepseek-session.sh + desktop/app-menu 'DeepSeek + DS Harness' and 'Back to Qwen'; a session = a gap for everyone else (hold text 'phase 4 gap: DeepSeek session', test lock via unit ds-session-lock, marker tmp/ds-session valid for its boot only). port_gap4 begin + gap-series wait during a session; weekend-watch alerts after 4 h (one-shot timer ds-hold-alert if the watcher is down); boot-resume removes a stale marker. DS Harness: ~/.dsh-deepseek, port 3081, configs/usability/dsh/web.deepseek.patch.yml. Jan: jan-add-deepseek.py runs once from jan-strata while Jan is closed (entry under the Strata provider, tools only) - NOT applied yet, Jan is open. Tests work/ds-launcher/test_deepseek_session.sh 37/37; real lock holder tested on sandbox paths. FOUND: boot-check never ran at the 11-06 reboot - systemd ordering cycle (boot-check After kwatch After default.target); fixed by removing kwatch's After=default.target (systemd-analyze verify default.target now clean); so boot-resume refused and the chain, series, retry and watcher are DOWN. Karl: 'wait for me to say resume': run/pause-window extended to 12-01 so C3c does not start at 23:00 by itself; on resume: remove run/pause-window, then boot-resume.sh resume.
* 2026-11-06 22:12 DEEPSEEK SESSION started (the launcher, config A): the queue is held, the test lock taken, P028x stopping.
* 2026-11-06 22:12 DEEPSEEK SESSION: DeepSeek config A up on 8080 (ok: model deepseek-v4.1-flash loaded, engine pid 118820 = config A's binary); the queue stays held until Back to Qwen.
* 2026-11-06 22:34 DEEPSEEK SESSION: Back to Qwen FAILED - P028x not back, the queue stays held (configs/usability/bin/deepseek-session.sh).
* 2026-11-06 22:34 DEEPSEEK SESSION: Back to Qwen FAILED - P028x not back, the queue stays held (configs/usability/bin/deepseek-session.sh).
* 2026-11-06 22:34 DEEPSEEK SESSION: Back to Qwen FAILED - P028x not back, the queue stays held (configs/usability/bin/deepseek-session.sh).
* 2026-11-06 22:49 REBOOT (staging/post7d/boot-resume.sh): the PC rebooted (boot 2026-11-06 20:20:34). Interrupted: question: none running (the last one, screen / deep / p8c / o03: running, ended); bench unit on queue-plan-c3c.json; was active: gap-series; was active: post7d-chain; was active: post7d-retry; was active: series-append-ctie; was active: weekend-watch; the previous boot shut down cleanly (last journal entry 2026-11-06 18:01:43). Resuming at the next clean boundary after the kernel check (Karl 11-05).
* 2026-11-06 22:54 REBOOT (staging/post7d/boot-resume.sh): the PC rebooted (boot 2026-11-06 20:20:34). Interrupted: question: none running (the last one, screen / deep / p8c / o03: running, ended); bench unit on queue-plan-c3c.json; was active: gap-series; was active: post7d-chain; was active: post7d-retry; was active: series-append-ctie; was active: weekend-watch; the previous boot shut down cleanly (last journal entry 2026-11-06 18:01:43). Resuming at the next clean boundary after the kernel check (Karl 11-05).
* 2026-11-06 22:55 REBOOT (staging/post7d/boot-resume.sh): outcome - NOT resumed: series-append-ctie (/bin/bash /home/USER/ai-speed-testing/strata-compare/work/r23/series-append-ctie.sh) was active - not restarted (unknown to boot-resume); Claude checks | done: kernel check ok (resume by hand after Karl's check); 8080 up: engine f4c4f654fb24 (P028x), policy on; chain restarted at step 4 (CHAIN_STEPS="4"; switch.sh re-waits for queue-plan-c3c.json to finish; was: waiting); series: boot-resume-series waits for a question started after the reboot, then gap-series with: work/r23/gap-port0211.sh work/r23/gap-basalt-fix.sh; retry restarted (it waits for the chain's end again; an interrupted retry is its own 'needs a decision'); weekend-watch restarted
* 2026-11-06 23:03 PAUSED FOR KARL'S TEST (Karl 11-06: 'pause everything ... I will say to resume'): run/pause-window + tmp/quiet-window = 2026-11-06 23:00 to 2026-12-01 00:00; o01 (pc3c) stopped by hand 8 min in (bench2.py, then its client, then run-ldr.sh stop; no failure counted), it reruns from the start. On 'resume': Back to Qwen if DeepSeek is up, remove both window files.
* 2026-11-06 23:04 DEEPSEEK SESSION started (the launcher, config A): the queue is held, the test lock taken, P028x stopping.
* 2026-11-06 23:05 DEEPSEEK SESSION: DeepSeek config A up on 8080 (ok: model deepseek-v4.1-flash loaded, engine pid 179592 = config A's binary); the queue stays held until Back to Qwen.
* 2026-11-06 23:09 DEEPSEEK SESSION ended: P028x back on 8080, the queue released.
* 2026-11-06 23:34 DEEPSEEK SESSION started (the launcher, config A): the queue is held, the test lock taken, P028x stopping.
* 2026-11-06 23:35 DEEPSEEK SESSION: DeepSeek config A up on 8080 (ok: model deepseek-v4.1-flash loaded, engine pid 205152 = config A's binary); the queue stays held until Back to Qwen.
* 2026-11-06 23:38 DEEPSEEK SESSION ended: P028x back on 8080, the queue released.
* 2026-11-07 00:37 REBOOT (staging/post7d/boot-resume.sh): the PC rebooted (boot 2026-11-06 20:20:34). Interrupted: question: none running (the last one, screen / deep / p8c / o03: running, ended); bench unit on queue-plan-c3c.json; was active: gap-series; was active: post7d-chain; was active: post7d-retry; was active: series-append-ctie; was active: weekend-watch; the previous boot shut down cleanly (last journal entry 2026-11-06 18:01:43). Resuming at the next clean boundary after the kernel check (Karl 11-05).
* 2026-11-07 00:37 REBOOT (staging/post7d/boot-resume.sh): outcome - NOT resumed: a gap driver / the series / a replay is alive or tmp/gpu-test.lock is held (202382 /bin/bash /home/USER/ai-speed-testing/strata-compare/results/r23/run-copies/gap-series-boot-1106-225) - no cleanup, nothing resumed | done: kernel check ok (resume by hand after Karl's check)
* 2026-11-07 00:37 RESUME (Karl 11-07, his DS Harness job finished, confirmed: 8080 idle 6 min, DS Harness 0 running tasks; not cancelled): run/pause-window + tmp/quiet-window removed 00:37:22, boot-resume.sh resume run by hand. The 'PC rebooted' + 'NOT resumed: the series is alive' lines just above are that run, not a new reboot: no reboot since 20:20, every unit was already up, so it only ran the kernel check (ok). chain 160935, series 202382, retry 162776, watcher 202412, kwatch 1630, ctie 165328, bench 1629 active; no hold. New: configs/usability/bin/ds-harness-task.py (running|cancel through DS Harness's own API; prints counts only), tested on a scratch instance + stub in work/ds-launcher/auto-resume/.

11-07 03:20 Strata v0.2.12 (found by the tag watch) changes our Qwen build's path: 250 files since v0.2.9 (CMakeLists.txt (build: +98: option(STRATA_AMD_COMMUNITY_TUNING "Compile the community-made gfx1010 SDWA dot ; -102: set(STRATA_WINDOW_MAX_T "auto" CACHE STRING "rows of a verify / batch window: 8,; -103: set_property(CACHE STRATA_WINDOW_MAX_T PROPERTY STRINGS auto 8 16) ...); include/strata/core/amd_community.hpp (engine set unknown: no build folder for /home/USER/ai-speed-testing/strata-compare/e; /home/USER/ai-speed-testing/strata-compare/logs/r21/tagcheck-v0.2.9-v0.2.12.json). FLAGGED for Karl's decision; measurements carry on on the served build (Karl 10-31: only installing or switching engines waits for him). Review read-only; after his decision: work/r22/tagcheck.sh --accept v0.2.12.

* 2026-11-07 03:35 phase 4 gap BEGIN (r23 v0.2.11 port gate (Karl 11-05: the pinned-off port against P028x; measurements only, P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-07 05:09 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-07 10:54 phase 4 gap BEGIN (Basalt prompt-path fix rerun: A, T, C on engine-r23basalt-fix (a test; P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-07 11:50 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
* 2026-11-07 11:52 BENCH PLAN SWITCH (staging/post7d/switch.sh, Karl's OK): queue-plan-c3c.json finished -> deep-research-bench.service on queue-plan-p5-holdout.json (unit backup tools/deep-research-bench.service.before-p5-holdout); queue pid 995198; first run ne profile, model profile flash-next 28732eeb029b): running (pid 995309, RSS 301 MiB), UI http://127.0.0.1:5000 -> HTTP 200, log /home/USER/ai/deep-re.

* 2026-11-07 12:21 phase 4 gap BEGIN (DeepSeek gate, C: the near-tie check through the served path, then C's speed under sampling if within rounding (Karl 11-06 (a); work/ds41/gate/gap-ctie-served.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-07 13:29 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.
* 2026-11-07 14:12 O05 CHECK (Karl 11-07: 6 min / 44 calls vs o04's 304 looked suspicious): GENUINE, counts as is; queue not touched. holdout baseline p5 o05 (the Qwen4 Flash confirmed-vs-rumored question; RULES-p5.md Q3: its reference says unreleased): rc 0, 340 s. The main agent made 42 tool calls itself: 15 web searches (0 failed) and 27 page fetches (25 extracted; 2 failed to fetch, normal). It never used research_subtopic (o04 spread ~30 subtopic agents of ~9 calls each = most of its 304 calls). Every call HTTP 200, 0 stream errors, 0 client drops, no empty turns. The agent ended on its own (finish stop, 18 turns, no forced wrap-up), with a 15.6 KB report and ~34 citations whose first line is 'Qwen4-Flash has not been released'; the synthesis call answered with 15.9 KB. A narrow question with a short true answer, researched directly - not a stall, skipped step, empty search or swallowed error.
* 2026-11-07 14:14 O04 + O06 FLAGGED FOR KARL (found while checking o05; queue not touched): both baseline runs hit the 131072 context window and pristine LDR 1.10.7 swallowed it as 'completed' (rc 0). o04: the agent's final answer stopped at the window (prompt 125,482 + 5,582 tokens, finish length, 11.2 KB, ends mid-sentence); the citation handler's synthesis was refused 400 (315,329 tokens); LDR logged 'Citation handler failed, using raw agent answer' -> the graded text is the cut-off answer. o06: the LangGraph agent's next turn was refused 400 (131,155 tokens), so its 20 turns of fetched pages never reached an answer; a fallback synthesized from ~5.5 KB of search snippets (prompt 1,573 tokens, 8.5 KB answer), then the citation synthesis was refused 400 (218,650 tokens) -> 'using raw agent answer' = the snippet-only text. o05 never neared the window. RULES-p5.md has no line for this; Claude's recommendation: count both as they are (this is the pristine baseline's own behavior; a rerun would repeat it) and flag them beside the grades like the search-trip flag. Karl decides.
* 2026-11-07 14:43 KARL 11-07 ON O04 / O06: count them as they are, flagged beside the grades like search trips - 'context overflow: cut-off answer' (o04), 'context overflow: snippet fallback' (o06); a dated note (results/bench2/p5-run-flags.json), not a rule change (RULES-p5.md unchanged); overflows counted per arm in p5.py's REPORT.md ('## Runs'); staging/phase5/overflow.py detects them (refused requests once each, raw-answer fallback; near-window warnings INFO only); relief_counts.py's flag column shows them. A run that overflows and is not in the note is flagged 'kind not yet checked' until Claude checks it by hand and adds it. After Phase 5: backlog C7 (strata-compare results/BACKLOG-1027.md) - how often across all runs + options, desk first.
* 2026-11-07 14:46 RESEARCH PAUSE (Karl 11-07: 'I want to use the PC. Hold the research queue at the next question boundary, don't interrupt anything running'): run/pause-window + strata-compare tmp/quiet-window = 2026-11-07 14:46 2099-12-31 23:59 (no question starts, no gap opens; the running holdout deep p5final o04, started 13:48, runs to its end); marker strata-compare tmp/research-pause. Released by 'Resume research' (icon being built) or by removing both files.
* 2026-11-07 14:50 RESEARCH PAUSE ICONS (Karl 11-07): 'Pause research' / 'Resume research' on the Desktop + applications (trusted, executable) -> strata-compare configs/usability/bin/research-pause.sh pause|resume|status|check. Pause = run/pause-window + strata-compare tmp/quiet-window (now -> 2099-12-31 23:59) + marker tmp/research-pause; never interrupts; user unit research-pause-wait sends a desktop notification when held (two looks 45 s apart); closing the window does not cancel; survives a reboot; no model switch. Resume removes only its own windows, names any other hold. Sandbox test of the real file: work/ds-launcher/research-pause/test_research_pause.sh 23/23. Live: the current pause adopted, waiter pid 1198811, held expected ~16:39 (holdout deep p5final o04).
* 2026-11-07 16:40 RESEARCH PAUSE: held (the queue's last question finished; nothing new starts until Resume research).
* 2026-11-08 02:40 RESEARCH RESUMED (the Resume research icon): the pause windows removed.

11-09 04:21 Strata v0.2.13 (found by the tag watch) changes our Qwen build's path: 420 files since v0.2.9 (CMakeLists.txt (build: +14: include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/strata_geometry.cmake)   # -DSTRATA_GE; +17: include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/strata_ggml.cmake)          # which gg; +18: include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/backends/cpu.cmake)         # strata_k ...); cmake/backends/cpu.cmake (engine set unknown: no build folder for /home/USER/ai-speed-testing/strata-compare/en; /home/USER/ai-speed-testing/strata-compare/logs/r21/tagcheck-v0.2.9-v0.2.13.json). FLAGGED for Karl's decision; measurements carry on on the served build (Karl 10-31: only installing or switching engines waits for him). Review read-only; after his decision: work/r22/tagcheck.sh --accept v0.2.13.
* 2026-11-09 07:10 PHASE 5 queue finished: kcheck p5-queue-finished OK (RULES-p5 4 Q6; weekend-watch).

* 2026-11-09 07:14 phase 4 gap BEGIN (r23 v0.2.11 port confirmation gap: B vs P with and without --chat-cache 0 on R2 / R3 (measurements only; P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 07:42 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 07:46 phase 4 gap BEGIN (Basalt speed gap: A, T, U, C-stack on engine-r23basalt-fix and U on P028x, priced against B and P028x (measurements only; P028x stays served, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 08:00 power key back to suspend (power-key-revert.timer, Karl 11-05: ignore until Monday morning)
* 2026-11-09 09:38 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 09:41 phase 4 gap BEGIN (DeepSeek gap D1: C2 / C3 / C4 speed, C's KL check, C's long-prompt arm (Karl 11-07; work/ds41/gate/gap-d1.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 10:50 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 10:53 phase 4 gap BEGIN (DeepSeek gap D2: C's sampled-distribution test on D1's winner, the 1017-drafter probe (Karl 11-07 / 11-08; work/ds41/gate/gap-d2.sh)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 11:28 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 11:31 phase 4 gap BEGIN (U adoption: STRATA_HC_UPMIX=1 into P028x's config with the mismatch guard (Karl 11-09), exact7 + a short speed check, then one restart): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 11:39 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

11-09 12:21 Strata v0.2.13.1 (found by the tag watch) changes our Qwen build's path: 420 files since v0.2.9 (CMakeLists.txt (build: +14: include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/strata_geometry.cmake)   # -DSTRATA_GE; +17: include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/strata_ggml.cmake)          # which gg; +18: include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/backends/cpu.cmake)         # strata_k ...); cmake/backends/cpu.cmake (engine set unknown: no build folder for /home/USER/ai-speed-testing/strata-compare/en; /home/USER/ai-speed-testing/strata-compare/logs/r21/tagcheck-v0.2.9-v0.2.13.1.json). FLAGGED for Karl's decision; measurements carry on on the served build (Karl 10-31: only installing or switching engines waits for him). Review read-only; after his decision: work/r22/tagcheck.sh --accept v0.2.13.1.

* 2026-11-09 15:39 phase 4 gap BEGIN (v0.2.13 shape gap: our port's parity programs and a smoke start at q4_mid / q4_big / q4_deep (Karl 11-09; information only, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* kwatch fired (KERNEL ERROR, 2026-11-09 15:56): 2026-11-09T15:56:43-06:00 HOSTNAME kernel: NVRM: Xid (PCI:0000:01:00): 31, pid=378329, name=gr_parity, intr 00000000. MMU Fault: ENGINE GRAPHICS GPC0 GPCCLIENT_T1_1 faulted @ 0x100_16000000. Fault is of type FAULT_PDE ACCESS_TYPE_VIRT_READ -- It stopped the Strata engines and server wrappers; the kernel-log tail is in strata-compare logs/r19/kwatch.log. To clear it after your check: rm ~/ai-speed-testing/strata-compare/tmp/r19/KERNEL_ERROR; systemctl --user restart kwatch; then ~/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh must exit 0 (a taint bit W/D/M/B/L in /proc/sys/kernel/tainted, now 4096, clears only with a reboot).
* 2026-11-09 16:18 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 16:29 phase 4 gap BEGIN (v0.2.13 shape gap: our port's parity programs and a smoke start at q4_mid / q4_big / q4_deep (Karl 11-09; information only, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 17:02 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 17:05 phase 4 gap BEGIN (v0.2.13 shape gap: our port's parity programs and a smoke start at q4_mid / q4_big / q4_deep (Karl 11-09; information only, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 17:08 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 17:37 phase 4 gap BEGIN (ADAPT_FETCH gap: P028x vs STRATA_ADAPT_FETCH=1 / =2 on the fetch build, helper GPU on (Karl 11-09; measurements only, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 19:03 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha f4c4f654fb24), chat-cache parking policy on; queue resumes.

* 2026-11-09 19:55 phase 4 gap BEGIN (ADAPT_FETCH=2 adoption: P028x on the fetch build with STRATA_ADAPT_FETCH=2 (Karl 11-09), exact7 + a short speed check, then one restart): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-09 20:06 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha 153ce47d3ef0), chat-cache parking policy on; queue resumes.
* 2026-11-09 22:15 STOP MODEL (the launcher): the queue held, the test lock taken, strata-qwen3.8-flash-next-iq3s on 8080 to stop.
* 2026-11-09 22:16 STOP MODEL: stopped (VRAM and RAM freed, 86.8 GiB RAM available); nothing restarts until Back to Qwen, Jan or DS Harness.
* 2026-11-09 22:21 STOP MODEL ended (opening Jan): P028x back on 8080, the test lock and the queue released.
* 2026-11-09 22:48 STOP MODEL (the launcher): the queue held, the test lock taken, strata-qwen3.8-flash-next-iq3s on 8080 to stop.
* 2026-11-09 22:49 STOP MODEL: stopped (VRAM and RAM freed, 87.1 GiB RAM available); nothing restarts until Back to Qwen, Jan or DS Harness.
* 2026-11-10 07:14 REBOOT (staging/post7d/boot-resume.sh): the PC rebooted (boot 2026-11-10 07:14:20). Interrupted: question: none running (the last one, p5-o01 / deep / p5final / o01: running, ended); a gap was OPEN (port-gap.lockpid 1242655, 8080 down; hold: phase 4 gap: Model stopped (the Stop model launcher, requested 2026-11-09 22:46:10): nothing starts a model until Back to Qwen); bench unit on queue-plan-p5-holdout.json; was active: ds-session-lock; the previous boot shut down cleanly (last journal entry 2026-11-09 22:53:42). Resuming at the next clean boundary after the kernel check (Karl 11-05).
* 2026-11-10 07:14 REBOOT (staging/post7d/boot-resume.sh): outcome - NOT resumed: ds-session-lock (/bin/bash /home/USER/ai-speed-testing/strata-compare/configs/usability/bin/deepseek-session.sh lock-holder) was active - not restarted (unknown to boot-resume); Claude checks | done: boot check passed (boot-check.service: 2026-11-10 07:14:29: kcheck ok, previous boot's kernel log clean after kwatch's start, clean shutdown); removed the stale tmp/port-gap.lockpid (pid 1242655, written before the boot); removed the stale tmp/ds-session; 8080 up: engine 153ce47d3ef0 (P028x), policy on; removed the stale tmp/bench2.hold - the queue goes on (an interrupted question reruns from the start)
* 2026-11-10 09:42 VERSION CHECK BACK ON in Jan's deep jobs (Karl 11-10): the fix installed in LDR's deep/checks.py (patch results/bench2/fixes/version-fix-1110/version-fix-1110.patch; sha 32a5d54be43e = the staged file; backup checks.py.before-versionfix1110), research-runner.py back to its pre-11-09 lines JOB_DEEP_FIX 'all,read,claims,steps' / ITEMS code fixes read claims fix:steps (= the bench's p5final; backup .before-versionon1110), staging/post7d/tests/test_runner_daily.py likewise (ALL OK), installed while no Jan job, bench run or LDR was live; runner restarted pid 1837 -> 289005. Next: one live check on o01 / o04 / o05 in a quiet window outside any gap; then delete trees/ (Karl's OK).
* 2026-11-10 10:0x VERSION CHECK LIVE CHECK (Karl 11-10; results/bench2/fixes/version-fix-1110/live-check.txt; replays live-version-1110-o01/o04/o05): o01 9 marks (STRATA_ADAPT_HELPER x5, COST_GATE x1, DISJOINT_ADAPT x3 - all true; STRATA_WARM not marked this time), o04 0, o05 10 FALSE marks on 2 names the stored answers never had: model_type x8, architectures x2 (kind other-project, use described: the report quotes the model card's config.json key correctly) - so Karl's condition is NOT met live on o05. The check stays ON (Karl's instruction) until he decides. trees/ (181 MB, git archives of strata v0.2.4 / v0.2.6) deleted per Karl.

* 2026-11-10 11:01 phase 4 gap BEGIN (v0.2.13 switch checks: the v0.2.13 port against the daily (Karl 11-10; measurements only, nothing switches)): queue held after its run, test lock taken, P021 on 8080 stopped.
* 2026-11-10 11:47 phase 4 gap END: the served build (configs default, P028x since 10-30) back on 8080 (engine sha 153ce47d3ef0), chat-cache parking policy on; queue resumes.
