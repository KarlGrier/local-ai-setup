| prompt | ours (base) ms | fork + 4060 Ti ms | fork, 5080 alone ms | fork+GPU2 vs ours | fork alone vs ours |
|---|---|---|---|---|---|
| pp4k (4118 tokens) | 1654 / 1647 → **1650** | 8913 / 8911 → **8912** | 1701 / 1749 → **1725** | +440.1 % | +4.5 % |
| pp8k (8042 tokens) | 2620 / 2580 → **2600** | 9873 / 9864 → **9868** | 2637 / 2499 → **2568** | +279.5 % | -1.2 % |
| pp32k (32791 tokens) | 9522 / 9529 → **9525** | 23389 / 23379 → **23384** | 8826 / 8758 → **8792** | +145.5 % | -7.7 % |
| pp120k (122903 tokens) | 33692 / 33696 → **33694** | 83620 / 83583 → **83601** | 31917 / 31908 → **31913** | +148.1 % | -5.3 % |

#### v36 pp4k (Cpp-v36-pp4k-prof.out)
```
verify window            wait for rings 9.442  pool 10.086  host 0.281  commit 0.021 ms/round; CPU experts 5.92 distinct / 7.74 routed per layer
adaptive tier            96 experts swapped into the VRAM tier (every 4 rounds, 0.035 ms/round)
prefill                  4118 tokens in 1731.4 ms  ->  2378.39 tok/s  (time to first token 1831.2 ms)
  per token              9.462 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 66304 rows, 0.3% row-cache hits, 47345 SSD reads (198.1 MB), read p50 191 us p99 468 us, blocked 88.238 ms total (submit 9.608 ms), cache 47522/1048576 rows, SSD kept awake by 16 reads (slowest 0.5 ms)
  CUDA1 experts           1831 routed entries computed
```

#### v36 pp4k (Cpp-v36-pp4k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding IQ4_XS in mapped host memory (322 MiB)
strata generate: KV streaming: 32768 of 131072 cells per QSA layer in VRAM, the K/V in 1.55 GiB of pinned RAM
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 835 MiB of VRAM (experts 675, dense 111), files read in 0.13 s (6139 MiB/s)
strata generate: the GPU computes the experts in the cache; it rounds differently from the CPU,
strata generate: CUDA1: 3300 additional experts, 6.21 GiB; results return through pinned host rows
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 4559 resident experts, decided on the device
strata generate: prompt chunk auto: 4352 tokens
strata generate: prompt path borrows 1591 cache slots (3.01 GiB)
strata mtp: EXACT speculative sampling on (STRATA_SPEC_EXACT): sampled requests draft from q (their own chain over 40525 tokens, a proposal stream of its own) and verify by accept / residual / bonus
strata prefill timing: 4118 tokens, GPU timeline 1581 ms, wall 1673 ms, host staging 48 ms: embed+steps 104 (6.6%) hc read 135 (8.5%) gdn 171 (10.8%) qsa proj 83 (5.2%) qsa indexer 0 (0.0%) qsa select 11 (0.7%) qsa attn 68 (4.3%) router+shared 44 (2.8%) host grouping 6 (0.4%) gather 10 (0.6%) wait copy 87 (5.5%) dequant 126 (8.0%) gemm gate/up 324 (20.5%) gemm down 154 (9.8%) combine 57 (3.6%) ple 6 (0.4%) kv stage 0 (0.0%) gdn conv+gates 21 (1.3%) gdn recurrence 99 (6.2%) gdn out proj 75 (4.7%)
strata prefill timing: host: chunk setup (PLE rows, the expert stream plan) 103 ms, waiting for each chunk 9 ms, after each chunk (the draft layer, progress) 92 ms, PLE 115 ms; MMQ groups read in place 1481, gathered 0
strata generate: prefill 4118 tokens in 1 chunks, 1673.2 ms (2461.2 tok/s); experts streamed 21608 (21608 by DMA, host 47.7 ms), resident 2933; PLE 114.9 ms
```

#### v36 pp8k (Cpp-v36-pp8k-prof.out)
```
verify window            wait for rings 9.173  pool 9.948  host 0.231  commit 0.019 ms/round; CPU experts 6.01 distinct / 8.18 routed per layer
adaptive tier            96 experts swapped into the VRAM tier (every 4 rounds, 0.031 ms/round)
prefill                  8042 tokens in 2684.0 ms  ->  2996.29 tok/s  (time to first token 2804.4 ms)
  per token              10.628 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 129120 rows, 0.2% row-cache hits, 76031 SSD reads (318.2 MB), read p50 188 us p99 416 us, blocked 132.732 ms total (submit 10.146 ms), cache 76440/1048576 rows, SSD kept awake by 25 reads (slowest 0.6 ms)
  CUDA1 experts           1790 routed entries computed
