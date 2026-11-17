# Engine-speed round r24 (2026-11-11 to 11-17): what was tested and found

This is the results of the round planned from `../engine-speed-1111/` (the profile pack, the 11-11 ideas file and ten
outside reports and audits). It is meant for anyone suggesting new decode-speed ideas for this setup. The companion
file `IDEAS-COVERED.md` lists every idea already tried, measured, planned or backlogged, so new suggestions don't repeat
them.

All numbers come from this box. Every gap ran with the served model, the served switches and the standard sampling
(temperature 1.0, top-p 0.95, top-k 20, min-p 0.05). "Fixed work" means a recorded request replayed with the same token
histories and window widths; "free-running" means ordinary sampled requests.

## 1. The daily setup

| part | today |
|---|---|
| model | Qwen3.8-Flash-Next (MoE, 48 layers, 512 routed experts, top-10), GSQ-RCO IQ3_S native pack, MTP drafter |
| engine | Strata v0.2.8 port with our fork's exact sampling (P028x) plus STRATA_ADAPT_FETCH=2 (the PCIe share admits what it fetches into the cache). The v0.2.13 port is built and passed its baseline gate; it is the Qwen4 base |
| context | 262,144 tokens (`--max-context 262144`); KV int8, 32,768 cells resident in VRAM, the rest streamed from pinned RAM. 256K cost -0.63 % on short decodes, accepted |
| GPU 1 | RTX 5080 16 GB: the verifier, the expert cache (4,467 slots), the MTP drafter |
| GPU 2 | RTX 4060 Ti 8 GB: a helper expert cache (3,300 slots) that computes the experts it holds |
| CPU / RAM | Ryzen 9 9950X3D (16 cores), 96 GB DDR5-6000; a 15-worker CPU expert pool (one worker per physical core) plus the host thread |
| PCIe share | `--pcie-frac auto` (PcieAuto); it settles at 0.40 in every measured start (a copy kernel on the GPU reads the misses from the pinned arena) |
| drafting | MTP, up to 7 drafts (`--spec 8`), drafts sampled and verified exactly (STRATA_SPEC_EXACT), an adaptive cumulative draft-length threshold, a cost gate; the prompt-lookup drafter as served |
| use | one user, one request at a time (coding agents and research runs); no batching |

**Speed** (six seeded test requests, 17 free-running base starts in five gaps):
- 167 tok/s decode;
- 21.0 ms per verify window;
- 3.51 committed tokens per window, mean window width 4.37 rows;
- per-depth acceptance of MTP drafts 0.80 / 0.83 / 0.88 / 0.90 / 0.91 / 0.87 (depths 1-6).

Over a capture of 275 real coding-agent requests (B1), decode is **89 % of model time**: the prompt cache keeps
prefill small.

**Where a window's experts come from** (per layer and window, the decode-timing line): 29.5 cache hits on the 5080,
4.3 CPU experts (4.5 rows), 2.0 over PCIe, plus whatever the helper card holds.

## 2. Where the decode time goes (A1, X9 and B1 changed the picture)

**The host's view** (the decode-timing line, free-running, 21.0 ms per window):
- verify 18.7 ms: the host's wait for the GPU 8.8 ms + per-layer host work 9.1 ms, of which the CPU pool is 8.3 ms;
- draft 2.3 ms.

**The GPU's own view**, from per-layer-step GPU timestamps (X9: a served-form replay, 18.7 ms per window, 2,428 windows):
- the MoE span is 9.6 ms of the window: VRAM expert groups 3.0 ms, PCIe expert groups 5.8 ms, the wait for CPU rows
  0.74 ms, the wait for the host's plan 0.14 ms;
- **the PCIe copies sit on the critical path**:
  - a step with PCIe experts (2.57 blobs of 1.4-2.5 MB) starts its copy at the plan; the copy lands 221 us later
    (23.6 GB/s);
  - the PCIe groups end 11 us after it, while the VRAM groups take 66 us;
  - so about 160 us of every such step waits on the link: about 65 us per blob, against 2.8 us per VRAM expert.
- **the CPU pool is mostly hidden**: it runs about 180 us per step that has CPU work, but the GPU waits for its rows only
  15 us of that. That is 0.68 ms per window, 3.6 %.

**The CPU pool's bandwidth:** expert bytes stream at 50.5-57.1 GB/s over the pool's run time (A1). That is 70-79 % of
the DRAM-limited read rate measured in an earlier round (about 74 GB/s at 6200 MT/s, about 72 expected at today's
6000).

