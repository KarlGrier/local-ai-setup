# Round 7 — summary (Strata on the RTX 5080 + RTX 4060 Ti PC, 2026-09-29 19:55 → 2026-09-30 ~04:30)

**Status: C\*7 is promoted and on 127.0.0.1:8080** (engine `engine-cstar7/strata` sha256 `886b6ab2…`,
`configs/Cstar7.json`, the launchers' default). The 48-hour passive uptime monitor is running
(`logs/r7/uptime/`, stop: `kill $(cat logs/r7/uptime/monitor.pid)`).

- **Rollback to C\*6:** `STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar6.json ./switch-model.sh strata`
  (stop first: `switch-model.sh` keeps whatever Strata is running).

**1. Round 6 wrap-up.** C\*6's full 2-hour soak passed: 333 requests, 0 errors, memory above your floors, no leak, chat
cache within budget. C\*6 was promoted at 22:22. The rollback test passed; I fixed the round-6 test, which never
actually switched.

**2. Item 0 — v0.1.25, v0.1.26, v0.1.27** (v0.1.27 was found at the first tag check). C\*6's 12 patches were ported. One
merge was needed, because our v5 kernel's file also got upstream's Turing change. Measured on its own, the update gives:
| | C\*6 | **C\*7** |
|---|---|---|
| 32K / 64K / 120K prompt (served, 4 alternating pairs) | 10.00–10.02 / 19.36–19.43 / 36.55–36.68 s | **9.64–9.66 / 18.65–18.71 / 35.19–35.33 s (−3.6…−3.7 %)** |
| decode | 94.1 tok/s | 93.7 (=; greedy output bit-identical) |
| accuracy (teacher-forced, 7 texts, one GPU and helper) | – | **bit-identical to C\*6** |
| needles / chat-cache round trip / browser / fallback | – | 72/72 / exact / 54/56 (the two known non-bugs) / pass |
| 2-hour soak | 333 requests, 0 errors | **335 requests, 0 errors** |

- **Where the gain comes from:** 0.1.25's fused hyper-connection norms (prompt path). They do not overlap our v5
  decode kernels, so both are kept. The grouping-table change does nothing on this config.
- **0.1.26's batched draft-layer pass is skipped with KV streaming:** confirmed in the code and at runtime.
  - The old pass costs **≤ 0.69 s per long prompt (6.6–7.2 % at 32K, 2.2 % at 112K)**. That is the ceiling for
    extending the batched pass to KV streaming (Round 8 backlog #1).
- **0.1.27's CJK draft vocabulary:** −1 to −2 % on English decode, so it is not used.
- **An upstream bug in 0.1.26+, found by the browser test and fixed (patch 0013):**
  - After a Stop during a long prompt read, the next request that read a prompt in batches failed.
  - The engine then exited and the server restarted it, losing all parked chats.
  - Cause: a stale "cancelled" error string that 0.1.26's new draft-layer hook reads.
  - Verified fixed with the browser test and round 5's stop120k. Write-up: `pr-drafts/26-stop-then-next-request.md`.

**3. Item 1 — engine oracle for next-layer expert staging** (recorded experts replayed as a perfect predictor, staged
to VRAM over PCIe during the GPU phase, staging VRAM charged to the expert cache):

| saving per window (T2 / T3 / T4) | static tier (your spec: `--adapt-swaps 0`) | **adaptive tier (what C\*7 serves)** |
|---|---|---|
| staging, perfect predictor, ≤ 4–6 experts per layer | **+11.8 … +15.1 %** | **−0.9 … +2.8 %** |
| staging everything (16 slots) | −3.6 … −7.3 % (slower) | – |
| CPU-cache warming ≤ 6 experts, perfect | +10.3 … +13.9 % | **+8.1 … +9.9 %** |
| staging ≤ 4 + warming ≤ 4 | **+16.6 … +17.8 %** | +0.1 … +4.2 % |
| **~60 %-recall predictor** (staging / warming) | +2.7…+4.6 % / +3.3…+3.7 % | **−2.9…−0.6 % / +1.7…+2.8 %** |

- **The ≥ ~15 % ceiling holds only with the static expert set.** On the served adaptive tier, staging is worth 0–3 % and
  warming 8–10 % even with perfect prediction; a realistic predictor keeps ~2–3 %. **→ do not build.**
- **Why:**
  - A layer's CPU experts on the static tier (~22–29 MB) take twice the GPU phase to copy.
  - Copies still in flight compete with the CPU pool for the same DRAM.
  - The DMA also slows the GPU's own stages.
  - The adaptive tier already holds most of what staging would move.
- **Method note:** greedy replay drifts as soon as the GPU computes a staged expert (a different rounding flips a
  near-tied router choice). So staging was measured on a teacher-forced fixed text, where the predictor covered ~98 %.
  Round 6's 14.7 % was a model, made before the 4060 Ti helper.

**4. Item 4 — two conversations at once** (feasibility, evidence vs estimate kept apart). **Recommendation: useful only
for overlapping tool waits.**
- **a) nsys (served flags):**
  - A window is 18.7 ms: the GPU works 14.6 ms of it and waits 2.7 ms for the CPU.
  - The CPU pool takes 6.4 ms per window.
  - *Estimate:* the ideal interleave of two conversations is **+28 % total throughput**, with each conversation ~36 %
    slower.
- **b) `--spec-split`, 8 = 4 + 4:**
  - It now beats the unsplit 8-token window: −3 … −6 % on the served tier, −11 … −15 % on the static tier.
  - One 8-token window is 14–16 % cheaper than two 4-token windows.
- **c) Merged windows:** a window with half of its tokens from each of two unrelated conversations needs **+17–18 %**
  more distinct CPU experts than a same-conversation window of the same size. It needs 7–10 % fewer than two separate
  half windows.
- **d) Code reading:**
  - The engine holds one sequence, one window, one drafter, one stop flag and one error string.
  - The chat cache time-multiplexes conversations between turns.
  - **The server already frees the engine between tool rounds.**
- **e) Two web-search agents, with the chat cache on:**
  - Overlapped through the queue: **+46 %** and +5 % total throughput in two runs; the gain follows the tool time
    there is to hide.
  - Each agent gets slower, and its first-token latency rises to ~3 s.
  - Peak memory is unchanged.
- **Biggest remaining unknown:** whether one host thread and one CPU pool can drive two windows without adding serial
  host time.

**Mistakes (caught):**
- A soak waiter that matched itself (~23 min idle).
- A round-trip config without the static expert set (invalid run, redone).
- A reproduction script that could not trigger the bug.
- The first oracle design (greedy replay; the GPU waiting for every copy), redesigned.
- Found from Round 6: its browser test had set C\*6's shared chat temperature to 0.6. Your 1.0 was restored before any
  promotion.

**Round 8 backlog:**
1. Batched draft-layer prompt pass with KV streaming (≤ 0.69 s per long prompt).
2. Prompt MMQ via a pointer table.
3. Underfilled prompt MMQ.
4. Deterministic draft-policy switch.
5. Warming with a better predictor (only if one appears).

Next-layer staging is dropped.

Full details: REPORT.md "Round 7"; day log: NOTES.md "ROUND 7"; data: `results/r7/`.