```

#### v36 pp8k (Cpp-v36-pp8k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding IQ4_XS in mapped host memory (322 MiB)
strata generate: KV streaming: 32768 of 131072 cells per QSA layer in VRAM, the K/V in 1.55 GiB of pinned RAM
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 835 MiB of VRAM (experts 675, dense 111), files read in 0.13 s (6151 MiB/s)
strata generate: the GPU computes the experts in the cache; it rounds differently from the CPU,
strata generate: CUDA1: 3300 additional experts, 6.21 GiB; results return through pinned host rows
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 4559 resident experts, decided on the device
strata generate: prompt chunk auto: 8192 tokens
strata generate: prompt path borrows 2408 cache slots (4.56 GiB)
strata mtp: EXACT speculative sampling on (STRATA_SPEC_EXACT): sampled requests draft from q (their own chain over 40525 tokens, a proposal stream of its own) and verify by accept / residual / bonus
strata prefill timing: 8042 tokens, GPU timeline 2421 ms, wall 2596 ms, host staging 54 ms: embed+steps 169 (7.0%) hc read 237 (9.8%) gdn 278 (11.5%) qsa proj 144 (6.0%) qsa indexer 0 (0.0%) qsa select 31 (1.3%) qsa attn 154 (6.4%) router+shared 70 (2.9%) host grouping 8 (0.3%) gather 22 (0.9%) wait copy 94 (3.9%) dequant 124 (5.1%) gemm gate/up 393 (16.2%) gemm down 206 (8.5%) combine 116 (4.8%) ple 11 (0.5%) kv stage 0 (0.0%) gdn conv+gates 41 (1.7%) gdn recurrence 192 (7.9%) gdn out proj 130 (5.4%)
strata prefill timing: host: chunk setup (PLE rows, the expert stream plan) 167 ms, waiting for each chunk 12 ms, after each chunk (the draft layer, progress) 175 ms, PLE 186 ms; MMQ groups read in place 1527, gathered 0
strata generate: prefill 8042 tokens in 1 chunks, 2595.8 ms (3098.1 tok/s); experts streamed 22425 (22425 by DMA, host 53.9 ms), resident 2124; PLE 185.9 ms
```

#### v36 pp32k (Cpp-v36-pp32k-prof.out)
```
verify window            wait for rings 8.646  pool 10.889  host 0.155  commit 0.018 ms/round; CPU experts 7.08 distinct / 9.61 routed per layer
adaptive tier            192 experts swapped into the VRAM tier (every 4 rounds, 0.051 ms/round)
prefill                  32791 tokens in 10299.7 ms  ->  3183.67 tok/s  (time to first token 10418.3 ms)
  per token              13.478 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 525136 rows, 21.5% row-cache hits, 242009 SSD reads (1012.2 MB), read p50 190 us p99 468 us, blocked 406.879 ms total (submit 19.584 ms), cache 243140/1048576 rows, SSD kept awake by 96 reads (slowest 0.6 ms)
  CUDA1 experts           1812 routed entries computed
```

