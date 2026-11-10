<!-- RETIRED 11-05 (Karl): the GDN issue is CLOSED, not held - the decode-path check (results/r23/decpath/decision.txt) put every prompt path, the decode reference included, in the same scatter (mean KL to the decode path 0.14-0.16; the 2-row reference vs true 1-row windows |dNLL| 0.37-0.48), and stock's 0.21 on ldrsyn20k is inside it. Not to be posted. Reopen only if the v0.2.11 port gates show something new (results/BACKLOG-1027.md G2). -->
<!-- DRAFT - NOT POSTED. Delete this line before posting. Fill the PLACEHOLDER section first, or post without it and add it as a comment. -->

**Title:** [Engine] v0.2.10: STRATA_GDN_TC=1 / STRATA_GDN_CONVL2=2 (on by default from serve on Linux CUDA) are not rounding-level on an RTX 5080 (sm_120, 84 SMs): first-token KL outside the rounding spread on Qwen3.8-Flash-Next IQ3_S

---

## What happens

On an RTX 5080 (sm_120, 84 SMs, 99 KB of opt-in shared memory a block), turning on the two GDN prompt paths that `serve/server.py` enables by default (`STRATA_GDN_TC=1`, `STRATA_GDN_CONVL2=2`) changes the first-token distribution after long prompts more than two rounding-only switches do on the same check. It holds for the pair and for `STRATA_GDN_TC=1` alone. We see it on an unmodified v0.2.10 build. We also see it on our own patched build of v0.2.10, where `STRATA_GDN_CONVL2=2` alone does it too. None of our patches touch `src/prefill/kernels.cu`, `src/prefill/gdn_tc.cuh` or the GDN half of `src/prefill/prefill.cpp`.

We cannot say the paths make the output **worse**. Most of the difference comes from a few prompts. On the prompt that moves most, the paths give the text's real next token. The default path does not (details below). This report is about "not rounding-level on this card", which `server.py`'s qualification note suggests it should be. It is not a claim that the paths are wrong.

## Method

- 40 prompts of 2,048-32,768 tokens: cuts of 8 long chat-formatted texts (documents, code, a synthetic agent-style transcript, a repetitive text).
- One `strata --serve` engine per arm. Each prompt is one request with no prompt cache. We keep the full-vocabulary logits of the first window (`STRATA_DUMP_FIRST_LOGITS`) and compute KL(off || on) per prompt.
- This is the method of `tools/quant_quality.py prompt` / `pcompare`, with longer prompts. The settings are the ones that tool fixes: `--expert-cache 1 --adapt-every 100000 --pcie-frac 0 --suffix-draft 0 --prompt-cache 0 --kv fp16 --prefill auto`, `STRATA_PREFILL_CPU_SHARE=0`, `STRATA_ROUTE_TAIL_SKIP=0`. Every prompt expert runs on the GPU prompt kernels.
- **Yardstick:** two switches that only change rounding, each measured the same way against the same build with the switch at its default:
  - `STRATA_PF_FUSED=0`: the unfused prompt expert kernels.
  - `STRATA_PREFILL_CPU_SHARE=0.4`: 40 % of the prompt expert rows on the CPU.

  We measured them on an earlier build of the engine (v0.2.1-based, 5080 alone), with the same prompts and settings.

## Numbers

**Same build, one setting changed (40 prompts):**

