# Phase 4 items 5-8: estimate for Karl's decision (10-27, no rush)

Read from the code as it stands after the six fixes, and from measured phase 4 run times. Nothing was changed for this.

**Time basis:**
- With Fix 6 the budget covers the whole run.
- At stage 3's matched budgets (171 min open, 47 min checkable), an open question takes ~2.85 h and the hard five ~3 h.
- A stage 2 (o01 + o03, one side) is therefore ~5.7 h, and a stage 3 side (o01-o03 + the hard five) ~11.5-12.5 h.

**The "without" side** is stage 3 p4s6 (tonight) if the six fixes are adopted and the build stays the same. Add **~12 h
for a fresh "without" side** if the build moves first: the Strata v0.2.7 port, or A8 follow-ups big enough to change the
reports.

Grading is my time, not GPU time: ~30-45 min per pair of open reports.

## Per item

| item | what exists | code h | GPU h | test cycles |
|---|---|---|---|---|
| **5 Evidence store of claims** (quote, URL, date; reports written from it) | evidence.py keeps every source, snippet, page text (up to 120K chars) and extraction; seed.py reloads it | **6-8** | **~23**: replays ~5-6, stage 2 ~5.7, stage 3 ~12 | **3** (+1-2 replay correction rounds) |
| **6 Read sources whole, follow links to primary sources** | pages that are fetched are already read whole (120K chars); the gap is that ~85 % of cited sources were never fetched (snippet only), and no link is followed | **4-6** | **~20**: offline part ~2-3, stage 2 ~5.7, stage 3 ~12 | **2-3** |
| **7 Extra search sources** | Exa-then-Tavily fallback (patch 0005) and Semantic Scholar's engine exist; Jan's runs already use both; measurements keep them off | **5-8** for all five parts | **~50** | **5** (one per part); calendar 1-2 months (credits) |
| **8 2-3 short runs merged vs one long run** | seed.py continues one run from its saved evidence | **3-5** | **~21**: replay ~3, stage 2 ~5.7, stage 3 ~12 | **3** |

### Item 5: evidence store of claims

**Code:**
- Claim records (quote, URL, date, source [N]) in the store, mirrored to claims.jsonl.
- Extraction returns claims whose quotes are checked word for word against the page text in code (the fixes' quote
  matcher); unverified quotes are dropped.
- Dates come from the page or the search result, or the claim's own date.
- The report writer picks each section's evidence from the claims.
- The citation check reads the claim quotes directly.
- seed.py carries the claims.
- An offline builder makes claims from a saved evidence.jsonl, for the replays.

**Replays:**
- Build the claim stores from p4s6's saved o01-o03 evidence and rewrite those three reports with and without them,
  graded blind.
- Also measure the share of quotes that pass the word-for-word check, and of claims that carry a date.

**Cost to watch:** claim extraction writes more per page, so fewer pages fit in the same budget.

### Item 6: read sources whole, follow links to primary sources

**Code:**
- "Read before cite": a rule for the agents, plus a capped automatic fetch of cited-but-unread sources inside the
  research window.
- Link following, one step deep: from a secondary page (news or a blog) to its primary source (regulator, paper, repo,
  vendor docs), chosen by a heuristic plus one model pick.
- Fetch quotas per run.
- Metrics: the share of cited sources read, and primary vs secondary sources.

**Offline part (no true stage 1, since fetching changes):**
- Fetch now the sources that p4s6's o01-o03 reports cited without reading (network only).
- Rerun the citation check against the full pages.
- That counts the snippet-only citations the full page does not support.
- Caveat: pages may have changed since the run.

**Cost to watch:** reading more within a fixed budget means fewer searches. That trade-off is what the runs measure.

### Item 7: extra search sources

Better split into parts, since credits limit some of them:

