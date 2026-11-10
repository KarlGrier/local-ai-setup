# Local Deep Research on Strata — deep-research setup

LDR **1.10.7** in `/home/USER/ai/deep-research`, tuned for the deepest research the machine can do: hours per
question are fine, answer quality and source coverage are what count. LLM: Strata on 127.0.0.1:8080 (through
strata-proxy on 8090). Search: **LDR's own SearXNG on 127.0.0.1:8889** (web + academic engines). Everything listens
on 127.0.0.1 only; venvs, caches, data and results live in this folder. Running log: `NOTES.md`.

## Research from Jan (since 2026-10-17)

In Jan, ask for it in plain words, e.g. *"Do a deep research: which 16 GB card should I add as a third GPU? Use
my notes in ~/notes/gpu.md"*. Jan's model calls the **deep-research** tools (an MCP server Jan starts:
`tools/research-mcp.py`):

| tool | what it does |
|---|---|
| research_start(question, files, time_budget_minutes) | queues a job (default 3 h of research, then the report); files = full paths of files or folders |
| research_quick(question) | a quick answer with sources for a factual question (plain LDR's quick summary, ~1-3 min): returned directly if ready within `quick_wait_seconds`, else read it with research_report |
| research_status(job) / research_list | progress: stage (researching / writing the report / checking citations), research time used and left, searches and pages read, the sub-question being researched, the latest findings (one line each), what it is waiting for / all jobs |
| research_inbox | lists the files in `~/ai/deep-research/inbox` |
| research_pause / research_resume / research_cancel | between model calls; a paused job's research clock stops |
| research_report(job, part) | the report in parts of ~12,000 characters, plus the paths of its .md and .html files |

* **Jobs** run one at a time in the order asked, by the user service `deep-research-runner.service`
  (`tools/research-runner.py`), so they keep going with Jan closed. Everything is on disk (`jobs/<id>/job.json`).
  A desktop notification comes when a job finishes or fails; reports land in `reports/` as `.md` and `.html`.
* **Strata:** started on demand when 8080 is down (the app launchers' `strata-ensure.sh`). Research waits while a
  test holds strata-compare's measurement lock (test scripts call `bringup/lib/research_wait.sh` after taking it, so
  the research pauses at its next step), and **yields to you**: while Jan, the chat page or a coding tool used Strata
  in the last 5 minutes, the research holds between its model calls (strata-proxy's gate).
* **Night:** research pauses between model calls at 23:00 and continues at 09:00 (the research clock stops); a job
  asked at night starts at 09:00. **PC off** during a job: it continues as a new run seeded from everything the
  earlier run saved (sources keep their [N], pages read are not downloaded again, findings and notes are given to
  the lead), with the research time that was left.
* **Inbox (since 2026-10-19):** put files in `~/ai/deep-research/inbox` and say "use my inbox": research_start gets
  `use_inbox: true` and the files are copied into the job when it is queued, so the inbox can be emptied right after.
  Jan itself cannot help here. In a normal chat it does not pass attachments to MCP tools and keeps no copy: it reads
  the file where you picked it and either puts the text into the conversation or indexes it into its own database. The
  model sees only name, type and size, not the path. Only Jan's separate "Cowork" agent mode copies attachments into a
  workspace folder.
* **Notifications:** research done and report started; report written and citation check started; finished or failed.
* **Into the inbox:** in Files, right-click > Scripts > **Send to research inbox** (copies; `-2` on a name clash), or
  open it with the **Research inbox** launcher (app menu and desktop). Jan's Cowork mode cannot fill it: its
  attachments always go to its own session workspace in Jan's data folder.
* **Semantic Scholar (since 2026-10-19):** your research also gets LDR's own Semantic Scholar engine (official API,
  no key) as an agent tool, with its LLM relevance filter and journal-quality filter off (in September the relevance
  filter flooded Strata). Not in measurements until phase 4. A key can be added later
  (`search.engine.web.semantic_scholar.api_key`).
* **Search fallback (built 2026-10-19; each service dormant until its key file in `~/.config/deep-research/` exists):**
  - What it does: when SearXNG fails or returns too few results (LDR: fewer than 5; the chat page: fewer than 3; Jan's
    web_search: fewer than 5), Exa (Lite search, with each page's highlights) is asked first, then Tavily if Exa is
    off, over its cap, failed or found nothing (`tools/search_fallback.py`).
  - Scope: Jan's research (the runner starts LDR with `LDR_SEARCH_FALLBACK=1` once either key exists), the chat page
    and Jan's web_search; never in measurements (bench2 refuses).
  - Limits: Exa $9.00 a month (`exa.key`, counter `exa-usage.json`; Exa's free credit is $10 a month, Lite is $4 per
    1,000 searches, so about 2,250 searches; HTTP 402 "out of credit" closes the month); Tavily 950 searches a month
    (`tavily.key`, `tavily-usage.json`). The keys are never printed or logged; uses in `logs/exa-fallback.jsonl` and
    `logs/tavily-fallback.jsonl`.
* **Earlier reports (since 2026-10-19):** an earlier research report is a starting point, not a source. research_report
  dates every report, heads one from an earlier Jan session "EARLIER REPORT - finished <date>" with the rule (say so,
  re-check anything that changes over time with a fresh search, mark points re-checked or carried over unchecked, never
  state unchecked points as current fact, call out what changed), and without a job id lists the finished reports
  instead of returning the newest. LDR's own library is not a search source in any run (search.tool = searxng).
* **Web search in Jan (since 2026-10-19):** the `web-search` MCP server (`tools/web-mcp.py`, the LDR venv's Python):
  - `web_search`: SearXNG (8889) first, then Exa, then Tavily as above; `source` = auto / searxng / exa / tavily;
    each result says which service answered.
  - `fetch_page`: the page's main text (trafilatura; PDFs via pdftotext), 8,000 characters by default (up to 30,000),
    or Exa's highlights for a page an Exa result returned (`full: true` opens the page). Only public addresses.
  - Jan's own built-in web search (it used the chat page's SearXNG on 8888) is switched off, so the model sees one
    search tool; Settings > Web search turns it back on. Log: `logs/web-mcp.log`.
* **Files:** Jan cannot hand attachments (also not Project files) to a tool: give paths, or use the inbox. The research reads them
  itself in parts of 120,000 characters (PDF, Markdown, text, code, HTML) with a `read_file` tool, and cites them
  with [N] like web pages.
* **Which tool (since 2026-10-19):** Jan answers with web_search + fetch_page by default; research_quick only when you ask
  ("quick research on ..."), research_start only when you ask for deep research. A quick answer runs LDR with no
  subtopic agents and at most 12 agent cycles (measurements never). While a measurement run holds LDR it cannot start:
  you get "NOT STARTED" and a web_search answer that says so. Failed research is labelled FAILED / CANCELLED.
* **Quick answers** (since 2026-10-18): a `research_quick` job runs plain LDR's quick summary (LDR restarted in the
  baseline profile; Strata's default effort) - the setup that answered all 10 hard checkable test questions and all
  15 easy ones in 1-2 min each. It goes before queued deep jobs (not before a running one, nor during a measurement
  run), does not yield to your chats, and is stopped after 15 min. The next deep job switches LDR back to the deep
  profile (a few seconds). Jan's MCP tool timeout is 30 s, so the answer usually comes back through research_report.
* **Settings** (`research.conf`, read every few seconds): `yield_minutes` (5; 0 = never yield), `night_pause`
  (23:00-09:00; off), `default_budget_minutes` (180), `max_budget_minutes` (600), `ldr_idle_stop_minutes` (15),
  `quick_wait_seconds` (25; keep it under Jan's tool-call timeout).
* **Logs:** `logs/research-runner.log`, `logs/research-mcp.log` (every tool call with its arguments),
  `logs/llm-calls.jsonl` (every model call; `"tooltag"` marks an answer cut off by tool-call text in prose - counted
  per job in research_status and in the report header).

## Start a deep research job

```bash
~/ai-speed-testing/strata-compare/switch-model.sh strata   # only if Strata isn't up already
~/ai/deep-research/run-ldr.sh start      # LDR (deep profile) + strata-proxy + LDR's SearXNG (8889)
~/ai/deep-research/run-ldr.sh status
```

**In the browser:** http://127.0.0.1:5000, user **karl** (password in `run/ldr-credentials`). Keep the strategy on
**langgraph-agent** and the mode on **Quick Summary** (the deep report replaces LDR's quick answer; do not use
"Detailed Report": LDR issue #6640, see below). The finished report is in **History**.

**From the shell** (writes everything to `results/TAG/`):

```bash
cd ~/ai/deep-research
.venv/bin/python tools/ldr-client.py research my-topic "your question"      # waits; prints a summary at the end
# results/my-topic/deep/report.md          the report (+ Sources), with the citation check at the end
# results/my-topic/deep/verification.json  every checked claim: verdict, quote from the page, note
# results/my-topic/deep/evidence.jsonl     every search result, every page read (full text) and extraction
# results/my-topic/deep/subagents.md       the subagents' findings
```

**Budget:** `LDR_DEEP_TIME_BUDGET_S` (default **10800 = 3 h** of research), then the report stage. Change it with
`LDR_DEEP_TIME_BUDGET_S=5400 ./run-ldr.sh restart` (it applies to the next research). The other knobs are listed
at the top of `run-ldr.sh`.

**How long to expect:** the research budget (default 3 h, plus ~5–10 min while subagents finish their last step),
then the report stage: ~4 min per section at xhigh (8–9 sections ≈ 40 min) and the citation check, ~3.5 min per 8
checked claims (default 120 claims ≈ 50 min; `LDR_DEEP_VERIFY_MAX_CLAIMS=0` checks all, which took ~3 h for a
400-claim report). **A default run takes about 4.5–5 hours.** Measured on 60-min runs: ~2.2–2.5M tokens processed,
Strata generating at ~100–105 tok/s the whole time. Cancel from the UI or `POST /api/terminate/<id>`; agents stop
between steps. The report is saved as `report-unverified.md` before the citation check starts.

**Status (2026-09-30 15:00): measurements paused at your request** — see "Measurements" below and "Resume".

## What a deep run does

Profile **deep** (`run-ldr.sh`'s default; `LDR_PROFILE=baseline` runs pristine LDR 1.10.7 for comparisons). The
changes to LDR are patch files in `patches/ldr/` (`apply.sh apply|revert|status`); 0001-0003 act only with
`LDR_DEEP=1`, which `run-ldr.sh` sets. **0004 (2026-10-18) acts in both profiles** (also applied to the baseline's copy,
`baseline/site/`): LDR fetches one page at a time. Pages fetched in parallel threads ran trafilatura's lxml parsing and
tree copies at the same time and corrupted the heap ("double free or corruption"; ldr-web crashed 10-18 20:14;
reproduced outside LDR 3/40 on both Python 3.12.3 and 3.12.13, 0/40 one at a time). LDR already serializes the
extractors within one page for the same reason. `.venv` runs **CPython 3.12.13** (uv's standalone build in
`searxng/python/`) since 10-18; the old 3.12.3 venv is kept as `.venv-py3.12.3`. `ldr-web` runs with
`PYTHONFAULTHANDLER=1`, so a crash leaves its Python stacks in the LDR log.

1. **Lead agent** plans the question, searches, reads pages and sends batches of up to 8 subtopics to subagents;
   it is told to research every sub-question, read primary sources and confirm key facts in two sources.
2. **Subagents** research one subtopic each (up to 30 model calls, their share of the budget) and return detailed
   findings with [N] source indices.
3. **Search**: one tool, LDR's SearXNG — web engines + arXiv, Semantic Scholar, PubMed, Europe PMC, Crossref, Google
   Scholar; 50 results per search. `!science`, `!arxiv`, `!pubmed`, `!gos`, `!se` inside a query target academic
   engines. No per-engine relevance-filter calls.
4. **Reading a page**: up to 120,000 characters of it go to an extraction step that returns up to 4,000 characters
   of verbatim quotes. Every page read is kept in full in the evidence store.
5. **When the budget runs out** every agent is told to wrap up and loses its tools; the lead writes its answer.
6. **Report**: an outline from everything gathered, one call per section with that section's page evidence, then
   Answer / Key findings / Limitations. If the question prescribes an answer format, the Answer keeps it.
7. **Citation check**: every sentence that cites sources is checked against the stored text of the sources it
   cites; unsupported and partly supported sentences are flagged inline and listed in a table.

| cap | upstream 1.10.7 | deep |
|---|---|---|
| lead agent model calls | 50 (UI max 100) | 200 |
| subagent model calls | 8 | 30 |
| subagent time | hard kill at 1,800 s (its work is lost) | fair share of the budget (≤ 1 h), then wrap-up |
| subtopics per call | 5 (hard limit 10) | 8 (hard limit 12) |
| page text per fetch | 10,000 chars | 120,000 chars |
| extraction output | 1,500 chars | 4,000 chars |
| results per search | 15–50, from an engine set that returned 0 here | 50 (60–160 available per query) |
| research time | until the agent stops (≈25 min in yesterday's test) | budget, default 3 h |

**Context:** Strata takes prompt + max_tokens ≤ 131,072. Every agent's history is compacted when it passes 56K
tokens (exact count with the model's vocabulary): older steps become research notes that keep every finding with
its [N], plus a list of the sources and searches involved; the recent steps stay verbatim. Before every call the
request is checked against the limit (the largest tool results of that request are shortened if needed), and
strata-proxy retries a context-400 with max_tokens reduced to fit.

## Search: LDR's own SearXNG (why the old one crashed)

`searxng/searxng.sh start|stop|status` (run-ldr.sh starts it): 127.0.0.1:8889, SearXNG master (2026-09-30) under
granian 2.8.3 on **CPython 3.12.13** (uv's standalone build in `searxng/python/`), with a keeper loop that restarts
it if it ever exits (logged in `searxng/logs/searxng-main-events.log`).

* **The crash:** Ubuntu's Python 3.12.3 lacks the fix for CPython bug gh-119585. When granian's extra worker thread
  exits after 30 s idle, a destructor that re-enters the GIL API deletes the thread state while Python code is still
  running on it (kernel log: segfault inside `_PyEval_EvalFrameDefault`, a write into the freed frame stack).
  granian spawns extra threads only when requests overlap — LDR's parallel searches do, the chat page's one-at-a-time
  searches never do, which is why only LDR crashed it. Reproduced: a minimal app 3/3 on 3.12.3, 0 on 3.12.13; real
  SearXNG with LDR's own client and yesterday's queries crashed 2/2 on 3.12.3 (within 3–4 idle periods) and survived
  30 idle periods on 3.12.13. Which SearXNG object carries the re-entering destructor is not identified (SearXNG
  leaves no thread-locals or context variables in granian's threads). Details: NOTES.md 2026-09-30.
* **Soak:** 4 h of LDR's request pattern (bursts of 2–6 concurrent searches, idle gaps longer than the thread
  timeout): **1,108+ searches, 0 failures, 0 restarts**; plus every LDR run today on real engines: 0 restarts.
* **Engines** (measured from this address): the old set (Brave + "google cse") is suspended here and returned
  **0 results**; now google, duckduckgo, startpage, bing (weight 0.5), yahoo, yandex, yep, seznam, mwmbl, Wikipedia,
  Wikidata, and academic: arXiv, Semantic Scholar, PubMed, Europe PMC, Crossref, Google Scholar (60–160 results per
  query). "Too many requests" suspensions last 120 s instead of 3600 s (PubMed's keyless API allows 3 req/s).

## Thinking effort (measured, chosen by quality)

| call type | effort | evidence |
|---|---|---|
Since 2026-10-20 (your decision after the phase 3 replays): medium everywhere except the citation check.

| call type | effort | evidence |
|---|---|---|
| agent / planning steps | **medium** (proxy mode file) | the hard five graded blind: 5/5 at both; xhigh 4.2x the time. `results/bench2/CHECKPOINT-phase3.md` §3 |
| page extraction | **medium** (proxy mode file) | 30 replayed extractions, blind: no level better (first: low 10 / medium 12.5 / xhigh 5.5); xhigh 6.3x medium's tokens. Same verdict as the blind re-judging of the 36 older tasks. `results/bench2/replays/extract/` |
| report writing | **medium**, up to 60K output tokens (LDR start env) | o01-o03 rewritten at both, two graded blind: medium 31 / xhigh 31.5 of 34; xhigh 3x the time. `results/bench2/replays/report/` |
| citation check | **xhigh** (LDR start env) | 120 claims at both, the 24 differences judged blind: medium passed 10 claims that should be flagged, xhigh 1. `results/bench2/replays/verify/` |
| history compaction | medium | xhigh once thought 30,000 tokens without answering (249 s) |

Any deep call that ends at max_tokens without an answer is retried one effort lower.
* **Where each setting lives:** the research runner sets agent and extraction through strata-proxy's mode file
  (`DEEP_EFFORTS`). It sets report writing and the citation check in LDR's environment at start
  (`DEEP_LDR_EFFORTS` → `run/ldr.efforts`).
* **When LDR is restarted:** the runner restarts LDR when `run/ldr.efforts` does not match.
* **Measurements:** bench2 and ldr-client set their own efforts and are unchanged.

## Subagent workers

Strata answers one request at a time; with 1 worker it was busy 96.6 % of a 60-min research hour, so extra workers
can only fill the last few percent — or change how the time is shared. Research hour, one run each
(`results/workers-compare.md`):

| | 1 worker | 2 workers | 4 workers |
|---|---|---|---|
| generated tok/s | 101.5 | 104.6 (+3 %) | not run |
| Strata busy | 96.6 % | 99.9 % | |
| pages with findings / searches | 23 / 35 | 30 / 41 | |
| subagents finished / findings text | 8 / 132K chars | 6 / 87K chars | |
| agent prompt tokens re-read (cache evictions) | 160K | 224K | |

Answer quality was not compared (both runs were stopped before their reports were saved; the report is now saved
before the citation check). Default stays at **1 worker** until the 4-worker run and a report comparison are done.

## Measurements

| step | status | where |
|---|---|---|
| SearXNG crash cause, fix, soak | done | `searxng/tests/`, `searxng/logs/` |
| extraction effort test | done (xhigh) | `results/extract-effort/summary.md` |
| citation-check effort / design | done (xhigh, joint per claim) | `results/deep-runs/research-6f922fd5…/verification-medium*.json` |
| smoke test (15-min budget, full pipeline) | done: 8 sections, 70 sources cited, 260 claims checked | `results/smoke2-deep/` |
| workers 1 / 2 / 4 | 1 and 2: research hour only; 4 not run | `results/workers-compare.md` |
| baseline vs tuned benchmark (3 BrowseComp, 3 FRAMES, 2 open-ended) | **not run** (paused) | questions: `results/bench/questions.jsonl` |

## Resume the measurements

```bash
cd ~/ai/deep-research
# workers test, then the baseline (pristine LDR 1.10.7 + the old engine set on a crash-free server):
LDR_DEEP_VERIFY_MAX_CLAIMS=40 OPEN_BUDGET=3600 setsid nohup tools/queue-measure.sh workers1 workers2 workers4 baseline \
  > logs/queue-measure.out 2>&1 &
# then, with the chosen worker count:
WORKERS=1 LDR_DEEP_VERIFY_MAX_CLAIMS=40 MULTI_BUDGET=2400 OPEN_BUDGET=3600 setsid nohup tools/queue-measure.sh tuned grade \
  > logs/queue-measure2.out 2>&1 &
tail -f logs/queue-measure.log          # results/bench/results.md at the end
```

Budget: ~2 h per open-ended run and ~1.2 h per multi-step run (tuned), ~0.5 h per baseline run. Before the tuned
phase: budget the subagents' wrap-up overrun into the fair share (in both 60-min runs the lead got only 1 model call).
## Proposals (not applied: strata-compare is yours, and Strata must not restart before ~04:10 Thu Oct 2)

### A. Strata at 262K context — possible, modest gain for LDR; measure first
* The model supports it natively: the GGUF says `qwen4exp.context_length = 262144` (48 layers, full attention every
  4th layer, 2 KV heads, a sparse top-2048 indexer). C\*7 runs `--max-context 131072`.
* What it would change for LDR: the lead agent could keep ~2× more history verbatim before compaction, and each
  report-section call could carry ~2× more page evidence (48K → ~100K tokens). It is not needed for correctness:
  with compaction and the per-call guard no deep call exceeds 131,072, and the largest prompts in the runs were
  93,432 tokens.
* Costs: prompt reading scales roughly linearly with sparse attention (120K = 35 s on C\*7, so ~75–85 s at 250K);
  each conversation's KV is ~23–25 KB/token (parked 11,471 tokens = 280 MiB, 27,235 = 622 MiB), so a full 262K
  conversation is ~6 GB instead of ~3 GB (host RAM beyond the 32K resident tokens). MemAvailable is ~31 GB with
  Strata at 52.6 GB RSS: fine for one request, but the chat cache (16 GiB budget) can hold fewer long
  conversations. Accuracy above 120K is unmeasured on this quant (the needle tests went to 120K).
* If you want it: after the monitor, a `Cstar7-262k.json` with `--max-context 262144`, then run the needle test at
  200K/250K, watch MemAvailable during a 250K prompt, and time it; then `LDR_DEEP_CONTEXT_TOKENS=262144
  LDR_DEEP_COMPACT_AT=110000 LDR_DEEP_REPORT_EVIDENCE_TOKENS=100000 ./run-ldr.sh restart`.

### B. The chat page's SearXNG (8888): same crash, and it returns nothing right now - **DONE 2026-10-19** (CPython
3.12.13 venv + the working engine set; see strata-compare NOTES.md "search reliability")
* It runs granian on Ubuntu's Python 3.12.3, so it has the same crash whenever requests overlap (the chat page sends
  one search at a time, which is why it survived round 5; round 7's two overlapped agents could trigger it).
* It currently returns **0 results**: its only web engines are Brave and "google cse", both suspended from this
  address ("too many requests"); checked 08:13 today.
* Options, smallest first: (1) add `--blocking-threads 1` to `websearch/searxng.sh` (no extra threads, so no thread
  exits; searches queue, fine for one chat); (2) rebuild `websearch/venv` on CPython 3.12.13 (`uv python install
  3.12` into the workspace, as done here); (3) enable the engines measured to work here (google, duckduckgo,
  startpage, bing, yahoo, yandex, yep, seznam, mwmbl; see `searxng/settings.yml`), or point the chat page's
  `web_search.searxng` at LDR's instance on 8889.

## What's left

1. **Measurements** (paused): w4, baseline vs tuned benchmark, grading, your read of the two open-ended reports.
2. **Lead reserve:** subagents overrun their fair share by 1.5–5 min (an xhigh extraction in flight + the wrap-up
   answer), so in a 60-min run the lead gets no follow-up round. Budget the overrun into the share.
3. **Report sources:** ~85 % of cited sources in the smoke run were search snippets the agents never opened; the
   citation check catches unsupported ones, but the outline could prefer read pages.
4. **The SearXNG object** whose destructor re-enters the GIL API is not identified (the fix does not depend on it).
5. Strata proposals above (262K context; chat-cache budget / a "don't park" flag; the chat page's SearXNG).

## Files

| what | where |
|---|---|
| launcher (profiles deep / baseline) | `run-ldr.sh` |
| LDR patches (+ apply/revert, regenerate) | `patches/ldr/` (`apply.sh`, `make-patches.sh`); pristine copy for baseline runs: `baseline/site/` |
| LDR's SearXNG | `searxng/` (`searxng.sh`, `settings.yml`, `settings.baseline.yml`, crash reproductions in `tests/`) |
| proxy (call log, context guard) | `tools/strata-proxy.py`, log `logs/llm-calls.jsonl` |
| research client / benchmark / tests | `tools/ldr-client.py`, `tools/bench.py`, `tools/queue-measure.sh`, `tools/extract-effort-test.py`, `tools/verify-effort-compare.py`, `tools/workers-compare.py`, `tools/strata-idle.py` |
| research from Jan (since 10-17) | `tools/research-mcp.py` (MCP), `tools/research-runner.py` + `systemd/deep-research-runner.service`, `tools/research_common.py`, `research.conf`, `jobs/`, `reports/` |
| proxy gate tests | `tests/gate/test_gate.py` (+ `fake_strata.py`; 16 offline checks) |
| phase 3/5 measurements | `tools/bench2.py` (run / grade / sort), `results/bench2/` (PLAN.md, questions, answers, runs) |
| model vocabulary (token counting) | `deep/tokenizer/` (copied from strata-compare's pack) |
| deep runs (evidence, report, checks) | `results/deep-runs/research-<id>/` |
| running log | `NOTES.md`; yesterday's README: `tmp/README.2026-09-29.md` |
