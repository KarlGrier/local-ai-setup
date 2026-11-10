# NLL many-positions: recompute on distinct texts (11-05)

Written by a helper; saved by Claude (the helper's .md write was refused). CPU only, from the rows the two gaps already
wrote (`results/r23/nll-many/gap/rows.tsv`, `results/r23/gdn-nll/gap/rows.tsv`). No engine, gate or gap component ran;
nothing in the gap folders, `ADOPTED-BOUND.json` or any rules file was changed. Numbers: `recompute.json`; score.py's
printouts: `compare-*.txt` (this folder). Scripts: `work/r23/scratch-recompute/` (overlap.py, spans.py, dedup.py,
stats.py, extra.py).

## Summary

- **Dedup, by token ids:** 32k = pp32k; tf-long64k = tf-long96k (over the scored 32,768 tokens); pp8k = 32k's first 8,011
  tokens. One more partial overlap: a 5,064-token span shared by 32k and tf-long28k (kept under Karl's rule; removing it
  changes nothing). 11 -> 8 texts, 31,408 -> 22,597 positions.
- **Bootstrap:** score.py resampled 2,048-token blocks - not positions, not texts. Its own block scan shows the SE still
  rising at text level, so it understates by ~2.2x; the duplicates understated it further.
- **The adopted bound is NOT valid on this data:** every comparison that is not byte-identical has a corrected SE 5 to
  6.5 x the 0.01 cap, including the two references the band is built from.
- **CPU share 0.4:** a per-token mean; on distinct texts -0.100 -> -0.063 (~6.5 % perplexity), text CI [-0.153, +0.049]
  includes 0, 3 of 8 texts the other way - and not a one-setting change (the fused int8 kernels never ran in that arm).
  Unfused is a clean single change (-0.084) but its CI also includes 0. Neither can be read as accuracy.
- **GDN on:** -0.149; outside the band on NLL only with 2,048-token blocks (whole texts: underpowered); outside through
  the KL checks, robustly only on the KL > 1 rows count.
- **The decode-path gap** scores the same texts and rows: it adds 0 texts and 0 positions. SE <= 0.01 at the text level
  would need ~200 distinct 32K texts.

## 1 The texts, compared by token ids

Compared as scored (cut at 32,768 tokens), with exact runs of >= 32 tokens.

| pair | overlap | rows in the gap |
|---|---|---|
| 32k = pp32k | identical: all 32,768 scored tokens and the files (32,769 tokens) | byte-identical dumps (ref); identical rows in every arm (3,968 / 3,968) |
| tf-long64k = tf-long96k | identical over the scored 32,768 tokens (the files differ after) | byte-identical dumps; identical rows in every arm |
| pp8k vs 32k | pp8k's first 8,011 tokens are 32k's; its last 8 differ | rows identical up to 7,160; from 7,168 (106 rows) pp8k's last chunk is partial, so its rows differ |
| 32k vs tf-long28k (not identical) | 32k[20,336:25,400] = tf-long28k[9,153:14,217], 5,064 tokens with different preceding context; also a 69-token piece | correlated, not identical; kept; sensitivity in section 3 |
| every other pair | only the 40-53-token chat header (below 1,024, not scored) and matches <= 650 tokens (<= 2 % of a text) | - |

Dedup as Karl ruled: keep 32k-32768 and tf-long64k-32768; drop pp32k-32768, tf-long96k-32768 and pp8k-8019.
Aliases (dumps byte-identical file by file, `cmp`): x28h = s210 = ref (= ref2); x28h-unfused = s210unf = unfused;
x28h-cpushare = s210cpu = cpushare - so the "P028x as reference" block and the GDN gap's band are the same numbers as
the ref block.

## 2 What score.py's bootstrap resamples

- **Unit:** a block = (text, pos // 2048), drawn with replacement (10,000 replicates, seed 20261104), the same draws for
  every arm: 129 blocks on the 11 texts, 93 on the 8 distinct texts. Neither single positions nor whole texts.
- **Block scan:** score.py's own `--block-scan` already showed the SE rising monotonically up to the whole text on the 11
  texts (unfused 0.017 -> 0.046): 2,048-token blocks do not reach the correlation length.
- **On distinct texts:**

| block | se unfused | se cpushare | se v2 | se GDN on |
|---|---|---|---|---|
| 1,024 | 0.0213 | 0.0215 | 0.0213 | 0.0212 |
| 2,048 | 0.0277 | 0.0277 | 0.0262 | 0.0258 |
| 4,096 | 0.0348 | 0.0360 | 0.0355 | 0.0356 |
| 8,192 | 0.0455 | 0.0415 | 0.0469 | 0.0455 |
| text | 0.0606 | 0.0515 | 0.0650 | 0.0562 |

- **A per-position bootstrap** would have given, for unfused, sd/sqrt(n) = 0.0071 - 8.5 x smaller than the whole-text SE.
  The text-level design effect is 49-84: the 22,597 positions carry the information of ~270-460 independent ones.
- **Caution:** with 8 texts (effectively 6.4, sizes differ) the whole-text bootstrap is itself crude; a cluster-robust SE
  (CR1), a delete-one-text jackknife and a t(7) interval agree with it to ~10 %.

## 3 Recomputed comparisons: NLL gap (reference ref = P021n fused)

d in nats/token; negative = lower NLL than ref; CIs 95 %.

| arm | d (11 texts) | d (8 distinct) | se, 2,048 blocks | CI, 2,048 blocks | se, whole texts | CI, whole-text bootstrap | t(7) CI (CR1) | texts lower / higher | se <= 0.01? |
|---|---|---|---|---|---|---|---|---|---|
| unfused (R1) | -0.1241 | -0.0835 | 0.0278 | [-0.138, -0.029] | 0.0603 | [-0.176, +0.060] | [-0.227, +0.060] | 5 / 3 | no |
| cpushare (R2) | -0.0999 | -0.0632 | 0.0274 | [-0.117, -0.011] | 0.0514 | [-0.153, +0.049] | [-0.190, +0.064] | 5 / 3 | no |
| v2 | -0.0489 | -0.0068 | 0.0266 | [-0.057, +0.047] | 0.0647 | [-0.096, +0.158] | [-0.151, +0.137] | 4 / 4 | no |
| ref2, x28h, x28h-nov2, r28h | 0 exactly | 0 exactly | 0 | - | 0 | - | - | - | yes (identical) |

The 11-text values reproduce decision.txt exactly. The dedup moved d toward 0 because the two texts counted twice were
among the most negative (32k: unfused -0.171, GDN on -0.289; tf-long64k: -0.260, -0.245); pp8k was mostly a copy of 32k.
The equal-weight mean over the 8 texts even has the opposite sign: unfused +0.025 +/- 0.097, cpushare +0.017 +/- 0.083,
v2 +0.126 +/- 0.134.

Per-text d (nats/token; ref NLL = that text's mean):

| text | positions | ref NLL | unfused | cpushare | v2 | GDN on |
|---|---|---|---|---|---|---|
| 32k | 3,968 | 3.06 | -0.171 | -0.116 | -0.174 | -0.289 |
| tf-long28k | 3,456 | 2.27 | -0.123 | +0.138 | +0.012 | -0.188 |
| tf-long40k | 3,968 | 4.11 | -0.172 | -0.007 | -0.012 | -0.146 |
| tf-long64k | 3,968 | 4.23 | -0.260 | -0.250 | -0.125 | -0.245 |
| tf-long112k | 3,968 | 3.15 | +0.106 | -0.129 | +0.012 | -0.198 |
| pp4k | 384 | 2.18 | +0.430 | +0.497 | +0.392 | +0.454 |
| ldrsyn20k | 1,886 | 4.78 | -0.053 | -0.123 | -0.066 | -0.002 |
| rep9k | 999 | 10.26 | +0.443 | +0.128 | +0.966 | +0.597 |

rep9k's KL is ~0.0001 in every arm while its ref NLL is 10.3 nats/token: its d is noise in the log-probabilities of
tokens the model gives almost no chance, not a distribution difference.

KL on the distinct texts (bounds from the references: mean <= 0.16995, p90 <= 0.28074, KL > 1 rows <= 650, changed top-1
<= 2,426.6):

| arm | KL mean | p90 | KL > 1 rows | changed top-1 | KL checks |
|---|---|---|---|---|---|
| unfused | 0.14973 | 0.25190 | 649 | 2,160 | (reference) |
| cpushare | 0.15450 | 0.25522 | 635 | 2,206 | (reference) |
| v2 | 0.14433 | 0.21260 | 621 | 2,043 | PASS on all four, robust at the text level |

Sensitivity (tf-long28k's shared span removed): unfused -0.084 (se 0.062), cpushare -0.072 (0.048), v2 -0.010 (0.066),
GDN on -0.147 (0.057) - nothing changes.

## 4 The adopted bound's terms, recomputed

- Band: 1.10 x max(0.0835, 0.0632) = **0.0918** (was 0.1365); under the whole-text bootstrap its 95 % range is
  [0.026, 0.196].
- v2: margin 0.044 (2,048 blocks) / 0.106 (whole texts); se > 0.01 under both -> UNDERPOWERED (unchanged).
- Identical arms PASS through byte identity, not through the bound.
- **Validity, plainly:** the corrected SE is above 0.01 for every comparison that is not byte-identical - v2 0.065
  (6.5 x the cap), unfused 0.060 (6 x), GDN on 0.056 (5.6 x), cpushare 0.051 (5 x). Even at score.py's 2,048-token unit
  the SE is ~2.7 x the cap. **The adopted bound is not valid on this data for any of these comparisons, including the two
  references the band is built from.**

## 5 GDN result, restated (stock v0.2.10, GDN on vs off; both arms fused)

NLL: d = **-0.149** nats/token on the 8 distinct texts (-0.184 on 11):

| unit | se | 95 % CI |
|---|---|---|
| 2,048-token blocks | 0.026 | [-0.200, -0.097] |
| whole texts (bootstrap) | 0.056 | [-0.221, -0.005] |
| whole texts (CR1, t(7)) | 0.052 | [-0.272, -0.027] |

- The two-sided band test (band + 1.645 se): OUTSIDE (lower NLL) with 2,048-token blocks; with whole texts NOT outside -
  UNDERPOWERED.
- All five long texts (32k and the four tf-long) are lower by 0.15-0.29, ldrsyn20k ~0; the two short texts higher (pp4k
  +0.45, rep9k +0.60); the equal-weight mean -0.002. "GDN on lowers NLL" holds on the long texts but is not shown across
  texts, and the NLL band test is not valid on this data.

KL:

| check | GDN on | bound | result | text-bootstrap replicates over the bound |
|---|---|---|---|---|
| mean | 0.1775 | 0.1700 | OUTSIDE | 86 % |
| p90 | 0.3202 | 0.2807 | OUTSIDE | 88 % |
| KL > 1 rows | 750 | 650 | OUTSIDE | 99.6 % (robust) |
| changed top-1 | 2,391 | 2,427 | now INSIDE (was OUTSIDE on 11 texts) | 33 % |

**Verdict:** "outside the rounding band" still holds on the distinct texts, but only through the KL checks, and of those
only the KL > 1 rows count holds at the text level. The adopted gate rule is still FAIL through the KL checks; its NLL
part is UNDERPOWERED.

## 6 The unit, and what cpushare and unfused differ in

**The unit is a per-token mean** (nats per scored token), not a total. 11 texts: cpushare -0.0999 (ref's perplexity
~10.5 % higher); 8 distinct texts: cpushare -0.063 (6.5 %), unfused -0.084 (8.7 %), GDN on -0.149 (16 %).

These paths move single-position NLL by 0.48 nats on average, and the KL mean against ref is ~0.15 (the batched-vs-window
rounding level is ~0.01-0.02). The mean d is a small leftover of that large two-sided scatter - not driven by a few
outliers (the top 1 % of differences carry 0.5 % of the sum), a broad shift inside some texts and reversed in others:
exactly the case where the text has to be the unit.

**cpushare vs ref - full diff.** Same: requests, positions, texts, engine arguments, KV (fp16), the config file
(`configs/r21n1.json`); the only env difference is `--env STRATA_PREFILL_CPU_SHARE=0.4` (`STRATA_PREFILL_CPU_SHARE_MAX=1792`
from the config in both). Different beyond the share:
- Start lines: "prompt experts on the fused int8 kernels" is missing in cpushare, x28h-cpushare and s210cpu - the fused
  kernels never ran.
- Prompt speed 11-20 % faster on the long texts, 74 % faster on rep9k.
- Why (P021n source, `src/prefill/prefill.cpp`): with a share on, the threshold for the streamed walk rises from 1,024 to
  1,792 tokens; the fused kernels run only on streamed chunks; the share acts only on staged chunks. The chunk size is not
  logged - 1,024 tokens, inferred (pp8k's rows leave 32k's at 7,168 = 7 x 1,024 in every arm; ref took the fused path, so
  its chunks were >= 1,024; cpushare never did, so its chunks were < 1,792).
- Result: in the cpushare arm every chunk took the staged walk, with the GPU's experts on MMQ and 40 % of the non-resident
  experts on the CPU.

So **cpushare = fused off + staged walk + CPU share**. It shares the fused-off change with unfused: per-position
differences correlate at 0.50, per-text d at 0.72, and d(cpushare - unfused) = +0.020 (SE 0.070). The two references are
therefore not independent; both mostly measure "fused int8 off". From the source, not measured: served chunks of >= 1,792
tokens keep the fused path even with the share on, so this arm is not the served arithmetic for long prompts either.

**unfused vs ref:** a clean one-variable change (only STRATA_PF_FUSED differs; the start lines differ only by the fused
line; prompt speed 0.994-0.999 of ref). d -0.084 on the distinct texts, whole-text CI [-0.176, +0.060], equal-weight mean
+0.025 - not established as accuracy either.

**A check inside one build (106 positions):** pp8k's last, partial chunk ran without the fused kernels while 32k's chunk
at the same rows (same context and target) ran with them: in ref d -0.034 (se 0.097), mean |difference| 0.42 nats.
Changing one chunk's path in the same build moves single positions as much as the arms differ from each other.

## 7 The decode-path gap, and how many texts SE <= 0.01 would need

- The decode-path gap scores pp4k, rep9k, ldrsyn20k, 32k, tf-long64k, tf-long28k, tf-long112k, tf-long40k - the same 8
  texts at the same rows (every 8th from 1,024), at most 22,597 positions, ~14,000 planned: **0 new distinct texts, 0 new
  distinct-text positions**. Its rules also bootstrap over 2,048-token blocks, so its CIs will be too narrow the same way.
- Texts needed for a whole-text SE <= 0.01: scaled from the current mix - unfused ~292, cpushare ~212-232, v2 ~296-336,
  GDN on ~215-248; if every new text is a full 32K read (from the spread of the 5 full-length texts, rough) - unfused ~190,
  cpushare ~214, v2 ~75, GDN on ~31. The references set the requirement: **~200 distinct 32K texts** (~6.5 M prompt
  tokens, ~1.6 h of engine time per arm, ~17 GB of dumps per arm). The real constraint is finding ~200 distinct long texts.
