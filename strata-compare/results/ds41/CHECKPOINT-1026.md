# DeepSeek-V4.1-Flash checkpoint - end of the 10-24 to 10-26 round

Read this before the next DeepSeek round. Full detail: results/ds41/round-report-1026.md and NOTES.md (10-24 to 10-26).
Status: final 10-27 (Karl's decisions in, below).

## Karl's decisions (10-27 morning)

- Qwen stays the main model on 8080. DeepSeek stays installed as an option (`./switch-model.sh deepseek`) with effort
  50 as its default.
- No more DeepSeek work this round; the long-context items are not rerun.
- Swap rule settled (below, "Swap rule"); LDR next.

## What ships (daily, `./switch-model.sh deepseek`, configs/DS41-daily.json, port 8086)

- Engine `engine-v026p343-slotram-ds41` (since 10-27 02:13): Strata v0.2.6 + our #343 port (prompt skip across the
  layer split) + a local slot RAM cap (STRATA_DS4_SLOT_RAM_GB; unset = stock; same answers as `engine-v026p343-ds41`
  with placement frozen). IQ_Q8K and BORROW are not in it.
- 4060 Ti first, layers 8 / 32; 6 experts per word (5 is lossy); decay 0.8, settle 0, Engram cache 16 MB; chunk 8192;
  STRATA_DS4_PROMPT_SKIP=1; **context 128K** (10-27; was 32K, backup DS41-daily.json.before-128k); sampling
  1.0 / 0.95 / 20 / 0.05.
- Slot keep on: up to 16 conversations in RAM and at most 1.7 GiB of them (a 128K conversation is ~0.13 GiB; 16 of
  them would leave 13.99 GB), the folder 2 GiB; RAM store 68 GB (lowest MemAvailable 15.5 GB with everything up and
  16 daily-length slots; 18.9 GB during a 97K-token prompt).
- Its own expert profile `logs/ds41/daily-profile.bin`, learning (the engine rewrites it at exit). Seeded once from
  `configs/DS41-daily-profile.seed.bin` (sha 8db93e48...9568, what the final config was measured with). Measurements
  always use their own pinned copies, never the daily file.
- Speed (A/B/A, final config): decode ~28.3 tok/s, P4K ~350, P20K ~700 tok/s; a 97K-token prompt reads at 947 tok/s
  (102 s) and decodes at 21.0 tok/s.
- Gate: final config vs stock v0.2.6 PASS (changed top-1 picks 32, bound 33.0; text NLL +0.0013, bound 0.0111). Daily
  end tests (conversation cache, follow-up re-reads with slot keep on, cap 16) PASS; released 10-26 16:44.
- Effort default **50** (10-27, Karl): `"reasoning_effort": "low"` in DS41-daily.json and DS41-daily.shared-settings.json
  (backups .before-e50). The server renders DeepSeek with its own V4.1 template (strata-v026/serve/fixtures/deepseek41),
  where low = 50, medium = 62, high = 75, max = 100, and the shared settings take only none / low / medium / high;
  "low" and the hard set's 50 render byte-identical prompts. Until 10-27 the "medium" placeholder meant 62. A request's
  own effort still wins (Jan or the LDR proxy sending "medium" gets 62).

## Gate rule (final, 10-26 16:55; skipcheck.rounding_checks, used by every gate)

A candidate is rounding-level when, against two rounding references (R1 = chunk 4096, R2 = CPU share / reserve):
KL mean and p90 <= 1.10 x the larger reference's; KL > 1 count <= the worse reference's + 1; changed top-1 picks vs the
base <= 1.10 x the larger reference's; text NLL over the base <= 1.10 x the larger reference's distance from the base.
Why the margins: rounding-level variants range 2,005-2,015 of 2,040 top-1 picks, so fixed margins of 1 were coin flips.

## Next DeepSeek round - main item: BORROW (port into Strata)

- What: Maya's in-place expert layout marker (every GGUF in-place layout uses it). Gain: more experts in VRAM on both
  cards and fewer bytes over the 4060 Ti's PCIe x4 link, which now sets the prompt pace (per 20K prompt it streams 76 GB,
  40 GB of it from the drive at ~1 GB/s, and waits 9.4 s of 38 s). Maya's measured lead (P20K +15 % in M1) came without
  BORROW, so its gain on top is the round's open question.