#### v36 pp32k (Cpp-v36-pp32k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding IQ4_XS in mapped host memory (322 MiB)
strata generate: KV streaming: 32768 of 131072 cells per QSA layer in VRAM, the K/V in 1.55 GiB of pinned RAM
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 835 MiB of VRAM (experts 675, dense 111), files read in 0.13 s (6135 MiB/s)
strata generate: the GPU computes the experts in the cache; it rounds differently from the CPU,
strata generate: CUDA1: 3300 additional experts, 6.21 GiB; results return through pinned host rows
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 4559 resident experts, decided on the device
strata generate: prompt chunk auto: 8192 tokens
strata generate: prompt path borrows 2408 cache slots (4.56 GiB)
strata mtp: EXACT speculative sampling on (STRATA_SPEC_EXACT): sampled requests draft from q (their own chain over 40525 tokens, a proposal stream of its own) and verify by accept / residual / bonus
strata prefill timing: 32791 tokens, GPU timeline 10211 ms, wall 10212 ms, host staging 193 ms: embed+steps 898 (8.8%) hc read 896 (8.8%) gdn 1080 (10.6%) qsa proj 605 (5.9%) qsa indexer 1 (0.0%) qsa select 238 (2.3%) qsa attn 697 (6.8%) router+shared 265 (2.6%) host grouping 36 (0.4%) gather 89 (0.9%) wait copy 444 (4.3%) dequant 549 (5.4%) gemm gate/up 1558 (15.3%) gemm down 832 (8.2%) combine 448 (4.4%) ple 44 (0.4%) kv stage 28 (0.3%) gdn conv+gates 168 (1.6%) gdn recurrence 785 (7.7%) gdn out proj 549 (5.4%)
strata prefill timing: host: chunk setup (PLE rows, the expert stream plan) 169 ms, waiting for each chunk 51 ms, after each chunk (the draft layer, progress) 696 ms, PLE 185 ms; MMQ groups read in place 6089, gathered 265
strata generate: prefill 32791 tokens in 5 chunks, 10211.6 ms (3211.1 tok/s); experts streamed 92790 (92790 by DMA, host 193.1 ms), resident 9145; PLE 185.0 ms
```

#### v36 pp120k (Cpp-v36-pp120k-prof.out)
```
verify window            wait for rings 10.648  pool 12.679  host 0.224  commit 0.019 ms/round; CPU experts 6.96 distinct / 9.40 routed per layer
adaptive tier            96 experts swapped into the VRAM tier (every 4 rounds, 0.033 ms/round)
prefill                  122903 tokens in 36896.4 ms  ->  3331.03 tok/s  (time to first token 37027.1 ms)
  per token              13.132 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 1966976 rows, 35.8% row-cache hits, 743097 SSD reads (3109.5 MB), read p50 190 us p99 452 us, blocked 1248.703 ms total (submit 143.088 ms), cache 712835/1048576 rows, SSD kept awake by 348 reads (slowest 1.0 ms)
  CUDA1 experts           2165 routed entries computed
```

#### v36 pp120k (Cpp-v36-pp120k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding IQ4_XS in mapped host memory (322 MiB)
strata generate: KV streaming: 32768 of 131072 cells per QSA layer in VRAM, the K/V in 1.55 GiB of pinned RAM
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 835 MiB of VRAM (experts 675, dense 111), files read in 0.13 s (6119 MiB/s)
strata generate: the GPU computes the experts in the cache; it rounds differently from the CPU,
strata generate: CUDA1: 3300 additional experts, 6.21 GiB; results return through pinned host rows
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 4559 resident experts, decided on the device
strata generate: prompt chunk auto: 8192 tokens
strata generate: prompt path borrows 2408 cache slots (4.56 GiB)
strata mtp: EXACT speculative sampling on (STRATA_SPEC_EXACT): sampled requests draft from q (their own chain over 40525 tokens, a proposal stream of its own) and verify by accept / residual / bonus
strata prefill timing: 122903 tokens, GPU timeline 36807 ms, wall 36808 ms, host staging 565 ms: embed+steps 986 (2.7%) hc read 3280 (8.9%) gdn 3883 (10.5%) qsa proj 2234 (6.1%) qsa indexer 3 (0.0%) qsa select 2406 (6.5%) qsa attn 2683 (7.3%) router+shared 934 (2.5%) host grouping 130 (0.4%) gather 330 (0.9%) wait copy 1518 (4.1%) dequant 1945 (5.3%) gemm gate/up 5659 (15.4%) gemm down 3085 (8.4%) combine 1684 (4.6%) ple 165 (0.4%) kv stage 281 (0.8%) gdn conv+gates 630 (1.7%) gdn recurrence 2946 (8.0%) gdn out proj 2026 (5.5%)
strata prefill timing: host: chunk setup (PLE rows, the expert stream plan) 178 ms, waiting for each chunk 182 ms, after each chunk (the draft layer, progress) 700 ms, PLE 164 ms; MMQ groups read in place 22820, gathered 265
strata generate: prefill 122903 tokens in 16 chunks, 36808.3 ms (3339.0 tok/s); experts streamed 339489 (339489 by DMA, host 564.6 ms), resident 32172; PLE 164.2 ms
```

