# Audit: what our LDR build tunes for Qwen3.8-Flash-Next (2026-10-27)

Code-reading audit, read only. Nothing was run or changed.

**Build audited:** stock LDR 1.10.7 (`src/whl/`) against our patches 0001-0005 as of 10-27 07:59.
For the six files that the six-fix work is changing now, the pre-fix copies in
`tmp/backup-2026-10-27/*.before-fixes` were used (report.py, setup.py, advisory.py, codetool.py, prompts.py,
langgraph_agent_strategy.py). `deep/checks.py` and everything behind `LDR_DEEP_FIX` are left out.
`run-ldr.sh` = its `.before-fixes` copy (the live file only adds the `LDR_DEEP_FIX` item line).
Not read: jobs/, reports/, results/deep-runs/, results/quick-runs/, data/, credentials.

**Where (short forms):**
- `deep/X.py`: `.venv/lib/python3.12/site-packages/local_deep_research/deep/X.py`. For report, setup, advisory,
  codetool and prompts the line numbers are from the pre-fix copies.
- `strategy`: `langgraph_agent_strategy.py`, pre-fix copy.
- `fetch`: `advanced_search_system/tools/fetch/__init__.py`.
- `fetcher`: `content_fetcher/fetcher.py`.
- `sx-engine`: `web_search_engines/engines/search_engine_searxng.py`.
- `proxy`: `tools/strata-proxy.py`.

**Tags in the "why" column:**
- [ctx]: sized to Strata's 131,072-token context.
- [speed]: sized to Strata's one-request-at-a-time, ~100 tok/s decode, or to the run's wall time.
- [model]: chosen from Flash-Next's measured behaviour.
- [Strata]: a workaround for the server, or for sharing the PC with it.
- [design]: general deep-research design, not tied to the model.
- [host]: the PC or the network.

## 1. Summary

- 73 changes to stock LDR 1.10.7 were found. 30 are settings, 28 are hard-coded, and 15 are mixed: the main number is a
  setting, but limits or wording around it are fixed.
- Most of the tuning follows from two facts about Strata: a 131,072-token context, and one request at a time at
  ~100 tok/s. The other changes are depth choices that are not model-specific, or workarounds for Strata.
- The [ctx] budgets would hold a frontier model back most:
  - compaction at 56K tokens;
  - 16,000 chars of each subagent report for the lead;
  - 300-char snippets;
  - 48K tokens of evidence per report section, 12K of findings;
  - output capped at 60K tokens.
- Also limiting:
  - 1 subagent worker;
  - the 200 / 30 step limits, which a fast model reaches long before the 3 h clock;
  - 120 checked claims with 2,000 tokens per cited source;
  - the code tool's short reads ("never whole files").
- Every reasoning-effort choice was measured on Flash-Next only: medium for the agent, extraction, report writing and
  compaction, and xhigh for the citation check.
- Agent and extraction efforts reach the model only through strata-proxy, because LDR 1.10.7 cannot send
  `reasoning_effort` on its own calls. An API model without the proxy would get no per-class effort.
- These are Strata workarounds an API model should skip:
  - the proxy's context-400 retry, research gate and chat-cache fields;
  - the memory guards;
  - the "length with no answer, retry one effort lower" ladder.

## 2. Findings by area

### 2.1 Search and fetching

