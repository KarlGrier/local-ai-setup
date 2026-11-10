# Single-card decode: Basalt 0.2.0 vs our Strata (P028x) on the RTX 5080 - study (11-03)

Read-only study. Nothing was built, run or measured for it: every number below comes from the 11-02/11-03 gap logs or
from reading the two trees. Estimates are marked as such. Scratch scripts (log parsers, the fit, the profile compare):
`basalt-020/scratch-study/` (parse.py, fit.py, profiles.py; they only read logs and the two profile files).

- Basalt: `basalt-020/src` = v0.2.0 f0bb833c. Line numbers are v0.2.0's.
- Strata: `strata-compare/strata-r22p028x` = v0.2.8 + our 28 commits (branch r22-port028x, 8f7a48aab). The solo arm is
  `configs/x28h-solo.json` (P028x without the 4060 Ti, STRATA_ROUTE_TAIL_SKIP=0).
- "Exact" below means one of: **bitwise** (same output bits), **rounding-level** (arithmetic order or the tier that
  computes an expert changes; our KL rule applies), or **distribution-exact** (sampled output keeps the exact
  distribution, seeded texts change; chi-square gates). Lossy items are left out (route-prior, route-tail-skip,
  relaxed drafting, the two-stage head, the int8 hc copy).

## 0. Summary

> **Updated after gap 18 (section 6).** Measured on our solo arm: GPU serial segment 8.9 ms, CPU experts 13.4 ms,
> drafting 2.3 ms and tail 0.9 ms of a 25.5 ms window. The fit below had put too much time on columns and too little
> on the CPU tier. The re-inferred gap to a lossless Basalt is mostly the GPU serial segment and drafting (~2.5-3 ms
> per window). The CPU side is roughly even: Basalt's pool is faster per entry, but our PCIe share offsets it. Section
> 6.5 re-ranks the candidates: adaptive cadence, L2 prefetch during the CPU phase, the draft chain, then a single-card
> C1/C2 A/B. PDL, GRAPH_PRIO, FUSE_WAIT and the device-planned tail drop to ~0.

- **Where the gap is.** At about the same window shape (3.4-3.6 tokens and 4.2-4.6 columns per window, similar
  acceptance) Basalt needs 21.4 ms per verify window and we need 25.7 ms. On the identical greedy `struct` text Basalt
  is still 7-10 % faster per window. Drafting is not the difference.
- **How it splits** (a fit of window time on window shape, section 1.3):
  - **~1.2-1.5 ms per window is exact engine work.** It is mostly on the GPU side of each layer: launch structure (PDL,
    priorities, node count), the MoE hand-off, idle GPU time while the CPU tier runs, the GDN kernels and drafting.
  - **~0.7-1.0 ms is Basalt's lossy int8 hc copy.** Not portable.
  - **~2 ms is window shape.** Basalt has 14 % fewer miss entries, from a faster, larger adaptive tier and a newer
    starting profile. Basalt's 4 % extra expert slots also come from the int8 hc copy, so a lossless Basalt would
    have about as many slots as we do. "Basalt lossless ~149" is therefore slightly optimistic: about 147.
  - The largest per-workload gaps are A-edit (+33.5 %) and R4 (+17.9 %), both short replies after a long prompt, and
    the cold start. There Basalt's GPU share recovers within the request and ours does not.
- **The CPU tier is half of each window in both engines.** We compute fewer entries there because of our PCIe share.
  Basalt runs one-token expert groups on its AVX-512 rows with gathers, while ours go to ggml's AVX2 dot with scalar
  lookups. It also runs one pool batch per layer where we run two phases with a host step between them.
- **Cheapest first.**
  - Four switches that already exist in our tree and are documented bitwise: `STRATA_DF_PDL=1`,
    `STRATA_IQ_GATHER=1`, `STRATA_GRAPH_PRIO=1`, `STRATA_FUSE_WAIT=2` (plus a one-line flag to unpin the pool).
  - Four settings that change rounding: the adaptive cadence with `STRATA_ADAPT_OVERLAP(_RESIDENT)`, Basalt's
    profile, `--spec 8` and `STRATA_IQ_MT_MIN=1`.
  - Then small and medium bitwise code: an L2 prefetch while the CPU runs, one pool batch per layer, the
    device-planned MoE tail, and a conditional-graph draft chain.
  - **Estimated together: +6-11 %, which closes most of the ~+9-11 % lossless gap.** The rest sits in large
    rounding-level kernel work: the GDN mid chain with tensor-core projections, and the hc-read structure.
- **Before any of it**, one solo-arm gap with `STRATA_DECODE_TIMING=1` (and once `STRATA_VERIFY_PROFILE=1`) would
  replace the fit with measured waits (section 5).

## 1. The measurement, decomposed

### 1.1 Client clock, the 9-workload screen (3 passes, rates pooled per workload)

| workload | P028x solo | Basalt stock | Basalt exact head | P028x (4060 Ti on) | exact head vs solo |
|---|---|---|---|---|---|
| W1-think | 159.1 | 182.7 | 172.8 | 173.2 | +8.6 % |
| W2-code | 139.8 | 165.1 | 163.5 | 154.7 | +16.9 % |
| W3-research | 141.3 | 170.7 | 162.9 | 162.6 | +15.3 % |
| A-edit | 108.7 | 151.0 | 145.1 | 125.3 | **+33.5 %** |
| B-write | 142.1 | 176.8 | 169.5 | 156.2 | +19.3 % |
| R1-verify20k | 135.7 | 153.8 | 149.2 | 154.1 | +9.9 % |
| R2-report54k | 128.3 | 147.4 | 143.7 | 154.4 | +11.9 % |
| R3-extract5k | 149.8 | 184.0 | 176.2 | 182.4 | +17.6 % |
| R4-agent33k | 113.4 | 129.6 | 133.7 | 130.0 | +17.9 % |
| geomean | 134.5 | 161.4 | 156.8 | 153.8 | **+16.6 %** |

Client and server clocks agree within 1 % on every workload (Basalt's W1/R1 server timings cover only the last pass of
the answer-room continuation, so they are not used). The decision's "Basalt lossless ~149" (exact head + the BF16 hc
bytes) is +11 % over 134.5.

### 1.2 Engine logs: per verify window (every request of the 3 passes; Basalt's warm-up left out)

| | Basalt stock | Basalt exact head | P028x solo |
|---|---|---|---|
| tokens / window | 3.48 | 3.42 | 3.58 |
| columns / window (window + drafts) | 4.29 | 4.23 | 4.55 |
| acceptance per draft | 0.751 | 0.749 | 0.730 |
| **ms / window** | **21.38** | **21.48** | **25.73** |
| ms / token | 6.15 | 6.28 | 7.18 |
| routed (expert, column) entries / column | 480 | 480 | 480 |
| GPU cache share of routed entries | 70.7 % | 70.9 % | 68.5 % |
| read over PCIe by the GPU | 0 % | 0 % | 8.5 % |
| computed by the CPU pool | 29.3 % | 29.1 % | 23.0 % |
| CPU entries / window | 603 | 591 | 502 (+185 over PCIe) |
| expert slots | 4,788 (elastic: 4,428-4,788) | same | 4,585 |
| adaptive swaps / window | **53** | 53 | not logged (at most 96 per round, a round every 4 windows: <= 24) |

Basalt's "hit rate" line counts every routed entry; Strata's divides by the entries not read over PCIe, so the
table recomputes both as shares of all routed entries.

The two engines draft about equally well: Strata gets slightly more tokens per window (3.58 vs 3.42-3.48) but
needs more columns for them. **The gap is the time per window: +4.3 ms (+20 %) at about the same window shape.**

