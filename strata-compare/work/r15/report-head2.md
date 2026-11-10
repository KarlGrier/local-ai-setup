## Round 15 — big-model rehearsal ("worst-case Qwen4 Flash"): two stand-in files on v0.1.40.2, every placement, the file tier, settings, quality, and the catch-up → C\*15 (2026-10-07 07:29 → 2026-10-08 END_TIME)

Chronological notes: `NOTES.md` ("ROUND 15"). Phone summary: `results/round15-summary.md`. Scripts: `work/r15/`; runbook
runs `bringup/out/r15` (IQ3_S: the port's gates, C\*15's clean clone), `r15q8` (Q8_0), `r15q5s` (the UD-Q5_K_XL splice).
Raw results: `results/r15/`, `results/runs.jsonl`. Branches (local): r15-port (= patches/r15p27), r15-meas (+ r15-meas27).
Configs: `configs/r15-q8.json` / `r15-q8-131k.json`, `configs/r15-q5s-C.json` / `r15-q5s-B.json`, `configs/Cstar15.json`.

**Display: the monitor is on the motherboard output (the AMD iGPU) for the whole round** (your correction; my first
notebook line had said the 4060 Ti). It has been there since the RAM test of 10-06 — a note is added at the end of the
Round 14 section for the part of that round after the resume. Nothing about the display was changed.

**Memory rule for the stand-ins** (your exception): MemAvailable ≥ 6 GiB, ≥ 300 MiB free on the 5080, chat cache 2 GiB,
a run stopped if swap grows by more than 4 GiB (bringup/lib/guard.py, 0.2-s samples, 3 in a row to stop). Every other
load kept the 20 GB floor. **The planner's default budget and my starting budget (64 GiB) did not use your 6 GiB margin**
(your note); step 4 added the largest budget that held it over a full run (Q8_0 71 GiB, the splice 72 / 71).

