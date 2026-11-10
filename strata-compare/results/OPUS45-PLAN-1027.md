# Opus 4.5 suite runs - plan for 11-01 .. 11-24 (for Karl's OK; nothing is sent before it)

Opus 4.5 (claude-opus-4-5-20251101) is guaranteed only until 11-24; no Claude spending before November. The quick set is
saturated (Opus 4.5 quick, 10-12: 90.8, $13.10), so the plan is the **hard set** - the same 29 items Qwen medium / xhigh
and DeepSeek e50 / e75 ran on 10-26.

## Run A (the main run) - hard set, 3 runs per item

- Items: the 29 hard-set items (9 coding with hidden tests, 5 math, 2 tools, 1 agentic, 8 honesty, 2 instruct, 2
  research). Same prompts, same graders; research replays the frozen web snapshot (no live web), graded blind with the
  same method as the local runs.
- Room: the same as the local runs - max_tokens 30,000, with Opus's thinking budget 28,976 (the room less 1,024); effort
  high (Opus 4.5's highest). Temperature: the API default 1.0 (thinking does not allow changing it); top_p / top_k
  cannot be set with thinking on.
- 3 runs per item: one sample is noisy (the DeepSeek honesty API test used 3 too); the run-1 answers compare directly
  with the local single runs, all three give the spread.
- Single-turn items go through the Batch API (half price); agentic and research turns run live with prompt caching.
- Guards: estimate printed first, run only if under $25; hard stop --budget 25 (below the usual $40).

**Cost estimate** (the suite's own estimator, from the local hard-set runs' token counts; Opus $5 / $25 per M tokens):

| token counts taken from | 3 runs | if Opus writes 2x the tokens | 1 run |
|---|---|---|---|
| Qwen medium | $5.56 | $10.28 | $1.85 |
| DeepSeek e50 | $7.80 | $14.80 | $2.60 |
| Qwen xhigh (thinks longest) | $14.70 | $28.71 | $4.90 |

The 10-12 quick run came in at 0.62x its estimate ($13.10 vs ~$21). Expected: **~$5-10 for Run A**, worst case under the
$25 stop. Biggest shares: coding and math (long thinking), research (multi-turn with fetched pages).

## Before the window (code only, no API call)
- Suite change: the Claude backend ignores --max-tokens today (it always uses the model's maximum: 64,000, thinking
  budget 48,000). Pass --max-tokens through for Claude endpoints, so the room matches the local runs; selftest + a dry
  run against the mock backend. ~30 min. (Alternative: run Opus at its own maximum like the 10-12 quick run - then its
  scores are "Opus at its best" rather than "same room"; cost up to ~2x.)
- Label: opus-4-5-hard-r3; command (for the record):
  `suite/run.sh --label opus-4-5-hard-r3 --endpoint claude:claude-opus-4-5-20251101 --mode quick --only <the 7 categories>
  --items <the 29 ids> --runs 3 --max-tokens 30000 --estimate-from h1026-qwen-xhigh --max-estimate 25 --budget 25`

## When and what comes back
- Proposed: the first weekday of the window (Mon 11-02), ~1-2 h wall (batches); no GPU, runs beside anything.
- Report: per item Opus (3 runs) vs Qwen medium / xhigh and DeepSeek e50 / e75 (pass / score, time is not comparable
  across API and local), the totals with intervals, honesty rate over 24 samples (vs DeepSeek API 67 %, local 40 %,
  Qwen medium 87.5 %), blind research grades, actual cost from the API's usage.
- Not planned (no deadline, say if wanted): Sonnet 4.6 / Opus 4.6 on the hard set (similar cost each).

## 10-29: run moved forward (Karl)
Karl 10-29: $30.14 of promotional credits expire 11-01 UTC (plus a new $100 until 12-02) - run the hard set NOW on them,
same settings, hard stop $25, Batch API where easy (the suite already batches every single-turn item). Started 09:56
(unit suite-opus45-now, work/suite/opus45-hard-now.sh; estimate $14.28, 2x $27.94). Then Sonnet 4.6 on the same hard set
(unit suite-sonnet46-now) if Opus <= $20, with effort pinned to high (--claude-effort, new 10-29) and a budget of
min($25, $30.14 - Opus - $1). Both before Sat 10-31 18:00 Chicago. The 11-02 timer will find the Opus run complete.