| Change | KL mean | median | p90 | rows KL > 0.5 | rows KL > 1 | max | top-1 changed |
|---|---|---|---|---|---|---|---|
| *rounding ref:* `STRATA_PF_FUSED=0` | 0.162 | 0.009 | 0.366 | 4 | 3 | 2.46 | 5 / 40 |
| *rounding ref:* `STRATA_PREFILL_CPU_SHARE=0.4` | 0.365 | 0.011 | 0.215 | 3 | 3 | 9.76 | 5 / 40 |
| **v0.2.10 stock:** TC=1 + CONVL2=2 vs both 0 | **0.648** | 0.009 | **1.031** | **7** | 4 | 14.27 | 4 / 40 |
| **v0.2.10 stock:** TC=1 alone vs both 0 | **0.561** | 0.015 | **0.553** | 5 | 2 | 15.37 | 7 / 40 |
| v0.2.10 + our patches: TC=1 + CONVL2=2 | 0.545 | 0.013 | 1.121 | 5 | 5 | 13.57 | 7 / 40 |
| v0.2.10 + our patches: TC=1 alone | 0.665 | 0.007 | 1.082 | 5 | 5 | 14.30 | 6 / 40 |
| v0.2.10 + our patches: CONVL2=2 alone | 0.500 | 0.010 | 0.276 | 3 | 2 | 14.06 | 8 / 40 |

**Against one fixed reference build:** the two rounding references define the bounds: KL mean <= 1.10 x the larger reference's, p90 <= the larger reference's, rows KL > 1 <= the larger count + 1, top-1 matches >= the lower reference's - 1.

| Stock v0.2.10 arm | KL mean | p90 | rows KL > 1 | top-1 same | within the spread? |
|---|---|---|---|---|---|
| bounds | <= 0.401 | <= 0.366 | <= 4 | >= 34 / 40 | |
| both GDN paths off | 0.132 | 0.096 | 1 | 37 / 40 | yes |
| TC=1 + CONVL2=2 | 0.508 | 0.967 | 4 | 35 / 40 | no (mean, p90) |
| TC=1 alone | 0.668 | 0.733 | 4 | 33 / 40 | no (mean, p90, top-1) |

All 40 logit rows differ bit for bit between off and on, so the paths ran on every prompt.

**Where the difference sits.** The medians are the same as the references' (about 0.01). The excess is in the tail:

- **Without the single worst prompt:**

  | Arm | KL mean | p90 |
  |---|---|---|
  | `STRATA_PF_FUSED=0` (reference) | 0.103 | 0.254 |
  | `STRATA_PREFILL_CPU_SHARE=0.4` (reference) | 0.124 | 0.166 |
  | stock TC + CONVL2 | 0.299 | 0.971 |
  | stock TC alone | 0.181 | 0.370 |
  | patched CONVL2 alone | 0.152 | 0.240 |

- **The worst prompt** is the same for every GDN-on arm (stock and patched; TC alone, CONVL2 alone and both): a 2,816-token cut of the synthetic transcript.
  - Off: the default path gives a nearly flat distribution (entropy 9.3 nats, top token `<|im_end|>` at ~5 %, `2` at 3-6 %). Both rounding references and the earlier build give the same.
  - On: every GDN-on arm gives `2` at > 0.9999 (top logit 13-14 above the next).
  - The 2-4 tokens before the cut occur 8-10 times earlier in the prompt, and each time `2` follows. So the on arms give the token the text continues with. On this prompt the default path looks like the outlier.
- **Mean NLL of the text's own next token** (36 prompts where the text goes on):

  | Arm | mean NLL | median NLL |
  |---|---|---|
  | stock off | 4.245 | 2.742 |
  | TC + CONVL2 | 3.940 | 1.789 |
  | TC alone | 4.303 | 2.508 |

  So the stack is not worse on this measure, but 36 positions are too few to say more (next section).

## Many-position check (stock v0.2.10, on vs off)

> **PLACEHOLDER - results pending, fill before posting.** Teacher-forced over about 31K positions, both GDN paths on vs off, the same build and settings as above.
>
> | Arm | positions | mean NLL | NLL vs off | KL mean (vs off) | KL p99 | top-1 agreement |
> |---|---|---|---|---|---|---|
> | both off | | | - | - | - | - |
> | TC=1 + CONVL2=2 | | | | | | |
> | TC=1 alone (if run) | | | | | | |

## Where STRATA_GDN_TC=1 runs on this card: the 99 KB split plan (dc149ef)

