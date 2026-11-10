# Frontier vs local models on the hard set (version 11-05)

This is the 11-05 update of results/FRONTIER-HARDSET-1101.md, which is kept unchanged. It was written 11-05 by a
write-up helper as desk work: no suite item, API call or model was run for it. Every number gives its source in
brackets. "scores.md" means suite/results/<label>/scores.md.

**r02 is PROVISIONAL everywhere in this file**, in every table and in the text. Karl's note in the approved rubric
(suite/items/research/r02-rubric.md, 11-01) says:
- Karl gave his first r02 ratings before a rubric existed.
- At the Qwen4 round he re-rates ALL r02 answers, old and new, on one shuffled page with the labels hidden.
- "Until then r02 ratings are provisional."
- Karl, 11-01: "a flawless Qwen3.8-27B answer tops out at 4; a 5 is only for Flash-Next at a size that fits."

r02's answer-key check is stricter than the rubric (it counts only Flash-Next as the top pick), so the r02 key
numbers are marked provisional too.

## What changed since 11-01

1. **Nothing new ran, and no number changed.** No suite file has changed since 11-01 12:24 (the scores), 12:25 (the
   ratings config) and 12:43 (the rubric) [file times in suite/results/ and suite/items/research/, checked 11-05]. The
   strata-compare NOTES have no suite line between 11-01 12:45 and Karl's 11-05 write-up request [NOTES 11-01 12:45,
   11-05 12:0x].
2. **The Opus 4.5 hard-set run "gated on the API-credit reset" already ran on 10-29.** It is not pending.
   - The 10-27 plan gated it: it would start only after Karl confirmed the credit reset (flag tmp/suite/opus45-credits-ok),
     on a daily timer from 11-02 to 11-24 with a $25 stop [NOTES 10-27 ~14:40].
   - Karl 10-29: he confirmed the credits. The flag file reads "Karl 2026-10-29: API credits confirmed ($130.15
     available). Run the Opus 4.5 hard set as scheduled (11-02)."
   - The same morning he moved the run forward: $30.14 of promotional credits were expiring 11-01 UTC (plus a new $100
     until 12-02), so "run the hard set NOW on them" [results/OPUS45-PLAN-1027.md, "10-29: run moved forward"].
   - work/suite/frontier-now.sh then ran all three Claude models: "done: Opus 4.5 $8.72, Sonnet 4.6 $6.56, Opus 4.6
     $7.39 = $22.67" [logs/suite/frontier-now.log, 10-29 23:42:40].
   - The daily timer (suite-opus45-hard.timer, 09:00) fired on 11-02, 11-03, 11-04 and 11-05. Each time it logged
     "opus-4-5-hard-r3 is complete already" and exited without an API call [logs/suite/opus45-hard.log].
   - It is still enabled (next run 11-06 09:00) and stays a no-op until 11-24 [systemctl --user list-timers, 11-05].
3. **A correction to the 11-01 text.** DeepSeek e75's r02 answer was **not** "stopped early by the server (4,500 of
   30,000 tokens)". That describes its c02_rle coding answer, which looped and was ended by the server's one-token
   repeat guard at 4,500 tokens. The r02 answer is an "agentic step cut off": after 10 tool calls its prompt filled
   DeepSeek's 32K context (31,252 prompt tokens, 256 left to answer). It has 11,550 output tokens and no JSON answer
   block, so the key scores it 0 [h1026-ds-e75 scores.md: the cut-off line and the r02 / c02 rows; NOTES 10-27
   01:33-01:45].
4. **Context the 11-01 version left out:**
   - **The local Qwen runs used config P021m** (10-26, test port 8085) [h1026-qwen-* meta.json, backend.server.config_file].
     8080 has served P028x (the v0.2.8 port) since 10-30 16:55. The hard set was not rerun on P028x [deep-research
     NOTES 10-30 16:55].
   - **DeepSeek ran at a 32K context** (config DS41-tune-after-h-ds-e50.json) [h1026-ds-* meta.json]. The daily
     DeepSeek launcher has used 128K since 10-27. "128K would have avoided" e75's r02 cut-off [NOTES 10-27 01:33-01:45].
   - **Claude settings:** a room of max_tokens 30,000 for every model and effort high. Opus 4.5 used thinking
     "enabled"; Sonnet 4.6 and Opus 4.6 used "adaptive" [the three Claude scores.md headers].

## Bottom line (unchanged from 11-01)

- **No model is clearly ahead overall.** The intervals overlap. Qwen medium's 87.7 % [76.4-98.9] is level with the
  three Claude models' 81.5-84.3 % [h1026-qwen-medium scores.md; Claude scores.md].
- **Honesty is the real split** (unknowable items answered honestly) [scores.md, Honesty row]:
  - Opus 4.5, Opus 4.6 and Sonnet 4.6: 24 of 24 each (3 runs x 8 items);
  - Qwen medium: 7 of 8;
  - DeepSeek: e50 3 of 8, e75 2 of 8;
  - Qwen xhigh: 1 of 8.
