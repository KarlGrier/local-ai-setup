# Item 5, first half (A): why ldr-web's memory grows - and the staged fixes

Written 2026-11-04 by the ldr-study helper. Staged only, in `staging/ldr-study/`. Nothing was installed, no setting or
unit was changed, no LDR / proxy call, research or search was made, no network. The live LDR was only read through
`/proc/<pid>/{status,smaps,maps,task/*/comm}`.

## 1. Short answer

There is no large leak of live objects. ldr-web's RSS climbs to the highest transient peak it has seen and keeps it,
because glibc keeps freed memory in its per-thread arenas. That gives a ratchet: a fresh LDR starts at 0.3 GB, reaches
1.0-2.6 GB within one deep question, and a long-lived LDR levels off at 4.2-4.5 GB. It does not grow linearly with
time, so Karl's "0.3 -> 4.7 GB per day" is the ratchet, not a daily rate. The peaks come from big in-process work
(page parsing, the report stage, PDF text extraction). The 264 MB Team Group page was the extreme case (16.9 GB peak;
now capped by patch 0006). The bench's fresh LDR per question (since 11-01) already bounds this for the bench. Jan's
runner keeps one LDR across jobs and needs the same rule.

## 2. Evidence

**RSS over time** (all 257 `results/ram-dip-*.json` snapshots, ldr-web group; `scratch/ramdip-ldr.txt`):
- The long-lived LDR of 10-31 12:52 went 0.30 GB (start) -> 2.17 (16:51) -> 2.55 -> 2.70 -> 2.85 (20:17) -> **4.19
  (20:37)**, then sat at **4.15-4.48 GB for 14 h** (20 snapshots, 11-01 01:23-10:30). Five deep questions ran on it in
  that time (p7b o03 + its rerun, p7c o01-o03), with no steady climb. It sometimes went down (4.39 -> 4.15).
- Fresh LDR per question (from 11-01 11:30): 1.0-1.8 GB after 1-2 h (for example s2 / s3 / p7ex s2 / s3 / p7dx s1 at
  57-76 min: 1.18 / 1.20 / 1.21 / 1.20 / 1.32 GB). Jumps happen within a single question: p7a o02 went **1.35 ->
  4.35 GB** between 19:11 and 20:17 on 11-01, on a fresh LDR. That window spans the lead's wrap-up (19:46) and the
  report stage (19:51-20:43). No page in it had more than 76 k chars (`scratch/bin/big_events.py`). The 10-31 20:17-20:37
  jump came near the end of p7b o03's research and includes one 640 k-char page (cambridge-commentary.ai, 3.8 s).
- **The idle LDR after s3 p7dx (pid 4148400, 11-04 09:32, one research done)**: VmRSS 1,746 MB, **VmHWM 2,732 MB**
  (so about 1 GB went back at the research's end), anon 1,639 MB, 73 threads. `scratch/bin/smaps_classify.py`:
  **28 glibc arena heaps (64 MiB-aligned), 795 MB, fully resident**; 702 MB in other anonymous blocks of 1 MiB or more
  (pymalloc arenas and large malloc blocks); main heap 89 MB; files 115 MB. One `jemalloc_bg_thd` belongs to pyarrow
  (loaded through pandas), and nothing points to it.
- The relief restarts follow the ratchet. NOTES 11-01: 14 restarts by 10:10 on the long-lived LDR, against 1-7 a day
  before.

**Offline reproductions** (venv python, imports only, under `nice -n 19 taskset -c 31 timeout 120 prlimit --as=4G`; no
server, model or network; `scratch/mem/*.jsonl`, `scratch/bin/repro_mem.py`, `store_replay.py`):
- LDR's own extraction pipeline (`extraction/pipeline.py`) ran over 44 pages (article pages built from our bench
  page texts, the G.Skill page, and 2 / 4 / 6 MiB Team Group prefixes), one page at a time (like patch 0004), with a
  new 4-thread pool per wave. After warm-up, 10 waves (220 extractions) left RSS swinging between **401 and 444 MB with
  no upward trend**, and Python's allocated blocks stayed flat at 874 k. So the extraction path has no object leak. Yet
  128-153 MB was *free inside malloc* and still resident: **malloc_trim(0) gave back 114 MB (443 -> 329 MB)**.
