# Frontier vs local models on the hard set (written 11-01)

**The models:**
- Claude, through the API (10-29/30): Opus 4.5, Opus 4.6 and Sonnet 4.6, 3 runs per item.
- Local, on this PC (10-26): Qwen3.8-Flash-Next at effort medium and xhigh, and DeepSeek V4.1 Flash at effort 50 and
  75, 1 run per item.

**The set:** the same 29 items in 7 categories, with the same prompts and graders and the same room (30,000 tokens).
Research replays the web as saved on 10-12, so no answer saw the live web.

## Bottom line

- **No model is clearly ahead overall.** The intervals overlap. Qwen medium (87.7 %) is level with the three Claude
  models (81.5-84.3 %).
- **Honesty is the real split:**
  - all three Claude models: 24 of 24 (100 %);
  - Qwen medium: 7 of 8;
  - DeepSeek: 2-3 of 8;
  - Qwen xhigh: 1 of 8.
- **Coding:** the local models score 87-100 %, the Claude models 74-99 %. Sonnet 4.6 and Opus 4.6 lost answers to the
  30,000-token room (13 and 9 answers cut off in coding and math), so part of that gap is the room, not the model.
- **Math:** five items. Every Claude model scored 60 %, the local models 60-80 %.
- **Research rests on one question now (r02), so it is a weak signal either way.** Karl's r02 ratings are provisional
  until he re-rates against the new rubric (below).

## Scores

This is the suite's script score. The overall is the mean of the 7 category scores; the interval is the suite's
bootstrap/Wilson. Research in this table is the answer key's script check, not Karl's rating.

| Model | Runs | Overall (interval) | First run only | Coding | Agentic | Math | Instruct | Tools | Honesty | Research (key) | API cost | Cut off |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Opus 4.5 | 3 | 84.3 (77-91) | 83.3 | 99 | 100 | 60 | 100 | 100 | 100 | 31 | $8.72 | 0 |
| Opus 4.6 | 3 | 82.5 (74-90) | 84.1 | 87 | 100 | 60 | 100 | 100 | 100 | 31 | $7.39 | 9 |
| Sonnet 4.6 | 3 | 81.5 (70-92) | 86.3 | 74 | 100 | 60 | 83 | 100 | 100 | 53 | $6.56 | 13 |
| Qwen medium | 1 | **87.7** (76-99) | 87.7 | 96 | 100 | 80 | 100 | 100 | 88 | 50 | - | 0 |
| Qwen xhigh | 1 | 76.8 (65-88) | 76.8 | 95 | 100 | 80 | 50 | 100 | 12 | 100 | - | 0 |
| DeepSeek e50 | 1 | 78.2 (66-91) | 78.2 | 100 | 100 | 60 | 100 | 100 | 38 | 50 | - | 0 |
| DeepSeek e75 | 1 | 73.9 (65-82) | 73.9 | 87 | 100 | 80 | 100 | 100 | 25 | 25 | - | 2 |

- **First run only** compares like with like: each Claude model's run 1 against the local models' single run.
- **Small categories:** agentic has 1 item, instruct 2, tools 2 and research 2, so a single answer moves those
  columns a lot.
- **Cost:** the Claude runs cost $22.67 in all, paid from expiring promotional credits. The local runs had no API
  cost. Wall times aren't comparable between the API and this PC.

## Research

There are two questions:
- **r02:** the best model for this PC;
- **r05:** the current price range of an RTX 5090.

Each answer gets the answer key's script check and Karl's blind 1-5 rating (given 11-01, imported from the blind pages).

| Model | r02 key (per run) | r02: Karl's rating (per run) | r05 key | r05: Karl's rating, on record only | Karl's mean (r02 only) |
|---|---|---|---|---|---|
| Opus 4.5 | 0 / 0 / 0.33 | 2 / 2 / 3 | 0.5 / 0.5 / 0.5 | 5 / 5 / 5 | 2.33 |
| Opus 4.6 | 0.33 / 0 / 0 | 2 / 2 / 2 | 0.5 / 0.5 / 0.5 | 5 / 5 / 5 | 2.00 |
| Sonnet 4.6 | 0.33 / 0.33 / 0 | 4 / 2 / 2 | 1 / 0.5 / 1 | 4 / 5 / 5 | 2.67 |
| Qwen medium | 0 | 2 | 1 | 5 | 2.00 |
| Qwen xhigh | 1 | 5 | 1 | 5 | **5.00** |
| DeepSeek e50 | 0 | 2 | 1 | 5 | 2.00 |
| DeepSeek e75 | 0 (cut off) | 2 | 0.5 | 5 | 2.00 |

**r05 is out of Karl's mean** (Karl, 11-01). It is saturated: 12 of the 13 answers got a 5, so it can't separate
the models. The ratings stay on file. The answer key's r05 check still separates them a little: most misses are a low
end outside the key's $3,500-7,000 range. So r05 stays in the script score above.

**r02 is provisional.**
- Karl gave his first ratings before a rubric existed. He approved one on 11-01 (suite/items/research/r02-rubric.md):
  - a 5 only for Qwen3.8-Flash-Next at a size that fits;
  - Qwen3.8-27B is a reasonable answer, at most 4;
  - earlier-generation models that fit are "dated but workable".
- At the Qwen4 round he re-rates all r02 answers, old and new, on one shuffled page with the labels hidden. His first
  ratings stay on file beside the new ones.
- The key's own r02 check is stricter than the rubric: it counts only Flash-Next as the top pick.

**In plain terms:** the research part of this comparison now rests on one question (r02, 13 answers), so it is a weak
signal either way. Qwen xhigh's 5 is a single answer.

**DeepSeek e75's r02 answer** was stopped early by the server (4,500 of 30,000 tokens). It names a pick but has no
structured part, so the key scores it 0.

## Caveats

- **Runs:** 1 run against 3. The local single runs are noisier (wider intervals); the first-run column is the fair
  comparison.
- **The room:** everyone had the same 30,000 tokens. Sonnet 4.6 and Opus 4.6 ran out on hard coding and math items,
  which counts against them here. At their own maximum room they would likely lose fewer answers, at up to about twice
  the cost (OPUS45-PLAN-1027.md).
- **Honesty:** 8 items. The local runs have one sample each, the Claude models three.
- **r05's replacement** for the Qwen4 round is set (results/BACKLOG-1027.md, section E, step 6): an RTX 5090 new vs.
  used price question with script checks of every quoted price against the saved pages.

**Sources:**
- per model: suite/results/<label>/scores.md, scores.json, grades.json and ratings.json;
- suite/items/research/ratings-config.json, which takes r05 out of the mean;
- suite/items/research/r02-rubric.md.