#### fk2 pp4k (Cpp-fk2-pp4k-prof.out)
```
verify window            wait for rings 71.292  pool 7.638  host 2.611  commit 0.084 ms/round; CPU experts 3.82 distinct / 4.34 routed per layer
adaptive tier            468 experts swapped in and 0 into empty slots (every 1 rounds, 0.092 ms/round), 96 moves dropped; 110.8 MB/round copied
second GPU               566.86 routed entries and 394.14 experts per round in 47.29 layers (0.71 left to the CPU), its rows after the CPU's in 46.00 layers, 66.037 ms/round; 350 experts swapped in and 0 into empty slots (0 still empty, 123 moves dropped; its copies between windows, 8.83 ms, at 6.4 GB/s); 228.57 experts per round prefetched, 183.29 of them used (0.280 ms/round of host time, 0 predictions waited for)
routing concentration    1000:0.604 2000:0.803 4000:0.991 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 11520 routed entries)
prefill                  4118 tokens in 7784.0 ms  ->  529.04 tok/s  (time to first token 8891.0 ms)
  per token              41.692 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 66288 rows, 0.2% row-cache hits, 47345 SSD reads (198.1 MB), read p50 189 us p99 502 us, blocked 104.436 ms total (submit 7.328 ms), cache 47522/1048576 rows
```

#### fk2 pp4k (Cpp-fk2-pp4k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3918 resident experts, decided on the device
strata generate: second GPU 1 (NVIDIA GeForce RTX 4060 Ti): 2643 experts from the profile and 0 empty slots, 4.97 GiB
strata generate: prompt path borrows 407 cache slots (0.77 GiB), 769 (1.45 GiB) on the second GPU
strata generate: prefill 4118 tokens in 1 chunks, 7505.4 ms (548.7 tok/s); experts streamed 0 (0 ahead), host 17.3 ms, resident 3470; PLE 0.0 ms
strata generate: prefill on the second GPU: experts streamed 19191 (19191 ahead), resident 1854; 607.6 ms queuing, 1290.8 ms GPU
strata generate: prefill GPU ms by section: PLE block 28; HC read (mixer) 101; GDN projections 202; GDN conv 15; GDN recurrence 73; GDN output norm 14; GDN output projection 58; QSA projections, norms, KV 51; QSA indexer appends 31; QSA block scores + top-k 8; QSA attention 45; QSA gate + output 22; HC write + HC read (FFN) 79; router, shared expert 49; grouping, experts 737; combine + HC write 5967; draft layer K/V 7
```

#### fk2 pp8k (Cpp-fk2-pp8k-prof.out)
```
verify window            wait for rings 67.444  pool 6.238  host 2.870  commit 0.079 ms/round; CPU experts 2.96 distinct / 3.26 routed per layer
adaptive tier            477 experts swapped in and 0 into empty slots (every 1 rounds, 0.090 ms/round), 96 moves dropped; 111.0 MB/round copied
second GPU               586.29 routed entries and 385.71 experts per round in 47.29 layers (0.57 left to the CPU), its rows after the CPU's in 46.14 layers, 62.079 ms/round; 360 experts swapped in and 0 into empty slots (0 still empty, 182 moves dropped; its copies between windows, 7.44 ms, at 6.4 GB/s); 218.86 experts per round prefetched, 180.57 of them used (0.260 ms/round of host time, 0 predictions waited for)
routing concentration    1000:0.749 2000:0.923 4000:1.000 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 10080 routed entries)
prefill                  8042 tokens in 8765.1 ms  ->  917.51 tok/s  (time to first token 9870.8 ms)
  per token              40.632 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 129024 rows, 0.0% row-cache hits, 76103 SSD reads (318.5 MB), read p50 186 us p99 430 us, blocked 151.089 ms total (submit 9.669 ms), cache 76512/1048576 rows
```

#### fk2 pp8k (Cpp-fk2-pp8k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3918 resident experts, decided on the device
strata generate: second GPU 1 (NVIDIA GeForce RTX 4060 Ti): 2643 experts from the profile and 0 empty slots, 4.97 GiB
strata generate: prompt path borrows 546 cache slots (1.03 GiB), 799 (1.51 GiB) on the second GPU
strata generate: prefill 8042 tokens in 1 chunks, 8469.2 ms (949.6 tok/s); experts streamed 0 (0 ahead), host 30.2 ms, resident 3339; PLE 0.0 ms
strata generate: prefill on the second GPU: experts streamed 19360 (19360 ahead), resident 1838; 414.1 ms queuing, 2146.8 ms GPU
strata generate: prefill GPU ms by section: PLE block 53; HC read (mixer) 150; GDN projections 303; GDN conv 28; GDN recurrence 143; GDN output norm 27; GDN output projection 97; QSA projections, norms, KV 91; QSA indexer appends 61; QSA block scores + top-k 20; QSA attention 101; QSA gate + output 38; HC write + HC read (FFN) 151; router, shared expert 87; grouping, experts 588; combine + HC write 6488; draft layer K/V 12
```

