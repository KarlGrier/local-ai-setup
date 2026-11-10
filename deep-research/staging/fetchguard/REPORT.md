# 11-03 stall of shop-7e-deep-p7dx/s2: what spun, the staged guard, the DOC_SCHEDULER

Written 2026-11-03 late evening (by the fetch-guard helper; saved by Claude because the helper's own write was refused).
Staged only, in `staging/fetchguard/`. Nothing was installed, no setting was changed, no LDR run or research was
started and no paid search was used. Install notes are in `INSTALL.md`.

## 1. What spun

**The page.** `https://www.teamgroupinc.com/en/support/compatibility/by-product/result/` is Team Group's compatibility
"result" page with no product chosen, so it lists the whole compatibility database:
- **263.7 MB of HTML**, sent as 5.5 MB of gzip. The download took 40.4 s, both in LDR's log and in one test fetch.
- One `<table>` from byte 4.6 M to byte 262.4 M with **165,933 rows**: 663,728 `<td>`, 498,187 `<div>`, 260,532 `<a>`,
  3.69 M `<` in total.

The G.Skill QVL page is innocent: 66.6 KB with no table; LDR extracted 9.0k chars from it in 0.08 s, and its extraction
call (#236, the run's last model call) returned at 18:47:38.

**The thread.** ldr-web TID 3747312 was the only running thread (state R, wchan 0: user space). At 22:30 it had 215 min
49 s of CPU, about 97 % of the 222 min since 18:48:14. It is the tool-call thread of subagent sub6, the first of the 5
subtopics started at 18:46:31, running `fetch_content` (summary_focus_query) on the Team Group URL. From the log:
- 18:47:33.78: "Fetching content from ...teamgroupinc..." - it took ContentFetcher's lock as soon as the G.Skill fetch
  released it.
- 18:48:14.14: the rate tracker's `html_download_www.teamgroupinc.com` line: `HTMLDownloader._fetch_html` had the 200.
- After that, `HTMLDownloader._extract_content` never logged its "Extracted N chars" line.

**The parser.** `HTMLDownloader._extract_content` calls `extraction/pipeline.py extract_content_with_metadata`: a
BeautifulSoup `html.parser` soup (kept alive for the whole call), `trafilatura.extract`, newspaper4k `Article.parse`,
then metadata - all in Python on the full 264 MB. The deep fetch cap (120,000 chars) applies only after extraction.
LDR's only size limit is SafeSession's 1 GiB on the compressed body; trafilatura's own 20 MB limit applies only to its
downloader, not to `extract()`.

Each step measured on slices of the saved page (one core, nice 19, `taskset -c 31`, `timeout 120`, 3.5-4 GiB
address-space cap; raw results in `scratch/attempt1.jsonl`, `scratch/attempt2.jsonl`):

| rows (prefix) | BeautifulSoup s / peak MB | trafilatura s / MB | newspaper4k s / MB |
|---|---|---|---|
| 1,006 (6 MiB) | 0.50 / 42 | 0.50 / 115 | 0.89 / 29 |
| 2,359 (8 MiB) | 1.25 / 69 | 1.03 / 225 | 1.84 / 53 |
| 5,066 (12 MiB) | 2.75 / 122 | 2.69 / 415 | 5.09 / 90 |
| 7,802 (16 MiB) | 5.03 / 177 | 4.44 / 607 | **23.7** / 362 |
| 13,462 (24 MiB) | 15.6 / 289 | 10.8 / 994 | (over the attempt budget) |

lxml's own parse takes 35 ms for 8 MiB - not the problem. Extrapolated to 165,933 rows: BeautifulSoup ~3.5 GB (21 KB
per row) and 10-40 min; trafilatura ~12 GB (74 KB per row) and >= 6 min; **newspaper4k roughly the square of the row
count, >= 3 h** (23.7 s x (165,933 / 7,802)^2 ~ 10,700 s; its last measured step grew 4.6x for 1.5x the rows).
cProfile at 7,802 rows (`scratch/profile-np4k-16mb.txt`): lxml `drop_tag` 9.4 s over 69k calls (lxml_html_clean's
Cleaner in newspaper's output formatter), `newspaper.parsers.get_tags` 7.2 s over 23.5k subtree walks, `get_level` 3.8 s
(`getroottree().getpath()` walks the siblings) - per-node work over the 165k sibling rows: the squared growth.
Memory fits: during trafilatura, soup 3.5 GB + trafilatura 12.2 GB + ~1 GB base ~ **16.8 GB = the 16.9 GB peak
(VmHWM)**; after it, soup 3.5 GB + newspaper4k ~7.7 GB + base ~ 12-13 GB ~ the 13.6 GB RSS at 22:30. So at 22:30 the
thread was most likely in newspaper4k (inferred from memory and scaling; no stack dump taken).

**Why the whole research stopped.** The parse held ContentFetcher's process-wide `_FETCH_LOCK` (patch 0004, kept
because parallel lxml corrupted the heap on 10-18); sub6 waited for both its parallel tool calls; the lead waited in
`research_subtopic`'s drain loop, and the subagent pool has one worker, so the 4 queued subtopics could not start. The
per-subagent backstop is 7,200 s of research clock, and that clock stops while the proxy gate is held (held 9,196 s in
this run). Nothing can interrupt a running Python thread. The DOC_SCHEDULER runs in its own thread (section 4) - why
the log kept moving.

## 2. The guard (staged as patch 0006)

Touches `research_library/downloaders/html.py`, `playwright_html.py`, `extraction/pipeline.py`; adds
`extraction/fetch_guard.py` (stdlib + loguru). Every HTML page fetched by the agents' `fetch_content` and by the deep
background reader passes through `HTMLDownloader`, so all are covered.
- **Download cap 16 MiB** (`LDR_FETCH_GUARD_MAX_MB`): the body is read streamed and decompressed and the read stops past
  the cap; a `Content-Length` above it is refused unread. The Team Group page now stops after ~0.35 MB of gzip.
- **Tag cap 400,000 `<`** (`LDR_FETCH_GUARD_MAX_TAGS`), ~5 ms, before any parser: catches dense pages under 16 MiB
  (Team Group: 3.69 M; its first 16 MiB 188k).
- **Skip, log, count:** a skip is a failed download with a reason like `[FETCH-GUARD] skipped: page larger than the
  16.0 MB cap (download stopped) (16.1 MB, 2.4 s)`; the agent gets `Failed to fetch <url>: [FETCH-GUARD] skipped: ...`
  and moves on (no JS-rendering retry; the deep page cache keeps the result, so it is not downloaded again); each skip
  logs `[FETCH-GUARD] skipped <url>: <reason>, <size>, <seconds>`, increments the in-process `counts()` and adds a record
  to `logs/fetch-guard.jsonl`; `tools/ldr-client.py` reads that file for the run's window and writes
  `summary.json["fetch_guard"] = {skipped, slow, pages, largest_mb, max_tags, slowest_s, events[]}`.
- **Watchdog 60 s** (`LDR_FETCH_GUARD_SLOW_S`): logs `still extracting <url> after 60 s`, then `slow page ... took N s`;
  counted as `slow`. It cannot stop the parse (a thread cannot interrupt lxml; a second parse beside it would bring back
  the 10-18 heap corruption). A true per-page time limit needs the extraction in a killable worker process (forkserver)
  - a bigger change to ldr-web's process model, not staged; the caps bound the time instead.
- **Page records:** one per parsed page (host, size, `<` count, seconds; no path), to re-check the caps on real data.

Worst page the guard still lets through (measured on the guarded path): the Team Group page's own first 16 MiB (7,800
rows, 188k `<`): **43.6 s and +909 MB**; with `LDR_FETCH_GUARD_MAX_MB=8`, ~5 s and ~300 MB.

