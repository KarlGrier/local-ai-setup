# r19 — #1683 on stock v0.1.42 (STRATA_ROUTE_TAIL_SKIP=0): UD-Q4_K_XL, RAM budget 72 / --resident-experts / budget 66

| arm | RAM copy (engine) | lent slots' experts in RAM | prompt | read tokens | prompt ms | prompt tok/s | TTFT s | drive GB during the request | decode tok/s | MemAvailable after (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| b72 | 63.95 GiB | 0 of 2258 | 32K r0 | 32768 | 11314.9 | 2896.0 | 11.361 | 29.01 | 64.4 | 17380 |
| b72 | 63.95 GiB | 0 of 2258 | 32K r1 | 32774 | 11213.9 | 2922.6 | 11.261 | 28.92 | 66.3 | 17361 |
| res | 70.53 GiB | 2258 of 2258 | 32K r0 | 32768 | 8944.6 | 3663.4 | 9.159 | 1.22 | 68.4 | 13138 |
| res | 70.53 GiB | 2258 of 2258 | 32K r1 | 32774 | 8753.3 | 3744.2 | 8.836 | 1.19 | 71.4 | 13103 |
| b66 | 63.95 GiB | 0 of 2258 | 32K r0 | 32768 | 11319.1 | 2894.9 | 11.366 | 29.0 | 65.4 | 17599 |
| b66 | 63.95 GiB | 0 of 2258 | 32K r1 | 32774 | 11217.4 | 2921.7 | 11.262 | 28.91 | 64.5 | 17518 |

Lowest MemAvailable over each server's whole run (memory guard, GiB): b72 16.9, res 12.8, b66 17.1

b72 start lines:
```
[strata] 2026-10-11 01:28:11 engine started: /home/USER/ai-speed-testing/strata-compare/tmp/r19/engine-v42-kq/strata --serve --pack /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/pack --native /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf --ple-
strata generate: profile /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/strata-stock/data/expert-profile.bin: 24576 ranked pairs, built for 24576 slots
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
strata generate: expert cache auto: 8.68 GiB free, 813 MiB reserved (+110 MiB for the draft head) -> 2092 slots
strata generate: expert cache 2669 slots, 7.78 GiB of VRAM; policy is
strata generate: pre-filled 2669 of 2669 slots from the profile in 3.4 s (2461 MB/s); slot 0 verified
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 2669 resident experts, decided on the device
FileExpertSource: RAM budget 72.00 GiB: 21907 of the 63.95 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: allocating 63.95 GiB page-locked cache complement
FileExpertSource: mapped pinned cache complement ready: resident 63.95 GiB, pinned 63.95 GiB in 15 s; page-locked and mapped
strata generate: WARNING: a prompt chunk of 16384 tokens lends 2258 cache slots to the prompt path, but only 0 of their experts fit in RAM: the others are read from the SSD on every chunk, and prompts can read ~3x slower than with --prefill auto (#669). A smaller --prefill, or auto, keeps them all in RAM
strata generate: resident RAM mode: 63.95 GiB of experts in RAM (page-locked), 2669 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
prefill: the CPU share is ON by default for prompt chunks below 1024 tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004). STRATA_PREFILL_CPU_SHARE=0 turns it off.
strata serve: the prompt path borrows 2258 CUDA0 cache slots (6.59 GiB)
strata serve: 490 MiB of VRAM free with everything loaded
strata verify: capturing the 4-token window (474 MiB of VRAM free)
strata verify: capturing the 1-token window (468 MiB of VRAM free)
strata verify: capturing the 3-token window (460 MiB of VRAM free)
strata verify: capturing the 2-token window (456 MiB of VRAM free)
strata serve: decode expert cache hit rate: 52.3% (55729 hits / 106560 lookups)
strata serve: resident RAM: 63.95 GiB of experts in RAM, 1824 exchanged with the VRAM tier, 357 blob reads from the file
strata serve: file tier I/O this request: the OS read 85032.6 MB from storage (504 major faults) for 10186.4 MB of expert reads
strata verify: capturing the 6-token window (450 MiB of VRAM free)
strata serve: decode expert cache hit rate: 62.7% (70469 hits / 112320 lookups)
strata serve: resident RAM: 63.95 GiB of experts in RAM, 3840 exchanged with the VRAM tier, 2615 blob reads from the file
strata serve: file tier I/O this request: the OS read 29008.3 MB from storage (16 major faults) for 27694.6 MB of expert reads
strata serve: decode expert cache hit rate: 61.2% (55263 hits / 90240 lookups)
strata serve: resident RAM: 63.95 GiB of experts in RAM, 5376 exchanged with the ```