#### fk2 pp32k (Cpp-fk2-pp32k-prof.out)
```
verify window            wait for rings 62.591  pool 7.190  host 3.709  commit 0.079 ms/round; CPU experts 3.71 distinct / 4.16 routed per layer
adaptive tier            400 experts swapped in and 0 into empty slots (every 1 rounds, 0.089 ms/round), 125 moves dropped; 77.5 MB/round copied
second GPU               471.12 routed entries and 316.38 experts per round in 45.88 layers (1.38 left to the CPU), its rows after the CPU's in 44.38 layers, 57.588 ms/round; 362 experts swapped in and 0 into empty slots (0 still empty, 144 moves dropped; its copies between windows, 10.25 ms, at 6.4 GB/s); 213.12 experts per round prefetched, 166.75 of them used (0.268 ms/round of host time, 1 predictions waited for)
routing concentration    1000:0.748 2000:0.937 4000:1.000 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 9120 routed entries)
prefill                  32791 tokens in 22277.4 ms  ->  1471.94 tok/s  (time to first token 23387.9 ms)
  per token              44.695 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 524976 rows, 13.6% row-cache hits, 240944 SSD reads (1007.9 MB), read p50 187 us p99 452 us, blocked 429.799 ms total (submit 43.972 ms), cache 243132/1048576 rows
```

#### fk2 pp32k (Cpp-fk2-pp32k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3918 resident experts, decided on the device
strata generate: second GPU 1 (NVIDIA GeForce RTX 4060 Ti): 2643 experts from the profile and 0 empty slots, 4.97 GiB
strata generate: prompt path borrows 838 cache slots (1.59 GiB), 865 (1.63 GiB) on the second GPU
strata generate: prefill 32791 tokens in 3 chunks, 21945.3 ms (1494.2 tok/s); experts streamed 0 (0 ahead), host 144.4 ms, resident 7153; PLE 73.7 ms
strata generate: prefill on the second GPU: experts streamed 41706 (39436 ahead), resident 4053; 845.2 ms queuing, 8954.9 ms GPU
strata generate: prefill GPU ms by section: PLE block 351; HC read (mixer) 470; GDN projections 1039; GDN conv 116; GDN recurrence 582; GDN output norm 109; GDN output projection 384; QSA projections, norms, KV 356; QSA indexer appends 248; QSA block scores + top-k 144; QSA attention 457; QSA gate + output 149; HC write + HC read (FFN) 616; router, shared expert 280; grouping, experts 1414; combine + HC write 15071; draft layer K/V 51
```

#### fk2 pp120k (Cpp-fk2-pp120k-prof.out)
```
verify window            wait for rings 68.382  pool 7.365  host 1.677  commit 0.084 ms/round; CPU experts 3.65 distinct / 4.08 routed per layer
adaptive tier            419 experts swapped in and 0 into empty slots (every 1 rounds, 0.090 ms/round), 96 moves dropped; 94.7 MB/round copied
second GPU               552.00 routed entries and 389.14 experts per round in 47.43 layers (0.43 left to the CPU), its rows after the CPU's in 46.43 layers, 62.538 ms/round; 337 experts swapped in and 0 into empty slots (0 still empty, 123 moves dropped; its copies between windows, 7.62 ms, at 6.4 GB/s); 225.57 experts per round prefetched, 174.57 of them used (0.284 ms/round of host time, 0 predictions waited for)
routing concentration    1000:0.620 2000:0.822 4000:1.000 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 11520 routed entries)
prefill                  122903 tokens in 82510.4 ms  ->  1489.55 tok/s  (time to first token 83620.1 ms)
  per token              40.527 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 1966848 rows, 29.9% row-cache hits, 740572 SSD reads (3099.1 MB), read p50 187 us p99 438 us, blocked 1248.033 ms total (submit 111.595 ms), cache 712835/1048576 rows