**The CPU pool's cost** (4.5 M pool runs, B1's trace): 7.8 us + 39.9 us per CPU expert. An extra row on an expert costs
nothing measurable, and 94.6 % of CPU jobs have one row: the cost is the weight read.

**Window cost by width** (B1): every extra verify row costs about 3 ms. MTP windows of 2 / 4 / 7 rows take 12.8 / 17.3 /
27.1 ms. The average is 5.74 ms per committed token.

## 3. Measurement findings

- **Decode speed follows acceptance, not the machine.**
  - Over 17 base starts with one config, tok/s correlates with tokens per window at **r = 0.984**.
  - Starts that happened to generate byte-identical outputs repeat their speed to 0.3 %, 4-12 hours apart.
  - The "drift" of the base (165.2 -> 167.0 -> 170.1 tok/s across three gaps) was the sampled text, not clocks,
    temperature, power, PCIe share, order or page cache.
  - Time model: ms per window = 10.38 + 3.03 x tokens per window (residual 0.29 %).
- **Acceptance-adjusted metric** (now the rule for switches that don't change drafting):
  - compare ms per window at equal acceptance (the fixed 3.03 slope), raw tok/s reported beside it;
  - two guards: the arm's tokens per window and its mean window width at equal acceptance must match the base's
    within 2 standard errors of the per-start luck (3.15 % and 0.33 %);
  - an acceptance trip gives NOT DECIDED (raw tok/s from the same lucky starts would be biased), not a raw verdict;
  - noise floor: 2 standard errors of the 0.29 % residual.
- **Smallest gain detected 80 % of the time (5 % two-sided):**

  | method | per-start sd | 3 v 3 | 4 v 4 | 6 v 6 |
  |---|---|---|---|---|
  | raw tok/s | 1.57 % | ~4.8 % | **~3.7 %** | ~2.8 % |
  | acceptance-adjusted | 0.29 % | ~0.9 % | **~0.7 %** | ~0.5 % |

  Raw tok/s needs about 40 starts per arm to see 1 %. Fixed work resolves about 0.2-0.3 % at 2 v 2. Served outputs
  don't repeat between starts (0/6 seeded requests identical over 4 starts), so free-running comparisons need the
  adjusted metric.
- Several earlier "wins" of 2.5-2.7 % (BALANCE, MIN1) were acceptance luck. At equal acceptance they are within noise
  or slower.

## 4. Everything tested this round

| item | result | why |
|---|---|---|
| A1 baseline diagnostic | read-out | Logging overhead within noise (+0.21 %, +0.02 % with the trace); CPU pool 50.5-57.1 GB/s; the forced-rejection fixtures did not show rounding-level state against today's width-to-width differences (ratio 1.02, interval 0.98-1.08: FAIL by the rule), so no wider verifier is built |
| A2 QIL | dropped | Byte-identical but not faster (+0.02 % at fixed work) |
| A2 HC_PERSIST | dropped (correctness) | 2.9 % slower at fixed work and fails the long-prompt KL rule |
| X1 -> X8 fused BF16 hyper-connection kernel | dropped | Bit-exact at every width, but 8.5 % slower |
| A3 PCIE_MIN1 (>= 1 PCIe expert a layer) | dropped | +0.57 % slower at fixed work; the free-running +2.70 % was luck |
| A3 PLE row cache 4M / 8M | dropped | +0.32 % / +0.11 % (within noise or slower) |
| A4 / X5 CPU pool layout | dropped | 12 workers = 15 (+0.01 %); 8 workers +2.6 % slower; one CCD +2.2 % slower; `--aux-cpus auto` -0.11 % (noise). The pool is bandwidth-bound, not worker-bound |
| A5 SPEC_COST (cost-aware draft stop) | dropped | -0.48 %, within noise |
| A3c / A3p / GBAL PCIE_BALANCE (timing-fed CPU / GPU split) | dropped | +2.5-2.6 % screens, then -1.72 % in GBAL; at equal acceptance -0.1 to +0.5 %, within noise in all three gaps |
| A3p pinning the PCIe share at 0.40 | dropped | -0.27 % (noise); outputs don't repeat more often when pinned |
| GBAL MIN1 stacked on BALANCE | dropped | Slower at equal acceptance (-1.0 %) |
| C256 256K context | adopted | Works (a 202K-token haystack, every needle right); -0.63 % short decode accepted |
| B1 routing-trace capture | done | 275 requests, 102,190 windows, the full route / residency / candidate-router record; trace overhead -1.37 % (1 v 1) |
| X9 deadline map | read-out | Every layer-step's GPU stamps and host stamps on one timeline; trace distortion +0.13 % (noise) |
| X10 copy-window (suffix-tree) drafting | dropped | 13.8 % of tokens sit in long repeats, and today's lookup already commits 27 % of them; the best causal trigger gains +0.3 %; hindsight ceiling ~5 % (every wrong copy row costs ~3 ms) |
| C1 PCIe miss selection by this window's saved time | dropped | Different picks (4.5 %), but the CPU pool's cost is per expert, not per row: ~0 saved |
| CPU expert kernels (IQ3_XXS singleton, AVX-512 IQ4_NL down) | dropped for now | The exposed CPU wait caps it at 3.6 %; at the most the bandwidth headroom allows (25-30 % faster), 2.7-2.9 %, under the +3 % bar. On top of X11: +1.2 points with no contention |
| X11 one-layer-ahead expert staging | **GO, being built** | See below |
| X11 predictors | scored | Router L+1 on layer L's input: 26 % recall / 45 % precision at 3 uploads a step (31 % / 41 % at 4); near-miss readahead 10.5 %; a miss-follows-miss table 9 % |
| X12 cost-gate miss feature | dropped | -0.03 % on held-out requests: the expected new misses per draft row barely vary (55-71 at every depth) |
| X14 i7 kernel benchmark (second PC) | harness only | The reference run here passed; the second PC's run is backlogged |

**X11 in numbers** (X9's stamps; decode 89 % of model time):
- **Bound** with perfect prediction one layer ahead, the link capped by today's step spacing: 13.6-15.6 % of window time
  (9.5-12.5 % on a smaller held cache).
- **Realistic model:**
  - the router-L+1 predictor at 3 uploads a step;
  - unpredicted misses served as today;
  - the ahead copies limited to the link time the previous step's own copies leave, 10 % tighter for shorter steps.
- **Result:** about 7 % before costs. After the router pass (0.5-1.4 %) and DRAM contention (0-10 %), **about 5 % decode
  central, 2.9-6.6 % range, about 4.4 % end-to-end**.
- **Full runahead** (perfect knowledge of the next layer's experts) would reach 12.8-15 % before its own costs: not
  pursued before the cheap version is measured.
- Upstream's similar ForesightSwap (per-layer swap slots out of the cache, a CPU-side router look-ahead) was measured
  slower or no better on every box by its authors, so it was not used. X11 uses a small staging ring (about 22 MB), a GPU-side router
  pass and the copy engine.

## 5. In progress

- **X11 stage 1** (built, reviewed, waiting for a gap): the router pass and the ahead copies in shadow mode (nothing
  uses them). One fixed-work gap measures the GPU pass, the look-ahead thread and the copies' link / DRAM cost
  separately. Stage 2 (the dispatch uses the staged experts, with a fallback when a copy is late) only if the measured
  costs keep the gain at or above +3 % end-to-end.
- **Block verification** (block-level speculative verification instead of token-wise):
  - A logging-only gap captures, at every verify row, the drafter's exact sampling distribution and the target's top-64
    logits. Sizing it needs exactly these.
  - The sizing tool's Monte Carlo self-test confirms the method is lossless.

## 6. Ground rules for any idea

- **Lossless**: every change must be exact (byte-identical output), rounding-level (within the measured spread of
  today's own rounding differences, judged against references), or distribution-preserving (a sampled-distribution
  test against the unchanged target).
- **Draft-only shortcuts are allowed**: a cheaper or approximate drafter is fine, as long as verification keeps the
  target's distribution and the target's weights are untouched.
- No BIOS, boot-flag or driver changes, nothing that needs a GPU reset, and no root-only tuning at run time (the engine
  runs as a normal user).
- Single user: one request at a time; batching ideas only matter if that changes.
- A build needs a predicted gain of about +3 % end-to-end; measurement gaps are cheap, builds are not.

## 7. What's coming

- **Qwen4 Flash** is expected, with about 1M context. Its size is unknown, possibly around 300B parameters, which may not
  fit in 96 GB of RAM at today's quant.
- Its base will be the v0.2.13 port, which has the SSD file tier in case the model must stream experts from disk.
- Ideas that help when experts stream from RAM or SSD over PCIe, or that scale with context length, will matter more
  then.

Measured and drafted with Claude Code.