- **Coding:** the local models score 87-100 % and the Claude models 74-99 %. Sonnet 4.6 and Opus 4.6 lost 13 and 9
  answers to the 30,000-token room (coding 7 + math 6, and coding 3 + math 6), so part of that gap is the room, not
  the model [scores.md, Coding / Math "cut off" columns].
- **Math:** five items. Every Claude model scored 60 %, the local models 60-80 % [scores.md, Math row].
- **Research rests on one question, r02 (PROVISIONAL), so it is a weak signal either way.** r05 is out of Karl's mean
  because it is saturated [suite/items/research/ratings-config.json].

## Scores

This is the suite's script score. The overall is the mean of the 7 category scores; the interval is the suite's
bootstrap / Wilson 95 %. Research here is the answer key's script check over r02 + r05, not Karl's rating.

| Model | Runs | Overall (95 % interval) | First run only | Coding | Agentic | Math | Instruct | Tools | Honesty | Research (key: r02 PROVISIONAL + r05) | API cost | Cut off |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Opus 4.5 | 3 | 84.3 (76.7-90.9) | 83.3 | 99.5 | 100 | 60 | 100 | 100 | 100 | 30.6 | $8.72 | 0 |
| Opus 4.6 | 3 | 82.5 (74.3-90.0) | 84.1 | 87.0 | 100 | 60 | 100 | 100 | 100 | 30.6 | $7.39 | 9 |
| Sonnet 4.6 | 3 | 81.5 (69.9-92.1) | 86.3 | 74.1 | 100 | 60 | 83.3 | 100 | 100 | 52.8 | $6.56 | 13 |
| Qwen medium | 1 | **87.7** (76.4-98.9) | 87.7 | 96.3 | 100 | 80 | 100 | 100 | 87.5 | 50 | - | 0 |
| Qwen xhigh | 1 | 76.8 (65.2-87.5) | 76.8 | 94.9 | 100 | 80 | 50 | 100 | 12.5 | 100 | - | 0 |
| DeepSeek e50 | 1 | 78.2 (66.4-90.7) | 78.2 | 100 | 100 | 60 | 100 | 100 | 37.5 | 50 | - | 0 |
| DeepSeek e75 | 1 | 73.9 (65.0-82.3) | 73.9 | 87.3 | 100 | 80 | 100 | 100 | 25 | 25 | - | 2 |

**Sources:**
- Every column except "First run only" comes from each label's scores.md (the Total line, the category table and the
  header's "API cost (reported usage)" and "cut off").
- The labels are opus-4-5-hard-r3, opus-4-6-hard-r3, sonnet-4-6-hard-r3, h1026-qwen-medium, h1026-qwen-xhigh,
  h1026-ds-e50 and h1026-ds-e75.
- "First run only" averages run 0's item scores per category, then the 7 categories. I recomputed it on 11-05 from the
  scores.md item tables and it matches the 11-01 values.

**Notes:**
- **First run only** compares like with like: each Claude model's run 1 against the local models' single run.
- **Small categories:** agentic has 1 item, instruct 2, tools 2 and research 2, so a single answer moves those
  columns a lot.
- **Cost:** the Claude runs cost $22.67 in all, from the promotional credits that expired 11-01 UTC
  [logs/suite/frontier-now.log; OPUS45-PLAN-1027.md]. The local runs had no API cost. Wall times are not comparable
  between the API and this PC.
- **Dates:** the Claude models ran 10-29 (Opus 4.5 09:56-23:29, Sonnet 4.6 10:55-23:38, Opus 4.6 11:39-23:42 CDT).
  The local models ran 10-26 to 10-27 [scores.md "Started / finished" lines].

## Research (r02 PROVISIONAL)

There are two questions:
- **r02:** the best model for this PC. **PROVISIONAL**: see the top of this file.
- **r05:** the current price range of an RTX 5090. It is out of Karl's mean but stays in the script score.

Each answer gets the answer key's script check and Karl's blind 1-5 rating. The ratings were given 11-01 on the
To-rate pages and imported 11-01 12:16.

| Model | r02 key per run (PROVISIONAL) | r02: Karl's rating per run (PROVISIONAL) | r05 key per run | r05: Karl's rating, on record only | Karl's mean (r02 only, PROVISIONAL) |
|---|---|---|---|---|---|
| Opus 4.5 | 0 / 0 / 0.33 | 2 / 2 / 3 | 0.5 / 0.5 / 0.5 | 5 / 5 / 5 | 2.33 |
| Opus 4.6 | 0.33 / 0 / 0 | 2 / 2 / 2 | 0.5 / 0.5 / 0.5 | 5 / 5 / 5 | 2.00 |
| Sonnet 4.6 | 0.33 / 0.33 / 0 | 4 / 2 / 2 | 1 / 0.5 / 1 | 4 / 5 / 5 | 2.67 |
| Qwen medium | 0 | 2 | 1 | 5 | 2.00 |
| Qwen xhigh | 1 | 5 | 1 | 5 | **5.00** |
| DeepSeek e50 | 0 | 2 | 1 | 5 | 2.00 |
| DeepSeek e75 | 0 (cut off: context full) | 2 | 0.5 | 5 | 2.00 |

