# Gap 19: stock v0.2.10, the GDN prompt paths and PF_HC_REGION (written 11-04, not run)

Karl 11-04: "Run stock v0.2.10 on the same KL check with the two GDN paths on vs. off, and add the HC region switch on
vs. off (upstream says same bits; ours changed greedy output). If stock shows the same failure: it's upstream's ... If
stock is fine: it comes from our port; record which patches interact, for the next port."

This gap is a diagnostic. **Nothing switches**, and nothing is built: it reuses `engine-v0210stock` (c8fe72abe45a), which
gap 17 built from the detached worktree `strata-v0210stock` at v0.2.10.

| file | what it is |
|---|---|
| `work/r22/gap19.sh run` | the gap (without `run` it only prints its header) |
| `work/r22/g19_rules.py` | the rules, fixed before the gap (its docstring) |
| `configs/s0210-h-gdn.json`, `-gdntc`, `-gdncv`, `-hcr` | the stock arms. Each is `s0210-h` plus exactly the environment difference its port arm had against `P0210x-h`; `cfgcheck` checks this before the gap opens. Made by `work/r22/scratch-g19/make_configs19.py` |
| `results/r22/gap19/PATCH-OVERLAP.md` | our 28 commits next to these paths: the suspects if the answer is OURS |
| `results/r22/gap19/` | the output: `summary.txt`, `gates.txt`, `kl2.txt`, `kl3.txt`, `pfy/`, `decision.txt` |

Checks done: `bash -n`, `py_compile`, `cfgcheck`, and `hcrdiag` on gap 17's logs. The rules were also run on a simulated
gap in `scratch-g19/sim`, with gap 17's port dirs standing in for stock. Only harmless stand-in processes (bash, sleep)
were started, to test the environment watcher. No GPU, no engine.

## Stock's defaults (read in strata-v0210stock)

- **The engine** runs both GDN paths **off** unless they are set:
  - `STRATA_GDN_TC` is opt-in.
  - `STRATA_GDN_CONVL2` is 0 on CUDA. `arch_defaults.cpp` sets it only on AMD, "not bitwise on CUDA 13.3 sm_120
    (#1522)".
- **Stock's `serve/server.py`** turns them **on as served** (`gdn_stack_env`, 0.2.9's QUAL-GDN). On Linux, for Qwen3.8 on
  CUDA, it sets `STRATA_GDN_TC=1` and `STRATA_GDN_CONVL2=2` with setdefault.
- **pf_yardstick and exact7 start the engine directly, without server.py.** An arm that left them unset would therefore
  run them OFF. So the "on" arms set server.py's values explicitly, as gap 17's `P0210x-h-gdn` did. "On by default" only
  holds through the server.
- **`STRATA_PF_HC_REGION`** is opt-in in the engine, and server.py does not set it.
- **`STRATA_PREFILL_V2` is ours**, and stock has no read site for it. The stock HC pair is therefore the release's prompt
  path with the HC region on vs off. The variable that differs is the same one as in the port's pair.

## Steps and time (8080 down; plus the wait for the running research question at `port_gap4.sh begin`)

The times come from gap 17: pf_yardstick 8.5 min, an exact7 set 3.3 min.

