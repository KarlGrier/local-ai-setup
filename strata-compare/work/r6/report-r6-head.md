## Round 6 — experimental engine work (2026-09-29 11:58 → 17:25, stopped early on your request)

**Status: candidate C\*6 passed every check that ran, but it is NOT promoted.** The 2-hour soak was stopped after
43 minutes on your request (133 requests, 0 errors so far) and is recorded as incomplete. **C\*5 (round 5) is on
8080**, unchanged: engine `engine-cstar5/strata` sha256 `3ee92c9a…`, `configs/Cstar5.json`. It answered a test question
at 17:21. Nothing of mine is running.

**Left to do (nothing else is open):**
1. **the soak:** a full 2-hour soak of C\*6 on 8080 (`work/r6/soak.sh 120`); 43 of 120 minutes ran;
2. **the promotion decision** (after the soak): if it passes, point the launchers at `configs/Cstar6.json` (prepared:
   `work/r6/run-strata.sh.new`, `work/r6/switch-model.sh.new`), run `work/r6/rollback_test.sh`, leave C\*6 on 8080,
   write patches/PR (already drafted) as final;
3. **the 48-hour passive uptime monitor** (`work/r6/uptime_monitor.py`, tested dry): not started, as you asked.

**To try the candidate on 8080** (stop the running C\*5 first — `switch-model.sh` keeps whatever Strata already runs):
`STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar6.json ./switch-model.sh strata`
**Back to C\*5:** `STRATA_PORT=8080 ./run-strata.sh stop && ./switch-model.sh strata` (the default is still C\*5).

| (4 alternating A/B pairs, fresh server each, your settings T 1.0) | C\*5 (on 8080) | **C\*6 (candidate)** |
|---|---|---|
| decode, all 768+-token requests | 89.9 tok/s | **93.6 tok/s (+4.1 %, runs do not overlap)** |
| time per generated token | 11.13 ms | **10.69 ms (−3.9 %)** |
| long reasoning 8K: math / code | 101.2 / 83.1 tok/s | **103.9 / 86.5 tok/s** |
| 32K / 64K / 120K prompt (uncached, cold page cache) | 10.0 / 19.4 / 36.6 s | 10.0 / 19.4 / 36.6 s (=) |
| GPUs | RTX 5080 | RTX 5080 + RTX 4060 Ti as helper (~6.5 GB of it; the desktop kept ≥ 535 MiB in the soak) |

C\*6 = Strata v0.1.24 + `patches/r6/0001–0012` (C\*5's 9 patches + 3 new) + the RTX 4060 Ti holding 3,300 more
experts. If the 4060 Ti lacks memory at start, the launcher starts the same build on the 5080 alone (tested).

**What was found:**
* **Round 5's verdict on the second GPU was wrong for Linux, and the reason is one line of upstream code.** With a
  helper GPU, upstream pins only 8 GiB of the 47 GB expert arena. The comment calls it a Windows (WDDM) workaround,
  but it applies on Linux too. With the whole arena pinned, the 4060 Ti helper makes verify windows 2–3.5 % faster
  instead of 2–9 % slower, and prompts are as fast as on the 5080 alone (32K: 10.9 s instead of 12.6 s).
* **An exact 1–4 % from the n-gram table.** The table is read from the SSD. Each verify window used to wait for its
  first token's rows, 0.61 ms per window. They are now requested one window early, while the window commits and the
  drafter runs. The output is bit-identical.
* **`--dump-routing` double-counted** 14.9 % of its rows (rejected drafts). Fixed and verified against the engine's
  own counters.
* **Where the time goes.** In decode, the GPU waits for the CPU experts 16 % of each window, most of it in layers 0–7.
  In a 32K prompt, weight movement is only 4 %. The time is in underfilled MMQ expert products (21 %), a per-expert
  group copy (10 %), and the GDN (25 %) and QSA (14 %) mixers.
* **Predicting and prefetching the next layer's experts: not built.** The perfect-prediction ceiling is 14.7 % of a
  window (model; your bar for a large track was ~15 % measured). Realistic estimates:
  * cache warming 5 %;
  * PCIe staging ~10 %, as a model that leaves out the DMA's effect on the GPU.

  This is Round 7's first item.
* **Dropped with numbers:**
  * per-layer cache budgets (~1 %);
  * using the helper only for some layers or window sizes (noise);
  * reading the n-gram rows beside layer 0 (the wait moved to the GPU);
  * the host's activation quantization overlap (≤ 1 %).

**Things that went wrong, all caught:**
* **Compile during a measurement:** I once compiled while a measurement ran. That run was redone, and builds then went
  through the queue.
* **Test-server stop bug:** my test-server stop script left one server running, so a baseline screen was not fresh. I
  added a fourth A/B pair.
* **Memory guard stop:** my memory guard correctly stopped a VRAM-grab test that goes below your 300 MiB floor. That
  failure mode can't be tested within the floor.
* **Sampler-test false alarm:** the sampler test first looked failed. The cause was its reference drifting with the
  adaptive expert tier. With placement frozen, the samples match (p 0.34 / 0.63).
* **Missed release alerts:** I did not read the tag watcher's log during the round. **Strata v0.1.25 (13:18) and v0.1.26
  (15:18) were released** after the Phase B freeze (12:40). Per your rule they are Round 7 backlog, not reviewed yet.
