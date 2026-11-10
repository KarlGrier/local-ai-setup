# Items 5 + 6 bundle with the six-fix follow-ups (A8) - staged, not installed (10-27 night)

**Where things stand:**
- The code is in ~/ai/deep-research/staging/bundle-1028 (copies of deep/*.py, the strategy and the fetch tool). The
  installed LDR package is untouched while stage 3 p4s6 runs.
- It is installed only after p4s6 is graded and the six fixes pass the gate (Karl's rule: a bad or mixed result
  stops here).

## What is in it

**Item 6: every cited source read** (`LDR_DEEP_FIX` gains `read`; never part of `all`):
- **New deep/reading.py, a background reader.** Each page a subagent's findings (or the lead's answer) cite without
  having read it is fetched (one at a time, under the run's egress policy, no model call) and kept in the store.
- **Primary sources.** A cited page that is not itself primary leads to up to 2 primary sources named in its text:
  written-out URLs on primary hosts, arXiv ids, DOIs, EU acts as EUR-Lex CELEX links, GitHub repositories. They are
  ranked by closeness to the citing sentence's words and get their own [N].
- **Caps:** 400 pages and 40 primary sources per run. The reader stops at the run's deadline.
- **Report writer (report.py):**
  - it waits for the last pages (at most 12 % of the time left, 15 min), then stops the reader;
  - only read sources are citable;
  - a reader-read page shows its most relevant passages;
  - labels carry the date and "primary source behind [N]";
  - the section rule says to cite only the evidence.
- **Fix 4's citation guard** treats a citation of an unread page as outside the evidence.
- **evidence.py:** add_read / mark_unreadable / link_primary, read / unreadable / primary records, and stats.
- **seed.py:** reloads these records.
- **strategy:** starts the reader after the tools are built and stops it at the end.

**Item 5: claims with quote, URL, date** (`claims`):
- **New deep/claims.py.** The extractor already returns verbatim quotes, one per line. Each becomes a claim in code,
  with no model call:
  - checked word for word against its page ("exact" / "close" / "not on the page");
  - dated from the quote, else the nearest date before it on the page (≤ 800 chars), else the page's date.
- The writer's evidence per source is the checked, dated quotes, with a rule to give dates where timing matters.
- **Offline on the combined rerun's evidence:** 11,299 quotes from 392 extractions; 90 % exact, 4 % close, 7 % not on
  the page (kept out); 4 s, no GPU.

**A8 (1) Fix 1** (A8-FIX1-MISSES.md):
- names described as this engine's are marked too, not only recommended ones;
- the shared launcher / CLI / server folders are kept apart from the engine's own code (new kind "launcher-only");
- another program's name presented for this engine is marked;
- JSON config keys (`"gpu"`, `"layer_split"`, ...) are checked;
- name cap 120.

Offline: the 10-24 report now yields the 5 config keys; the flag rules were checked on a test set.

**A8 (2) Fix 5:**
- A task that names a program version the profile does not have is about another state. The lead, the report writer,
  the setup check and the consistency pass then get the profile's hardware only, plus a note.
- Offline: the 10-24 question gets the hardware-only view; o01-o03 and the hard five keep the whole profile.

**A8 (3) Consistency:**
- The prompt asks for a rule applied to this setup against a claim about it, and gets the setup facts.
- A focused step per action-list setting (up to 10, 5 per call) collects its sentences across sections: rules first,
  at most 3 per section.
- Offline: the K4 pair (Tier A "auto loads the drafter" vs the DSpark section's 1.5x rule) is now in one prompt.

**A8 (4) Fix 1 false flags** (from stage 3 p4s6 o01, 10-28 00:40): all 5 of o01's version-check flags were false -
`--expert-cache`, `--kv-resident`, `STRATA_KV_PREFETCH`, `STRATA_EXPDEC` (and `STRATA_DS4_AUTO_PIN`, a server setting)
are options of Strata v0.2.6. Two causes:
- the engine's folders are the overlap of two model answers; for a whole-project question one answer took only the
  DeepSeek engine, the other every engine and src/core, kernels, prefill - so the overlap made src/core's options
  "another engine". Now: the prompt says a whole-project task lists every engine; folders only one answer names are
  "disputed", and a name found there is not flagged (kind "unsure");
- the repository-wide search keeps 400 hits and bench/results filled them (--expert-cache: 380 files), hiding
  src/program's hit. Now: when the search is cut, the engine's, shared and disputed folders are searched on their own.
- Offline (o01's clone, the run's two folder answers, a fake model that says "another engine" for all 5): --expert-cache
  now has 51+ hits in the engine's folders (0 before), --kv-resident 5+; 4 of 5 come out "unsure" (not flagged);
  STRATA_DS4_AUTO_PIN (serve/server.py only) is left to the model. The real replay is in step 3 below.

**Fix 3 regression** (from the combined rerun):
- A result without its unit uses the unit-aware value ("75 GB ÷ 11.4 MB = 6,579"), and % counts as /100.
- A match a power of 1,000 away is "units unclear", not "wrong".
- Ranges ("= 18-25 MB") are not checked.
- ^ is an operator.
- Offline:

| report | wrong flags before | after |
|---|---|---|
| combined rerun (fixed) | 14 | 1, the real "5.9 GB + 1,357 × 11.4 MB = 15.5 GB" (21.4) |
| planted copy | 3 of 3 caught | 3 of 3 caught |
| code-tool rerun | 0 | 0 |

**Fix 3, two more false-alarm kinds** (from stage 3 p4s6 o02, 10-28 03:20; o02's 2 "wrong" were both false):
- a unit written on one side only, either side ("132.07 / 15,360 = 8.6 MB each", the GB cut off on the left): a match a
  power of 1,000 away is "units unclear" (was: only when the result's unit was missing);
- a side that goes on calculating ("138 + 110 = 248 GB / 1.8 GB/s ≈ 138 s"): its first number is compared too.
- Offline (no model): planted copy 3 of 3 still caught; combined rerun (fixed) still 1, the real one; p4s6 o02 2 -> 0
  (2 "units unclear"); o01 / o02 of all three arms 0 wrong.

**Tools:**
- fix-replay.py `write` (the whole report stage from saved evidence, any fixes / items).
- read-pass.py (item 6 offline: the cited-but-unread pages fetched now, plus primary sources, into a copy of the
  evidence).

**Karl's decisions 10-28 ~07:30 (go into the bundle before its replays):**
- **Setup check without the like-with-like notes** (staged deep/setup.py, backup .before-nobaseline): the check no
  longer asks for "baseline" verdicts, and one returned anyway is not marked; "already set" stays. The writer's own
  like-with-like rule (report.py) is unchanged. Offline test: the prompt has no baseline rule, an already-set claim is
  marked, a baseline claim is ignored.
- **Profile (user-setup.md, after the hard five end, not mid-run):**
  - the OS line says the user has root and makes system changes themselves (the no-sudo rule is Claude Code's only);
  - a line says the served Qwen uses MTP speculation (up to 7 draft tokens with the adaptive draft-length rule,
    min-p 0.5).
- **Stay as they are until later:** o01's frozen "4060 Ti 16 GB" text until after the bundle's stage 3 (corrected for
  the Phase 5 holdout); SearXNG safe_search 0 until the LDR week ends (then 1).

**INSTALLED 2026-10-28 08:48** after the p4s6 gate passed (narrow: open 29.0 / 28.0 / 22.5 of 34, hard five 5/5 tie;
blind-p4s6/SUMMARY.md). install.sh: 8 files (reading.py, claims.py new; strategy, checks, report, evidence, seed, setup
changed; *.before-bundle kept), imports ok, patches/ldr regenerated. LDR stopped for a clean restart (it starts again on
the next run; Strata is off while gap 12 holds the GPU). Items wired (backups *.before-bundleitems): bench2-queue.sh
plan items `read`, `claims` -> LDR_DEEP_FIX=all,read,claims; run-ldr.sh writes them to run/ldr.items as "read" /
"claims" ("fixes" for all, "fix:<list>" for a subset); codetool-test.py --bundle (run-full-bundle). Profile edits done
08:47 (user-setup.md.before-mtp-root): MTP speculation line; root for the user, no-sudo for the assistant only.

**WATCH ITEM (Karl, 10-28 ~09:00) - the bundle's combined rerun (10-24 question, full 240 min):** compare the blind
answer-key score and the wrong-engine count with the code-tool rerun without fixes (run-full: 3.5 of 7, 6 wrong-engine
names, 246 research min). Read it at equal research time: the effort table's research minutes must be within ~10 % of
run-full's 246, else say how far apart they are. "Clearly worse" = key score 2.5 of 7 or lower, OR wrong-engine names
9 or more (the six-fix run's 2.0 and 11 qualify). If the bundle run is clearly worse, FLAG IT TO KARL before the
bundle's stage 3 result counts (stage 3 may still run; its result is held until Karl decides).

## To do after p4s6 is graded (Wed 10-28)

1. **Install:**
   - back up the installed files (*.before-bundle);
   - copy the staged files in (deep/*.py incl. the new reading.py and claims.py, the strategy, the fetch tool is
     unchanged);
   - regenerate patches/ldr.
2. **Items in the bench and run scripts** (only when no run is live, since bench2-queue.sh must not be edited while it
   runs):
   - bench2-queue.sh: items `read`, `claims` add to LDR_DEEP_FIX (`all,read,claims`);
   - run-ldr.sh: the same for its items;
   - codetool-test.py: a `--bundle` flag (all,read,claims).
3. **Replays:**
   - Fix 1 on the 10-24 report and both reruns;
   - Fix 1 on p4s6 o01 (its 5 false flags must clear; the 10-24 report's real flags must stay);
   - Fix 3 (model-listed half) on both reruns;
   - Fix 5 + consistency on both reruns (K4 must be caught);
   - item 5 + 6: `fix-replay.py write` on p4s6 o01-o03 (+ the read pass), with and without, graded blind.
4. **One combined rerun:** the 10-24 question, 240 min, vs run-full-fixes. **Then one stage 3** at 171 / 47 min vs p4s6.
   - **Karl 10-27: report research minutes and code-tool calls next to the answer-key score**, so the effect of less
     research time can be told apart from the fixes themselves. Table:
     `/usr/bin/python3 -I tools/effort-table.py LABEL=RUN_DIR ... --score LABEL="x of 7 (overall y of 10)"`.
     - Research min = deep.elapsed_s - deep.report_seconds.
     - Code-tool calls = deep/code-tool.jsonl operations: grep / read / tree / GitHub API (clone and pin are not counted).
     - The scores come from the blind grading only.
     - Baseline rows, both graded in one round (blind-fixes):

| run | research min | report min | research code-tool calls (search / read / tree / GitHub) | calls per research min | checks' code-tool calls | answer key (blind) |
|---|---|---|---|---|---|---|
| rerun, no fixes (10-27 08:00) | 246 | 44 | 487 (237 / 115 / 15 / 120) | 1.98 | 0 | 3.5 of 7 (overall 3.0 of 10) |
| six fixes (10-27 16:55) | 180 | 58 | 261 (99 / 63 / 8 / 91) | 1.45 | 66 | 2.0 of 7 (overall 4.5 of 10) |

     - Corrected 10-28 00:30: the first version of this table counted the version check's own greps (Fix 1, in the
       report stage, 66 calls) as research calls (327, 1.82 a minute). Research phase only:
     - Reading: the fixes run had 66 fewer research minutes AND used the code tool less per minute (1.45 vs 1.98):
       searches 0.55 vs 0.96 a minute (99 vs 237), reads 0.35 vs 0.47, GitHub the same (0.51 vs 0.49). One run each, so
       the per-minute drop may be run-to-run variation; the six fixes act in the report stage, not in the research.
     - The bundle's rerun gets the same 240-min budget as the fixes run; its row goes under these two.
     - Scores from different grading rounds are not compared directly (blind-grading rule), so all three reports are
       graded again together in one round.

## Replays 10-28 (run-replays-bundle.sh, from 10:57) - first results

- **Fix 1:** p4s6 o01's 5 false flags are CLEARED (all five now "this version"; the replayed report has 0 version marks;
  its 22 other-project names, e.g. KTransformers' --kt-* flags, are "attributed" and not marked). The 10-24 report:
  of the grader's 30 wrong-engine names, 25 are marked in the text (21 before). Marks rose 56 -> 133 (new kind
  "launcher-only": Qwen-launcher options offered for the DeepSeek engine); whether any are false marks is judged in the
  replay grading. Not marked: --cache-type-k, --kv-cache-dtype (judged "attributed" to llama.cpp/vLLM),
  --conversation-cache-mib / -slots (launcher-only, attributed), --fit.
- **Fix 3:** planted 3 of 3 caught; the six-fix run's real error (5.9 GB + 1,357 x 11.4 MB = 21.4, not 15.5) still
  flagged. Two NEW false alarms from the model-listed half: "within 2 % of the measured 11.7 s" checked as "= 2 %", and
  "~2-3 MB" checked as "= 2". Fix staged 10-28 (staging deep/checks.py, backup .before-bounds): the prompt asks for
  "bound" (= / ~ / <= / >= / range with stated_low/high), and the quote's own words decide when the model does not say
  ("within / under / up to" -> <=, "at least / over" -> >=, "~ / about / roughly" -> ~ at 15 %, "a-b" -> range).
  Offline over 484 model-listed calcs (today's replays + p4s6 + both reruns): only those 2 change (to ok); the written-
  equation tests are unchanged (planted 3/3, the real one, o01-o03 0).
- **HOLD:** the chain (chain-bundle.sh) is held (fixes/HOLD-bundle-chain) so the combined rerun does not start on the
  known false-alarm code. When the replays end: install the staged checks.py (no run live), remove HOLD, start the chain
  again (it then runs the rerun, then stage 3 p4s7).
- **Done 15:26:** replays ended 15:24 (kcheck rc 0); staged checks.py installed (backup checks.py.before-bounds,
  patches regenerated, 0001 backup .before-bounds); HOLD lifted; chain restarted (ldr-bundle-chain). Combined rerun
  running from 15:26 (LDR env checked: LDR_DEEP_FIX=all,read,claims, CRITIC, CODE, setup profile).

## Replays 10-28 - the rest (F5c, write replays) and a replay flaw

- **F5c (Fix 5 + consistency, rerun reports):** K1 caught (layer-major vs the single-device gate, pairs 5 and 21).
  K4: the setup check marks the headline "`--dspark none` is the mandatory first action" as ALREADY SET (the baseline
  already runs without DSpark) - the K4 error is flagged. The consistency pass still does NOT find the K4 pair itself
  (Tier A "auto loads the 8 GB drafter" vs the DSpark section's 1.5x rule); its focused --dspark step found a weaker
  pair (8 GB vs 5.6 GB freed). Pairs: 26 on run-full (14 in round 1), 29 on run-full-fixes - false alarms not judged.
- **CORRECTION - the Fix 1 replay of p4s6 o01 had no code.** fix-replay.py gives the version check only the repos the
  question or profile link; the p4s6 research had cloned Niko1221/Strata itself (its deep/code-tool.jsonl), a replay
  starts with a fresh code tool, so b-f1-p4s6o01 and all six write replays ran the version check WITHOUT the clone
  (engine_dirs {}). "o01's 5 false flags cleared" above is therefore NOT shown. The 10-24 replays (b-f1-jan1024 /
  -full / -fixes) did have the clone (the question links the repo) - their results stand.
- **No-code false flags:** without the clone the model reads "docs only, no engine code shown" as "another engine":
  o02 write replays 25-26 marks (Qwen-engine options such as --pcie-frac, --pipeline-windows, STRATA_SPLIT_UNIFORM).
  In live runs this path is rare (the research usually clones the repo), but possible.
  - Fix staged (staging deep/checks.py, backup .before-nocode): no engine folders read from the code -> "another
    engine" / "launcher-only" become "unsure" (not flagged); other-project / other-version / not-found stay. Offline on
    the saved results: o02 25 -> 5 and 26 -> 4 (the rest are quant names judged "another program" by the model);
    the 10-24 replays with the clone unchanged (9, 19, 40).
  - fix-replay.py (backup .before-knownrepos): the replay now also opens the pinned repos the research cloned.
- **Stage 3 held again** (HOLD-bundle-chain, 15:34): the chain stops after the rerun; after-rerun-1028.sh (unit
  ldr-after-rerun) then, with no run live, installs the staged checks.py, replays Fix 1 on p4s6 o01 and o02 WITH the
  clone (b-f1-p4s6o01-code, b-f1-p4s6o02-code), and starts stage 3 p4s7. STOP-after-rerun stops it.
- **Write replays (items 5 + 6):** blind 2-way grading in results/bench2/blind-bw (one fresh grader per question; inline
  marks and check sections stripped, so the version-check noise does not reach the graders). No "[from research
  context ...]" writer marks in any of the six. Fix 1's 68 flags on the 10-24 replays are being judged against the
  v0.2.4 code (fixes/fix1-judge/).

## WATCH ITEM - FLAGGED (10-28 21:10; codetool/SUMMARY-BUNDLE-1028.md)

The bundle's combined rerun (19:25, rc 0, kernel clean; research 182 min, report 57) graded blind in one round with
both earlier reruns: key 1.0 of 7 (code-tool rerun 4.0, six fixes 2.5), overall 3.5 of 10 (3.0 / 4.5), wrong-engine
names 10, 1 in the action list (5 / 2, 8 / 6). The watch rule is met on both counts, though not at equal research time
vs the code-tool rerun (182 vs 246 min). Stage 3 p4s7 runs on; its result is held for Karl's decision.
After the rerun: checks.py no-code version check installed 19:26 (backup .before-nocode); Fix 1 with the clone on p4s6
o01: 4 of the 5 old false flags clear (STRATA_DS4_AUTO_PIN stays - the server/launcher pattern); o02: 9 marks, mostly
that pattern. Stage 3 started 19:44 (after-rerun-1028.sh).

## Stage 3 p4s7 + the repo-page leak check (10-29 ~07:50)

- **Stage 3 (blind-p4s7/SUMMARY.md):** open 28.5 (bundle) vs 28.0 (six fixes) of 34; o01 7.5 / 8.5, o02 9.5 / 8.5,
  o03 11.5 / 11.0; wrong claims 18 / 19; hard five 5 of 5 each. No clear gain.
- **Leak check (Karl 10-29; saved evidence and logs only):** the bundle's 10-24 rerun fetched 14 Strata main-branch
  pages, 2 repo-root pages, 3 releases-list pages and 5 v0.2.7 pages next to 34 pinned at v0.2.4, plus 38 issue pages;
  item 6's reader read 6 Strata pages (all main / latest); link-following brought in none. The report cites 7 main pages,
  1 repo root, 3 releases-list pages, 1 v0.2.7 page next to 22 at v0.2.4 (the six-fix rerun: none at main; the
  code-tool rerun: 21 at main, scored best).
  - STRATA_PREFILL_LAYER_MAJOR / _DIRECT (+ _LM_*, and STRATA_PREFILL_WARM): issue #1670, a fork's feature request (base
    0.1.39, "PRs offered"), fetched in research; item 5 took 25 verbatim quotes from it (undated, "exact"), the writer
    stated them as Strata's. The version check classed them right (other version) but called the use "attributed".
  - ds4_experts_rule.hpp (main code-tool read, its title said OTHER VERSION - cut by the 100-character title limit in
    the writer's source labels), STRATA_READ_AHEAD and --resident-budget-gib ("the v0.2.4 troubleshooting notes" =
    main's TROUBLESHOOTING.md, web fetch), --prefill-pipe (main MULTI_GPU.md): main pages written up as v0.2.4.
  - --dsv41-split / --dsv41-expert-profile: in no evidence, sub-agent note, lead answer or outline - the writer made
    them up (next to the main MULTI_GPU / ds4_experts_rule citations).
  - So 7 of the grader's 10 wrong names come from Strata pages not at v0.2.4 (4 main, 3 the fork's issue), 2 are made
    up, 1 is llama.cpp's (hedged). Item 5's rule "state each fact as its quote supports it" turns those quotes into flat
    statements - the bundle-specific part.
- **Fix (installed 07:48, backups *.before-verpin):** codetool.version_note() labels a pinned project's GitHub page at
  another ref (blob/tree/raw at main or another tag, the repo root, a newer release, the releases list, an issue / PR,
  a single commit); report.py puts the label AHEAD of the title in every writer prompt and the verifier's source
  blocks; the section rule: such a source's flags / defaults / files / numbers are never the user's version's, and stay
  out of the recommended steps unless a source at the user's version confirms them. Offline: 66 of the bundle rerun's
  752 read sources labelled. (A version-check rule for "attributed" names was tried and dropped: +1 true, +1 known-false
  mark, still missed _DIRECT.)
- **Running (unit ldr-after-stage3):** the report-stage replay on the bundle rerun's evidence (b-w-bundle-verpin), then
  the second 10-24 rerun with the fix (run-full-bundle-verpin, 240 min). Both graded blind against the first bundle
  rerun and the six-fix rerun.

## Karl 10-29 (after stage 3): decision rule and the o01 trace

- **Decision after the second 10-24 rerun:** KEEP items 5 + 6 in the deep defaults if its answer key is at least the
  six-fix level (2.5 of 7) AND its action list has no more wrong-engine names than the six-fix rerun's (graded in one
  round). If still clearly worse: find which item drives it (item 5's quote-as-fact writing or item 6's fetching) and
  report BEFORE changing any default.
- **o01 trace (blind-p4s7/SUMMARY.md):** the bundle's 6 wrong claims are all the writer's (4 with no source, 2 misreads
  of correct sources); none is a proposal / forum / Q&A post stated as fact -> the label is NOT extended beyond GitHub.
- **Replay with the labels (08:38, b-w-bundle-verpin, same evidence as the first bundle rerun):** cited non-v0.2.4 Strata
  pages 15 -> 0 (58 sentences -> 0); ds4_experts_rule.hpp, STRATA_READ_AHEAD, --resident-budget-gib, --prefill-pipe,
  STRATA_PREFILL_WARM and the made-up --dsv41-split / --dsv41-expert-profile are gone; STRATA_PREFILL_LAYER_MAJOR /
  _DIRECT remain only as "a proposal for the Qwen engine, not v0.2.4". --cache-type-k 4 -> 3 mentions (llama.cpp).
  Second 10-24 rerun with the fix running from 08:38 (run-full-bundle-verpin).