The identical greedy text (Basalt's `struct` fixture, 7,230 tokens, the same text in both engines) says the same:

| struct, cold, 3 passes | windows | columns / window | ms / window | ms / token | GPU cache share | CPU entries / window |
|---|---|---|---|---|---|---|
| Basalt stock | 965-1,004 | 7.46-7.87 | 28.6-30.0 | 4.0 | 78.0-78.6 % | 766-825 |
| Basalt exact head | 970-1,004 | 7.51-7.71 | 29.5-29.7 | 4.0 | 78.3-78.6 % | 784-792 |
| P028x solo | 1,082-1,090 | 6.90 | 31.8 | 4.78 | 75.6 % (+7.3 % PCIe) | 566 (+241 PCIe) |

Basalt computes **more** entries on the CPU per window than Strata and still runs each window 7-10 % faster with 8 %
more columns. (Part of struct's gap is the draft cap: our `--spec 7` allows 6 drafts, Basalt's default 8 allows 7;
struct accepts 96 % of drafts, so the cap binds there.)

### 1.3 A fit of window time on window shape

Least squares over every request of the arm (32-33 requests each, rms residual 0.22-0.28 ms):

`ms/window = a + b * columns + c * (CPU + PCIe entries) + d * (context in K tokens)`

| arm | a (fixed) | b (per column) | c (per miss entry) | d (per 1K context) |
|---|---|---|---|---|
| Basalt stock | 6.11 | 0.78 | 19.7 us | 0.001 |
| Basalt exact head | 5.96 | 1.10 | 18.1 us | 0.009 |
| P028x solo | 7.63 | 1.52 | 15.7 us | 0.024 |

Evaluated at P028x solo's own mean window (4.55 columns, 687 miss entries, 17K context):

| term | P028x solo | Basalt exact head's model | difference |
|---|---|---|---|
| fixed | 7.63 | 5.96 | +1.66 |
| columns | 6.91 | 5.02 | +1.90 |
| miss entries | 10.80 | 12.42 | -1.62 |
| context | 0.41 | 0.15 | +0.26 |
| **window** | **25.76** | **23.55** | **+2.2 ms (+9 %)** |

Read with care: columns and miss entries rise together, so b and c trade off against each other; the sums are robust,
the split is not. What it says:

1. **At an equal window, Basalt (exact head) is ~2.2 ms (9 %) faster.** That is engine work. About 0.7-1.0 ms of it
   is the int8 hc copy (fewer bytes per window, lossy, not portable): **~1.2-1.5 ms per window (5-6 %) is exact engine
   efficiency** to look for.
2. **The rest (~2.1 ms, 23.55 -> 21.48) is the window shape**: Basalt's windows have 14 % fewer miss entries (591 vs
   687) and fewer columns. Fewer misses = a higher GPU share (adaptive tier, starting profile, 4.4 % more slots).
   The slot surplus is the int8 hc copy again (680 MiB in VRAM where BF16 needs 1,279 MB): a lossless Basalt would
   have ~275 fewer slots, about as many as ours. So the portable part of the shape is the adaptive tier and profile.
3. **Per miss entry, Strata is not slower** (15.7 us vs 18-20 us): our PCIe share takes a quarter of the misses off the
   CPU pool. The CPU tier's *speed per expert* may still be worse (section 2.3): the pool waits are roughly half of
   each engine's window.
4. **Long context costs Strata more** (0.024 ms per 1K tokens per window vs 0.001-0.009): at 54K about +1 ms per window.

### 1.4 Per workload: where the shape differs most

