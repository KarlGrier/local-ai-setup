# Gap 19 prep: our port's 28 commits next to the GDN prompt paths and PF_HC_REGION

Read-only, 11-04. Source: branch `r22-port0210` @ fdd2fffa8 (worktree `strata-r22p0210`) against tag v0.2.10 (ffa80d731),
read with `git -C strata-r22p0210 log / show / diff v0.2.10..HEAD`, and the stock tree `strata-v0210stock`. Nothing was
compiled or run. Gap 19 decides whose failure each item is. This file lists the suspects if the answer is OURS.

## Where the paths live in v0.2.10

- **STRATA_GDN_TC** (opt-in in the engine).
  - `src/prefill/kernels.cu`: `gdn_recurrence()`'s dispatch. `tc` applies for chunks of `kGdnTcMin` (128) tokens or
    more. It calls `gdn_rec_tc` and reads `STRATA_GDN_TC_TILES`, `_FUSE` and `_NP`.
  - `src/prefill/gdn_tc.cuh` holds the scan; `include/strata/prefill/gdn_probe.hpp` the probe.
  - The prompt only: nothing in `src/core/verify.cpp` or `mtp.cpp` reads it.
- **STRATA_GDN_CONVL2** (0 on CUDA; the AMD table only).
  - `src/prefill/kernels.cu`: `gdn_conv()`. Value 1 runs `gdn_conv_l2_kernel`; value 2 runs `gdn_conv_w_kernel` +
    `gdn_conv_hist_kernel`. It applies only when T > `CONV_TILE`.
  - The prompt only.
- **Who calls them:** `src/prefill/prefill.cpp`, the GDN half of a prompt layer. There are two copies: the main path at
  about lines 4110-4126 and the layer-split path at about 7386-7395.
- **The served default:** `serve/server.py` `gdn_stack_env` (inside `child_env`) sets TC=1 and CONVL2=2 with setdefault,
  on Linux, Qwen3.8, CUDA.
- **STRATA_PF_HC_REGION** (opt-in).
  - `src/prefill/prefill.cpp`: `pf_hc_region()`, `hc_set_bytes()` and `Prefill::carve()`. With the switch on, xn16 / lo /
    lo16 / gated and the BF16x2 lows are taken in the shared region (the region = max of the GDN / QSA / MoE / HC sets).
    The switch also prints a start line.
  - **Its reach is wider than the kernels.** The prompt path's own bytes shrink, so `src/program/generate.cpp` lends fewer
    expert-cache slots ("prompt path borrows N cache slots"; the CLI near line 19326, serve near 10571-10587). With the
    prompt CPU share on (`prefill.cpp` `cpu_share_*`, `Prefill::arm_cpu_share`; `STRATA_PREFILL_CPU_SHARE` 0.4,
    `_MAX` 1792 in our configs), the split of a short prompt's experts between the CPU and the GPU then changes.
- **The prompt v2 path (ours, for context):** `src/prefill/moe_fused_iq.cu` (the v2 kernels), `moe_fused.cu`
  (`group_bytes` + 64 counter bytes when v2 is asked for), and the start line in `prefill.cpp` `mmq_plan()`.

## What gap 17's own logs already show (exact7, `g19_rules.py hcrdiag g17-p210a g17-hcr`)

The four items that differ are exactly the 136-token prompts that ran with the CPU share. Their loan fell from 260 to
252 slots, and their CPU-expert count moved (3510 -> 3514, 3447 -> 3456). The three long prompts (share 0.00) are
identical, even though their chunk size moved (14336 -> 16384) and their resident count moved too.

So the bits change through **placement**, not through the HC kernels. None of our 28 commits touches that chain
(`carve`, `hc_set_bytes`, the loan sizing, the CPU share), so stock is expected to do the same. Gap 19's mechanism table
shows it for stock. `G19_HCR_SHARE0=1` would confirm it in the same gap: the pair with `STRATA_PREFILL_CPU_SHARE=0` should
be 7/7.

## The 28 commits

"Prompt" means the commit changes code that runs in the prompt pass. "Same file" means it shares a file with the paths
above, but not a function.

