# Basalt follow-up - the decision (rule fixed 11-02 before the results; FOLLOWUP-PLAN.md)

## The screen (client clock; per pass the geometric mean over 9 workloads)

| arm | decode | prompt |
|---|---|---|
| Basalt 0.2.0 stock (two-stage head) | 161.5 (158.5-164.4, 3 passes) | 2,430.3 (2,395.3-2,452.8, 3 passes) |
| Basalt exact head (BASALT_EXACT_HEAD=1) | 156.7 (151.9-159.4, 3 passes) | 2,431.6 (2,415.8-2,439.4, 3 passes) |
| P028x (x28h, 4060 Ti on) | 154.8 (154.6-155.3, 3 passes) | 2,102.2 (2,100.5-2,104.4, 3 passes) |
| P028x, 4060 Ti off (x28h-solo) | 134.5 (133.2-136.2, 3 passes) | 2,098.4 (2,095.7-2,100.7, 3 passes) |

## The arithmetic

- exact head, measured: -2.96 % decode vs stock (156.7 vs 161.5)
- hyper-connections in BF16, estimated: exact-head arm 3.03 tokens per verify window -> +0.313 ms/token central (+0.294 to +0.353, drafter 0.020 ms in the upper end)
- Basalt lossless: 149.4 tok/s (-3.5 % vs P028x)
- helper value on P028x, measured: 0.976 ms/token saved (+15.1 % for P028x; range 0.875 to 1.067 ms)
- **Basalt lossless + 4060 Ti: 174.9 tok/s = +13.0 % vs P028x 154.8** (range 164.9 to 181.8 = +6.2 to +17.6 %)

**Verdict (the rule): +8 % OR BETTER on the central value, but the range's low end is +6.2 %: reported as such - Karl decides.** Either way: revisit Basalt if it supports Qwen4 before Strata does.