```

#### fk2 pp120k (Cpp-fk2-pp120k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3918 resident experts, decided on the device
strata generate: second GPU 1 (NVIDIA GeForce RTX 4060 Ti): 2643 experts from the profile and 0 empty slots, 4.97 GiB
strata generate: prompt path borrows 838 cache slots (1.59 GiB), 865 (1.63 GiB) on the second GPU
strata generate: prefill 122903 tokens in 8 chunks, 82178.2 ms (1495.6 tok/s); experts streamed 0 (0 ahead), host 264.1 ms, resident 24350; PLE 26.8 ms
strata generate: prefill on the second GPU: experts streamed 157744 (157744 ahead), resident 14189; 1478.1 ms queuing, 30780.0 ms GPU
strata generate: prefill GPU ms by section: PLE block 1499; HC read (mixer) 1649; GDN projections 3667; GDN conv 433; GDN recurrence 2186; GDN output norm 410; GDN output projection 1398; QSA projections, norms, KV 1268; QSA indexer appends 930; QSA block scores + top-k 1257; QSA attention 1769; QSA gate + output 546; HC write + HC read (FFN) 2306; router, shared expert 960; grouping, experts 3533; combine + HC write 57946; draft layer K/V 52
```

#### fk1 pp4k (Cpp-fk1-pp4k-prof.out)
```
verify window            wait for rings 6.441  pool 49.706  host 2.669  commit 0.109 ms/round; CPU experts 10.61 distinct / 13.82 routed per layer
adaptive tier            455 experts swapped in and 0 into empty slots (every 1 rounds, 0.083 ms/round), 0 moves dropped; 122.6 MB/round copied
routing concentration    1000:0.618 2000:0.826 4000:1.000 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 8640 routed entries)
prefill                  4118 tokens in 1584.9 ms  ->  2598.23 tok/s  (time to first token 1693.8 ms)
  per token              24.932 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 66192 rows, 0.1% row-cache hits, 47321 SSD reads (198.0 MB), read p50 193 us p99 507 us, blocked 100.742 ms total (submit 12.504 ms), cache 47498/1048576 rows
```

#### fk1 pp4k (Cpp-fk1-pp4k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3845 resident experts, decided on the device
strata generate: prompt path borrows 1023 cache slots (1.94 GiB), 0 (0.00 GiB) on the second GPU
strata generate: prefill 4118 tokens in 1 chunks, 1535.4 ms (2682.0 tok/s); experts streamed 21754 (21754 ahead), host 89.0 ms, resident 2786; PLE 0.0 ms
strata generate: prefill GPU ms by section: PLE block 20; HC read (mixer) 94; GDN projections 202; GDN conv 16; GDN recurrence 74; GDN output norm 16; GDN output projection 60; QSA projections, norms, KV 66; QSA indexer appends 32; QSA block scores + top-k 8; QSA attention 46; QSA gate + output 22; HC write + HC read (FFN) 84; router, shared expert 63; grouping, experts 663; combine + HC write 28; draft layer K/V 7
```

#### fk1 pp8k (Cpp-fk1-pp8k-prof.out)
```
verify window            wait for rings 6.574  pool 20.163  host 0.095  commit 0.126 ms/round; CPU experts 12.36 distinct / 16.34 routed per layer
adaptive tier            384 experts swapped in and 0 into empty slots (every 1 rounds, 0.088 ms/round), 0 moves dropped; 118.1 MB/round copied
routing concentration    1000:0.608 2000:0.808 4000:1.000 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 8160 routed entries)
prefill                  8042 tokens in 2399.3 ms  ->  3351.82 tok/s  (time to first token 2511.9 ms)
  per token              10.337 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 128960 rows, 0.1% row-cache hits, 76007 SSD reads (318.1 MB), read p50 190 us p99 415 us, blocked 129.754 ms total (submit 21.001 ms), cache 76416/1048576 rows
```

#### fk1 pp8k (Cpp-fk1-pp8k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3845 resident experts, decided on the device
strata generate: prompt path borrows 1153 cache slots (2.18 GiB), 0 (0.00 GiB) on the second GPU
strata generate: prefill 8042 tokens in 1 chunks, 2343.8 ms (3431.2 tok/s); experts streamed 21884 (21884 ahead), host 139.8 ms, resident 2660; PLE 0.0 ms
strata generate: prefill GPU ms by section: PLE block 26; HC read (mixer) 142; GDN projections 305; GDN conv 29; GDN recurrence 144; GDN output norm 29; GDN output projection 98; QSA projections, norms, KV 102; QSA indexer appends 62; QSA block scores + top-k 20; QSA attention 101; QSA gate + output 38; HC write + HC read (FFN) 156; router, shared expert 91; grouping, experts 881; combine + HC write 53; draft layer K/V 12
```