res start lines:
```
[strata] 2026-10-11 01:29:41 engine started: /home/USER/ai-speed-testing/strata-compare/tmp/r19/engine-v42-kq/strata --serve --pack /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/pack --native /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf --ple-
strata generate: profile /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/strata-stock/data/expert-profile.bin: 24576 ranked pairs, built for 24576 slots
strata generate: the file tier reads through the file cache (STRATA_UNBUFFERED_LOAD=1 ignored: without --resident-budget-gib the file cache holds the experts)
strata generate: expert cache auto: 8.68 GiB free, 813 MiB reserved (+110 MiB for the draft head) -> 2092 slots
strata generate: expert cache 2669 slots, 7.78 GiB of VRAM; policy is
strata generate: pre-filled 2669 of 2669 slots from the profile in 1.5 s (5526 MB/s); slot 0 verified
strata generate: routing-aware prefetch on (the next layer's router, file tier)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 2669 resident experts, decided on the device
FileExpertSource: allocating 70.53 GiB page-locked cache complement
FileExpertSource: 65.24 GiB really free for a 70.53 GiB page-locked complement; the model files' cached pages were released: 77.27 GiB free
FileExpertSource: mapped pinned cache complement ready: resident 70.53 GiB, pinned 70.53 GiB in 70 s; page-locked and mapped
FileExpertSource: 2258 of the prompt path's 2258 lendable slots keep their experts in RAM too
strata generate: resident RAM mode: 70.53 GiB of experts in RAM (page-locked), 2669 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
prefill: the CPU share is ON by default for prompt chunks below 1024 tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004). STRATA_PREFILL_CPU_SHARE=0 turns it off.
strata serve: the prompt path borrows 2258 CUDA0 cache slots (6.59 GiB)
strata serve: 476 MiB of VRAM free with everything loaded
strata verify: capturing the 4-token window (460 MiB of VRAM free)
strata verify: capturing the 1-token window (454 MiB of VRAM free)
strata verify: capturing the 3-token window (446 MiB of VRAM free)
strata verify: capturing the 6-token window (442 MiB of VRAM free)
strata verify: capturing the 5-token window (436 MiB of VRAM free)
strata verify: capturing the 2-token window (432 MiB of VRAM free)
strata serve: decode expert cache hit rate: 48.6% (62963 hits / 129600 lookups)
strata serve: resident RAM: 70.53 GiB of experts in RAM, 218 exchanged with the VRAM tier, 0 blob reads from the file
strata serve: file tier I/O this request: the OS read 121066.5 MB from storage (123745 major faults) for 8357.0 MB of expert reads
strata serve: decode expert cache hit rate: 62.2% (66865 hits / 107520 lookups)
strata serve: resident RAM: 70.53 GiB of experts in RAM, 418 exchanged with the VRAM tier, 0 blob reads from the file
strata serve: file tier I/O this request: the OS read 1222.0 MB from storage (9787 major faults) for 0.0 MB of expert reads
strata serve: decode expert cache hit rate: 61.5% (55197 hits / 89760 lookups)
strata serve: resident RAM: 70.53 GiB of experts in RAM, 572 exchanged with the VRAM tier, 0 blob reads from the file
strata serve: file tier I/O this reques```

b66 start lines:
```
[strata] 2026-10-11 01:32:03 engine started: /home/USER/ai-speed-testing/strata-compare/tmp/r19/engine-v42-kq/strata --serve --pack /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/pack --native /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf --ple-
strata generate: profile /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/strata-stock/data/expert-profile.bin: 24576 ranked pairs, built for 24576 slots
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
strata generate: expert cache auto: 8.68 GiB free, 813 MiB reserved (+110 MiB for the draft head) -> 2092 slots
strata generate: expert cache 2669 slots, 7.78 GiB of VRAM; policy is
strata generate: pre-filled 2669 of 2669 slots from the profile in 3.2 s (2584 MB/s); slot 0 verified
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 2669 resident experts, decided on the device
FileExpertSource: RAM budget 66.00 GiB: 21907 of the 63.95 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: allocating 63.95 GiB page-locked cache complement
FileExpertSource: mapped pinned cache complement ready: resident 63.95 GiB, pinned 63.95 GiB in 14 s; page-locked and mapped
strata generate: WARNING: a prompt chunk of 16384 tokens lends 2258 cache slots to the prompt path, but only 0 of their experts fit in RAM: the others are read from the SSD on every chunk, and prompts can read ~3x slower than with --prefill auto (#669). A smaller --prefill, or auto, keeps them all in RAM
strata generate: resident RAM mode: 63.95 GiB of experts in RAM (page-locked), 2669 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
prefill: the CPU share is ON by default for prompt chunks below 1024 tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004). STRATA_PREFILL_CPU_SHARE=0 turns it off.
strata serve: the prompt path borrows 2258 CUDA0 cache slots (6.59 GiB)
strata serve: 490 MiB of VRAM free with everything loaded
strata verify: capturing the 4-token window (474 MiB of VRAM free)
strata verify: capturing the 1-token window (468 MiB of VRAM free)
strata verify: capturing the 5-token window (460 MiB of VRAM free)
strata verify: capturing the 2-token window (456 MiB of VRAM free)
strata verify: capturing the 3-token window (450 MiB of VRAM free)
strata serve: decode expert cache hit rate: 54.0% (60679 hits / 112320 lookups)
strata serve: resident RAM: 63.95 GiB of experts in RAM, 2016 exchanged with the VRAM tier, 357 blob reads from the file
strata serve: file tier I/O this request: the OS read 86067.7 MB from storage (4467 major faults) for 10183.4 MB of expert reads
strata serve: decode expert cache hit rate: 62.1% (62919 hits / 101280 lookups)
strata serve: resident RAM: 63.95 GiB of experts in RAM, 3840 exchanged with the VRAM tier, 2615 blob reads from the file
strata serve: file tier I/O this request: the OS read 28995.1 MB from storage (0 major faults) for 27683.2 MB of expert reads
strata serve: decode expert cache hit rate: 61.7% (66333 hits / 107520 lookups)
strata serve: resident RAM: 63.95 GiB of experts in RAM, 5664 exchanged with the```