- Cost: re-laying out the expert slots, the tail region and the cache, ~1.5-2 days of code.
- **Upstream watch:** Strata upstream may port it first (Niko has been pulling Maya changes within days). The Saturday
  release check looks for it in the release notes and the diff (expert layout / slot / tail changes, "borrow"). If it
  lands upstream: A/B that release against ours instead of porting (v0.2.6 + #343 still needs carrying over).
- Then: the usual gate (above), 3-pass A/B/A vs the ship config, keep only on a real gain.

## Maya: fallback only

- Failed on this PC under the swap rule (10-26 h2h): the kernel swapped the engine's own memory while Maya read experts
  through the page cache, with ~34 GB still free (M1: 229 -> 1,089 MB in ~4 s; M2: 544 MB). Likely cause: swappiness 60
  (vfs_cache_pressure 100, min_free_kbytes 67584; read only, not changed - no system changes on our own).
- Karl may lower swappiness later and retry the 10-minute check (mainly if the BORROW port turns out too hard).
- What Maya showed before it failed: P4K 399 / 481, P20K 693 / 900 (M1 / M2) vs Strata + #343 333 / 601.

## IQ_Q8K: dropped (findings to keep)

- Where it acts in Strata: only on the async expert path (T <= DS4_ASYNC_T = 8: decode and windows of up to 8). Windows of
  9-16 take the synchronous mv path and windows >= 96 the prompt path (F32 / F16) - a 16- or 128-token window gate never
  reaches it. Any future test of decode-side rounding must use 8-token windows (ports.py iq_w8).
- Gate PASS at 8-token windows; placement steps moved 2-15 % less KL (not the halving asked); the decode check showed no
  gain in matching tokens (3 / 24 / 29 with vs 29 / 24 / 29 without). Dropped by Karl's rule.
- Reading: GPU/CPU activation rounding is a small part of why placement changes answers; the prompt path, summation order
  and batching matter as much. Maya's FP8 gain (KL 0.162 vs 0.171) is quality-vs-reference, not consistency.
- The port (apply_variant.py "iqq8k", DS4_IQ_Q8K=0 byte-identical to stock) stays on disk if a reference path ever
  makes the quality-vs-reference question testable here (the original FP8 / FP4 weights do not fit the disk).

## Maya's prompt-compute ideas, re-ranked (the 4060 Ti is the pace)

1. Fewer layers on the 4060 Ti - DONE (8/32, P20K +16 %).
2. Earlier / larger read share for the 4060 Ti's pipeline (Strata side): +10-15 % if its 9.4 s of waits per 20K halve.
3. Tensor-core prompt attention (ATTN_MMA): +5-8 %.
4. Leaner expert tiles + FP16 rows + router rows: +3-6 %, exact.
5. Wider attention slabs: ~0 on an 8 GB card. 6. FAT_ROWS: <= 1 %.
(#360 is already in v0.2.6.) BORROW comes first; these after it.

## Open questions

- Repeatability: open - see "Open: the repeat-pair test" below.
- Resuming is exact (4-piece resume = 4 pieces without resume, byte for byte; 1-piece resume = fresh); the 4-piece split
  itself is rounding-level.
- Context: 128K reserved costs 22 of 1,330 VRAM expert slots; daily since 10-27 (round report section 10).
- Long prompts and swap: ~95K-token prompts stream the CPU-lane experts (121 GB in place) through the page cache, and
  the kernel pushes other programs' idle pages to swap (34 MB over two documents, engine swap 0, 23 GB free). The v3
  swap rule stopped the long-context items there (1 of 6 answered); under the 10-27 rule that run passes (replayed), but
  Karl chose not to rerun them this round. A DeepSeek long-context comparison is still missing.
- Honesty: DeepSeek invents answers to made-up questions (graded set 4 of 10; hard set 5 of 8 at e50 and at e25) -
  less effort does not help. Qwen medium: 0 of 10 and 1 of 8.
- Upstream issue for the follow-up re-read (pr-drafts/47): built and tested, 12 / 12 with slot keep off. Never post.

## Hard set (10-26 night): DeepSeek at its best vs Qwen at its best

29 hard items (8 honesty items plus every graded label: math, coding with hidden tests, tool use, multi-step, two of them
research questions), one run each, the
same room for every answer: max_tokens 30,000, no separate thinking cap. Qwen P021m on 8085, DeepSeek on the final daily
config. Grades: the suite's checkers; research also blind. Tables: results/ds41/hard/REPORT.md; round report section 9.

| setting | score (of 100) | s per answer | mean thinking tokens | thinking at the room limit | cut off |
|---|---|---|---|---|---|
| Qwen medium | **88.5** | 23.2 | 3,348 | 2 | 0 |
| Qwen xhigh | 67.4 | 87.7 | 11,854 | 10 | 0 |
| DeepSeek effort 50 | **72.4** | 202.4 | 5,512 | 2 | 0 |
| DeepSeek effort 75 | 66.7 | 251.1 | 6,980 | 3 | 2 |

- **DeepSeek's better setting (e50) minus Qwen's better setting (medium): -16.1 points per item (95 % -31.0 to -3.4).**
  DeepSeek better on 1 item (c16), worse on 5 (four honesty items, m09), equal on 23. Without the honesty items the two
  are level (-3.2 points per item on the other 21).
- Honesty: Qwen medium 87.5, xhigh 12.5; DeepSeek e50 37.5, e75 25.0, e25 37.5 - less effort does not help DeepSeek
  (at e25 it still thinks ~4,700 tokens before inventing an answer).
- Blind research (/10): Qwen medium 7.25, xhigh 7.0, DeepSeek e50 6.5, e75 4.5 (results/ds41/hard/blind/grades.jsonl).
- e75's two cut-offs: one "0000..." loop ended by the server's repeat guard; one filled the old 32K context during
  research (128K now prevents that). m03 scored 0 under all four settings (too hard for the room).
- Result: Qwen stays the main model; DeepSeek's default effort is 50 (Karl, 10-27).
- DSpark: never loads with `auto` here (the routed experts far exceed VRAM), so the planned A/B/A did not run.

## Open: the repeat-pair test (next DeepSeek round)

What is known (results/ds41/hard/pairs2.md, round report section 6):
- Fixed-seed request pairs in one engine are not identical. Ruled out: the reuse path (REUSE=0 pairs still differ),
  DSpark (`--dspark none` pairs still differ), the Engram row cache and the prompt-path pick (read in the code). The
  sampler counter (never reset per request, ds4_main.cpp:327) is part of it; v026test resets it (DS4_TEST_SEED_RESET=1).
- With the expert cache on, not even a fresh engine's first request repeats: identity checks must freeze placement
  (`--no-expert-cache`).
- Carry-over (the same 2,047-token segment scored twice in one engine, engine v026test, shipped profile, placement
  frozen): window 1 (the decode path) is identical; window 128 (the prompt path) is not - KL mean 0.0022, 15 top-1
  changes, mostly in the first 16 positions (0.10), 0.0008 past position 512.

The next test (one GPU gap, ~15 min; pairs2.py `carryover_frozen` is the template):
1. The same check at window 128 with the RAM store off: mkcfg from `A.final()` + engine v026test + `--no-expert-cache`
   + `--ssd-cache 0`, `scorearm.sh` with SCORE_WINDOW=128 on carryover.ids.json, judged with pairs2.py `copies()`.
2. Identical -> the RAM store's contents (they keep filling between requests even with VRAM placement frozen) change the
   prompt path; look at how a stored expert's compute path differs from an in-place read.
3. Still different -> the prompt pass's learned timing (pm, which shifts the CPU / GPU split between requests); first
   find in the code whether it can be pinned, then repeat with it pinned.
4. If both are found: a fixed-seed repeat pair (cont_client.py exact, REUSE=0, counter reset, frozen) should then come
   out identical - that is the pass mark.

## Swap rule (10-27, Karl; tunearm.sh and maya-tunearm.sh)

A run fails if any engine memory gets swapped (VmSwap > 0), or if swap-ins / swap-outs keep happening: 5 samples in a
row (~11 s) adding up to >= 4 MB (swap-ins: while swap use is not falling; swap-outs: after the run's first episode). The
first swap-out episode - a one-off push-out of other programs' idle pages - is logged only (swap.tsv, summary line).
Replayed on the round's 108 runs: A1, x5-A, x5-B and lc-e50 now pass; the Maya runs and S1 still fail. NOTES.md 10-27.

## Driver lessons from the last night

- after.py arm() fills lowest_mem from the monitor line when arm.json lacks it (monitor_lowest).
- A driver that resumes another driver's state must load it only after that driver has ended (ctx128b loaded early and
  dropped three keys; restored from the log).
- A driver that copies a check from another driver's state must copy the state it reads (the hard-set driver looked for
  the build record in its own state and skipped the repeat pairs as "build failed").

## Then: LDR (with 8080 up) - started 10-27

Karl's go (10-27): build the read-only code tool now (code only, 8080 up; GPU only for the test run); a blind grader may
read Karl's 10-24 DeepSeek-tuning LDR report, for this test only. Otherwise don't read the user's own LDR research or
chats (titles and dates only); benchmark runs (results/bench2) are ours. LDR files: ~/ai/deep-research/results/bench2/
CHECKPOINT-phase3.md, PLAN.md, NOTES.md.
