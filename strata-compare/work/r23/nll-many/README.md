# work/r23/nll-many - text NLL at many positions for the KL gate (item 6)

Plan, numbers and the proposed bound: `results/r23/nll-many/PLAN.md`. Nothing here has run on the GPU.

## How it works

The batched prompt path in every build we have (P021n, P021m, P027, P028, P028x, P0210 and their twins) has two
debug hooks. `STRATA_PREFILL_DUMP_R` writes the final residual (hc x n_embd = 10,240 fp32) of every 64th prompt row.
`STRATA_PREFILL_DUMP_R_ALL` writes every row as BF16 (run_impl only; it declines the layer-major walk, and our configs
pin that walk off anyway). `score.py run` reads each long text once, cold, with pf_yardstick's settings and keeps
those rows. `score.py compare` then applies the model's head offline: the final hyper-connection mixer
(`output_hc_*`, gr_read's contract) and `output.weight` (Q6_K, read from the GGUF). That gives the full-vocabulary
distribution at every kept row, so it can score:

- the NLL of the text's own next token,
- the top-1 pick,
- the exact KL against the reference arm at the same row.

## Commands

```
P="nice -n 19 .venv/bin/python -I work/r23/nll-many/score.py"
$P selftest [--quick]                       # synthetic + mock-engine checks, no GPU (about a minute on one core)
$P run CONFIG OUT [--set long11] [--rows all:8] [--env K=V] [--kv fp16]      # GPU, inside a gap only
$P validate OUT                             # offline head vs the engine's own window rows (5 check prompts)
$P --threads 4 compare ROOT --ref ref --refs unfused,cpushare --cands A,B [--block 2048] [--block-scan 1024,2048,4096,8192,text] \
   [--rows-out rows.tsv] [--json res.json]  # dump dirs (offline head: 2.4 GB RAM; ~1 s per 128 rows per arm, 1 thread)
$P compare X --from-rows rows.tsv --stride 2 --cands ...    # re-analyse the stored table (every 16th row of an all:8 run)
$P compare DIR... --format pfy --cands ...  # pf_yardstick long40 / long80b dirs (= kernel_rule3's numbers, + bootstrap)
$P compare DIR --format logpos --ref base --refs R1,R2 --cands B    # STRATA_LOGPOS TSVs (DeepSeek teacher dirs)
```

`compare` prints, for each arm:

- the KL metrics in kernel_rule3's form (mean, p90, KL > 1, changed top-1) with their bounds,
- the NLL distance d = mean(NLL_arm - NLL_ref) with its 95% block-bootstrap CI and se,
- the per-position sd, the fraction of positions with |d| > 0.5, and the design effect.

For each candidate it also prints two verdicts:

- **rule3**: the 10-26 point rule.
- **proposed**: FAIL when d > 1.10 x max |d_R| + 1.645 se, UNDERPOWERED when se > `--se-cap` (0.01).

Exit code 1 means a candidate FAILs the proposed rule.

## Files

- `score.py`: the tool.
- `mock_engine.py`: the selftest's stand-in for `strata --serve`. It speaks the same protocol and writes the hooks'
  file layouts.
- `scratch/`: one-off analyses, kept for the record:
  - `rule3_repro.py`: kernel_rule3.py's own functions vs score.py on every stored long40 dir.
  - `explore_tf16.py`, `what_n_buys.py`: the round-16 noise structure.
  - `power_sim.py`: the rules' false-fail rate and power.
  - `head_smoke.py`, `chunk_time.py`, `kl32_check.py`: real-head load, timing, and float32 vs float64.
  - `past_table.py`: the past-case table.

## Tested offline (11-04)

- **Selftest PASS:**
  - BF16 rounding matches gr_parity.cpp bit for bit.
  - The Q6_K decoder matches a line-by-line transcription of ggml's loop on random blocks and on the real head's first
    64 rows.
  - The mixer matches gr_parity.cpp's reference (relative error 4e-7).
  - Rule rates:

    | candidate | rule3 fails | proposed rule fails |
    |---|---|---|
    | rounding-level (H0) | 35/200 | 0/200 |
    | 5 se worse | | 100/100 |

  - The dump pipeline gives exactly 0 for an identical arm.
  - The rows-table round trip reproduces the analysis.
  - `run` works against the mock engine in both row modes (rows, values, the validation pairing).
  - `run` reports a truncated dump.
- **kernel_rule3.py reproduced** to 1e-15 on every stored long40 dir: gaps 8, 12-17, plus int8.
- **Real head:** loads in 14 s on one core (3.3 GB RSS). float32 KL and NLL agree with float64 to 5e-8.
- **Not tested:** the real engine. That is `validate`'s job, as the first step of the gap.
