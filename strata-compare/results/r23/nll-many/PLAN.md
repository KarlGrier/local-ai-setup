# Item 6: the NLL check at many positions (next KL-gate revision), plan for Karl (11-04)

Tool: `work/r23/nll-many/score.py` (+ README). Written and tested offline only: no engine run, no build, no GPU.
Past-case outputs: `past-cases.txt` and `past-*.json` in this folder.

## 1. Getting logits at many positions: the options and their GPU cost

The NLL check today (kernel_rule3.py, Karl 10-26/10-30) scores one position per pf_yardstick long40 prompt: the
decode window's row after each cut, 36 positions. The KL rows are those 36 plus 4 at text ends.

The rounding references are gap 8's, against ref = P021n (`configs/r21n1.json`):

- **unfused**: `r21n1-unfused.json`, STRATA_PF_FUSED=0.
- **cpushare**: `r21n1.json` + STRATA_PREFILL_CPU_SHARE=0.4.

| option | what it scores | positions | GPU per arm | engine code |
|---|---|---|---|---|
| today: pf_yardstick long40 | the window row after each cut | 36 | ~8.5 min (570K prompt tokens) | none |
| more cuts per long prompt, cold | the same | N | ~0.9 ms per prompt token per cut: 2,000 cuts at long40's mix = 32M tokens = **~8 h** | none |
| more cuts, reusing the prefix (prompt / chat cache) | the same | N | cheap | not usable: the yardstick forces `--prompt-cache 0` (every stored run: "0 reused"), and reuse would read each cut's tail in short chunks, which is not a cold long prompt's arithmetic |
| "teacher-forced over the quant-quality set" (`tools/quant_quality.py run`, data/quant_quality/v1: code / docs / English / other languages / agent, 5 x 1,000 tokens, STRATA_LOGPOS) | decode windows only | ~5,000 | minutes | none, but **blind to the prompt kernels** (see below) |
| `force=N` teacher forcing after each cut | window rows after a batched cut | 36 x N | ~+1 min for N = 256 | none, but limited (see below) |
| **recommended:** `STRATA_PREFILL_DUMP_R_ALL` / `_DUMP_R` + the head applied offline | the batched prompt path's own rows, where the prompt kernels act | every 8th row of 11 texts: **~31,400** (every 64th: ~3,900; every row: ~251,000) | **~6 min** (one cold read of each text, 262K tokens + 5 short check prompts) | **none**: the hook is in every build since P021n; score.py applies the head |
| a new engine scoring mode (the head on every prompt row inside the engine) | same as recommended | same | same | C++ + a build, and only the new build would have it (P021n / P021m / P028x would need rebuilt twins) |

Notes on the table:

