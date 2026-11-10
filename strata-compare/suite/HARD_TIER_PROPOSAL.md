# Hard tier: proposal (2026-10-13, not built)

Asked for after the Sonnet 5.5 ceiling check: which categories still separate the models, which are saturated, and a
hard tier for the saturated ones calibrated so the best model lands around 50-70 %. Nothing here is built yet.

**Status (your decision, 2026-10-13):** not built. To be scheduled after the Oct 14 port and the usability round.
Calibration on hosted Flash and your local IQ3_S (C*17.1), aiming for Flash at 50-70 %; no Claude spending until next
month (November). Section 2 has how long building and calibrating would take.

## 1. Which categories still separate the models

Labels: c171-iq3s-full, c171-iq3s-quick, r16-q4-quick, or-qwen3.8-flash-full, opus-4-5-quick, sonnet-4-6-quick (as
regraded), opus-4-6-quick, sonnet-5-5-quick (or-qwen3.8-27b-full not graded yet). "Separates" = the best label's 95 %
interval lies entirely above the worst label's.

| category | best | worst | spread | best low vs worst high | verdict |
|---|---|---|---|---|---|
| Honesty | 100 (4 Claude models) [83.9-100] | c171 quick 66.7 [44.9-83.1] | 33.3 | 83.9 > 83.1 | separates (just) |
| Coding | 100 (Sonnet 5.5, Opus 4.5) [86.7-100] | c171 quick 81.1 [62.0-93.1] | 18.9 | 86.7 < 93.1 | overlap; separates only in paired tests (Flash vs c171 full p 0.008); top 5 labels at 98-100 |
| Long context | 100 (Opus 4.5/4.6, Sonnet 5.5) [61-100] | Sonnet 4.6 33.3 [9.7-70] | 66.7 | 61.0 < 70.0 | overlap: big spread, too few items (6); top saturated |
| Agentic | 100 (6 labels, Sonnet 5.5 since its re-run at the 65,536 step limit) [43.9-100] | Opus 4.5 / 4.6 66.7 [20.8-93.9] | 33.3 | 43.9 < 93.9 | overlap: 3 repos; top saturated |
| Research | Q4 85.7 [48.7-97.4] | Opus 4.5 69.4 [32.1-94.4] | 16.3 | 48.7 < 94.4 | overlap: 7 items; not saturated (no label at 100); local r04 = 0 is the fixed-upstream server bug |
| Math | 100 (Sonnet 5.5, Q4, Flash) | Opus 4.5 90.0 [69.9-97.2] | 10.0 | 83.9 < 97.2 | saturated (all 90-100) |
| Instruction following | 100 (6 labels) | c171 full 95.0 | 5.0 | 83.9 < 100 | saturated (all 95-100) |
| Tool calls | 100 (all 8) | 100 | 0 | - | saturated |

