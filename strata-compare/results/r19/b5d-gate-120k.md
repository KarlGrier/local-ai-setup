| setting | decode after 120K, each request (run, rep, tok/s) | mean |
|---|---|---|
| STRATA_SPEC_PROB=1 | b5c-sp-a r0 140.5; b5c-sp-b r0 129.2; b5d-sp-a r0 127.9; b5d-sp-a r1 136.9; b5d-sp-b r0 133.0; b5d-sp-b r1 146.9 | 135.7 |
| + STRATA_COST_GATE (PR) | b5c-gate-a r0 123.8; b5c-gate-b r0 132.8; b5d-gate-a r0 129.1; b5d-gate-a r1 130.0; b5d-gate-b r0 129.1; b5d-gate-b r1 153.3 | 133.0 |

gate vs SPEC_PROB alone after 120K (b5c + b5d, n = 6 / 6): -2.0 %