**Sources:**
- Key scores and ratings: each label's scores.md, section "Research with web search: key checks and your ratings".
  The key is shown there as 0 / 33 / 50 / 100 and here as 0-1.
- The means: the same section's "mean N of 5" line.
- The import: NOTES 11-01 12:16.

**r05 is out of Karl's mean** (Karl, 11-01).
- It is saturated: 12 of the 13 answers got a 5 (Sonnet 4.6's first run, run 0 in scores.md, got a 4), so it cannot separate the models.
- The ratings stay on file [ratings-config.json "exclude_from_comparison"; NOTES 11-01 12:25].
- The answer key's r05 check still separates the models a little, so r05 stays in the script score. Most misses are a
  low end outside the key's range (the "low_end_current" check) [scores.md, r05 rows].

**r02 is PROVISIONAL** [r02-rubric.md; NOTES 11-01 12:25, 12:45; results/BACKLOG-1027.md section E]:
- **The rubric** was approved by Karl 11-01:
  - a 5 only for Qwen3.8-Flash-Next at a quantization that fits;
  - Qwen3.8-27B is "reasonable", at most 4 (Karl's change);
  - GLM-5.3-Flash, MiMo-V2.6-Flash and Signal-3.8-Flash-Next at a fitting size are also reasonable, at most 4;
  - earlier-generation models that fit are "dated but workable".
- **Karl's first ratings came before the rubric existed.** They stay on file beside the new ones when he re-rates.
- **The re-rating page was not built** (Karl, 11-01 12:45). It is parked for the Qwen4 round (BACKLOG-1027.md
  section E step 6): all r02 answers, old and new, on one shuffled page with the labels hidden, imported as a separate
  round.
- **Qwen4 has not landed as of 11-05.** The day-one kit is still being prepared [NOTES 11-04 13:1x, 11-05 12:0x], so
  r02 stays provisional.
- The key's own r02 check is stricter than the rubric: it counts only Flash-Next as the top pick.

**In plain terms:** the research part of this comparison rests on one question (r02, 13 answers), and that question's
ratings are provisional, so it is a weak signal either way. Qwen xhigh's 5 is a single answer.

## Caveats

- **Runs:** 1 run for each local model against 3 for each Claude model. The local single runs are noisier (wider
  intervals); the first-run column is the fair comparison.
- **The room:** everyone had the same 30,000 tokens. Sonnet 4.6 and Opus 4.6 ran out on hard coding and math items,
  which counts against them here. At their own maximum room they would likely lose fewer answers, at up to about twice
  the cost [OPUS45-PLAN-1027.md].
- **Honesty:** 8 items. The local runs have one sample each, the Claude models three.
- **Builds:** the local Qwen numbers are P021m's (10-26), not the served P028x's. DeepSeek's are at a 32K context, not
  the daily 128K (see "What changed", point 4).
- **The web:** research replays the web as saved on 10-12, and every model was told the date was 10-12. No answer saw
  the live web [scores.md, research section header].

## Still open

1. **The r02 re-rating** at the Qwen4 round: one shuffled page, labels hidden, against the rubric. Until then r02 is
   PROVISIONAL [BACKLOG-1027.md section E step 6].
2. **r05's replacement** for the Qwen4 round: an RTX 5090 new vs used price question, with every quoted price checked
   by script against the saved pages. The old r05 stays on file for the earlier labels [BACKLOG-1027.md section E
   step 6].
3. **The no-op timer:** suite-opus45-hard.timer keeps firing daily until 11-24, each time finding the run complete.
   Whether to disable it is Karl's call; nothing is spent while it runs.
4. **The Opus 4.5 thinking budget is not checked.** Its scores.md header lists thinking "budget_tokens 48000" with
   max_tokens 30,000. The 10-27 mock test of the --max-tokens change sent a thinking budget of 28,976 for a 30,000
   room [NOTES 10-27 09:00-09:12]. The header may show the model default rather than what was sent. The batch request
   files would settle it; they were not opened here.
5. **Not part of this comparison:** the Sonnet 5.5 LDR experiment (backlog C4). It is planned after Phase 5 with its
   own budget and stop [NOTES 10-27 ~14:40; deep-research PLAN-ITEMS5-8-1027.md].

## Sources

- suite/results/<label>/scores.md, meta.json and ratings.json for the 7 labels
- suite/items/research/ratings-config.json and r02-rubric.md
- results/FRONTIER-HARDSET-1101.md (the previous version)
- results/OPUS45-PLAN-1027.md ("10-29: run moved forward")
- results/BACKLOG-1027.md section E step 6
- tmp/suite/opus45-credits-ok
- logs/suite/frontier-now.log and logs/suite/opus45-hard.log
- systemctl --user list-timers (11-05)
- NOTES.md: 10-27 09:00-09:12, 10-27 ~14:40, 10-27 01:33-01:45, and 11-01 12:16 through 11-05 12:0x
