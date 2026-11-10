# Per-position |dNLL| and KL by position in the text (11-05, Karl (b))

CPU only, from the distinct-text tables (8 texts, 22,597 positions, every 8th row). Bins: 1,024-2K (rows start at 1,024), 2-8K, 8-16K, 16K+ (5 texts reach it). Numbers: position-bins.json. Bound revoked (ADOPTED-BOUND.REVOKED.json): information only.

| path vs ref | bin | n | mean abs dNLL (text CIs in JSON) | median | p90 | KL mean (text CIs in JSON) |
|---|---|---|---|---|---|---|
| unfused | 1-2K / 2-8K / 8-16K / 16K+ | 1024/5632/6213/9728 | 0.48 / 0.56 / 0.49 / 0.43 | 0.15/0.23/0.15/0.09 | 1.33/1.47/1.24/1.19 | 0.119/0.126/0.185/0.145 |
| cpushare | same | same | 0.49 / 0.50 / 0.52 / 0.45 | 0.17/0.20/0.15/0.09 | 1.34/1.31/1.41/1.20 | 0.123/0.117/0.192/0.156 |
| v2 | same | same | 0.50 / 0.51 / 0.49 / 0.42 | 0.15/0.21/0.13/0.08 | 1.46/1.34/1.29/1.11 | 0.099/0.105/0.181/0.149 |
| GDN on | same | same | 0.57 / 0.56 / 0.54 / 0.46 | 0.16/0.23/0.15/0.09 | 1.58/1.49/1.47/1.25 | 0.163/0.138/0.212/0.180 |

Trend inside texts (text fixed effects; whole-text bootstrap = verdict unit; 2,048-block CI not used for the verdict):
abs dNLL slope per 10K tokens: unfused -0.064 [-0.089, -0.033], cpushare -0.046 [-0.080, -0.005], v2 -0.031 [-0.077, +0.014], GDN -0.070 [-0.117, -0.018]. The scatter does not grow with position.
KL slope: all CIs include 0. KL 16K+ minus 1-2K (5 long texts): cpushare +0.056 [+0.030, +0.099] (5/5 texts up), v2 +0.049 [+0.010, +0.106] (5/5), unfused +0.027 [-0.048, +0.088], GDN -0.007 [-0.126, +0.087].
Per-text tables, signed d per bin, CIs: position-bins.json.
