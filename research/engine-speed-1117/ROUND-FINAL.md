# Engine-speed round r24: final report (2026-11-11 to 11-18)

The round is closed. This file ends it. `ROUND-RESULTS.md` (11-17) has the measurement picture and the first results,
and `IDEAS-COVERED.md` has every idea's final status. All numbers come from this box, with the served model, the served
switches and the standard sampling.

## 1. What was tested

**15 measurement gaps:**
- A1 (baseline diagnostic);
- A2 (QIL, HC_PERSIST);
- A3 / A3c / A3p / GBAL (PCIe share variants);
- A4 (CPU pool layout);
- A5 (SPEC_COST);
- B1 (routing-trace capture, 102,190 windows);
- X9 (GPU deadline map);
- C256 (256K context);
- X14ref (second-PC kernel harness);
- BV (block-verification capture);
- X11S (one-layer-ahead staging, stage 1);
- FE (early PCIe copy).

**About 20 desk studies:** the A0 code checks; X1-X4; X7 / X12; X10 / C1 replays; X11's bounds and predictors; CPU
kernels; base drift; block verification and token-recycling sizing; the copy-engine check; Phase D (D1-D3); and X13.

**The test rules:**
- correctness contracts first: exact7, long40, KL bands, the sampled-distribution test, live admission read-backs;
- speed on the acceptance-adjusted metric (see `ROUND-RESULTS.md` section 3);
- a build needs about +3 % predicted end-to-end.

## 2. Results since `ROUND-RESULTS.md`

| item | result | the number that decides it |
|---|---|---|
| Block verification of the MTP chain | dropped | +0.175 % committed tokens per window (95 %: +0.11 to +0.22 %) from a full capture of the drafter's q and the target's top-64 rows. The prediction matched observed acceptance at every depth within 0.5 points |
| Token recycling (reuse the target's past distributions as the first draft) | dropped | Even an oracle replay gains +0.062 commits per window, under the 0.12 hurdle. The MTP drafter already puts 80 % of its first draft on the target's mass |
| X11 one-layer-ahead staging, stage 1 | dropped | Measured costs: router pass +0.74 %, shadow copies +11.95 %. The copies cut the CPU pool's DRAM rate by about 12 % (54.8 -> 47.8 GB/s). Realistic net: -3.1 % end-to-end |
| Faster CPU expert kernels | dropped | Still 2.7-2.9 % at most, with X11 gone |
| Early PCIe copy on a branch stream (FE) | parked | Byte-identical (exact7 7/7; 241 M admitted slots read back, 0 differ). +1.3 % adjusted (default grid), +2.6 % (84-block grid, a guard tripped); -1.3 to -1.7 % ms per window at fixed work. Under +3 % for new code |
| Copy-engine variant of the early copy | parked | The PCIe share controller reads only the start-up link probe and the CPU pool's time per expert, so a hidden copy cannot move the share. FE's one share move came from the pool slowing down |
| QSA_ROWS on the 5080 | dropped this round | Expected at most ~1 %. Its only bench faults at contexts under 32,768 cells (reported upstream: Niko1221/Strata#6209) |
| Two column groups per window (D1) | dropped | Central +0.1 %: the GPU is already ~95 % busy in a window, and a second group adds a 101-112 µs dense pass per layer. It reaches +3.0-4.2 % only with a PCIe copy that costs the GPU ~no compute |
| Exclusive residency for the helper's fixed experts (D2) | parked | Capacity only, decode ~0 %. 6.2 GiB of RAM freeable with a compacted arena (1.0 GiB in place) |
| Lossless compression of expert bytes (D3) | dropped for speed | 400 real blobs, 6 formats: zstd 1.01x, entropy bound 1.04x. CPU decode 2.3 GB/s a core against the pool's 54.8 GB/s. Even free GPU decoding gains +0.07 % |
| Cheaper draft-only drafter (X13) | dropped | Ceiling 2.1 % (central) before any acceptance loss. Drafting is 2.33 of 21.7 ms a window, 205 MiB read per draft step |

## 3. What was adopted

- **256K context** (`--max-context 262144`), at -0.63 % short decode.
- **The measurement methods:**
  - the acceptance-adjusted metric with its two guards;
  - fixed-work replays;
  - the routing trace v2 with causal replay;
  - GPU-clock phase stamps (the deadline map);
  - forced-path state fixtures;
  - the live admission read-back as part of a byte contract.

No decode-speed switch was adopted. The daily runs as it did when the round started: 167 tok/s on the seeded six, 21 ms
per verify window, 3.5 tokens per window. The round's earlier 2.5-2.7 % "wins" were acceptance luck.

## 4. Lessons for Qwen4

1. **Host DRAM is the shared wall.** The CPU pool streams expert bytes at about 55 GB/s, and anything else that reads
   host memory during the CPU phase slows it:
   - extra link copies: -12 %;
   - an earlier copy of the same bytes: -3 to -4 %.

   Price every new host-to-GPU transfer against the pool, not only against the link.
2. **The GPU has no idle time to give.** In a window it is ~95 % busy (VRAM groups, the PCIe copy, the dense part).
   Ideas that add a GPU pass or SM work need a matching saving on the GPU's own clock.
3. **The PCIe share rule is bandwidth-only.** It balances the link probe against the CPU pool's speed and never sees
   exposed time. A timing-aware rule (one that reads the GPU's wait for CPU rows) is the open lever, about +2.5 % at
   most today.
4. **Judge on adjusted time.** Served outputs differ start to start, and speed follows acceptance (r = 0.984). Raw tok/s
   needs about 40 starts per arm to see 1 %; the adjusted metric sees ~0.7 % at 4 v 4.
5. **Keep experts in the arena mode if at all possible.**
   - The resident-RAM mode for larger models turns off the PCIe-share admissions, which were worth +12.7 % decode.
   - The arena limit is about 58 GiB of experts. Leaving the helper's fixed experts out of RAM (D2) would raise it to
     about 64. That is worth building only if Qwen4's experts land in that band.
6. **Don't count on compressing IQ expert bytes.** They are near-random at 8 bits a byte. Re-run the check on Qwen4's
   real files; it matters only if Qwen4 ships a plain int4-style format.
7. **The drafter is not the place to save.** Drafting is ~11 % of a window, and half of that is fixed launch and sync
   work.
8. **Read an upstream test binary's argument assumptions before pinning non-default arguments.** Its first GPU run is
   inside a gap, and a wild read there is a kernel error that stops the gap.

**On the Qwen4 day-one list from this round:**
- the certified two-pass index selector check (STRATA_SELECT_TWO_PASS_CHECK, then cold 128K / 256K);
- selected-page KV gathering for short warm continuations;
- the compression re-check;
- D2's revisit rule;
- X13's four-number re-check if the MTP layer changes;
- the start-share and exact-T HC items already listed.

## 5. What's next

The next focus is open. `IDEAS-COVERED.md` now lists 228 ideas: 57 adopted, 103 dropped, 8 planned (on the
Qwen4 day-one list) and 60 backlog, the backlog ones with their kill tests.

Measured and drafted with Claude Code.
