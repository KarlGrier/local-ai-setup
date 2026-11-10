| item | unset (a) | =0 | unset (b) | unset = 0 | unset repeats |
|---|---|---|---|---|---|
| greedy-math | adf3b21c4b45 | adf3b21c4b45 | 98d7cb862c32 | yes | NO |
| greedy-code | 082bc96e07c9 | 082bc96e07c9 | 27eb33005148 | yes | NO |
| seeded-math | 0e932fe52068 | 0e932fe52068 | 1b2290bc22d5 | yes | NO |
| seeded-code | 2c4518427f44 | 5210df1178fe | 6e2ff748e77e | NO | NO |

**Reading (B2).** On the two-card candidate (C\*16.1's flags on v0.1.42) with STRATA_ROUTE_TAIL_SKIP unset, the start-up
line says "STRATA_ROUTE_TAIL_SKIP=7 is ON (default)": the start-up default (generate.cpp ~L8102) tests `--peer-device` and
`--batch` but not the helper cache. The dispatch (expert_source.cpp L3598) skips only with `d.peer == nullptr &&
d.remote_count == 0`, i.e. never with the helper, and the engine's cumulative per-request line ("route tail skip: N missed
experts skipped ... since the start", generate.cpp L12289, printed whenever N > 0) appeared **0 times in 12 requests** in
both unset arms (it appears on every request on one card: Round 18's v0.1.42 one-GPU logs, e.g.
logs/engine-r18v42-pr-gate-one-tson-main.log). So **the tail skip does not act on the two-card config**; only its start-up
line is misleading. The served hashes cannot show it either way: served outputs are not repeatable here (adaptive swaps
follow timing: unset a vs unset b differ on all 4 items), so unset vs 0 differing on 1 of 4 is that noise.

**One-GPU configs:** STRATA_ROUTE_TAIL_SKIP=0 is set in every one-GPU config that serves or measures on a v0.1.42 engine
this round (work/r19/cfg/*, configs/r19-q4-*, configs/r16-q4.json at B7; C\*17's one-GPU fallback when it is made at
promotion). Left as recorded: Round 18's measurement configs (r18v42-*-one-tson-* measured the skip ON on purpose;
r18v42-base-one). The served one-GPU fallback today (Cstar161-single.json) runs v0.1.41, which has no such default.
