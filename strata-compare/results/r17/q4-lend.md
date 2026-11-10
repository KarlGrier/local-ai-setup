# r17 — UD-Q4_K_XL on stock v0.1.41: RAM budget vs --resident-experts (A B B A, fresh server each)

| arm | prompt | read tokens | prompt ms | prompt tok/s | TTFT s | drive GB during the request | decode tok/s | MemAvailable after (MiB) |
|---|---|---|---|---|---|---|---|---|
| budget-a | 32K r0 | 32768 | 11615.3 | 2821.1 | 11.661 | 28.82 | 64.0 | 17187 |
| budget-a | 32K r1 | 32774 | 11525.0 | 2843.7 | 11.571 | 29.17 | 68.4 | 17009 |
| resident-a | 32K r0 | 32768 | 9142.3 | 3584.2 | 9.368 | 1.22 | 66.6 | 12783 |
| resident-a | 32K r1 | 32774 | 9502.8 | 3448.9 | 9.581 | 1.19 | 69.6 | 12590 |
| resident-b | 32K r0 | 32768 | 9166.9 | 3574.6 | 9.395 | 1.22 | 70.0 | 12897 |
| resident-b | 32K r1 | 32774 | 9493.2 | 3452.4 | 9.578 | 1.19 | 71.1 | 12815 |
| budget-b | 32K r0 | 32768 | 12028.1 | 2724.3 | 12.074 | 28.82 | 63.4 | 17263 |
| budget-b | 32K r1 | 32774 | 11867.5 | 2761.7 | 11.914 | 29.17 | 61.0 | 17071 |

budget-a start lines:
```
[strata] 2026-10-09 01:19:11 engine started: /home/USER/ai-speed-testing/strata-compare/work/r17/engine-stock-kq/strata --serve --pack /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/pack --native /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf --p
strata generate: profile /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/strata-stock/data/expert-profile.bin: 24576 ranked pairs, built for 24576 slots
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
strata generate: expert cache auto: 8.63 GiB free, 813 MiB reserved (+110 MiB for the draft head) -> 2078 slots
strata generate: expert cache 2651 slots, 7.73 GiB of VRAM; policy is
strata generate: pre-filled 2651 of 2651 slots from the profile in 3.3 s (2532 MB/s); slot 0 verified
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 2651 resident experts, decided on the device
FileExpertSource: RAM budget 66.00 GiB: 21925 of the 64.00 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: allocating 64.00 GiB page-locked cache complement
FileExpertSource: 60.27 GiB really free for a 64.00 GiB page-locked complement; the model files' cached pages were released: 64.53 GiB free
FileExpertSource: the rest comes from reclaimed cache of other files: page-locking it in steps, as far as the RAM allows (#1250)
FileExpertSource: mapped pinned cache complement ready: resident 64.00 GiB, pinned 64.00 GiB in 18 s; 64.00 GiB page-locked after taking the pages in steps; 
strata generate: WARNING: a prompt chunk of 16384 tokens lends 2225 cache slots to the prompt path, but only 0 of their experts fit in RAM: the others are read from the SSD on every chunk, and prompts can read ~3x slower than with --prefill auto (#669). A smaller --prefill, or auto, keeps them all in RAM
strata generate: resident RAM mode: 64.00 GiB of experts in RAM (page-locked), 2651 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
prefill: the CPU share is ON by default for prompt chunks below 1024 tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004). STRATA_PREFILL_CPU_SHARE=0 turns it off.
strata serve: the prompt path borrows 2225 CUDA0 cache slots (6.49 GiB)
strata serve: 491 MiB of VRAM free with everything loaded
strata verify: capturing the 4-token window (469 MiB of VRAM free)
strata verify: capturing the 1-token window (465 MiB of VRAM free)
strata verify: capturing the 3-token window (455 MiB of VRAM free)
strata verify: capturing the 6-token window (451 MiB of VRAM free)
strata verify: capturing the 5-token window (445 MiB of VRAM free)
strata verify: c```

resident-a start lines:
```
[strata] 2026-10-09 01:20:46 engine started: /home/USER/ai-speed-testing/strata-compare/work/r17/engine-stock-kq/strata --serve --pack /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/pack --native /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf --p
strata generate: profile /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/strata-stock/data/expert-profile.bin: 24576 ranked pairs, built for 24576 slots
strata generate: the file tier reads through the file cache (STRATA_UNBUFFERED_LOAD=1 ignored: without --resident-budget-gib the file cache holds the experts)
strata generate: expert cache auto: 8.63 GiB free, 813 MiB reserved (+110 MiB for the draft head) -> 2078 slots
strata generate: expert cache 2651 slots, 7.73 GiB of VRAM; policy is
strata generate: pre-filled 2651 of 2651 slots from the profile in 1.5 s (5611 MB/s); slot 0 verified
strata generate: routing-aware prefetch on (the next layer's router, file tier)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 2651 resident experts, decided on the device
FileExpertSource: allocating 70.49 GiB page-locked cache complement
FileExpertSource: 57.14 GiB really free for a 70.49 GiB page-locked complement; the model files' cached pages were released: 68.97 GiB free
FileExpertSource: the rest comes from reclaimed cache of other files: page-locking it in steps, as far as the RAM allows (#1250)
FileExpertSource: mapped pinned cache complement ready: resident 70.49 GiB, pinned 70.49 GiB in 59 s; 70.49 GiB page-locked after taking the pages in steps; 
FileExpertSource: 2225 of the prompt path's 2225 lendable slots keep their experts in RAM too
strata generate: resident RAM mode: 70.49 GiB of experts in RAM (page-locked), 2651 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
prefill: the CPU share is ON by default for prompt chunks below 1024 tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004). STRATA_PREFILL_CPU_SHARE=0 turns it off.
strata serve: the prompt path borrows 2225 CUDA0 cache slots (6.49 GiB)
strata serve: 477 MiB of VRAM free with everything loaded
strata verify: capturing the 4-token window (461 MiB of VRAM free)
strata verify: capturing the 1-token window (457 MiB of VRAM free)
strata verify: capturing the 3-token window (447 MiB of VRAM free)
strata verify: capturing the 2-token window (443 MiB of VRAM free)
strata verify: capturing the 6-token window (437 MiB of VRAM free)
strata serve: decode expert cache hit rate: 53.1% (60938 hits / 114720 lookups)
strata serve: resident RAM: 70.49 GiB of experts in RAM, 221 exchanged with the VRAM tier, 0 blob reads from the file
strata serve: file tier I/O this request: the OS read 143927.7 MB from storage (199702 major f```
