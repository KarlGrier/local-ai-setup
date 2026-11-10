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

## The pick (--prefer unsloth -> unsloth: set on the command line)

- group ['qwen4exp', '48', '512']: tie: quality decides - `Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00004.gguf`, `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` have equal expert bytes (46.84 GiB, spread 0.00 MiB <= the 0.1 GiB tolerance) and all fit (margin 26.55 GiB): Karl's rule cannot choose, and the list order is not a choice. Next: the KL / NLL step (commands step 3: pf_yardstick long40 of EACH tied file against one local reference via --kl-ref-config, + the text NLL); the lower KL wins; the served file is one of them (its config is configs/P028x.json)
  - tie broken by --prefer unsloth: Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00004.gguf (dropped: Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf); final: Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00004.gguf
  - **PROVISIONAL - the rule's pick by size would be `UD-Q4_K_XL`** (unsloth/Qwen3.8-Flash-Next-GGUF): about 72.64 GiB of experts by the size estimate, margin 0.74 GiB (TIGHT); its header must be read (a live `plan` fetches it; offline it was not) before the pick above stands. Also larger than the header-read pick: `UD-IQ4_XS` (~56.19 GiB), `UD-Q3_K_XL` (~52.28 GiB)
  - KL driver `gap-fn31b-kl.sh` (bash -n OK; arms {'X': 'UD-IQ3_XXS', 'R': 'UD-Q4_K_XL (local: /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL)'}; reference UD-Q4_K_XL (local: /home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL))

## Slot model calibration (the served file, F1-frame-pools.md's logged numbers)

- logged budget (3,526 x largest): room 8.745 GiB -> uniform 3,526, sized 4,583 (logged 3,526 / 4,583); pin 2500 -> 3,238 (logged 3,238)
- day1's room (fit model): room 8.751 GiB -> uniform 3,529, sized 4,587 (logged 3,526 / 4,583); pin 2500 -> 3,238 (logged 3,238)
- the 4060 Ti's 3,300 today = 6.2062 GiB (F1: 6.206 GiB)

## fn31b

- UD-IQ3_XXS (unsloth, listed), stock mode; RUNS WITH A PACK CONVERSION; experts 46.84 GiB in 73.38 GiB of room (margin 26.55)
- config `/home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun/B-stock/configs/fn31b.json`: --expert-cache 3,400 (expected 4,419 slots; auto would be 3,425 / 4,451), --expert-cache-device1 3288 (rule today-bytes: the next ranks that fit 6.206 GiB (today's 3,300 x Flash-Next's blobs = the measured-safe helper bytes) -> 3,288 experts, 6.206 GiB); expert-profile.bin: 24576 ranked pairs; HC types ['Q8_0'] -> STRATA_HC_Q8=1
- disk: 189.8 GB free - download 0.0 - pack 4.7 - reference pack 4.8 - splice 0.0 - drafter 1.0 = **179.3 GB** after (floor 100: OK)
- drafter fallback (no --mtp given): `MTP/mtp-Qwen3.8-Flash-Next-shared-BF16.gguf` (5.23 GB, BF16; here, verified) -> `/home/USER/ai-speed-testing/strata-compare/bringup/out/fn31b/mtp-rt`; the config carries --spec 7 --spec-min-p 0.5 --mtp to it and the drivers refuse until it exists. Steps: `nice -n 19 /home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B /home/USER/ai-speed-testing/strata-compare/work/qwen4-kit/mtp_from_gguf.py inspect /home/USER/ai-speed-testing/strata-compare/models/unsloth-v31/MTP/mtp-Qwen3.8-Flash-Next-shared-BF16.gguf`; `bash /home/USER/ai-speed-testing/strata-compare/work/r23/nogap-run.sh /home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun/B-stock/drafter-fn31b.log /home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B /home/USER/ai-speed-testing/strata-compare/work/qwen4-kit/mtp_from_gguf.py convert /home/USER/ai-speed-testing/strata-compare/models/unsloth-v31/MTP/mtp-Qwen3.8-Flash-Next-shared-BF16.gguf --out /home/USER/ai-speed-testing/strata-compare/bringup/out/fn31b/mtp-rt`; then no reference rt for a new model: CHECK-PLAN.md's acceptance check (results/qwen4-kit/mtp-fallback/, ~45 min with 8080 down) before trusting its speed numbers
- download (plan, rc 0): to transfer 0.0 GB: ~0 min at 100 MB/s (no cap; the guessed line rate --plan-line-mb; while an LDR run is live: 75 % of the measured line, 35 MB/s before a measurement); at once; paused only while a gap is open (measuring); free 189.8 GB -> 189.8 GB after (floor 100 GB: OK)
  - `/home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B /home/USER/ai-speed-testing/strata-compare/work/qwen4-kit/gentle_dl.py --tree /home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun/B-stock/listing/unsloth--Qwen3.8-Flash-Next-GGUF@d96201194f10.json --repo unsloth/Qwen3.8-Flash-Next-GGUF --commit d96201194f103c906994f283f504209dc8d2a10c --dest /home/USER/ai-speed-testing/strata-compare/models/unsloth-v31/UD-IQ3_XXS --rate 0 --window measure UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00004.gguf UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00002-of-00004.gguf UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00003-of-00004.gguf UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00004-of-00004.gguf`  (Karl 11-05: starts at once, pauses only while a gap is open (measuring) and resumes when it closes; no fixed cap - while an LDR run holds bench.lock it leaves 25 % of the measured line (35 MB/s before a measurement))
- pack (--compat-bf16; ~4.7 GB; not made yet): `bash /home/USER/ai-speed-testing/strata-compare/work/r23/nogap-run.sh /home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun/B-stock/pack-fn31b.log env PYTHONDONTWRITEBYTECODE=1 STRATA_GGUF_PY=/home/USER/ai-speed-testing/strata-compare/strata/third_party/llama.cpp/gguf-py /home/USER/ai-speed-testing/strata-compare/.venv/bin/python -I -B /home/USER/ai-speed-testing/strata-compare/strata-r22p028x/tools/iq_pack.py --gguf /home/USER/ai-speed-testing/strata-compare/models/unsloth-v31/UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00004.gguf --out /home/USER/ai-speed-testing/strata-compare/bringup/out/fn31b/pack --compat-bf16`
- driver exact: `/home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun/B-stock/drivers/gap-fn31b-exact.sh` (bash -n OK; .ready file: none)
- driver speed: `/home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun/B-stock/drivers/gap-fn31b-speed.sh` (bash -n OK; .ready file: none)
- params: `/home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/dayone-dryrun/B-stock/drivers/params-fn31b.json`; minutes {'e7': 4, 'smoke': 2, 'q': 7, 'qr': 12, 'pfy': 9, 'pfyr': 14, 'scr': 5, 'cmp': 10}