| part | code h | GPU h | limit |
|---|---|---|---|
| 7a Semantic Scholar on every search | ~0.5 (already in Jan's runs; lift bench2's refusal for the arm) | stage 3 side ~12 | free |
| 7b Tavily on every search | ~2 (merge + dedupe with SearXNG, per-run credit cap, key read from its file inside the script) | side ~12 | 1,000 credits a month ≈ one screen side |
| 7c Exa Lite on every search | ~1 (shares 7b's merge) | side ~12 | Exa's $9 cap, shared with Jan's fallback; resets 11-01 |
| 7d Exa highlights instead of local extraction on some pages | ~2 | extraction replay ~1 (~30 Exa requests), then test case + side ~11 | Exa cap |
| 7e Exa shopping (product questions) | ~2 to write 3-5 questions, frozen first, Karl approves | 2 sides ~15 (new questions need their own "without" side) | Exa cap |

Bundling 7a-7c into one "all sources" side saves ~24 h, but cannot say which paid source earned its credits. That is
the point of item 7, so I'd keep them apart, or bundle 7a-7c first and test 7b/7c apart only if the bundle helps.
7d's replay alone decides whether 7d goes further.

### Item 8: merged short runs

**Code:**
- A research-only mode for the short runs.
- Merge 2-3 evidence stores with citation renumbering (the new part: seed.py reloads one run, not several with
  overlapping URLs).
- One report from the merged store.
- Under Fix 6: N research windows plus one report reserve, with the same total time as one long run.

**Cheap first test (offline):**
- o01-o03 each already have 4-5 saved full runs (p4base, p4s2-p4s6).
- Merge each question's evidence and write one report, graded blind against the single-run reports.
- This tests the "merge" half before any short runs are made.

## Items 5 and 6 built together and tested as one bundle

They fit together: item 6 decides which pages are read, and item 5 turns what is read into checked claims. Built
together, the claim extraction is written once, for the pages item 6 adds.

| | items 5 and 6 apart | bundled |
|---|---|---|
| code h | 10-14 | **9-12** |
| GPU h | ~43 | **~21-24** |
| test cycles | 5-6 | **3** (+1-2 replay correction rounds) |
| calendar | ~6-8 days | **~3-4 days** (code in the gaps over 1.5-2 days, replays day 2-3, rerun + stage 3 one night) |

**Testing, like the six fixes:**
1. **Replays, ~6-8 GPU h:**
   - claim stores built from p4s6's saved o01-o03 evidence, and the reports rewritten with and without them;
   - item 6's offline pass (the cited-but-unread pages fetched now) fed into the same stores, to show what the extra
     pages add;
   - graded blind against the p4s6 reports.
2. **One combined rerun, ~2.9 h:**
   - o03 with both items, against p4s6's o03;
   - o03 because it rests on dated regulation facts with primary sources (the Official Journal), so both items matter.
   - o01 + o03 (~5.7 h) if Karl also wants item 5's own stage 2 case.
3. **One stage 3, ~12 h:**
   - o01-o03 + the hard five at the matched budgets;
   - the hard five may run longer with more reading, but still end by 47 min.

**Risks:**
- If the bundle regresses or comes out mixed, splitting it costs one more stage 3 (~12 h).
- The replays give item 5 its own signal, but item 6 only a partial one.

## All four

| | code h | GPU h | test cycles |
|---|---|---|---|
| each item apart | 18-27 | ~114 | 13-14 |
| 5 + 6 bundled, 7 and 8 apart | 17-25 | ~92-95 | 11 |

Item 7's ~50 h is limited by search credits, not GPU time. **Correction (10-27 20:50):** at stage 3's matched budgets a side is ~12.5 h, not the old ~8.5 h, so item 7 is ~65 GPU h and all four items ~130 h apart, ~110 h with 5 + 6 bundled. Karl's decision and the dated plan: PLAN-ITEMS5-8-1027.md.

## Fit with the other backlog items

- **C3b (per-model profile files):** items 5 and 6 add new fixed sizes (the claim budget per section, fetch quotas),
  which belong in the profile files.
- **C3c (bigger fixed sizes):** its "evidence per section 48K -> 72K" overlaps item 5, which changes what that evidence
  is. If items 5 and 6 go first, measure C3c's section size on the claim store.
- **Strata v0.2.7 port:** if the port lands between p4s6 and these runs, add ~12 h for a new "without" side on the new
  engine.
- **Jan:** Jan's jobs go first, so wall-clock dates can slip.
