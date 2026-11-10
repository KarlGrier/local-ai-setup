# Phase 3 plan (draft 2026-10-17 21:10) - test set, baseline, failure sorting, thinking levels

## Test set (frozen before any run; answers stored apart from the questions)

* `questions-screen.jsonl` / `questions-holdout.jsonl`: id, kind (checkable | open), question, files (open-ended).
* `answers/` (outside anything a run reads; runs never see it): per checkable id the answer, accepted variants
  (numbers with units, name spellings), and two sources (URL, date, the quoted sentence) that I checked myself.
* Checkable (15 + 15): hard, multi-step (2-4 hops: find X, then a fact about X), short checkable answer, about events
  after the model's knowledge (July 2026 or later), spread over topics (science, sport, business, tech releases,
  politics, culture) so no single site answers everything. Each must be answerable from public pages that LDR's
  SearXNG engines can reach (checked: the two sources open without a login).
* Open-ended (3 + 3), from the user's uses, split so each set has one technique, one product and one news topic:
  - screen: (1) what is new in running MoE experts from RAM that Strata has not tried (files: strata-compare
    REPORT.md + NOTES.md); (2) which 16 GB card to add as a third GPU (5080 + 4060 Ti, 96 GB RAM); (3) a general
    topic (mine; chosen when the set is built)
  - holdout: (4) projects like Strata; (5) what is confirmed about Qwen4 Flash; (6) a product search (mine)

## Runs (daytime only, 09:00-23:00; one at a time)

* Baseline: pristine LDR 1.10.7 (`LDR_PROFILE=baseline`: its own defaults, the baseline SearXNG 8890, langgraph-agent,
  quick mode). Deep: the current deep profile (agent/extract/report/verify xhigh, workers 1). Same Strata (C\*18t),
  same sampling (T 1.0 / 0.95 / 20 / 0.05), start lines checked first.
* Budgets: checkable ~30 min research each, open-ended ~2 h (deep: LDR_DEEP_TIME_BUDGET_S; baseline: runs until its
  agent stops, cut at the same budget + report time).
* Through the job runner (deep) or tools/ldr-client.py (baseline) - not holding strata-compare's test lock (the gate
  would hold the research). Every model call's input and output captured (proxy capture mode, per run) so both setups
  can be sorted the same way.
* Estimate: deep 15 x ~1 h + 3 x ~3 h = ~24 h; baseline 18 x ~0.5 h = ~9 h -> about 2.5 days of daytime.

## Grading

* Checkable: automatic - the final answer is matched against the stored answer and its variants (normalised text,
  numbers with tolerance); a wrong or missing answer is a fail. Reported per setup: correct / 15, time per question.
* Open-ended: by me, blind (reports renamed A/B in random order, setup names and LDR/deep formatting cues removed),
  against my own research on the same question (done before I read any report): coverage of what matters, correctness
  of each checked claim, sources (dated, primary), fit to the user's hardware / files, and what it missed.

## Failure sorting (every failed checkable question, both setups)

From the captured calls and the deep evidence store: where does the answer string (or its variants) first appear?
* never found - in no search result and no page read
* found but not read - in a search snippet / result URL, but the page with it was never opened
* read but dropped - in a page that was read, but not in that page's extraction / the agent's notes
* in the notes but wrong in the report - in an extraction, subagent report or the lead's notes, but the final answer
  is wrong or missing

## Thinking levels per step (medium vs xhigh; low too for extraction)

