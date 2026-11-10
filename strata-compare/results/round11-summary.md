# Round 11 — summary (live; updated after every phase)

**Status (10-05 10:40) — Round 11 is done. C\*13 is promoted and running on 8080.**

1. **C\*13 = Strata v0.1.39 + 37 patches**: research decode **+12 %**, decode screen +13 %, fresh holdouts **+9.4 % / +10.5 %**, total time −7…−10 %; prompt times unchanged.
2. Every gate passed: exact checks, quality, needles, Stop, server tests, the browser test, **2-hour soak (440 requests, 0 errors, no slowdown)**, real rollback test.
3. Five upstream bug fixes included (#550 stale residency table, #652 follow-up re-reads, #454 stop strings ignored, #700 tool-tag 400s, #567 prompt re-encoding).
4. Dropped after measurement: upstream's **--remote-expert-opt (−18 % here: keep it out of setup)**, peer mode (−15 %), #693 (lost a follow-up's checkpoint), the drafter port, helper caps, all precision options.
5. Rollback: stop 8080, then `STRATA_CONFIG=configs/Cstar121.json ./switch-model.sh strata`. Optional 262K config: `configs/Cstar13-262k.json`. A 48-hour monitor is running.

Full write-up: REPORT.md "Round 11"; PR drafts 41–46 in pr-drafts/; patches in patches/r11c39/.

## Start of round
- 48-hour uptime monitor stopped after 3 h 22 min: 14 samples, health ok, one server process (C\*12.1) throughout.
  11 of your requests (one 30,158-token answer at 117 tok/s; an LDR-shaped conversation growing to 18K tokens,
  110–133 tok/s). MemAvailable 36 → 33 GiB after them, 5080 480–504 MiB free.
- Release watcher restarted (every 40 min). **Newest release = v0.1.38 = our base** → nothing to port yet.