Links are to `ffa80d731`.

1. **sm_120 cannot run the full scan.** It needs `kTcScanSmem<false>` = 124,944 B ([gdn_tc.cuh#L46](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/src/prefill/gdn_tc.cuh#L46)), more than the card's 101,376 B opt-in.
   - `gdn_rec_tc(..., split=false)` returns `cudaErrorNotSupported` ([kernels.cu#L1323](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/src/prefill/kernels.cu#L1323)).
   - The dispatch then retries with the single-buffered v / T / P plan ([kernels.cu#L3082-L3088](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/src/prefill/kernels.cu#L3082-L3088)).
   - That plan came with **dc149ef** ("opt-in STRATA_GDN_TC on 99-KB cards (split v/T/P buffering)").
   - So on this card `STRATA_GDN_TC=1` only ever runs the split plan.
2. **With 84 SMs it also takes the fused output norm.**
   - `gdn_tc_tiles()` returns 1 below 2 x 48 = 96 SMs ([kernels.cu#L1298](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/src/prefill/kernels.cu#L1298); 51567de1a).
   - So `tcnp` is set ([kernels.cu#L3053](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/src/prefill/kernels.cu#L3053)). The scan is `gdn_tc_scan_kernel<true, true, 3, 1>`: the split plan with the output norm fused in (ee0511484, `kTcScanSmemSplitNorm` = 98,832 B). `gdn_out_norm_kernel` is skipped.
   - This holds for any 99 KB card with 48-95 SMs (e.g. RTX 5080 84, RTX 5070 Ti 70).
3. **The model-level figures we could find cover other kernels:**
   - The `STRATA_GDN_TC` KL in docs/DETAILS.md (0.0157, PR #3779) is from a CMP 170HX. That is GA100 with a 166,912 B opt-in, so the full double-buffered plan.
   - The `server.py` qualification note ("KL mean 0.0019 / max 0.0125 ... (l620)", [server.py#L4024](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/serve/server.py#L4024)) names l620. That is the RTX PRO 5000, which the `gdn_tc_tiles` comment gives 110 SMs. If it was measured after 51567de1a, it ran the split plan with two tiles and the separate norm kernel.
   - We found no model-level check of the one-tile + fused-norm instance.
4. **Why we call the split path a suspect and not the cause.**
   - On our patched build, `STRATA_GDN_CONVL2=2` alone (`gdn_conv_w_kernel`, which does not touch the scan) moves the same worst prompt the same way.
   - So the split plan cannot be the whole story. The GDN state over a few thousand tokens may simply be this sensitive here. #1522 got a first-token KL of 0.138 from a last-bit change in the q/k L2 sum on an RTX 5090.
   - We did not see a race in the SPLIT staging. The v / T / P restage after the mid-chunk barrier ([gdn_tc.cuh#L634](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/src/prefill/gdn_tc.cuh#L634)) follows their last reads.

**Env-only switches that separate the parts** (we have not run them yet):

| Run | What it isolates |
|---|---|
| on the 5080: `STRATA_GDN_TC_FUSE=0` | split plan, separate norm kernel |
| on the 5080: `STRATA_GDN_TC_TILES=2` | two tiles in two waves, separate norm |
| on a 110-SM card: `STRATA_GDN_TC_TILES=1` | the 5080's instance |
| on sm_80 / sm_90: `gdn_harness --paths tc,tcs` | the split itself |

## Defaults

- The engine runs both paths off unless set.
- Since bee469c46 (v0.2.9), `serve/server.py` `gdn_stack_env` sets `STRATA_GDN_TC=1` and `STRATA_GDN_CONVL2=2` with `setdefault` for Qwen3.8 on Linux CUDA ([server.py#L4031-L4043](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/serve/server.py#L4031-L4043)). So every Linux CUDA user of the server gets them, on every card the runtime gate lets through.
- `src/core/arch_defaults.cpp` keeps `STRATA_GDN_CONVL2` off on CUDA because "it is not bitwise on CUDA 13.3 sm_120 (#1522)".
- #5037 asks to turn the stack on for Windows too (no KL run there).

## Environment

- **GPUs:**
  - Main: GeForce RTX 5080 16 GB, compute capability 12.0, 84 SMs.
  - Helper: RTX 4060 Ti 8 GB (sm_89) holding 3,300 experts (`--expert-cache-device1 3300`).
- **Does the helper matter?** The GDN layers' prompt kernels (conv, recurrence, output norm) run on the main card only. In the prompt pass the helper computes only the MoE rows of the experts it holds. Every arm had the same helper setup, so it should not matter for these kernels, but we have not re-run on the 5080 alone.
- **Software:**
  - Linux 7.0 (Ubuntu 24.04 userland).
  - NVIDIA driver 615.71.09 (open kernel module).
  - CUDA toolkit 13.3.73, GCC 13.3.0.
- **Strata:**
  - Tag v0.2.10 (`ffa80d731`), unmodified, engine 0.1.56.
  - Built from source: CMake Release, `CMAKE_CUDA_ARCHITECTURES=89;120`, the pinned ggml (3cf0325).
  - A local build, cf. #4879. Off and on are the same binary, so the comparison measures the switches, not the build.
- **Model:** Qwen3.8-Flash-Next GSQ-RCO IQ3_S.
  - `models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` via `--native`.
  - `models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` via `--ple-gguf`.
  - Its native IQ3_S pack, the MTP draft layer.

<details><summary>Exact engine arguments and environment of every arm (only the two GDN switches differ)</summary>

```
strata --serve --pack <IQ3_S pack> --native models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
  --ple-gguf models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf --expert-profile data/expert-profile.bin
  --spec 7 --spec-min-p 0.5 --mtp <draft layer> --ple-inflight 128 --vram-reserve-mib 713 --expert-cache-device1 3300
  --expert-cache 1 --adapt-every 100000 --pcie-frac 0 --suffix-draft 0 --prompt-cache 0 --kv fp16 --max-context 33280
  --prefill auto

CUDA_VISIBLE_DEVICES=<5080>,<4060 Ti> CUDA_MODULE_LOADING=LAZY STRATA_IO_THREADS=64 STRATA_GR_V3=1 STRATA_PF_FUSED=1
STRATA_SIDE_MIXER=2 STRATA_QSA_SPLIT_ATTN=1 STRATA_MMVQ_IL=1 STRATA_ADAPT_LAG=2 STRATA_DISJOINT_ADAPT=1
STRATA_PREFILL_CPU_SHARE=0 STRATA_PREFILL_CPU_SHARE_MAX=1792 STRATA_DEQUANT_WIDE=1 STRATA_DEFAULTS=026
STRATA_ROUTE_PRIOR=0 STRATA_PROMPT_ATTN_IMMA=0 STRATA_PREFILL_LAYER_MAJOR=0 STRATA_PLE_AUTO_RAM=0
STRATA_ROUTE_TAIL_SKIP=0 STRATA_ADAPT_ASYNC=0 STRATA_LOOKUP_MAX_T=0 STRATA_GR_V3_PF=0 STRATA_GR_R2=0
STRATA_SMALL_UNR=0 STRATA_QSA_FUSE_NR=0 STRATA_IL_PAD=0 STRATA_DF_PDL=0 STRATA_PCIE_START=old
STRATA_ARENA_RAM_FALLBACK=0 STRATA_MTP_KEEP=1 STRATA_SPILL_OFF=1 STRATA_PENALTY_PROMPT=1
STRATA_PCIE_FRAC_DEFAULT=old STRATA_MMVQ_IL_ROWS=<a fixed row table>
off: STRATA_GDN_TC=0 STRATA_GDN_CONVL2=0   on: =1 / =2   TC alone: =1 / =0
```
None of the fixed settings selects a GDN kernel (`STRATA_DEFAULTS=026` has no sm_120 entry and no GDN switch).
</details>

## Repro without our harness

- **Use a set of prompts, not one.** A single prompt most likely shows KL ~0.01, as rounding changes do. The difference is in the tail.
- **Arms:** off / on / TC alone, plus a rounding reference (`STRATA_PF_FUSED=0`).
- **Compare** the tail (p90, rows KL > 0.5) between the arms.
- **Card:** one GPU. We dropped the drafter and the second card here, and we have not run this exact form.

```sh
# 1. 15 prompts: three long files of the repo cut at 2K-32K tokens, as engine requests
python3 - > req.txt <<'EOF'
import sys; sys.path.insert(0, "tools"); import strata_tokenizer as T
tk = T.Tokenizer.from_gguf("models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf")
for f in ("docs/DETAILS.md", "serve/server.py", "src/prefill/kernels.cu"):
    ids = tk.encode(open(f, encoding="utf-8").read())
    for n in (2048, 4096, 8192, 16384, 32768):
        print("GEN 1 " + ",".join(map(str, ids[:n])))
print("QUIT")
EOF

# 2. one engine per arm; each request's first-window logits go to first-<arm>.<i> (float32, whole vocabulary)
run() {  # run ARM TC CONVL2 PF_FUSED
  STRATA_GDN_TC=$2 STRATA_GDN_CONVL2=$3 STRATA_PF_FUSED=$4 STRATA_PREFILL_CPU_SHARE=0 STRATA_ROUTE_TAIL_SKIP=0 \
  STRATA_DUMP_FIRST_LOGITS=first-$1 \
  build/strata --serve --pack <IQ3_S pack> \
    --native models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf \
    --ple-gguf models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf \
    --expert-profile data/expert-profile.bin --expert-cache 1 --adapt-every 100000 --pcie-frac 0 \
    --suffix-draft 0 --prompt-cache 0 --kv fp16 --max-context 33280 --prefill auto < req.txt > /dev/null
}
run off 0 0 1; run on 1 2 1; run tc 1 0 1; run unfused 0 0 0

# 3. KL(off || x) per prompt: mean / median / p90 / rows > 0.5 / max / top-1 changed
python3 - <<'EOF'
import numpy as np
def lp(f):
    x = np.fromfile(f, dtype=np.float32).astype(np.float64); x -= x.max(); return x - np.log(np.exp(x).sum())
for arm in ("unfused", "tc", "on"):
    kl, flip = [], 0
    for i in range(15):
        a, b = lp(f"first-off.{i}"), lp(f"first-{arm}.{i}")
        kl.append(float((np.exp(a) * (a - b)).sum())); flip += int(a.argmax() != b.argmax())
    k = np.array(kl)
    print(f"{arm:8s} mean {k.mean():.3f} median {np.median(k):.3f} p90 {np.percentile(k, 90):.3f} "
          f"rows>0.5 {(k > 0.5).sum()} max {k.max():.2f} top-1 changed {flip}/15")
EOF
```

## What we did not test

- `STRATA_GDN_CONVL2=2` alone on the unmodified build (only on our patched build).
- `STRATA_GDN_TC_FUSE=0` / `STRATA_GDN_TC_TILES=2` on the 5080 (see the table above).
- Other cards: no 99 KB card with >= 96 SMs, no sm_80 / sm_90 card, the 5080 without the helper card.
- The official prebuilt engine (only our CUDA 13.3.73 build).
- The served settings (`--kv int8`, prompt CPU share on, the auto expert cache), Windows, other quants.
- Whether decode-time quality or task scores move. The many-position check above is pending.

Related: #1522 (CONVL2=1 not bitwise on sm_120), #3779 / #3712 (where `STRATA_GDN_TC` came from), #5037 (the stack on Windows), #4879 (local sm_120 builds; there, turning the GDN stack off did not help).

Measured and drafted with Claude Code.
