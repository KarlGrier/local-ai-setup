### Round 7 backlog (ranked by expected gain × confidence ÷ cost)

| # | item | expected | risk / cost | first step |
|---|---|---|---|---|
| 1 | **Next-layer expert staging to VRAM** (predict layer l+1's CPU experts with router(l+1) on layer l's router input, computed on the GPU during the pool phase; DMA the predicted non-resident experts into a staging ring during the GPU phase; the real router still decides) | model: ~10 % realistic (pre-MoE, K=10), 14.7 % oracle with warming | high (graph + host + DMA ring; GPU arithmetic → TF) | an **engine oracle run** first: greedy, `--adapt-swaps 0 --suffix-draft 0`, replay a recorded trace as the oracle, measure the real ceiling incl. the DMA's effect on the GPU phase's VRAM bandwidth; go only if ≥ 15 % |
| 2 | **Prompt: MMQ reads experts through a pointer table** (no per-expert copy into the 16-expert group buffer) | ≤ 10 % of prompt GPU time (exact) | high: ggml MMQ template change; the tail read past a matrix (why `MMQ_TAIL` zero-pads) needs a padded or bounds-checked source | a parity test of one layer (bit-exact outputs) with padded ring slots |
| 3 | **Prompt: underfilled MMQ** (~160 rows per expert per chunk; 21 % at ~1.4 TFLOPS) | unknown, possibly large | high (kernel work) | profile MMQ tile occupancy per expert size; try tile sizes for 64–256 rows |
| 4 | **Deterministic draft policy switch** (`DraftPolicy` uses measured round times) | exact A/B tests without `--suffix-draft 0` | low | upstream suggestion (PR draft 24) |
| 5 | **Adaptive draft length** (item 9, not attempted) | unknown | med | replay candidates from the v2 trace (missing counterfactuals = unknown), confirm with real runs |
| 6 | Helper expert choice by exposure (put the 4060 Ti's 3,300 experts on the layers where the CPU is on the critical path) | ~1 % (the per-layer budget replay gave +1.1–1.4 % for the 5080's cache) | med | replay first |
| 7 | Decode n-gram reads: the drafts' rows (only token 0 is prefetched now); SSD power-state latency in decode (p50 ~450 µs vs ~110 µs in prompts) | ≤ 1 % | low | prefetch each draft's rows as the MTP produces it |
| 8 | The host's activation quantization before the pool (6.9 µs/layer, serial) | ≤ 1 % | low | parallel over tokens / workers, exactness test |
| 9 | Carried from round 5: v0.1.23's batched window not bit-identical at T=6 (corpus text); EAGER VRAM (draft 12); first long prompt allocates GPU memory (draft 15; warm-up covers it); setup.py moves `strata*` folders (draft 11); page min-p (draft 08) | – | – | upstream |
