# Item 8: merge tool (staged 10-29, NOT installed)

Item 8 asks whether 2-3 short research runs, merged into one evidence store and written up as one report, beat one
long run. This folder holds the **merge half**: a tool that merges saved deep runs of one question into one run
folder, offline tests on real bench2 runs, and the three merged folders for the first GPU test. No model, network, GPU
or live file was used. The installed package, tools/, run/ and the run folders were only read.

```
tools/merge-evidence.py     the tool (-> ~/ai/deep-research/tools/ at install; it needs nothing else installed)
tests/test_merge.py         offline tests; test-results.json / verify-results.json = the last results
merged/o01-3 o02-3 o03-3    the GPU step's input: p4s3 + p4s6 (+ its 10-28 read pass) + p4s7, per question
```

## What the tool does

```
merge-evidence.py --out OUT RUN_DIR RUN_DIR [RUN_DIR] [--evidence RUN_DIR=DIR] [--label RUN_DIR=NAME]
                  [--question FILE] [--index-order interleave|runs] [--subagent-order interleave|runs]
                  [--lead-share-tokens N] [--replace]
```

OUT is a run folder that `fix-replay.py write --run OUT` reads as it is: `marks.json` (the question, merged_from),
`deep/evidence.jsonl`, `deep/lead_answer.md`, `deep/subagents.md`, `deep/code-tool.jsonl` (the version check opens
the clones the runs made). It also writes `merge-map.tsv` (run, old_idx, new_idx, url) and `merge-summary.json`
(counts, warnings, examples). It takes about 2 s and 0.2 GB RAM per merge, and the output is byte-identical on
reruns.