| # | commit | what | files | GDN paths | HC region / loan / CPU share | prompt arithmetic |
|---|---|---|---|---|---|---|
| 1 | 5765aa2bc | --side-stash | generate.cpp (serve) | no | no | no |
| 2 | 308a52cc5 | --chat-cache | generate.cpp (serve) | no | no | no |
| 3 | addca661b | chat cache keeps the prefix checkpoint | generate.cpp (serve) | no | no | no |
| 4 | 86570881b | web search switch | serve/server.py, websearch.py, web app | no (not `child_env` / `gdn_stack_env`) | no | no |
| 5 | 7a4afae36 | web search date / host | websearch.py | no | no | no |
| 6 | c1a2077bb | STRATA_ROUTER_Q8K | expert_source.{hpp,cpp}, verify.{hpp,cpp}, elementwise.{hpp,cu} | no | no (the decode doorbell; the prompt CPU share does not use it) | no (decode, incl. the yardstick's first window) |
| 7-9 | 61908aeae, e49584cfe, dafa1a765 | Q8_K rounding, bsums, NaN | elementwise.cu | no | no | no (decode) |
| 10 | 785b1a1f7 | #619 nextn layers | native_dense.cpp, tools/iq_pack.py | no | no | no (architecture check) |
| 11 | d7831da85 | model_check.py | serve/ | no | no | no |
| 12 | 433d05bc0 | chat cache dropped after non-finite | generate.cpp (serve) | no | no | no |
| 13 | 109ecc0b9 | `</think>` in a code fence | serve/frontend.py | no | no | no |
| 14-15 | 302e86ef2, e9bf127f4 | Tavily / Exa fallback | websearch.py | no | no | no |
| 16 | 8bda45013 | chat_drop owner tag | server.py, generate.cpp (serve) | no | no | no |
| 17 | 4ad866b9a | answer_room continuation | server.py, generate.cpp (serve) | no | no | no |
| 18 | f16db7c72 | **STRATA_GR_FORK** | fused_gr.{hpp,cu}, xor_scatter.cuh, verify.cpp, mtp.cpp | no | no | **same file**: fused_gr.cu also holds the prompt's HC read (`gr_mix_r`, `gr_write_norm_rs`), but the fork hooks only `fused_gr_read_multi_slice` (decode windows) |
| 19 | c7cf663d6 | the fork's own scratch | verify.{hpp,cpp} | no | no | no (decode) |
| 20 | 3ab636d54 | patch guards | patch_guard.*, fused_gr.cu (+2), qsa_prompt_attn.cu (+3), generate.cpp | no | no | no (geometry getters only; checks at start) |
| 21-22 | 8a0cedc81, b92a2add3 | guard fixes | patch_guard.* | no | no | no |
| 23 | 65837e059 | **STRATA_PREFILL_V2** | moe_fused_iq.{hpp,cu} (+512), moe_fused.{hpp,cu}, prefill.cpp (+35), patch_guard.*, tests | no (no GDN function) | **sizing chain**: `group_bytes` + 64 bytes when v2 is asked for, inside `moe_bufs`' max (no slot moved: the off arms' loans match, 260 = 260) | **yes**: the MoE half of the same prompt layers and chunks |
| 24 | d8aa76f3d | STRATA_SPEC_EXACT | sampler, verify, mtp, generate.cpp | no | no | no (sampled decode) |
| 25-26 | eddc0c583, 0fe78a39b | STRATA_COST_GATE | cost_gate.hpp, mtp.cpp, generate.cpp | no | no | no (draft length) |
| 27 | 0df5f4c45 | STRATA_DRAFT_CUM | draft_cum.hpp, mtp.cpp, generate.cpp | no | no (its `draft_cum_place` only reads where the experts are) | no |
| 28 | fdd2fffa8 | **v2 takes the current kernels' term** | moe_fused_iq.cu, test | no | no | **yes** (v2's arithmetic; since then v2 on = off bit for bit on long40 with GDN off, gap 16: 0 of 40) |

**No commit touches** `src/prefill/kernels.cu`, `gdn_tc.cuh`, `gdn_probe.hpp`, the GDN half of `prefill.cpp`,
`pf_hc_region` / `hc_set_bytes` / `carve`, the loan sizing, or the CPU share.

## The candidates, ranked, if gap 19 says OURS

### The GDN stack (0, 0t, 0v)

The port's arms carry our six switches; stock's arms do not. Two checks would split the suspects, each one
pf_yardstick (~9 min):
- **`P0210x-h-off` + GDN:** the port's build with every switch of ours off. Does the build or the switches cause it?
- **`P0210x-h-nov2` + GDN:** v2 off.

1. **v2 (65837e059 + fdd2fffa8).**
   - The only commits with prompt arithmetic: the MoE half of the same layers and chunks.
   - Bit for bit with v2 off, but that was checked only with GDN off.
   - The GDN half reads that MoE half's output through the HC read.
2. **GR_FORK (f16db7c72 + c7cf663d6).**
   - The yardstick's first-token row comes out of the first decode window, which reads the GDN state the prompt left.
   - The fork's other summation order meets the TC state there.
   - Test: GR_FORK=0 + GDN.
3. **ROUTER_Q8K (c1a2077bb, 61908aeae, e49584cfe, dafa1a765).** The decode doorbell's Q8_K rows in that same first window.
4. **SPEC_EXACT / COST_GATE / DRAFT_CUM (d8aa76f3d, eddc0c583, 0fe78a39b, 0df5f4c45).** The first window's drafting.
   Unlikely: the row is the window's first.
5. **The rest:** serve-side, guards, #619. No prompt or decode arithmetic.

### PF_HC_REGION (3)

The mechanism above is upstream's own (the loan and the CPU share). Stock showing 7/7 would therefore be a surprise. If it
does, the suspects are:
1. **v2's +64 bytes in `group_bytes`:** the only change of ours in the sizing chain the HC region acts through. Compare the
   two pairs' "borrow" column in decision.txt.
2. **ROUTER_Q8K / GR_FORK:** the decode that follows a moved prompt.
