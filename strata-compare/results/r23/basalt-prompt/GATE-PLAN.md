# Gate plan: Basalt's prompt path, the exact and rounding-level parts (r23; written 11-04, nothing built or run)

Port: worktree `strata-r23basalt`, branch `r23-basalt-prompt` = r22-port0210 (fdd2fffa8) + 3 commits, all switches off by
default (STUDY.md section 6). What the gate decides per part: exact (bit for bit), rounding-level (our KL yardstick rule),
or out; then what each is worth on Basalt's cold 16K / 64K fixtures and on the 9-workload screen. **Nothing switches**:
P028x stays served; a part that passes is a candidate, Karl's call (with his 5 switch conditions of gap 16).

Two gaps with 8080 down (port_gap4.sh begin/end, bench.lock + gpu-test.lock, watch.py: MemAvailable >= 12 GiB, 5080
free >= 300 MiB, the swap rule, kcheck every 60 s; guard.py per step; the kernel log after each step; P028x back at the
end with its sha checked). The build waits for a gap too (an LDR run is live now).

## 1. Arms (configs to write before the gap, from configs/P0210x-h.json)

Every arm = P0210x-h with `exe` -> engine-r23basalt/strata and `server` -> strata-r23basalt/serve/server.py, plus:

| arm | config (new) | adds | part | class claimed |
|---|---|---|---|---|
| B | r23-B.json | nothing (every r23 switch unset) | the base | = P0210x-h bit for bit |
| A | r23-A.json | STRATA_PF_AHEAD=1 | copy-ahead, in-layout slots | exact |
| T | r23-T.json | STRATA_PF_TAIL_SPLIT=1 | tail split | rounding-level |
| U | r23-U.json | STRATA_HC_UPMIX=1 | Basalt 10f338cc's twin, already in our tree | exact (upstream: bitwise on CUDA sm_80+, 5090) |
| K | r23-K.json | STRATA_CKPT_POOL=1, STRATA_CKPT_POOL_READY=2 | Basalt f0f637c4's twin, in our tree | exact |
| KP | r23-KP.json | STRATA_KV_PREFETCH=1 | the K/V prefix on its own stream | exact (by design) |
| G | r23-G.json | STRATA_GDN_CHUNKED=2 | FP32 chunked GDN (Basalt's chunked GDN without its BF16) | rounding-level; priced first |
| S | r23-S.json | A + T + U + K (+ KP, G where they passed) | the stack | as its parts |
| C | r23-C.json | S + `--prefill auto:24576` + STRATA_PF_FIRST_CHUNK=1 | the cap arm (the scan picks the largest chunk that fits) | rounding-level |
| A2 | r23-A2.json | STRATA_PF_AHEAD=2 | copy-ahead with Basalt's staged-layout slots | rounding-level (optional) |

`bringup/patchtest.sh lossless` must learn the new names (it fails a config with unknown prompt switches); the env check
(envcheck, as gap 17's) must see each arm's variables in the running engine.

## 2. Build (in the gap; CPU only, ~15-25 min)

1. `work/r23/basalt-prompt/build-r23.sh` = work/r22/build-port0210.sh with W = strata-r23basalt and the output
   engine-r23basalt: `cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF
   "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR=...`,
   `cmake --build --target strata -j <= 16` under work/r22/build_memguard.sh, nice 5. SHA256 + SOURCE (the head 3383d1f8d).
2. Gates: build PASS; no new warning in prefill.cpp (grep the build log for prefill.cpp warnings, compared with the
   r22p0210 build log); `strings engine-r23basalt/strata` holds STRATA_PF_AHEAD, STRATA_PF_TAIL_SPLIT,
   STRATA_PF_FIRST_CHUNK.
3. The build must verify what STUDY.md section 6 lists (captures, types, the if-init forms, -Wall -Wextra). No new unit
   test exists for run_impl's chunk loop; the run steps below are the test.

## 3. Gap A - correctness and the profile (~2 h with 8080 down)

Times from gap 17: an exact7 set 3.3 min, pf_yardstick long40 8.5 min; the new 24-prompt set ~6 min.

**A1 Profile first (~10 min).** B with STRATA_PREFILL_TIMING=1 and STRATA_TRACE=1, Basalt's cold pp16k and pp64k
(bp90_client.py, a fresh engine each), 1 pass; the same for T, and for G (G's "gdn" phase only prices it). Output: the
per-phase GPU timeline (expert waits, GEMMs, GDN, QSA, host grouping, PLE), host staging, the chunk setup / sync / chunk
callback times, and "checkpoint at L: sync X ms, save Y ms". STUDY.md section 4 gets the measured split; G goes on only
if its GDN phase is shorter than B's.

**A2 The base is today's build.** exact7 at pin 2500 (slots MATCHED): B vs gap 17's g17-p210a -> 7/7. pf_yardstick
long40 on B -> 0 of 40 first-token logit files differ from gap 17's p210 dir.

**A3 Copy-ahead is exact (A).** A new prompt set (below) at the served chunk, run twice per pair on the same build:
- B vs A with the yardstick's settings and `--prefill auto:16384`, `--kv int8`: 24 of 24 logit files byte-identical.
- the same pair with the served CPU share (`--keep-share`: STRATA_PREFILL_CPU_SHARE=0.4, _MAX=1792): 24 of 24.
- each A run's stderr has the per-prompt line "STRATA_PF_AHEAD=1: N experts copied ahead ..., M read in place" with
  M > 0 on the cuts whose rest is staged (else UNEXERCISED - not decided).
- exact7 A vs B: 7/7 (its prompts are single chunks: a regression guard only).
- Optional: one 16,676-token prompt under compute-sanitizer --tool racecheck and --tool synccheck: no hazard.

**A4 The two existing exact switches (U, K).** exact7 U vs B and K vs B: 7/7. long40 U vs B: 0 of 40 differ. If U
differs (the 5080's cuBLAS may sum k in another order than upstream's 5090): U is rounding-level and needs A6's rule on
long40 (gap 8's references) to stay in the stack. K has no prompt-logit effect to check (the yardstick has no chat cache).

**A5 KV prefix prefetch (KP, optional).** The 16 cuts of the set at >= 33K with KV streaming kept
(`--keep-kv-resident 32768`, --kv int8): B vs KP byte-identical. (The yardstick drops --kv-resident by default, so KP is
untested there.)

**A6 The tail split is rounding-level (T).** The KL rule in its current form (kernel_rule2 + kernel_rule3: KL mean and
p90 <= 1.10 x the larger reference's, KL > 1 rows <= the worse reference's + 1, changed top-1 <= 1.10 x the larger
reference's, text NLL over the base <= 1.10 x the larger reference's distance), at the SERVED chunk on the new set:
- base `ref16` = A3's first B run; references `unfused16` (STRATA_PF_FUSED=0) and `cpushare16` (STRATA_PREFILL_CPU_SHARE=0.4),
  both on engine-r23basalt, `--prefill auto:16384 --kv int8`; candidate `T16`.
- and long40 as gap 17 (gap 8's references): T changes at most one long40 prompt (the yardstick's bare `auto` reads in
  8192 chunks), so this is a check that nothing else moved.
- Note: long40 has never run at our served chunk (bare `auto` = 8192 in the yardstick). The new set's references at
  `auto:16384` are therefore new, and the rule compares T16 only with them.

**A7 The cap arm (C).** One engine start at `--prefill auto:24576`: the line "prompt chunk auto: N tokens, a M-slot ring"
and "borrows K slots" give the chunk the 90 % lend allows (estimate ~20-22K) - C's config then pins `auto:N`. Then the
A6 rule for C (chunk N, PF_FIRST_CHUNK=1) against ref16 and the references, on the new set and on long40 at
`--prefill auto:N`. During C's start and runs: 5080 free >= 300 MiB throughout (watch.py), else C is void.

**A8 PF_AHEAD=2 (optional, only if A shows the copies are read in place and B1 prices A above noise).** It moves the CPU
share's candidates on short prompts: the A6 rule on the 40 short segments (128-1000 tokens) and 8 prompts of 1.2-1.8K
tokens, with the served share, references as A6.

**The new prompt set `tail24`** (24 cuts whose rest after the last multiple of 16,384 is 256-1,000 tokens, so it is a
staged chunk at our served stream-all size 1,792 and at the yardstick's 1,024; at the yardstick's bare `auto` the same
cuts leave the same rests after 8192 chunks):
- tf-long40k.prompt: 16684, 17084, 17384, 33188, 33618
- tf-long64k.prompt: 16640, 16944, 33068, 33768, 49572, 49852
- tf-long112k.prompt: 16804, 17234, 33328, 49408, 50152, 65836, 65956, 66236
- tf-long96k.prompt: 17384, 33468, 49712, 66386, 66536

(rests 256-1,000; 16 cuts >= 33K for A5; max 66,536 tokens: --max-context 67,048 with int8 K/V and --expert-cache 1
fits easily.) NLL rows: the text's next token after each cut (all four texts go on past their cuts).

**Scripts to write before the gap** (none written yet; all under work/r23/basalt-prompt/):
- `pf_yardstick_r23.py` = work/r22/pf_yardstick.py + `--prefill SPEC` (instead of the forced bare "auto"), `--set tail24`,
  `--keep-share` (do not force STRATA_PREFILL_CPU_SHARE=0), `--keep-kv-resident N` (do not drop --kv-resident);
- `r23_rules.py` = work/r22/g17_rules.py's form with the rules of this file, kernel_rule3's next-token list generalized to
  tail24;
- `gap23.sh` (parts a / b) = work/r22/gap17.sh's skeleton (envcheck, fatalchk, kc, bprun, scr).

## 4. Gap B - speed (~1.5 h with 8080 down)

**B1 Basalt's cold fixtures, prompts** (bp90_client.py --sets pp16k,pp64k, a fresh engine per measurement, 3 passes in
turned order: B A T U K S C, then reversed, then as first; + G and KP if they passed A): ~1.3 min per arm and pass.

**B2 Basalt's decode fixtures** (--sets decode), 1 pass for B, S, C: the parts must not move decode (a check).

**B3 The 9-workload screen** (work/r22/abarm.sh: W1-W3, agent x2, research4 x4; T 1.0 / 0.95 / 20 / min-p 0.05, effort
medium; a warm-up first), 3 passes in turned order: B, S, C. ~4.2 min per pass.

**B4 The chat-cache trade of T and C** (Karl's #693 lesson): per arm B / T / C, a fresh engine, request 1 = the bp90 16K
prompt; request 2 = a prompt that shares its first ~16,500 tokens and then differs; request 3 = request 1 + its answer +
a follow-up. Report request 2's and 3's prompt reads (tokens read, ms) and the "checkpoint at L" lines. Expected: B reads
~120 tokens for request 2 (from the 16,384 checkpoint), T and C read ~16.5K (no checkpoint before it); all read only
the new part of request 3. Karl decides the trade.

## 5. Rules (fixed before the gap; r23_rules.py writes decision.txt)

- **Baseline:** build PASS; A2 7/7 and 0 of 40 differ. Else nothing below is decided.
- **Exact parts** (A, U, K, KP): exact7 7/7 MATCHED, and their logit checks 0 differ (A: both A3 pairs, M > 0). A part
  that differs is not exact: it may go on as rounding-level only by A6's rule.
- **Rounding-level parts** (T, C, G, A2): kernel_rule2 AND kernel_rule3 PASS on tail24 at the served chunk against ref16 /
  unfused16 / cpushare16, AND on long40 against gap 8's references (C at its own chunk).
- **Gain, per part** (B1 against B, the same build): change = mean / B's mean - 1, noise = the larger arm's pass-to-pass
  spread for that fixture. CANDIDATE = the part's gates pass, the fixture it targets (A, T: 16K and 64K; C, KP, K: 64K
  and 16K; U, G: both) above +max(noise, 1.0 %), the other fixture not below -noise. NO GAIN = gates pass without that.
- **The stack (S) and the cap arm (C) on the screen:** per workload, decode and prompt tok/s each, the arm's pass mean >=
  B's pass mean x (1 - the larger of the two arms' spreads for that workload and number) - the per-workload no-loss
  condition of 11-03; the screen's prompt geomean not below B. B2: decode of S and C within B's spread.
- **C** also needs 5080 free >= 300 MiB throughout, MemAvailable >= 12 GiB, the lend line and B4 reported.

## 6. GPU time

| step | minutes (8080 down) |
|---|---|
| build (CPU only, inside the gap) | 15-25 |
| A1 profile (B, T, G on 16K + 64K) | 10 |
| A2 exact7 B + long40 B | 12 |
| A3 four tail24 runs + exact7 A | 27 |
| A4 exact7 U, K + long40 U | 15 |
| A5 KP pair (optional) | 8 |
| A6 unfused16, cpushare16, T16 on tail24 + long40 T | 27 |
| A7 C's start + tail24 + long40 at its chunk | 16 |
| A8 (optional) | 15 |
| **gap A** | **~2.0 h** (+ the build; ~1.7 h without the optional steps) |
| B1 9 arms x 3 passes | 35 |
| B2 3 decode passes | 5 |
| B3 3 arms x 3 passes + warm-up | 40 |
| B4 3 arms | 6 |
| **gap B** | **~1.5 h** |

A core run if the gaps are short: A1, A2, A3, A6 (tail24 only); then B1 with B, A, T, S and B3 with B, S: ~1 h + ~55 min.

## 7. Expected gain per part, and how much of Basalt's lead it closes

Estimates from STUDY.md section 4 (no profile yet; A1 replaces them). Rates; 16K = 16,676 tokens, 64K = 66,617.

| part | 16K | 64K | screen prompt geomean | where it comes from |
|---|---|---|---|---|
| A, PF_AHEAD=1 | +1 .. +2.5 % | +0.3 .. +0.7 % | +0 .. +0.5 % (R4) | the staged rest's link idle per layer (routing sync, grouping, attention: ~1-3 ms x 48), up to 112 copies a parity |
| T, PF_TAIL_SPLIT=1 | +7 .. +13 % | +2 .. +3.5 % | +0.5 .. +1 % (R4 +3 .. +7 %) | the staged rest (~0.5-0.7 s) becomes a second stream-all chunk (~0.1-0.4 s) |
| A + T | as T (T leaves A no staged rest at these lengths) | as T | as T | |
| U, HC_UPMIX=1 | +0 .. +4 % | +0 .. +4 % | +0 .. +3 % | the FP32 gate rows (40 KB a token) no longer written and read back per half: ~128 GB of DRAM traffic at 16K |
| K, CKPT_POOL(+READY) | +0.3 .. +1.5 % | +0.3 .. +1.5 % | ~0 .. +0.5 % | ~15-40 ms per checkpoint (a fresh ~118 MB image), 2 / 5 per fixture |
| KP, KV_PREFETCH=1 | ~0 | +0.3 .. +1 % | +0 .. +0.5 % (R2, R4) | ~2.8 GB of K/V prefix staged on the compute stream at 64K |
| G, GDN_CHUNKED=2 | -3 .. +4 % | -3 .. +5 % | -2 .. +3 % | the 36 GDN layers' recurrence (~7-9 % of the time); upstream expects it slower under 128 SMs |
| C, cap ~20-22K + FIRST_CHUNK (instead of T) | +13 .. +19 % | +5 .. +9 % | +1 .. +3 % | 16K in one chunk; 64K in 4 (or 3) chunks instead of 5 |
| **S = A + T + U + K** | **+7 .. +19 %** | **+2 .. +9 %** | **+0.5 .. +4 %** | (A adds ~0 on top of T at these lengths) |
| **S with C** (C in place of T) | **+13 .. +25 %** | **+5 .. +15 %** | **+1 .. +6 %** | |

Basalt's lead (11-02, means): 16K +32.3 %, 64K +24.1 %, screen prompt +15.3 %. Measured as the share of the log ratio:
- S closes about **a quarter to three fifths** at 16K (0.24-0.62), **a tenth to two fifths** at 64K (0.09-0.40), and a
  twentieth to a quarter on the screen (0.03-0.28);
- S with C about **half to four fifths** at 16K (0.44-0.80) and **a quarter to two thirds** at 64K (0.23-0.65).
What stays: Basalt's two lossy kernels (chunked BF16 GDN, one-MMA FP16 attention: about 7-9 % on long prompts), its
32K chunks (our buffers do not hold them in the lend; PF_HC_REGION after gap 19 would get closer), and whatever A1 finds
in our fixed cost per chunk that the switches above do not cover.
