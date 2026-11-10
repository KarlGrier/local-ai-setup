#!/usr/bin/env python3
# AMENDMENT 2026-11-07 (Karl) - it applies from now on, not to finished gates; recorded before the confirmation gap
# (work/r23/gap-confirm0211.sh). Karl, 11-07, on results/r23/port-0211/HUNT-1107.md:
#   "Measurement rule: yes, as a dated amendment applying from now on. Per-workload prompt numbers exclude the
#   chat-cache save. Time the save as its own line in every screen, and judge it separately against its own noise,
#   taking its two-speed pattern into account, so a real regression in saving still shows."
#   "Prompt clock: engine clock for the per-workload prompt numbers, as you recommend. The overall screen rule stays on
#   the client clock minus the save, at -1%. Add one INFO flag, not a fail: if a workload's outside-engine time is worse
#   in all 3 passes by more than its own spread, flag it for review, so a server-side slowdown hitting one workload
#   can't hide under the overall rule. Record the amendment as dated before the confirmation gap."
# The rule as implemented (work/r22/g17_rules.py, section "11-07 park amendment"):
#   - Per-workload prompt numbers exclude the chat-cache save and are taken on the engine clock: prompt tokens / (the
#     engine's prompt ms - the `chat cache: parked ... in N ms` line logged just before that request). They feed Karl
#     11-03's no-loss rule (wl_noloss) and g16's "no workload more than 3 % below".
#   - The overall screen rule (g16's geometric mean, -1 %) stays on the client clock minus the save: prompt tokens /
#     (TTFT - save).
#   - The save is judged as its own "chat-cache save" line (save_rule), against its own noise and with its two levels
#     taken into account. The level mix is INFO.
#   - The outside-engine INFO flag (outside_flags). It is INFO and never changes a verdict.
#     - A workload's outside-engine time per request = client TTFT - the engine's prompt ms. The save is inside the
#       engine figure, so it cancels.
#     - Its spread = the larger of the two arms' half-ranges over their passes.
#     - Flag: every pass of the arm is above the base's mean by more than that spread -> "outside-engine time worse in
#       every pass - for review (INFO)".
# A gate that started before 2026-11-07 14:00 keeps the rules it ran under; so does screen data without engine logs.
# This file's own screen code is the pre-amendment client clock of its finished gate(s) and is kept as it ran. A new
# gate takes the amended numbers, the save line and the INFO flag from work/r22/g17_rules.py, not from a copy of this
# file's code.
"""decpath_rules.py - r23 (Karl 11-05): THE DECODE-PATH CHECK, the rules of work/r23/gap-decpath.sh, written BEFORE any run.

Karl 11-05: "run the decode-path check, and put it before Basalt a: the Basalt prompt-path port would otherwise be judged
against a prompt path that may itself be the outlier. Score the same positions token by token through the decode path.
For each prompt variant (default fused, unfused, CPU share, v2 kernels, GDN on), report its distance from the decode
path, by prompt length. If the default fused path is the outlier: tell me how big the effect is on real long-prompt
work and what turning it off would cost in prompt speed, before changing anything."

WHY: the NLL gap (results/r23/nll-many/gap) and the stock GDN gap (results/r23/gdn-nll/gap) scored every 8th prompt row
(1,024 on) of 11 long texts through the PROMPT path (STRATA_PREFILL_DUMP_R_ALL + score.py's offline head). Every
variant has LOWER NLL than the default fused path (unfused -0.124, cpushare -0.100, v2 -0.049, GDN on -0.184 nats).
The default's rows are identical for stock v0.2.10, P021n and P028x. Which side is right is open; the decode path is
the reference here. NOTE (found writing this): the 11 texts are 8 distinct ones - 32k = pp32k (all 32,768 tokens),
tf-long64k = tf-long96k (all 32,768), pp8k = 32k's first 8,011 - so the NLL gap's block bootstrap counted three texts
twice. This check reads each distinct text once.

THE DECODE PATH (what "token by token through the decode path" can mean in these engines, no build)
  serve mode needs --spec >= 2, so the verify windows that read a prompt (STRATA_LOGPOS, upstream's teacher-forced
  scorer, every build since 0.1.x) are at least 2 rows wide. 1-row windows exist only in the measurement twin
  engine-r22p028xm (P028x + 5 MEASUREMENT commits): force=N + STRATA_FORCE_T1=1 scores every forced token in a 1-token
  window "as speculation-off decode draws it" (gap 16), but writes NLL and the top pick only (no distribution, no KL).
  So:
  dec     (the reference) the served binary engine-r22p028x, configs/x28h.json (P028x without vision), every token of
          the text read through 2-ROW verify windows (--spec 2, --short-read above the text length) with STRATA_LOGPOS +
          STRATA_LOGPOS_TOPK=64: per position the log-probability of the text's next token, the full-vocabulary argmax
          and the 64 most likely tokens. Every position's K/V comes from the decode path too. Settings otherwise score.py
          run's (= quant_quality's fixed yardstick): --expert-cache 1 (every expert on the CPU pool, as decode's misses),
          --pcie-frac 0, no adaptation, no suffix drafts, no prompt cache, FP16 K/V, STRATA_ROUTE_TAIL_SKIP=0,
          STRATA_PREFILL_CPU_SHARE=0 (the prompt-path switches never run: all variants share this one reference).
          With --pcie-frac 0 and one cache slot the experts' device does not depend on the window shape (gr-fork.md
          point 2), so 2-row windows are the decode path's verify windows with the smallest shape serve allows.
  dec1    (window check, optional) engine-r22p028xm, the same settings, force=N + STRATA_FORCE_T1=1: 1-row windows on
          ldrsyn20k (16,110 tokens; prompt = its first 2 tokens, every later token forced). NLL + top pick only.
  s210dec (stock check, optional) engine-v0210stock, configs/s0210-h.json, as dec, on ldrsyn20k.
  Texts for dec, in this order, each read whole while the measured rate says it fits the budget (DECPATH_DEC_MIN,
  default 50 min of engine time; a long text may be cut to fit, not below 8,192 tokens): pp4k (4,096), rep9k (9,010),
  ldrsyn20k (16,110), 32k (32,768), tf-long64k (32,768), tf-long28k (28,672), tf-long112k (32,768), tf-long40k
  (32,768). Estimated ~45-55 tok/s in 2-row windows with every expert on the CPU (r21/yq: 1,000 tokens in 12.4 s at
  --spec 4; one 1-row window 20 ms at 1K, 28-36 ms at 28-32K in the NLL arms' logs): ~6 of the 8 texts in 50 min,
  ~14,000 positions (1-4K ~2,300, 4-16K ~6,700, 16-32K ~5,600).

POSITIONS: every 8th row from 1,024 on (the arms' rows: score.py run --rows all:8), up to the read length - 2. A row at p
  predicts the text's token p + 1; the dec line at p must carry that target (checked at every position).
  Strata: 1-4K [1,024, 4,096), 4-16K [4,096, 16,384), 16-32K [16,384, 32,768); blocks of 2,048 tokens inside a text
  (never across a stratum edge), 10,000 bootstrap replicates, seed 20261105, 95 % percentile intervals.

THE PROMPT VARIANTS (their rows already exist; nothing new runs for them):
  default  results/r23/nll-many/gap/x28h  (P028x fused; ref (P021n) and stock s210 must be byte-identical: aliases)
  unfused  .../gap/unfused   (P021n, STRATA_PF_FUSED=0; s210unf and x28h-unfused: aliases if byte-identical)
  cpushare .../gap/cpushare  (P021n, STRATA_PREFILL_CPU_SHARE=0.4; s210cpu, x28h-cpushare likewise)
  v2       .../gap/v2        (P021n, STRATA_PREFILL_V2=1 with Basalt's term; on P028x v2 = v2 off bitwise)
  gdn      results/r23/gdn-nll/gap/s210gdn (stock v0.2.10, STRATA_GDN_TC=1 + STRATA_GDN_CONVL2=2)
  An arm whose rows differ from every group joins as its own variant (e.g. x28h-unfused if not = unfused).
  NOTE: the served config already sets STRATA_PREFILL_CPU_SHARE=0.4 (with _MAX 1792); the yardstick forces 0, so the
  NLL gap's "default" is the share OFF and its "cpushare" arm carries the served env value (in served form the share
  acts only on chunks below 1,792 tokens).

METRICS of a variant X against dec, per stratum and over all positions:
  K   KL(dec || X) over 65 bins (dec's 64 most likely tokens + the rest; X's probabilities from the full vocabulary):
      a lower bound of the full KL, exact up to the mass outside dec's top 64. Mean, p90, rows with K > 1.
  TV  total variation over the same 65 bins = the chance that a T = 1 draw differs from the decode path's (coupled).
  A   top-1 agreement: X's full-vocabulary argmax = dec's.
  D   mean(NLL_X - NLL_dec) (signed, nats/token) and |D|-free spread mean |NLL_X - NLL_dec|.
  paired against the default: dK = K_def - K_X, dD = D_def - D_X, c = D_def - |D_X| (per replicate), with CIs.

VALIDITY (else NOT JUDGED, the reason named):
  dec ran cleanly (run_dec + env_dec PASS), >= 3 distinct texts, every used line's target = the text's next token;
  pairing: over all positions A(default) >= 0.70 and median K(default) <= 0.20 (a shifted or wrong pairing gives
  chance-level agreement and K >> 1; rounding between the window and the batched path at the same K/V is ~0.01-0.02).
  A stratum with < 500 positions or < 2 texts is THIN: reported, not judged.

THE VERDICT (overall = the headline; each stratum too), V = the variants other than the default:
  DEFAULT IS THE OUTLIER  (a) D_def > 0 with its CI above 0, and for EVERY X in V: (b) dK_X's CI above 0 (the default is
                          farther from the decode path in KL) and (c) c_X's CI above 0 (its NLL distance beyond X's)
  DEFAULT IS NOT THE OUTLIER  some X in V with neither (b) nor (c): X is not closer to the decode path in either measure
  MIXED                   otherwise (the default farther than some variants, or in one measure only): per-variant lines
  CLOSEST to the decode path: the arm (default included) with the smallest K; "tied" with the next one when the paired
  K difference's CI holds 0.

WINDOW CHECK (dec1, INFO, ldrsyn20k): W_D = mean(NLL_dec1 - NLL_dec) and W_A = top-1 agreement dec1 vs dec at every
  position from 1,024; "2-row windows stand for the 1-row decode path" if |W_D| <= max(0.02, 0.25 x the smallest
  |D_def - D_X| on the same text's positions) and W_A >= A(default) there. Beside it, D_X and A_X against dec1 (NLL
  and top pick only) on that text.
STOCK CHECK (s210dec, INFO, ldrsyn20k): mean KL(dec || s210dec) over dec's top 64 (quant_quality.py compare's rule)
  <= 0.02 and |mean(NLL_s210dec - NLL_dec)| <= 0.02 -> "x28h's decode path stands for stock's"; else a FLAG, and the
  GDN arm is also reported against s210dec on that text.

EFFECT ON REAL LONG-PROMPT WORK (reported always; the main ask if the default is the outlier): the 9-workload screen's
  prompt lengths (gap b's B1n/B1a/B1r.jsonl; fallback the 11-05 values W3 26,729, A-edit 2,677, B-write 1,370, R1
  24,240, R2 54,071, R3 5,011, R4 33,417) mapped to their stratum: after a prompt of that length, the default's next
  pick differs from the decode path's in (1 - A_def) of cases vs (1 - A_closest) for the closest variant, a T = 1 draw
  differs with probability TV_def vs TV_closest, and the NLL distance D_def vs D_closest (perplexity exp(D) - 1).
  R2 (54K) lies beyond the measured 32K (the 16-32K numbers, flagged as an extrapolation); W1 / W2 (~120 tokens) below
  1,024 (not measured). Generation quality itself is not measured here.

SPEED (what turning it off would cost): cold prompt speed, Basalt's bp90 fixtures pp16k (16,676 tokens) and pp64k
  (66,617), a fresh engine per (arm, fixture, pass), 2 passes in turned order, P028x as served (x28h, two cards):
  spd-def (as served: PF_FUSED=1, CPU share 0.4 / max 1,792), spd-unf (+ STRATA_PF_FUSED=0), spd-sh0
  (+ STRATA_PREFILL_CPU_SHARE=0, the yardstick's default env). Cost = mean_X / mean_def - 1 with the passes' spread
  (max - min) / mean beside it. GDN on: not priced (gap 17 did not measure its prompt speed) and not measured here.

OPTIONAL (only if it fits the deadline): decode gap b's Basalt arm-passes that failed 11-05 06:50-06:51 (a DeepSeek
  engine held the 5080: B decode/pp16k/pp64k pass 1, LO decode/pp16k/pp64k pass 1, LO decode pass 2 - recomputed at
  run time from gap b's cold-*.jsonl), rerun on engine-r23decode with gap b's configs into results/r23/decpath/bp90-rerun;
  merged with gap b's records in decb-merged/ (gap b's files untouched) -> decode_rules.py decide-b ->
  decision-b-merged.txt. And Karl's pillow 13.0.0 step (its own RESULT.txt; it never fails the gap).

Nothing switches; nothing is served from this; P028x stays on 8080.

11-05 REVISION, BEFORE ANY ANALYSIS (Karl 11-05, after results/r23/nll-many/recompute/REPORT.md: the 11 texts are 8
distinct, and 2,048-token-block bootstraps understate the SE ~2.2 x against whole texts; the many-positions NLL bound is
revoked as a gate: results/r23/nll-many/gap/ADOPTED-BOUND.REVOKED.json). Everything above about the runs, their settings,
the env checks, the speed arms, the pillow step and the bp90 rerun stands unchanged. The verdict, its unit and its
intervals below REPLACE "THE VERDICT" above, its per-stratum verdicts and its block-bootstrap CIs (those numbers stay in
result.json as information and are never used for the verdict). Karl, verbatim: "Verdict unit: whole texts (8). Report
the 2,048-block SE beside it, labelled, and never use it for the verdict. Fix the distance measure before the analysis
runs, and use the same one for every text. Primary rule: Outlier: the default fused path is the farthest prompt path
from the decode path in at least 7 of 8 texts. Not an outlier: it's farthest in 4 or fewer. 5 or 6: inconclusive. Write
the chance rate for the actual number of arms into the rules."
  TEXTS     the 8 distinct texts, as the dec arm reads them (its plan holds no duplicate): pp4k, rep9k, ldrsyn20k, 32k,
            tf-long64k, tf-long28k, tf-long112k, tf-long40k. pp32k (= 32k), tf-long96k (= tf-long64k) and pp8k (= 32k's
            first 8,011 tokens) are never read by dec and are dropped wherever the gaps' rows are used. The 5,064-token
            span 32k shares with tf-long28k stays (Karl's rule). Positions: every 8th row from 1,024, as before.
  DISTANCE  fixed now, the same for every text and every path: D_t(path) = the mean, over text t's scored positions, of
            KL(dec || path) over 65 bins (dec's 64 most likely tokens + the rest; the path's probabilities from its full
            vocabulary). Why: it weighs each position by what the decode path would draw; it cannot cancel the way a
            signed NLL mean does; it is not driven by tokens the model gives almost no chance (rep9k: NLL ~10 nats per
            token at KL ~0.0001 - its NLL differences are noise). A lower bound of the full KL (exact up to the mass
            outside dec's top 64), the same bound for every path.
  PATHS     byte-identical arms are one path (the dumps compared file by file): default = x28h = ref = s210; unfused =
            x28h-unfused = s210unf; cpushare = x28h-cpushare = s210cpu; v2; gdn (s210gdn): A = 5 paths expected (the
            analysis counts them and prints A). NOTE: cpushare = fused int8 OFF + the staged walk + the CPU share (the
            recompute, section 6) - not one switch, and not the served long-prompt arithmetic (served chunks of >= 1,792
            tokens keep the fused path with the share on).
  RULE      per text the farthest path = the largest D_t (the default counts only when strictly the largest; exact
            ties are not expected). k = the texts in which the default is the farthest, N = the texts read.
            N = 8: DEFAULT IS THE OUTLIER if k >= 7; DEFAULT IS NOT AN OUTLIER if k <= 4; INCONCLUSIVE if k = 5 or 6.
            Fewer texts read (dec's 50-min budget may stop at ~6): the same proportions - OUTLIER k >= ceil(7N/8), NOT
            k <= floor(N/2), else INCONCLUSIVE - FLAGGED "Karl's rule is written for 8 texts". N < 5: NOT JUDGED.
  CHANCE    if each of the A paths were equally likely to be the farthest in a text, independently: k ~ Binomial(N, 1/A).
            A = 5, N = 8: P(k >= 7) = 0.000084, P(k <= 4) = 0.9896, P(k = 5 or 6) = 0.0103
            A = 5, N = 7: P(k = 7) = 0.000013, P(k <= 3) = 0.9667, P(4-6) = 0.0333
            A = 5, N = 6: P(k = 6) = 0.000064, P(k <= 3) = 0.9830, P(4-5) = 0.0169
            A = 5, N = 5: P(k = 5) = 0.000320, P(k <= 2) = 0.9421, P(3-4) = 0.0576
            (N = 8 with A = 4: 0.000381 / 0.9727 / 0.0269; with A = 6: 0.000024 / 0.9954 / 0.0046.) The decision prints
            the exact rates for the A and N it has.
  CIs       whole texts only: the equal-weight mean over texts of D_t per path, and of the paired D_t(default) -
            D_t(path), with a t(N-1) interval (= CR1, one value per text) and a whole-text bootstrap (10,000 replicates,
            seed 20261105); the position-weighted mean with a CR1 interval (clusters = texts, t(N-1)). Beside them, the
            2,048-token-block bootstrap SE, labelled "2,048-block SE (not used for the verdict)".
  SECONDARY, information only, declared now:
   (a) the same count and means split into SHORT = pp4k, rep9k (their reads end at 4,096 and 9,010 tokens) and LONG =
       the other six (every read >= 16,110 tokens: 32k and the four tf-long texts to 28-32K, ldrsyn20k - the
       research-style text - to 16,110; the long-prompt worry is about 16K+ research and agent prompts).
   (b) per-position |dNLL| between paths, binned by position in the text: 0-2K, 2-8K, 8-16K, 16K+ (scored rows start at
       1,024): the two references (unfused, cpushare) and each arm (v2, gdn) against ref (= default) - on all 8
       distinct texts from the two gaps' rows.tsv and on the dec positions - and every path against dec. Per bin: mean
       and median |dNLL|, positions, texts, a whole-text bootstrap interval of the mean; per text, its last bin's mean
       minus its first bin's (scatter growing with position = drift on long prompts).
   (c) the 1-row check (dec1, ldrsyn20k): how far the 2-row decode path sits from true 1-row windows - mean |dNLL|,
       signed dNLL and top-1 agreement at every position and per bin. "The reference is SOUND on that text" if, at the
       same every-8th rows, its mean |dNLL| to the 1-row path is <= 0.5 x the smallest mean |dNLL| of any prompt path
       to dec there, and its top-1 agreement with the 1-row path is >= the best prompt path's agreement with dec; else
       NOT SHOWN SOUND. One text only: its intervals are 2,048-block ones, labelled.
  The effect-on-real-work and speed sections stay as above (information; the per-range numbers are position-weighted).

Subcommands: rules --out F | configs [--check] | pre | plan NAME | run ... | envwatch ... | unittests | mpl-check |
  vision-check | freeze-diff | bp90-missing | merge-b | compare | decide | selftest (synthetic data and a mock engine only)
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True       # modules are loaded from trees this script must not write into
for _i, _a in enumerate(sys.argv):   # BLAS threads before numpy loads (score.py's rule; default 1)
    if _a == "--threads" and _i + 1 < len(sys.argv):
        for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ.setdefault(_k, sys.argv[_i + 1])

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = WS / "results/r23/decpath"
NLLG = WS / "results/r23/nll-many/gap"
GDNG = WS / "results/r23/gdn-nll/gap"
SCORE = WS / "work/r23/nll-many/score.py"
NRP = WS / "work/r23/nll_rules.py"
GAPB = WS / "results/r23/decode-timing/gap-b"
SCRATCH = WS / "work/r23/scratch-decpath"
STRATA = [("1-4K", 1024, 4096), ("4-16K", 4096, 16384), ("16-32K", 16384, 32768)]
EVERY, BLOCK, BOOT, SEED, TOPK = 8, 2048, 10000, 20261105, 64
MIN_POS = 1024
PAIR_A, PAIR_K = 0.70, 0.20
THIN_N, THIN_T = 500, 2
WIN_FLOOR, STOCK_K, STOCK_D = 0.02, 0.02, 0.02

# the prompt variants: key, folder, label, required. Karl's five: default, unfused, cpushare, v2, gdn.
ARMS = [("default", NLLG / "x28h", "default fused (P028x as served)", True),
        ("ref", NLLG / "ref", "P021n fused", False),
        ("s210", GDNG / "s210", "stock v0.2.10 fused, GDN paths off", False),
        ("unfused", NLLG / "unfused", "unfused (STRATA_PF_FUSED=0, P021n)", True),
        ("x28h-unfused", NLLG / "x28h-unfused", "unfused (P028x)", False),
        ("s210unf", GDNG / "s210unf", "unfused (stock)", False),
        ("cpushare", NLLG / "cpushare", "CPU share 0.4 (P021n)", True),
        ("x28h-cpushare", NLLG / "x28h-cpushare", "CPU share 0.4 (P028x)", False),
        ("s210cpu", GDNG / "s210cpu", "CPU share 0.4 (stock)", False),
        ("v2", NLLG / "v2", "v2 kernels (STRATA_PREFILL_V2=1, P021n)", True),
        ("gdn", GDNG / "s210gdn", "GDN on (stock, TC=1 + CONVL2=2)", True)]
KARL5 = ["default", "unfused", "cpushare", "v2", "gdn"]
# 11-05 revision (text-level verdict)
SHORT_FILES = ("pp4k.tokens", "rep9k.tokens")
DUP_PREFIX = ("pp32k-", "tf-long96k-", "pp8k-")          # rows.tsv names of the three duplicate texts
BINS = [("0-2K", 0, 2048), ("2-8K", 2048, 8192), ("8-16K", 8192, 16384), ("16K+", 16384, 1 << 40)]
MIN_TEXTS = 5
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131}
NLL_ROWS = NLLG / "rows.tsv"
GDN_ROWS = GDNG / "rows.tsv"

# plans: (file, cut, min_cut when it may be shortened to fit; 0 = whole or not at all)
PLANS = {
    "main": [("pp4k.tokens", 4096, 0), ("rep9k.tokens", 9010, 0), ("ldrsyn20k.tokens", 16110, 4096),
             ("32k.tokens", 32768, 8192), ("tf-long64k.prompt", 32768, 8192), ("tf-long28k.prompt", 28672, 8192),
             ("tf-long112k.prompt", 32768, 8192), ("tf-long40k.prompt", 32768, 8192)],
    "t1": [("ldrsyn20k.tokens", 16110, 4096)],
    "stock": [("ldrsyn20k.tokens", 16110, 4096)],
    "mock": [("pp4k.tokens", 2048, 0), ("rep9k.tokens", 4096, 1024), ("ldrsyn20k.tokens", 4096, 1024)],
}
# seconds for a read of L tokens: c0 L + c1 L^2 / (2 x 32768)  (per-token cost growing with the context)
COST = {"logpos": (0.017, 0.008), "force": (0.022, 0.010)}
SAFETY = 1.10
WL_FALLBACK = [("W1-think", 110), ("W2-code", 126), ("W3-research", 26729), ("A-edit", 2677), ("B-write", 1370),
               ("R1-verify20k", 24240), ("R2-report54k", 54071), ("R3-extract5k", 5011), ("R4-agent33k", 33417)]
BP_SETS = {"decode": ("conv", "struct", "prose"), "pp16k": ("pp16k",), "pp64k": ("pp64k",)}
BP_EXPECTED = [("B", "decode", 1), ("B", "pp16k", 1), ("B", "pp64k", 1), ("LO", "decode", 1), ("LO", "pp16k", 1),
               ("LO", "pp64k", 1), ("LO", "decode", 2)]      # found 11-05 07:00 from gap b's files (engine logs 1.9 KB)
TPL = WS / "configs/x28h.json"
DERIVED = {   # name: (template, top-level changes, env changes)
    "x28h-twin": (TPL, {"exe": str(WS / "engine-r22p028xm/strata"), "log": str(WS / "logs/engine-decpath-twin.log")}, {}),
    "spd-def": (TPL, {"log": str(WS / "logs/engine-decpath-spd-def.log")}, {}),
    "spd-unf": (TPL, {"log": str(WS / "logs/engine-decpath-spd-unf.log")}, {"STRATA_PF_FUSED": "0"}),
    "spd-sh0": (TPL, {"log": str(WS / "logs/engine-decpath-spd-sh0.log")}, {"STRATA_PREFILL_CPU_SHARE": "0"}),
    "vistest": (WS / "configs/P028x.json", {"log": str(WS / "logs/engine-decpath-vistest.log"), "fallback": None}, {}),
}
_MODS = {}


def load(name, path):
    if name not in _MODS:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _MODS[name] = m
    return _MODS[name]


def score_mod():
    return load("score", SCORE)


def qq_mod():
    S = score_mod()
    return S.module("pf_yardstick", S.PFY).tool()


def gate(a, status, detail):
    if getattr(a, "gate", None) and getattr(a, "gates", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail} [decpath {time.strftime('%m-%d %H:%M')}]\n")


def read_gates(p):
    g = {}
    for line in Path(p).read_text().splitlines() if Path(p).exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)
    return g


def stratum(p):
    for name, lo, hi in STRATA:
        if lo <= p < hi:
            return name
    return None


def load_ids(f):
    return score_mod().load_ids(f)


def plan_items(name, ids_of=None):
    ids_of = ids_of or load_ids
    out = []
    for f, cut, mn in PLANS[name]:
        n = min(len(ids_of(f)), cut)
        out.append({"file": f, "cut": n, "min_cut": min(mn, n) if mn else 0, "name": f"{f.split('.')[0]}-{n}"})
    return out


def max_len(name, ids_of=None):
    return max(x["cut"] for x in plan_items(name, ids_of))


def model_s(kind, L):
    c0, c1 = COST[kind]
    return c0 * L + c1 * L * L / (2 * 32768)


# ================================================================================================ rules / configs / pre
def cmd_rules(a):
    Path(a.out).write_text(__doc__.split("\nSubcommands:")[0].rstrip() + "\n")
    print(f"wrote {a.out} (sha {hashlib.sha256(Path(a.out).read_bytes()).hexdigest()[:12]})")
    return 0


def derived(name):
    tpl, top, envc = DERIVED[name]
    c = json.loads(Path(tpl).read_text(encoding="utf-8-sig"))
    c.update(top)
    c["env"] = dict(c.get("env", {}), **envc)
    return c


def cmd_configs(a):
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    bad = []
    for name, (tpl, top, envc) in DERIVED.items():
        want = derived(name)
        want["_comment"] = (f"r23 decode-path gap (Karl 11-05; work/r23/gap-decpath.sh): {Path(tpl).name} with "
                            + ", ".join([f"{k}={v}" for k, v in top.items()] + [f"env {k}={v}" for k, v in envc.items()])
                            + ". Measurement only, never served.")
        p = d / f"{name}.json"
        if not a.check:
            p.write_text(json.dumps(want, indent=1) + "\n")
            continue
        try:
            have = json.loads(p.read_text())
        except (OSError, ValueError) as e:
            bad.append(f"{name}: {e}")
            continue
        h, w = dict(have), dict(want)
        h.pop("_comment", None), w.pop("_comment", None)
        if h != w:
            keys = sorted(k for k in set(h) | set(w) if h.get(k) != w.get(k))
            bad.append(f"{name}: differs from {Path(tpl).name} + its changes in {keys}")
        if have.get("env", {}).get("STRATA_ROUTE_TAIL_SKIP") != "0":
            bad.append(f"{name}: STRATA_ROUTE_TAIL_SKIP is not 0")
        if not Path(have.get("exe", "")).exists():
            bad.append(f"{name}: exe {have.get('exe')} missing")
    if a.check:
        print("configs " + ("OK: " + ", ".join(DERIVED) if not bad else "BAD: " + "; ".join(bad)))
        return 1 if bad else 0
    print(f"wrote {len(DERIVED)} configs to {d}")
    return 0


def cmd_pre(a):
    """before the gap: the variants' rows exist and ran cleanly in their gaps, the configs, the rules file"""
    bad, info = [], []
    for k, d, lab, req in ARMS:
        g = read_gates(d.parent / "gates.txt")
        n = d.name
        ok = (d / "index.json").exists() and g.get(f"run_{n}", ("",))[0] == "PASS" and g.get(f"env_{n}", ("",))[0] == "PASS"
        if not ok:
            (bad if req else info).append(f"{k} ({d.relative_to(WS)}): {'no index.json' if not (d / 'index.json').exists() else 'run/env gate not PASS'}")
            continue
        rows = json.loads((d / "index.json").read_text()).get("rows")
        if rows != "all:8":
            bad.append(f"{k}: rows {rows}, not all:8")
    for c in ("x28h.json", "s0210-h.json", "P028x.json"):
        e = json.loads((WS / "configs" / c).read_text(encoding="utf-8-sig")).get("env", {})
        if e.get("STRATA_ROUTE_TAIL_SKIP") != "0":
            bad.append(f"configs/{c}: STRATA_ROUTE_TAIL_SKIP={e.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}")
    rt = OUT / "rules.txt"
    want = __doc__.split("\nSubcommands:")[0].rstrip() + "\n"
    if not rt.exists() or rt.read_text() != want:
        bad.append("results/r23/decpath/rules.txt is missing or not this script's rule text")
    for f in {x[0] for p in ("main", "t1", "stock") for x in PLANS[p]}:
        if not (score_mod().PR / f).is_file():
            bad.append(f"prompt file {f} missing")
    line = ("PASS " if not bad else "REFUSED ") + ("; ".join(bad) if bad else
                                                   f"variants' rows present ({', '.join(k for k, *_ in ARMS if (_[0] / 'index.json').exists())}); "
                                                   f"optional missing: {', '.join(info) or 'none'}; rules.txt = the script's")
    print(line)
    return 1 if bad else 0