## Phase verdicts
| phase | kept | not kept | state |
|---|---|---|---|
| 0 base / profile / fixes | **#550, #652, #454 (stop), #700** — correctness fixes, no speed cost; **#567** (TTFT −31 % / −61 % on cached 31K / 98K turns, 0 id differences in 28.5 M tokens) | – | **done** |
| 0.1 release v0.1.39 (07:34) | **adopted as the new base**: computes exactly what C\*12.1 computes, all gates pass, decode LDR +0.8 % / decode screen +2.1 % / full screen +3.0 %, TTFT equal | – | done (10:50) |
| A CPU path | **A.2** (the GPU writes the CPU pool's quantized inputs): exact, every verify round 1.3 % shorter, decode +1.4 % (research) / +1.8 % (decode screen) | IQ gather (no gain), IQ prefetch (no effect), huge pages (no effect; 0.1.39 default anyway), helper-late (noise; one clean re-check queued); A.3–A.5 not needed per the profile | **done** |
| B GPU critical path | **B.1** fork's hyper-connection read (decode +2.3 / +2.7 %), **B.2** split decode attention (+4.3 % research, decode after 32K / 120K +6.5 / +3.5 %), **B.3** faster matvec, exact (+1.0 / +1.6 %); A.2 re-confirmed | B.4 drafter (noise; one part not exact as ported), helper-late (noise) | **done**; combined build being measured |
| C helper balance | – (your 3300 helper slots stays best: 2400 −3.9 %, 1500 −7.3 %, 3500 +0.8 % = noise) | per-layer helper cap (−6 … −13 %); **upstream's --remote-expert-opt (#578): −17.9 %**; upstream's peer mode: −14.7 % decode, prompts 4–7 % slower | **done** (nothing new kept) |
| D prompts / 262K | **262K context works** (200K / 250K prompts in 51 / 65 s, needles 8/8 at 200K/250K, a 190K chat restored from the chat cache in 0.12 s; costs 118 GPU expert slots and +1.5 GiB RAM; optional config). #547 / #603 are in 0.1.39 already | **#693 equal prompt chunks — dropped in Phase G**: faster on fresh long prompts (up to −12 %) but it removes the 16K mid-prompt checkpoint, so a research follow-up re-read its whole 22K prompt (1.7 → 5.2 s); `--prefill auto:32768` (~1 % at 64K+, not worth it) | **done** |
| E higher precision | – | FP8 n-gram table, rotated KV, RoPE table, BF16 embedding, prompt BF16x2: **none improves accuracy measurably** (short texts all within ±0.0025 nats; BF16 embedding and FP8 table lean worse on long texts; BF16x2 also +10 % TTFT at 120K) | **done** (none adopted) |
| F Signal | Q6_K embedding dequantizer (bit-exact): **Signal AP-Q4_K_XL now loads** | Signal decodes at 70.5 vs IQ3_S 130.9 tok/s here (same acceptance, same answer lengths) | **done** |
| G integrate | **C\*13** = v0.1.39 + Phase 0 fixes (#550, #652, #454, #700, #567) + A.2 + B.1 + B.2 + B.3. vs C\*12.1: research decode **+11.9 %**, decode screen **+12.6 %**, full **+10.2 %**, fresh general holdout **+9.4 %**, fresh LDR holdout **+10.5 %**; total time −7…−10 %; prompts unchanged; every gate passed | #693 (lost the follow-up checkpoint), --prefill auto:32768 | **promoted 10:36** (soak 440 requests 0 errors, soaked vs fresh −0.5 % = no slowdown, rollback test passed) |

## Phase 0 profile (C\*12.1 as served, ms per window)
**Biggest finding: the desktop on the 4060 Ti.** Your monitor runs on the helper GPU; while the screen redraws, the
helper's per-layer work waits for the desktop's drawing. Same build, same requests — desktop busy (22–34 % of the
4060 Ti): LDR decode ~103 tok/s, host waits for the helper 2.9 ms per window; desktop quiet: ~124 tok/s, 0.6 ms.
The redraws followed Chrome's GPU process (not only my terminal); since 04:29 the desktop has been quiet (0 %) in
every measured run, and each table records it. For your daily use: plugging the monitor into the motherboard (iGPU) output would remove this
cost (up to ~17 % on research traffic) — your call, nothing changed.

| part (quiet desktop) | LDR | math | code |
|---|---|---|---|
| window | 18.54 | 16.86 | 15.58 |
| GPU: wait for the CPU | 4.08 | 2.94 | 2.84 |
| GPU: hyper-connection reads / GDN / QSA / VRAM experts | 3.03 / 2.65 / 1.95 / 2.39 | 3.02 / 2.63 / 1.71 / 2.52 | 2.76 / 2.50 / 1.61 / 2.08 |
| GPU: plan wait | 0.32 | 0.31 | 0.30 |
| CPU pool: gate/up rows | 3.24 | 2.52 | 2.22 |
| CPU pool: middle quantization | 0.04 | 0.03 | 0.03 |
| CPU pool: down rows (Q2_0 layers / IQ4_NL layers) | 2.12 (0.28 / 1.84) | 1.66 | 1.44 |
| host: input quantization / plan + dispatch / helper launch | 0.29 / 0.15 / 0.45 | 0.28 / 0.14 / 0.42 | 0.22 / 0.12 / 0.41 |
| host: wait for the helper (quiet / busy desktop) | 0.63 / 2.92 | 0.68 | 0.82 |
| draft round | 1.80 | 1.49 | 1.29 |

The CPU pool is memory-bound: gate/up reads ~240 MB per window at ~74 GB/s (the DRAM limit). ~87 % of CPU experts
get one token per window. → Phase A: #650 huge pages, d9ce223 (input quantization 0.29), the GPU hit plan (plan wait
0.32), the IQ_GATHER / IQ_PREFETCH switches (only the multi-token share); **A.3 (Q2_0 down) skipped — only 0.28 ms**;
**#500 skipped — the middle quantization is 0.04 ms (< 0.1)**.