Saturated at the top (the hard tier's targets): tool calls, instruction following, math, coding, long context,
agentic. Honesty separates and stays as it is. Research is not saturated, only small (7 items); more research items
would need a new frozen web snapshot, so it is left out here.

## 2. The hard tier

Every item graded mechanically (hidden tests, exact answers, checked constraints, expected call traces); no model
grades another. The same sampling, effort and sandbox as now. Items written as parameterised generators where
possible (fresh numbers per version, answers computed by brute force in the sandbox), which limits contamination and
lets a too-easy item be made harder without rewriting it.

| sub-tier | items | what makes it hard | grading |
|---|---|---|---|
| coding-hard | 20 | multi-file tasks (3-6 modules, 300-1,000 lines): a small interpreter with closures, a regex subset with backtracking, 3-way text merge, SQL SELECT over CSV (joins, GROUP BY, NULLs), CommonMark-subset renderer, JSON Schema subset, stack VM, Knuth-Plass line breaking, RGA text CRDT, ... | 40-100 hidden tests each; score = fraction passed, plus "fully solved" count |
| agentic-hard | 12 repos | 2-8K lines each; a feature spanning 3+ modules, 2-3 interacting bugs found only by hidden tests, a refactor under a hidden regression suite; 20-40 steps | hidden suite green (partial credit by fraction passed); per-step cap raised from 32,768 to 65,536 |
| math-hard | 25 | olympiad-style (AIME/HMMT hard, some proof-free olympiad shortlist style) with integer or exact answers; no tools | exact answer |
| longctx-hard | 20 (5 docs x 4) | ~80K Qwen tokens per document (~105K Claude tokens): multi-hop joins across sections (ledger + later corrections + rate table), state tracking through 300+ events with retroactive changes, contradictions between distant sections, temporal ordering | exact values; sets scored per element |
| tools-hard | 20 | multi-turn, 8-15 tools with distractors, nested and enum arguments, parallel calls, tool errors to recover from, a result that must feed the next call | expected call trace + final answer |
| instruct-hard | 20 | 6-10 stacked verifiable constraints per prompt (exact counts per paragraph, forbidden letters, a JSON block plus prose, ordering rules) | each constraint checked; score = fraction met |

Local limit that shapes longctx-hard: C*17.1 serves 131,072 tokens. The current documents are already ~95K Qwen tokens,
which leaves 35,342 tokens of answer room (Q4's lb_track ran out exactly there). Hard documents at ~80K leave ~48K.
"Reasoning across 100K tokens" in Claude's tokenizer fits; 100K Qwen tokens would leave ~28K and penalise thinking.

### Calibration: hosted Flash at 50-70 %, checked on your IQ3_S

Hosted Flash is the calibration model: it has the best non-Claude total on the current suite (93.4 %; only Sonnet
5.5 is higher, 97.6 % after its agentic re-run), so pinning it at 50-70 % is the closest stand-in for "the best
model at 50-70 %" without Claude spending; Sonnet 5.5 will probably land above that band. Your local IQ3_S (C*17.1) is
the second reference: the tier exists mostly to compare local quants, so items it never solves and items it always
solves are both wasted on it. No Claude requests during calibration; Claude models, if run at all, come afterwards
(not before November) as out-of-sample models, each within your $25 / $40 gates.

1. Write ~1.5x the items needed per sub-tier, as parameterised generators where possible (a too-easy or too-hard item
   is re-issued with other parameters, not rewritten).
2. Pass 1: hosted Flash 2 runs per item, IQ3_S 1 run per item, the whole pool.
3. Select to a spread, not only boundary items: about a third Flash solves, a third it partly solves or solves 1 of 2,
   a third it fails; drop items IQ3_S and Flash both fail every time, and items both solve every time. That puts
   Flash near 60 % and IQ3_S somewhat below (probably 35-55 %), with room on both sides for Q4, 27B and Max.
4. Pass 2: the re-issued and borderline items only (~30-40 % of the pool), same two models.
5. Selection bias: items chosen against Flash and IQ3_S understate those two a little. Mitigation: calibrate on a
   random half of each sub-tier's pool and check the predicted score on the other half before freezing.
6. Freeze the item set (fingerprint) before any scored run; the calibration answers are not scores.

### How long building and calibrating would take

Building (my work; for scale: the current suite, 117 items plus harness and the Claude/OpenRouter backends, took
about a day). Each item gets a reference solution or computed answer that the grader is tested against.

| part | drafted (1.5x) | work |
|---|---|---|
| coding-hard | 30 multi-file tasks, 40-100 hidden tests each, reference solutions | ~6-10 h |
| agentic-hard | 18 repos of 2-8K lines (from 3-4 shared app skeletons), a seeded task, visible + hidden suites, a reference fix each | ~15-25 h |
| math-hard | 40 problem generators with brute-force verifiers | ~4-6 h |
| longctx-hard | 3-4 document generators (ledger, event log, ...) with computed answers, 7-8 documents | ~4-6 h |
| tools-hard | 30 multi-turn scenarios with mock tools and expected traces | ~3-4 h |
| instruct-hard | 30 prompts with constraint checkers | ~2-3 h |
| harness | multi-file coding answers, partial-credit grading, multi-turn tools, document generation, self-tests, report | ~4-6 h |
| **total** | | **~40-60 h, about 5-7 working sessions**, plus ~1-2 h of your review of the item list before pass 1 |

Calibrating (machine time; hosted Flash runs in parallel with the local runs, collection only, as now):

| step | IQ3_S local | hosted Flash | my work |
|---|---|---|---|
| pass 1 (whole pool) | ~10-11 h (1 run) | ~8-10 h, ~$12 (2 runs) | - |
| selection and re-issue | - | - | ~4-8 h |
| pass 2 (~35 % of the pool) | ~3-4 h | ~3 h, ~$4 | - |
| **total** | **~14 h (two nights)** | **~$16, $0 Claude** | **~4-8 h** |

So about two to three days elapsed from a finished pool to a frozen tier, then the scored runs (section 3).
If you want Opus 4.5 on the hard tier, its guaranteed availability ends 2026-11-24: the Claude window would be
November 1-24.

## 3. Run time and cost (estimates)

Base output per item (C*17.1-like): coding 50K, agentic 60K per repo (25 steps), math 30K, longctx 35K, tools 6K,
instruct 4K; 3.4M output tokens per quick run. Each model's output scaled by its observed ratio to C*17.1 in the same
category on the current suite; "2x" doubles every output token (hard items may stretch thinking more than easy ones).
Claude: Batch API (half price) for single-turn items; documents and agentic context cached (write 1.25x, read 0.1x;
5-minute cache, so a step that thinks longer than 5 minutes re-writes). OpenRouter: no caching assumed.

**Local (decode ~140 tok/s on C*17.1, ~70 on Q4; agentic test runs ~5 s per step):**

| config | quick (1 run) | full (3 runs) | today's suite for comparison |
|---|---|---|---|
| C*17.1 | ~7 h | ~21 h | full 9.4 h |
| Q4 | ~13.5 h | ~40 h | quick 5.9 h |

**API (quick; full = 3x):**

| model | price in/out per M | quick | 2x output | biggest part |
|---|---|---|---|---|
| Opus 4.5 | $5 / $25 | ~$60 | ~$100 | agentic ~$21 |
| Opus 4.6 | $5 / $25 | ~$83 | ~$146 | agentic ~$36 |
| Sonnet 4.6 | $3 / $15 | ~$81 | ~$149 | agentic ~$33 |
| Sonnet 5.5 | $2 / $10 | ~$68 | ~$128 | agentic ~$38 |
| Qwen3.8 Flash (Alibaba) | $0.15 / $0.47 | ~$4 | ~$6 | agentic ~$2.40 |
| Qwen3.8 27B (DeepInfra bf16) | $0.15 / $1.875 | ~$9 | ~$15 | agentic ~$3.40 |
| Qwen3.8 Max 0902 (Alibaba) | $2 / $6 | ~$52 | ~$72 | agentic ~$31 (no caching assumed) |

Wall time on the API: Claude ~3-6 h per quick run (the Batch API up to an hour per batch; 12 agentic repos run
serially, Sonnet 5.5 at its thinking length ~25 min each); Flash ~3 h; 27B ~12-15 h (DeepInfra ~14 tok/s per stream;
agentic serial ~14 h alone).

**Against your gates:** every Claude model is over the $25 "run only under" line for a whole hard-tier quick run, and
over the $40 hard stop. OpenRouter Max 0902 is over its $15 stop. Options:
(a) run the hard tier in two parts per Claude model: single-turn + long context (~$25-45) and agentic (~$21-38);
(b) cut agentic-hard to 10 repos x 20 steps (~-35 % of its cost);
(c) run agentic-hard only on the local models + Flash/27B, and on one Claude model.
Each needs your OK when its estimate is over $25.

## 4. Fixes that come with it (same rules for every model)

- Agentic step cap 32,768 -> 65,536: **done 2026-10-13** for every model (Sonnet 5.5 hit 32,768 on 2 of 3 current
  repos while thinking before its first write; no other label went above 15,679; its agentic items were re-run).
- `run.sh estimate` without `--from` picks the newest complete local label even when it holds one category (it chose
  c171-r04-fix2026, research only, and printed $7.91 for Max 0902 instead of $11.04): pick the newest label that
  covers every category.
