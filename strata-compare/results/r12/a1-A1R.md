## A1 on A1R: 69 requests, 180726 MTP-drafted positions of MTP windows (0 unpaired), 68 requests matched

### overlap sum min(p, q) vs observed acceptance (reached positions), per draft step
| group | step | positions | overlap | observed acceptance | target mass outside the draft vocabulary |
|---|---|---|---|---|---|
| LDR | 1 | 74068 | 0.8061 | 0.8064 (n 74068) | 0.0345 |
| LDR | 2 | 55462 | 0.8031 | 0.8218 (n 45997) | 0.0336 |
| LDR | 3 | 43602 | 0.7987 | 0.8269 (n 30797) | 0.0334 |
| decode | 1 | 3341 | 0.7983 | 0.7920 (n 3341) | 0.0306 |
| decode | 2 | 2430 | 0.7997 | 0.8119 (n 2015) | 0.0247 |
| decode | 3 | 1823 | 0.7803 | 0.8288 (n 1262) | 0.0294 |
| all | 1 | 77409 | 0.8057 | 0.8058 (n 77409) | 0.0343 |
| all | 2 | 57892 | 0.8030 | 0.8214 (n 48012) | 0.0332 |
| all | 3 | 45425 | 0.7980 | 0.8270 (n 32059) | 0.0333 |

### per request kind (all steps)
| kind | positions | overlap | acceptance | step 1 / 2 / 3 overlap |
|---|---|---|---|---|
| analysis | 47268 | 0.8030 | 0.8142 | 0.810 / 0.802 / 0.794 |
| correctness:arith | 91 | 0.8266 | 0.8312 | 0.870 / 0.839 / 0.768 |
| correctness:code | 266 | 0.7699 | 0.8000 | 0.758 / 0.766 / 0.794 |
| correctness:network | 255 | 0.9380 | 0.9289 | 0.945 / 0.931 / 0.936 |
| correctness:science | 215 | 0.7763 | 0.8022 | 0.769 / 0.771 / 0.794 |
| correctness:translate | 289 | 0.6663 | 0.6740 | 0.716 / 0.652 / 0.597 |
| followup | 14866 | 0.8160 | 0.8248 | 0.811 / 0.816 / 0.825 |
| longreason:code | 2757 | 0.7605 | 0.7636 | 0.757 / 0.770 / 0.754 |
| longreason:math | 3183 | 0.8265 | 0.8403 | 0.843 / 0.831 / 0.797 |
| queries | 1628 | 0.7919 | 0.8016 | 0.747 / 0.820 / 0.830 |
| speed:32k | 538 | 0.7935 | 0.8043 | 0.804 / 0.795 / 0.774 |
| synthesis | 93771 | 0.8031 | 0.8155 | 0.807 / 0.802 / 0.797 |
| toolcall | 659 | 0.8300 | 0.8530 | 0.850 / 0.835 / 0.801 |
| triage | 14940 | 0.7928 | 0.8070 | 0.789 / 0.797 / 0.795 |

### missing overlap split (tasks: 38; fit 19 tasks / 90349 positions, held-out 19 / 90377)
LDR: held-out overlap 0.8048 -> gap 0.1952; (i) target mass outside the draft vocabulary 0.0335 (17 % of the gap); (ii) corrections on held-out: one temperature 1.04 -> 0.8049 (+0.01 points), per step {1: 1.06, 2: 1.02, 3: 0.96} -> 0.8050 (+0.01), affine per step {1: (1.1, 0.1), 2: (1.04, 0.0), 3: (0.92, -0.1)} -> 0.8049 (+0.01); (iii) the rest 0.1615 (83 % of the gap)
all: held-out overlap 0.8034 -> gap 0.1966; (i) target mass outside the draft vocabulary 0.0338 (17 % of the gap); (ii) corrections on held-out: one temperature 1.04 -> 0.8035 (+0.01 points), per step {1: 1.06, 2: 1.02, 3: 0.96} -> 0.8036 (+0.02), affine per step {1: (1.04, 0.0), 2: (1.04, 0.0), 3: (0.92, -0.1)} -> 0.8035 (+0.01); (iii) the rest 0.1627 (83 % of the gap)
