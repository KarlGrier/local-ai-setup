# C7: LDR context overflow - desk analysis (2026-11-09, after Phase 5)

Backlog item C7 (results/BACKLOG-1027.md, Karl 11-07): "(1) how often across all stored runs, per profile (baseline /
deep) and phase, and what each overflow did to the answer; (2) options with costs." Desk only: no run, no change. The
detector is staging/phase5/overflow.py (research-logs.json: refused requests and the raw-answer fallback). The source is
every stored bench run under results/bench2/runs/; Jan jobs, deep-runs and quick-runs were not read.

## 1. Frequency

| | runs | with an overflow |
|---|---:|---:|
| **deep profile** (every phase 4 / 7 / 8 arm, Phase 5 final) | 156 | **0** |
| **baseline = stock LDR** | 63 | **7** |
| - of them checkable questions | 54 | 0 |
| - of them open questions | 9 | **7** |

By phase:
- screen-baseline (10-18): o01, o02;
- screen-extra-baseline (10-19): o07, o08;
- Phase 5 holdout baseline: o04, o06;
- Phase 5 o01 line, baseline: o01.

So it is a property of stock LDR on open questions: 7 of its 9 open-question runs, and in every phase. Stock LDR's
LangGraph agent ran 97 to 357 model calls on those. The deep profile never got there: it has its own page and claim
caps, the setup profile and the critic.

## 2. What each overflow did to the answer

| run | refused prompts (tokens) | what reached the report |
|---|---|---|
| screen-baseline o01 | 133,116 (agent turn); 529,311 (citation synthesis) | snippet fallback (prompt 1.8K -> 13.8 KB answer) |
| screen-baseline o02 | 140,408; 409,146 | snippet fallback (1.7K -> 10.8 KB) |
| screen-extra-baseline o07 | 582,563 (synthesis) | the agent's full answer (85K + 17K tokens, finish stop), uncited |
| screen-extra-baseline o08 | 142,711; 141,902 | snippet fallback (1.7K -> 14.4 KB) |
| holdout-baseline-p5 o04 | 315,329 (synthesis) | **cut-off** agent answer (finish length at 125,482 + 5,582) |
| holdout-baseline-p5 o06 | 131,155; 218,650 | snippet fallback (1.6K -> 8.5 KB) |
| p5-o01-baseline-p5 o01 | 387,543 (synthesis) | the agent's full answer (99K + 14K tokens, finish stop), uncited |

That is 4 snippet fallbacks, 1 cut-off and 2 complete but uncited agent answers. Two kinds of refusal cause them:
- **The agent's own next turn** goes just over the window (131-143K): its fetched pages are lost, and LDR answers
  from search snippets.
- **The citation synthesis** puts every fetched source into one prompt (219K-583K): it is always refused, and LDR
  keeps the agent's raw answer.

All 7 counted complete in stock LDR (Phase 5 counts them as they are, flagged: results/bench2/p5-run-flags.json; the
o01 entry was added 11-09 after the same hand check).

## 3. Options and costs

| option | fixes | cost | risk |
|---|---|---|---|
| **A. Leave it (recommended for now)** | nothing in stock LDR | none | none. Your paths: deep jobs 0 of 156; quick jobs run stock LDR with LDR_QUICK_LIMITS (no subtopic agents, at most 12 agent cycles, 15 min cap), far from the 97-357 calls above. The baseline must stay pristine to stay a reference |
| B. Agent budget below 131K (drop or shorten the oldest tool results once the prompt passes ~110K) | the agent-turn refusals (4 runs) | ~1 desk day (LDR patch in the agent loop) + a baseline-with-patch screen of the 9 open questions (~10-15 GPU h) | the agent loses early pages; not the synthesis refusals |
| C. Compact history (the model summarizes old tool results) | the agent-turn refusals | ~2 desk days + the same screen; more calls per run (slower) | summaries drop facts; quality must be graded |
| D. Harder cap on fetched pages (tokens per page, and in total in the synthesis) | both kinds, if the synthesis prompt is capped too | ~0.5 desk day + the same screen | less source text per claim. It is the only option that touches the synthesis refusal (219K-583K) |
| E. A 256K Qwen config | the agent-turn refusals only: 5 of the 7 synthesis prompts are above 256K anyway | KV: 12 QSA layers x 2 KV heads x 256 x (K+V) at int8 = ~12 KiB a cell -> ~+1.5 GiB of RAM for the extra 128K cells, with RAM already tight (MemAvailable ~23 GB beside a serving 8080); full-window prompts take ~2x the time (~28 -> ~56 s cold at ~4,600 tok/s); the indexer's scoring grows with the cells; whether the model is trained past 131K must be checked first; a gap to measure all of it | moves the wall, does not remove it |

**Recommendation: A.** Jan's deep jobs run the deep profile, which never overflowed in 156 stored runs. Its quick jobs
use stock LDR with the quick limits; the bench has no stored run of that exact setup, so they are untested here, but
capped well below the call counts that overflowed. If Karl wants stock LDR's
open-question runs fixed anyway (e.g. to compare against a stronger baseline), D plus B is the cheapest pair: one
patch and one screen. E is not worth its RAM for this, because the synthesis prompts would still be refused.