**Tests** (`tests/test_fetch_guard.py`, offline: a loopback server, the saved pages, the staged files vs stock LDR's;
output `tests/test-output.txt`): 7 / 7 pass in 7 s - the 264 MB page served gzip-chunked is skipped after 16.1 MB with
+28 MB peak; served with `Content-Length` it is refused unread; the G.Skill page and a 4 MiB slice give **byte-identical**
text to stock LDR; the tag cap, direct pipeline callers, the watchdog and the switch-off behave as intended.
**Patch checks:** `0006-fetch-guard.patch` applies to the pristine files and reverses cleanly; on a scratch venv copy:
old `apply.sh` "patched" -> apply 0006 -> new `apply.sh` "patched" -> revert "pristine" -> apply "patched".

## 3. How often it would have fired

70 ldr-web logs; 52 from patch 0004 on (10-18 21:11 -> 11-03): 13,564 timed page extractions, median 0.09 s, p90 0.47,
p99 12.0, p99.9 37.7, max 311 s. Exactly **one** page was ever downloaded and never finished: Team Group, 11-03.
- **Watchdog (60 s): 4 times + Team Group** (0.03 %): xuchen-li.github.io 311 s (10-31), servethehome.com 148 s (11-02),
  gist.github.com 89 s (10-19), tekblueprint.org 70 s (10-22). At 30 s: 17 times.