def cmd_plan(a):
    its = plan_items(a.name)
    tot = 0.0
    for x in its:
        t = model_s(a.kind, x["cut"])
        tot += t
        print(f"{x['name']:22s} {x['cut']:6d} tokens  min cut {x['min_cut']:5d}  ~{t / 60:5.1f} min (cumulative {tot / 60:5.1f})")
    return 0


# ================================================================================================ the engine runner
class Budget:
    """the read-time estimate: the cost model scaled by what the finished reads took"""

    def __init__(self, kind, budget_s, clock=time.time):
        self.kind, self.clock, self.t0 = kind, clock, clock()
        self.end, self.done_model, self.done_real = self.t0 + budget_s, 0.0, 0.0

    def scale(self):
        return max(0.5, self.done_real / self.done_model) if self.done_model > 0 else 1.0

    def est(self, L):
        return SAFETY * self.scale() * model_s(self.kind, L)

    def fit(self, item):
        """(cut to read, note) or (0, why)"""
        rem = self.end - self.clock()
        if self.est(item["cut"]) <= rem:
            return item["cut"], ""
        if item["min_cut"] <= 0:
            return 0, f"needs ~{self.est(item['cut']) / 60:.1f} min, {max(rem, 0) / 60:.1f} left"
        lo, hi = item["min_cut"], item["cut"]
        if self.est(lo) > rem:
            return 0, f"even {lo} tokens need ~{self.est(lo) / 60:.1f} min, {max(rem, 0) / 60:.1f} left"
        while hi - lo > 64:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if self.est(mid) <= rem else (lo, mid)
        cut = lo - lo % 64
        return cut, f"cut to {cut} of {item['cut']} tokens to fit ({rem / 60:.1f} min left)"

    def add(self, L, secs):
        self.done_model += model_s(self.kind, L)
        self.done_real += secs


