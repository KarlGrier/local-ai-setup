# Round 15 — the splice's placement C at 120K: which build gives the degenerate answer (2026-10-08T02:03:17-05:00)

the full set (r15-q5s-Cx72-full): both 120K requests 256 tokens / 255 characters, drafts 170/170, decode hit rate 100 %,
needle 0/6; 8K-64K normal. Each arm: a fresh server with C's placement, the 120K needle (run 0).

| arm | needle 120K | output | decode expert-cache hit rate |
|---|---|---|---|
| stock | 6/6 | 2037 characters for 725 tokens | 53.8 % |
| nosplitattn | 6/6 | 2245 characters for 788 tokens | 53.4 % |

→ (first reading, withdrawn by the control below) stock passes and ours passes without STRATA_QSA_SPLIT_ATTN.
| asis | 6/6 | 2196 characters for 780 tokens | 54.0 % |

→ ours as configured PASSES on a fresh server: the full set's failure needs the earlier requests too (not the switch alone).

**After the full set's own order** (fresh server: warm-up, 8K / 32K / 64K speed prompts with 768 tokens each, then the
120K needle):

| arm | 8K / 32K / 64K answers (characters per token) | needle 120K | output | decode expert-cache hit rate |
|---|---|---|---|---|
| asis | 3057 / 768 (4.0) / 2988 / 768 (3.9) / 2796 / 768 (3.6) | 6/6 | 1883 characters for 662 tokens | 52.9 % |
| stock | 3143 / 768 (4.1) / 2814 / 768 (3.7) / 2944 / 768 (3.8) | 6/6 | 1581 characters for 522 tokens | 53.4 % |

**After the full set's own order** (fresh server: warm-up, 8K / 32K / 64K speed prompts with 768 tokens each, then the
120K needle):

| arm | 8K / 32K / 64K answers (characters per token) | needle 120K | output | decode expert-cache hit rate |
|---|---|---|---|---|
| timing | 2974 / 768 (3.9) / 2888 / 768 (3.8) / 3015 / 768 (3.9) | 6/6 | 1982 characters for 687 tokens | 52.8 % |
| stocktiming | 3261 / 768 (4.2) / 2949 / 768 (3.8) / 2948 / 768 (3.8) | 6/6 | 1876 characters for 682 tokens | 49.8 % |

**After the full set's own order** (fresh server: warm-up, 8K / 32K / 64K speed prompts with 768 tokens each, then the
120K needle):

| arm | 8K / 32K / 64K answers (characters per token) | needle 120K | output | decode expert-cache hit rate |
|---|---|---|---|---|
| fullset | 3213 / 768 (4.2) / 3128 / 768 (4.1) / 2845 / 768 (3.7) / 2502 / 768 (3.3) | 6/6 | 2377 characters for 798 tokens | 52.5 % |

**Conclusion (04:39):** the degenerate answers were seen in one session only (the full set r15-q5s-Cx72-full, from its
120K speed prompt on, every later multi-chunk prompt). Eight fresh sessions did not reproduce it: ours fresh, ours
without STRATA_QSA_SPLIT_ATTN, ours as configured, stock fresh, ours and stock in the full set's order with and without
the timing switches, and the full set's exact config and order (its 120K speed prompt included). Intermittent, cause
unknown. Nothing ties it to our patches, but stock never ran in that failing session's conditions either, so neither build is cleared of it.
The saved C config caps the context at 64K as a precaution.