| workload | ms/window B-exact / solo | columns B-exact / solo | GPU share B-exact / solo | solo PCIe |
|---|---|---|---|---|
| W1-think | 14.24 / 19.27 | 3.16 / 4.00 | 82.1 / 81.3 % | 5.0 % |
| W2-code | 20.71 / 23.96 | 4.31 / 4.46 | 73.0 / 70.6 % | 7.7 % |
| W3-research (27K) | 25.64 / 31.16 | 5.04 / 5.28 | 67.9 / 62.4 % | 10.2 % |
| **A-edit** (after W3's 27K prompt) | 38.32 / 39.39 | 6.33 / 5.19 | **53.9 / 38.9 %** | 16.4 % |
| B-write | 21.94 / 25.39 | 4.72 / 4.63 | 73.5 / 69.5 % | 8.2 % |
| R1-verify20k | 20.55 / 24.69 | 3.65 / 4.02 | 68.6 / 67.3 % | 8.9 % |
| R2-report54k | 24.02 / 27.70 | 4.34 / 4.62 | 65.9 / 65.7 % | 9.2 % |
| R3-extract5k | 26.98 / 29.98 | 5.58 / 5.47 | 70.1 / 67.1 % | 9.2 % |
| **R4-agent33k** (short reply after 33K) | 25.12 / 30.80 | 4.73 / 4.62 | **66.3 / 56.5 %** | 11.7 % |
| first request of a fresh engine (384 tokens) | 20.5-20.6 / 25.9-27.0 | 4.2-4.3 / 4.3-4.4 | 72-73 / 66-68 % | 11.5-12.2 % |

The largest gaps are the short requests right after a long prompt (A-edit +33.5 %, R4 +17.9 %) and the cold start:
Basalt's GPU share recovers within the request (it swaps ~95-115 experts per window in A-edit), ours stays low.
Steady long replies (W1, R1, R2) differ by the per-window engine time alone.

## 2. Where the time goes, engine by engine

### 2.1 The window's critical path (both engines)

Both run a verify window as one CUDA graph per width, layer after layer; in every MoE layer the GPU's routed experts
and the CPU pool's experts run side by side and the combine waits for both. The CPU is the long pole: in our last
STRATA_VERIFY_PROFILE + STRATA_DECODE_TIMING run on the 5080 (r18, 10-10, C\*14 with the helper and `--pcie-frac 0`,
`results/r18/prof-side.txt`) a window of T 3.82 spent **11.4 of 23.5 ms in `waitCPU`**, 0.5 ms in the plan / PCIe
waits (waitA + waitB) and ~11.6 ms in GPU kernels (GDN mixer 2.9, hc reads + router 3.2, VRAM hits 2.2, QSA 1.2,
shared expert 0.9, head 0.64, combine 0.5), plus 1.27 ms of drafting outside the window. waitCPU grew 1.36 ms per
extra distinct CPU expert per layer-window (~28 us per expert), i.e. the pool's own cost per expert.

Basalt's fit (19.7 us per CPU entry) puts its CPU-dependent share at ~12 ms of 21.4 ms, about the same; its GPU-side
remainder is ~9.5 ms (stock) / ~10.8 ms (exact head) against our ~14.9 ms. **So the gap is mostly on the GPU side of
the layer (dense kernels, launch and hand-off structure, drafting) and in how early the CPU gets its work, not in how
many experts the CPU computes.** Two things would make this a measurement instead of a fit (section 5): a solo
window breakdown from our own diagnostics, and Basalt's `--wait-stats` on the same prompts.

### 2.2 The GPU side of a layer

(From reading both trees, `src/core/verify*` and `src/kernels/cuda/`. Node counts are estimates; neither engine logs
Basalt's.) The structure below is what changed in Basalt after fb0944c7 (10-20), where Basalt was level with us on one
card (10-21 A/B +1.9 %): the 10-24 MoE-ring series (87ed79b2, 83ffa621, 5d8704d9), the lazy commit and L2 prefetch
(4d9b608c, abccf9af), per-layer landing (670f6c72), the MTP draft fixes (35966539, 10-31 series), the QSA changes
(a9937aed, 9718298c) and the one-card adaptive defaults (b80e0262).

**MoE hand-off, per layer.**
- Strata: router GEMV and top-10 (verify.cpp:2080-2089) -> `doorbell_publish_q8k` (a counter in host memory,
  elementwise.cu:446-466) -> the **host plans** the layer (distinct experts, PCIe share; expert_source.cpp:4880-5012)
  and raises flagA (verify.cpp:3567-3571) -> the GPU spins in `wait_flag_ge(m_flagA_)` and copies the plan back over
  PCIe (verify.cpp:2280-2281) -> hit experts -> wait flagB -> PCIe share -> wait for the CPU rows ->
  `copy_rows_from_mapped` -> `moe_hit_add` -> combine (2285-2351). About 15 nodes and 3 spin-wait kernels per layer.
  The pool starts only after the host's plan is published (r18: `plan` 0.55-0.60 ms per window, ~12 us per layer).
- Basalt (device-planned tail, record_moe.cpp:24-213, dec_moe.cuh): the router runs inside the hc read
  (record_layer.cpp:273-289); a ring block launched with the read classifies the entries from a device residency table
  and rings the host **as soon as the top-10 ids are out, while the read still runs** (dec_moe.cuh:593-648); the
  gate/up "glue" launch plans CUDA0's groups itself; the combine spins on the CPU pool's word and reads its rows from
  host memory (native_moe.cu:199-215). About 4 nodes, no wait kernels. The host only serves the CPU entries
  (execution.cpp:255-262). One layer (47, IQ4_XS gate/up) falls back to separate kernels ("glue off ... types 23 / 20").
- Exactness of a port: the plan order is the same in both (Strata's `resident_plan` keeps "the host pool's layout and
  order", verify_kernels.hpp:107-109) and so is the combine's order, so **the device plan plus a self-waiting
  combine on Strata's own grouped kernels is bitwise** - with one condition: Basalt has no PCIe share in this path.
  Strata would either drop its PCIe share (pcie_frac 0: a measured trade, our share takes 27 % of the misses off the
  CPU) or compute the same "last pcie_num/256 of the distinct misses" rule on the device.

**Launch structure.** Basalt uses programmatic dependent launch everywhere (always on; 201 / 274 PDL launches per
window, 88 call sites) and runs its side branches at the highest stream priority with node priorities in the
instantiated graph. Strata: PDL only with `STRATA_DF_PDL=1` (opt-in, quantizations and dense projections only, 15
sites, verify.cpp:1273-1281: "every value is the same"); node priorities only with `STRATA_GRAPH_PRIO=1`
(verify.cpp:216-222, docs/DETAILS.md:1530: bit-exact, +1.8 % on an sm_80 card; it puts the shared expert at the
lowest priority, Basalt at the highest). Estimated ~2,000 graph nodes per Strata window (a comment cites 1,950 for a
6-token window, verify.cpp:1711) against ~800 in Basalt. None of these switches is in P028x.

**GDN layers (36 of 48).** Basalt: for windows of 1-4 rows one persistent "mid chain" kernel (qkv+z pair, recurrence,
out projection; mid_chain.cu, record_gdn.cpp:76-96), for 5-8 rows three kernels; projections on int8 tensor cores
(`dense_tc`). Strata: ~8-10 kernels (quantize, interleave, qkv `mmvq_il`, conv, step norm, quantize, interleave, out,
z and the a/b gates on side streams; verify.cpp:1538-1673). The recurrence is bitwise between the trees; **`dense_tc`
is not**: "the native kernels' math with fewer roundings, not their bits" (dense_tc.hpp:2-14), and on a card under 160
SMs (the 5080 has 84) the mid chain's out projection takes yet another reduction order (unified-kernel.md:14). So the
mid chain is a rounding-level port, and a large one. Its by-product is attractive: a column's value no longer depends
on the window width.

**Inside the CPU wait.** While a layer's combine waits for the CPU tier (about half of every window), Basalt's GPU
(a) commits the later GDN layers of the previous window (a commit finisher at the next window's start takes the rest;
commit.cpp:94-197) and (b) reads the next layer's projection weights (GDN qkv / gate / ssm_out, or QSA q/k/v/indexer/out)
into L2 (record_moe.cpp:64-95). Both bitwise. Strata's GPU idles there; its commit runs serialized on `cs_`
(verify.cpp:3646-3690). In r18 our GDN qkv + out projections took ~2.4 ms per window at T 3.8 (~67 us per layer, at
~30 % of DRAM bandwidth), so an L2-warm read is worth something, but how much depends on whether the hit experts'
~50 MB per layer evict it again (64 MB L2).

**Shared expert.** Basalt: the hc read's spare router row computes the shared gate dot and writes the q8_1 rows; the
side branch is the three projections (gate and up on two streams, highest priority); the combine applies the gate
(83ffa621; shared_expert.cu:128-143). Strata: 7 kernels at default priority on `sh_cs_` (verify.cpp:2154-2196). Bitwise
either way. Mostly hidden behind the host wait today, so a small gain.

**QSA layers (12 of 48).** Basalt: K, V and indexer on three high-priority branches, the gate rows of the query
projection beside the attention (9718298c: -0.4 % window time), five to eight queries score their blocks as two rows
of four (a9937aed), the block scoring is skipped when every selection is the identity (qsa_select.hpp:31). Its decode
attention `qsa_dec_attn` is bitwise its own batch kernel; our served `STRATA_QSA_SPLIT_ATTN` is not bitwise Strata's
decode kernel (qsa_prompt_attn.hpp:37-40). Our context term (0.024 ms per 1K tokens per window vs Basalt's
0.001-0.009) points here and at the KV streaming (Basalt instead backs KV cells in VRAM on demand, "elastic KV",
taking expert slots: 4,788 -> 4,428 at 54K).

**MTP drafting.** Per draft step both read ~85 MB of head (Basalt: a 2-bit screen of 106,299 rows + <= 64 exact rows
from the main head; Strata: 40,525 Q6_K rows). Basalt runs the whole draft chain as one conditional CUDA graph that
decides on the device whether to continue (conditional.cpp, draft.cpp:39-130), returns once the last draft has
arrived while the skipped nodes finish beside the next window, streams the head with evict-first loads so the layer's
other weights stay in L2 (35966539), and overlaps K/V append and head start (09e317b3, b063ffd4: -7..-11 us per
window). Strata waits on the host between steps and relaunches a graph each time (mtp.cpp:1792-1810), head in ~5
launches. Our draft costs 1.1-1.3 ms per window (r18). Bitwise if the drafter's arithmetic is kept; Basalt's 2-bit
screen would change q (our exact sampling stays distribution-exact, acceptance moves).

**Excluded (lossy):** the int8 hc copy - Basalt's `hc_fused_read` decodes from it unconditionally (hc_fused.cu:1332,
hc up in an fp16 hi/lo split), so its fused read + router + top-10 + q8_1 "queue kernel" can come over only as a
structure re-done in BF16 (large). The two-stage head. Note also: with `STRATA_GR_FORK=1` our `STRATA_GR_V3=1` has
no effect (the fork path returns first, fused_gr.cu:2634-2643).

### 2.3 The CPU expert tier

(From reading both pools; `src/kernels/cpu/` in each tree. Nothing measured.)

| | Basalt | Strata (ours) |
|---|---|---|
| one-token expert groups (most CPU groups: Strata's own note says ~1.4 tokens per group, native_expert.cpp:433) | AVX-512 multi-token rows for any token count, IQ4_NL down on its AVX2 multi-token rows (native_expert.cpp:91-109, 140-149) | `STRATA_IQ_MT_MIN` default 2 (native_expert.cpp:351-368): one token goes to ggml-cpu's per-token AVX2 dot (:452, :501-513). The AVX-512 one-token rows `x512_one` (:415-417) need `iq512_gather_on()`, false on AMD |
| IQ3_S / IQ2_S grid lookups | always gathered (iq_avx512.cpp:106-110, 140-145); sign masks by pdep (:44-50) | scalar unless `STRATA_IQ_GATHER=1` or an Intel CPU (`cpu_gather_fast`, expert_layout.cpp:257-276); measured 3-5 % slower with gathers on **Zen 4** (microcoded) - never measured on our Zen 5 |
| per-layer pool work | one batch per layer: ~12 tasks per thread split by byte share; an expert's down rows start once its own gate/up rows are done and quantized; no barrier (pool.cpp:464-492) | two phases of 48 tasks (gate/up, then down), the host quantizes every expert's intermediate alone in between, `wait_parked` before and after each phase (pool.cpp:1365-1395) |
| park / wake | pause spin, yield after 50 us, sleep at 20 ms (pool.cpp:142-161); **no pinning** since d5273cba ("a foreign task landing on a pinned worker core stalled the whole pool for a scheduler slice") | pause spin to 20 ms (pool.cpp:1000-1025); every worker pinned to one logical CPU, `pin=true` hard-coded (generate.cpp:6762) |
| between doorbells | idle workers score layer l+1's router (4-bit copy) on layer l's rows and read the likeliest CPU-only expert into cache (cpu_warm.cpp; 7dcf8ac3, 20dc3fb2) | nothing for RAM-resident experts (`RouterLookahead` only warms the page cache of the file tier) |
| who plans the layer | the GPU (device-planned tail); the host only takes its CPU entries (expert_source.cpp:2028-2030) | the host plans (distinct experts, PCIe share) and publishes the plan before the CPU work (expert_source.cpp:4884-5014) |
| PCIe share of misses in solo decode | none (only batch windows stage a few) | `pcie_frac` auto 0.35-0.40 of the distinct misses (8.5 % of routed entries) |

Identical in both (no gain from porting): the Q2_0 down kernel, the IQ4_NL AVX2/VNNI rows, IQ4_XS gate/up (ggml),
the 2 KB `_MM_HINT_T0` prefetch, one NUMA node.

Exactness of the CPU items:
- **Gathers and pdep masks: bitwise.** The same grid words; `row_dot` is the same text in both trees (Basalt
  iq_avx512.cpp:153-184, Strata :180-237). Strata's own parity test covers both lookups (iq512_gather_parity.cpp).
  With `STRATA_IQ_GATHER=1` Strata's one-token `x512_one` path for IQ3_XXS / IQ3_S also turns on, and that path is
  ggml's single-token dot bit for bit (checked at first use, native_expert.cpp:410-414).
- **One token on the multi-token rows (`STRATA_IQ_MT_MIN=1`): rounding-level** against today (16-lane sums and
  `_mm512_reduce_add_ps` instead of ggml's 8 lanes). It is Basalt's rule and has a property we want anyway: a token's
  rows round the same alone as in a group, so output no longer depends on how many drafts a window held. Upstream
  measured it -1..-3 % on IQ3_S AVX-512 **without** gathers.
- **One batch per layer: bitwise** (each row the same code on the same bytes; the quantizer unchanged).
- **Warm-up: bitwise** (it only reads memory). Basalt measured the CPU tier landing 3-10 us earlier per layer, the
  pool wait -0.1..-0.2 ms per struct window, and bench rates flat within noise (7dcf8ac3).
- **No pinning: bitwise.**

### 2.4 The adaptive tier and the starting placement

| | Basalt 0.2.0, one card, `serve` | Strata P028x solo |
|---|---|---|
| cadence | a round every window (`adapt-every 1` on a one-card server, options.cpp:42, b80e0262); each round takes 3 windows (evict to a free RAM place, copy in, land), the next starts when the last has landed | a round every 4 windows (`adapt_every` 4, generate.cpp:771), `STRATA_ADAPT_LAG=2` (ours): a window takes a round's swaps two windows later |
| size | 96 swaps; x4 (384) after a round that ranked >= 2x96 candidates (cold start, topic change) (tiers.cpp:341-345, state.hpp:131-134) | 96 (generate.cpp:807) |
| decay | 0.85 per round (tiers.cpp:592) | 0.7 (generate.cpp:776) |
| entry bar | candidate above victim + margin; spare swaps promote once-routed experts (only with one blob size over all layers: not our pack, which has 7) | candidate count >= 2.0 and >= victim + 1.5 (`adapt_min_gain`, generate.cpp:779, 11468-11477) |
| landing | per layer, on the device: the next window's gate/up launch waits on its own layer's 4-byte "landed" word (670f6c72); experts become resident at a fixed window count, so the text does not depend on timing | the window waits for the round's copies before it starts (lag 2: they have landed by then). Strata's own per-layer gate `STRATA_ADAPT_OVERLAP` exists (same tokens) but is off with ADAPT_LAG and needs `STRATA_ADAPT_OVERLAP_RESIDENT=1` in the resident RAM mode (generate.cpp:11253-11270) |
| ranking | at the window's last layer, on a thread while head and sampling run (edf40b03: idle before the next verify 0.119 -> 0.053 ms/window, +0.5 %) | between windows |
| measured | 53 swaps per window over the screen; ~95-115 per window in A-edit | not logged; at most ~24 per window |

Both tiers are run-to-run deterministic (placement depends on the window count, not on timing) - unlike Strata's
`--adapt-async`, which we pinned off for that reason. Placement changes only which tier rounds an expert:
**rounding-level**, the same class as a cache-size change.

**Starting profile.** Basalt 0.2.0 ships a new one, "learned from varied prompts" (data/profiles/qwen4exp-48x512.prof,
a 0.2.0 decode lever). Ours is v0.2.8's data/expert-profile.bin (= strata-cstar18's). Same format apart from our 4-byte
"STRP" magic (expert_cache.cpp:170-215: version 1, 48 x 512, 24,576 ranked pairs). They share only **68 %** of their
top 4,585 pairs (66 % of the top 3,700), and Basalt's gives the later layers more slots (layers 30-47: +10 to +30 slots
each; layers 0-9 fewer) - `scratch-study/profiles.py`. The first request of a fresh engine shows 72-73 % GPU share in
Basalt vs 66-68 % in ours.

## 3. Candidates portable into Strata (exact only)

Gains are estimates for **our single-card decode** (the 9-workload screen), from the measured window split above:
our CPU-dependent part is ~10.8 ms of a 25.7 ms window (fit) or ~11.4 of 23.5 ms (r18 profile), so 10 % off the CPU
expert path is ~1 ms per window, ~4 %; 1 ms of GPU work removed from every window is also ~4 %. None of these was
measured on our build. "Bitwise" items need exact7 + byte-identical logits; "rounding-level" ones our KL rule (mean,
p90, KL>1, changed top-1, NLL within the references' spread); "distribution-exact" ones the chi-square / near-tie checks.

| # | change | Basalt (file:line) | in Strata / our patches? | est. gain, single card | effort | exactness | risks |
|---|---|---|---|---|---|---|---|
| C1 | AVX-512 grid **gathers** for IQ3_S / IQ2_S on our Zen 5 (and with them Strata's own one-token AVX-512 rows for IQ3_XXS / IQ3_S, ggml's bits) | iq_avx512.cpp:106-110, 140-145 (always on) | **present, off on AMD**: `STRATA_IQ_GATHER=1` (iq_avx512.cpp:38-45; `x512_one` native_expert.cpp:410-417) | 0-4 % (gate/up of 27 of 48 layers is IQ3_XXS/IQ3_S; upstream: 1.3x ggml's one-token dot on a Xeon, but 3-5 % *slower* on Zen 4, whose gathers are microcoded; Zen 5 never measured) | **small: one env var** | **bitwise** (same grid words; `x512_one` checks its bits against ggml at first use) | may be slower on Zen 5 too: an A/B decides |
| C2 | one-token expert groups on the multi-token rows (Basalt's rule: no `mt_min`) | native_expert.cpp:91-109, 140-149 | **present, off**: `STRATA_IQ_MT_MIN=1` (native_expert.cpp:351-368); our default 2 sends a lone token to ggml's per-token AVX2 dot (:452, :501-513) | -2 to +3 % (upstream measured -1..-3 % on IQ3_S AVX-512 *without* gathers; with C1 and for IQ2_S, 20 layers, unknown) | small: one env var, after C1 | **rounding-level** vs today; afterwards a token rounds the same alone as in a group, so greedy output stops depending on the draft count (a plus for our exactness tests) | KL gate; measure only together with C1 |
| C3 | **one pool batch per layer**: an expert's down rows start when its own gate/up rows are done and quantized; ~12 tasks per thread by byte share; no barrier, no host-side quantize between phases | pool.cpp:464-492 (mode 8), 283-290; pool.hpp:119 | absent: two phases of 48 tasks, host quantizes between, `wait_parked` around each (pool.cpp:1365-1395, 1287-1293) | 1-3 % (one slowest-core tail and two park handshakes fewer per layer: est. 5-15 us x 48 layers, on the critical path since the window waits for the CPU) | medium (~80 lines in pool.cpp + the quantize hook) | **bitwise** (rows are independent; same quantizer) | the down tasks spin on a per-expert flag: needs the pool's stress test |
| C4 | no pinning of the pool workers / host thread | pool.cpp (no affinity calls; d5273cba) | absent: `pin=true` hard-coded (generate.cpp:6762) | 0-1 % on average; it removes scheduler-slice stalls when another task lands on a pinned core (our box runs SearXNG, the LDR runner, watchers) | small (a flag) | **bitwise** | upstream measured pinning better on a 6-core box; ours has 16 cores and 15 workers |
| C5 | CPU **warm-up**: between doorbells idle workers score layer l+1's router (4-bit copy) and read the likeliest CPU-only expert into cache | cpu_warm.cpp; execution.cpp:297-309; pool.cpp:369-399 (7dcf8ac3, 20dc3fb2) | absent for RAM-resident experts (`RouterLookahead` warms only the file tier's page cache, expert_source.cpp:3173) | 0-1 % (Basalt: CPU tier lands 3-10 us earlier per layer, struct pool wait -0.1..-0.2 ms/window, bench rates flat) | medium (~250 lines) | **bitwise** (memory reads only) | competes with the pool for RAM bandwidth; low value per effort |
| A1 | adaptive tier **cadence and memory**: a round every window, decay 0.85, per-layer landing so a window waits only for its own layer's copies | options.cpp:42, tiers.cpp:592, 670f6c72 | **settings exist**: `--adapt-every 1`, `--adapt-decay 0.85`, `STRATA_ADAPT_LAG` unset, `STRATA_ADAPT_OVERLAP=1` + `STRATA_ADAPT_OVERLAP_RESIDENT=1` (generate.cpp:1640-1667, 11253-11304; "same tokens, a layer waits for its own copies") | **2-5 %** (GPU share 68.5 -> ~70-71 % is ~0.4-1.1 ms per window; most of it on A-edit, R4 and the cold start, where we are 18-34 % behind) | small: settings only | **rounding-level** (placement); deterministic by window count, unlike `--adapt-async` | upstream: OVERLAP_RESIDENT +7.0 % on an A4000 but -2.6 % on a 3060 (copies share RAM bandwidth with the pool); every-window rounds with the *blocking* tier would stall each window: try OVERLAP first |
| A2 | Basalt's **three-step rounds** (evict into free places of the RAM copy, copy in, land; no exchange buffers), x4 rounds after a saturated one, ranking at the window's last layer on a thread | tiers.cpp:334-536 (xq_round, xq_advance), 545-621 (init_tiers); state.hpp:131-134; edf40b03 | absent (blocking tier with exchange buffers; the async tier is not run-to-run exact) | +1-2 % over A1 if A1's measurement shows the tier's own wait | medium-large | rounding-level (placement), deterministic | only after A1 says the remaining cost is the tier itself |
| A3 | Basalt's 0.2.0 **starting profile** ("learned from varied prompts") | data/profiles/qwen4exp-48x512.prof (7a60b7a3) | different file: ours shares 68 % of the top 4,585 pairs | 0-2 % (first requests, topic changes; A1 shrinks it) | **small: prepend "STRP" to the file, point `--expert-profile` at it** | rounding-level (placement) | it was learned on Basalt's prompts; ours may suit our workloads better - A/B on the screen; MIT data file |
| D1 | **`--spec 8`** (Basalt's default since c4409d3e: up to 7 drafts; ours 7 = up to 6) | c4409d3e | a setting | 0-2 % on the screen (A-edit / B-write average 4.7-5.1 drafts per MTP window, so the 6-draft cap binds there); ~+5 % on struct-like text (struct accepts 96 %) | small: one flag | **distribution-exact** for sampled requests (our exact sampling); rounding-level for greedy (other window widths) | the cost gate's table was fitted at spec 7: re-check its chi-square cases |
| G1 | **PDL** across the window (Basalt: always, 201-274 launches per window) | pdl.hpp, 88 call sites | **present, off**: `STRATA_DF_PDL=1` (quantizations + dense projections, 15 sites; verify.cpp:1273-1281) | 1-3 % (the GPU-side half of the window is chains of small kernels; ~1-2 us per serialized boundary) | **small: one env var** (more sites later: medium) | **bitwise** ("every value is the same") | opt-in upstream: never measured on sm_120 by us; graph capture must still succeed |
| G2 | graph **node priorities** for side branches | lifecycle.cpp:279-302, capture.cpp:30-81 | **present, off**: `STRATA_GRAPH_PRIO=1` (verify.cpp:216-222, 1070-1083) | 0-2 % (reporter: +1.8 % on an sm_80 card) | small: one env var | **bitwise** | it puts our shared expert lowest (Basalt: highest); check both |
| G3 | the plan wait folded into the plan copy | (Basalt has no plan wait: G4) | **present, off on sm_120**: `STRATA_FUSE_WAIT=2` (verify.cpp:415-437; Turing default, +0.6..1.4 %) | 0-1 % | small: one env var | **bitwise** | `=1` (rows too) was -1.5 % on Turing: use 2 |
| G4 | **device-planned MoE tail**: the device classifies the layer from its residency table, rings the host as soon as the ids are out, the hit experts start without the host's plan, the combine waits on the CPU word itself | record_moe.cpp:24-213; dec_moe.cuh:580-648, 2193-2238; native_moe.cu:199-215; expert_resources.cpp:30-47; 87ed79b2, 5d8704d9 | partial: `resident_plan` + the `skip_` protocol exist for the all-resident case (`STRATA_VERIFY_DEVICE_PLAN`, expert_source.cpp:5045) | 1-3 % (the pool starts ~12 us per layer earlier without the host's plan step, plus the doorbell during the read; 3 wait kernels and ~10 nodes fewer per layer) | medium-large (the PCIe share has to move to the device too, or be dropped) | **bitwise** on our grouped kernels (same plan and combine order); a PCIe-share change is rounding-level | Basalt's glue kernels themselves would need a cross-tree parity test - keep ours |
| G5 | the GPU **works during the CPU wait**: (a) L2 prefetch of the next layer's projection weights, (b) lazy GDN commit with a finisher | record_moe.cpp:64-95; commit.cpp:94-197; verify_kernels.hpp:55-74 (4d9b608c, abccf9af) | absent (commit serialized on `cs_`, verify.cpp:3646-3690) | 1-3 % (our GDN qkv + out ~2.4 ms per window at ~30 % of DRAM bandwidth; the commit itself <= 0.15 ms) | small-medium for a stand-alone prefetch branch forked after the doorbell; medium for the lazy commit | **bitwise** | the hit experts stream ~50 MB per layer through the 64 MB L2: the gain must be measured |
| G6 | **MTP chain as one conditional graph** (device decides to continue), early return, evict-first head loads, K/V append beside the query projection | conditional.cpp, draft.cpp:39-130, forward.cpp:324-339 (35966539, 09e317b3, b063ffd4) | absent: host wait and a graph launch per step, head in ~5 launches (mtp.cpp:1264-1305, 1792-1810) | 0.5-2 % (our drafting is 1.1-1.3 ms per window) | medium | **bitwise** with our drafter's arithmetic (Basalt's 2-bit draft screen: distribution-exact only) | conditional nodes need CUDA 12.4+ (we build with 13.3) |
| G7 | **shared expert fed by the FFN read** (gate dot and q8_1 rows from the read, gate applied in the combine, two streams, high priority) | record_layer.cpp:299-303, 409-436; shared_expert.cu:128-143 (83ffa621) | absent: 7 kernels at default priority (verify.cpp:2154-2196); `STRATA_LFUSE`'s gated combine is a related piece | 0-1 % (mostly hidden behind the host wait today) | small-medium | **bitwise** (IEEE product, never fused into the sum) | low priority |
| G8 | QSA: block scoring skipped when every selection is the identity; five to eight queries as two rows of four; the query projection's gate rows beside the attention | qsa_select.hpp:31; a9937aed; 9718298c, qsa_mid.cu | absent | 0.5-1 % on the screen (more at 54K: our context term is +1 ms per window there) | medium | bitwise (scores and tiles unchanged); `qsa_mid` uses dense_tc tiles: rounding-level | a part is the KV streaming, not the scoring - measure first |
| G9 | **GDN mid chain + `dense_tc`** (one persistent kernel for windows of 1-4 rows; int8 tensor-core projections) | mid_chain.cu, dense_tc.cu, record_gdn.cpp:76-96, record_layer.cpp:161-233 | absent (~8-10 kernels per GDN layer) | 2-4 % (our GDN mixer is ~2.9 ms per window; it is the GPU part on the critical path before the router) | **large** | **rounding-level** (dense_tc is "not their bits"; on 84 SMs another out-projection order) | full KL gate; Basalt's unified-kernel notes warn about register spills, co-residency and harness/engine mismatch |
| G10 | one queue kernel for the hc read + router + top-10 + q8_1 + shared gate dot + ring counters | hc_fused.cu (int8 only) | absent; ours is `GR_FORK` + separate router | 1-3 % if re-done in BF16 (our hc reads + router ~3.2 ms per window, the largest GPU block) | **large** (new BF16 kernel) | rounding-level at best | Basalt's version exists only for the lossy int8 copy |

Not in the table: Basalt's int8 hc copy, two-stage verify head, `--route-prior`, `--route-tail-skip`, relaxed drafting
(all lossy); its PCIe-staged batch misses (batch windows only); its peer-card and layer-split work (not one card);
"once-routed" promotions and cross-layer ranking (need one blob size over all layers; our pack has 7).
Cross-check of a sub-report: `STRATA_ROUTE_TAIL_SKIP=7` is Strata's server default when experts miss the cache
(generate.cpp:11164-11174), but the solo arm pins it to 0 (24 of 24 engine environments checked on 11-03), so it does
not explain any of the CPU-share difference.

## 4. Ranking (gain per effort) and the gap that would be left

| rank | items | kind | est. gain together | effort | gate |
|---|---|---|---|---|---|
| 1 | G1 `STRATA_DF_PDL=1`, C1 `STRATA_IQ_GATHER=1`, G2 `STRATA_GRAPH_PRIO=1`, G3 `STRATA_FUSE_WAIT=2` | env switches already in the tree | +2-6 % | one gap, ABAB | exact7 + byte-identical logits (bitwise by construction; C1's one-token path checks itself against ggml) |
| 2 | A1 adaptive cadence (`--adapt-every 1`, `--adapt-decay 0.85`, no ADAPT_LAG, `STRATA_ADAPT_OVERLAP=1` + `_RESIDENT=1`), A3 Basalt's profile, D1 `--spec 8`, C2 `STRATA_IQ_MT_MIN=1` | settings | +2-6 % (A1 most; mostly A-edit, R4, cold starts) | one gap, ABAB, one change at a time | KL rule (placement / window width / lone-token rounding); D1 also the chi-square cases |
| 3 | C4 unpinned pool (a flag), G5a L2 prefetch of the next layer's projection weights on a side branch forked after the doorbell | small code | +1-4 % | small | bitwise |
| 4 | C3 one pool batch per layer, G4 device-planned MoE tail, G6 conditional-graph draft chain, G5b lazy GDN commit, G7 shared expert fed by the read | medium code | +3-7 % | medium each | bitwise (G4: keep our grouped kernels and the PCIe rule on the device) |
| 5 | G9 GDN mid chain + dense_tc, G10 a BF16 queue kernel for the hc read + router, G8 QSA changes, A2 three-step rounds, C5 CPU warm-up | large / low value | the rest | large | KL rule (G9, G10) |

**Remaining gap.** Lossless Basalt on our screen is ~147-149 tok/s against our 134.5 (+9-11 %). Ranks 1-3 are
estimated at +4-10 % together (not additive: C1/C2 and A1/A3 overlap). That would leave **~1-6 %**. With rank 4 the
estimate covers the rest of the exact engine gap. What would still separate the two engines is in rank 5, mainly the
GDN mixer, whose rounding changes, and Basalt's int8 hc reads, which we do not take.

The error bars are wide. Every gain above is derived from a 33-request fit and a 10-10 profile of an older build, and
none is measured on P028x. Two of the cheap items can also come out negative: gathers on Zen 5, and OVERLAP_RESIDENT
competing with the CPU pool for RAM bandwidth. Rank 1's switches are cheap enough that their measurement is the
estimate.

## 5. What to measure first (when Karl schedules a gap)

1. **A solo-arm breakdown, no code change.** Run x28h-solo through the 9-workload screen once with
   `STRATA_DECODE_TIMING=1` (per request: adapt wait, GPU-reach wait, per-layer host plan / CPU, stage,
   commit, draft, CPU experts / VRAM hits / PCIe per layer-window, **swaps/window**). Run it once more with
   `STRATA_VERIFY_PROFILE=1` as well (GPU stage split; it changes the graph, so use it for the split, not for rates).
   About 20 min.
   - This turns sections 1.3 and 2.1 into measurements.
   - It shows whether A-edit's low GPU share is the adaptive cadence or the refill after the prompt loan.
   - If a Basalt gap is allowed: `--decode-timing --wait-stats` on the same prompts.
2. **Rank 1 ABAB** on the screen, then rank 2 one setting at a time. Use the usual harness (abarm.sh), 3 passes, and
   the same sampling.
3. **Only then code work.** Code work waits until item 7 and gap 17 are done (HEAD2HEAD-PLAN catch-up list). The
   first code item would be whichever of C3, G5a or G4 matches the largest measured wait.

## 6. Measured (gap 18, 11-03 12:14-12:22)

P028x on the 5080 alone, one 9-workload screen pass per arm:
- `configs/x28h-solo-dtime.json` = x28h-solo + `STRATA_DECODE_TIMING=1`. Client geomean 134.2 (11-03 solo: 134.5), so
  the logging costs nothing and the split below is the served solo arm's.
- `x28h-solo-vprof.json` = + `STRATA_VERIFY_PROFILE=1`. It printed **no stage table**: Strata prints the profile only
  inside the `STRATA_DECODE_TIMING` block (generate.cpp:17339-17378). So that arm gave rates only (131.8; the
  profile stamps cost ~2 %). Where a stage split is needed below, r18's (10-10, older build) stands in. Its serial GPU
  stages add up to 8.9 ms at T 3.8, today's measured serial segment.
- Parsed with `scratch-study/dtime.py` (log reading only).

### 6.1 Where a P028x solo window goes (measured; 5,442 windows, warm-up left out)

| part | ms / window | ms / token | share |
|---|---|---|---|
| **GPU serial segment** ("GPU-reach wait": from a layer's CPU rows to the next layer's doorbell = combine, hc reads, router, GDN / QSA mixer, quantizations) | 8.91 | 2.56 | 34.9 % |
| **CPU experts** (the pool, host thread included) | 13.43 | 3.85 | 52.6 % |
| **drafting** (MTP) | 2.29 | 0.66 | 9.0 % |
| window tail (head, sampling, readback, launch: verify time outside the layers) | 0.91 | 0.26 | 3.6 % |
| host plan / staging / commit / adaptive wait | 0.08 / 0.01 / 0.01 / 0.01 | 0.03 | 0.4 % |
| **window** (T 4.44 columns, 3.49 tokens) | **25.54** | **7.32** | |

| request | windows | columns | tokens/w | ms/w | GPU serial | CPU experts | draft | tail | ms/token | distinct CPU experts per layer | GPU + PCIe share | swaps/w |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| warm-up | 138 | 3.95 | 2.78 | 23.77 | 10.04 | 10.51 | 1.96 | 1.26 | 8.55 | 5.65 | 80.0 % | 23.7 |
| W1-think | 780 | 3.82 | 2.95 | 18.71 | 8.60 | 7.37 | 1.88 | 0.86 | 6.34 | 4.44 | 86.3 % | 23.8 |
| W1-cont | 179 | 5.32 | 4.19 | 28.90 | 9.19 | 16.33 | 2.43 | 0.95 | 6.90 | 9.45 | 76.3 % | 24.1 |
| W2-code | 875 | 4.69 | 3.51 | 24.78 | 8.78 | 12.87 | 2.22 | 0.91 | 7.06 | 7.49 | 78.6 % | 24.0 |
| W3-research | 499 | 5.06 | 4.10 | 30.33 | 9.29 | 17.33 | 2.77 | 0.94 | 7.40 | 9.97 | 72.1 % | 23.9 |
| A-edit | 284 | 4.88 | 4.00 | 31.61 | 8.92 | 19.44 | 2.30 | 0.95 | 7.90 | 11.06 | 66.9 % | 24.0 |
| B-write | 700 | 4.23 | 3.18 | 23.34 | 8.70 | 11.71 | 2.04 | 0.89 | 7.34 | 6.80 | 78.6 % | 24.0 |
| R1-verify20k | 963 | 3.86 | 3.19 | 24.48 | 8.67 | 12.72 | 2.20 | 0.89 | 7.67 | 7.39 | 75.0 % | 24.0 |
| R1-cont | 105 | 5.96 | 5.53 | 33.43 | 9.87 | 19.47 | 3.09 | 1.00 | 6.05 | 11.18 | 73.6 % | 23.8 |
| R2-report54k | 746 | 4.38 | 3.30 | 26.98 | 9.24 | 14.28 | 2.55 | 0.91 | 8.18 | 8.27 | 74.0 % | 24.1 |
| R3-extract5k | 200 | 5.74 | 4.82 | 32.99 | 9.56 | 19.81 | 2.64 | 0.98 | 6.84 | 11.33 | 73.5 % | 24.0 |
| R4-agent33k | 111 | 4.62 | 3.32 | 29.52 | 9.15 | 16.80 | 2.64 | 0.93 | 8.89 | 9.63 | 70.8 % | 24.2 |

The cost functions behind it (fits over the 11 requests, each on its own measured component):
- **GPU serial = 6.50 + 0.51 x columns + 0.0093 x context (K tokens) ms.** It is nearly flat: 8.6-9.9 ms in every
  request (~186 us per layer). The context adds only +0.5 ms at 54K. KV streaming reads at most 2.3 MiB per window
  from RAM, even at 54K.
- **CPU = 1.80 ms per distinct CPU expert per layer-window, i.e. 37.6 us per expert.** A second token on the same
  expert costs only 1.9 us. There are 1.34 entries per distinct expert, so most CPU groups are single tokens.
  Per window that is 500 entries (374 distinct) at 26.9 us per entry. The pool moves 46-55 GB/s of expert bytes from
  16 threads, below the 80 GB/s of RAM bandwidth Basalt's probe measured on this box.
- **The PCIe share (168 entries per window) costs no visible window time.** It runs inside the CPU phase.
- **Drafting = 0.94 + 0.39 per draft step ms** (0.67 ms per step on average). A step reads ~200 MB (head 85 MB, draft
  layer ~115 MB): ~0.2 ms at the card's bandwidth. So the per-step part is ~2x its bytes, and the 0.94 ms fixed part (the
  round's catch-up and launches) is what Basalt's 10-31 MTP commits target.
- **The adaptive tier sits at its cap in every request**: 23.7-24.2 swaps per window = 96 per round, one round every 4
  windows. It costs 0.01 ms of wait per window.
- **A-edit was 126.8 tok/s here (1,136 tokens, 66.9 % GPU + PCIe share)**, against 108.7 on 11-03 (329 tokens). The
  penalty of a short reply after a long prompt comes at the start of the reply, and a longer reply spreads it out.

### 6.2 The fit (section 1.3) against the measurement

| term | fit, P028x solo 11-03 | measured, gap 18 |
|---|---|---|
| fixed per window | 7.63 ms | 7.96 ms (serial 6.50 + draft 0.55 + tail 0.91) |
| per column | 1.52 ms | **0.90 ms** (serial 0.51 + draft 0.39) |
| per miss entry | 15.7 us (CPU + PCIe) | **26.9 us per CPU entry** (37.6 per distinct expert); PCIe entries ~0 |
| per 1K context | 0.024 ms | 0.009 ms |

The totals were right; the split was not. Columns and CPU entries rise together (correlation 0.68 over our requests,
0.83-0.88 over Basalt's), so the fit gave the columns time that belongs to the CPU tier. Point 3 of section 1.3 ("per
miss entry Strata is not slower") was this artifact, and so was section 2.1's "~14.9 ms GPU side". Measured, our
non-CPU part is 12.1 ms (8.9 serial + 2.3 draft + 0.9 tail).

### 6.3 Basalt's split, re-inferred (Basalt has no timing log in our runs)

**Method.**
- Basalt's per-request window time was refit with its non-CPU cost per column held at our measured 0.90 ms.
  Values from 0.5 to 1.3 move the result by about +-1 us per entry.
- The same method on our 11-03 requests gives 22-24 us per CPU entry against the measured 26.9, about 15 % low.
  Basalt's figure is corrected by the same factor.

**Result.**
- **Basalt exact head**: about 22 us per CPU entry (19-23) x 591 entries = **~13.0 ms of CPU** (11.1-13.5). The rest
  is **~8.5 ms** (8.0-10.4).
- Adding 0.7-1.0 ms for BF16 hc gives a **lossless Basalt window of ~22.3 ms: ~9.3 non-CPU + ~13.0 CPU**. Ours is
  25.5 = 12.1 + 13.4.

**What the gap is made of.**
- **About 2.8 ms (range 1-3.3) of the ~3.2 ms lossless gap per window is on the non-CPU side.** That is the serial GPU
  segment, drafting and the window tail.
  - Drafting is the clearest piece. Ours costs 2.29 ms per window. Basalt reports 0.45 ms per window on a 5090 (prose,
    ~1.7 drafts), which is perhaps 0.8-1.2 ms on our card at ~3.3 drafts. So drafting is about 1-1.5 ms of the gap.
  - The serial segment plus the tail is the other ~1.2-1.7 ms. r18's split of that segment (proxy): hc reads +
    router 3.2, GDN mixer 2.9, QSA 1.2, combine / copies 0.5, plan / PCIe waits 0.5 ms; head 0.64 ms in the tail.
- **The CPU side is about even (~0.4 ms).** Basalt's pool looks ~15-30 % cheaper per entry (22 vs 26.9 us). That fits
  its AVX-512 rows for single tokens, the code difference in section 2.3. But Basalt computes 18 % more CPU entries,
  because it has no PCIe share. At our miss counts, our PCIe share is worth ~2.5 ms per window.
- **Window shape: we have ~7 % more misses per column** (150 vs 140), worth ~0.9 ms of CPU per window. That is the
  adaptive tier's part.
- **Revised summary.** Section 0 said "~1.2-1.5 ms exact engine work + ~2 ms window shape". The measurement turns that
  into **~2.5-3 ms exact on the GPU / drafting side + ~1 ms of window shape**. Our slower CPU tier (per entry) is
  mostly balanced by the PCIe share.

### 6.4 What the timing logs say about the four switches (gap 18: no gain on the two-card form)

- **`STRATA_FUSE_WAIT=2` (G3) and the device-planned tail (G4)** shorten the GPU's wait for the host's plan. The
  measured host plan is 0.08 ms per window (~2 us per layer), and staging and commit are 0.01 ms each. There is
  nothing for them to remove, which fits the -0.87 %. G4 drops to <= 1 %; only its earlier doorbell during the hc read
  would remain.
- **`STRATA_DF_PDL=1` and `STRATA_GRAPH_PRIO=1` (G1, G2)** can only shorten the serial GPU segment or reorder side
  branches.
  - The serial segment has the same absolute size on two cards (~40 % of a 22 ms window). So the two-card +0.15 %
    (noise 3.9 %) bounds PDL's saving at <= ~0.9 ms per window, most likely ~0.
  - The side branches (VRAM hits, shared expert, PCIe groups) run inside the CPU phase on one card, so priorities
    cannot shorten the window.
  - Neither needs a single-card retest unless a stage profile shows launch gaps.
- **`STRATA_IQ_GATHER=1` (C1)** is the only one the logs point at, and only weakly.
  - The CPU phase is 52.6 % of a window on one card, against ~37 % on two (11-03 ON arm: 306 CPU entries x 26.9 us =
    8.2 of 22.3 ms).
  - The pool runs below RAM bandwidth, so a faster decode can show.
  - The two-card +0.80 % (noise 3.2 %) implies a CPU-phase gain of ~2 % (-6 to +11 %), i.e. ~+1 % (-3 to +6 %) on one
    card.
  - Worth one single-card A/B, together with C2 (`STRATA_IQ_MT_MIN=1`). C2 also takes the single tokens of the 20
    IQ2_S layers off ggml's dot, where Basalt differs. Not worth a test on its own.

### 6.5 The candidates re-ranked with the measured numbers

| rank | item | what the measurement says it targets | est. gain, one card | effort | exactness |
|---|---|---|---|---|---|
| 1 | A1 adaptive cadence (`--adapt-every 1`, `--adapt-decay 0.85`, no ADAPT_LAG, `STRATA_ADAPT_OVERLAP=1` + `_RESIDENT=1`) | the tier is at its cap in all 12 requests (24 swaps per window, wait 0.01 ms); 7 % more misses per column than Basalt; each distinct CPU expert per layer-window costs 1.8 ms | +2-4 % | settings | rounding-level (placement) |
| 2 | G5a: L2 prefetch of the next layer's projection weights during the CPU phase, plus our own extension: the next layer's hc matrices | the serial segment is 8.9 ms (35 %), and the GPU idles ~10 of each window's 13.4 CPU ms (r18: hits + shared ~3 ms) | +2-5 % | small-medium | bitwise |
| 3 | G6: the draft chain (one conditional graph, early return, evict-first head, the round's overlaps) | drafting is 2.29 ms (9 %): 0.94 fixed + 0.39 per step; ~0.2 ms of bytes per step | +2-4 % | medium | bitwise (drafter arithmetic kept) |
| 4 | C1 + C2, one single-card A/B | CPU phase 52.6 %, 37.6 us per distinct expert, pool below RAM bandwidth; Basalt ~15-30 % cheaper per entry | -2 to +5 % | settings | bitwise (C1) / rounding-level (C2) |
| 5 | C3: one pool batch per layer | the CPU cost has no visible per-layer intercept (-0.6 ms in the fit), so barrier overhead is small | 0-2 % | medium | bitwise |
| 6 | A3 Basalt's profile; D1 `--spec 8` | first requests and topic changes; tool-call windows near the draft cap | 0-2 % each | settings | rounding-level / distribution-exact |
| 7 | G9 GDN mid chain + dense_tc; G10 a hc + router queue kernel in BF16 | the serial segment's two largest blocks (r18: GDN mixer 2.9, hc reads + router 3.2 ms) | 2-4 % each | large | rounding-level |
| 8 | G7 shared expert, G8 QSA (context: +0.5 ms at 54K), C4 unpinning, C5 warm-up | small measured targets | <= 1 % each | small-medium | bitwise |
| 9 | G4 device-planned tail, G1 PDL, G2 GRAPH_PRIO, G3 FUSE_WAIT | the waits they remove are measured <= 0.1 ms per window, or bounded by gap 18's two-card A/B | ~0 | - | stay off (as Karl recorded) |

**Remaining gap.** Lossless Basalt is ~22.3 ms per window against our 25.5 (about +11-14 %). Ranks 1-4 are estimated
at +6-10 % together, which would leave ~2-5 %, mostly in rank 7 (the GDN mixer and the hc-read structure). The error
bars stay wide on Basalt's side: its split is inferred, not logged.

### 6.6 Next measurement (if Karl wants the inference replaced)

1. **One more profile pass**, ~4 min, with **both** `STRATA_DECODE_TIMING=1` and `STRATA_VERIFY_PROFILE=1`. That
   gives today's stage split of the 8.9 ms serial segment and of drafting, which ranks 2, 3 and 7 depend on.
2. If a Basalt gap is allowed: `basalt serve` with `--decode-timing --wait-stats` on the same screen. That replaces
   section 6.3.
3. Then rank 1 (settings, KL gate) and rank 4 (one single-card A/B).
