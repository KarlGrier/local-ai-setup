# Unsloth Dynamic v3.1 for Qwen3.8-Flash-Next: header check (11-04, Qwen4 day-one rehearsal)

Written by a helper; saved by Claude (the helper's .md write was refused). Headers only: no GPU, no engine, no build, no
download beyond header bytes. day1.py ran unchanged (it already reads head-only files, NAME + NAME.size; sha256
1658d93f..., mtime 09:20; its self-test outputs still stand).

## Answer first

- **Nothing blocks either v3.1 file on our engine today** - types, architecture, shapes or file layout - on the 0.2.10
  tree (`strata-r22p0210`, fdd2fffa8) and the served 0.2.8 tree (`strata-r22p028x`, 8f7a48aab); their type tables are
  identical. Both files are `qwen4exp`, with the same 37 shape keys as Flash-Next and the same tokenizer and template.
  Every routed-expert type has GPU kernels on both cards. They need a pack with `--compat-bf16` (their Q8_0
  hyper-connections and Q8_0 PLE value rounded to BF16) - UD-Q4_K_XL ran here the same way (92.37 % suite, best measured).
  setup.py would refuse both by name (#444), but our configs do not go through setup.
- **Karl's size reading is right:** UD-IQ3_XXS v3.1 83.63 GB vs our IQ3_S 83.62 GB, 46.84 GiB of experts in both (equal
  within ~1 MB). Unsloth grew UD-IQ3_XXS from 81.96 GB (pre-v3.1) to exactly our size, so the chart's comparison is at
  the same size. Caveat: 28.80 GB (34 %) of each "~84 GB" is the n-gram table (IQ4_NL in all of them, read from the SSD).
  UD-IQ2_XS is 75.83 GB with 39.38 GiB of experts.
- **MTP is in neither file - nor in ours.** Our drafter (`strata-v0115/mtp/rt`) was built from Qwen's checkpoint and
  works with any quant of this model. The n-gram table, the PLE projections and every `ple.*` key are present.
- **#444's refusal of Qwen's UD-IQ3_XXS / UD-Q2_K_XL was setup's allow-list, not a kernel gap.** The self-test took its
  type-level reason from GLM's file (FF 2048: IQ3_XXS downs possible there). Flash-Next's FF is 640, which no
  256-value-block down type divides, so its downs are IQ4_NL, Q2_0 or Q5_0. The pre-v3.1 Qwen files pass today's tables too.
- **Small cost:** UD-IQ3_XXS has 0.26 GiB more dense on the 5080 -> **-135 slots** (4,583 -> ~4,448, -2.9 %); the 4060
  Ti's 3,300 experts take 6.23 GiB (today 6.21); decode model 144 vs 145 tok/s.
- **Quality is the real question, and Karl's rule cannot settle it:** the expert bytes are equal.

## 1. What was fetched (network rules kept)

- Repo `unsloth/Qwen3.8-Flash-Next-GGUF`, pinned at commit `d96201194f103c906994f283f504209dc8d2a10c`. v3.1 was uploaded
  11-04 15:15-17:43 UTC ("Better UD 3.1 quants", "Add mix n match engram") into the same repo.
- Range requests: `work/qwen4-kit/unsloth-v31/scratch/fetch_heads.py` (starts at 1 MiB, doubles, cap 64 MiB; a reply must
  be 206 with the asked Content-Range; any HTTP error stops). Parsed as data by `bringup/gguf_head.py` under `python -I`;
  the file cut at the header end with NAME.size beside it. Nothing refused or rate-limited; ~90 MB in total.
- Saved under `work/qwen4-kit/unsloth-v31/headers/` (FETCH-LOG-*.json lists each file):

| file | header saved | file size |
|---|---|---|
| UD-IQ3_XXS 1/4 (metadata only, 0 tensors) | 10,946,618 (whole file) | 10,946,618 |
| UD-IQ3_XXS 2/4, 3/4, 4/4 | 76,763 / 1,071 / 173 | 49,946,027,488 / 4,869,325,888 / 28,800,138,432 |
| UD-IQ2_XS 1/3 (metadata only) | 10,946,618 (whole file) | 10,946,618 |
| UD-IQ2_XS 2/3, 3/3 | 77,728 / 173 | 47,021,008,288 / 28,800,138,432 |
| MTP/mtp-...-Q8_0, MTP/mtp-...-shared-Q8_0 (sidecars) | 10.9 MB each | 4.14 / 2.79 GB |
| engram/...-Q5_1, -Q8_0, -BF16 (sidecars) | 173 each | 38.4 / 54.4 / 102.4 GB |
| pre-v31/: UD-IQ3_XXS + UD-Q2_K_XL at the 10-06 commit 766911a6 | 10.9 MB + 30-48 KB each | 81.96 / 78.87 GB |

- Not fetched: the READMEs and charts (outside the rule), so the recovery and KLD figures are Karl's reading, unchecked.

## 2. Sizes vs Karl's numbers

| file | total | without the n-gram shard | experts (bpw) | dense on the 5080 (pack forms) | host embedding |
|---|---|---|---|---|---|
| ours: ISTA GSQ-RCO IQ3_S (2 shards) | **83.62 GB** (77.87 GiB) | 54.82 GB | 46.84 GiB (3.33) | 3.89 GiB | 0.31 GiB (IQ4_XS) |
| UD-IQ3_XXS v3.1 (4 shards) | **83.63 GB** (77.88 GiB) | 54.83 GB | 46.84 GiB (3.33) | 4.15 GiB | 0.49 GiB (Q6_K) |
| UD-IQ2_XS v3.1 (3 shards) | **75.83 GB** (70.62 GiB) | 47.03 GB | 39.38 GiB (2.80) | 4.54 GiB | 0.31 GiB (IQ4_XS) |
| UD-IQ3_XXS pre-v3.1 (10-06) | 81.96 GB | 53.16 GB | 45.29 GiB (3.22) | 4.15 GiB | 0.49 GiB |

- Karl's ~84 / ~76 GB are the full downloads; the chart point is at our size (experts by hand from the type mixes: 50,293
  MB UD vs 50,292 MB ours).