- One finished research's whole evidence (p7a o01: 1,079 records, 5,618 sources) was rebuilt with the store's own
  methods: **about 60-75 MB live**. After it was freed, 47 MB stayed resident as malloc free space until a trim (83 ->
  35 MB). Even a research that was never freed would explain about 70 MB, not gigabytes, and the 14-hour plateau shows
  that none is kept.
- `MALLOC_ARENA_MAX=2` made no difference in this low-concurrency test (458 vs 443 MB). Its real effect needs
  ldr-web's 70-80 threads. Measure it with memwatch (section 4) before using it.

## 3. Causes, ranked

1. **Allocator high-water retention (the mechanism, about all of the growth).** Freed peaks stay resident in glibc's
   arenas (28 of them in the idle LDR) and in fragmented pymalloc arenas. glibc returns memory only at a heap's top, so
   RSS tracks the largest peak so far. Evidence: the plateau, the 1 GB drop at a research's end (top-of-heap trims
   only), the fully resident arena heaps, and malloc_trim's 26-58 % in both offline runs.
2. **What makes the peaks (the trigger).** Big in-process work in many threads:
   - **Single heavy pages.** BeautifulSoup + trafilatura + newspaper4k need 50-100x the HTML size (staging/fetchguard
     section 1). Team Group peaked at 16.9 GB. After patch 0006 (16 MiB / 400 k-tag cap) the worst page that passes is
     about +0.9 GB.
   - **The report stage.** The 11-01 +3 GB jump lines up with it: 48 k-token section prompts, citation-check passages
     over every read page, a per-character position list for every page and quote check (`checks._norm_map`,
     `claims.PageIndex`, `enginescope.locate`: about 4 MB of Python ints per 120 k-char page per call), and tokenizer
     runs over whole histories.
   - **The DOC_SCHEDULER (contributed, size not measured).** Its own thread ran pypdf over about 587 arXiv and 120
     direct PDFs per LDR lifetime. Each PDF was downloaded whole into memory (only SafeSession's 1 GiB cap applies),
     and "Exceeded 5000 form XObject" warnings show heavy ones (11-01 18:59). It starts 30 min after login, so the
     ram-dip points at 57-76 min above include about 30 min of it. It is **off from the s4 p7dx LDR (11-04 10:01)**:
     "[DOC_SCHEDULER] Document scheduler disabled for user karl" is in its log. **The check:** compare that LDR's RSS
     near 11:01 (60 min in) and at its end with the 1.18-1.32 GB scheduler-on values above, and the next fresh LDRs'
     ram-dip snapshots too. With memwatch installed, its research-start / end / periodic lines answer this directly.
   - Smaller transient churn: the fetch tool logs every page's whole text (up to 120 k chars) to loguru (284 times in
     the s3 log, 2.2 MB of lines over 20 k characters), so each such line passes through the stderr and database sinks.
3. **True leaks found: small only.** These were read in the code (state kept across researches):

| place | what it keeps | verdict |
|---|---|---|
| `deep/files.py` `_texts` | the full text of every user file a Jan job read (PDF via pypdf) | grows per path, Jan file jobs only; **0007 empties it at research end** |
| `deep/llm.py` `_drops` | one small record per effort drop | negligible |
| `deep/enginescope.py` `_RX` | compiled regexes per engine pair | bounded |
| `web/routes/globals.py` `_active_research`, `_termination_flags` | one entry per research, popped at cleanup | fine |
| `research_service._last_emit_times` | emit times, TTL cleanup | fine |
| `utilities/log_utils._log_queue` | DB log queue, maxsize 1000 | bounded (but bursty with the 120 k page lines) |
| rate-limit tracker | 2 x LRUCache(100) per tracker; a new tracker per search engine (814 in the s3 LDR) | fine |
| EvidenceStore + its page cache | one research's evidence, about 60-75 MB | freed after the research (offline check) |
| deep reader thread | holds the store until `stop()` or deadline + 600 s | fine |
| subagent ThreadPoolExecutors | one per `research_subtopic` call, `shutdown(wait=False)` | threads exit; arenas are reused |
| trafilatura / justext / newspaper state | one-time about 45 MB and 734 k blocks after the first pages | flat afterwards (offline) |