#### fk1 pp32k (Cpp-fk1-pp32k-prof.out)
```
verify window            wait for rings 6.655  pool 17.277  host 1.747  commit 0.087 ms/round; CPU experts 11.88 distinct / 16.49 routed per layer
adaptive tier            576 experts swapped in and 0 into empty slots (every 1 rounds, 0.070 ms/round), 0 moves dropped; 140.0 MB/round copied
routing concentration    1000:0.758 2000:0.930 4000:1.000 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 11520 routed entries)
prefill                  32791 tokens in 8688.2 ms  ->  3774.21 tok/s  (time to first token 8792.1 ms)
  per token              13.525 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 525056 rows, 13.6% row-cache hits, 241008 SSD reads (1008.2 MB), read p50 188 us p99 443 us, blocked 407.721 ms total (submit 46.619 ms), cache 243195/1048576 rows
```

#### fk1 pp32k (Cpp-fk1-pp32k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3845 resident experts, decided on the device
strata generate: prompt path borrows 1426 cache slots (2.70 GiB), 0 (0.00 GiB) on the second GPU
strata generate: prefill 32791 tokens in 3 chunks, 8619.7 ms (3804.2 tok/s); experts streamed 47262 (44314 ahead), host 558.9 ms, resident 5628; PLE 97.0 ms
strata generate: prefill GPU ms by section: PLE block 140; HC read (mixer) 463; GDN projections 1039; GDN conv 117; GDN recurrence 587; GDN output norm 113; GDN output projection 388; QSA projections, norms, KV 360; QSA indexer appends 251; QSA block scores + top-k 145; QSA attention 459; QSA gate + output 151; HC write + HC read (FFN) 626; router, shared expert 281; grouping, experts 3101; combine + HC write 211; draft layer K/V 51
```

#### fk1 pp120k (Cpp-fk1-pp120k-prof.out)
```
verify window            wait for rings 7.017  pool 17.384  host 1.545  commit 0.120 ms/round; CPU experts 11.65 distinct / 15.25 routed per layer
adaptive tier            565 experts swapped in and 0 into empty slots (every 1 rounds, 0.069 ms/round), 0 moves dropped; 136.7 MB/round copied
routing concentration    1000:0.615 2000:0.818 4000:1.000 6000:1.000 8000:1.000 10000:1.000 12000:1.000 16000:1.000 20000:1.000  (top-N experts' share of 11520 routed entries)
prefill                  122903 tokens in 31958.5 ms  ->  3845.70 tok/s  (time to first token 32054.7 ms)
  per token              13.713 ms/token (WALL CLOCK: embed, layers, head, sample)
  ple io: 1966848 rows, 29.9% row-cache hits, 740580 SSD reads (3099.2 MB), read p50 190 us p99 437 us, blocked 1254.822 ms total (submit 154.439 ms), cache 712835/1048576 rows
```

#### fk1 pp120k (Cpp-fk1-pp120k-prof.err)
```
strata generate: native pack: /home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s experts (largest blob 2.66 MB), token embedding type 23 in mapped host memory (322 MiB)
strata generate: PLE on, table 320001536 rows of /home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
strata mtp: draft layer loaded, 939 MiB of VRAM (experts 675 as Q2_0 blobs, dense 111)
strata generate: R4 hit path ON - resident experts are computed on the GPU
strata generate: token graph hit path: 3845 resident experts, decided on the device
strata generate: prompt path borrows 1426 cache slots (2.70 GiB), 0 (0.00 GiB) on the second GPU
strata generate: prefill 122903 tokens in 8 chunks, 31890.1 ms (3854.0 tok/s); experts streamed 177256 (177256 ahead), host 1082.7 ms, resident 19095; PLE 41.9 ms
strata generate: prefill GPU ms by section: PLE block 306; HC read (mixer) 1672; GDN projections 3719; GDN conv 439; GDN recurrence 2208; GDN output norm 425; GDN output projection 1417; QSA projections, norms, KV 1282; QSA indexer appends 943; QSA block scores + top-k 1266; QSA attention 1784; QSA gate + output 552; HC write + HC read (FFN) 2346; router, shared expert 973; grouping, experts 11204; combine + HC write 791; draft layer K/V 53
```