def count_lines(p):
    if not Path(p).exists():
        return 0
    with open(p, "rb") as f:
        return sum(1 for _ in f)


def engine_cmd(cfg, kind, plan, ids_of=None):
    qq = qq_mod()
    L = max_len(plan, ids_of)
    args = qq.engine_args(cfg, False, L)     # --max-context L+512, --short-read L+64, --prefill 512, the fixed set
    if "--spec" in args:
        args[args.index("--spec") + 1] = "2"
    else:
        args += ["--spec", "2"]
    return args, L


def cmd_run(a):
    qq = qq_mod()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8-sig"))
    out = Path(a.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tsv, ftsv, idxp = out / "score.tsv", out / "force.tsv", out / "index.json"
    for p in (tsv, ftsv, idxp, out / "stderr.txt"):
        p.unlink(missing_ok=True)
    env = dict(os.environ)
    env.update(cfg.get("env", {}))
    if cfg.get("lib_dirs"):
        env["LD_LIBRARY_PATH"] = ":".join(cfg["lib_dirs"] + [env.get("LD_LIBRARY_PATH", "")])
    env.update(qq.FIXED_ENV)
    for kv in a.env or []:
        k, _, v = kv.partition("=")
        env[k] = v
    env.pop("STRATA_LOGPOS", None)
    env.pop("STRATA_LOGPOS_TOPK", None)
    if a.kind == "logpos":
        env["STRATA_LOGPOS"] = str(tsv)
        env["STRATA_LOGPOS_TOPK"] = str(TOPK)
    if qq.mem_available_gb() < a.min_free_gb:
        raise SystemExit(f"only {qq.mem_available_gb():.0f} GB available (< {a.min_free_gb}): not starting an engine")
    args, L = engine_cmd(cfg, a.kind, a.plan)
    bud = Budget(a.kind, a.budget_min * 60)
    items = plan_items(a.plan)
    idx = {"kind": a.kind, "plan": a.plan, "config": a.config, "args": args, "env": a.env or [], "budget_min": a.budget_min,
           "requests": [], "skipped": [], "problems": [], "started": time.strftime("%F %T")}

    def save():
        idx["scale"] = round(bud.scale(), 3)
        idx["seconds"] = round(time.time() - bud.t0)
        idxp.write_text(json.dumps(idx, indent=1))
    errf = open(out / "stderr.txt", "w")
    print("engine:", " ".join(args), flush=True)
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errf, text=True,
                         cwd=cfg.get("cwd"), env=env, bufsize=1)
    for line in p.stdout:
        if line.startswith("READY"):
            break
    else:
        idx["problems"].append(f"the engine ended before READY (exit {p.wait()})")
        save()
        raise SystemExit(f"the engine ended before READY; see {out}/stderr.txt")
    idx["ready_s"] = round(time.time() - bud.t0, 1)
    save()
    for it in items:
        cut, note = bud.fit(it)
        if cut == 0:
            idx["skipped"].append(f"{it['name']}: {note}")
            print(f"skipped {it['name']}: {note}", flush=True)
            save()
            continue
        ids = load_ids(it["file"])[:cut]
        r = {"name": f"{it['file'].split('.')[0]}-{cut}", "file": it["file"], "cut": cut, "full": it["cut"], "note": note}
        t0 = time.time()
        if a.kind == "logpos":
            n0 = count_lines(tsv)
            p.stdin.write("GEN 1 " + ",".join(map(str, ids)) + "\n")
        else:
            N = cut - 2
            errf.flush()
            off = (out / "stderr.txt").stat().st_size
            p.stdin.write(f"GEN {N} force={N} " + ",".join(map(str, ids)) + "\n")
        p.stdin.flush()
        done = None
        for line in p.stdout:
            if line.startswith(("DONE", "ERR")):
                done = line.strip()
                break
        secs = time.time() - t0
        if done is None and idx["requests"]:          # the engine ended inside a text (the watchdog): keep the finished ones
            idx["problems"].append(f"{r['name']}: the engine ended inside this text (exit {p.poll()}); "
                                   f"{len(idx['requests'])} finished text(s) kept")
            save()
            p.kill()
            errf.close()
            print(f"PROBLEM: {idx['problems'][-1]}")
            return 2
        if done is None or not done.startswith("DONE") or "nonfinite" in done:
            idx["problems"].append(f"{r['name']}: the engine answered {done!r}")
            save()
            p.kill()
            raise SystemExit(f"{r['name']}: the engine answered {done!r}; see {out}/stderr.txt")
        if a.kind == "logpos":
            n1 = count_lines(tsv)
            r.update(first_line=n0, end_line=n1)
            if n1 - n0 != cut - 1:
                idx["problems"].append(f"{r['name']}: {n1 - n0} LOGPOS lines, expected {cut - 1} (positions 0..{cut - 2}; "
                                       "fewer = part of the text took the batched path)")
        else:
            got = []
            with open(out / "stderr.txt", errors="replace") as f:
                f.seek(off)
                for line in f:
                    if line.startswith("FORCE ") and len(line.split()) == 5:
                        k, tg, am, nl = line.split()[1:]
                        got.append((1 + int(k), int(tg), int(am), float(nl)))   # prompt = 2 tokens: row 1 + k
            with open(ftsv, "a") as f:
                for q, tg, am, nl in got:
                    f.write(f"{r['name']}\t{q}\t{tg}\t{am}\t{nl:.6f}\n")
            badt = sum(1 for q, tg, _, _ in got if q + 1 >= len(ids) or ids[q + 1] != tg)
            r.update(forced=len(got))
            if len(got) != N or badt:
                idx["problems"].append(f"{r['name']}: {len(got)} FORCE lines of {N}, {badt} with another target")
        bud.add(cut, secs)
        r.update(seconds=round(secs, 1), tok_s=round(cut / secs, 1) if secs > 0 else None)
        idx["requests"].append(r)
        save()
        print(f"{r['name']}: {cut} tokens in {secs:.0f} s ({cut / max(secs, 1e-9):.1f} tok/s){'; ' + note if note else ''}; "
              f"model scale {bud.scale():.2f}", flush=True)
    p.stdin.write("QUIT\n")
    p.stdin.flush()
    try:
        p.wait(timeout=600)
    except subprocess.TimeoutExpired:
        p.kill()
    errf.close()
    save()
    for b in idx["problems"]:
        print("PROBLEM:", b)
    print(f"{len(idx['requests'])} texts read ({sum(r['cut'] for r in idx['requests'])} tokens) in "
          f"{time.time() - bud.t0:.0f} s; skipped {len(idx['skipped'])}")
    return 1 if idx["problems"] or not idx["requests"] else 0