- **Skips:** raw sizes were never logged - certain: 1 (Team Group); the only plausible others are the 4 slow pages (the
  13 pages with >= 1 M chars of text took 3-311 s; the guard's worst passing page ~44 s). Estimate 0-4 skips in 13,564
  extractions (<= 0.03 %) plus Team Group; the page records will settle it.

## 4. Karl's question: the DOC_SCHEDULER

**What it is:** LDR's per-user background job "Process Documents for karl" (`scheduler/background.py`
`_process_user_documents`), APScheduler interval `document_scheduler.interval_seconds` = 1800 s, scheduled at login (the
bench and the runner log in as karl) - so first 30 min after each ldr-web start (11-03: login 17:49:12, first 18:19:31).
Our settings (its own log line) are LDR's defaults: enabled=True, pdfs=False, text=True, index=False.
**What it does:** takes the 20 most recently completed researches since `document_scheduler.last_run`; for every
`ResearchResource` with a downloadable URL (every source the research collected: ~1,000-3,500 per deep run) it calls
`DownloadService.download_as_text` - an API where one exists (arXiv), else the PDF downloaded in memory from the
publisher (ieeexplore, ssrn, springer, wiley, acm, ...) and text-extracted with pypdf. The text is stored as a library
Document in karl's encrypted LDR database (`LDR_DATA_DIR` = `data/`; not opened); duplicates linked by content hash;
failures (paywall_or_login, 403, 404) recorded, so each resource is tried once. With `download_pdfs=false` no PDF files
are written; with `generate_rag` / `sweep_library_collections` false no embeddings are built (the RAG reconciler is not
even scheduled). In our setup it never finishes a batch: each ldr-web lifetime (3-5 h) covers part of the newest
research's sources, so `last_run` has not moved since 10-18 11:41 and every start begins again with the newest completed
research (normally the previous bench run). It does not tell bench runs from Karl's own research.
**Part of anything we measure or use? No.** No LLM calls, no search-engine or paid-search calls; its log lines are not in
`research-logs.json`; the deep mode, the bench, the report and the citation check do not read the library (NOTES 10-18:
the library search engine is registered but never offered to the agent; the fetch tool reads a library document only
when handed a `/library/document/` URL). It only shares the ldr-web process with the research:
- **CPU:** the second-busiest ldr-web thread at 22:30 had 16 min 39 s of CPU at ~10 % of a core - most likely the
  scheduler's worker: ~6-7 % of one core over 4.2 h, plus GIL contention with the research threads.
- **Network, the 11-03 17:49 LDR (18:19-22:30):** 1,041 API attempts, 587 arXiv PDF downloads, 120 direct PDF downloads,
  682 publisher-page attempts (310 ieeexplore, 86 ssrn, 81 springer, 54 acm), 587 HTTP 403, 305 HTTP 404; 658 texts saved
  (230 new documents, 2.6 M words, 428 linked). Bytes not logged; at 1-3 MB per PDF roughly 0.7-2 GB.
- **All of 11-03 (4 ldr-web lifetimes):** 1,453 arXiv + 275 direct PDF downloads, 2,356 publisher attempts, 2,372 HTTP
  403; 1,625 texts saved (634 new documents, 6.6 M words).
- **Memory:** not logged (pypdf "Exceeded 5000 form XObject invocations" warnings show some heavy PDFs).
- **Shared rate-limit table:** its failures raise e.g. `pdf_download_ieeexplore.ieee.org` to a 10 s wait, which a
  research PDF fetch from that host then also waits; HTML fetches use separate `html_download_*` keys.
**Turning it off cleanly (nothing changed):**
1. **Env var, no DB change (suggested):** `export LDR_DOCUMENT_SCHEDULER_ENABLED=false` in `run-ldr.sh` beside the other
   `LDR_*` exports (`SettingsManager.get_setting` reads `LDR_<KEY>` before the DB; `parse_boolean("false")` is False - a
   value like "disabled" would count as True). At login LDR then logs "[DOC_SCHEDULER] Document scheduler disabled for
   user karl"; it takes effect at the next ldr-web start, for every LDR `run-ldr.sh` starts (bench, runner, Jan's
   research).
2. The setting `document_scheduler.enabled` off on LDR's Settings page (persists in karl's settings DB; reschedules now).
3. `document_scheduler.extract_text` off with `download_pdfs` off (the job still fires every 30 min, returns at once).
**Effect on measurements:** none on LLM calls, tokens, searches, fetched pages, the report or the citation check; it
removes the background CPU / GIL load, ~1-2 GB of downloads, the rate-limit side effects and the DB writes from ldr-web
after each run's first 30 min - slightly less wall-clock noise (expected <= 1-2 %, not measured). The LDR Library stops
collecting the researches' sources.

## 5. Files

Staged: `REPORT.md`, `INSTALL.md`, `install.sh` (not run), `0006-fetch-guard.patch`, `apply.sh` + `apply.sh.patch`,
`tools/ldr-client.py` + `tools/ldr-client.patch`, `site/` (the 4 files as they will look after install),
`tests/test_fetch_guard.py` + `tests/test-output.txt`. `scratch/`: `pages/` (the two saved pages; `teamgroup.html`
252 MiB - kept for the tests), `bin/` (repro_steps.py, profile_np4k.py, scan_logs.py, worst_under_cap.py),
`attempt1.jsonl`, `attempt2.jsonl`, `profile-np4k-16mb.txt`, `past-fetch-times.jsonl` (per-fetch timings, hosts only),
`testwork/`. Fetches: each page once, with LDR's own browser User-Agent; both answered 200; no bot block was met.
