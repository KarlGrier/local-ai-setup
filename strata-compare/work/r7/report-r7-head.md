## Round 7 — C\*6 soak and promotion, Strata v0.1.25–v0.1.27 → C\*7, the staging oracle, two conversations at once (2026-09-29 19:55 → 2026-09-30 ~04:30)

**Status: C\*7 is promoted and running on 127.0.0.1:8080** (the launchers' default; engine `engine-cstar7/strata`
sha256 `886b6ab2…`, `configs/Cstar7.json`). The 48-hour passive uptime monitor is watching it.

**What happened, in order:**
1. **C\*6 passed its full 2-hour soak** (333 requests, 0 errors) and was promoted at 22:22. The rollback test passed.
2. **Strata v0.1.25, v0.1.26 and v0.1.27** (v0.1.27 appeared at the first tag check) were reviewed. C\*6's 12 patches
   were ported onto v0.1.27 and the update was measured on its own:
   * prompts **3.6–3.7 % faster** (120K: 36.6 → 35.2 s), from 0.1.25's fused hyper-connection norms;
   * decode **bit-identical**;
   * accuracy **bit-identical**, needles 72/72, the chat-cache round trip exact.
3. The browser test then found **a bug in upstream 0.1.26+**: after a Stop during a long prompt read, the next request
   crashed the engine. I fixed it (patch 0013) and verified the fix. The fixed build passed the 2-hour soak (335
   requests, 0 errors) and was **promoted as C\*7** at 02:40.
4. **Item 1 (engine oracle for next-layer expert staging):** the ~15 % ceiling exists only with the static expert set.
   On your served configuration a perfect predictor saves **0–3 %** by staging, or **8–10 %** by CPU-cache warming,
   and a ~60 %-recall predictor keeps **~2–3 %** (warming) or loses (staging). **Do not build.**
5. **Item 4 (two conversations at once):** **useful only for overlapping tool waits.** That already works through the
   server's queue (+5 % to +46 % total throughput for two web-search agents, no engine change). Engine-level
   concurrency has an ideal ceiling of +28 % total throughput with each conversation ~36 % slower; not worth
   prototyping for single-user chat.

| | C\*6 (round 6) | **C\*7 (now on 8080)** |
|---|---|---|
| base | Strata v0.1.24 + 12 patches | **v0.1.27 + 13 patches** (12 ported + the Stop fix) |
| 32K / 64K / 120K prompt (uncached, served, 4 pairs) | 10.00–10.02 / 19.36–19.43 / 36.55–36.68 s | **9.64–9.66 / 18.65–18.71 / 35.19–35.33 s** |
| decode | 94.1 tok/s (all long requests, T 1.0) | 93.7 tok/s (= ; greedy output bit-identical) |
| accuracy (teacher-forced, 7 texts, one GPU and helper) | – | **bit-identical to C\*6** |
| needles / round trip / browser / fallback | 72/72 · exact · 54/56 · pass | **72/72 · exact · 54/56 · pass** |
| Stop during a long prompt read, then continue | works | works (upstream 0.1.26+ does not; fixed in 0013) |
| 2-hour soak | 333 requests, 0 errors | **335 requests, 0 errors** |

**My mistakes this round (all caught, none affect a result):**
* My soak waiter matched its own command line and sat idle for ~23 minutes.
* The first C\*7 round trip used a config without the static expert set the test needs. It was re-run correctly.
* My own quick reproduction script for the Stop bug did not trigger it (its prompts never took the batched path).
  The evidence is the browser test and round 5's stop120k, which did.
* The first oracle design (greedy decode, the GPU waiting for every staged copy) could not measure staging. It was
  redesigned: fixed text, landed copies only.
* I found a Round 6 mistake: its browser test had set C\*6's shared chat temperature to 0.6. I restored your 1.0
  before any promotion.

**Tag watcher:** read at every step (`logs/r7/tagwatch-reads.log`); v0.1.27 at 19:57, nothing newer since.