- Where the bits go: downs - UD 45 IQ4_NL + 3 Q2_0 layers, ours 39 + 9; gate/up - UD 26 IQ2_S + 21 IQ3_XXS + 1 IQ4_XS (no
  IQ3_S), ours 20 IQ2_S + 10 IQ3_S + 17 IQ3_XXS + 1 IQ4_XS; dense - UD's attention, GDN out and shared experts all Q6_K,
  ours IQ4_XS / Q4_K / Q5_K / Q6_K; hyper-connections Q8_0 in UD, BF16 in ours.
- Engram: every v3.1 quant's last shard is the same file; sidecars offer the table as Q5_1 (38.4 GB), Q8_0 (54.4 GB),
  BF16 (102.4 GB).
- v3.1 re-made UD-IQ1_M, IQ1_S, IQ2_XS (new), IQ3_XXS, IQ4_XS, Q2_0 (new), Q2_K_XL, Q3_K_XL. UD-Q4_K_XL was only re-split
  (same bytes less shard 1's 6-byte padding): our HF-cache copy is still current. Q5_K_XL, Q6_K_XL, Q8_0, BF16 untouched.

## 3. What blocks each v3.1 file now

| check | UD-IQ3_XXS v3.1 | UD-IQ2_XS v3.1 | source |
|---|---|---|---|
| architecture | `qwen4exp`: accepted | same | model_family.hpp:22 |
| shapes | all 37 `qwen4exp.*` keys equal ours; 1,224 tensors, names and shapes identical (0 diff lines) | same | gguf_reader.hpp:805 |
| expert types | OK on both cards | OK on both cards | iq_kernels.cu:846/851; generate.cpp:4461 |
| the expert rule | gate = up type every layer; n_ff 640 % qk(down) = 0 for every down | same | iq_kernels.cu:5477 |
| shard 1 (metadata only, ends 6 B before its aligned data start) | loads: fixed upstream 5fde38470, in both trees (it stopped UD-Q5_K_XL in Round 15) | same | gguf_reader.hpp:515-521 |
| a layer split across shards | layer 43 (gate + down in shard 2, up in shard 3): iq_pack writes a v4 index with per-role shards, as the old UD-Q4_K_XL's layer 11, which ran | none | tools/iq_pack.py:28-31, :486 |
| float forms | **pack with `--compat-bf16`** (rounding): 194 Q8_0 hyper-connection tensors + the Q8_0 `ple_value` -> BF16; F32 router / shared-expert gate / GDN alpha-beta / hc inject -> BF16 (exact if the values are BF16; iq_pack checks); `ple_conv1d` F32 -> F16 by the loader | `--compat-bf16`: Q8_0 hc -> BF16; `ple_conv1d` BF16 -> F16 (never run here); router, shared gate F32 -> BF16 | iq_pack.py:72, :245 |
| n-gram table | IQ4_NL, in kPleFormats (same type and size as ours) | same | ngram.cpp:185 |
| setup.py | refuses `UD-IQ3_XXS` by name (#444); our configs do not use setup | refuses `UD-IQ2_XS` | setup.py:3245-3257 |
| never run here | `token_embd` Q6_K (listed as supported, iq_kernels.cu:5324) | `ple_conv1d` BF16 | |

Expert classes (gate-up / down, blob per expert, layers) - every class runs on both cards, in the CPU pool and on the
prompt path:

| UD-IQ3_XXS v3.1 | | UD-IQ2_XS v3.1 | | ours (IQ3_S) | |
|---|---|---|---|---|---|
| IQ2_S / Q2_0, 1,510,400 B | 3 | IQ2_XXS / Q2_0, 1,305,600 | 5 | IQ2_S / Q2_0, 1,510,400 | 5 |
| IQ2_S / IQ4_NL, 1,971,200 | 23 | IQ2_S / Q2_0, 1,510,400 | 18 | IQ3_XXS / Q2_0, 1,715,200 | 3 |
| IQ3_XXS / IQ4_NL, 2,176,000 | 21 | IQ2_XXS / IQ4_NL, 1,766,400 | 3 | IQ3_S / Q2_0, 1,868,800 | 1 |
| IQ4_XS / IQ4_NL, 2,662,400 | 1 | IQ2_S / IQ4_NL, 1,971,200 | 21 | IQ2_S / IQ4_NL, 1,971,200 | 15 |
| | | IQ2_S / Q5_0, 2,176,000 | 1 | IQ3_XXS / IQ4_NL, 2,176,000 | 14 |
| | | | | IQ3_S / IQ4_NL, 2,329,600 | 9 |
| | | | | IQ4_XS / IQ4_NL, 2,662,400 | 1 |

- Prompt path: UD-IQ3_XXS all 48 layers on the 5080's fused int8 prompt kernels, as ours (moe_fused_iq.cu:2271);
  UD-IQ2_XS 9 layers are not (8 IQ2_XXS gate/up layers use MMQ, 1 Q5_0 down layer the FP16 dequantizer) -> slower prompts.
- CPU pool: UD-IQ3_XXS only 3 layers (ours 9) have Q2_0 downs (generic ggml-cpu dot); the rest the AVX2 IQ4_NL path.
- Details: per-tensor verdicts `day1-check/files/*.tensors.tsv`; `day1-check/report.md`; against the served tree
  `day1-check-p028x-tree/` (identical verdicts and tables).

## 4. MTP, n-gram, PLE

- **MTP / nextn:** no tensors in either file. Unsloth ships MTP as separate llama.cpp-format GGUFs
  (`MTP/mtp-*-{BF16,Q8_0,Q4_K_M}.gguf`, "shared" variants, a Q8_0 copy at the repo root): `qwen4exp`, block_count 49, one
  `blk.48` layer with the `nextn.*` and `hc_head_*` tensors, Q8_0 experts. Our served file has no in-file MTP either:
  P028x's `--mtp strata-v0115/mtp/rt` came from Qwen/Qwen3.8-Flash-Next@de4b8e4d via tools/mtp_fetch.py. **Nothing
  changes:** same drafter, `--spec 7 --spec-min-p 0.5`, the cost gate.
- **n-gram table:** `per_layer_token_embd.weight`, IQ4_NL, [160, 320,001,536], 26.82 GiB, alone in the last shard
  (`--ple-gguf` = shard 4/4 or 3/3). PLE projections `blk.1.ple_{conv1d,key,value,norm_*}` present. `ple.*` keys all
  present and equal to ours (layers [1], ngram 3, heads 8, conv 4, eos 248044, the multipliers, 16 head offsets and vocab
  sizes, image token 248056, embedding_length_per_layer_input 160).
- **Engram sidecars:** single-file GGUFs with split.count 1 but split.tensors.count 1224; Q5_1 / Q8_0 / BF16 all in
  kPleFormats. Whether `--ple-gguf` accepts their split keys as they are is not checked (the repo ships a `set_split.py`).

## 5. Slots and fit

Strata's sized fill, recomputed as in `results/catchup/F1-frame-pools.md` by `scratch/slots_v31.py` (per-layer blobs from
the headers, the served STRP profile, the 5080 budget after the dense difference); the served row reproduces the logs.

| arm | 5080 auto | 4060 Ti 3,300 by count | 4060 Ti max (7.56 free - 512 MiB) | held on GPUs |
|---|---|---|---|---|
| ours (served) | **4,583** (8.742 GiB) | 6.206 GiB | 3,749 | 32.1 % |
| UD-IQ3_XXS as shipped (+0.257 GiB dense) | **4,447-4,449** (-135, -2.9 %) | 6.226 GiB (fits) | 3,737 | 31.5 % |
| UD-IQ2_XS as shipped (+0.645 GiB dense) | 5,050-5,051 (+467, +10 %; smaller blobs) | 5.29 GiB | 4,411 | 34.0 % |
| splice: UD-IQ3_XXS experts in our file | 4,584 | 6.230 GiB | - | 32.1 % |
| splice: UD-IQ2_XS experts in our file | 5,451-5,453 | 5.28 GiB | - | - |

- The +0.26 GiB dense: all-Q6_K attention 1.62 vs 1.42 GiB; Q6_K/Q8_0 shared experts 0.20 vs 0.14; Q6_K GDN out 0.43 vs
  0.41; the Q8_0 PLE key -0.02. The Q8_0 hc become BF16 in the pack (1.19 GiB, like ours); the F32 router BF16 (0.12, like
  ours).
- RAM: expert arena 46.84 GiB page-locked as today (39.38 for IQ2_XS); embedding +0.17 GiB host (Q6_K); P028x's 12 GiB
  chat cache fits; floor and swap rules unchanged.
- Karl's rule (day1): both fit (UD-IQ3_XXS 46.84 in 73.38 GiB, margin 26.6; UD-IQ2_XS 39.38 in 73.17). **UD-IQ3_XXS ties
  with our IQ3_S on expert bytes, so the rule cannot choose** (day1's "PICK UD-IQ3_XXS" is only list order - kit gap,
  section 8). UD-IQ2_XS is smaller, so not the rule's pick. The rule's pick among all Flash-Next files is still UD-Q4_K_XL
  (71.73 GiB, margin 0.74, TIGHT), which v3.1 did not re-make.
- Decode (day1's model, reads ~9 % low on Flash-Next): UD-IQ3_XXS 144, ours 145, UD-IQ2_XS 165 tok/s. The -135 main slots
  ~ -0.25 to -0.55 % (F1's +0.5-1.1 % for 396 helper slots, a helper slot = 0.7 of a main slot).
- Disk: 157.9 GB free; UD-IQ3_XXS alone would leave 74.3 GB (under the 100 GB floor); both (159.5 GB) do not fit.

## 6. #444

Upstream issue Niko1221/Strata#444 (read with `gh`, nothing posted): "How do I make it use the models I already have?",
10-02, closed. The user pointed `--gguf-dir` at Unsloth's UD-IQ3_XXS and UD-Q2_K_XL; setup refused them; the maintainer
said only the GSQ-RCO quants, the Coder's IQ1_M, Swift's files and UD-Q4_K_XL work, no technical reason. The fix (v0.1.35)
is setup.py's `gguf_unsupported` name check (setup.py:3245-3257, the MODELS allow-list; tools/test_setup_choices.py:137).
The pre-v3.1 Qwen files pass today's tables (UD-IQ3_XXS IQ2_S/IQ4_NL x 47 + IQ3_S/IQ4_NL x 1; UD-Q2_K_XL IQ2_XS/IQ4_NL x
47 + IQ3_XXS/IQ4_NL x 1). **Correction to SELFTEST.md / NOTES 09:3x:** "IQ3_XXS downs = the reason behind setup's
UD-IQ3_XXS / UD-Q2_K_XL refusals" holds for GLM-5.3's file (FF 2048), not Qwen's: on Flash-Next a 256-value-block down
(IQ3_XXS, IQ2_XS, Q2_K, Q3_K) is impossible by shape (640 % 256 != 0, iq_kernels.cu:5477), so Unsloth's Flash-Next downs
are IQ4_NL, Q2_0, Q5_0 or Q8_0.

## 7. Options (nothing is missing, so (a) and (b) are not needed to run v3.1; priced for what they add)

### (c1) As shipped - the first arm, testing Unsloth's claim as published
- Download all shards, 83.6 GB, ~40 min at fetch_model's 35 MB/s cap, once disk is decided.
- Pack: `tools/iq_pack.py --gguf <shard 1> --out bringup/out/ud31/pack --compat-bf16` (~1.4 GB, seconds, v4 index).
- Config: P028x's own with only `--pack`, `--native` (shard 1/4) and `--ple-gguf` (shard 4/4) changed; keep the drafter,
  the env switches, `--expert-cache-device1 3300`, the 12 GiB chat cache (same model and shapes, so the series' switches
  apply). STRATA_MMVQ_IL_ROWS has no Q8_0 rows, so the few Q8_0 projections take the plain kernel. Do NOT use day1's
  `day1-check/day1/ud31.json` (a Qwen4-style stock config: spec off, switches dropped, helper 3,704, chat cache 2 GiB,
  header-file paths).
- Tests: exact7 at the matched pin twice (repeatability; new file, own REF); long40 KL against a local reference for both
  ours and v3.1 (relative; UD-Q4_K_XL from the HF cache is the closest higher-precision quant here; Q8_0 / BF16 do not
  fit); the suite at medium; the 9-workload screen x3 vs P028x.

### (a) Splice - Round 15's method, an expert-only A/B with an exact pack
- `work/r15/splice.py` (work/r12/a7splice.py made general): v3.1's 144 routed-expert tensors + our 1,080 others (dense,
  embedding, n-gram table); names and shapes match (checked); MTP outside the GGUF either way.
- vs Round 15: only v3.1's shards 1-3 needed (54.8 GB download; its n-gram shard unused); splice.py as is writes one
  83.6 GB file copying our table - a ~15-line variant writes only 54.8 GB (keeps our shard 1's `split.*` keys, writes only
  shard 1's tensors, our shard 2 beside it as a hard link); **no `--compat-bf16`** (our hc and PLE projections are BF16;
  r15q5s's pack: "1.5 GB in 1 s, no --compat-bf16") -> the dense path stays bit-identical to P028x, P028x's config applies,
  the 5080 keeps **4,584** slots; native pack v3 (no split layer).
- Time: Round 15 wrote 122.6 GiB in 118 s -> ~1 min; then sync and evict before any GPU start (Round 15: 123 GiB of dirty
  pages tripped the swap guard while an engine page-locked its memory).
- Disk: 54.8 downloaded + 54.8 written = 109.6 GB.
- Limit: not the file Unsloth measured (their 99.9 % includes their Q6_K/Q8_0 dense): it answers "are their experts better
  than ISTA's at equal bytes", not "is their file better".

### (b) Type support for IQ3_XXS and other 256-value-block downs - not needed for Flash-Next (by shape); sized for Qwen4
- Decode: add X(18) (and X(17) / X(22) / X(10) / X(11) if needed) to `STRATA_D_FMTS` (iq_kernels.cu:852/854); `Fmt<18>`,
  `Fmt<17>`, `Fmt<22>` exist for gate/up with their q8_1 dots -> a list change + one template instance per down kernel
  per arch (89;120); Q2_K / Q3_K need new `Fmt`s.
- Prompt: MMQ lists IQ3_XXS / IQ2_XS / IQ2_S (moe_mmq.cu:318; check it is role-agnostic); the fused int8 downs take IQ4_NL
  / Q2_0 only (moe_fused_iq.cu:2271) and are tiled for 2560/640 anyway (SHAPES.md) - Qwen4 needs that work regardless.
- CPU: the generic ggml-cpu dot covers any type, but the down activation buffer caps n_ff at 768 at Q8_K
  (native_expert.hpp:17-19) - raise it. iq_pack: type-generic.
- ~a day of code + a build + a kernel-vs-reference check + a GPU gap for exact7 x2 + KL. Only when Qwen4's headers show
  such downs.

### (c2) Engram swap - a Q5_1 or Q8_0 n-gram table via `--ple-gguf` (+9.6 / +25.6 GB disk, more SSD bytes per token);
a separate, later A/B; first check that the engine accepts the sidecars' split keys.

### (c3) UD-IQ2_XS - only if Karl wants speed over his rule: +467 5080 slots, day1's decode estimate +14 %; against: 9
layers off the fused prompt path, 2.80 bpw experts.

## 8. What this rehearsal teaches for Qwen4 day one (kit gaps)

1. The header fetch works and is cheap (~11 MB per quant; Unsloth's shard 1 is metadata only). `bringup/fetch_model.py
   heads` needs a pinned PINS.json with sha256s, writes only under models/ unless `--dest-anywhere`, ranges up to 512 MiB;
   a `heads REPO@COMMIT --match` path into work/ with a 64 MiB cap would save a step (today's scratch fetcher is one).
2. Unsloth's current layout to expect on day one: shard 1 metadata-only and unpadded (needs 5fde38470 - upstream has it);
   layers split across shards (v4 index); the n-gram table as the last shard, shared by all quants, plus "mix n match"
   engram files; MTP as separate llama.cpp-format GGUFs. day1 handled all of these but reports none - add info lines.
3. **Qwen4's drafter is the open item.** Ours comes from the original checkpoint via tools/mtp_fetch.py; if that cannot
   read Qwen4's checkpoint, Unsloth's `mtp-*.gguf` (nextn layer + hc_head tensors) is the other source - it needs a
   converter to our rt format. Without a drafter there is no `--spec`, and decode drops a lot.
4. day1 needs a same-model swap mode (shape keys and tokenizer match the served file -> write P028x with the three paths
   swapped) and `--files-at DIR` (today its config points at the header files).
5. Ties under Karl's rule: day1 silently picks one of two equal-size quants - it should say "tie: quality decides" and point
   at the KL step.
6. Tell a shape limit from a missing kernel: print per file which down types FF allows (`n_ff % qk`) - that would have
   prevented the #444 misreading. For Qwen4 check `expert_feed_forward_length` first: a multiple of 256 -> Unsloth's low
   quants carry IQ3_XXS / IQ2_XS / Q2_K / Q3_K downs and option (b) becomes day-one work.
7. KL reference: the published KLDs are vs BF16 on Unsloth's data; locally nothing above Q4 fits, so day one's KL is
   relative to the largest local quant - choose and name that reference config before the release.
8. Disk: one ~84 GB quant already breaks the 100 GB floor today (157.9 GB free) - freeing space needs Karl's decision
   before Qwen4 lands.
9. Repo churn: pin the commit; the per-file lastCommit from the API (expand=1, paginated) shows which quants were really
   re-made (here IQ1_M...Q3_K_XL; Q4_K_XL only re-split); Unsloth also re-uploaded on 10-05.

## Files

- Headers: `work/qwen4-kit/unsloth-v31/headers/` (UD-IQ3_XXS/, UD-IQ2_XS/, MTP/, engram/, pre-v31/, FETCH-LOG-*.json).
- Scratch: `work/qwen4-kit/unsloth-v31/scratch/` (fetch_heads.py, slots_v31.py, slots_splice.py, slots_v31.json, the API
  listings).
- day1 runs (each with its `*.stdout.txt`): `results/qwen4-kit/unsloth-v31/day1-check/` (the v3.1 pair + ours, 0.2.10
  tables); `day1-check-p028x-tree/` (against the served tree); `day1-pre-v31/` (the 10-06 UD-IQ3_XXS / UD-Q2_K_XL).
- Nothing installed in configs/; nothing written outside work/qwen4-kit/unsloth-v31/ and results/qwen4-kit/unsloth-v31/.
