# Round 6 — summary (Strata on the RTX 5080 + RTX 4060 Ti PC, 2026-09-29, stopped early at 17:25)

**Status: candidate C\*6 passed every check that ran but is NOT promoted.** The 2-hour soak was stopped at 43 minutes on
your request (133 requests, 0 errors), so it is incomplete. **C\*5 (round 5) is on 127.0.0.1:8080**, unchanged
(engine sha256 3ee92c9a…, configs/Cstar5.json), and verified answering. Nothing of mine is running.

**Left to do:**
1. **The full 2-hour soak of C\*6:** `work/r6/soak.sh 120`.
2. **The promotion decision:** if the soak passes, apply the prepared launcher change (`work/r6/*.new`) and run
   `work/r6/rollback_test.sh`.
3. **The 48-hour passive uptime monitor** (`work/r6/uptime_monitor.py`): not started.

- **Try C\*6 on 8080:** `STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar6.json ./switch-model.sh strata`
- **Back to C\*5:** `STRATA_PORT=8080 ./run-strata.sh stop && ./switch-model.sh strata`

**C\*6** = Strata v0.1.24 + 12 patches (C\*5's 9 + 3 new) + the RTX 4060 Ti as a helper GPU (3,300 more experts). Engine
`engine-cstar6/strata` sha256 a56a444b… (clean build, sm_89 + sm_120), config `configs/Cstar6.json` sha256 b9bd8eb2…
If the 4060 Ti lacks memory at start, the launcher uses the 5080 alone (tested).

**Key numbers (4 alternating A/B pairs, fresh server each, your settings T 1.0 / 0.95 / 20 / 0.05):**
| | C\*5 | C\*6 |
|---|---|---|
| decode, all long requests | 89.9 tok/s | **93.6 (+4.1 %, runs don't overlap)** |
| time per generated token | 11.13 ms | **10.69 ms (−3.9 %)** |
| long reasoning 8K math / code | 101.2 / 83.1 | **103.9 / 86.5** |
| prompt 32K / 64K / 120K (uncached, cold) | 10.0 / 19.4 / 36.6 s | same |
| accuracy (teacher-forced, 7 texts) | – | one GPU: bit-identical to C\*5; with helper: within the usual last-bit spread |
| needles / quality / web-replay chat / chat-cache round trip | – | 72/72 · 28/29 (= C\*5) · 16/16 · bit-exact |
| sampler test | – | unbiased (with expert placement frozen: p 0.34 / 0.63) |
| Stop, overflow, concurrent, idle CPU, launcher fallback | – | all pass (VRAM-grab test not possible within the 300 MiB floor) |
| browser test incl. the Web search switch | – | 54/56 (the 2 = known non-bugs from round 5) |
| soak | – | **incomplete: 43 of 120 min, 133 requests, 0 errors, MemAvailable ≥ 25.4 GB** |

**Why C\*6 is faster (measured):**
1. **The second GPU works after all.** Upstream pins only 8 GiB of the 47 GB expert arena whenever a helper GPU is on,
   a Windows workaround applied on Linux too. Pinning all of it (patch 0011) turns the 4060 Ti from 2–9 % slower into
   2–3.5 % faster per verify window, with prompts as fast as one GPU (32K 10.9 vs 12.6 s capped). Round 5 rejected the
   helper because of this cap.
2. **Exact n-gram prefetch (patch 0012).** The next window's first-token rows are requested at commit: 0.61 → 0.28 ms
   per window, windows 1–4 % faster, bit-identical output.
3. **`--dump-routing`** writes only kept rows (patch 0010; it double-counted 14.9 %).

**Phase A findings:**
* **Decode:** the GPU waits for the CPU experts 16 % of each window, mostly in layers 0–7.
* **Prompts:** in a 32K prompt, weight movement is 4 %. The time goes to underfilled MMQ (21 %), a per-expert group copy
  (10 %), GDN (25 %) and QSA (14 %).
* **Router:** no sync delay after the router.
* **Cache warming:** −36 % of the CPU expert time in a microbenchmark.
* **Prediction ceilings:** perfect prediction 14.7 % of a window (oracle, model); causal predictor 58–80 % byte recall,
  realistic 5 % (warming) / ~10 % (staging, model).
* **Large prediction/staging track not started:** it is below your ~15 % bar.
* **Dropped:** per-layer cache budgets (~1 %) and selective helper use (noise).

**Mistakes (caught and redone):**
* **Compile during a measurement:** one Phase A run was contaminated by a build and re-done.
* **Non-fresh baseline screen:** my stop script left a server running once, so a fourth A/B pair was added.
* **Tag-watcher log unread:** **Strata v0.1.25 (13:18) and v0.1.26 (15:18)** were released during the round, after the
  Phase B freeze. They are Round 7 item 0, unreviewed.

**Round 7 backlog:**
0. Review v0.1.25 / v0.1.26 and measure them on their own.
1. An engine oracle run for next-layer PCIe staging; build it only if ≥ 15 %.
2. Prompt MMQ via a pointer table (removes the ~10 % copy).
3. The underfilled prompt MMQ.
4. A deterministic draft-policy switch.
5. Adaptive draft length.
6. Helper expert placement by exposure.
7. Prefetching the drafts' n-gram rows.

Full details: REPORT.md "Round 6"; day log: NOTES.md "ROUND 6".
