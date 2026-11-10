### Phase D — Strata v0.1.31 (released 05:07, during Phase C), measured on its own

v0.1.31 is 61 commits over v0.1.30. What matters here:
- **Linux pinning:** the 8 GiB arena pin cap now applies only under Windows/WDDM (#253), which replaces our patch 0011.
- **Server fixes:** a status race (#266), the tokenizer (#268), and truncated tool calls (#211/#231).
- **Verify window:** a bounded final wait and GPU-wait release (#267).
- **Grouped experts:** a "decode once" path for the grouped expert kernels (8ec94aa, bitwise).
- **Hyper-connection read:** a new opt-in version (v3, another summation order; off by default).

**The port** (`patches/r9/0001–0013`, branch `r9-pr245`):
- **GR v5:** merged by hand into upstream's reorganized hyper-connection code. The default is our v5;
  `STRATA_GR_V3=1` selects upstream's v3, `STRATA_GR_OLD=1` upstream's old kernels.
- **0011 dropped;** upstream's fix verified (every expert by DMA: 32K 89,736 / 89,736, 112K 314,076 / 314,076).
- **The MMQ offsets patch** applied cleanly (same llama.cpp pin).

**Measured on its own (CLI exact pairs, fixed cache):**
- Plain v0.1.31 + our patches is bit-identical to C\\*9, with the same prompt speed.
- **But decode per round is 6–9 % slower** (math 31.05 vs 29.13 ms): upstream's "decode once" path gives nothing
  measurable on this setup. So PR245 still pays, and was transplanted onto v0.1.31's kernels (fallback to
  upstream's format-generated switches; `STRATA_EXPERTS_OLD=1` = v0.1.31's own path).

**C\\*10 = v0.1.31 + `patches/r9/0001–0013`** (clean clone `work/r8/build-cstar10.sh`, engine `f3ff83cd…`, tree `430fc30e`):
| check | result |
|---|---|
| exact vs C\\*9 (greedy + sampled math / code, 2K, 32K, 112K) | **bit-identical on all 7**; ms per round equal |
| teacher-forced NLL, 14 texts | **14/14 identical** to the C\\*8 / C\\*9 reference |
| round trip | exact |
| needles | **72/72** |
| Stop at 120K | 7/7 |
| A/B vs C\\*9 (decode + full screens, ABBA) | **equal**: decode 110.3 / 111.3 vs 110.9 / 112.4 tok/s; TTFT 32K–120K within 0.06 s |
| fresh holdout ABBA | **equal**: decode 102.3 / 102.4 vs 102.6 / 103.9; 28K document 10.19 vs 10.17–10.20 s |
| browser test | 52/56: the 2 known non-bugs + the 2 live-answer checks (SearXNG suspended again: 0 results from both engines); every web mechanic passes |
| fallback | see below (a launcher bug of mine, fixed) |

**A bug in our launcher, found by the fallback test.** run-strata.sh (written in Round 6) read the main card's free
VRAM with `nvidia-smi -i "$CUDA_VISIBLE_DEVICES" … | head -1`. A helper config lists two cards, so nvidia-smi
prints two lines; `head` can close the pipe under it, and `pipefail` + `set -e` then ended the start without a
word. It's timing-dependent: it passed for C\\*9 and could hit any start of a helper config. Fixed: it now queries
the first card only.
