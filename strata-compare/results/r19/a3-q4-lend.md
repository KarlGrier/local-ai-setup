# r19 — #1683 on stock v0.1.42 (STRATA_ROUTE_TAIL_SKIP=0): UD-Q4_K_XL, RAM budget 72 / --resident-experts / budget 66

| arm | RAM copy (engine) | lent slots' experts in RAM | prompt | read tokens | prompt ms | prompt tok/s | TTFT s | drive GB during the request | decode tok/s | MemAvailable after (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| b72 | 64.00 GiB | 0 of 2225 | did not run | | | | | | | |
| res | – | – | did not run | | | | | | | |
| b66 | 64.00 GiB | 0 of 2225 | did not run | | | | | | | |

Lowest MemAvailable over each server's whole run (memory guard, GiB): b72 17.3, b66 17.7

b72 start lines:
```
[strata] 2026-10-10 15:53:42 engine started: /home/USER/ai-speed-testing/strata-compare/tmp/r19/engine-v42-kq/strata --serve --pack /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/pack --native /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf --ple-
strata generate: profile /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/strata-stock/data/expert-profile.bin: 24576 ranked pairs, built for 24576 slots
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
strata generate: expert cache auto: 8.63 GiB free, 813 MiB reserved (+110 MiB for the draft head) -> 2078 slots
strata generate: expert cache 2651 slots, 7.73 GiB of VRAM; policy is
strata generate: pre-filled 2651 of 2651 slots from the profile in 3.4 s (2423 MB/s); slot 0 verified
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 2651 resident experts, decided on the device
FileExpertSource: RAM budget 72.00 GiB: 21925 of the 64.00 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: allocating 64.00 GiB page-locked cache complement
FileExpertSource: mapped pinned cache complement ready: resident 64.00 GiB, pinned 64.00 GiB in 15 s; page-locked and mapped
strata generate: WARNING: a prompt chunk of 16384 tokens lends 2225 cache slots to the prompt path, but only 0 of their experts fit in RAM: the others are read from the SSD on every chunk, and prompts can read ~3x slower than with --prefill auto (#669). A smaller --prefill, or auto, keeps them all in RAM
strata generate: resident RAM mode: 64.00 GiB of experts in RAM (page-locked), 2651 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
prefill: the CPU share is ON by default for prompt chunks below 1024 tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004). STRATA_PREFILL_CPU_SHARE=0 turns it off.
strata serve: the prompt path borrows 2225 CUDA0 cache slots (6.49 GiB)
```

b66 start lines:
```
[strata] 2026-10-10 15:54:09 engine started: /home/USER/ai-speed-testing/strata-compare/tmp/r19/engine-v42-kq/strata --serve --pack /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/pack --native /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf --ple-
strata generate: profile /home/USER/ai-speed-testing/strata-compare/bringup/out/r16q4/strata-stock/data/expert-profile.bin: 24576 ranked pairs, built for 24576 slots
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
strata generate: expert cache auto: 8.63 GiB free, 813 MiB reserved (+110 MiB for the draft head) -> 2078 slots
strata generate: expert cache 2651 slots, 7.73 GiB of VRAM; policy is
strata generate: pre-filled 2651 of 2651 slots from the profile in 3.3 s (2501 MB/s); slot 0 verified
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 2651 resident experts, decided on the device
FileExpertSource: RAM budget 66.00 GiB: 21925 of the 64.00 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: allocating 64.00 GiB page-locked cache complement
FileExpertSource: mapped pinned cache complement ready: resident 64.00 GiB, pinned 64.00 GiB in 15 s; page-locked and mapped
strata generate: WARNING: a prompt chunk of 16384 tokens lends 2225 cache slots to the prompt path, but only 0 of their experts fit in RAM: the others are read from the SSD on every chunk, and prompts can read ~3x slower than with --prefill auto (#669). A smaller --prefill, or auto, keeps them all in RAM
strata generate: resident RAM mode: 64.00 GiB of experts in RAM (page-locked), 2651 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
strata generate: the file tier reads unbuffered (STRATA_UNBUFFERED_LOAD=1)
prefill: the CPU share is ON by default for prompt chunks below 1024 tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004). STRATA_PREFILL_CPU_SHARE=0 turns it off.
strata serve: the prompt path borrows 2225 CUDA0 cache slots (6.49 GiB)
```