- **The quant-quality set.** It reads every token through the windows, so PF_FUSED, the CPU share and v2 never run (pf_yardstick.py's docstring says the same). Both rounding references would be bit-identical to ref, which makes the bound 0. It is fine for a decode-path check, and `--format logpos` reads its output.
- **`force=N` teacher forcing.** It exists only in the measurement twins (021mt / 028xm / 0210m ...), not in P021n, the gates' reference build. It writes NLL and top-1 only (FORCE lines, no distributions), so there is no KL. And forced tokens after one cut are strongly correlated: in round 16, 1,536 of them were worth about 140 independent positions.
- **A new engine scoring mode.** It is only the fallback, if `validate` fails.

So no new engine mode is needed, and I created no worktree (strata-r23score). Every arm of the gap can run on the
exact binaries of the past cases.

The offline head is checked against the engine inside each arm. The `run` set includes 5 short prompts whose last
token sits at a dumped position (2048, 4096, 8192, 12288 and pp4k's 2048). `score.py validate` compares the engine's
own window logits there with the offline head on the full read's row:

- **Pass:** mean KL <= 0.05, each <= 0.5 (rounding between the batched and window paths is ~0.01-0.02).
- **Fail:** a wrong head would give KL >> 1.

Offline, the head's parts are tested against transcriptions of ggml's Q6_K loop and gr_parity.cpp's reference. The
real head loads in 14 s (2.4 GB).

## 2. The script

`score.py run` uses one engine with pf_yardstick's engine and settings: the 5080 alone, experts on the CPU, FP16 K/V,
no adaptation, no PCIe share, CPU share 0 unless `--env`. It sends one GEN request per text: long40's 8 texts plus
long80b's 3 (pp32k, tf-long96k, pp8k), each up to 32,768 tokens. After each request it moves the dump to the arm's
folder and checks the rows (positions 0, K, 2K ... below n - 1). A dump that lost rows is reported, which the mock
test covers.

`score.py compare` scores every kept row from position 1,024 on (kernel_rule2/3 judge prompts > 1,000 tokens), each
as the text's own next token. It reports:

- **Paired NLL difference:** the per-position difference against the reference arm.
- **Distance:** d = mean(NLL_X - NLL_ref).
- **CI:** a 95% CI and se from a block bootstrap. Blocks are 2,048 tokens inside a text, resampled with replacement,
  the same blocks for every arm, 10,000 replicates.
- **KL metrics:** kernel_rule2/3's mean, p90 (numpy linear), KL > 1 and changed top-1, on the same positions, with
  exact full-vocabulary KL.

`--block-scan` and `--from-rows --stride` measure how se depends on block size and row spacing, from the gap's own
data.

On the stored long40 dirs, `--format pfy` reproduces kernel_rule3.py exactly: every KL metric and the NLL distance on
gaps 8 and 12-17 and the int8 arms, within 1e-15.

## 3. The proposed bound

The 10-26 point rule (d_cand <= 1.10 x max |d_R1|, |d_R2|) has a coin-flip problem that more positions do not cure. At
any N, the references' distances and the candidate's distance are noise of the same size. So a candidate that is
just one more rounding variant fails about 15% of the time: analytically 0.5 x (1 - 0.70); 35 of 200 in the
selftest's simulation. DeepSeek B (section 4) is such a case.

**Proposal (NLL check, many positions):**

1. **Positions:** every 8th batched prompt row from 1,024 on, over the 11 long texts (~31,400 positions, ~130 blocks).
2. **Pass when** d_cand <= 1.10 x max(|d_R1|, |d_R2|) + 1.645 x se(d_cand). This is Karl's spread bound plus a
   one-sided 95% noise margin on the candidate's own distance, with se from the block bootstrap.
3. **Valid only when** se(d_cand) <= 0.01 nats. A loss 5 se beyond the bound (0.05 nats/token, ~5% perplexity, below
   a quant step: Q4 vs IQ3_S on long texts was 0.08-0.25) then fails ~99% of the time. Otherwise the verdict is
   UNDERPOWERED, and the fix is more text, not a decision.

Simulation (heavy-tailed t3 noise + a block effect; `scratch/power_sim.py`, 150 trials a row; the candidate's true
shift vs the reference build, references unshifted):

| true shift | point rule fails | proposed rule fails |
|---|---|---|
| 0 (one more rounding variant) | 15% | 0% (the references' spread adds margin; <= 5% by construction) |
| 2 se | 72% | 25% |
| 3 se | 95% | 58% |
| 4 se | 99% | 83% |
| 5 se | 100% | 99% |

Alternatives, if Karl prefers:

- Fail only when the bootstrap's 5th percentile of (d - bound) > 0. This is more conservative: 86% at 5 se.
- Add a fixed tolerance under the spread bound (`--floor`).

The KL checks stay as they are, on the same positions. One note: the count checks share the coin-flip problem. DeepSeek
B's changed top-1 was 38 vs the bound 37.4, with a Poisson sd of about 6, so the same margin could be given to the
counts later. That is Karl's call and is not in this proposal.

**What N buys.** Model: round 16's in-context long-text data on Qwen (4 rounding-level arms, 9,216 positions): per-position sd 1.16
nats and a region effect of ~0.11 nats per 512 tokens. The measured 36-row se was 0.05-0.39.

| design | positions | se of d (predicted) | loss caught ~99% (5 se) |
|---|---|---|---|
| long40 cut rows (today) | 36 | 0.15 median (measured, 0.05-0.39) | ~0.75 nats |
| every 64th row | 3,925 | 0.019-0.023 | ~0.10 |
| every 16th | 15,700 | 0.010-0.016 | ~0.06 |
| **every 8th** | **31,400** | **0.008-0.012** | **~0.05** |
| every 4th | 62,800 | 0.007-0.014 | 0.04-0.07 |
| every row | 251,000 | 0.005-0.014 | 0.03-0.07 |

The range in the se column spans two assumptions: 512-token regions independent, or one shared effect per 2,048-token
block. Past every 8th row, the region effect dominates: more text buys power, more rows do not. If the gap measures
se > 0.01, read the ≥64K texts to 64K (`--max-len 65536`, ~+40% text, se x ~0.85) or add texts.

DeepSeek's teacher-forced positions are calmer: per-position sd 0.25-0.29, se 0.003-0.006 at 2,040 positions.

## 4. What it would have said about the past cases (stored data only)

| case | positions | d [95% CI] | se | rule3 | proposed |
|---|---|---|---|---|---|
| P021m's served v2 (gap 8 `v2`; the 10-30 FAIL) | 36 | +0.143 [-0.10, +0.43] | 0.133 | FAIL (bound 0.086) | UNDERPOWERED (S = +0.4 se) |
| v0.2.8 port without switches (gap 15 `r28h`; gap 12 `r27a` and gap 14 `r27h-noboth` have the same rows) | 36 | +0.118 [-0.13, +0.46] | 0.153 | FAIL | UNDERPOWERED (+0.2 se) |
| gap 14 `r27h-nofork` | 36 | +0.144 [-0.17, +0.59] | 0.202 | FAIL | UNDERPOWERED |
| gap 9 `pcie` (adopted 10-23 under kernel_rule2, which had no NLL check) | 36 | +0.172 [-0.06, +0.48] | 0.140 | FAIL | UNDERPOWERED |
| P028x `x28h` = `x28h-nov2` = `r27h-nov2` = gap 17 `p210` / `p210hcr` (same rows) | 36 | -0.024 [-0.13, +0.08] | 0.053 | PASS | UNDERPOWERED |
| int8 IMMA, gap 8 + gap 9 pooled | 116 | +0.227 [+0.08, +0.40] (refs +0.200 / +0.296: refi8 itself sits low) | 0.083 | PASS (bound 0.326) | UNDERPOWERED; KL top-1 FAIL (16 vs 12.1) |
| **DeepSeek B vs A (11-03)** | 2,040 (8 segments) | +0.0070 [-0.004, +0.019] | 0.006 (0.0056-0.0077 over block sizes) | FAIL (bound 0.0037) | **PASS** (S = +0.0033 = +0.6 se, margin 0.0097) |
| DeepSeek stored gates: v0.2.6 vs v0.2.4, final vs stock, #343 port (+0.0048 vs 0.0049: S -0.1 se), IQ_Q8K w8 / w16, prompt skip, 5 vs 6 experts | 2,040 / 16,376 | | 0.002-0.008 | PASS | PASS (no verdict change; 5 vs 6 still fails its KL checks) |

At 36 positions, every Qwen verdict is noise either way. Both 10-30 FAILs (+0.143, +0.118) have 95% CIs that
include 0 and P028x's -0.024. The new data is needed to say anything about them; that is the gap below.

The full outputs are in `past-cases.txt`, including the KL metrics and the block scans for DeepSeek.

## 5. The gap (for Karl's OK; not started)

The setup is pf_yardstick's: the 5080 alone, 8080 down under port_gap4 begin/end like gaps 8-17, holding
tmp/gpu-test.lock, and starting the engines with `8>&- 9>&-`. A kernel check runs after each arm. Each arm runs:

```
score.py run CONFIG results/r23/nll-many/gap/ARM --set long11 --rows all:8 [--env ...]
```

| # | arm | config | why | GPU |
|---|---|---|---|---|
| 1 | ref | `configs/r21n1.json` (engine-r22p021n, P021n, v2 off) | the gates' reference build since gap 8 | ~6 min |
| 2 | ref2 | the same again | the dump path is deterministic (pf_yardstick ref = ref2 bit for bit): d must be exactly 0 | ~6 min |
| 3 | unfused | `configs/r21n1-unfused.json` (STRATA_PF_FUSED=0) | rounding reference R1 | ~6 min |
| 4 | cpushare | `configs/r21n1.json --env STRATA_PREFILL_CPU_SHARE=0.4` | rounding reference R2 | ~6 min |
| 5 | v2 | `configs/r21n1-v2.json` | P021m's served v2 kernels (the 10-30 FAIL) | ~6 min |
| 6 | x28h | `configs/x28h.json` (engine-r22p028x, as served: fork + v2) | P028x | ~6 min |
| 7 | x28h-nov2 | `configs/x28h-nov2.json` | v2 off on P028x; gap 16 found it bit-identical to x28h, so d must be exactly 0 | ~6 min |
| 8 | r28h | `configs/r28h.json` (engine-r22p028) | the v0.2.8 port without switches (the other 10-30 FAIL) | ~6 min |
| opt | x28h-unfused, x28h-cpushare | `x28h.json --env STRATA_PF_FUSED=0` / `--env STRATA_PREFILL_CPU_SHARE=0.4` | P028x's own rounding references, so later gates can use the served build as the reference | +12 min |

**Total:** ~48 GPU minutes (8 arms; ~60 with 8080 down, begin / end and kernel checks included). Add +12 for the
optional pair.

Per-arm cost: 291K prompt tokens at the yardstick's ~1,120 tok/s (gap 8's logs), ~1 min engine start/stop, and ~20 s
of dump handling.

Memory and disk:

- **RAM:** as pf_yardstick, plus ~1.4 GB for the driver (a 32K read's R_ALL file is 0.67 GB; it is deleted after
  subsampling).
- **Disk:** ~0.67 GB an arm, ~5.4 GB in all, out of 148 GB free.

After the GPU part (CPU only, off any timed run, nice 19):

1. **Validate:** `score.py validate` on every arm, ~20 s each.
   - **If ref does not AGREE:** stop. Nothing is judged, and the fallback is the engine-side mode (a build, with your OK).
2. **Compare** (~10 min with 4 threads; ~35 min on 1):

   ```
   score.py --threads 4 compare results/r23/nll-many/gap --ref ref --refs unfused,cpushare \
       --cands ref2,v2,x28h,x28h-nov2,r28h --block-scan 1024,2048,4096,8192,text \
       --rows-out results/r23/nll-many/gap/rows.tsv --json results/r23/nll-many/gap/result.json
   ```

3. **What N buys, measured:** `--from-rows ... --stride 2 / 8` (every 16th / 64th row) gives the se-vs-N curve.
4. **Report** to Karl:
   - the measured se and the bound;
   - the past cases at ~31K positions: v2, r28h, P028x;
   - a recommendation to adopt the rule, or to extend the texts if se > 0.01.

Timing: as decided 10-31, the scoring gap runs after item 7's parts, on a free night, and Karl is told before it starts.

## 6. Notes

- The 36-row data shows the noise directly. At the first token after a long prompt, rounding-level arms differ by
  0.7-1.8 nats sd per position, and 25-33% of positions move by more than 0.5 nats. This is the copy-token chaos seen
  in rounds 3 and 16.
- The reference arm's own noise enters every distance. In the int8 case all three arms sit 0.2-0.3 above refi8. At
  many positions this shrinks with se.
- KL means at the cut rows are high: 0.16-0.40, even for the references. The batched rows' KL will be smaller and
  steadier. The gap shows both.
