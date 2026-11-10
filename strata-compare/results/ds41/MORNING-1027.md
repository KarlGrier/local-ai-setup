# Morning report 10-27 - DeepSeek round closed; LDR next

Everything ran overnight (10-26 21:26 to 10-27 02:13). Every kernel check was clean. 8080 is back on P021m and the
research queue is released. Full detail: round-report-1026.md (sections 5, 6, 9 and 10) and CHECKPOINT-1026.md.

## 1. Hard set: DeepSeek at its best vs Qwen at its best

29 hard items, one run each, the same 30,000-token room for every answer:

| setting | score (of 100) | s per answer | thinking hit the room limit | cut off |
|---|---|---|---|---|
| Qwen medium | **88.5** | 23 | 2 | 0 |
| Qwen xhigh | 67.4 | 88 | 10 | 0 |
| DeepSeek effort 50 | **72.4** | 202 | 2 | 0 |
| DeepSeek effort 75 | 66.7 | 251 | 3 | 2 |

- **Main result: DeepSeek's better setting minus Qwen's better setting = -16.1 points per item (95 % -31.0 to -3.4).**
  DeepSeek is better on 1 item and worse on 5 (four honesty items and one math item). Without the 8 honesty items the
  two are level (-3.2 points per item on the other 21).
- **Honesty** (made-up questions): Qwen medium 87.5, Qwen xhigh 12.5. DeepSeek scored 37.5 at effort 50, 25.0 at 75
  and **37.5 at effort 25**, so less thinking does not help it. It still thinks ~4,700 tokens before inventing an
  answer.
- **Blind research** (out of 10): Qwen medium 7.25, xhigh 7.0, DeepSeek e50 6.5, e75 4.5. Qwen medium is ahead of
  DeepSeek e50 on both questions.
- **DeepSeek effort 75's two cut-offs** were not the room limit:
  - one answer fell into a "0000..." loop, which the server's repeat guard ended;
  - the other filled the old 32K context during research (256 tokens left to answer). 128K now prevents that.
- **Suggested DeepSeek default: effort 50** (better than 75 and faster). Your call.

## 2. DSpark and repeatability

- DSpark never loads in this config (`auto`; the experts don't fit the GPUs), so there was no A/B/A and the config is
  unchanged.
- Repeat pairs with `--dspark none`: still no pair identical, so DSpark is not the cause.
- Carry-over (the same text scored twice in one engine):
  - With expert placement frozen, the decode path is byte-identical.
  - The prompt path still differs, mostly over its first ~16 positions; past position 512 it is 6-7x below the
    rounding references.
  - Next test, in the checkpoint: the same check with the RAM store off.

## 3. Daily context is now 128K

**One real long prompt** on the daily config at 128K with everything up, 96,917 tokens:

| read | decode at that length | lowest free memory | slot it leaves |
|---|---|---|---|
| 102 s (947 tok/s) | 21.0 tok/s (28 on short prompts) | **18.9 GB** (>= 14: pass) | 0.10 GB in RAM, 101 MB on disk |

The follow-up on that conversation came back from RAM: only 115 new tokens read, first token in 3.6 s.

**Worst case.** 16 RAM slots all near 128K (~0.13 GB each) would leave 13.99 GB, just under the rule. So conversation
RAM is now capped at **1.7 GiB**: ~13 full-length 128K chats, or all 16 normal ones. Past the cap the least recently
used conversation moves to the disk folder and comes back from there.

**The cap is a small local engine change**, checked three ways:
- a conversation moves to disk and back correctly;
- two seeded requests give identical text on the capped engine and the shipped one, with placement frozen;
- the launcher starts and answers.

**Switched 02:13.** The 32K config is kept as configs/DS41-daily.json.before-128k.

**Long-context items** (optional): the run swap guard stopped them after 6 minutes, so there is no comparison (1 of 6
answered; it scored 1.00, like Qwen).
- The kernel pushed 34 MB of other programs' idle pages to swap while the ~95K-token documents streamed the model
  files through memory.
- The engine itself never swapped, and free memory stayed above 23 GB.
- In daily use a very long prompt can do the same, a few tens of MB. Lower swappiness (your call, as for Maya) is the
  way to test it properly.

## 4. Graded set and the rest of the block (reported 10-26 evening, unchanged)

- **Quick set:** saturated. Every category is at the ceiling except honesty (Qwen 100, DeepSeek 60) and math (level at
  83.3).
- **Blind research on the quick set:** Qwen 8.3, DeepSeek 7.8 (three questions).
- **Resuming a conversation is exact:** a resumed run scores byte-identically to the same run without the
  set-aside / take-back. All three variants pass the five-check rounding rule.
- **Follow-up fix:** 12 / 12. The upstream issue is drafted but not posted.

## 5. Two slips of mine tonight (fixed; no result changed)

- **The hard-set driver skipped the repeat pairs as "build failed".** It looked for the build record in the wrong state
  file. I re-ran them after the 128K check.
- **The 128K driver called a passing long run a fail.** It read the lowest memory from a field the run never fills. I
  re-judged it from the monitor's own line, then ran the cap tests and the switch. The shared code now reads the
  monitor line.
- **A third check needed a rework.** The first identity check compared builds with the expert cache on, where even one
  build doesn't repeat itself (the control showed 292 vs 513 tokens). It was redone with placement frozen.

## 6. LDR: where we are, next steps

**Where we are** (from results/bench2/CHECKPOINT-phase3.md, PLAN.md and LDR NOTES.md):
- Phase 4:
  - Items 1 (setup profile + setup check) and 8 (critic) are the default for your Jan deep research since 10-23.
  - Item 4 (the tried list) and item 2 (the "not yet" fresh check) went through stage 3 and stay off (10-24 21:40).
  - Early stop is dropped from deep research.
- The bench queue is idle. The Jan runner is up; its relief restart is at 13 GB when DeepSeek is on 8080. 8080 runs
  P021m.

**Next, from your open list (10-24 notes):**
1. **Read-only code tool for the research agent:**
   - shallow clone into a capped scratch folder, deleted after the run;
   - grep with file:line, a file tree, and line-range reads;
   - public GitHub API, unauthenticated;
   - never build or run anything from the clone.

   The test reruns your 10-24 DeepSeek speed-ideas question with the tool. The key: findings Fable, Pro and Astra agreed
   on, each verified against Strata v0.2.4's source first. Then a blind grade, plus every code reference in both reports
   checked against the repo.
2. **The six fixes from that 10-24 run,** each through the usual stages:
   - an engine/version check for every flag in an action plan;
   - checker findings marked inline;
   - arithmetic done in code;
   - no citations outside the evidence;
   - gains measured against your own baselines;
   - the time budget enforced.
3. **Later:** a code tool in Jan, and why long-context paths disagree (the yardstick follow-up).

**Two questions before I start:**
- The code-tool test grades your own 10-24 LDR report against the rerun. Is it OK for a blind grader to read that one
  report? I don't read your LDR research otherwise.
- Shall I start building the code tool? It's code-only work; 8080 stays up, and the GPU is used only for the test run.

Measured and drafted with Claude Code.