def cmd_envwatch(a):
    """the runner's engine environment as it starts (by /proc/PID/exe in the job's tree, never a command line)"""
    NR = load("nll_rules", NRP)
    qq = qq_mod()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8-sig"))
    want = NR.want_of(cfg, a.env, qq.FIXED_ENV)
    L = max_len(a.plan)
    args_want = {"--expert-cache": "1", "--pcie-frac": "0", "--kv": "fp16", "--adapt-every": "100000", "--suffix-draft": "0",
                 "--prompt-cache": "0", "--spec": "2", "--short-read": str(L + 64), "--prefill": "512",
                 "--max-context": str(L + 512)}
    ngpu = len([x for x in cfg.get("env", {}).get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
    exe = os.path.realpath(cfg["exe"])
    seen, t_end = {}, time.time() + a.max_s
    while time.time() < t_end:
        done = not NR.alive(a.job)
        for pid in sorted(NR.proc_tree(a.job) | {a.job}):
            if pid in seen:
                continue
            try:
                if os.readlink(f"/proc/{pid}/exe") != exe:
                    continue
                env = dict(x.split("=", 1) for x in Path(f"/proc/{pid}/environ").read_bytes().decode("utf-8", "replace")
                           .split("\0") if "=" in x)
                argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace").split("\0")
            except OSError:
                continue
            bad = check_engine(env, argv, want, ngpu, args_want, a.kind)
            seen[pid] = bad
            killed = ""
            if bad and a.kill:
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed = "; STOPPED (by pid) before it measures"
                except OSError:
                    killed = "; could not stop it"
            print(f"engine pid {pid}: {len(want)} env keys, STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}"
                  + (f" -> ENV MISMATCH {', '.join(bad)}{killed}" if bad else " -> ENV OK"), flush=True)
        if done:
            break
        time.sleep(0.5)
    bad_all = [b for v in seen.values() for b in v]
    if not seen:
        line = f"no engine {exe} started in job {a.job}"
    elif bad_all:
        line = f"{sum(1 for v in seen.values() if v)} of {len(seen)} start(s) not as configured: " + "; ".join(sorted(set(bad_all)))
    else:
        line = f"{len(seen)} start(s), {len(want)} env keys as configured (+ the yardstick's fixed env), {a.kind} hooks, the runner's args"
    ok = bool(seen) and not bad_all
    print(("ENV CHECK OK: " if ok else "ENV CHECK FAILED - the arm is void: ") + line, flush=True)
    gate(a, "PASS" if ok else "FAIL", line[:400])
    return 0 if ok else 1


def check_engine(env, argv, want, ngpu, args_want, kind):
    NR = load("nll_rules", NRP)
    bad = [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]
    extra = {"STRATA_MON_GPU"} | ({"STRATA_LOGPOS", "STRATA_LOGPOS_TOPK"} if kind == "logpos" else set())
    bad += [f"{k}={env[k]} (not in the config)" for k in sorted(env) if k.startswith("STRATA_") and k not in want and k not in extra]
    if env.get("STRATA_ROUTE_TAIL_SKIP") != "0":
        bad.append(f"STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}")
    if kind == "logpos" and (not env.get("STRATA_LOGPOS") or env.get("STRATA_LOGPOS_TOPK") != str(TOPK)):
        bad.append("STRATA_LOGPOS / STRATA_LOGPOS_TOPK=64 not set")
    if kind == "force" and (env.get("STRATA_LOGPOS") or env.get("STRATA_FORCE_T1") != "1"):
        bad.append("force arm: STRATA_FORCE_T1=1 missing or STRATA_LOGPOS set")
    n = len([x for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
    if n != ngpu:
        bad.append(f"{n} GPU(s) in CUDA_VISIBLE_DEVICES (want {ngpu})")
    if len(argv) < 2 or argv[1] != "--serve":
        bad.append("not the --serve engine")
    bad += [f"{k} {NR.last_val(argv, k)} (want {v})" for k, v in args_want.items() if NR.last_val(argv, k) != v]
    return bad


# ================================================================================================ pillow step helpers
def norm_pkg(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None, None
    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(==|@|\s)", line + " ")
    name = (m.group(1) if m else line).lower().replace("_", "-")
    return name, line


def freeze_map(p):
    out = {}
    for line in Path(p).read_text().splitlines():
        k, v = norm_pkg(line)
        if k:
            out[k] = v
    return out


def cmd_freeze_diff(a):
    A, B = freeze_map(a.before), freeze_map(a.after)
    diff = sorted(k for k in set(A) | set(B) if A.get(k) != B.get(k))
    other = [k for k in diff if k != a.allow]
    ok = not other and (a.want is None or B.get(a.allow, "").lower() == a.want.lower()) and \
        (a.want is not None or not diff)
    print(f"freeze diff: {', '.join(f'{k}: {A.get(k)} -> {B.get(k)}' for k in diff) or 'none'} -> "
          + ("OK" if ok else "NOT OK" + (f" (other packages changed: {', '.join(other)})" if other else "")))
    return 0 if ok else 1


def cmd_unittests(a):
    import unittest
    sys.path.insert(0, str(a.tree))
    from PIL import Image  # noqa: F401  (the version that is tested)
    import PIL
    names = ["serve.test_exif_orientation", "serve.test_ds_pictures"]
    buf = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    res = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    Path(a.out).write_text(buf.getvalue())
    ok = res.wasSuccessful() and res.testsRun > 0 and not res.skipped
    print(f"unit tests ({', '.join(names)}) on Pillow {PIL.__version__}: {res.testsRun} run, {len(res.failures)} failed, "
          f"{len(res.errors)} errors, {len(res.skipped)} skipped -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def cmd_mpl_check(a):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image
    import PIL
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(3, 2), dpi=80)
    x = np.linspace(0, 6.3, 50)
    ax.plot(x, np.sin(x))
    ax.set_title("pillow check")
    p = d / "mpl-check.png"
    fig.savefig(p)
    plt.close(fig)
    im = Image.open(p)
    im.load()
    arr = plt.imread(p)
    ok = im.size == (240, 160) and im.mode in ("RGBA", "RGB") and arr.shape[:2] == (160, 240)
    print(f"matplotlib {matplotlib.__version__} (Agg) on Pillow {PIL.__version__}: wrote {p.name} {im.size} {im.mode}, "
          f"read back {arr.shape} -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def picture(fmt):
    """left half red, right half blue. The JPEG carries EXIF Orientation 6, so the server's Vision.normalize turns it
    upright with Pillow (a plain JPEG or PNG passes through without Pillow: serve/server.py)"""
    from PIL import Image
    im = Image.new("RGB", (448, 448), (220, 30, 30))
    im.paste((30, 40, 220), (224, 0, 448, 448))
    b = io.BytesIO()
    if fmt == "JPEG":
        ex = Image.Exif()
        ex[0x0112] = 6
        im.save(b, format=fmt, quality=90, exif=ex)
    else:
        im.save(b, format=fmt)
    return b.getvalue()


def cmd_vision_check(a):
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    q = "What two colours does this picture show? Answer in five words or fewer."
    res, ok_all = [], True
    for fmt, mime in (("JPEG", "image/jpeg"), ("PNG", "image/png")):
        data = picture(fmt)
        (d / f"vision-test.{fmt.lower()}").write_bytes(data)
        body = {"messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}},
            {"type": "text", "text": q}]}], "max_tokens": a.max_tokens, "chat_template_kwargs": {"enable_thinking": False}}
        t0 = time.time()
        r = {"format": fmt, "bytes": len(data)}
        try:
            req = urllib.request.Request(a.url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=a.timeout) as h:
                code, out = h.status, json.loads(h.read().decode())
        except urllib.error.HTTPError as e:
            code, out = e.code, {"error": e.read().decode(errors="replace")[:500]}
        except Exception as e:      # noqa: BLE001 (any failure is a FAIL with its reason)
            code, out = None, {"error": f"{type(e).__name__}: {e}"}
        msg = (out.get("choices") or [{}])[0].get("message", {}) if isinstance(out, dict) else {}
        text = (msg.get("content") or "").strip()
        named = sorted(c for c in ("red", "blue") if re.search(rf"\b{c}\b", text.lower()))
        good = code == 200 and bool(text) and bool(named)
        ok_all &= good
        r.update(http=code, seconds=round(time.time() - t0, 1), answer=text[:400], colours_named=named,
                 error=out.get("error") if isinstance(out, dict) else None, verdict="PASS" if good else "FAIL")
        res.append(r)
        print(f"vision {fmt}: HTTP {code}, {r['seconds']} s, answer {text[:120]!r}, colours named {named or 'none'} -> {r['verdict']}")
    (d / "vision.json").write_text(json.dumps(res, indent=1))
    return 0 if ok_all else 1


# ================================================================================================ decode gap b's failed passes
def bp_complete(recs, arm, s, k):
    lab = f"bp{arm}-{s}-{k}"
    key = "decode_tps" if s == "decode" else "prompt_tps"
    have = {r["test"] for r in recs if r.get("label") == lab and r.get(key)}
    return all(t in have for t in BP_SETS[s])


def bp_missing(bdir):
    out = []
    for arm in ("B", "LO"):
        p = Path(bdir) / f"cold-{arm}.jsonl"
        recs = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        for k in (1, 2, 3):
            for s in ("decode", "pp16k", "pp64k"):
                if not bp_complete(recs, arm, s, k):
                    out.append((arm, s, k))
    return out


def cmd_bp90_missing(a):
    m = bp_missing(a.bp90)
    for arm, s, k in m:
        print(f"MISSING {arm} {s} {k}")
    same = sorted(m) == sorted(BP_EXPECTED)
    print(f"INFO {len(m)} arm-passes missing in {a.bp90}; " + ("= the 7 recorded 11-05 07:00" if same else
          f"recorded 11-05 07:00: {' '.join(f'{x}-{y}-{z}' for x, y, z in BP_EXPECTED)}"))
    return 0


def cmd_merge_b(a):
    """gap b's screen + bp90 records and gates, with the rerun's arm-passes in place of the failed ones (gap b's files are
    only read): MERGED/{gates.txt, speed/*.jsonl, bp90/cold-*.jsonl}"""
    src, rr, dst = Path(a.gap_b), Path(a.rerun), Path(a.merged)
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "speed").mkdir(parents=True)
    (dst / "bp90").mkdir()
    for f in (src / "speed").glob("*.jsonl"):
        shutil.copy(f, dst / "speed" / f.name)
    rerun = [json.loads(x) for f in rr.glob("cold-*.jsonl") for x in f.read_text().splitlines() if x.strip()]
    labels = {r["label"] for r in rerun}
    g_rr = [x for x in (rr / "gates.txt").read_text().splitlines()] if (rr / "gates.txt").exists() else []
    keys_rr = {x.split(" ", 1)[0] for x in g_rr}
    keep = [x for x in (src / "gates.txt").read_text().splitlines()
            if not (x.split(" ", 1)[0] in keys_rr or any(x.startswith(f"{p}_{l} ") for p in ("env", "fatal") for l in labels))]
    (dst / "gates.txt").write_text("\n".join(keep + g_rr) + "\n")
    for arm in ("B", "LO"):
        p = src / "bp90" / f"cold-{arm}.jsonl"
        old = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        new = [r for r in old if r.get("label") not in labels] + [r for r in rerun if r.get("label", "").startswith(f"bp{arm}-")]
        (dst / "bp90" / f"cold-{arm}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in new))
    print(f"merged: {len(labels)} rerun arm-passes ({', '.join(sorted(labels)) or 'none'}) over gap b's records -> {dst}; "
          f"still missing: {' '.join(f'{x}-{y}-{z}' for x, y, z in bp_missing(dst / 'bp90')) or 'none'}")
    return 0


# ================================================================================================ compare
def read_logpos(d):
    """dec / s210dec: {file: {"cut", "name", "pos": {p: (target, lp_target, argmax, ids (64), lps (64))}}}"""
    import numpy as np
    idx = json.loads((Path(d) / "index.json").read_text())
    lines = (Path(d) / "score.tsv").read_text().splitlines()
    out = {}
    for r in idx["requests"]:
        pos = {}
        for line in lines[r["first_line"]:r["end_line"]]:
            f = line.split("\t")
            if len(f) < 8 + TOPK:
                continue
            tk = [z.split(":") for z in f[8:8 + TOPK]]
            pos[int(f[0])] = (int(f[1]), float(f[2]), int(f[3]), np.array([int(x) for x, _ in tk]),
                              np.array([float(y) for _, y in tk]))
        out[r["file"]] = {"cut": r["cut"], "name": r["name"], "pos": pos}
    return out


def read_force(d):
    idx = json.loads((Path(d) / "index.json").read_text())
    by = {r["name"]: r["file"] for r in idx["requests"]}
    out = {}
    for line in (Path(d) / "force.tsv").read_text().splitlines():
        n, q, tg, am, nl = line.split("\t")
        out.setdefault(by[n], {})[int(q)] = (int(tg), int(am), float(nl))
    return out


def arm_request(d, f):
    idx = json.loads((Path(d) / "index.json").read_text())
    return next((r for r in idx["requests"] if r["kind"] == "text" and r["file"] == f and r.get("rows")), None)


def alias_groups(arms, files):
    NR = load("nll_rules", NRP)
    groups = []                                  # [(rep key, [keys])]
    for k, d in arms:
        for rep in groups:
            rd = dict(arms)[rep[0]]
            ok = True
            for f in files:
                x, y = arm_request(d, f), arm_request(rd, f)
                if x is None or y is None or not NR.same_bytes(Path(d) / x["dump"], Path(rd) / y["dump"]):
                    ok = False
                    break
            if ok:
                rep[1].append(k)
                break
        else:
            groups.append((k, [k]))
    return groups


def kl65(lp_dec, lq):
    """per position: KL(dec || X) and TV over dec's 64 tokens + the rest; lp_dec, lq (n, 64) natural logs"""
    import numpy as np
    p, q = np.exp(lp_dec), np.exp(lq)
    pr = np.clip(1.0 - p.sum(1), 0.0, 1.0)
    qr = np.clip(1.0 - q.sum(1), 1e-12, 1.0)
    kl = (p * (lp_dec - lq)).sum(1) + np.where(pr > 1e-9, pr * (np.log(np.maximum(pr, 1e-300)) - np.log(qr)), 0.0)
    tv = 0.5 * (np.abs(p - q).sum(1) + np.abs(pr - qr))
    return np.maximum(kl, 0.0), tv


def kl_top_floor(ids_r, lp_r, ids_a, lp_a):
    """quant_quality.py compare's rule: over REF's 64, both renormalised, a token RUN does not list gets RUN's floor"""
    da = dict(zip(ids_a.tolist(), lp_a.tolist()))
    floor = float(lp_a.min())
    pr = [math.exp(v) for v in lp_r]
    pa = [math.exp(da.get(i, floor)) for i in ids_r.tolist()]
    sr, sa = sum(pr), sum(pa)
    return sum((x / sr) * math.log((x / sr) / (y / sa)) for x, y in zip(pr, pa) if x > 0)


def cmd_compare(a, head=None, roots=None):
    import numpy as np
    S = score_mod()
    dec = read_logpos(a.dec)
    files = [f for f in dec if len(dec[f]["pos"])]
    arms = [(k, str(d)) for k, d, _, _ in (roots or ARMS) if (Path(d) / "index.json").exists()
            and all(arm_request(d, f) for f in files)]
    groups = alias_groups(arms, files)
    adir = dict(arms)
    head = head or S.Head()
    rows = {"text": [], "pos": [], "target": [], "nll_dec": [], "top_dec": []}
    cols = {g: {"nll": [], "kl": [], "tv": [], "top": []} for g, _ in groups}
    tgt_bad = 0
    for f in files:
        dd = dec[f]
        ids = load_ids(f)
        reqs = {g: arm_request(adir[g], f) for g, _ in groups}
        P = sorted(p for p in dd["pos"] if p % EVERY == 0 and p >= MIN_POS and all(p + 1 < r["cut"] for r in reqs.values()))
        for p in P:
            tg, lt, am, _, _ = dd["pos"][p]
            if ids[p + 1] != tg:
                tgt_bad += 1
        P = [p for p in P if ids[p + 1] == dd["pos"][p][0]]
        if not P:
            continue
        rows["text"] += [dd["name"]] * len(P)
        rows["pos"] += P
        rows["target"] += [dd["pos"][p][0] for p in P]
        rows["nll_dec"] += [-dd["pos"][p][1] for p in P]
        rows["top_dec"] += [dd["pos"][p][2] for p in P]
        tid = np.stack([dd["pos"][p][3] for p in P])
        tlp = np.stack([dd["pos"][p][4] for p in P])
        for g, _ in groups:
            pa, R = S.rows_of(Path(adir[g]), reqs[g])
            where = {int(v): j for j, v in enumerate(pa)}
            for c0 in range(0, len(P), a.chunk):
                js = P[c0:c0 + a.chunk]
                z = head.logits(np.asarray(R[[where[p] for p in js]], np.float32))
                _, lse, _ = S.lse_rows(z)
                n_ = np.arange(len(js))
                tg = np.array([dd["pos"][p][0] for p in js])
                lq = z[n_[:, None], tid[c0:c0 + a.chunk]].astype(np.float64) - lse[:, None]
                kl, tv = kl65(tlp[c0:c0 + a.chunk], lq)
                cols[g]["nll"] += (lse - z[n_, tg]).tolist()
                cols[g]["kl"] += kl.tolist()
                cols[g]["tv"] += tv.tolist()
                cols[g]["top"] += z.argmax(axis=1).tolist()
        print(f"  {dd['name']}: {len(P)} positions x {len(groups)} variant group(s)", flush=True)
    res = {"dec": str(a.dec), "files": files, "groups": {g: m for g, m in groups},
           "labels": {k: lab for k, _, lab, _ in (roots or ARMS)}, "target_mismatch": tgt_bad, "n": len(rows["pos"])}
    arr = {k: np.array(v) for k, v in rows.items()}
    garr = {g: {k: np.array(v) for k, v in c.items()} for g, c in cols.items()}
    res["stats"] = all_stats(arr, garr, rep_of(groups, "default"), B=a.boot)
    name2file = {dec[f]["name"]: f for f in files}
    res["name2file"] = name2file
    if rep_of(groups, "default") in garr and len(arr["pos"]):
        res["text_level"] = text_level(arr, garr, rep_of(groups, "default"), name2file, B=a.boot)
        res["bins"] = bins_compare(arr, garr, rep_of(groups, "default"), B=a.boot)
    res["bins_rows"] = rows_bins(getattr(a, "nll_rows", None), getattr(a, "gdn_rows", None), B=a.boot)
    if a.dec1 and (Path(a.dec1) / "force.tsv").exists():
        res["window"] = window_stats(arr, garr, read_force(a.dec1), dec, rep_of(groups, "default"), a.boot)
    if a.stock and (Path(a.stock) / "score.tsv").exists():
        res["stock"] = stock_stats(dec, read_logpos(a.stock), a.boot)
    Path(a.json).write_text(json.dumps(res, indent=1))
    if a.rows_out:
        with open(a.rows_out, "w") as fo:
            fo.write("\t".join(["text", "pos", "stratum", "nll_dec", "top_dec"] + [f"{h}_{g}" for g, _ in groups
                                                                                    for h in ("nll", "kl", "tv", "top")]) + "\n")
            for i in range(len(arr["pos"])):
                fo.write("\t".join([arr["text"][i], str(arr["pos"][i]), stratum(int(arr["pos"][i])), f"{arr['nll_dec'][i]:.6f}",
                                    str(arr["top_dec"][i])] + [f"{garr[g][h][i]:.6g}" for g, _ in groups
                                                               for h in ("nll", "kl", "tv", "top")]) + "\n")
    print(report(res))
    return 0


def rep_of(groups, key):
    return next((g for g, m in groups if key in m), None)


def boot_means(blocks, vals, B, seed=SEED):
    """per column: (point mean, replicate means (B,)) - blocks resampled with replacement, the same draw for every column"""
    import numpy as np
    ub, inv = np.unique(blocks, return_inverse=True)
    nb = len(ub)
    C = np.random.default_rng(seed).multinomial(nb, np.full(nb, 1.0 / nb), size=B).astype(np.float64)
    nblk = np.bincount(inv, minlength=nb).astype(np.float64)
    den = C @ nblk
    out = {}
    for k, v in vals.items():
        v = np.asarray(v, np.float64)
        out[k] = (float(v.mean()), (C @ np.bincount(inv, weights=v, minlength=nb)) / den)
    return out, nb


def ci(rep):
    import numpy as np
    return [float(np.percentile(rep, 2.5)), float(np.percentile(rep, 97.5))]


def all_stats(arr, garr, dflt, B=BOOT, seed=SEED):
    import numpy as np
    out = {}
    strat = np.array([stratum(int(p)) for p in arr["pos"]])
    blk = np.array([f"{t}|{int(p) // BLOCK}" for t, p in zip(arr["text"], arr["pos"])])
    for sname in [s for s, _, _ in STRATA] + ["all"]:
        m = np.ones(len(strat), bool) if sname == "all" else strat == sname
        if not m.any():
            out[sname] = {"n": 0}
            continue
        vals = {}
        for g, c in garr.items():
            d = c["nll"][m] - arr["nll_dec"][m]
            vals[f"K|{g}"], vals[f"TV|{g}"] = c["kl"][m], c["tv"][m]
            vals[f"A|{g}"] = (c["top"][m] == arr["top_dec"][m]).astype(float)
            vals[f"D|{g}"], vals[f"Dabs|{g}"] = d, np.abs(d)
        bm, nb = boot_means(blk[m], vals, B, seed)
        st = {"n": int(m.sum()), "blocks": nb, "texts": sorted(set(arr["text"][m].tolist())), "arms": {}, "paired": {}}
        for g, c in garr.items():
            k = c["kl"][m]
            st["arms"][g] = {x: {"mean": bm[f"{x}|{g}"][0], "ci": ci(bm[f"{x}|{g}"][1])} for x in ("K", "TV", "A", "D", "Dabs")}
            st["arms"][g]["K"].update(p90=float(np.percentile(k, 90)), gt1=int((k > 1).sum()), median=float(np.median(k)))
        if dflt in garr:
            for g in garr:
                if g == dflt:
                    continue
                dK = bm[f"K|{dflt}"][1] - bm[f"K|{g}"][1]
                dD = bm[f"D|{dflt}"][1] - bm[f"D|{g}"][1]
                cA = bm[f"D|{dflt}"][1] - np.abs(bm[f"D|{g}"][1])
                st["paired"][g] = {"dK": {"mean": bm[f"K|{dflt}"][0] - bm[f"K|{g}"][0], "ci": ci(dK)},
                                   "dD": {"mean": bm[f"D|{dflt}"][0] - bm[f"D|{g}"][0], "ci": ci(dD)},
                                   "c": {"mean": bm[f"D|{dflt}"][0] - abs(bm[f"D|{g}"][0]), "ci": ci(cA)}}
            ks = sorted(garr, key=lambda g: bm[f"K|{g}"][0])
            if len(ks) > 1:
                gap = bm[f"K|{ks[1]}"][1] - bm[f"K|{ks[0]}"][1]
                st["closest"] = {"arm": ks[0], "next": ks[1], "gap_ci": ci(gap), "tied": bool(ci(gap)[0] <= 0)}
            else:
                st["closest"] = {"arm": ks[0], "next": None, "tied": False}
        out[sname] = st
    return out


def window_stats(arr, garr, force, dec, dflt, B):
    """dec1 (1-row windows, NLL + top pick) against dec (2-row) at every position from 1,024; and the variants against
    dec1 at their rows on that text"""
    import numpy as np
    out = {}
    for f, fz in force.items():
        if f not in dec:
            continue
        P = sorted(p for p in fz if p >= MIN_POS and p in dec[f]["pos"] and fz[p][0] == dec[f]["pos"][p][0])
        if not P:
            continue
        n1 = np.array([fz[p][2] for p in P])
        n2 = np.array([-dec[f]["pos"][p][1] for p in P])
        a1 = np.array([fz[p][1] for p in P])
        a2 = np.array([dec[f]["pos"][p][2] for p in P])
        blk = np.array([p // BLOCK for p in P])
        bm, nb = boot_means(blk, {"W_D": n1 - n2, "W_abs": np.abs(n1 - n2), "W_A": (a1 == a2).astype(float)}, B)
        w = {k: {"mean": v[0], "ci": ci(v[1])} for k, v in bm.items()}
        w.update(n=len(P), blocks=nb)
        name = dec[f]["name"]
        m = np.array([t == name for t in arr["text"]])
        sel = [i for i in np.nonzero(m)[0] if int(arr["pos"][i]) in fz]
        if sel and dflt in garr:
            q = np.array([fz[int(arr["pos"][i])][2] for i in sel])
            qa = np.array([fz[int(arr["pos"][i])][1] for i in sel])
            w["vs_dec1"] = {g: {"D": float((c["nll"][sel] - q).mean()), "A": float((c["top"][sel] == qa).mean())}
                            for g, c in garr.items()}
            w["vs_dec"] = {g: {"D": float((c["nll"][sel] - arr["nll_dec"][sel]).mean()),
                               "A": float((c["top"][sel] == arr["top_dec"][sel]).mean())} for g, c in garr.items()}
            dd = w["vs_dec"]
            spread = min([abs(dd[dflt]["D"] - dd[g]["D"]) for g in dd if g != dflt] or [0.0])
            w["spread"] = spread
            w["stands"] = bool(abs(w["W_D"]["mean"]) <= max(WIN_FLOOR, 0.25 * spread) and w["W_A"]["mean"] >= dd[dflt]["A"])
            w["rows_n"] = len(sel)
            for g, c in garr.items():                 # (c) of the 11-05 revision: the same every-8th rows
                w["vs_dec"][g]["Dabs"] = float(np.abs(c["nll"][sel] - arr["nll_dec"][sel]).mean())
            q8 = np.array([fz[int(arr["pos"][i])][2] for i in sel])
            a8 = np.array([fz[int(arr["pos"][i])][1] for i in sel])
            w["at8"] = {"Dabs": float(np.abs(q8 - arr["nll_dec"][sel]).mean()), "D": float((q8 - arr["nll_dec"][sel]).mean()),
                        "A": float((a8 == arr["top_dec"][sel]).mean())}
            best_abs = min(v_["Dabs"] for v_ in w["vs_dec"].values())
            best_a = max(v_["A"] for v_ in w["vs_dec"].values())
            w["sound"] = bool(w["at8"]["Dabs"] <= 0.5 * best_abs and w["at8"]["A"] >= best_a)
            w["sound_why"] = (f"2-row vs 1-row |dNLL| {w['at8']['Dabs']:.3f} (<= 0.5 x {best_abs:.3f}?), top-1 agreement "
                              f"{100 * w['at8']['A']:.1f} % (>= {100 * best_a:.1f} %?) at {len(sel)} rows")
        w["bins"] = bin_table([name] * len(P), P, {"1-row vs 2-row": np.abs(n1 - n2)}, B)
        w["bins_top1"] = {b: float((a1 == a2)[[lo <= p < hi for p in P]].mean()) for b, lo, hi in BINS
                          if any(lo <= p < hi for p in P)}
        out[name] = w
    return out


def stock_stats(dec, sto, B):
    import numpy as np
    out = {}
    for f, ds in sto.items():
        if f not in dec:
            continue
        P = sorted(p for p in ds["pos"] if p >= MIN_POS and p in dec[f]["pos"] and ds["pos"][p][0] == dec[f]["pos"][p][0])
        if not P:
            continue
        kl = np.array([kl_top_floor(dec[f]["pos"][p][3], dec[f]["pos"][p][4], ds["pos"][p][3], ds["pos"][p][4]) for p in P])
        d = np.array([-ds["pos"][p][1] + dec[f]["pos"][p][1] for p in P])
        A = np.array([ds["pos"][p][2] == dec[f]["pos"][p][2] for p in P], float)
        bm, nb = boot_means(np.array([p // BLOCK for p in P]), {"K": kl, "D": d, "A": A}, B)
        s = {k: {"mean": v[0], "ci": ci(v[1])} for k, v in bm.items()}
        s.update(n=len(P), blocks=nb, agree=bool(s["K"]["mean"] <= STOCK_K and abs(s["D"]["mean"]) <= STOCK_D))
        out[dec[f]["name"]] = s
    return out


# ================================================================================================ 11-05: text-level statistics
def chance(A, N):
    """k ~ Binomial(N, 1/A): the rule's three outcomes' probabilities if each path were equally likely to be the farthest"""
    hi, lo = math.ceil(7 * N / 8), math.floor(N / 2)
    p = 1.0 / A
    P = [math.comb(N, k) * p ** k * (1 - p) ** (N - k) for k in range(N + 1)]
    return {"A": A, "N": N, "hi": hi, "lo": lo, "p_out": sum(P[hi:]), "p_not": sum(P[:lo + 1]), "p_inc": sum(P[lo + 1:hi])}


def text_verdict(k, N):
    if N < MIN_TEXTS:
        return f"NOT JUDGED ({N} texts read, fewer than {MIN_TEXTS})"
    c = chance(5, N)
    if k >= c["hi"]:
        return "DEFAULT IS THE OUTLIER"
    if k <= c["lo"]:
        return "DEFAULT IS NOT AN OUTLIER"
    return "INCONCLUSIVE"


def tq(df):
    return T975.get(df, 2.0 if df < 30 else 1.96)


def mean_t(v):
    """equal-weight mean of one value per text: mean, se, t(N-1) interval (= CR1 with one value per cluster)"""
    import numpy as np
    v = np.asarray(v, float)
    n = len(v)
    m = float(v.mean())
    se = float(v.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    return {"mean": m, "se": se, "ci": [m - tq(n - 1) * se, m + tq(n - 1) * se] if n > 1 else [float("nan")] * 2, "n": n}


def cr1_pooled(s, n):
    """the position-weighted mean sum(s) / sum(n) with a CR1 interval, clusters = texts, t(G-1)"""
    import numpy as np
    s, n = np.asarray(s, float), np.asarray(n, float)
    G = len(s)
    est = float(s.sum() / n.sum())
    e = s - est * n
    se = float(math.sqrt(G / (G - 1) * (e ** 2).sum()) / n.sum()) if G > 1 else float("nan")
    return {"mean": est, "se": se, "ci": [est - tq(G - 1) * se, est + tq(G - 1) * se] if G > 1 else [float("nan")] * 2}


def text_counts(G, B, seed=SEED):
    import numpy as np
    return np.random.default_rng(seed).multinomial(G, np.full(G, 1.0 / G), size=B).astype(np.float64)


def text_level(arr, garr, dflt, name2file, B=BOOT, seed=SEED):
    """per text, per path: D_t = mean KL(dec || path) (the fixed distance), TV, top-1, NLL d, |d|; the farthest path per
    text; k and the rule; text-level means and intervals; the 2,048-block SE beside them (not used for the verdict);
    the short / long split"""
    import numpy as np
    T = np.asarray(arr["text"])
    texts = list(dict.fromkeys(T.tolist()))
    paths = list(garr)
    per = {}
    for t in texts:
        m = T == t
        per[t] = {"n": int(m.sum()), "file": name2file.get(t, t), "paths": {}}
        for g, c in garr.items():
            d = c["nll"][m] - arr["nll_dec"][m]
            per[t]["paths"][g] = {"K": float(c["kl"][m].mean()), "TV": float(c["tv"][m].mean()),
                                  "A": float((c["top"][m] == arr["top_dec"][m]).mean()), "D": float(d.mean()),
                                  "Dabs": float(np.abs(d).mean()), "Ksum": float(c["kl"][m].sum())}
        ks = {g: per[t]["paths"][g]["K"] for g in paths}
        order = sorted(paths, key=lambda g: -ks[g])
        per[t]["order"] = order
        per[t]["default_farthest"] = bool(all(ks[dflt] > ks[g] for g in paths if g != dflt))
        per[t]["farthest"] = order[0]
        per[t]["closest"] = order[-1]
        per[t]["default_rank"] = order.index(dflt) + 1

    def summary(sub):
        N = len(sub)
        k = sum(per[t]["default_farthest"] for t in sub)
        out = {"texts": sub, "N": N, "k": k, "A": len(paths), "chance": chance(len(paths), N) if N else None,
               "verdict": text_verdict(k, N) if N else "NO TEXTS",
               "farthest_counts": {g: sum(per[t]["farthest"] == g for t in sub) for g in paths},
               "closest_counts": {g: sum(per[t]["closest"] == g for t in sub) for g in paths}, "means": {}, "paired": {}}
        if N == 0:
            return out
        C = text_counts(N, B, seed)
        for g in paths:
            v = np.array([per[t]["paths"][g]["K"] for t in sub])
            r = C @ v / N
            out["means"][g] = dict(mean_t(v), boot_ci=ci(r))
            if g != dflt:
                dv = np.array([per[t]["paths"][dflt]["K"] - per[t]["paths"][g]["K"] for t in sub])
                out["paired"][g] = dict(mean_t(dv), boot_ci=ci(C @ dv / N))
        return out
    res = {"per_text": per, "paths": paths, "default": dflt, "all": summary(texts),
           "short": summary([t for t in texts if per[t]["file"] in SHORT_FILES]),
           "long": summary([t for t in texts if per[t]["file"] not in SHORT_FILES])}
    # position-weighted means: CR1 over texts, and the 2,048-block SE beside it (not used for the verdict)
    blk = np.array([f"{t}|{int(p) // BLOCK}" for t, p in zip(T, arr["pos"])])
    bm, nb = boot_means(blk, {g: garr[g]["kl"] for g in paths}, min(B, 4000), seed)
    res["pooled"] = {}
    for g in paths:
        c = cr1_pooled([per[t]["paths"][g]["Ksum"] for t in texts], [per[t]["n"] for t in texts])
        res["pooled"][g] = dict(c, block2048_se=float(bm[g][1].std(ddof=1)), block2048_note="2,048-block SE (not used for the verdict)")
    res["blocks2048"] = nb
    return res


def bin_of(p):
    for name, lo, hi in BINS:
        if lo <= p < hi:
            return name
    return None


def bin_table(texts, pos, absvals, B=BOOT, seed=SEED):
    """per pair, per position bin: mean / median |dNLL|, positions, texts, whole-text bootstrap interval of the mean;
    per text, its last bin's mean minus its first bin's"""
    import numpy as np
    T = np.asarray(texts)
    bins = np.array([bin_of(int(p)) for p in pos])
    out = {}
    for pair, v in absvals.items():
        v = np.asarray(v, float)
        row = {}
        for b, _, _ in BINS:
            m = bins == b
            if not m.any():
                continue
            ts = list(dict.fromkeys(T[m].tolist()))
            s = np.array([v[m & (T == t)].sum() for t in ts])
            n = np.array([(m & (T == t)).sum() for t in ts], float)
            C = text_counts(len(ts), min(B, 4000), seed)
            r = (C @ s) / (C @ n)
            row[b] = {"mean": float(v[m].mean()), "median": float(np.median(v[m])), "n": int(m.sum()), "texts": len(ts),
                      "text_ci": ci(r)}
        grow = {}
        for t in dict.fromkeys(T.tolist()):
            mt = T == t
            have = [b for b, _, _ in BINS if (mt & (bins == b)).any()]
            if len(have) >= 2:
                grow[t] = float(v[mt & (bins == have[-1])].mean() - v[mt & (bins == have[0])].mean())
        out[pair] = {"bins": row, "growth_last_minus_first": grow,
                     "texts_growing": sum(x > 0 for x in grow.values()), "texts_with_2_bins": len(grow)}
    return out


def bins_compare(arr, garr, dflt, B=BOOT):
    import numpy as np
    absv = {f"{g} vs dec": np.abs(c["nll"] - arr["nll_dec"]) for g, c in garr.items()}
    absv.update({f"{g} vs ref": np.abs(c["nll"] - garr[dflt]["nll"]) for g, c in garr.items() if g != dflt})
    return bin_table(arr["text"], arr["pos"], absv, B)


def rows_bins(nll_rows, gdn_rows, B=BOOT):
    """(b) on all 8 distinct texts from the two gaps' rows.tsv (no head, no engine): |dNLL| against ref"""
    import numpy as np
    out, src = {}, []
    for p, cols in ((Path(nll_rows) if nll_rows else NLL_ROWS, (("unfused", "nll_unfused", "nll_ref"), ("cpushare", "nll_cpushare", "nll_ref"),
                                                                 ("v2", "nll_v2", "nll_ref"))),
                    (Path(gdn_rows) if gdn_rows else GDN_ROWS, (("gdn", "nll_s210gdn", "nll_s210"),))):
        if not p.exists():
            continue
        lines = p.read_text().splitlines()
        hd = {h: i for i, h in enumerate(lines[0].split("\t"))}
        rows = [x.split("\t") for x in lines[1:]]
        rows = [r for r in rows if not r[hd["text"]].startswith(DUP_PREFIX)]
        texts, pos = [r[hd["text"]] for r in rows], [int(r[hd["pos"]]) for r in rows]
        absv = {f"{k} vs ref": np.abs(np.array([float(r[hd[a]]) - float(r[hd[b]]) for r in rows])) for k, a, b in cols if a in hd and b in hd}
        out.update(bin_table(texts, pos, absv, B))
        src.append(f"{p.relative_to(WS) if str(p).startswith(str(WS)) else p} ({len(set(texts))} texts, {len(rows)} rows)")
    return {"pairs": out, "source": src}



def fmt_ci(x, nd=4, pct=False):
    if pct:
        return f"{100 * x['mean']:.1f} % [{100 * x['ci'][0]:.1f}, {100 * x['ci'][1]:.1f}]"
    return f"{x['mean']:+.{nd}f} [{x['ci'][0]:+.{nd}f}, {x['ci'][1]:+.{nd}f}]"


def report(res):
    L = [f"{res['n']} positions; groups: " + "; ".join(f"{g} = {'/'.join(m)}" for g, m in res["groups"].items())
         + f"; target mismatches {res.get('target_mismatch', 0)}"]
    for s, st in res["stats"].items():
        if not st.get("n"):
            L.append(f"[{s}] no positions")
            continue
        L.append(f"[{s}] {st['n']} positions, {st['blocks']} blocks, texts {', '.join(st['texts'])}")
        for g, v in st["arms"].items():
            L.append(f"  {g:14s} K {v['K']['mean']:.4f} (p90 {v['K']['p90']:.4f}, >1 {v['K']['gt1']})  TV {100 * v['TV']['mean']:.1f} %  "
                     f"top-1 {100 * v['A']['mean']:.1f} %  D {fmt_ci(v['D'])}  |d| {v['Dabs']['mean']:.3f}")
        for g, v in st.get("paired", {}).items():
            L.append(f"    default - {g}: dK {fmt_ci(v['dK'])}  dD {fmt_ci(v['dD'])}  c {fmt_ci(v['c'])}")
    return "\n".join(L)


# ================================================================================================ decide
def verdict(st, dflt):
    """(verdict, lines) for one stratum's stats"""
    if not st.get("n"):
        return "NO DATA", []
    if st["n"] < THIN_N or len(st["texts"]) < THIN_T:
        return "THIN (not judged)", [f"{st['n']} positions in {len(st['texts'])} text(s)"]
    D = st["arms"][dflt]["D"]
    a = D["ci"][0] > 0
    why, nb, nc, neither = [], 0, 0, []
    for g, v in st["paired"].items():
        b, c = v["dK"]["ci"][0] > 0, v["c"]["ci"][0] > 0
        nb += b
        nc += c
        if not b and not c:
            neither.append(g)
        why.append(f"{g}: (b) {'yes' if b else 'no'} (dK {fmt_ci(v['dK'])}), (c) {'yes' if c else 'no'} (c {fmt_ci(v['c'])})")
    n = len(st["paired"])
    if a and n and nb == n and nc == n:
        v = "DEFAULT IS THE OUTLIER"
    elif neither:
        v = f"DEFAULT IS NOT THE OUTLIER (no closer in either measure: {', '.join(neither)})"
    else:
        v = "MIXED"
    return v, [f"(a) D_default {fmt_ci(D)} -> {'yes' if a else 'no'}"] + why


def workloads():
    out = {}
    for f in ("B1n", "B1a", "B1r"):
        p = GAPB / "speed" / f"{f}.jsonl"
        for x in p.read_text().splitlines() if p.exists() else []:
            if x.strip():
                r = json.loads(x)
                if r.get("id") and r.get("prompt_tokens"):
                    out[r["id"]] = int(r["prompt_tokens"])
    src = "gap b's B1n/B1a/B1r.jsonl"
    if len(out) < 5:
        out, src = dict(WL_FALLBACK), "the 11-05 values (gap b's files not read)"
    return out, src


def speed_lines(d, g=None):
    """the speed arms' records; a record counts with its env gate PASS and no fatal gate (when the gates are given)"""
    import statistics as stt
    recs = {}
    for arm in ("def", "unf", "sh0"):
        p = Path(d) / f"cold-{arm}.jsonl"
        recs[arm] = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        if g is not None:
            recs[arm] = [r for r in recs[arm] if g.get(f"env_{r.get('label')}", ("",))[0] == "PASS"
                         and f"fatal_{r.get('label')}" not in g]
    L, out = [], {}
    for t in ("pp16k", "pp64k"):
        v = {arm: [r["prompt_tps"] for r in recs[arm] if r.get("test") == t and r.get("prompt_tps")] for arm in recs}
        if len(v["def"]) < 2:
            L.append(f"{t}: default {len(v['def'])} of 2 passes - NOT MEASURED")
            continue
        md = stt.mean(v["def"])
        sp = (max(v["def"]) - min(v["def"])) / md
        parts = [f"default {md:,.0f} tok/s ({len(v['def'])} passes, spread {100 * sp:.1f} %)"]
        for arm, lab in (("unf", "PF_FUSED=0"), ("sh0", "CPU share 0")):
            if len(v[arm]) >= 2:
                mx = stt.mean(v[arm])
                spx = (max(v[arm]) - min(v[arm])) / mx
                out[(t, arm)] = mx / md - 1
                parts.append(f"{lab} {mx:,.0f} ({100 * (mx / md - 1):+.1f} %, spread {100 * spx:.1f} %)")
            else:
                parts.append(f"{lab}: {len(v[arm])} of 2 passes - not measured")
        L.append(f"{t}: " + "; ".join(parts))
    return L, out


def text_level_lines(res, dflt, lab, out):
    """the decision's primary and secondary sections (11-05 revision)"""
    tl = res["text_level"]
    paths = [dflt] + [g for g in tl["paths"] if g != dflt]
    al = tl["all"]
    ch = al["chance"]
    L = ["PRIMARY (Karl 11-05; the unit is the whole text): distance = per text, the mean over its scored positions of "
         "KL(dec || path) over 65 bins (dec's top 64 + the rest); the farthest path per text; k = the texts where the "
         "default is the farthest"]
    L.append(f"prompt paths: A = {al['A']} (" + "; ".join(f"{g} = {' / '.join(res['groups'][g])}" for g in paths) + ")")
    L.append("  note: cpushare = fused int8 OFF + the staged walk + the CPU share (not one switch, not the served long-prompt "
             "arithmetic); unfused is the clean one-switch reference")
    L.append(f"  {'text':20s} {'pos':>5s} " + " ".join(f"{g[:10]:>10s}" for g in paths) + "  farthest   default's rank")
    for t, x in tl["per_text"].items():
        L.append(f"  {t:20s} {x['n']:5d} " + " ".join(f"{x['paths'][g]['K']:10.5f}" for g in paths)
                 + f"  {x['farthest']:10s} {x['default_rank']} of {al['A']}" + ("  (short)" if x["file"] in SHORT_FILES else ""))
    L.append(f"  k = {al['k']} of N = {al['N']} texts; the rule for N = {al['N']}: OUTLIER k >= {ch['hi']}, NOT k <= {ch['lo']}, "
             f"else INCONCLUSIVE; chance rates (each of the {al['A']} paths equally likely farthest): P(k >= {ch['hi']}) = "
             f"{ch['p_out']:.6f}, P(k <= {ch['lo']}) = {ch['p_not']:.4f}, P(between) = {ch['p_inc']:.4f}")
    if al["N"] != 8:
        L.append(f"  FLAG: Karl's rule is written for 8 texts; {al['N']} were read (the dec arm's budget) - the thresholds above are "
                 "the same proportions (ceil(7N/8), floor(N/2))")
    L.append("  farthest per path: " + ", ".join(f"{g} {al['farthest_counts'][g]}" for g in paths)
             + "; closest per path: " + ", ".join(f"{g} {al['closest_counts'][g]}" for g in paths))
    out["verdict"] = al["verdict"]
    out["k"], out["N"], out["A"], out["chance"] = al["k"], al["N"], al["A"], ch
    L.append(f"=> PRIMARY VERDICT: {al['verdict']} (the default is the farthest prompt path from the decode path in {al['k']} of {al['N']} texts)")
    L.append("text-level means of the distance (equal weight per text; t(N-1) = CR1 and whole-text bootstrap intervals), and the "
             "position-weighted mean (CR1 over texts) with the 2,048-block SE beside it, labelled:")
    for g in paths:
        m, pw = al["means"][g], tl["pooled"][g]
        L.append(f"  {g:10s} {lab.get(g, g)[:34]:34s} mean {m['mean']:.5f} t[{m['ci'][0]:.5f}, {m['ci'][1]:.5f}] boot[{m['boot_ci'][0]:.5f}, "
                 f"{m['boot_ci'][1]:.5f}] | position-weighted {pw['mean']:.5f} CR1[{pw['ci'][0]:.5f}, {pw['ci'][1]:.5f}] se {pw['se']:.5f}; "
                 f"2,048-block SE {pw['block2048_se']:.5f} (not used for the verdict)")
    for g, v in al["paired"].items():
        L.append(f"  default - {g:10s} {v['mean']:+.5f} t[{v['ci'][0]:+.5f}, {v['ci'][1]:+.5f}] boot[{v['boot_ci'][0]:+.5f}, {v['boot_ci'][1]:+.5f}]")
    L.append("SECONDARY (information only, declared before the analysis):")
    for part, nm in (("short", "pp4k, rep9k"), ("long", "the texts read to >= 16,110 tokens")):
        x = tl[part]
        if not x["N"]:
            L.append(f"  (a) {part} ({nm}): no texts read")
            continue
        L.append(f"  (a) {part} ({nm}): the default is the farthest in {x['k']} of {x['N']}; mean distance per path: "
                 + ", ".join(f"{g} {x['means'][g]['mean']:.5f}" for g in paths))
    L.append("  (b) per-position |dNLL| by position in the text (pooled mean / median, positions, texts; whole-text bootstrap "
             "interval of the mean); growth = per text, its last bin's mean minus its first bin's:")
    for title, tab in (("against ref, all 8 distinct texts (the gaps' rows.tsv)", res.get("bins_rows", {}).get("pairs", {})),
                       ("on the dec positions", res.get("bins", {}))):
        if not tab:
            continue
        L.append(f"    {title}:")
        for pair, v in tab.items():
            cells = "; ".join(f"{b} {x['mean']:.3f}/{x['median']:.3f} ({x['n']}, {x['texts']}t) [{x['text_ci'][0]:.3f}, {x['text_ci'][1]:.3f}]"
                              for b, x in v["bins"].items())
            L.append(f"      {pair:20s} {cells} | growing in {v['texts_growing']} of {v['texts_with_2_bins']} texts")
    return L



def cmd_decide(a):
    o = Path(a.outdir)
    g = read_gates(o / "gap" / "gates.txt") if (o / "gap" / "gates.txt").exists() else read_gates(o / "gates.txt")
    L = [f"decode-path check - decision ({time.strftime('%F %T')}; rules: work/r23/decpath_rules.py = rules.txt with its 11-05 revision, written before the analysis)"]
    out = {"written": time.strftime("%F %T")}
    rp = Path(a.result)
    why = []
    if g.get("run_dec", ("MISSING",))[0] != "PASS" or g.get("env_dec", ("MISSING",))[0] != "PASS":
        why.append(f"dec arm: run {g.get('run_dec', ('MISSING',))[0]}, env {g.get('env_dec', ('MISSING',))[0]}")
    res = json.loads(rp.read_text()) if rp.exists() else None
    if res is None:
        why.append("no compare result")
    dflt = None
    if res:
        groups = res["groups"]
        dflt = next((k for k, m in groups.items() if "default" in m), None)
        al = res["stats"]["all"]
        if dflt is None:
            why.append("the default arm is missing")
        elif al.get("n", 0) == 0:
            why.append("no positions")
        else:
            if len(al["texts"]) < MIN_TEXTS:
                why.append(f"only {len(al['texts'])} distinct text(s) read through the decode path (the rule needs {MIN_TEXTS}+)")
            if "text_level" not in res:
                why.append("no text-level statistics in the compare result (an older compare)")
            if res.get("target_mismatch"):
                why.append(f"{res['target_mismatch']} decode lines carry another target than the text's next token")
            A, Km = al["arms"][dflt]["A"]["mean"], al["arms"][dflt]["K"]["median"]
            if A < PAIR_A or Km > PAIR_K:
                why.append(f"pairing check failed: top-1 agreement {100 * A:.1f} % (>= {100 * PAIR_A:.0f} %), median K {Km:.3f} (<= {PAIR_K})")
    if why:
        L.append("=> NOT JUDGED: " + "; ".join(why))
        out["verdict"] = "NOT JUDGED"
    else:
        lab = res.get("labels", {})
        L.append(f"decode path: engine-r22p028x (x28h), 2-row verify windows, STRATA_LOGPOS top 64; {res['n']} positions "
                 f"(every 8th row from 1,024) in {len(res['stats']['all']['texts'])} texts: {', '.join(res['stats']['all']['texts'])}")
        L.append("variant groups (byte-identical rows share a line): " + "; ".join(
            f"{k} = {' / '.join(m)}" for k, m in res["groups"].items()))
        L += text_level_lines(res, dflt, lab, out)
        # window and stock checks
        for k_, w in (res.get("window") or {}).items():
            L.append(f"(c) 1-row check ({k_}, {w['n']} positions, 1-row windows on engine-r22p028xm vs the 2-row decode path on the "
                     f"served binary; 2,048-block intervals, one text): NLL d {fmt_ci(w['W_D'])}, mean |dNLL| {w['W_abs']['mean']:.3f}, "
                     f"top-1 agreement {100 * w['W_A']['mean']:.1f} % -> the reference is "
                     + ("SOUND on that text" if w.get("sound") else "NOT SHOWN SOUND on that text") + f" ({w.get('sound_why', 'no prompt-path rows on it')})")
            for b_, x_ in w.get("bins", {}).get("1-row vs 2-row", {}).get("bins", {}).items():
                L.append(f"    {b_:6s} |dNLL| 1-row vs 2-row mean {x_['mean']:.3f} median {x_['median']:.3f} ({x_['n']} positions), "
                         f"top-1 agreement {100 * w.get('bins_top1', {}).get(b_, float('nan')):.1f} %")
            if "vs_dec1" in w:
                L.append("  against 1-row (NLL d / top-1): " + "; ".join(f"{g_} {v_['D']:+.3f} / {100 * v_['A']:.1f} %" for g_, v_ in w["vs_dec1"].items()))
                L.append("  against 2-row, same rows:     " + "; ".join(f"{g_} {v_['D']:+.3f} / {100 * v_['A']:.1f} %" for g_, v_ in w["vs_dec"].items()))
                L.append("  mean |dNLL| to 2-row, same rows: " + "; ".join(f"{g_} {v_.get('Dabs', float('nan')):.3f}" for g_, v_ in w["vs_dec"].items()))
        if not res.get("window"):
            L.append("(c) 1-row check: not run (dec1 missing) - the 2-row reference is not checked against 1-row windows")
        for k_, s_ in (res.get("stock") or {}).items():
            L.append(f"stock check ({k_}, {s_['n']} positions): KL(dec || s210dec) {s_['K']['mean']:.4f}, NLL d {fmt_ci(s_['D'])}, "
                     f"top-1 agree {100 * s_['A']['mean']:.1f} % -> " + ("x28h's decode path stands for stock's" if s_["agree"]
                                                                        else "FLAG: stock's decode path differs - read the GDN line against it"))
        if not res.get("stock"):
            L.append("stock check: not run (s210dec missing)")
        # effect on real work
        wl, src = workloads()
        L.append(f"effect on real long-prompt work ({'THE MAIN ASK: the default is the outlier' if out['verdict'].startswith('DEFAULT IS THE OUTLIER') else 'INFO'}; "
                 f"position-weighted numbers per range, no intervals; the 9-workload screen's prompt lengths from {src}):")
        for w_, n_ in wl.items():
            s = stratum(min(n_, 32767)) if n_ >= MIN_POS else None
            st = res["stats"].get(s, {}) if s else {}
            if not s:
                L.append(f"  {w_:14s} {n_:6,d} tokens: below 1,024 - not measured")
                continue
            if not st.get("n"):
                L.append(f"  {w_:14s} {n_:6,d} tokens ({s}): no positions in that range")
                continue
            c = st.get("closest", {}).get("arm")
            c = c if c != dflt else (sorted((k for k in st["arms"] if k != dflt), key=lambda k: st["arms"][k]["K"]["mean"]) or [None])[0]
            x, y = st["arms"][dflt], st["arms"].get(c) if c else None
            ext = " (beyond the measured 32K: the 16-32K numbers, an extrapolation)" if n_ >= 32768 else ""
            line = (f"  {w_:14s} {n_:6,d} tokens ({s}{ext}): the default's next pick differs from the decode path's in "
                    f"{100 * (1 - x['A']['mean']):.1f} % of cases, a T=1 draw in {100 * x['TV']['mean']:.1f} %, NLL d {x['D']['mean']:+.3f} "
                    f"(perplexity {100 * (math.exp(x['D']['mean']) - 1):+.1f} %)")
            if y:
                line += (f"; {c}: {100 * (1 - y['A']['mean']):.1f} %, {100 * y['TV']['mean']:.1f} %, {y['D']['mean']:+.3f} "
                         f"({100 * (math.exp(y['D']['mean']) - 1):+.1f} %)")
            L.append(line)
        L.append("  (per position: the next-token distribution after a prompt of that length, teacher-forced; generation "
                 "quality itself is not measured here)")
    sl, sv = speed_lines(Path(a.outdir) / "gap" / "speed", g)
    out["speed"] = {f"{k[0]}:{k[1]}": v for k, v in sv.items()}
    L.append("prompt speed, cold, Basalt's fixtures on P028x as served (x28h, two cards; what turning the fused path off costs):")
    L += ["  " + x for x in sl]
    L.append("  GDN on: prompt speed not priced (gap 17 did not measure it) and not measured here")
    L.append("  note: the served config already has STRATA_PREFILL_CPU_SHARE=0.4 (max 1,792); the NLL yardstick forces 0")
    pr = Path(a.outdir) / "pillow" / "RESULT.txt"
    if pr.exists():
        L.append("pillow step: " + pr.read_text().strip().splitlines()[-1][:300])
    mb = Path(a.outdir) / "decision-b-merged.txt"
    if mb.exists():
        L.append(f"decode gap b, merged with the rerun passes: {mb.relative_to(WS)} - " +
                 "; ".join(x.strip() for x in mb.read_text().splitlines() if x.startswith("=> item"))[:400])
    L.append("Nothing is changed or switched by this gap: P028x stays served; Karl decides.")
    (Path(a.outdir) / "decision.txt").write_text("\n".join(L) + "\n")
    (Path(a.outdir) / "decision.json").write_text(json.dumps(out, indent=1))
    print("\n".join(L))
    return 0


# ================================================================================================ selftest
def selftest(a):
    import numpy as np
    sc = Path(a.dir)
    if sc.exists():
        shutil.rmtree(sc)
    sc.mkdir(parents=True)
    fails = []

    def chk(name, ok, detail=""):
        print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")
        if not ok:
            fails.append(name)
    S = score_mod()
    # 1 kl65 against the full-vocabulary KL on a small vocabulary (top 64 of 300 hold ~all mass / part of it)
    rng = np.random.default_rng(1)
    for spread in (6.0, 1.0):
        zd = rng.standard_normal(300) * spread
        zx = zd + rng.standard_normal(300) * 0.3
        ld = zd - np.log(np.exp(zd).sum())
        lx = zx - np.log(np.exp(zx).sum())
        top = np.argsort(-ld)[:64]
        kl, tv = kl65(ld[top][None], lx[top][None])
        full = float((np.exp(ld) * (ld - lx)).sum())
        tvf = 0.5 * float(np.abs(np.exp(ld) - np.exp(lx)).sum())
        chk(f"kl65 <= full KL, close when top 64 hold the mass (spread {spread})", kl[0] <= full + 1e-12 and
            (spread < 3 or abs(kl[0] - full) < 0.02 * full + 1e-6) and tv[0] <= tvf + 1e-12,
            f"kl65 {kl[0]:.5f} full {full:.5f}, tv65 {tv[0]:.4f} full {tvf:.4f}")
    kl0, tv0 = kl65(ld[top][None], ld[top][None])
    chk("kl65 of identical distributions is 0", abs(kl0[0]) < 1e-12 and abs(tv0[0]) < 1e-12)
    # 2 the budget: whole, shortened, skipped; the scale follows the real reads
    t = [0.0]
    b = Budget("logpos", 600, clock=lambda: t[0])
    it = {"cut": 32768, "min_cut": 8192, "name": "x"}
    chk("budget: a 32K read does not fit 10 min at the prior model", b.fit(it)[0] == 0 or b.fit(it)[0] < 32768)
    c, note = Budget("logpos", 200, clock=lambda: 0.0).fit({"cut": 16110, "min_cut": 4096, "name": "y"})
    chk("budget: shortened to fit, a multiple of 64", 4096 <= c < 16110 and c % 64 == 0 and SAFETY * model_s("logpos", c) <= 200, note)
    b.add(4096, 2 * model_s("logpos", 4096))
    chk("budget: the scale follows the real reads", abs(b.scale() - 2.0) < 1e-9)
    t[0] = 590
    chk("budget: nothing fits at the end", b.fit({"cut": 4096, "min_cut": 0, "name": "z"})[0] == 0)
    # 3 the runner against a mock engine (LOGPOS lines and FORCE lines as the engines write them), the env check rules
    mock = sc / "mock_engine.py"
    mock.write_text(MOCK)
    mock.chmod(0o755)
    cfg = {"exe": str(mock), "args": ["--pack", "none", "--spec", "7", "--kv", "int8"], "env": {"CUDA_VISIBLE_DEVICES": "0",
           "STRATA_ROUTE_TAIL_SKIP": "0"}, "cwd": str(sc)}
    (sc / "mock.json").write_text(json.dumps(cfg))
    for kind in ("logpos", "force"):
        od = sc / f"run-{kind}"
        ns = argparse.Namespace(config=str(sc / "mock.json"), outdir=str(od), kind=kind, plan="mock", budget_min=30,
                                env=["STRATA_FORCE_T1=1"] if kind == "force" else None, min_free_gb=0)
        try:
            rc = cmd_run(ns)
        except SystemExit as e:
            rc = f"SystemExit {e}"
        idx = json.loads((od / "index.json").read_text()) if (od / "index.json").exists() else {}
        n = len(idx.get("requests", []))
        if kind == "logpos":
            d = read_logpos(od)
            ids = load_ids("rep9k.tokens")
            okt = all(d["rep9k.tokens"]["pos"][p][0] == ids[p + 1] for p in d["rep9k.tokens"]["pos"])
            chk("run logpos on the mock: rc 0, 3 texts, cut-1 lines each, targets = the text", rc == 0 and n == 3 and okt and
                len(d["pp4k.tokens"]["pos"]) == 2047, f"rc {rc}, {n} texts, problems {idx.get('problems')}")
        else:
            fz = read_force(od)
            ids = load_ids("pp4k.tokens")
            okt = all(fz["pp4k.tokens"][q][0] == ids[q + 1] for q in fz["pp4k.tokens"])
            chk("run force on the mock: rc 0, cut-2 forced rows from position 1, targets = the text", rc == 0 and okt and
                sorted(fz["pp4k.tokens"])[:2] == [1, 2] and len(fz["pp4k.tokens"]) == 2046, f"rc {rc}, problems {idx.get('problems')}")
    od = sc / "run-die"           # the engine ends inside the 2nd text (a watchdog stop): rc 2, the 1st text kept
    os.environ["MOCK_DIE"] = "2"
    try:
        rc = cmd_run(argparse.Namespace(config=str(sc / "mock.json"), outdir=str(od), kind="logpos", plan="mock", budget_min=30,
                                        env=None, min_free_gb=0))
    except SystemExit as e:
        rc = f"SystemExit {e}"
    finally:
        os.environ.pop("MOCK_DIE", None)
    idx = json.loads((od / "index.json").read_text())
    chk("run: the engine ending inside a text -> rc 2, the finished text kept", rc == 2 and len(idx["requests"]) == 1 and
        len(read_logpos(od)["pp4k.tokens"]["pos"]) == 2047, f"rc {rc}")
    args, L = engine_cmd(cfg, "logpos", "mock")
    NR = load("nll_rules", NRP)
    qq = qq_mod()
    want = NR.want_of(cfg, None, qq.FIXED_ENV)
    aw = {"--expert-cache": "1", "--pcie-frac": "0", "--kv": "fp16", "--adapt-every": "100000", "--suffix-draft": "0",
          "--prompt-cache": "0", "--spec": "2", "--short-read": str(L + 64), "--prefill": "512", "--max-context": str(L + 512)}
    env = dict(want, STRATA_LOGPOS="x", STRATA_LOGPOS_TOPK="64")
    chk("envwatch rules: the runner's own args and env pass", not check_engine(env, args, want, 1, aw, "logpos"),
        str(check_engine(env, args, want, 1, aw, "logpos")))
    chk("envwatch rules: tail skip on fails", bool(check_engine(dict(env, STRATA_ROUTE_TAIL_SKIP="1"), args, want, 1, aw, "logpos")))
    chk("envwatch rules: a stray switch fails", bool(check_engine(dict(env, STRATA_PF_FUSED="0"), args, want, 1, aw, "logpos")))
    chk("envwatch rules: --spec 7 fails", bool(check_engine(env, [x if x != "2" else "7" for x in args], want, 1, aw, "logpos")))
    chk("envwatch rules: a logpos arm without STRATA_LOGPOS fails", bool(check_engine(want, args, want, 1, aw, "logpos")))
    # 4 compare on synthetic rows + a synthetic head (score.py's Head with small weights), checked by hand at one position
    n_e, hc, lr, V = 8, 4, 3, 300
    w = (rng.standard_normal(hc * n_e).astype(np.float32) * 0.1 + 1, rng.standard_normal((lr, hc * n_e)).astype(np.float32) * 0.1,
         rng.standard_normal((hc * n_e, lr)).astype(np.float32) * 0.1, rng.standard_normal((V, n_e)).astype(np.float32), n_e, hc, lr)
    head = S.Head(weights=w)
    texts = {"pp4k.tokens": 4096, "rep9k.tokens": 9010, "ldrsyn20k.tokens": 16110, "32k.tokens": 18432,
             "tf-long64k.prompt": 4096, "tf-long28k.prompt": 4096, "tf-long112k.prompt": 4096, "tf-long40k.prompt": 4096}
    roots = []
    base = {f: rng.standard_normal((n // EVERY + 1, hc * n_e)).astype(np.float32) for f, n in texts.items()}
    for k, sh in (("default", 0.08), ("ref", 0.08), ("unfused", 0.04), ("v2", 0.02)):
        d = sc / "arms" / k
        d.mkdir(parents=True)
        reqs = []
        for i, (f, n) in enumerate(texts.items()):
            sh_ = 0.0 if k in ("default", "ref") and f == "tf-long40k.prompt" else sh   # the default closest in one text
            r_ = base[f] + (np.random.default_rng(i + 99 + 1000 * ("unfused", "v2").index(k) if k in ("unfused", "v2") else i + 99)
                            .standard_normal(base[f].shape).astype(np.float32) * sh_ if sh_ else 0)
            u = r_.view(np.uint32).astype(np.uint64)
            np.save(d / f"a.{i}.npy", ((u + ((u >> 16) & 1) + 0x7FFF) >> 16).astype(np.uint16))
            reqs.append({"name": f"{f.split('.')[0]}-{n}", "file": f, "cut": n, "kind": "text", "rows": len(r_), "dump": f"a.{i}.npy"})
        (d / "index.json").write_text(json.dumps({"requests": reqs, "rows": f"all:{EVERY}"}))
        roots.append((k, d, k, True))
    dd = sc / "dec"
    dd.mkdir()
    lines, reqs = [], []
    for f, n in texts.items():
        ids = load_ids(f)
        z = head.logits(base[f]).astype(np.float64)                            # the decode path: the clean rows
        z = z + np.random.default_rng(7).standard_normal(z.shape) * 0.02      # + its own rounding
        lz = z - np.log(np.exp(z - z.max(1, keepdims=True)).sum(1, keepdims=True)) - z.max(1, keepdims=True)
        first = len(lines)
        for p in range(0, n - 1, EVERY):           # (dec lines at the rows' positions only: smaller files)
            row = lz[p // EVERY]
            top = np.argsort(-row)[:TOPK]
            tg = ids[p + 1] % V
            lines.append("\t".join([str(p), str(tg), f"{row[tg]:.9f}", str(int(row.argmax())), f"{row.max():.9f}", "0", "nan", "nan"]
                                   + [f"{int(t_)}:{row[t_]:.6f}" for t_ in top]))
        reqs.append({"name": f"{f.split('.')[0]}-{n}", "file": f, "cut": n, "first_line": first, "end_line": len(lines)})
    (dd / "score.tsv").write_text("\n".join(lines) + "\n")
    (dd / "index.json").write_text(json.dumps({"requests": reqs}))
    d1 = sc / "dec1"                               # a synthetic 1-row arm on ldrsyn20k: dec's NLL + small noise
    d1.mkdir()
    dl = read_logpos(dd)["ldrsyn20k.tokens"]
    nz = np.random.default_rng(11).standard_normal(len(dl["pos"])) * 0.01
    (d1 / "force.tsv").write_text("".join(f"ldrsyn20k-16110\t{q}\t{v[0]}\t{v[2]}\t{-v[1] + e:.6f}\n" for (q, v), e in zip(sorted(dl["pos"].items()), nz)))
    (d1 / "index.json").write_text(json.dumps({"requests": [{"name": "ldrsyn20k-16110", "file": "ldrsyn20k.tokens", "cut": 16110}]}))
    orig = load_ids
    globals()["load_ids"] = lambda f: [x % V for x in orig(f)]
    try:
        ns = argparse.Namespace(dec=str(dd), dec1=str(d1), stock=None, json=str(sc / "result.json"), rows_out=str(sc / "rows.tsv"),
                                chunk=64, boot=500)
        cmd_compare(ns, head=head, roots=roots)
    finally:
        globals()["load_ids"] = orig
    res = json.loads((sc / "result.json").read_text())
    chk("compare: default and ref fall in one group, unfused and v2 their own", res["groups"].get("default") == ["default", "ref"]
        and "unfused" in res["groups"] and "v2" in res["groups"], str(res["groups"]))
    nexp = sum(len([p for p in range(0, n - 1, EVERY) if p >= MIN_POS and p + 1 < n]) for n in texts.values())
    chk("compare: positions = every 8th row from 1,024 of both texts", res["n"] == nexp, f"{res['n']} vs {nexp}")
    rr = (sc / "rows.tsv").read_text().splitlines()
    hd = rr[0].split("\t")
    f1 = rr[1].split("\t")
    p0 = int(f1[1])
    Rb = S.bf16_to_f32(np.load(sc / "arms/unfused/a.0.npy"))[p0 // EVERY]
    lq = head.logp(Rb[None])[0]
    ids4 = [x % V for x in orig("pp4k.tokens")]
    chk("compare: NLL of unfused at the first position by hand", abs(float(f1[hd.index("nll_unfused")]) + lq[ids4[p0 + 1]]) < 1e-3,
        f"{f1[hd.index('nll_unfused')]} vs {-lq[ids4[p0 + 1]]:.6f}")
    st = res["stats"]["all"]
    chk("compare: stats per stratum and paired lines", set(res["stats"]) == {"1-4K", "4-16K", "16-32K", "all"} and
        set(st["paired"]) == {"unfused", "v2"} and res["stats"]["16-32K"]["n"] > 0)
    tl = res["text_level"]
    pt = tl["per_text"]
    chk("text level: 8 texts, the default farthest in 7 (not in tf-long40k, where it is the clean rows), A = 3",
        tl["all"]["N"] == 8 and tl["all"]["k"] == 7 and tl["all"]["A"] == 3 and not pt["tf-long40k-4096"]["default_farthest"]
        and tl["all"]["verdict"] == "DEFAULT IS THE OUTLIER", f"k {tl['all']['k']}, ranks {[x['default_rank'] for x in pt.values()]}")
    hand = float(np.mean([pt[t]["paths"]["default"]["K"] - pt[t]["paths"]["unfused"]["K"] for t in pt]))
    chk("text level: the paired mean is the equal-weight mean of the per-text differences; short = pp4k, rep9k",
        abs(tl["all"]["paired"]["unfused"]["mean"] - hand) < 1e-12 and tl["short"]["N"] == 2 and tl["long"]["N"] == 6
        and "block2048_se" in tl["pooled"]["default"])
    rows_ = (sc / "rows.tsv").read_text().splitlines()
    h_ = rows_[0].split("\t")
    kk = [float(r.split("\t")[h_.index("kl_v2")]) for r in rows_[1:] if r.startswith("pp4k-4096\t")]
    chk("text level: D_t = the mean KL over the text's rows (pp4k, v2, from rows.tsv)",
        abs(pt["pp4k-4096"]["paths"]["v2"]["K"] - float(np.mean(kk))) < 1e-5 * max(1.0, float(np.mean(kk))) + 1e-9)
    bc = res["bins"]
    chk("bins: 0-2K, 2-8K, 8-16K, 16K+ for every path vs dec and vs ref; 16K+ only from 32k",
        set(bc["v2 vs dec"]["bins"]) == {"0-2K", "2-8K", "8-16K", "16K+"} and "unfused vs ref" in bc and
        bc["default vs dec"]["bins"]["16K+"]["texts"] == 1)
    br = res.get("bins_rows", {}).get("pairs", {})
    chk("bins from the gaps' rows.tsv: 8 distinct texts (the 3 duplicates dropped), unfused / cpushare / v2 / gdn vs ref",
        set(br) == {"unfused vs ref", "cpushare vs ref", "v2 vs ref", "gdn vs ref"} and
        max(x["texts"] for x in br["unfused vs ref"]["bins"].values()) == 8, str({k: [x["texts"] for x in v["bins"].values()] for k, v in br.items()}))
    wn = res["window"]["ldrsyn20k-16110"]
    chk("1-row check: |dNLL| ~0.008 (noise 0.01), top-1 100 %, SOUND, bins present",
        0.004 < wn["W_abs"]["mean"] < 0.012 and wn["W_A"]["mean"] == 1.0 and wn["sound"] and "2-8K" in wn["bins"]["1-row vs 2-row"]["bins"],
        wn.get("sound_why", ""))
    c8 = chance(5, 8)
    chk("chance rates (A 5, N 8): P(k >= 7) 0.000084, P(k <= 4) 0.9896, P(5-6) 0.0103",
        abs(c8["p_out"] - 8.448e-05) < 1e-8 and abs(c8["p_not"] - 0.98959) < 1e-4 and abs(c8["p_inc"] - 0.01032) < 1e-4
        and c8["hi"] == 7 and c8["lo"] == 4, str(c8))
    c6 = chance(5, 6)
    chk("the rule: N 8 -> 7 OUTLIER, 5-6 INCONCLUSIVE, 4 NOT; N 6 -> 6 / 4-5 / 3; N 4 -> NOT JUDGED",
        [text_verdict(k_, 8) for k_ in (8, 7, 6, 5, 4, 0)] == ["DEFAULT IS THE OUTLIER"] * 2 + ["INCONCLUSIVE"] * 2 + ["DEFAULT IS NOT AN OUTLIER"] * 2
        and (c6["hi"], c6["lo"]) == (6, 3) and text_verdict(5, 6) == "INCONCLUSIVE" and text_verdict(4, 4).startswith("NOT JUDGED"))
    cr = cr1_pooled([2, 4, 9], [1, 2, 3])
    chk("CR1 of a pooled mean by hand (2.5, se 0.381881)", abs(cr["mean"] - 2.5) < 1e-12 and abs(cr["se"] - 0.3818813) < 1e-6
        and abs(cr["ci"][1] - (2.5 + 4.303 * 0.3818813)) < 1e-5, str(cr))
    # 5 decide on synthetic stats: the three verdicts and THIN
    def fake(dd_, dk, cc, n=2000, texts_=("a", "b", "c")):
        arms = {"default": {"D": {"mean": dd_[0], "ci": dd_[1]}}}
        paired = {g: {"dK": {"mean": 0, "ci": dk[g]}, "c": {"mean": 0, "ci": cc[g]}} for g in dk}
        return {"n": n, "texts": list(texts_), "arms": arms, "paired": paired}
    v1, _ = verdict(fake((0.1, [0.05, 0.15]), {"u": [0.01, 0.03], "v": [0.02, 0.04]}, {"u": [0.02, 0.1], "v": [0.01, 0.2]}), "default")
    v2_, _ = verdict(fake((0.1, [0.05, 0.15]), {"u": [-0.01, 0.03], "v": [0.02, 0.04]}, {"u": [-0.02, 0.1], "v": [0.01, 0.2]}), "default")
    v3, _ = verdict(fake((0.1, [0.05, 0.15]), {"u": [0.01, 0.03], "v": [-0.02, 0.04]}, {"u": [0.02, 0.1], "v": [0.01, 0.2]}), "default")
    v4, _ = verdict(fake((0.1, [0.05, 0.15]), {"u": [0.01, 0.03]}, {"u": [0.02, 0.1]}, n=300), "default")
    v5, _ = verdict(fake((0.1, [-0.01, 0.15]), {"u": [0.01, 0.03]}, {"u": [0.02, 0.1]}), "default")
    chk("verdict: OUTLIER / NOT (u neither) / MIXED / THIN / (a) fails -> MIXED",
        v1 == "DEFAULT IS THE OUTLIER" and v2_.startswith("DEFAULT IS NOT") and v3 == "MIXED" and v4.startswith("THIN") and v5 == "MIXED",
        f"{v1} | {v2_} | {v3} | {v4} | {v5}")
    # decide end to end on the synthetic compare (gates PASS) -> a decision file with every section
    od = sc / "out"
    (od / "gap").mkdir(parents=True)
    (od / "gap" / "gates.txt").write_text("run_dec PASS x\nenv_dec PASS x\n")
    (od / "gap" / "speed").mkdir()
    for arm, v in (("def", 4400), ("unf", 4000), ("sh0", 4350)):
        (od / "gap" / "speed" / f"cold-{arm}.jsonl").write_text("".join(json.dumps({"test": t_, "prompt_tps": v * (1 + 0.01 * k), "pass": k,
                                                                            "label": f"sp-{arm}-{t_}-{k}"})
                                                                + "\n" for t_ in ("pp16k", "pp64k") for k in (1, 2)))
        with open(od / "gap" / "gates.txt", "a") as gf:
            gf.write("".join(f"env_sp-{arm}-{t_}-{k} PASS x\n" for t_ in ("pp16k", "pp64k") for k in (1, 2)))
    with open(od / "gap" / "gates.txt", "a") as gf:
        gf.write("fatal_sp-sh0-pp64k-2 FAIL synthetic\n")
    cmd_decide(argparse.Namespace(outdir=str(od), result=str(sc / "result.json")))
    txt = (od / "decision.txt").read_text()
    chk("decide: the text-level verdict, chance rates, labelled block SE, secondary (a)/(b)/(c), the workloads, speed",
        "=> PRIMARY VERDICT: DEFAULT IS THE OUTLIER" in txt and "P(k >= 7) = 0.00" in txt and "(not used for the verdict)" in txt
        and "(a) short" in txt and "(b) per-position" in txt and "(c) 1-row check" in txt and "SOUND on that text" in txt
        and "16K+" in txt and "R1-verify20k" in txt and "PF_FUSED=0 " in txt and "-9." in txt and "GDN on: prompt speed not priced" in txt
        and "below 1,024 - not measured" in txt and "CPU share 0: 1 of 2 passes" in txt)
    (od / "gap" / "gates.txt").write_text("run_dec FAIL x\nenv_dec PASS x\n")
    cmd_decide(argparse.Namespace(outdir=str(od), result=str(sc / "result.json")))
    chk("decide: a failed dec arm -> NOT JUDGED", "NOT JUDGED" in (od / "decision.txt").read_text())
    # 6 freeze diff
    (sc / "f1.txt").write_text("numpy==2.5.3\nPillow==12.3.0\nmatplotlib==3.11.2\n")
    (sc / "f2.txt").write_text("numpy==2.5.3\npillow==13.0.0\nmatplotlib==3.11.2\n")
    (sc / "f3.txt").write_text("numpy==2.6.0\npillow==13.0.0\nmatplotlib==3.11.2\n")
    fd = lambda b_, a_, want: cmd_freeze_diff(argparse.Namespace(before=str(sc / b_), after=str(sc / a_), allow="pillow", want=want))
    chk("freeze-diff: only pillow -> OK; numpy too -> NOT OK; rollback = before -> OK",
        fd("f1.txt", "f2.txt", "pillow==13.0.0") == 0 and fd("f1.txt", "f3.txt", "pillow==13.0.0") == 1 and fd("f1.txt", "f1.txt", None) == 0)
    # 7 decode gap b's missing passes (its real files, read only) and the merge on a copy
    if (GAPB / "bp90").exists():
        m = bp_missing(GAPB / "bp90")
        chk("bp90-missing on gap b's files: the 7 recorded (or fewer later, never others from passes 1-2)",
            all(x in BP_EXPECTED or x[2] == 3 for x in m), " ".join(f"{x}-{y}-{z}" for x, y, z in m))
        rr_ = sc / "rerun"
        rr_.mkdir()
        recs = [{"label": f"bp{arm}-{s}-{k}", "test": t_, "pass": k, "prompt_tps": 4000.0, "decode_tps": 150.0}
                for arm, s, k in m for t_ in BP_SETS[s]]
        for arm in ("B", "LO"):
            (rr_ / f"cold-{arm}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs if r["label"].startswith(f"bp{arm}-")))
        (rr_ / "gates.txt").write_text("".join(f"env_bp{arm}-{s}-{k} PASS synthetic\n" for arm, s, k in m))
        cmd_merge_b(argparse.Namespace(gap_b=str(GAPB), rerun=str(rr_), merged=str(sc / "merged")))
        chk("merge-b: nothing missing after the merge, gap b's files untouched", not bp_missing(sc / "merged" / "bp90") and
            (sc / "merged" / "gates.txt").exists())
    # 8 configs (into the scratch dir) and their check
    cmd_configs(argparse.Namespace(dir=str(sc / "cfg"), check=False))
    chk("configs: written and checked", cmd_configs(argparse.Namespace(dir=str(sc / "cfg"), check=True)) == 0)
    print(f"selftest: {len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else ""))
    return 1 if fails else 0


MOCK = r'''#!/home/USER/ai-speed-testing/strata-compare/.venv/bin/python
"""decpath selftest's stand-in for the engine: READY; GEN 1 <ids> -> one STRATA_LOGPOS line per position 0..n-2 (the
engine's layout, 64 id:logp pairs); GEN N force=N <ids> -> N "T" lines on stdout and N FORCE lines on stderr; QUIT"""
import os, sys, math
lp = os.environ.get("STRATA_LOGPOS")
die, k_req = os.environ.get("MOCK_DIE"), 0
print("READY", flush=True)
for line in sys.stdin:
    if line.startswith("QUIT"):
        break
    k_req += 1
    if die == str(k_req):
        sys.exit(9)
    f = line.split()
    keys = {k: v for k, v in (x.split("=", 1) for x in f[2:-1] if "=" in x)}
    ids = [int(x) for x in f[-1].split(",")]
    if "force" in keys:
        N = int(keys["force"])
        sys.stderr.write(f"strata serve: FORCE begin: prompt {len(ids) - N} tokens, {N} forced\n")
        for k in range(N):
            print("T", ids[len(ids) - N + k], flush=False)
            sys.stderr.write(f"FORCE {k} {ids[len(ids) - N + k]} {ids[len(ids) - N + k]} {0.5 + (k % 7) / 10:.6f}\n")
        sys.stderr.flush()
    elif lp:
        with open(lp, "a") as o:
            for p in range(len(ids) - 1):
                tg = ids[p + 1]
                o.write("\t".join([str(p), str(tg), "-1.0", str(tg), "-1.0", "1", "nan", "nan"]
                                  + [f"{tg + j}:{-1.0 - j / 10:.6f}" for j in range(64)]) + "\n")
    print("DONE 1 tokens", flush=True)
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name):
        p = sp.add_parser(name)
        p.add_argument("--gate")
        p.add_argument("--gates")
        return p
    sub("rules").add_argument("--out", default=str(OUT / "rules.txt"))
    p = sub("configs")
    p.add_argument("--dir", default=str(OUT / "cfg"))
    p.add_argument("--check", action="store_true")
    sub("pre")
    p = sub("plan")
    p.add_argument("name", choices=list(PLANS))
    p.add_argument("--kind", default="logpos", choices=list(COST))
    p = sub("run")
    p.add_argument("config")
    p.add_argument("outdir")
    p.add_argument("--kind", required=True, choices=list(COST))
    p.add_argument("--plan", required=True, choices=list(PLANS))
    p.add_argument("--budget-min", type=float, required=True)
    p.add_argument("--env", action="append")
    p.add_argument("--min-free-gb", type=float, default=16)
    p = sub("envwatch")
    p.add_argument("job", type=int)
    p.add_argument("config")
    p.add_argument("--kind", required=True, choices=list(COST))
    p.add_argument("--plan", required=True, choices=list(PLANS))
    p.add_argument("--env", action="append")
    p.add_argument("--kill", action="store_true")
    p.add_argument("--max-s", type=float, default=7200)
    p = sub("unittests")
    p.add_argument("--tree", default=str(WS / "strata-r22p028x"))
    p.add_argument("--out", required=True)
    sub("mpl-check").add_argument("--out", required=True)
    p = sub("vision-check")
    p.add_argument("url")
    p.add_argument("--out", required=True)
    p.add_argument("--max-tokens", type=int, default=256)
    p.add_argument("--timeout", type=float, default=300)
    p = sub("freeze-diff")
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--allow", default="pillow")
    p.add_argument("--want")
    sub("bp90-missing").add_argument("--bp90", default=str(GAPB / "bp90"))
    p = sub("merge-b")
    p.add_argument("--gap-b", default=str(GAPB))
    p.add_argument("--rerun", default=str(OUT / "bp90-rerun"))
    p.add_argument("--merged", default=str(OUT / "decb-merged"))
    p = sub("compare")
    p.add_argument("--dec", required=True)
    p.add_argument("--dec1")
    p.add_argument("--stock")
    p.add_argument("--json", required=True)
    p.add_argument("--rows-out")
    p.add_argument("--chunk", type=int, default=64)
    p.add_argument("--boot", type=int, default=BOOT)
    p.add_argument("--threads", default="1")          # read by score.py at import (BLAS threads)
    p.add_argument("--nll-rows", default=str(NLL_ROWS))
    p.add_argument("--gdn-rows", default=str(GDN_ROWS))
    p = sub("decide")
    p.add_argument("outdir", nargs="?", default=str(OUT))
    p.add_argument("--result", default=str(OUT / "gap" / "result.json"))
    sub("selftest").add_argument("--dir", default=str(SCRATCH / "selftest"))
    a = ap.parse_args()
    return {"rules": cmd_rules, "configs": cmd_configs, "pre": cmd_pre, "plan": cmd_plan, "run": cmd_run,
            "envwatch": cmd_envwatch, "unittests": cmd_unittests, "mpl-check": cmd_mpl_check, "vision-check": cmd_vision_check,
            "freeze-diff": cmd_freeze_diff, "bp90-missing": cmd_bp90_missing, "merge-b": cmd_merge_b,
            "compare": cmd_compare, "decide": cmd_decide, "selftest": selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
