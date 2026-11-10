# dayone.py dry run on Flash-Next (11-05)

`work/qwen4-kit/dayone.py dryrun` ran every step that needs no GPU, with Qwen3.8-Flash-Next as the stand-in. It ran
offline except for one HF API listing check (below). Nothing was downloaded, packed, installed or posted. No engine or
gap component ran, and no `.ready` file was written. Scratch went to `work/qwen4-kit/scratch-d/` only.

## Inputs

| input | what |
|---|---|
| repo | `unsloth/Qwen3.8-Flash-Next-GGUF`, pinned at `d9620119`, from the saved tree (`unsloth-v31/dl/tree.json`) |
| headers | the saved headers in `unsloth-v31/headers/` |
| local candidate | our ISTA IQ3_S (`models/ISTA-GSQ-RCO/IQ3_S`) |
| download destination | `models/unsloth-v31/` (UD-IQ3_XXS and the BF16 MTP file are already there and verified) |
| KL reference | the HF cache's UD-Q4_K_XL, as `gap-ud31.sh` uses |
| engine | the served tree / engine (`strata-r22p028x`, `engine-r22p028x`), standing in for the release's |

## Results

| step | result |
|---|---|
| listing | 13 model quants; 14 side files (MTP, engram, mmproj, imatrix). A live API listing at the pin gave the saved tree exactly: 77 files, the same sizes and oids. `main` is still the pin (`live-listing-check.txt`). |
| headers | Reused for UD-IQ3_XXS (on disk, every SHA256SUMS line matches the pins) and UD-IQ2_XS (saved headers). The range-request fetch (`fetch_model.fetch_head`) ran on the local UD-IQ3_XXS copy, and all 4 headers came out byte-identical to the saved ones. |
| day1 check | Both v3.1 files are `RUNS WITH A PACK CONVERSION` (`--compat-bf16`); ours is `RUNS`. The room is 73.4 GiB. |
| pre-screen | 10 quants have no header. Their size estimates put **UD-Q4_K_XL** as the rule's pick, *provisionally*: about 72.6 GiB by estimate (REPORT: 71.7 GiB), margin about 0.7 GiB, TIGHT. Offline, its header (and UD-IQ4_XS's and UD-Q3_K_XL's) was not read, so the plan marks the pick PROVISIONAL. |
| pick among the read headers | Tie: UD-IQ3_XXS = ISTA IQ3_S, 46.84 GiB of experts each. `--prefer` gives: auto -> any (no v3.1 quality result yet) -> both, quality decides; ista -> ours, which is the served file, so nothing new; unsloth -> UD-IQ3_XXS (`prefer/variants.json`). |
| disk | 192.3 GB free. Pick A or B: 182.8 / 181.7 GB left after (OK). The provisional UD-Q4_K_XL would leave **81.0 GB, under the 100 GB floor** (`provisional-UD-Q4_K_XL-download-plan.txt`, rc 3). |
| download | The kit's `gentle_dl.py --plan`: 0 GB to transfer (already verified). Karl's 11-05 default is `--window measure`: it starts at once and pauses only while a gap is open (lockpid non-empty), resuming when it closes. There is no fixed cap; while an LDR run holds `run/bench.lock` (read from /proc/locks) it leaves 25 % of its own measured line rate, or caps at 35 MB/s before a measurement. Checksums, pinning, page-cache dropping and the 100 GB floor are kept. `gentle_dl.py --selftest` 10/10. |
| pack | iq_pack `--compat-bf16` for UD-IQ3_XXS and for R, run under `nogap-run.sh`. Printed only. |
| slot model | On the served file it reproduces F1's logged numbers exactly: 3,526 uniform / **4,583** sized; pin 2500 -> **3,238**; the 4060 Ti's 3,300 = 6.206 GiB. day1's room model is 3 uniform slots high (8.751 vs 8.745 GiB), so the 64 MiB margin covers it. |
| configs | A (swap) = `x28h` + three paths + `--expert-cache 3400` (expected 4,419 slots) + `--expert-cache-device1 3300` + `STRATA_HC_Q8=1`. That is gap-ud31's U form. B (stock) = day1's stock config + 3400 / **3288** (today's 6.21 GiB) + HC_Q8 + the drafter converted from Unsloth's shared-BF16 MTP. R = `--resident-budget-gib 52` (RAM tier − 5, as ud31-R; Karl 11-05). Every KL arm gets a memory wait before it starts (R needs 70 GiB, X / P 64.8) and a watch while it runs: MemAvailable under 13 GiB, engine VmSwap > 0 or +4 MiB of swap-ins/outs stops its engine by PID and records 'aborted: memory', so it never swaps. |
| checks | Both cfgchecks PASS, including `--quality-only` on R. The lossless rule (a read-only mirror of patchtest's) PASSES on all four configs. Both predls PASS. |
| drivers | A: exact / kl (dump: P, X, R) / speed. B: exact / kl (pfy: X, R) / speed. All 6 pass `bash -n`; none has a `.ready` file. |

The rule selftests pass: `q4_rules.py selftest` 12/12, `dayone.py selftest` 17/17 (sha256: dayone.py f09e00e0fce7,
q4_rules.py 71314a18152f, gentle_dl.py 3b6d29505054).

## Layout

```
A-swap/  B-stock/      PLAN.md + plan.json, CHECKS.txt, configs/, drivers/ (gap-*.sh + params-*.json), day1check*/,
                       listing/, execute-*.txt (what `dayone.py execute download|pack|drafter --plan` would run)
prefer/                the pick under --prefer auto | ista | unsloth | any (pick-only plans)
```

The dry-run drivers are for the stand-in only. Do not add them to the gap series: A duplicates `gap-ud31.sh`.