| step | what | min |
|---|---|---|
| 0 | before the gap (no GPU): no other gap open; earlier gap 19 outputs moved to `prev-*`; `cfgcheck`; the stock engine is gap 17's build (SHA, SOURCE, the worktree at v0.2.10 and clean); gap 8's references and gap 17's port arms linked into `pfy/`; the kernel watcher runs | 0 |
| 1 | pf_yardstick long40 on `s0210-h` (both paths off) and `s0210-h-gdn` (TC=1 + CONVL2=2) | ~17 |
| 2 | gap 17's two KL rules (`kernel_rule2` + `kernel_rule3` with the NLL check, gap 8's ref and rounding references), with the port's gap 17 dirs scored in the same call | <1 |
| 3 | exact7 at pin 2500: stock off (`g19-s210`, against gap 17's `g17-s210`: the cross-gap repeat), then stock HC on (`g19-s210hcr`) against it | ~7 |
| 3b | only with `G19_HCR_SHARE0=1`: the same pair with `STRATA_PREFILL_CPU_SHARE=0` (the placement check, below) | +7 |
| 4 | optional, each only if it ends before the deadline (45 min after the gap opens, `G19_MAX_MIN`): GDN_TC alone, GDN_CONVL2 alone (pf_yardstick + KL), then pf_yardstick on `s0210-h-hcr` (bitwise against off) | 0-27 |
| 5 | rules -> `decision.txt`; P028x back (`port_gap4.sh end`) and a kernel check | ~2 |

- **Base only:** about 27 min with 8080 down (~25 min of GPU).
- **With the optional steps as the deadline allows:** about 43 min. Both GDN paths alone fit; the HC yardstick run does
  not.
- **With `G19_HCR_SHARE0=1`:** about 41 min, but only one GDN path alone (TC) fits.

**Every engine's environment is checked as it starts** (`g19_rules.py envcli`). It finds the engine by `/proc/PID/exe`
in the step's own process tree, never by a command-line pattern, and checks:
- the config's env exactly (pf_yardstick's fixed env over it; ENVX for 3b);
- no other `STRATA_*` variable (the script unsets stray ones at start);
- `STRATA_ROUTE_TAIL_SKIP=0` and 2 GPUs;
- the harness's arguments: pin 2500 for exact7; `--expert-cache 1`, `--pcie-frac 0` and `--kv fp16` for pf_yardstick.

An engine that fails the check is stopped by its PID before it measures, and the arm is void. Children run with
`8>&- 9>&-`. A kernel-check failure stops new steps and leaves the gap **open** (8080 down, exit 3: Karl decides). If
`port_gap4.sh end` fails, the script exits 4.

## The verdicts (`decision.txt`)

Each item gets one of three verdicts: **UPSTREAM** if stock fails the same gate the port failed, **OURS** if stock passes
where the port failed, and **UNCLEAR** otherwise. UNCLEAR includes: stock-off fails the KL rule itself, an env check
failed, an arm is incomplete, the two KL rules disagree on stock, or the exact7 slots differ.

- **(0) The GDN stack; (0t) / (0v) each path alone, if run.**
  - The table shows KL mean, p90, KL > 1 rows, top-1, changed top-1 and NLL, stock beside port.
  - It also gives the same-build distance (on against off).
  - Bitwise rows show whether stock's arm and the port's arm are identical, of 40.
- **(3) PF_HC_REGION.**
  - stock on vs off, n/7, at MATCHED slots, with the start line present in every ON item.
  - The mechanism table for both pairs: borrowed slots, the prompt's CPU experts and share, the resident count and the
    chunk, per item.

**What gap 17's logs already say about (3).** The port's 4 differing items are exactly the 136-token prompts that ran
with the prompt CPU share (0.4). The HC region cut their loan from 260 to 252 slots, and their CPU-expert count moved
(3510 -> 3514, 3447 -> 3456). The 3 long prompts (share 0) stayed identical, even where the chunk size moved
(14336 -> 16384).

So the bits seem to change through placement, not through the HC kernels. None of our commits touches that chain, so
**UPSTREAM is the expected answer**: upstream's "same bits" holds for the kernels at a fixed placement. `G19_HCR_SHARE0=1`
confirms it in the same gap: 7/7 with the share off. It costs ~7 min and leaves room for only one GDN path alone.

**What follows:**
- **OURS:** the suspects are in `PATCH-OVERLAP.md`. The two quickest splits are `P0210x-h-off` + GDN (does the build or
  our switches cause it?) and `P0210x-h-nov2` + GDN, one pf_yardstick each in a later gap.
- **UPSTREAM:** it goes on the upstream list. Karl decides what is posted.