SQLAlchemy's thread-local sessions and LangGraph's internals were not traced in depth. The plateau and the replay
leave no room for them to be a big factor.

## 4. Staged fixes (not installed)

- **`patches/0007-memwatch.patch`**: new `deep/memwatch.py` plus hooks in the strategy and in `tools/fetch`
  `_fetch_raw_content`.
  - One JSON line per research start / end and every 10 min to `logs/ldr-mem.jsonl`: RSS, HWM, anon, threads, glibc
    in-use / free / mmapped (mallinfo2), arena heaps, Python blocks, gc counts.
  - `gc.collect()` + `malloc_trim(0)` 30 s after each research ends (a timer thread, so the research's objects are
    already unreferenced). The same after any fetch of 100 k chars or more and after any PDF, at most once per 20 s.
  - Empties the user-file text cache at research end.
  - Switches: `LDR_MEM_TRIM=0` turns the trims off and keeps the records; `LDR_MEMWATCH=0` turns everything off. It
    changes nothing a research reads, sends or writes. Expected: the idle RSS after a research falls toward the live
    size (from about 1.75 GB toward about 1 GB), and the records show which phase sets each peak.
- **`patches/runner-fresh-ldr.patch`** (`tools/research-runner.py`): a Jan job gets a fresh LDR when the running one
  holds at least `LDR_FRESH_RSS_GB` (default 1.0 GB; a fresh idle LDR is about 0.3 GB). This is the bench's 11-01
  condition applied to Jan, and it costs about 30 s per job start. The log says "LDR restarted fresh ... (LDR holds X
  GB ...)"; the old profile-restart line is unchanged.
- Optional, measure first: `MALLOC_ARENA_MAX=2` (or 4) in `run-ldr.sh`. There is no staged diff for it, and the
  offline test could not show a gain.
- Already done: patch 0006 (page caps); DOC_SCHEDULER off (11-04).

**Tests** (`tests/run.sh`): it builds `scratch/testsite`, a copy of the installed package with 0007-0009 applied, and
runs `tests/test_ldr_study.py`. **15 / 15 pass** (`tests/test-output.txt`). The memwatch ones cover the record fields,
a trim after a 3 x 190 MB burst in short-lived threads (freed 186 MB), the fetch thresholds and the 20-s gap, the
research end (record, file cache emptied, trim from the timer), and the switch-off. The runner rule is tested on the
test process's own `/proc` entry.

## 5. Install (only when Karl says so; no LDR run or Jan job live)

1. `patch -d .venv/lib/python3.12/site-packages -p1 < staging/ldr-study/patches/0007-memwatch.patch` (then 0008 and
   0009 if those are wanted too, in that order; see PAPERS.md). Back up the touched files first, as earlier installs
   did.
2. `patches/ldr/make-patches.sh`: this regenerates 0001-0003 so that they contain the change. Checked on a scratch
   copy: after the three patches plus a regeneration, apply.sh's state test answers "patched". Without the
   regeneration it answers "modified", because 0007-0009 edit lines that 0001-0003 add. apply.sh itself needs no change.
3. Runner: `patch -d /home/USER/ai/deep-research -p1 < staging/ldr-study/patches/runner-fresh-ldr.patch`, then restart
   the runner unit while no Jan job runs.
4. It takes effect at the next LDR start. Then read `logs/ldr-mem.jsonl` after one bench question: the research-end
   RSS vs the trim's RSS, the peak phase, and the scheduler-off comparison.

Undo: the backups; or reverse-apply in reverse order and regenerate again.

## 6. Files

`patches/0007-memwatch.patch`, `patches/runner-fresh-ldr.patch`, `site/` (the staged files after all patches),
`orig/` (the installed files they were made from), `tests/`. Scratch: `scratch/bin/` (smaps_classify, repro_mem,
make_pages, store_replay, pdf_mem, big_events), `scratch/mem/`, `scratch/ramdip-ldr.txt`. Rule note: two commands used
`cd` (a subshell and a scratch-dir test run); neither touched anything outside staging/ldr-study.