- **One index per source.** URLs are normalised: scheme and host lower-cased, default port and trailing slash
  dropped, and in-page fragments dropped (`#L10-L20`, `#page=4`, `#section`). The fragment is kept for `file://`
  (`#part=N` is a different piece of the user's file) and for `#!` / `#/` routes. Matching URLs get one index, also
  inside a single run: a run's collector gives a URL a new index on every search, so 540-900 URLs per run had
  several indices. New indices are 1..N. By default they are assigned round-robin across the runs (see open point
  4). Any index without a URL still gets its own new index, so nothing keeps an old number by accident.
- **Records.** Every record of every run is kept, renumbered (`idx`, `via` and search rows) and tagged `"run"`.
  `seed.load` then does the per-source merge itself: the longest page text, all snippets, fetches and extractions,
  the first date, via and primaries. On top of that the tool drops:
  - claims whose quote the source already has (case and spacing ignored);
  - duplicate or self primary links;
  - `unreadable` records for a page that some run did read.
- **References.** These texts are renumbered: subagent texts and topics, notes, and lead answers. Every match of the
  report writer's own `CITE_RE` (`[N]`, `[N, M]`, `[N-M]`, `【N】`) is renumbered when all its numbers are sources of
  that run. A range stays a range where the new numbers are consecutive, and numbers that collapse into one source
  are dropped as repeats. Three cases are not renumbered:
  - inside backtick code, matches are left alone;
  - a match that was not a citation in its own run (`[0, 2]`, `[66866]`) is left as it is;
  - if such a match would now cite a merged source, it is written `[ N]` instead, so it cannot point at another
    run's page.

  Page text, snippets, extractions, claim quotes and fetch focuses are never touched.
- **Lead answers.** Each run's answer is kept as its own block (`===== Lead answer of run 2 of 3 (p4s6) =====`),
  renumbered. `--lead-share-tokens N` cuts each block to N/runs tokens with the served model's tokenizer.
- **Subagents.** Reports from all runs are kept, interleaved by default (run 1's first, run 2's first, ...).

## How it was tested

`nice -n 19 .venv/bin/python -I -B staging/item8/tests/test_merge.py [--claims]` takes about 30 s. It writes its
merges to tests/out and deletes them afterwards. `--verify DIR ...` checks existing merged folders instead.
It reads the originals and the merge with the installed `seed.load`, read-only and with no bytecode written.

1. **34 unit cases** for URL normalisation and renumbering (ranges, repeats, code, `[[N]](url)`, full-width
   brackets, non-citations).
2. **Five real merges:** o01 and o03, each as 2-way (p4s6 + p4s7) and 3-way (p4s3 + p4s6 + p4s7), plus o01 3-way
   with the options (p4base + p4s6 with its read-pass evidence + p4s4, `--lead-share-tokens 10000`, run order).
   Each merge is checked for:
   - **No collision:** each (run, old idx) has one new index, each new index one URL, no URL has two indices, and
     the merged store's sources are exactly the mapped ones.
   - **Citations:** every reference in every merged text is the original's with the new numbers, and its source has
     the original's URL. Text outside the references is unchanged. Non-citations cite no merged source.
     About 18-34K citations were checked per merge.
   - **Per-source content kept:** page text equals the longest copy; snippets, fetches, dates, titles, via and
     primaries are kept; every claim quote is kept, none appears twice and none is new; `unreadable` appears only
     where no run read the page; subagents, notes and queries are all kept.
   - **fix-replay's own path:** `fix-replay.py`'s `run_store()` (what `write` does before the model) runs on the
     merged folder. With `--claims`, `fill_store` also runs under `LDR_DEEP_FIX=all,read,claims` and rebuilds the
     claim stores (5-16 s).
   - **Determinism:** the same merge made twice gives identical files.
3. **The three staged folders** pass the same checks (`--verify`).
4. **The checker itself** was tested by corrupting a merged copy four ways: a citation, a claim, a fetch moved to
   another source, and a word in a note. All four were caught.

| staged | sources per run -> merged (in 2 / 3 runs) | pages read (p4s3/p4s6/p4s7 -> merged) | subagents | lead tokens whole -> share |
|---|---|---|---|---|
| o01-3 | 6235 / 6682 / 6660 -> 14644 (1321 / 470) | 219 / 462 / 516 -> 883 | 46 | 10.9K / 9.5K / 11.9K -> 9.3K |
| o02-3 | 8539 / 6596 / 6899 -> 15934 (1727 / 611) | 242 / 363 / 333 -> 641 | 40 | 8.2K / 6.2K / 7.9K -> 9.3K |
| o03-3 | 7702 / 7601 / 5947 -> 12865 (1678 / 955) | 270 / 585 / 580 -> 862 | 51 | 15.6K / 8.7K / 15.7K -> 8.6K |

The staged folders were built with:
`merge-evidence.py --out merged/oNN-3 runs/screen-deep-{p4s3,p4s6,p4s7}/oNN --evidence runs/screen-deep-p4s6/oNN=fixes/readpass/oNN --lead-share-tokens 10000`

## The later GPU step (not run)

Run it in a GPU gap with no timed run live. It takes about 1 h per question, about 3 h for all three: o01's b-w
replays took 34-36 min each on one run's evidence, and these prompts hit the same caps. Wrap it like
run-replays-bundle.sh (`r()` into replays.log, kcheck after). fix-replay takes run/bench.lock itself.

```
WS=/home/USER/ai/deep-research
for q in o01 o02 o03; do
  $WS/.venv/bin/python -I $WS/tools/fix-replay.py write --fix all,read,claims --setup --critic --budget-left 3045 \
    --label i8-merge3-$q --run $WS/staging/item8/merged/$q-3 8>&- 9>&-
done
```

- `--budget-left 3045` is a long run's report time (2565 s reserve + 480 s wrap-up), the same as the b-w replays.
  The verpin replay used 3600.
- Output goes to `results/bench2/fixes/replays/i8-merge3-oNN/report.md`. Grade it blind against the fresh baseline's
  reports, in one grading round. For an early look, the b-w-bundle-oNN replays (same report stage, one run's
  evidence) can stand in.
- The report stage that runs is whatever is installed at the time. Today's after-stage3 chain installs the verpin
  report.py, so compare against reports written by the same report.py.

## Open points

1. **Which runs.** p4s3 / p4s6 / p4s7 are the only labels with all of o01-o03. The alternatives are p4s4/p4s5 in
   place of p4s3, or 2-way p4s6 + p4s7. The runs come from different phase-4 stages, so this test measures the merge,
   not a build.
2. **Read-pass parity.** p4s7 read its cited pages live, and p4s6 uses the 10-28 read pass, but p4s3 has no read
   pass. Under `--fix read`, p4s3's cited-but-unread pages give no evidence. Fix: run
   `tools/read-pass.py runs/screen-deep-p4s3/oNN --out staging/item8/readpass-p4s3/oNN --max-minutes 30` (network
   only, no model), then rebuild with a second `--evidence`. Not done here because the network was off limits.
3. **Lead answers.** The outline reads at most 10,000 tokens of the lead answer (report.py). With whole answers it
   would see only run 1's. The staged folders share the 10K, which keeps 17-50 % of each answer. Single-run reports
   are cut too (p4s7 o01: 11.9K -> 10K). The sources cited only in a cut tail drop out of the "cited" set, which
   matters little under `--fix read`. Karl's call: share or whole.
4. **Fixed report budgets.** The merged stores have 1.5-1.8x the read pages of the best single run. The report
   writer's caps do not grow with them:
   - The outline digest (~45K tokens) gives each source fewer tokens and cuts the list where its budget ends. The
     list is in index order, so the round-robin indices make that cut hit every run alike.
   - Section prompts keep about 30 of the 40-51 subagent reports (12K tokens, at least 400 each). The interleaved
     order spreads that cut across runs.

   Whether these caps eat the merge's gain is part of what the GPU test shows. Raising them would be a report.py
   change, not made here.
5. **Known limits.** None of these is a correctness problem; each is either the report writer's own behaviour or is
   listed in merge-summary.json:
   - No http/https or `www.` unification and no percent-decoding. One o02 index has `$` vs `%24` variants; it is
     mapped by index and listed in the summary warnings.
   - Bracketed number lists that happen to be valid indices (`layer split [13,26]` in a note) are renumbered, exactly
     as `cited_indices` treats them.
   - References inside code (14-40 per merge) are left alone.
   - Claim records in the merged file are informational only: `seed.load` ignores them, and with `--fix claims`
     `fill_store` rebuilds every source's claims from all extractions (o01-3: 14,456).
6. **Not in this folder.** The research-only mode for the short runs and Fix 6's N-window budget (item 8's other
   code) come after this test, if it looks good.
