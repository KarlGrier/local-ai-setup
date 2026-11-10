# Round 10 — summary (final, 2026-10-03 23:35)

**In 5 lines:**
1. **C\*12.1 is on 8080** (= C\*12 on Strata v0.1.38: the same output and speed, plus v0.1.38's server security fixes;
   promoted 10-03 23:30 after its gates, a 2-hour soak with 0 errors and a real rollback test). C\*12 was promoted at 19:00.
2. **vs C\*11 on two untouched holdouts: decode +7.9 % / +8.4 %, total time −8.3 % / −7.7 %, TTFT −16 % on a 30K document,
   −14…−19 % on research prompts over 4K**; accuracy closer to the exact computation than C\*11.
3. Biggest win: the 5080 stops pulling in experts the 4060 Ti already holds (+5.4 %); then fused prompt experts + 16K
   chunks, upstream #453 / #413, and three graph-branch ports from the Eddoursul fork.
4. Not kept: the helper following the chat, your learned profile (−4.2 %), slower decay, spec 8, #443, B.4; Q4 = half the
   speed (better long-text NLL, same acceptance); Signal does not load (Q8_0 token embedding).
5. **I missed Strata v0.1.37 / v0.1.38 during the round** (the watcher flagged them; I didn't read it for ~25 h). Ported
   after C\*12: C\*12's patches on v0.1.38 give exactly C\*12's output (TF 18/18 bit-identical, 7/7 hashes) at the same
   speed; our swap landing beat upstream's new wait by 1.8 %, so it stayed. → **C\*12.1, promoted; round ended (no backlog).**
## Helper-tier counts (Phase A)
| | before (v0.1.35, A.1): fresh / an hour / aged | with A.2 (v0.1.36): fresh / an hour / aged |
|---|---|---|
| swaps pulling in an expert the helper already holds | 22.9 % / 22.8 % / 22.8 % | **0 / 0 / 0** |
| experts held by both cards (of the helper's 3,300) | 637 → 968 / 800–1,070 / 924 | **0** |
| routed entries 5080 / helper / CPU | 71.0 / 6.6 / 22.4 · 71.5 / 6.5 / 22.0 · 71.5 / 6.5 / 22.0 % | 64.8 / 18.4 / 16.7 · 65.2 / 18.2 / 16.6 · 64.6 / 18.4 / 17.0 % |
| host waits for the helper | 0.3 % of decode | 2.9–3.1 % |
A.2: LDR decode **+5.4 % fresh, +5.3 % aged**, decode screens +2.5 %. A.3 (helper's set following the chat): moves up to
4,675 experts per request, CPU share −0.5…−0.9 points more, no repeatable gain → dropped. #477's learned profile: the
helper gets 37 % of entries and becomes the bottleneck → −4.2 %.

## The Eddoursul fork vs ours — stage table (Phase C, both on the 5080 alone, ms per verify window)
| stage | ours math | fork math | ours code | fork code |
|---|---|---|---|---|
| router / ring / hits | 0.44 | 0.74 | 0.45 | 0.68 |
| wait for the pool's plan | 0.25 | 0.03 | 0.25 | 0.03 |
| shared expert + inputs | 0.94 | 0.10 (+1.68 beside) | 0.87 | 0.08 (+1.38) |
| routed experts (VRAM) | 2.74 | 3.03 | 2.15 | 2.50 |
| wait for the CPU | 5.16 | 12.41 | 3.69 | 8.88 |
| GDN mixer | 3.03 | **2.39** | 2.75 | **2.36** |
| QSA mixer | 1.73 | **0.84** | 1.62 | **0.83** |
| hyper-connection reads | 3.18 | **2.32** | 2.74 | **2.23** |
| head | 0.75 | 0.61 | 0.67 | 0.61 |
| window / decode | 18.98 ms / 127.6 tok/s | 22.85 / 107.3 | 15.95 / 103.8 | 18.55 / 99.5 |
With its second GPU the fork waits 35–40 ms per window here (per-layer round trips over Gen4 ×4): 3× slower. Prompts,
fork alone vs our base: 4K +4.5 %, 8K −1.2 %, 32K −7.7 %, 120K −5.3 % (C\*12 is faster than the fork alone now).
Ported (exact): its mixer branches (34a35db, b063c13) −1.5…−1.7 % per round, the shared expert on a branch (962b99c's
idea) ~0.9 %.

## C\*12 vs C\*11
| screen | decode | TTFT | total time |
|---|---|---|---|
| fresh general holdout | +7.9 % (110.1 → 118.8 tok/s) | 30K doc −16 % (8.69 → 7.30 s); short −11 % | −8.3 % |
| LDR holdout | +8.4 % (113.0 → 122.5), ms/round −8.5 % | < 4K −6.8 %, 4–16K −18.7 %, ≥ 16K −14.0 % | −7.7 % |
| full screens | +6.6 % (117.3 → 125.1) | 32K −14.8 %, 64K −12.5 %, 120K −11.0 % | −6.6 % |
Gates: 7/7 with every new switch off; TF closer to FP16 than C\*11 (0.042 vs 0.107); needles 12/12; round trip identical;
Stop 7/7; repeat 3/3; browser 54/56 (the 2 known non-bugs); fallback ok; soak 414 requests / 0 errors, MemAvailable ≥ 22.2
GB, chat cache ≤ 12,273 of 12,288 MiB; soaked vs fresh +0.6 %; rollback test passed.

## By phase
| phase | kept (→ C\*12) | not kept |
|---|---|---|
| v0.1.36 | the port (same output and speed as C\*11); cluster kernels (−2.8 % per round at 112K); fused prompt experts (TTFT −3.3…−5.9 %) | – |
| A helper tier | A.2 (+5.4 %) | A.3, #477 learned profile, make_profile, decay 0.8 / 0.9, --adapt-tuned (n/a) |
| B upstream PRs | #453 (TTFT −0.6 s per long prompt), #413 (−1.1…−1.4 %) | #443 (max4 slower; WARP1 ≈ 0.2 %), B.4 (no served gain), #439 / #454 n/a |
| C fork | 34a35db + b063c13 + 962b99c's idea (graph branches) | its second GPU (3× slower here), 2ec7a80, the rest (backlog) |
| D settings / Q4 | `--prefill auto:16384` (with fused) | spec 8 × suffix 3 / 8 / 16; Q4 (half speed); Signal (does not load) |

## Side findings
- Exact sampling + upstream's timing-based draft policy → sampled text varies run to run (distribution exact); Round 9's
  "repeatable" holds with exact sampling off. An unseeded warm-up made served repeats differ; without it they repeat.
- Process slips: the release flags unread for ~25 h; Phase C's queue idle at a hold 04:43–09:50; a queue runner that logs
  every exit code as 0.

**Running now:** C\*12.1 on 127.0.0.1:8080 and a passive 48-hour monitor (logs/r10/uptime/). Queue runner and release
watcher stopped. Rollback: stop 8080, then `STRATA_CONFIG=configs/Cstar12.json ./switch-model.sh strata`.

Details: REPORT.md "Round 10"; NOTES.md; the live log of this summary: work/r10/round10-summary-live.md.