* Extraction: replay recorded extraction tasks (the screen runs' pages + focus) at low / medium / xhigh; plus the
  old 36 tasks (results/extract-effort/) re-judged by me, blind.
* Report writing and citation check: replay from the screen runs' saved evidence (same outline, same evidence) at
  medium vs xhigh; judged blind; citation check also against my own verdicts on a sample.
* Agent steps: a second deep pass over the checkable screen questions with agent effort medium (everything else as
  the deep profile) - the agent level cannot be replayed.

## Checkpoint

Results (scores, time per question, the failure sorting, the level comparisons) and a ranked build list - then wait
for the go.

## Revision 2026-10-18 (the user's rules, after the baseline got 15/15 checkable)

* Hard checkable set (FROZEN-hard.txt): 20 questions that pass a snippet filter (answer not in the top-10 snippets of one
  plain search for the question), confirmed on two pages, split at random: `hard-screen` (h01-h10) replaces the screen
  set's checkable questions for comparisons; `hard-holdout` (h11-h20) replaces the holdout's. Open-ended o01-o06 stay.
* Phase 3 runs (queue-plan.json): hard-screen on baseline and deep; o01-o03 on deep; the easy set on deep for only
  5 questions (c02 c22 c24 c27 c29, random) - enough to show deep does not break easy questions, and for call captures.
* Grading of the hard set: the automatic grade is checked by hand per question (number/substring matching is loose).
* Phase 5 holdout: hard-holdout (10) + o04-o06 on baseline and the final setup.
* Revision 15:20 (the user): deep at **medium** is the main pass (o01-o03 + the 10 hard screen questions); **xhigh only
  as the confirming subset**: o01-o03 + 5 hard screen questions (h02 h04 h05 h06 h08, random). The 5 easy questions run
  at medium. Medium runs go first. Runs folders: `<set>-deep-medium/` (medium) and `<set>-deep/` (xhigh).
* Checkpoint item (the user, 15:30): the research-vs-chat wait table again at the chosen thinking levels; propose
  pre-empt-and-replay in strata-proxy only if a first chat message still often waits over a minute.

## Revision 2026-10-18 18:43 (the user, after the hard-screen baseline got 10/10)

* The hard set is at the ceiling for plain LDR too, so checkable runs show time and regressions only. Hard medium step
  cut to the 5 xhigh-subset questions (h02 h04 h05 h06 h08); the 5 easy deep runs dropped; no stricter checkable set.
* Two more open-ended screen questions, frozen 18:49 before any run (`screen-extra`, FROZEN-extra.txt): o07 new
  open-weight models that could replace Qwen3.8-Flash-Next on this PC; o08 open-source deep-research agents that run
  on a local model + SearXNG. Each on baseline, deep medium and deep xhigh; graded blind against my own research like
  o01-o03.
* Phase 5: the holdout's checkable questions are only a quick sanity check; the final result is judged on the
  open-ended holdout reports (o04-o06).
* Jan: `research_quick` (plain LDR's quick summary, ~1-3 min) next to the deep report, so factual questions don't
  need a deep run (README "Quick answers").
* 10-18 21:1x: from 10-19 on, both profiles fetch one page at a time (patch 0004, after the lxml thread crash) and LDR
  runs on CPython 3.12.13. Earlier runs fetched in parallel on 3.12.3: compare times across that line with care.

## Phase 4 build list (candidates; ranked at the checkpoint, built only after the go)

**Testing order (the user, 10-20):**
1. Each item is tried first on replays of the saved runs:
   * the hardware profile at the step where each error starts (corrected 10-20 evening): the lead agent's final answer
     replayed +/- the profile (o07 call 650, o02 call 635), the reports written from those answers, and report
     replays from the original lead answers +/- the profile (o07, o02);
   * the "not yet" check run directly on the saved o03 reports.
2. Only items that fix their test case on replay get full deep runs, with and without, on the new build.
3. Only items that pass that go to the screen set.

Items that change what gets searched (early stop, the "tried" list, extra sources, ...) still need full runs. Details
and the estimate: CHECKPOINT-phase3.md section 8.
10-23 (the user, after the phase 4 checkpoint): item 2 (the "not yet" check) is bundled into the next item's stage 2-3
runs (item 4, the "tried / ruled out" list) instead of separate runs; early stop is dropped from deep research (a
quick-research idea only); next is item 4.

From the round brief: read sources whole and follow links to primary sources; an evidence store of claims (quote,
URL, date); gap analysis for the next searches; two independent sources for important claims, with disagreements
recorded; stop when searches stop adding facts; section-by-section writing, then a fresh-context critic, targeted
research and revision, with a verifier that removes unsupported claims; a "tried / ruled out" list from the user's
files; report rules (a link per claim, newest first with dates, rumours labelled, hardware fit, technique maturity and
cost, product price and trade-off); token counting from the served model; 2-3 short runs merged vs one long run.

Added by the user during phase 3:
* (10-18) **Early stop** once the answer is confirmed in two sources. Deep spends its whole budget on questions the
  baseline answers in a minute. **10-23 (the user): dropped from deep research; kept only as a quick-research idea.**
* (10-19) **A fixed profile of the user's hardware and setup**, taken from the user's files and checkable by them, given
  to the report writer. The citation check then verifies claims about the user's own setup against those files, not
  only web claims against web pages. Reason: o01 at medium called the CPU a "16-core AMD 9800X3D" (it is a 9950X3D),
  gave the 5080's link two different ways, and used an odd model name.
  - Profile contents: RTX 5080 16 GB (PCIe Gen5 x16) + RTX 4060 Ti 8 GB (chipset Gen4 x4), 96 GB DDR5-6000,
    Ryzen 9 9950X3D (AVX-512, no AMX), Linux, Strata C*18t serving Qwen3.8-Flash-Next IQ3_S.
  - Fits with the "tried / ruled out" list above: both are extracted once per file set and saved for the user to
    check.
* (10-19) **Semantic Scholar's own engine** (official API, no key; LLM relevance and journal filters off), on in the
  user's research since 10-19 and off in measurements: A/B on the screen set alongside Tavily (same design).
* (10-19) **Tavily as an extra source**, not only a fallback: A/B on the screen set (deep at the chosen level; SearXNG
  alone vs SearXNG + Tavily for every search), judged blind like the open-ended questions. Watch the free 1,000
  credits/month: a deep run makes ~60-240 searches, so the A/B needs roughly 1-3 months' allowance or a paid month.
* (10-19) **Exa 3.0 (released 10-19), the user's three items:**
  (a) **Exa Lite as an extra source** on the screen set, next to Tavily (same design: SearXNG alone vs SearXNG + Exa
      Lite for every search, judged blind). Lite is $4 per 1,000 searches; the free $10/month (our cap $9.00 =
      2,250 Lite searches, shared with the fallback) covers ~9-35 deep runs at 60-240 searches each.
  (b) **Exa Dynamic Highlights instead of our local page extraction on some pages:** for a share of the pages (e.g. the
      ones Exa returned), take Exa's highlights for the query instead of fetching the page + Strata's extract call.
      Compare research time and report quality (blind), and check whether the highlights are verbatim enough for
      the citation check (quotes found word for word on the live page). Dynamic Highlights: Exa's 3.0 post calls
      them generally available at no extra charge; the API reference still needs the header
      `Exa-Beta: dynamic-highlights-2026-08-28` and they cannot be combined with maxCharacters. Check first whether
      Lite accepts them (Lite rejects unsupported parameters with HTTP 400); otherwise Auto ($7 per 1,000).
  (c) **Product questions and Exa's shopping index** (3.0 added 1.27B shopping listings with prices and availability,
      on the same index for Lite and Auto): a few product questions written and frozen before any run; SearXNG alone
      vs + Exa; score whether prices and where-to-buy are right and current (checked against the shops' pages at
      grading time).

## Switch point between phase 3 and phase 4: chat-cache memory change (the user's OK of proposal A, 2026-10-19)
Applied once phase 3 is complete (after its checkpoint, with the 0.2.0 port), never mid-queue, so phase 3 run times
stay comparable. Record the exact switch time in NOTES.md.
1. Research calls are marked by the proxy (tools/strata-proxy.py apply_chat_cache_policy, run/chat-cache-policy.json,
   built and tested 10-19, OFF until the switch): every research call carries strata_owner=research; the one-off
   classes (extract, compact, report, verify, other) carry strata_checkpoint=false (upstream #830: no checkpoint, so
   nothing to park; already in the served build); report/verify calls carry strata_chat_drop=research.
   The user's chats (Jan, OpenCode, dsh) carry no tag and keep being parked.
2. Engine + server change on the ported build (not written yet): GEN keys owner=<tag> (kept on the live conversation
   and on its parked copy) and chat_drop=<tag> (drop every parked conversation with that tag, and do not park the live
   one if it has it, before the request). Server: strata_owner / strata_chat_drop -> those keys (validated short words).
3. Before switching on, confirm parking only affects speed (bringup/lib/roundtrip.py on the phase 4 build: direct x2,
   park -> resume, resume + edit: NLL identical and the same state hashes); also a strata_checkpoint=false call vs the
   same call without it (same output), and the drop: research conversations gone, a Jan-style chat still parked and
   resumed. If a resumed conversation does NOT match a fresh one, stop and tell the user (it matters for the replays).
4. Decided (the user, 10-19): keep parking the research agent's conversation (o03: 213 of 318 agent calls resumed it,
   6.16M tokens = ~24 min of re-reading saved on a 143-min run); skip parking only for the one-off calls; drop at the
   report start.
5. After the first phase 4 run: report the lowest free memory (MemAvailable) and whether any relief restart happened.

## Comparing phase 4 with phase 3 (the user's rule, 10-19)
Phase 4 runs on a new build (0.2.0 port + chat-cache change): never compare its minutes with phase 3's. Chosen: compare
across the switch by work, not time - calls (per class), prompt tokens, tokens read fresh, generated tokens, searches,
page fetches (tools/run_work.py, from the proxy's call log and the run's capture; costs nothing). Minutes are compared
only between runs on the same build (every phase 4 A/B has both arms on the new build). Not chosen: re-timing a phase 3
run on the new build (~2.5 h of queue time for one run, and one run says little about run-to-run spread). The port
round's A B B A speed checks (decode, 32K prompt) give the build-to-build speed ratio as context.

## After phase 5 (the user, 10-19)
* Quick answers during measurement runs: they fall back to web_search (NOT STARTED) while a measurement holds LDR.
  Revisit if they are still often blocked - option 1 of results/proposal-quick-answers-2026-10-19.md (a separate
  on-demand quick LDR). Option 2 (quick-only limits) is built.