| item | value (stock -> ours) | where | why (notes) | limits a stronger model? | setting or hard-coded |
|---|---|---|---|---|---|
| Results per web search | SearXNG 15 -> 50 (LDR's max) | run-ldr.sh:123 | 50 is LDR's maximum; our SearXNG returns 60-160 per query [design] | No: more results only help | Setting: `LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_MAX_RESULTS`, `LDR_SEARCH_MAX_RESULTS`. (`LDR_DEEP_SEARCH_RESULTS` is read into the config but nothing uses it.) |
| Search categories | general -> general + science | run-ldr.sh:122 | One search reaches the web and academic engines [design] | No | Setting: `..._DEFAULT_PARAMS_CATEGORIES` |
| Snippet length the agents see | full -> 300 chars (store keeps the full one) | strategy:1192-1193; deep/__init__.py:65 | "A 50-result search cost ~11K tokens of context uncut" (NOTES 09-30) [ctx] | Yes: a 200K-1M model can read full snippets. At 300 chars the dates and figures that decide which page to open get cut | Setting: `LDR_DEEP_SNIPPET_CHARS` |
| Page text given to extraction | 10,000 -> 120,000 chars | fetch:54-62; deep/__init__.py:57 | Depth (NOTES 09-30). ~30K tokens fits beside the prompt in 131K [ctx] | Maybe: a frontier model could read long PDFs whole. The user's file parts use the same size | Setting: `LDR_DEEP_FETCH_MAX_CHARS` (also deep/files.py:69, 120) |
| Extraction output | "Maximum 1500 characters" -> 4,000, plus "keep every quote that bears on the focus or the overall question" | deep/prompts.py:191-193; fetch:512-518 | Depth. The 09-30 effort test ran with this limit [design] | Maybe: a stronger extractor could keep more verbatim text | Mixed: number `LDR_DEEP_EXTRACT_MAX_CHARS`, wording hard-coded |
| Page cache per research | none -> each URL downloaded once | fetch:346-350, 358-359; deep/evidence.py:127-134 | [design] | No | Hard-coded (always on in deep) |
| One page at a time | parallel -> one fetch at a time per process, download included | fetcher:26, 221-224 (patch 0004, both profiles) | Parallel lxml parsing corrupted the heap (ldr-web crash 10-18) [host] | Maybe: with parallel subagents every download waits in one queue (30 s timeout each) | Hard-coded |
| Per-engine agent tools | 17 engine tools on -> off, plus 5 more per account | run-ldr.sh:95-98; tools/ldr-client.py:64-65 | Each search fired ~10 parallel LLM relevance-filter calls that queued on Strata at xhigh (test t0: 76 calls, 64K tokens) [Strata] | Maybe: an API model can absorb those calls, but SearXNG already covers arXiv, PubMed and S2 | Setting: `LDR_SEARCH_ENGINE_WEB_<E>_AGENT_ENABLED`, plus per-account keys |
| Semantic Scholar tool (Jan runs only) | off -> on, with its LLM relevance filter and journal filter off | run-ldr.sh:109-112; tools/ldr-client.py:60 | Same flood of parallel filter calls [Strata] | Maybe | Setting: `LDR_RESEARCH_S2`, plus a per-account key |
| Search fallback | none -> Exa, then Tavily, when SearXNG returns < 5 results (Jan runs only) | sx-engine:690-711 (patch 0005) | [host] | No | Setting: `LDR_SEARCH_FALLBACK` |
| Search-failure stop | none -> a run whose searches mostly fail is stopped and marked FAILED | sx-engine:26, 683-789; tools/research_common.py:267-285 | "No report from the model's own knowledge" (user, 10-21) [design] | No | Hard-coded thresholds (more than half of >= 6 searches) |
| Bang hints in prompts | none -> `!science`, `!arxiv`, `!pubmed`, `!gos`, `!se` | deep/prompts.py:46-49, 57-58 | Our SearXNG engine set [host] | No | Hard-coded |
| Code tool caps | none -> 40 grep hits, <= 120 lines per read, 240 chars per line, 200 tree entries, files > 2 MB refused, clone 400 MB / 300 s, issue search 10 x 600 chars, issue body 3,000 + 8 comments x 1,500, 20 commits; the prompt says "search first and read short ranges - never whole files" | deep/codetool.py:39-45, 369-399, 412-419, 444-449 | Keeps tool results small for the agent's context (NOTES 10-27 lists the caps, no other reason) [ctx] | Yes: a 1M-context model could read whole files and more hits. The rule forces many small calls | Mixed: `LDR_DEEP_CODE_MAX_MB`, `LDR_DEEP_CODE_CLONE_S`; the rest and the wording are hard-coded |

### 2.2 Context and compaction

| item | value (stock -> ours) | where | why (notes) | limits a stronger model? | setting or hard-coded |
|---|---|---|---|---|---|
| Context the code assumes | unrestricted -> 131,072 tokens | deep/__init__.py:67; run-ldr.sh:83-84 | Strata's `--max-context 131072` [ctx] | Yes: every budget below is derived from it | Setting: `LDR_DEEP_CONTEXT_TOKENS`, `LDR_LLM_CONTEXT_WINDOW_SIZE`, `LDR_LLM_LOCAL_CONTEXT_WINDOW_SIZE`, `LDR_LLM_CONTEXT_WINDOW_UNRESTRICTED=false` |
| max_tokens per call | 30,000 (LDR default) -> 30,000, locked | run-ldr.sh:85; deep/__init__.py:68 | LDR's default. Prompt + max_tokens must fit 131K, so prompts over ~101K are refused (NOTES 09-29) [ctx] | Maybe: the agent's working room is 131,072 - 30,000 - 512 | Setting: `LDR_LLM_MAX_TOKENS` |
| Compaction threshold | none -> each agent's history compacted at 56,000 tokens | deep/__init__.py:69; deep/middleware.py:107-113 | Well under the ~100K hard limit. README proposal A: 110,000 at a 262K context [ctx] | Yes: with 200K-1M the agent could keep its own steps verbatim much longer. Every compaction is a lossy summary written by the model | Setting: `LDR_DEEP_COMPACT_AT` |
| Recent steps kept verbatim | 6 messages, at most 35 % of the threshold | deep/middleware.py:128-137 | [ctx] | Yes (follows the threshold) | Mixed: `LDR_DEEP_KEEP_RECENT`; 35 % hard-coded |
| Re-compaction guard | only after +20 % growth, or at 90 % of the hard limit | deep/middleware.py:108-110 | Thrash guard (NOTES 09-30) [ctx] | No | Hard-coded |
| Compaction chunks and fallback | room = context - max_tokens - 512 - 3,000 - task; a huge message cut in half; if the summary fails, history cut to 12,000 tokens | deep/middleware.py:144-163, 201 | [ctx] | Maybe | Hard-coded |
| Per-call context guard | none -> largest tool results shortened to fit context - max_tokens - 512 (each to >= 500 tokens) | deep/middleware.py:33, 204-231 | Strata refuses an over-long request instead of cutting it [ctx][Strata] | No: it is a safety net. The 512 margin assumes exact Qwen token counts | Hard-coded |
| Subagent report seen by the lead | full -> first 16,000 chars (the store keeps all of it) | strategy:1741-1743; deep/__init__.py:63 | Lead context [ctx] | Yes: a large-context lead could read whole subagent reports | Setting: `LDR_DEEP_SUB_RETURN_MAX_CHARS` |
| Tokenizer | none -> Qwen BPE (248,320 tokens, qwen35 pre-tokenizer); 8 tokens per message (ChatML); +150 for the tool template; chars/3 without it | deep/tokens.py:15, 21-61, 99-102; run-ldr.sh:116 (`deep/tokenizer/`) | Exact counts for Strata's window [model] | Yes: another model counts differently, so all budgets above are approximate. The guard margins are small (512 tokens) | Mixed: `LDR_DEEP_TOKENIZER_DIR` (unset = chars/3); the overhead constants are hard-coded |
| Earlier findings in a continued run | none -> up to 60,000 chars; 150 sources and 120 searches listed | deep/seed.py:22, 145-166 | [ctx] | Maybe | Hard-coded |
| Source and search lists in compaction notes | none -> 400 sources, 300 queries, titles at 90 chars | deep/evidence.py:161-183; deep/middleware.py:170 | [ctx] | No | Hard-coded |
| Tried-list sizes (feature off by default since 10-24) | none -> parts of 60,000 chars ("room to think and list within the 131K context"); <= 30 entries a part (an uncapped part ran past 16K tokens); merge 100,000 chars; 200 final entries; a 36,000-char block in the prompts; max_tokens 32,768 | deep/tried.py:25-29, 120, 152 | [ctx][model] | Yes: a large-context model could read the files whole in one call | Hard-coded (on/off: `LDR_DEEP_TRIED`) |

### 2.3 Prompts and instructions

| item | value (stock -> ours) | where | why (notes) | limits a stronger model? | setting or hard-coded |
|---|---|---|---|---|---|
| Lead depth addendum | none -> added to LDR's lead prompt (see list below) | deep/prompts.py:38-53; strategy:2860-2866 | "Deepest research; run time doesn't matter" (NOTES 09-30) [design] | Maybe: "generously" can mean many subagents, which costs money on an API. The step count is in the prompt | Mixed: text hard-coded, numbers from settings |
| Subagent prompt | LDR's short prompt -> "findings, not a short summary", two sources, bang hints | deep/prompts.py:55-65; strategy:1646-1649 | [design] | No | Hard-coded |
| Wrap-up | none -> "TIME TO WRAP UP" message; the agent loses its tools | deep/prompts.py:67-70; deep/middleware.py:85-104, 208-211 | Enforces the budget [design] | No | Hard-coded |
| Compaction prompt | none -> keep every finding with its [N], dead ends, open questions | deep/prompts.py:8-36 | [design] | No | Hard-coded |
| Report size rules | none -> outline of 3-10 sections; sections "typically 300-900 words"; 4-10 key findings | deep/prompts.py:99, 132, 151 | [design] | Maybe: these cap depth per section for a stronger writer | Hard-coded |
| Citation-check framing rule | none -> "framing and connective words do not make a claim partial; a missing or different fact does" | deep/prompts.py:187-189 | xhigh was over-strict on framing words (NOTES 09-30 11:25) [model] | No: harmless, though a better checker may not need it | Hard-coded |
| Call-class marks | none -> each deep prompt opens with "You are the history-compaction / report-writing / claim-verification step ..."; the critic, setup-check, tried-list and "not yet" prompts reuse the verification mark | deep/prompts.py:1-6; deep/advisory.py:23, 48; deep/setup.py:23; deep/tried.py:34; deep/notyet.py:25 | strata-proxy sorts calls into classes by these marks, for effort and the chat cache [Strata] | No: the text is harmless | Hard-coded |
| Setup profile block | none -> the user's hardware facts in the lead and report prompts | deep/setup.py:17-21, 59-67; strategy:2873-2876 | The lead sometimes ignored the profile (o02 E1) [design] | No | Mixed: on with `LDR_DEEP_SETUP_PROFILE`; text hard-coded |
| Code tool prompt | none -> "check at the version the user runs ... read short ranges - never whole files"; the example names the Strata repo | deep/codetool.py:412-419, 444-449 | [ctx] | Yes: the "never whole files" part | Hard-coded (on with `LDR_DEEP_CODE`) |
| Other addenda | none -> the user's files, the continuation note, the tried-list intro and report note | deep/files.py:77-85; deep/seed.py:139-167; deep/tried.py:66-71 | [design] | No | Hard-coded |

The lead depth addendum adds these points to LDR's lead prompt:
- break the task into sub-questions;
- "use research_subtopic generously" (up to 8 per call);
- read primary sources;
- confirm facts in two sources;
- the budget in minutes and steps;
- "a separate step writes the final report".

### 2.4 Report stage and checks

| item | value (stock -> ours) | where | why (notes) | limits a stronger model? | setting or hard-coded |
|---|---|---|---|---|---|
| Report pipeline | LDR's citation-handler answer -> outline, sections, opening, then the checks | strategy:3203-3239; deep/report.py | LDR's detailed mode passes only 1,000 chars to its planner (#6640/#6711) [design] | No | Setting: `LDR_DEEP_REPORT`, `LDR_DEEP_VERIFY` |
| Answer room in report calls | none -> output up to min(60,000, context - prompt - 1,024), at least 4,096; a prompt over context - 9,216 is cut | deep/report.py:139-150 | "Report calls may use up to 60K output tokens (within the context)" (NOTES 09-30) [ctx] | Maybe: an API with a lower output limit refuses 60K, and one with a 1M context still gets 60K | Hard-coded (uses the context setting) |
| Outline material | none -> budget = context - max_tokens - 6,000; lead answer <= min(10,000, budget/6) tokens; subagent findings 40 %; a one-line digest per source gets the rest; 2 tries, then a one-section fallback | deep/report.py:161-171, 199-223 | [ctx] | Yes: at 1M the planner could see all the evidence instead of digests | Hard-coded |
| Section evidence | none -> 48,000 tokens per section (60 % extractions, then page passages of ~900 chars); findings 12,000 tokens | deep/report.py:52, 225-256; deep/__init__.py:74 | Sized for 131K. README proposal A: 100,000 at 262K [ctx] | Yes | Mixed: `LDR_DEEP_REPORT_EVIDENCE_TOKENS`; the 12,000 and the 60 % split are hard-coded |
| Opening (Answer, Key findings) | none -> the sections cut to context - max_tokens - 4,000 - task - 1,500 | deep/report.py:266-275 | [ctx] | Maybe: in a long report the later sections drop out of the Answer's view | Hard-coded |
| Claims checked | all -> 120 key claims (Answer and Key findings first, then figures, dates, quotes and names) | deep/__init__.py:77; deep/report.py:304-320, 557-560; research.conf; tools/research-runner.py:220 | A full check of ~400 claims took ~1.5 h at xhigh (NOTES 09-30 13:17) [speed] | Yes: a fast model could check every claim | Setting: `LDR_DEEP_VERIFY_MAX_CLAIMS`; `verify_max_claims` in research.conf for Jan jobs |
| Citation-check design | per source -> per claim, all cited sources together; 2,000 tokens per source; 8 claims or 36,000 tokens per call | deep/report.py:322-395; deep/__init__.py:76 | Per source inflated "partial" (66 % vs 17 %). Joint: 260 claims in 33 calls of ~9K tokens (NOTES 09-30) [model][speed] | Maybe: 2,000 tokens per source can miss the passage; a large-context checker could take whole pages | Mixed: `LDR_DEEP_VERIFY_CLAIM_SOURCE_TOKENS`; batch size hard-coded. (`LDR_DEEP_VERIFY_PAGE_TOKENS` serves only the old per-source design.) |
| Setup check | none -> full list first; a "flagged only" retry when the answer runs to length or has no JSON | deep/setup.py:78-86; deep/report.py:573-589 | The lead sometimes ignored the profile [design]; the retry exists for long outputs [model] | No | Mixed: on with `LDR_DEEP_SETUP_PROFILE`; retry hard-coded |
| Critic, "Check these" list | none -> at most 20 issues asked for, 8 shown | deep/advisory.py:19, 35, 143-166 | User 10-21: advisory only, never rewrites [design] | Maybe: 8 lines can hide valid issues from a stronger critic | Mixed: on with `LDR_DEEP_CRITIC=1`; limits hard-coded |
| Two-source verifier (dropped 10-22) | none -> 40 claims, 4 other sources, 900-char passages, 6 claims or 36,000 tokens per call | deep/advisory.py:20-21, 88-137 | 22-24 min per run, nothing unique reached the list [speed] | Maybe | Mixed: `LDR_DEEP_VERIFY2=flag`; limits hard-coded |
| "Not yet" fresh check (off since 10-24) | none -> at most 15 claims; 8 results; 3 pages read at 3,000 chars; 400-char snippets; 20/30 s timeouts | deep/notyet.py:63-67, 82-105 | [ctx][speed] | Maybe | Mixed: `LDR_DEEP_NOTYET`, `LDR_DEEP_NOTYET_MAX`; the rest hard-coded |

Not audited: the six fixes (`deep/checks.py`, `LDR_DEEP_FIX`). They add more checks to the report stage, with their own
timing estimates measured on Flash-Next.

### 2.5 Time and step limits

| item | value (stock -> ours) | where | why (notes) | limits a stronger model? | setting or hard-coded |
|---|---|---|---|---|---|
| Research time budget | until the agent stops (~25 min in a test) -> 3 h of research (Jan: default 180 min, max 600), then the report | deep/__init__.py:56; strategy:2694-2705; research.conf; tools/research_common.py:38-39; tools/research-mcp.py:353-356 | "Deepest research; run time doesn't matter" (09-30) [speed] | Maybe: not a cap for a fast model, which reaches the step limits first. 3 h of a paid API is a cost question | Setting: `LDR_DEEP_TIME_BUDGET_S`; per job `budget_s`; research.conf `default_budget_minutes`, `max_budget_minutes` |
| Lead step limit | 50 (UI max 100) -> 200 model calls; wrap-up at 199 | deep/__init__.py:50; strategy:2054-2056; deep/middleware.py:88-89 | Depth (09-30) [design][speed] | Yes: a fast model can spend 200 calls well inside 3 h | Setting: `LDR_DEEP_MAX_ITERATIONS` (overrides the UI value) |
| Subagent step limit | 8 -> 30 | deep/__init__.py:51; strategy:2054-2056 | Depth [design] | Yes: same reason | Setting: `LDR_DEEP_MAX_SUB_ITERATIONS` |
| Subtopics per call | 5 (hard 10) -> 8 (hard 12) | deep/__init__.py:52-53; strategy:131-134 | Depth [design] | Maybe | Setting: `LDR_DEEP_MAX_SUBTOPICS`, `LDR_DEEP_MAX_SUBTOPICS_HARD` |
| Subagent time | hard kill at 1,800 s -> wrap-up at its fair share (<= 3,600 s); backstop 7,200 s | deep/__init__.py:54-55; strategy:131-134, 1688-1704 | The hard kill threw a subagent's work away (09-30) [design] | No | Setting: `LDR_DEEP_SUBAGENT_BUDGET_S`, `LDR_DEEP_SUBAGENT_HARD_S` |
| Fair share of research time | none -> each subagent gets at most 75 % of the remaining time divided by the waves still to run; none starts with < 60 s left | strategy:1692-1704 | With 1 worker the subagents ran one after another and used up the run; only 2 of 6 started (smoke 2) [Strata][speed] | Maybe: built for serial waves; with parallel workers it still holds back 25 % | Hard-coded (0.75, 60 s) |
| Quick mode (Jan) | full agent -> no subagents, <= 12 agent cycles, stopped at 15 min; pristine LDR at Strata's default effort | run-ldr.sh:106-108; tools/research-runner.py:52-54, 211-214, 416, 488-491 | Quick answers stay quick (user 10-19) [speed] | Maybe: 12 cycles caps a quick answer that a fast model could extend in 1-3 min | Mixed: `LDR_QUICK_LIMITS`; 12 and 15 min hard-coded |
| Measurement time limits | none -> ldr-client allows budget + 150 min for deep runs; bench2 gives 30 / 120 min of research plus 60 / 90 min for the report, + 30 | tools/ldr-client.py:225-229; tools/bench2.py:39, 149-179, 453-454 | Measured report-stage times [speed] | No (measurements only) | Mixed: CLI flags; allowances hard-coded |
| Time estimates shown to the user | none -> "1-3 minutes", "often another 30-90 min" for the report, "4.5-5 hours" for a default run | tools/research-mcp.py:39, 68-70, 385; README.md:116-120 | Measured on Flash-Next [speed] | No: text only, but wrong for another model | Hard-coded text |

### 2.6 Reasoning effort and the proxy

| item | value (stock -> ours) | where | why (notes) | limits a stronger model? | setting or hard-coded |
|---|---|---|---|---|---|
| Agent (tool-calling) calls | none (Strata's default, medium since 10-17) -> medium for Jan jobs; xhigh by default in ldr-client measurements; medium in bench2 phase 4 | proxy:592-601; tools/research-runner.py:49, 416; tools/ldr-client.py:42, 237-253; tools/bench2.py:102-112 | Hard five graded blind: 5/5 at both levels; xhigh took 4.2x the time (README "Thinking effort") [model] | Maybe: a stronger model may gain from more thinking. Only the proxy can set it | Setting: `agent_effort` in `run/proxy-mode.json` |
| Page extraction | none -> medium for Jan; xhigh by default in measurements | fetch:521-530; deep/__init__.py:59; proxy mode `extract_effort` | 09-30: xhigh won on quality. 10-20 replay: no level better, xhigh used 6.3x medium's tokens [model] | Maybe | Setting: `LDR_DEEP_EXTRACT_EFFORT` (empty = the proxy decides); proxy `extract_effort` |
| History compaction | none -> medium | deep/__init__.py:60; deep/middleware.py:197 | xhigh thought 30,000 tokens / 249 s with no answer (09-30) [model] | Maybe: a stronger model may do better at higher effort | Setting: `LDR_DEEP_COMPACT_EFFORT` |
| Report writing (also the "not yet" check) | none -> package default xhigh; medium for Jan jobs and phase 4 | deep/__init__.py:61; deep/report.py:148; tools/research-runner.py:50, 215-219 | Report replay: medium 31 vs xhigh 31.5 of 34, at 3x the time (10-20) [model] | Maybe | Setting: `LDR_DEEP_REPORT_EFFORT` |
| Citation check, setup check, critic | none -> xhigh | deep/__init__.py:62; deep/report.py:148 | Medium passed 10 claims that should be flagged, xhigh 1 (10-20) [model] | No | Setting: `LDR_DEEP_VERIFY_EFFORT` |
| Tried list | none -> low for the per-part calls, medium for the merge | deep/tried.py:120, 152 | [model] | Maybe | Hard-coded |
| No-answer retry ladder | none -> a call that ends at max_tokens without an answer, or fails, is retried one level lower (xhigh/high -> medium -> low; no effort -> medium), at most 3 tries | deep/llm.py:11, 21-52 | Runaway thinking at xhigh (09-30) [model] | Maybe: on an API, a rate-limit error would also lower the effort. "xhigh" may not exist there | Hard-coded |
| Per-class effort in the proxy | none -> the proxy adds `reasoning_effort` (or turns thinking off) by call class when the client sent none | proxy:7-15, 90-98, 158-169, 592-601 | LDR 1.10.7 cannot send `reasoning_effort` itself (NOTES 09-29) [Strata] | n/a: skip the proxy for an API; LDR then sends no effort on agent calls | Setting: `run/proxy-mode.json` |
| Context-400 retry | none -> when Strata refuses "prompt + max tokens exceeds the context", the call is retried once with max_tokens = context - 8 - prompt - 64, if that leaves >= 1,024 | proxy:20-24, 95-97, 685-705 | Strata refuses instead of cutting; it matches Strata's error text [Strata] | n/a: skip | Setting: `PROXY_GUARD_MARGIN`, `PROXY_GUARD_MIN_ANSWER` |
| Research gate | none -> calls are held on pause or abort, a test lock, another client in the last 5 min, or Strata down (it is then started); the research clock stops meanwhile | proxy:35-48, 263-501; deep/control.py:50; strategy:116-129 | One GPU shared with the user's chats and tests [Strata] | n/a: skip (harmless if no pauses) | Setting: research.conf `yield_minutes`, `night_pause`; `run/research-control.json` |
| Chat-cache fields | none -> `strata_owner` on every call; `strata_checkpoint=false` on one-shot classes; `strata_chat_drop` on report and verify calls | proxy:126-147; `run/chat-cache-policy.json` | Strata's host RAM (parked one-shot calls) [Strata] | n/a: skip; an API may reject unknown fields | Setting: `run/chat-cache-policy.json` |
| Streaming, timeout, retries | no streaming, 600 s, 2 retries -> streaming on, 1,800 s, 1 retry | tools/ldr-client.py:46-54 | Streaming lets Strata stop a cancelled call. 1,800 s covers a full 128K answer waiting in Strata's single queue. A retry re-sends the whole prompt (09-29) [Strata] | No: keep streaming; the long timeout is just loose | Setting: per account (`llm.streaming`, `llm.request_timeout`, `llm.max_retries`) via `ldr-client.py setup` |
| Temperature | 0.7 -> 1.0 (top-p / top-k / min-p come from Strata's config) | run-ldr.sh:78-80 | The user's sampling rule for Qwen: T 1.0 / 0.95 / 20 / 0.05 [model] | Maybe: some APIs fix or ignore temperature with reasoning on | Setting: `LDR_TEMPERATURE` (sets `LDR_LLM_TEMPERATURE`) |

Server-side, not in LDR: Strata closes thinking at 3/4 of max_tokens ("answer_room", since 0.2.1). That is part of
why 30,000 / 60,000 work on Flash-Next (NOTES 10-20).

### 2.7 Other

| item | value (stock -> ours) | where | why (notes) | limits a stronger model? | setting or hard-coded |
|---|---|---|---|---|---|
| Subagent workers | 4 -> 1 | run-ldr.sh:113-114 | Strata answers one request at a time. 2 workers: +3 % tok/s but fewer subagents finished (09-30) [Strata] | Yes: an API runs subagents in parallel; 1 worker makes a deep run serial | Setting: `LDR_WORKERS` (`LDR_LANGGRAPH_AGENT_MAX_SUBAGENT_WORKERS`) |
| Endpoint and model | user's choice -> Strata through the proxy (8090); the model id is read from Strata's `/v1/models`; LDR will not start if Strata does not answer | run-ldr.sh:70-77, 129-131, 150-151 | [Strata] | Yes: an API model needs a launcher change | Mixed: `LDR_VIA_PROXY`, `STRATA_URL`; model discovery hard-coded |
| Memory guards | none -> start needs >= 14 GB available; runs stop below 12 GB; Strata restarts below 20 GB (13 GB for DeepSeek) | run-ldr.sh:38; tools/ldr-client.py:40; tools/research-runner.py:64-71 | Strata shares the host's RAM [Strata] | No (pointless for an API) | Hard-coded |
| LDR kept off the GPUs | none -> `CUDA_VISIBLE_DEVICES=""` | run-ldr.sh:65 | Strata needs the VRAM [Strata] | No | Hard-coded |
| Tool-call tag log | none -> the proxy logs `<tool_call` text in prose answers | proxy:53-55, 245, 811 | Strata cuts an answer where the model writes the tag in prose [model][Strata] | No (log only) | Hard-coded |

## 3. Recommendation

### Per-model profile

Make one file per model, for example `profiles/flash-next.env` and `profiles/<api-model>.env`. `run-ldr.sh` would
load it. Its numbers (from the tables above) are the current ones on Flash-Next.

1. **Context and output:**
   - `LDR_DEEP_CONTEXT_TOKENS` and the three LDR context-window keys;
   - `LDR_LLM_MAX_TOKENS`;
   - the report output cap (60,000 at report.py:150; make it a setting, limited by the model's own output cap);
   - the 8K answer reserve (report.py:139).
2. **Compaction:** `LDR_DEEP_COMPACT_AT`, `LDR_DEEP_KEEP_RECENT`, and the 35 % recent-window share as a new
   setting. Better: derive the threshold from the context. Today it is about half of (context - max_tokens): 56,000 of
   101,072. README proposal A used 110,000 for a 262K context.
3. **What the lead and writers see:**
   - `LDR_DEEP_SUB_RETURN_MAX_CHARS`, `LDR_DEEP_SNIPPET_CHARS`, `LDR_DEEP_FETCH_MAX_CHARS`,
     `LDR_DEEP_EXTRACT_MAX_CHARS`, `LDR_DEEP_REPORT_EVIDENCE_TOKENS`;
   - new settings for the hard-coded report caps: section findings 12,000, outline lead answer 10,000, findings 40 %,
     the opening cut;
   - the citation-check batch (8 claims / 36,000 tokens) and `LDR_DEEP_VERIFY_CLAIM_SOURCE_TOKENS`;
   - the seed text (60,000) and the tried-list sizes.
4. **Tokenizer:** `LDR_DEEP_TOKENIZER_DIR`, and the 8-per-message and 150-per-template overheads as settings. An API
   model should use chars/3 or the provider's count, with a larger safety margin than 512 tokens.
5. **Effort:**
   - one effort per call class: agent, extraction, compaction, report, verify, tried-list;
   - an effort-name map (Strata's low / medium / high / xhigh to the API's names);
   - a switch for the retry ladder (llm.py:11). On an API it should retry errors at the same effort, with backoff.
   - A way to send the agent's effort without strata-proxy. LDR 1.10.7 cannot do it, so either a small patch that
     passes `reasoning_effort` to LDR's chat client, or a thin pass-through proxy without the Strata parts.
6. **Pace and size of a run:**
   - `LDR_WORKERS`;
   - `LDR_DEEP_MAX_ITERATIONS`, `LDR_DEEP_MAX_SUB_ITERATIONS`, `LDR_DEEP_MAX_SUBTOPICS`;
   - the default time budget;
   - `LDR_DEEP_VERIFY_MAX_CLAIMS` (0 = all is realistic on a fast model);
   - the quick-mode limits (12 cycles, 15 min);
   - the fair-share reserve (0.75) as a setting.
7. **Sampling:** temperature, and whether to send it at all.
8. **Code tool:**
   - the read sizes (120 lines, 40 hits, 240 chars, 200 entries);
   - a prompt variant without "never whole files" for large-context models.
9. **User-facing time estimates:** take them from the profile (or from measured run times), not fixed text.

### Keep global

- SearXNG: the engine set, the general + science categories, 50 results per search, and the bang hints.
- The search fallback and the search-failure stop.
- The page cache, the evidence store, the user's files, the seeded continuation and the code tool's safety rules.
- The report pipeline:
  - outline, sections, opening;
  - the joint citation-check design and its framing-word rule;
  - the setup profile and setup check;
  - the critic list.
- The wrap-up mechanics (message, tools removed), the per-call context guard (with a margin taken from the profile),
  and the subagent wrap-up instead of the hard kill.
- The one-page-at-a-time fetch lock, as a crash fix. But only the parsing needs it: with parallel workers, move the
  lock so it no longer covers the download.

### Skip for API models

- strata-proxy as it is:
  - the per-class effort injection from the mode file (replace it as in item 5 above);
  - the context-400 retry, which matches Strata's error text;
  - the research gate (pauses, yield to other clients, test locks, starting Strata);
  - the chat-cache fields `strata_owner`, `strata_checkpoint`, `strata_chat_drop`.
- The memory guards and relief restarts, and `CUDA_VISIBLE_DEVICES=""`.
- Model discovery from Strata's `/v1/models` and the "Strata must answer" start check.
- `LDR_WORKERS=1`. Use the stock 4, or more, within the API's rate limits.
- Turning off the per-engine tools and their LLM relevance filters. That was done to protect Strata's single queue;
  on an API it can be turned back on if wanted.
- The "length with no answer, one effort lower" ladder (it exists for Flash-Next's runaway xhigh thinking), and
  Strata's answer_room behaviour, which an API does not have.
- The 1,800 s read timeout. Keep streaming for cancels, but a shorter timeout is enough.
