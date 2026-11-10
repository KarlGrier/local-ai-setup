# day1.py self-test (2026-11-04)

The test read headers only, offline, on 11 files from disk. Everything ran under `nice -n 19 taskset -c 31 timeout 120`
in about 6 s. There was no engine, no GPU, no build and no network. The command is in `stdout.txt` and the kit's
README; the full output is `report.md` / `report.json`. Per file there is `files/<file>.tensors.tsv` (every tensor
with its verdict) and `files/<file>.keys.txt`. The picks' configs, parameters and commands are in `day1/`; none was
installed in `configs/`.

## What came out

| file | what it is | verdict | experts | room | fit |
|---|---|---|---|---|---|
| ISTA IQ3_S (served) | Flash-Next | RUNS | 46.84 GiB | 73.81 | fits, all in the RAM arena |
| Unsloth UD-Q4_K_XL (HF cache) | Flash-Next | runs with `--compat-bf16` (Q8_0 hc / PLE value -> BF16) | 71.73 | 72.47 | **fits, margin 0.74 GiB (TIGHT)** |
| r12 splice3 | IQ3_S experts + UD-Q4 rest | runs with `--compat-bf16` | 46.84 | 72.47 | fits |
| r15 splice-q5 | UD-Q5_K_XL experts | RUNS | 91.61 | 73.81 | 17.8 GiB on the SSD |
| Signal AP-Q4_K_XL (HF cache) | Flash-Next fine-tune | runs with `--compat-bf16`; setup.py would refuse the name | 63.28 | 73.37 | fits |
| **GLM-5.3 UD-Q2_K_XL** (the refusal case) | other arch | **REFUSED** (see below) | 92.23 | 64.59 | 27.6 GiB over |
| NVFP4-GPTQ dense GGUF | experts live in a ready-made pack | REFUSED: no experts in the GGUF | - | - | - |
| SYNTH q4x768 (head-only, 10-27) | qwen4exp, 768 experts | RUNS | 74.71 | 73.52 | 1.2 GiB on the SSD |
| SYNTH q4flash300 (head-only) | arch `qwen4`, ~300B | REFUSED: architecture unknown to this tree | 127.50 | 66.90 | 60.6 GiB over |
| SYNTH q4a3b | qwen35moe | runs (own path); 90 Q8_0 GDN tensors marked CHECK | 18.12 | 76.21 | fits |
| SYNTH q4dense27 | dense, arch `qwen4` | REFUSED (arch; no experts) | - | - | - |

About the GLM refusal:
- Its expert layers are IQ2_XS gate/up with **IQ3_XXS down** (39 layers). IQ3_XXS is in no down kernel list
  (`STRATA_D_FMTS`, `iq_kernels.cu:851`), and the engine stops at load (`generate.cpp:4461`).
- This is the type-level reason behind setup's name refusal of UD-IQ3_XXS / UD-Q2_K_XL. A Qwen4 UD file with
  IQ3_XXS (or Q2_K / Q3_K) downs would be refused the same way.
- It is also refused by architecture (`glm5-next`).

## The picks (Karl's rule)

- **Flash-Next group:** the pick is UD-Q4_K_XL, the largest that fits and runs. The splice-q5 file (17.8 GiB over)
  was skipped.
  - The margin is 0.74 GiB, so the report flags it TIGHT: the chat-cache cap (2 GiB in the fit; P028x serves 12 GiB)
    decides it.
- **q4x768:** nothing fits, so the pick is the smallest runnable one, with 1.2 GiB on the SSD.
- **GLM / qwen4 / dense groups:** nothing runs, and the reason is given for each.

## Model checks

- **The 5080's room for Flash-Next:** 8.75 GiB, the same as measured (`logs/engine-P028x.log`: 4,585 slots, 8.75 GiB).
- **The decode model (UPGRADE-ESTIMATE.md sections 8-9) on its two measured points:**

  | file | model | measured | difference |
  |---|---|---|---|
  | Flash-Next | 145 tok/s | 158.9 engine clock | −9 % |
  | splice-q5 | 30 tok/s | 37.3 | −21 % |

  It reads low on both. Use it to compare quants and layouts.

## Helper tests

- `retok-identity/`: math, code and p2000 re-tokenized with Flash-Next's own tokenizer. All three give identical ids.
- `retok-glm-tokenizer/`: the same files encoded with GLM's tokenizer:
  - the lengths change: 137 -> 158 and 2000 -> 1903 tokens;
  - the warning fires: `<|im_start|>` / `<|im_end|>` are not in that vocabulary.
- `pfy-check-flash-next.txt`: all 40 long40 cuts lie inside their texts.
- `kr3-wrapper-gap16.txt`: `day1.py kr3` on gap 16's yardstick dirs is byte-identical to `kernel_rule3.py` run
  directly. The x28h verdicts pass.

## Not covered

- No real Qwen4 file exists yet. The synthetic heads are 10-27 guesses (`bringup/synth_header.py`).
- Whether F32 tensors are BF16-valued only shows at pack time.
- The qwen35moe config follows the qwen4exp layout and says so (`_day1.warning`).
