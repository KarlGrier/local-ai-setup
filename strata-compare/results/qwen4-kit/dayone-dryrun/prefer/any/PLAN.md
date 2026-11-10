# Day-one plan (2026-11-05 14:52, dayone.py 2026-11-05)

`dayone.py dryrun --out /home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun`

No GPU, no engine run, nothing downloaded or packed by `plan`. Each step below runs on its own (`dayone.py execute STEP --plan ...`), after Karl's go.

## Listing and candidates

- `unsloth/Qwen3.8-Flash-Next-GGUF` at commit `d96201194f103c906994f283f504209dc8d2a10c` (/home/USER/ai-speed-testing/strata-compare/work/qwen4-kit/unsloth-v31/dl/tree.json): 13 model quants, 14 side files

| quant | publisher | source | GB | header | verdict | experts GiB | fits | estimate (no header) |
|---|---|---|---|---|---|---|---|---|
| BF16 | unsloth | listed | 354.0 | none | - | - | - | 298.67 GiB, over (margin -225.29; from UD-IQ3_XXS) |
| Q8_0 | unsloth | listed | 188.2 | none | - | - | - | 144.25 GiB, over (margin -70.87; from UD-IQ3_XXS) |
| UD-Q6_K_XL | unsloth | listed | 169.2 | none | - | - | - | 126.5 GiB, over (margin -53.12; from UD-IQ3_XXS) |
| UD-Q5_K_XL | unsloth | listed | 158.3 | none | - | - | - | 116.37 GiB, over (margin -42.99; from UD-IQ3_XXS) |
| UD-Q4_K_XL | unsloth | listed | 111.3 | none | - | - | - | 72.64 GiB, fits (margin 0.74; from UD-IQ3_XXS) |
| UD-IQ4_XS | unsloth | listed | 93.7 | none | - | - | - | 56.19 GiB, fits (margin 17.19; from UD-IQ3_XXS) |
| UD-Q3_K_XL | unsloth | listed | 89.5 | none | - | - | - | 52.28 GiB, fits (margin 21.11; from UD-IQ3_XXS) |
| UD-IQ3_XXS | unsloth | listed | 83.6 | disk | RUNS WITH A PACK CONVERSION | 46.838 | True | - |
| IQ3_S | ista | local | 83.6 | disk | RUNS | 46.838 | True | - |
| UD-Q2_K_XL | unsloth | listed | 79.6 | none | - | - | - | 42.87 GiB, fits (margin 30.29; from UD-IQ2_XS) |
| UD-IQ2_XS | unsloth | listed | 75.8 | headers | RUNS WITH A PACK CONVERSION | 39.38 | True | - |
| UD-Q2_0 | unsloth | listed | 70.5 | none | - | - | - | 34.46 GiB, fits (margin 38.71; from UD-IQ2_XS) |
| UD-IQ1_M | unsloth | listed | 68.0 | none | - | - | - | 32.09 GiB, fits (margin 41.07; from UD-IQ2_XS) |
| UD-IQ1_S | unsloth | listed | 66.4 | none | - | - | - | 30.58 GiB, fits (margin 42.59; from UD-IQ2_XS) |

Pre-screen: room 73.17 GiB, the largest header-read fit 46.8384 GiB; headers to read before trusting the pick: UD-IQ4_XS, UD-Q3_K_XL, UD-Q4_K_XL (offline: not fetched)

## The pick (--prefer any -> any: set on the command line)

- group ['qwen4exp', '48', '512']: tie: quality decides - `Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00004.gguf`, `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` have equal expert bytes (46.84 GiB, spread 0.00 MiB <= the 0.1 GiB tolerance) and all fit (margin 26.55 GiB): Karl's rule cannot choose, and the list order is not a choice. Next: the KL / NLL step (commands step 3: pf_yardstick long40 of EACH tied file against one local reference via --kl-ref-config, + the text NLL); the lower KL wins; the served file is one of them (its config is configs/P028x.json)
  - --prefer any: QUALITY DECIDES (the KL driver runs every tied file against the reference); final: Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00004.gguf, Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
  - **PROVISIONAL - the rule's pick by size would be `UD-Q4_K_XL`** (unsloth/Qwen3.8-Flash-Next-GGUF): about 72.64 GiB of experts by the size estimate, margin 0.74 GiB (TIGHT); its header must be read (a live `plan` fetches it; offline it was not) before the pick above stands. Also larger than the header-read pick: `UD-IQ4_XS` (~56.19 GiB), `UD-Q3_K_XL` (~52.28 GiB)

