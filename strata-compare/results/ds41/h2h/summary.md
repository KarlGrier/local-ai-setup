# Maya v1.1.28 vs our tuned Strata (v026) - head-to-head, 2026-10-26

Ship config: `{"order": "rev", "DS4_SPLIT": "10,30", "DS4_SETTLE_MS": 0, "DS4_CACHE_DECAY": "0.8", "DS4_ENGRAM_CACHE_MB": 16}`. Build: 2026-10-26 07:16:29 in 2 min. Effort 62 (= medium) for every arm; T 1.0 / 0.95 / 20 / min-p 0.05.

Maya's memory: --mmap-experts off with the copy capped at 50 GB (DS4_COPY_GB) after the first try - Maya's default (in place through the page cache) swapped its own engine memory: M1 1,089 MB (P4K 399.2, P20K 693.2 before it), M2 544 MB (P4K 480.5, P20K 899.5); S2 failed on 1 MB of swap-ins (the guard then had no volume floor); the first S1 (27.64 / 308.2 / 514.1) fails the new guard's later-burst rule (12 MB).
Maya check: Maya check: GUARD: failed: memory - the engine's own memory was swapped (VmSwap 166932 kB) engine swap max 166932 kB, decode None (the 50 GB copy) - Maya counted as failed on this PC

| Arm | decode tok/s | P4K tok/s | P20K tok/s | drive GB/token | P20K drive GB | VRAM experts | lowest MemAvail | drive temp |
|---|---|---|---|---|---|---|---|---|
| S1 | None | None | None | None | None | None | None |  |
| M1 | None | None | None | None | None | None | None |  |
| S2 | None | None | None | None | None | None | None |  |
| M2 | None | None | None | None | None | None | None |  |
| S3 | None | None | None | None | None | None | None |  |

A/B/A (compare.py: gain vs noise):

Follow-ups (Jan's format; read = tokens the engine read for the follow-up, target = last answer + new message):
- S (the round's test-ckpt-v026-keep0): D, TTFT 19.63 s notools F5 (cap 512): prompt 7987 (server 7987), passes [[7987, 7864, 123]] (prompt, reused, read); after a normal answer (1 pass): shared 7864 of the previous 7865, history matches, expected checkpoints {'ck0': 7865, 'ck1': 7864}, went back to 7864, read 123 (target 123) -> ok, TTFT 4.02 s follow-up reads (slot keep off): FAIL - 6 of 12 read only the last answer + the new message; after a budget-hit answer (2 passes): 0/6 ok, read 7692 (target 140), TTFT 19.47 s; after a normal answer (1 pass): 6/6 ok, read 250 (target 250), TTFT 4.84 s; render mismatches 0, history differs 0 

Quality (teacher-forced KL, 8 x 256 positions after a 12,000-token prefix, vs the round's reference config):
- S: None
- M1: None
- M2: None

Pinpoint (report only, before the head-to-head): rc 0: Moves the percentiles most: **pin2-placement** (+ GPU order and layer split): against the step before, p90 0.01299, mean 0.00771. - results/ds41/tuning/pinpoint.md

Decision rule (maya-catchup.md): switch only if Maya is ahead beyond noise on decode and prompts with no quality loss and our clients work (Jan tool calls, deep research, /v1/responses, numeric effort); otherwise port the list. The user decides.
