# r23 gaps: NLL many-positions, decode items part a, part b (written 11-04, not run)

Karl queued these on 11-04, in this order, one gap between each pair of the remaining 7d questions: NLL many-positions,
then decode items part a, then decode items part b. `work/r23/gap-series.sh` starts them. P028x stays served, and nothing
switches until item 7 is done.

| file | what it is |
|---|---|
| `work/r23/gap-nll.sh` | gap 1: the NLL check at many positions (`results/r23/nll-many/PLAN.md` section 5) |
| `work/r23/nll_rules.py` | its rules, written before the gap: the bound as PLAN.md proposes, validation, adoption |
| `work/r23/gap-decode-a.sh` | gap 2: build, tests, exact7, pf_yardstick, timing arms, and the two-card timing pass |
| `work/r23/gap-decode-b.sh` | gap 3: the 9-workload screen and Basalt's bp90 fixtures |
| `work/r23/decode_rules.py` | the rules for both decode gaps, written before them: EXACT, PASS and GAIN (`GATE-PLAN.md` section 6) |

Each driver runs as `bash <driver>` with no arguments. Every path in them is absolute, because the series runner runs a
snapshot copy from `results/r23/run-copies/`. No driver has a `.ready` file yet; the series waits for one per driver.

## Common to all three

**Refusals.** A driver refuses with exit 1 and touches nothing (8080 untouched) when any of these holds:
- `tmp/gpu-test.lock` is held by anyone (`flock -n -x` fails), or `tmp/port-gap.lockpid` is alive.
- An engine process (exact names: strata, strata-host, strata-vision, strata-dsv41, llama-server, ollama) or an NVIDIA
  compute process is not under the server listening on 8080.
- That server's engine is not P028x (`engine-r22p028x`, sha `f4c4f654fb24`). Its strata-vision helper is allowed.
- Something listens on 8081 (a test server).
- nvidia-smi does not answer, or the kernel-log watcher is not running.
- Part b only: the conditions listed under gap 3.

Refusals are logged to `results/r23/nll-many/gap-nll-starts.log` or `results/r23/decode-timing/gap-decode-starts.log`.

**The gap itself:**
- **Open and close.** `port_gap4.sh begin` waits for the running question, holds the queue, takes the test lock and
  stops 8080. The driver then waits up to 120 s for the 8080 engines to exit and MemAvailable to reach 40 GB.
  `port_gap4.sh end` waits for memory, starts P028x, and checks its SHA and the parking policy.
- **Engine environment.** Every engine's environment is checked as it starts. The engine is found by `/proc/PID/exe` in
  the step's own process tree, or by `g17_rules.py envcheck` inside `with_server.sh`. The check covers:
  - the config's env exactly;
  - `STRATA_ROUTE_TAIL_SKIP=0`;
  - the GPU count;
  - no other `STRATA_*` (each driver unsets every `STRATA_*` except `STRATA_MON_GPU` at start);
  - the harness's args.

  An engine that does not match is stopped by its PID, and the arm is void.
- **Process handling.**
  - Children get `8>&- 9>&-`, and the driver closes any inherited fd 8 or 9 at start.
  - No `pgrep -f` or `pkill` pattern is used; processes are found by PID, pid file or `pgrep -x`.
  - No command line holds the string `/strata --serve`.
- **Kernel checks and the deadline.** A kernel check runs after every arm and every step. After the deadline, no new
  step starts.
- **A kernel-check failure** stops new steps and leaves the gap OPEN: 8080 down, test lock and queue hold kept. The
  driver exits 3, the series stops with an alert, and Karl decides. Part a then writes no decision file, so part b
  refuses.
- **Exit codes:**
  - 0 = done; the outcome is in `decision.txt`.
  - 1 = refused, or the gap did not open.
  - 3 = kernel-check failure.
  - 4 = `port_gap4.sh end` failed.

  The series runner stops on any exit other than 0.
- **Earlier attempts.** An earlier attempt's outputs are moved to `prev-*` / `gap-?-prev-*`, so the rules judge only
  this attempt's files.

## 1 NLL many-positions (`gap-nll.sh`): ~64 min with 8080 down, deadline 75 min (`NLL_MAX_MIN`)

| step | what | min |
|---|---|---|
| 0 | refusals; the 6 configs; engines (`engine-r22p021n` / `-p028x` / `-p028` SHA = their SHA256 files, P028x = f4c4f654fb24); the 11 prompt files; >= 20 GB free | 0 |
| 1 | `port_gap4.sh begin`, memory wait | ~1 |
| 2 | arm **ref** (P021n), then `score.py validate` on it at once. If it does NOT AGREE, no further arm runs, the gap ends and nothing is judged | ~6.5 |
| 3 | arms ref2, unfused, cpushare (`--env STRATA_PREFILL_CPU_SHARE=0.4`), v2, x28h, x28h-nov2, r28h: `score.py run CFG gap/ARM --set long11 --rows all:8` under `guard.py`, `nll_rules.py envwatch`, a kernel check after each | ~42 |
| 3b | optional: x28h-unfused, x28h-cpushare (P028x's own rounding references). Each starts only if 7 min fit before the deadline (they do at the expected times) | ~12 |
| 4 | byte identity (`ident`): ref2 = ref, x28h-nov2 = x28h; `port_gap4.sh end`; a kernel check | ~3 |
| 5 | **after the gap** (8080 back, CPU only, nice 19, `NLL_THREADS`=4): validate the other arms; `score.py compare` (ref / unfused, cpushare / ref2, v2, x28h, x28h-nov2, r28h, block scan, `rows.tsv`); `--from-rows` strides 2 and 8; with the optional arms, compare with x28h as the reference; `nll_rules.py decide` | ~16 |

Output goes to `results/r23/nll-many/gap/`:
- `summary.txt`, `gates.txt`, `<arm>/`;
- `validate-*.txt`, `compare*.txt`, `result*.json`, `rows.tsv`;
- `decision.txt` / `.json`;
- when validated: `ADOPTED-BOUND.json` and `PAST-VERDICTS-NOTE.txt`.

**The rules (`nll_rules.py` docstring).** Nothing is judged until `validate_ref` AGREES.

| check | rule |
|---|---|
| NLL FAIL | d > 1.10 x max(\|d_R1\|, \|d_R2\|) + 1.645 x se(d) |
| NLL UNDERPOWERED | not FAIL, and se > 0.01 |
| NLL PASS | otherwise |
| KL (unchanged) | mean and p90 <= 1.10 x the larger reference; rows with KL > 1 <= the larger + 1; changed top-1 <= 1.10 x the larger |
| candidate | PASS = every KL check and NLL pass; FAIL = a KL check or NLL fails; UNDERPOWERED = KL checks pass, NLL UNDERPOWERED |

The rules re-derive every verdict from `result.json` and flag any disagreement with score.py's own verdict. ref2 = ref
and x28h-nov2 = x28h are expected to be exact; a miss is a FLAG in the decision.

**Adoption.** Karl 11-04: "adopt the new bound once the gap has validated the offline head against the engine's own
output."
- Validated: `ADOPTED-BOUND.json` is written. Gates after this one use this NLL rule in place of kernel_rule3's point
  rule; the KL checks stay.
- `PAST-VERDICTS-NOTE.txt` keeps every past verdict as recorded. It adds what the ~31K-position data says about v2, r28h
  and x28h.
- Not validated: NOT JUDGED, and neither file is written. The fallback is the engine-side scoring mode, which needs a
  build and Karl's OK.

## 2 Decode items part a (`gap-decode-a.sh`): ~100 min with 8080 down, deadline 125 min (`R23A_MAX_MIN`)

| step | what | min |
|---|---|---|
| 0 | refusals; the worktree check: `strata-r23decode` is on r23-decode-exact at c4c15d32c, HEAD~2 = fdd2fffa8, v0.2.10 + 30, clean, llama.cpp = its pinned ggml; the 10 gate configs (exe = `engine-r23decode/strata`); gap 17's g17-p210a exact7 (7 files) and p210 yardstick (40 files); the MTP `experts.bin` (512 Strata-form blobs) | 0 |
| 1 | `port_gap4.sh begin` (nothing else runs during the compile), memory wait | ~1 |
| 2 | **build** (as GATE-PLAN 1): cmake tests ON into `strata-r23decode/build`, targets strata, pool_tasks_test, pool_test, pool_stress, numa_pool_test, patch_guard_test (nice 5, 16 jobs, an inline ninja memory guard: pause < 24 GB, stop < 14 GB). Installed as `engine-r23decode/strata` + SOURCE + SHA256. Gates `build_x`, `build8`, `build_src`, `build_warn` | ~15-20 |
| 3 | **tests**: pool_tasks_test (synthetic, then one real blob per pair: IQ2_S, IQ3_S and IQ3_XXS gate/up each with IQ4_NL and with Q2_0 down, plus IQ4_XS/IQ4_NL; cut from the GGUF by `decode_rules.py blobs`); pool_test --selftest; numa_pool_test; pool_stress 20 (plain, then `STRATA_POOL_ONE_BATCH=1`); patch_guard_test; the serve tests (gap 17's rule) | ~10 |
| 4 | **exact7 x7** at pin 2500, with `envcli` and the switches' start lines in each run's 7 logs: r23-B vs g17-p210a; r23-B2 vs r23-B; r23-L, r23-O, r23-LO vs r23-B (r23-B.json + ENVX); r23-Bs (the solo base, INFO); r23-Os vs r23-Bs | ~25 |
| 5 | **pf_yardstick long40** on r23-B and r23-LO: 0 of 40 logit files may differ, B vs LO and B vs gap 17's p210 | ~18 |
| 6 | **timing arms** (INFO): one screen pass each on r23-Bt, r23-LOt, r23-Bst, r23-Ost, then `t2_report.py`; then `t2pass.sh dv`, the two-card timing pass on P028x (ANALYSIS section 7; its exit 3 counts as a kernel-check failure) | ~22 |
| 7 | `decode_rules.py decide-a`, `port_gap4.sh end`, a kernel check | ~3 |

If the build fails, steps 3-6 are skipped except `t2pass.sh`.

Output goes to `results/r23/decode-timing/gap-a/`:
- `summary.txt`, `gates.txt`;
- `build*.log`, `tests/`, `pfy/`, `timing/`, `env-e7-*.txt`;
- `decision.txt` / `.json`, which part b reads.

The exact7 logs are in `bringup/out/logs/prof/r23-*`, and the two-card pass is in `results/r23/decode-timing/t2/`.

**EXACT for each item.** Every listed gate must pass; a missing gate makes the item NOT DECIDED and a failed one makes
it FAIL.
- **Item L:** the build, the tests, e7_B, e7_B2, e7_L and e7_LO, both logit checks, and their env and start-line gates.
- **Item O:** the same, with e7_O and e7_Os (after r23-Bs ran) in place of e7_L.

## 3 Decode items part b (`gap-decode-b.sh`): ~105 min with 8080 down, deadline 125 min (`R23B_MAX_MIN`)

**When part b refuses.** `decode_rules.py check-a` reads part a's `decision.json`. Part b refuses (exit 1) unless all of
these hold:
- the build passed;
- e7_B and e7_B2 passed;
- r23-LO passed exact7;
- at least one item is EXACT. With `R23B_SCREEN_ANYWAY=1`, it is enough that one item's exact7 rows passed.

It also refuses if `engine-r23decode/strata` is no longer part a's build (SHA).

**Arms.** B and LO always; L when item L qualifies; O, Bs and Os when item O qualifies.

| step | what | min |
|---|---|---|
| 1 | `port_gap4.sh begin`, memory wait | ~1 |
| 2 | **the 9-workload screen**, 3 passes in turned order: pass 1 `B L O LO Bs Os`, pass 2 `Os Bs LO O L B`, pass 3 `O B Os LO Bs L`, through `with_server.sh` + `abarm.sh`. Each arm-pass gets `g17_rules.py envcheck --pins --ngpu`, the switch's start line in the whole engine-log slice (the line prints on first use, during the warm-up), the fatal-line check, the settled PCIe share (INFO) and a kernel check | ~77 (18 arm-passes) |
| 3 | **Basalt bp90**, cold, 3 passes (`B LO`, `LO B`, `B LO`): decode, pp16k and pp64k, a fresh engine each | ~22 |
| 4 | `decode_rules.py decide-b`, `port_gap4.sh end`, a kernel check | ~3 |

Output goes to `results/r23/decode-timing/gap-b/`: `summary.txt`, `gates.txt`, `speed/`, `speed-table.md`, `bp90/`,
`decision.txt` / `.json`.

**The rules (`decode_rules.py` docstring = GATE-PLAN 3.4 / 3.5 / 6).** Each arm is compared with its own base (L, O and
LO with B; Os with Bs), on 3 complete clean passes each:
- **No loss per workload** (decode and prompt each): mean_X >= mean_base x (1 - the larger pass spread).
- **No loss overall:** the geomean of the per-pass geomeans >= base x (1 - noise).
- **GAIN:** decode above base by more than max(noise, 1 %).
- **bp90:** LO >= B x (1 - B's pass spread) on conv, struct and prose decode and on pp16k and pp64k prompt.

| verdict | item L | item O | L+O |
|---|---|---|---|
| PASS | EXACT + L and LO no loss + bp90 | EXACT + O, Os and LO no loss + bp90 | both EXACT + LO no loss + bp90 |
| GAIN | PASS + L's decode gain | PASS + O's two-card gain (Os's one-card gain is reported beside it) | PASS + LO's decode gain |

A fatal line in an item's arm makes the item FAIL; one in a base arm makes it NOT DECIDED.

## Checks done (11-04; no GPU, no engine, no build; only `sleep` stand-ins started)

- **Syntax:** `bash -n` on all three drivers, and `py_compile` on both rules files.
- **`nll_rules.py selftest`: 0 failures.**
  - The 29 stored past candidates (PLAN.md section 4's `past-*.json`) were re-judged, and every one agrees with
    score.py's own verdict.
  - Gap 8 v2 comes out UNDERPOWERED, and DeepSeek B passes NLL.
  - Synthetic gaps produce PASS, FAIL, UNDERPOWERED, a KL top-1 FAIL, NOT JUDGED (validate fails, or a reference is
    missing), and the ref2 flag.
- **`decode_rules.py selftest`: 0 failures.**
  - `e7gate` and `lines` on gap 17's real summary and logs: g17-p210a PASS, g17-hcr FAIL, and no r23 line in the port's
    logs.
  - `srccheck` passes on `strata-r23decode`. `warncheck` passes on the port's own logs and catches one injected new
    warning.
  - `blobs` cut all 7 pairs, with sizes equal to `native_experts.txt`.
  - The part a decision tree and part b's refusal cases (build, exact7 base, no EXACT item) behave as specified.
  - Part b's rules were run on gap 17's screen and bp90 data, relabelled (they decide every arm), plus synthetic GAIN,
    LOSS, start-line-missing and fatal-line cases.
- **`preflight`** was run against the live system with a scratch lock file. It passes with P028x on 8080, and it refuses
  when a lock holder is present and when the 8080 engine is not P028x.
- **The environment watchers** were run on a `sleep` stand-in: they find it by exe in the job's tree, read its env, and
  stop it by PID.

## Judgement calls (Karl may want them changed)

- **NLL: compare runs after the gap.** It runs with 8080 back, CPU only and nice 19, as PLAN.md's "after the GPU part"
  says. The series waits for the driver, so no 7d question overlaps it. Only `validate ref` runs inside the gap, so a
  failed head stops the GPU arms early.
- **pool_test input.** pool_test's default `pack/full/experts.bin` does not exist here. It runs with
  `--file strata-v0115/mtp/rt/experts.bin --layer 0` instead: the configs' MTP layer, 512 Strata-form blobs.
- **Build memory guard.** `build_memguard.sh` does not watch `strata-r23decode`, and existing scripts may not be edited.
  The same thresholds therefore run inline in `gap-decode-a.sh`.
- **Part b's refusal is stricter than build + exact7.** It also refuses when no item can be EXACT (a test or the logits
  failed), because PASS needs EXACT. `R23B_SCREEN_ANYWAY=1` relaxes this. Its refusal stops the series, so the Basalt
  gaps wait for Karl.
- **bp90's "B's pass spread".** It is taken as (max - min) / mean, gap 17's bp90 form.
- **The per-workload rule is strict.** On gap 17's relabelled data it flags a -0.1 % prompt difference against 0.1 %
  noise (R4). The bp90 struct row reproduces gap 17's known -2.4 % (B's spread 2.3 %).

## 4-5 Basalt prompt path, parts a and b (`gap-basalt-a.sh`, `gap-basalt-b.sh`; written 11-04, not run)

The gate of `results/r23/basalt-prompt/GATE-PLAN.md` (port: worktree `strata-r23basalt`, branch `r23-basalt-prompt` @
3383d1f8d = r22-port0210 + STRATA_PF_AHEAD / PF_TAIL_SPLIT / PF_FIRST_CHUNK, all off by default). Rules, written before
any run, and the helper tools: `work/r23/basalt_rules.py` (its docstring is the rule text). Refusals, open / close, env
checks, kernel checks and exit codes as in "Common to all three" (exit 1 = refused before the gap opened, 8080 untouched).
Refusals go to `results/r23/basalt-prompt/gap-a-starts.log` / `gap-b-starts.log`.

**Which KL form decides** a rounding-level part (T, C, G; A or U if not exact) is read at part a's start: the NEW form
only when the NLL gap's `results/r23/nll-many/gap/decision.json` says JUDGED, its `validate_ref` gate PASS and
`ADOPTED-BOUND.json` exists; otherwise the OLD form (kernel_rule2 + kernel_rule3 with the point NLL check). Each verdict
line in `decision-a.txt` names its form. New form = the same KL checks (rule3 without its point NLL) on tail24 + long40,
plus the many-positions NLL check (score.py run on ref / unfused / cpushare / candidate on engine-r23basalt, validate on
each, compare with the adopted bound's parameters).

### Part a: ~2.0-3.1 h with 8080 down (old form), +~45 min (new form); deadline 240 min (`GA_MAX_MIN`)

| step | what | min |
|---|---|---|
| build | engine-r23basalt (build-port0210.sh's cmake, nice 5, <= 16 jobs, inline memory guard for this tree); gates: build, no new prefill.cpp warning vs r22p0210, the 3 names in the binary | 15-25 |
| A1 | B, T, G + STRATA_PREFILL_TIMING=1 + STRATA_TRACE=1 on cold pp16k / pp64k (fresh engine each) -> `profile.txt`, `g_go` | ~10 |
| A2 | exact7 B vs g17-p210a (pin 2500, MATCHED); long40 B vs gap 17's p210 (0/40). Miss -> nothing decided, the gap ends | ~13 |
| A3 | tail24 (--prefill auto:16384 --kv int8) B16 / A16 and, with the served share, B16s / A16s: 24/24 each; "M read in place"; exact7 A | 27-60 |
| A4 | exact7 U, K vs B; long40 U vs B40 | ~15 |
| A6 | unfused16, T16 (24 plan lines), long40 T40; the KL rule (tail24: ref16 = B16, cpushare16 = B16s; long40: gap 8's refs) | 21-37 |
| G | optional, only if A1 says go and it fits with what C needs: G16, G40, the KL rule | 15-25 |
| A7 | one start of S at auto:24576 + FIRST_CHUNK -> the lend's chunk N; C on tail24 + long40 at auto:N; KL; VRAM >= 300 MiB | 16-25 |
| NLL | new form only: score.py arms ref, unfused, cpushare, T, C (+ G, A, U when needed; ~7 min each) + compare inside the gap (nice 19) | ~45 |
| A5 | optional: KP on the 16 cuts >= 33K with --keep-kv-resident 32768 | ~8-20 |

Tail24 is 916K prompt tokens: ~6 min at the plan's rate, ~14 at the yardstick's measured 1,120 tok/s; the driver uses
each step's measured time for the optional steps.

Outputs: `results/r23/basalt-prompt/gap-a/` (summary-a.txt, gates.txt, **decision-a.txt**, profile.txt, kl-*.txt,
pfy/, pfy40/, nll/, profile/, build*.log); `engine-r23basalt/` (strata, SOURCE, SHA256); arm configs in
`results/r23/basalt-prompt/gap-configs/` (= configs/P0210x-h.json + each arm's switches, checked by `cfgcheck`).

### Part b: ~1.5 h with 8080 down; deadline 150 min (`GB_MAX_MIN`)

Refuses (exit 1) unless decision-a.txt says BUILD PASS, BASELINE PASS, PART_B ALLOWED and engine-r23basalt is part a's
build. Prices B + the parts part a classed EXACT / ROUNDING-LEVEL + S (S_PARTS) + C (C_PARTS + auto:C_CHUNK).

| step | what | min |
|---|---|---|
| B1 | bp90 cold pp16k / pp64k, a fresh engine each, 3 passes (arms, reversed, arms) | ~35 |
| B2 | bp90 decode fixtures, 1 pass, B S C | ~5 |
| B3 | the 9-workload screen, 3 passes (B S C / C S B / S C B) | ~40 |
| B4 | chat-cache trade: B / T / C with STRATA_TRACE=1, requests 1-3 (`basalt_rules.py chat3`), reported | ~6 |

Outputs: `results/r23/basalt-prompt/gap-b/` (summary-b.txt, gates.txt, **decision-b.txt**, bp90/, speed/,
chat/chat-trade.txt).

### Checks done (11-04; no GPU, no engine, no build)

- `bash -n` both drivers; `py_compile` on basalt_rules.py.
- `kl` on gap 17's long40 dirs reproduces kernel_rule2.py / kernel_rule3.py's stored lines exactly; on gap 8's v2 the
  old form FAILs on NLL, the new form reports it as INFO.
- `kl`, `same`, `ahead`, `planlines` on synthetic tail24 dirs (plan-line formula: T 24 of 24, C at 20480 16 of 24).
- `arms` + `cfgcheck` into scratch (every arm = P0210x-h + its switches), `e7gate` on gap 17's summary, `nllmode` on
  the live (absent) NLL decision and on synthetic JUDGED / NOT JUDGED roots, `nllgate` on a past compare JSON,
  `profile` / `lend` / `vram` / `chatrep` on synthetic logs and real guard lines.
- `decide-a` on synthetic gates (all pass; new form with UNDERPOWERED C and a void A; baseline fail -> PART_B REFUSED),
  `preb`, and `decide-b` on gap 17's speed / bp90 data relabelled.
- `pfy` / `nllrun` engine arguments checked with a stand-in exe; `envcli` / `envcheck` on sleep / python stand-ins:
  found by exe, stray switch caught, stopped by PID; `chat3 --dry-run`: request 1 16,676 tokens, request 2 shares
  16,500.

### Judgement calls (Karl may want them changed)

- **The plan's pf_yardstick_r23.py / r23_rules.py / gap23.sh** are `basalt_rules.py` subcommands (`pfy`, `kl`,
  `decide-a`/`-b`, ...) and the two drivers. Only these new files were allowed.
- **cpushare16 = A3's B16s.** It has exactly B + STRATA_PREFILL_CPU_SHARE=0.4 (_MAX 1792 from the config), which saves
  one tail24 run.
- **Many-positions arms** use score.py unchanged except for the prompt chunk: `nllrun` wraps Popen in score.py's module
  to pass auto:16384 / auto:N. They also use --max-len 33536, so the 4 texts >= 33.5K end in a staged 768-token rest
  that T and C change. The compare runs inside the gap, because decision-a must exist before part b.
- **C's parts** are those passed when A7 starts, from a provisional decision without the NLL gates. T is inert inside C,
  because FIRST_CHUNK takes precedence above 16384.
- **The gain targets** are read as: A, T -> 16K; C, KP, K -> 64K; U, G, S -> either.
- **B3's "prompt geomean not below B"** is strict.
- **B2's noise** is gap 17's 3-pass cold-H spread, since B2 has one pass.
- **Not run:**
  - A8 (PF_AHEAD=2): its condition needs B1, and its prompt set is not defined.
  - `patchtest.sh lossless`: it does not know the new switch names and cannot be edited.

## 7 Unsloth Dynamic v3.1 (`gap-ud31.sh`; written 11-04, not run): ~105 min with 8080 down, deadline 120 min (`UD31_MAX_MIN`)

Karl 11-04: "P, U, S, R; text NLL and KL against R; speed with the no-loss rule; exactness. Put it after the DeepSeek C
gap, once tonight's NLL gap has validated the scorer." The last step of `gap-series.sh`. P028x stays served and nothing
switches. Rules, written before any run: `work/r23/ud31_rules.py` (its docstring is the rule text). The splice:
`work/r15/splice_shard1.py` (a new file; `splice.py` is unchanged). Arm configs: `results/r23/ud31/configs/`, written by
`ud31_rules.py configs` from `configs/x28h.json` (never edited) and checked by `cfgcheck` before the gap.

| arm | what | config = x28h.json + |
|---|---|---|
| P | P028x as served, without vision | nothing (`configs/x28h.json`) |
| U | UD-IQ3_XXS v3.1 as shipped; pack `bringup/out/ud31/pack-u` (`--compat-bf16`) | `--pack`, `--native` shard 1/4, `--ple-gguf` shard 4/4; **+ `STRATA_HC_Q8=1` (11-05, section 7a)** |
| S | v3.1's 144 routed experts in our ISTA shard 1 (`models/unsloth-v31/splice-S/`, our shard 2 hard-linked); pack `pack-s` (no `--compat-bf16`) | the same three paths |
| R | UD-Q4_K_XL (HF cache), the KL reference, quality only; pack `pack-r` (`--compat-bf16`) | the three paths + r21-yq-udq4's memory form: the 5080 alone, `--resident-budget-gib 52`, chat cache 2 GiB, `STRATA_UNBUFFERED_LOAD=1`, no `--expert-cache-device1`; **+ `STRATA_HC_Q8=1` (11-05, section 7a)** |

**Refusals** (exit 1, 8080 untouched), on top of "Common to all three": the 4 UD-IQ3_XXS shards incomplete, or a size /
SHA256SUMS line not the pinned oid in `work/qwen4-kit/unsloth-v31/dl/tree.json` (`predl`); the NLL gap not validated
(`results/r23/nll-many/gap/decision.json` JUDGED, `validate_ref` PASS, `ADOPTED-BOUND.json`: `prenll`); the configs not
x28h + their named differences (`cfgcheck`); `patchtest.sh lossless` failing on U or S; under 100 GB free after the
splice, packs and dumps; R's HF shards not their recorded sizes; P028x's exact7 `x28h-e7a` incomplete. Refusals go to
`results/r23/ud31/gap-ud31-starts.log`.

| step | what | min |
|---|---|---|
| 1 | `port_gap4.sh begin`, memory wait | ~2 |
| 1a | the 4 shards re-hashed (sha256 = the pinned oids, pages dropped as read; a mismatch ends the gap at once) | ~1 |
| 1b | pack U; the splice (shard 1 only, ~54.8 GB: fdatasync + DONTNEED every GiB, then verify: our order, the experts' types, split keys, head = ours, spot checks, shard 2 = our inode); `sync -f`, Dirty + Writeback <= 256 MiB, page cache evicted; pack S (its dense.bin + index = `bringup/out/r20a/pack`'s byte for byte: `pack_S_dense`); pack R | ~8 |
| 2 | exact7 at pin 2500: U1 vs P028x's `x28h-e7a` (INFO), U2 vs U1 (7/7 + slots MATCHED), S1, S2 the same; `decode_rules.py envcli` on each | ~15 |
| 3 | `score.py run CFG gap/nll/ARM --set long11 --rows all:8` on P, U, S, R (`nll_rules.py envwatch`; a watchdog stops an arm's engine by PID after 3x its minutes) | ~31 |
| 4 | the 9-workload screen (`abarm.sh`), passes P U S / S U P / U S P, a fresh server each (`g17_rules.py envcheck`); after pass 1: start lines (`startlines base`), `patchtest.sh lossless` with the engine log, the slots | ~40 |
| 5 | inside the gap when 10 min fit (8 threads), else after it (nice 19, 4 threads, MemAvailable >= 22 GB): `validate` per arm with ITS OWN head; `score.py validate` on P (`head_P`: the same 5 KL values); `compare`; `decide` -> `results/r23/ud31/decision.txt`; `port_gap4.sh end`; a kernel check | ~8 + 2 |

Outputs: `results/r23/ud31/` (decision.txt / .json, pre-checks/, configs/) and `results/r23/ud31/gap/` (summary.txt,
gates.txt, pack-*.log, splice.log, evict-*.txt, nll/<arm>/ + validate-*, speed/, result.json, rows.tsv, compare.txt).
Earlier attempts move to `results/r23/ud31/prev-*`. exact7 labels: `bringup/out/logs/prof/u31-<MMDDHHMM>-{U,S}{1,2}-*`.

**The rules (`ud31_rules.py`).** This is a QUANT COMPARISON, NOT A LOSSLESS GATE. A lower text NLL is better, and a lower
KL against R is better. "Pass" means only WITHIN THE ROUNDING BAND: not different from P beyond what rounding alone
moves at these positions.

| part | rule |
|---|---|
| heads | each arm's own: `output_hc_*` from its pack's dense.bin (what its engine reads), `output.weight` from its GGUF (Q6_K; R's Q8_0). score.py's own Head reads only our ISTA GGUF |
| validate | per arm, its own head: mean KL <= 0.05, each <= 0.5; `head_P` must match score.py's own validate on P, else QUALITY NOT JUDGED |
| statistics | ADOPTED-BOUND.json's: rows from 1,024, blocks of 2,048 tokens, bootstrap 10,000, seed 20261104, z 1.645, se cap 0.01 |
| band | 1.10 x max(\|d_R1\|, \|d_R2\|) from the NLL gap: P028x's own pair (`result-x28h.json`) when it ran, else P021n's (`result.json`) |
| text NLL, X vs P | d = mean(NLL_X - NLL_P): WORSE if d > band + 1.645 se; BETTER if d < -(band + 1.645 se); else UNDERPOWERED if se > 0.01; else WITHIN THE ROUNDING BAND |
| KL vs R | per arm: mean, p90, KL > 1, changed top-1 vs R (INFO). X vs P: dKL = mean(KL(R\|\|X) - KL(R\|\|P)), the same four classes (FURTHER FROM R / CLOSER TO R / ...), the same band |
| exactness | REPEATABLE = e7_X2 7/7 + MATCHED, env gates, lossless (config + log), start lines, S: splice_verify + pack_S_dense |
| speed | g17's per-workload no-loss: every workload's decode and prompt tok/s >= P's x (1 - the larger pass spread) -> NO LOSS, else LOSS (listed); VOID on an env / fatal gate |

**Checks done (11-04; no GPU, no engine, no pack, no splice).** `bash -n`; `py_compile` on both Python files.
`ud31_rules.py selftest`: 0 failures, on Q8_0 vs a scalar ggml transcription; P's pack hc bytes = the GGUF bytes
score.py reads; U's (header files) and R's output.weight found; the configs + cfgcheck (a stray switch fails);
predl / rehash on synthetic files; prenll and the band (both sources); the compare on synthetic dumps with per-arm heads
(two passes with two heads each; S = P exactly; one KL by hand); decide on synthetic gaps (all verdict classes, VOID,
NOT JUDGED); headcheck. Also `cmd_compare`'s CLI path with stand-in heads (scratch). `splice_shard1.py --dry` on our
shard 1 + v3.1's header files: 144 experts (gate/up 52 IQ2_S + 42 IQ3_XXS + 2 IQ4_XS, downs 45 IQ4_NL + 3 Q2_0, 46.84 GiB),
1,079 others ours, 54.81 GB of data, all 1,224 names equal. The watchdog's tree walk, with a sleep stand-in.

**Judgement calls (Karl may want them changed).**
- **The band** comes from the NLL gap's references (P028x's own pair when it ran). The gap measures no rounding pair of
  its own, which saves ~12 min. dKL uses the same nats/token band: it is the NLL difference with R's distribution as
  the soft label.
- **R's form** is r21-yq-udq4's memory form, not P028x's, because its 71.7 GiB of experts do not fit in RAM. It is
  quality only.
- **The configs keep r20a's tokenizer path.** `tok_X` checks that each pack's exported tokenizer is identical.
- **pack_S_dense compares with r20a's pack.** If it differs, a fresh pack of our own file shows whether the difference
  comes from the tool (`pack_S_tool`).
- **U's "as shipped" includes `--compat-bf16`'s BF16 rounding** of its Q8_0 hyper-connections and PLE value. The
  engine cannot read them otherwise. **Superseded 11-05 (section 7a):** the verify read can (`STRATA_HC_Q8=1`), the
  pack and the prompt path cannot.

## 1b GDN prompt paths on stock v0.2.10 at many positions (`gap-gdn-nll.sh`; written 11-04, not run): ~16 min with 8080 down (~30 with the optional pair), deadline 35 min (`GDN_NLL_MAX_MIN`)

Karl 11-04: "If tonight's NLL gap validates the many-positions scorer, add a stock on-vs-off arm with it (~6 min each)."
This is the step right after `gap-nll.sh` in `gap-series.sh`. It measures stock v0.2.10's two GDN prompt paths
(`STRATA_GDN_TC=1` + `STRATA_GDN_CONVL2=2`, which stock `serve/server.py`'s `gdn_stack_env` sets on Linux / CUDA /
Qwen3.8) OFF vs ON with `score.py`, at about 31K positions instead of gap 19's 36. That way Karl's upstream issue does
not rest on the 36-position check. P028x stays served and nothing switches. The rules were written before any run:
`work/r23/gdn_nll_rules.py` (its docstring is the rule text).

| arm | config | what |
|---|---|---|
| s210 | `configs/s0210-h.json` | stock, the 14 pins, both GDN paths off: the reference |
| s210gdn | `configs/s0210-h-gdn.json` | the same, plus TC=1 and CONVL2=2 only: the candidate |
| s210unf (optional) | s0210-h + `--env STRATA_PF_FUSED=0` | stock's own rounding reference 1 |
| s210cpu (optional) | s0210-h + `--env STRATA_PREFILL_CPU_SHARE=0.4` | stock's own rounding reference 2 |

**Refusals** (exit 1, 8080 untouched), on top of "Common to all three". `gdn_nll_rules.py pre` must pass. It checks:
- **nll:** the NLL gap validated the scorer: `results/r23/nll-many/gap/decision.json` JUDGED, `validate_ref` PASS,
  `ADOPTED-BOUND.json`, and `result-x28h.json` or `result.json` holding both rounding references.
- **cfg:** the two configs differ only in the GDN pair, and the pair equals stock `server.py`'s `GDN_STACK_CUDA`.
- **head:** score.py's own head applies (the static half). `--native` is score.py's GGUF, `--pack` is r20a's, the pack
  serves `output.weight` natively, and its `output_hc_*` bytes equal the GGUF's.
- **engine:** `engine-v0210stock` = c8fe72abe45a = its SHA256 file.

The driver also needs the 11 prompt files and at least 20 GB free. Refusals are logged to
`results/r23/gdn-nll/gap-gdn-nll-starts.log`.

| step | what | min |
|---|---|---|
| 1 | `port_gap4.sh begin`, memory wait | ~1 |
| 2 | arms s210 and s210gdn: `score.py run CFG gap/ARM --set long11 --rows all:8` under `guard.py`, with `nll_rules.py envwatch` (2 GPUs), a watchdog (21 min) and a kernel check after each. If s210 is not clean, no further arm runs | ~13 |
| 3 | optional, only if 14 min fit before the deadline: s210unf, s210cpu | ~13 |
| 4 | `port_gap4.sh end`; a kernel check | ~2 |
| 5 | **after the gap** (8080 back, CPU only, nice 19, `GDN_NLL_THREADS`=4, MemAvailable >= 20 GB): `score.py validate` on every arm; `gdn_nll_rules.py compare` (score.py's own `load_dump` + `analyse`, `result.json`, `rows.tsv`); `decide` -> `results/r23/gdn-nll/decision.txt` | ~6 |

Outputs: `results/r23/gdn-nll/` (decision.txt / .json, pre-checks.txt) and `results/r23/gdn-nll/gap/` (summary.txt,
gates.txt, `<arm>/`, validate-*.txt, compare.txt, result.json, rows.tsv). Earlier attempts move to
`results/r23/gdn-nll/prev-*`.

**The rules (`gdn_nll_rules.py`).** NOT JUDGED (with the reason named) unless pre, run and env of s210 and s210gdn, and
`validate_s210` (score.py's head = the stock build's) all PASS and the compare wrote its result.

| part | rule |
|---|---|
| statistics | ADOPTED-BOUND.json's: rows from 1,024, blocks of 2,048 tokens, bootstrap 10,000, seed 20261104, z 1.645, se cap 0.01 |
| distance | d = mean(NLL_s210gdn - NLL_s210) with its block-bootstrap se / CI; KL(s210 \|\| s210gdn): mean, p90, KL > 1, changed top-1 |
| band | 1.10 x max(\|d_R1\|, \|d_R2\|), plus the KL bounds in kernel_rule3's form. From stock's own pair when both ran cleanly; else borrowed from the NLL gap at the same positions: P028x's own pair (`result-x28h.json`) if it ran, else P021n's (`result.json`). The decision names the source |
| NLL | OUTSIDE (higher NLL) if d > band + 1.645 se; OUTSIDE (lower NLL) if d < -(band + 1.645 se); else UNDERPOWERED if se > 0.01; else INSIDE |
| verdict | "the GDN paths' distance is OUTSIDE the rounding band" = NLL OUTSIDE or a KL check outside; INSIDE = NLL INSIDE and all four KL checks inside; else UNDERPOWERED |
| INFO | the adopted one-sided gate rule's verdict; mean \|per-position d\| beside the references'; per text and per position range (1-4K, 4-16K, 16-32K); the block scan; gap 19's 40-prompt numbers. FLAGS: `validate_s210gdn` not PASS, a stock reference identical to s210, a position count different from the borrowed band's, a kernel-check failure |

**Checks done (11-04; no GPU, no engine, no build).**
- `bash -n` on the driver, and `py_compile` on the rules file.
- `gdn_nll_rules.py selftest`: 0 failures, run twice. It covers:
  - `pre`'s parts on the real files: cfg, head bytes (`output_hc_norm` / `down` / `up` = the GGUF's), the engine SHA.
    A stray switch, CONVL2=1, and another `--pack` each fail.
  - `nll_rules.py`'s envwatch rules on all four arms' environments (2 GPUs). The OFF arm with TC=1 fails.
  - `compare` on synthetic dumps (a synthetic head, the real pp4k / rep9k texts), with one KL and one NLL checked by
    hand. score.py's `--from-rows` re-analysis of `rows.tsv` matches.
  - `decide` on every branch: own band, P028x's band, P021n's band, higher, lower, inside, underpowered, KL-only,
    NOT JUDGED, and the flags.

**Judgement calls (Karl may want them changed).**
- **The NLL test is two-sided.** At 36 positions, gap 19 found NLL -0.31 with the paths ON (lower). The issue is
  whether the paths move the output beyond rounding in either direction. The adopted one-sided gate rule is reported
  beside it.
- **`validate_s210` runs after the gap**, as briefed. If score.py's head did not agree with the stock build, the ~7 min
  of s210gdn were spent for nothing. gap-nll.sh validates its ref at once inside the gap.
- **The optional pair starts only if both arms fit** (14 min). With one of the two, the band is borrowed and the one
  stock reference is INFO.
- **`validate_s210gdn` is INFO.** If the ON arm's window rows disagree with its batched rows, that is flagged, not
  disqualifying: the verdict scores the batched rows, which is where the GDN prompt paths run.

## 8 The decode-path check (`gap-decpath.sh`; written 11-05, not run): ~95-100 min with 8080 down, deadline 120 min (`DECPATH_MAX_MIN`)

Karl 11-05: run it before Basalt a, so the Basalt prompt-path port is not judged against a prompt path that may itself
be the outlier. The first step of `gap-series.sh` (after 7d's o03). Rules, runner, env check, compare and decide:
`work/r23/decpath_rules.py`. Its docstring is the rule text, copied to `results/r23/decpath/rules.txt` before any run
(`pre` refuses if the two differ).

**What "the decode path" is here (no build).**
- Serve mode needs `--spec` >= 2, so upstream's teacher-forced scorer (STRATA_LOGPOS in the verify windows that read a
  prompt) reads in windows of at least 2 rows.
- **dec** (the reference) runs on the served binary (engine-r22p028x, `configs/x28h.json`). Every token goes through
  2-row windows (`--spec 2`, `--short-read` above the text), with STRATA_LOGPOS_TOPK=64. The K/V of every position
  comes from the decode path too.
- Its settings are score.py run's (= quant_quality's yardstick): one expert slot (every expert on the CPU pool),
  `--pcie-frac 0`, FP16 K/V, no adaptation, STRATA_ROUTE_TAIL_SKIP=0.
- 1-row windows exist only in the measurement twin (engine-r22p028xm: `force=N` + STRATA_FORCE_T1=1). It gives NLL
  and the top pick only, so it is the window check (**dec1**), not the reference.
- **s210dec** reads stock v0.2.10's decode path on the same text, to confirm it agrees with x28h's.
- The prompt variants are **not rerun**. Their rows are the NLL gap's (x28h = ref = s210, unfused, cpushare, v2,
  x28h-unfused / -cpushare) and the GDN gap's (s210gdn, s210unf, s210cpu). Byte-identical arms are grouped.

**Found while writing it.** The NLL gap's 11 texts are 8 distinct ones:
- 32k = pp32k (all 32,768 tokens);
- tf-long64k = tf-long96k (all 32,768 tokens);
- pp8k = 32k's first 8,011 tokens.

Its bootstrap therefore counted three texts twice. This gap reads each distinct text once.

| step | what | min |
|---|---|---|
| 0 | pre-gap (no GPU; 8080 untouched): preflight (lock, other gap, servers, 8081, kernel watcher), P028x's SHA, `pre` (the variants' rows exist and ran cleanly, rules.txt), `configs --check` (5 derived configs in `results/r23/decpath/cfg/` = template + the declared change), >= 20 GB free; optional engines checked (twin d716ab8217c2, stock c8fe72abe45a, engine-r23decode = part a's) | - |
| 1 | `port_gap4.sh begin`; wait for the memory; a kernel check | ~3 |
| 1b | Karl's pillow 13.0.0 step (below); it cannot fail the measurements | ~4-6 |
| 2 | **dec** (required): pp4k, rep9k, ldrsyn20k, 32k, tf-long64k, tf-long28k, tf-long112k, tf-long40k in that order, each whole while the measured rate says it fits. Budget `DECPATH_DEC_MIN` = 50 min, capped so that 20 min remain; a long text may be cut, not below 8,192. Estimate ~50 tok/s, so ~6 texts and ~14,000 positions. Envwatch kills a mismatched engine; watchdog at budget + 12 min (a stop inside a text keeps the finished texts: rc 2); a kernel check | ~51 |
| 3 | optional (14 min): prompt speed, cold, Basalt's pp16k + pp64k, one fresh engine per run: x28h as served / + STRATA_PF_FUSED=0 / + STRATA_PREFILL_CPU_SHARE=0, 2 passes in turned order (12 starts), g17 envcheck `--pins`, fatal lines, a kernel check each | ~13 |
| 4 | optional (9 min): **dec1**, 1-row windows on ldrsyn20k (7 min budget) | ~8 |
| 5 | optional (9 min): **s210dec**, stock's decode path on ldrsyn20k (7 min budget) | ~8 |
| 6 | optional (fits): decode gap b's failed Basalt arm-passes, recomputed from its cold-*.jsonl. At writing: B decode/pp16k/pp64k pass 1, LO decode/pp16k/pp64k pass 1, LO decode pass 2. Engine-r23decode, gap b's configs, into `results/r23/decpath/bp90-rerun/` | ~10 |
| 7 | `port_gap4.sh end` + a kernel check; after the gap (CPU, nice 19): merge-b + `decode_rules.py decide-b` give `decision-b-merged.txt` (gap b's own files are untouched); `compare` (offline head on ~14K positions x ~5 groups, ~10-20 min); `decide` writes `results/r23/decpath/decision.txt` | ~2 |

**The rules (summary; rules.txt has the full text).**
- **Metrics per variant against dec**, by stratum (1-4K / 4-16K / 16-32K) and overall:
  - K = KL(dec || X) over dec's top 64 + the rest (a lower bound of the full KL);
  - TV = the chance that a T=1 draw differs;
  - top-1 agreement;
  - D = mean NLL distance;
  - paired against the default: dK and c = D_def - |D_X|.
  - Block bootstrap: 2,048-token blocks, 10,000 replicates.
- **The default is THE OUTLIER** if all three hold:
  - D_def > 0 (CI);
  - for every variant, the default is farther in K (dK CI > 0);
  - for every variant, the default is farther in NLL distance (c CI > 0).
- **NOT THE OUTLIER** if some variant is closer in neither measure. **MIXED** otherwise.
- **NOT JUDGED** in any of these cases:
  - dec did not run cleanly;
  - fewer than 3 texts were read;
  - the target check failed;
  - the pairing check failed (default's top-1 agreement < 70 %, or median K > 0.2).
- **Effect on real work.** The 9-workload screen's prompt lengths (gap b's B1 files), each mapped to its stratum,
  for the default and the closest variant:
  - the next pick differs from the decode path's in X % of cases;
  - a T=1 draw differs in Y %;
  - the NLL distance (as perplexity %).
- **Speed.** The cost of PF_FUSED=0 and of the CPU share off, against the served form.
  - GDN on: not priced (gap 17 did not measure it).
  - The served config already sets the CPU share to 0.4 (max 1,792); the yardstick forces it to 0.

**Step 1b, pillow (Karl 11-05, added by the coordinator).**
- **Install.** Record the version (must be 12.3.0, else nothing is installed) and `pip freeze` to
  `results/r23/decpath/pillow/freeze-before.txt`. Then `pip install --no-deps pillow==13.0.0`. Compare the freeze:
  only pillow may change.
- **Tests.**
  - The served tree's `serve/test_exif_orientation.py` and `test_ds_pictures.py`. They run with unittest, since
    .venv has no pytest. They import from the tree without writing to it, with TMPDIR inside the pillow folder.
  - A matplotlib Agg PNG, reopened with PIL and `plt.imread`.
  - A test server on 8081 from `cfg/vistest.json` (= `configs/P028x.json` with its own log and no fallback). It gets
    one JPEG with EXIF orientation 6, so the server's Pillow path runs, and one PNG. Each must answer HTTP 200 and
    name red or blue.
- **Pass:** `strata-compare/requirements.lock.txt` (`pip freeze` after the install).
- **Any failure:** `pip install --no-deps pillow==12.3.0`, then a freeze compare against before. "ROLLED BACK" plus
  the reason goes into the summary and `pillow/RESULT.txt`.
- A kernel check runs after its test server.

**Checks done (11-05; no GPU, no engine, no gap component run).**
- `bash -n` on the driver.
- `decpath_rules.py selftest`: 0 failures. It covers:
  - KL65 against the full-vocabulary KL;
  - the budget and the shortening;
  - the runner on a mock engine: LOGPOS lines, FORCE lines, and an engine ending inside a text (rc 2);
  - the env rules;
  - compare on synthetic rows with score.py's Head, one NLL checked by hand;
  - the verdict branches;
  - decide end to end and NOT JUDGED;
  - freeze-diff;
  - bp90-missing on gap b's real files (the 7 above) and merge-b on a copy;
  - the configs.
- `pre` PASS. `configs --check` OK. `plan main`: ~65 min for all 8 texts at the prior model.

**Judgement calls (Karl may want them changed).**
- **The reference is 2-row windows**, not 1-row: serve mode cannot score 1-row windows with distributions. The
  1-row arm checks it on one text.
- **Experts on the CPU (one slot)**, as the yardstick and the NLL arms ran. Served decode computes cache hits on the
  GPU, which rounds differently. That is not measured here.
- **Speed runs before dec1 / s210dec**, so the "what would it cost" numbers are there if dec runs long.
- **The pillow step comes before the first arm**, as asked. Its test server costs ~2 min of the gap.

## 9 Decode b screen rerun (`gap-screen-rerun.sh`; written 11-05, not run): ~12 min with 8080 down, deadline 25 min (`R23S_MAX_MIN`)

**Why.** On 11-05 at ~06:50:33 a DeepSeek engine (strata-dsv41, pid 1135004, 15.0 GiB on the 5080) started inside gap
b. Pass 3's last three arm-passes died at start with "cudaMalloc ... out of memory ... other programs on it:
strata-dsv41" (`gap-b/speed/*.engine.log`): LO3 at 06:50:34, Bs3 at 06:50:39 and L3 at 06:50:42. Gap b's
`decision.txt` therefore has L, LO and Bs at 2 of 3 clean passes, and items L, O and L+O are NOT DECIDED.
- **Bs3 is rerun too.** The request named L3 and LO3, but Bs3 died the same way. Without it, Os vs Bs has only 2 base
  passes and item O cannot be decided. `R23S_ONLY="LO3 L3"` drops it.
- **Os3 is clean.** Its last request ended at 06:49:58, and the DeepSeek profile copy was written at 06:50:33.
- **The 7 Basalt arm-passes** lost to the same start are the decode-path gap's step 6 (section 8).

Rules, written before any run: the docstring of `work/r23/screen_rerun_rules.py` (a new file; `decode_rules.py` is
not edited).

| step | what | min |
|---|---|---|
| 0 | pre-gap (no GPU; 8080 untouched): `decode_rules.py check-a` (gap b's own pre-check), engine-r23decode = part a's build, gap b's preflight (lock, other gap, servers, 8081), kernel watcher, files and configs. Then `missing`: gap b's uncounted arm-passes whose engine log has both collision lines, in the original pass's positions (pass 3 `O B Os LO Bs L` -> **LO Bs L**). Any other uncounted pass is KEPT as gap b judged it. Nothing to rerun = exit 1 | - |
| 1 | `port_gap4.sh begin`; memory wait; a kernel check | ~1 |
| 2 | gap b's darm unchanged per arm-pass: `with_server.sh` + `abarm.sh` (warm-up, W1-W3, agent x2, research4 x4), `g17_rules.py envcheck --pins --ngpu`, the start-line check (`--want late,one` / `none` / `late`), fatal lines, the PCIe share (INFO), a kernel check. **New:** a foreign-GPU-user check before and during each arm (below). An arm starts only if 5 min remain before the deadline | ~11 (3 x ~3.7) |
| 3 | `port_gap4.sh end` + a kernel check; after the gap (CPU, nice 19): `screen_rerun_rules.py final` | ~1 |

**The foreign-GPU-user check (new; this is exactly how gap b was lost).** It looks for an engine process by exact name,
or an NVIDIA compute process holding >= 512 MiB, whose binary is not in `engine-r23decode/`.
- Before the arm: the driver waits up to 60 s for it to go. If it stays, the gate is `foreign_N FAIL` and the arm is not
  started.
- During the arm: sampled every 5 s into `N.foreign`. One sighting gives `foreign_N FAIL`: the arm-pass is VOID and is
  never merged.

**The merge and the verdict (`final`).**
1. The decode-path gap's `merge-b`, called unchanged: gap b's records, with its bp90 rerun
   (`results/r23/decpath/bp90-rerun/`, if it ran) in place of the failed Basalt arm-passes.
2. This gap's arm-passes over that. For each label it ran, gap b's `N{n,a,r}.jsonl`, `N.wu.jsonl` and its
   env / lines / pcie / fatal gates are replaced. Never replaced: a pass gap b already counts, and a VOID pass.
3. `decode_rules.py decide-b`, unchanged, on `screen-rerun/merged/`.

`decision-b-final.txt` and `.json` list the sources, what is still missing, then the decision. Gap b's and the
decode-path gap's files are only read.

Output goes to `results/r23/decode-timing/screen-rerun/`: `starts.log`, `summary.txt`, `gates.txt`, `missing.txt`,
`speed/`, `speed-table.md`, `merged/`, `decision-b-final.txt` / `.json`. An earlier attempt's outputs move to `prev-*`
inside that folder.

**In the series:** not yet. It needs a `STEPS` entry in `gap-series.sh` and a `.ready` file. Put it after
`gap-decpath.sh`, so the bp90 rerun is in the merge. If it runs first, `final` gives bp90 NOT DECIDED; run
`.venv/bin/python -I -B work/r23/screen_rerun_rules.py final` by hand after the decode-path gap (CPU only).

**Checks done (11-05; no GPU, no engine, no gap component run).**
- `bash -n` on the driver.
- No `pgrep -f`, `pkill` or `/strata --serve` in either file, and no system /tmp.
- `foreign()` on stubbed pgrep / nvidia-smi:
  - flagged: a 15 GiB process, an unknown amount, a named engine;
  - skipped: under 512 MiB, a dead pid, a binary in the engine folder.
- `screen_rerun_rules.py selftest`: 0 failures in 14 checks. It covers:
  - `missing` on synthetic data: the order, KEPT without collision lines, `--only`;
  - `missing` on gap b's real files: exactly LO3 Bs3 L3;
  - `final`, all three + bp90 rerun: L GAIN / O PASS / L+O GAIN;
  - Bs3 not run gives O NOT DECIDED; a fatal line in L3 gives L FAIL;
  - a foreign process gives a VOID pass (L NOT DECIDED);
  - no bp90 rerun gives bp90 NOT DECIDED;
  - a counted pass is never replaced;
  - the merge on gap b's real files (all screen arms at 3 passes);
  - gap b's files unchanged.

## 7a v3.1 revision (11-05, before any run): `STRATA_HC_Q8=1` on U and R, the frozen pack-rounding rule

Karl 11-05, after `results/r22/port-0211-review.md` Flag 1: "v3.1 U arm: yes, add STRATA_HC_Q8=1. P stays exactly as
served with the switch off ... Any reference or exactness rows used for U must be made with the same switch." The rule
text is `ud31_rules.py`'s docstring. The driver copies it to `results/r23/ud31/gap/rules.txt` at the gap's start (gate
`rules`), and `decide` flags any later change.

**What the switch does in our served engine** (strata-r22p028x, read only):
- `native_dense.cpp:404-430`: every shard of `--native` is walked. Each Q8_0 `blk.N.hc_{attn,ffn}_{down,up,inject}` /
  `output_hc_{down,up}` tensor gets the GGUF's own bytes as its Q8_0 copy.
- `:431-466`: only a layer row still without one (a BF16 file) is quantized from the pack at load. That is the lossy
  kind, which is why P and S stay off.
- With one dense GPU (the helper card is not a layer split), the BF16 copies of the layer rows are not loaded
  (`generate.cpp:4427`).
- U has 194 Q8_0 hc tensors (675,430,400 B) in shard 2. The engine should log "STRATA_HC_Q8=1: 0.63 GiB". A value of
  0.62 would mean the rows were quantized from BF16.
- **Read by** the verify / decode read: `verify.cpp:1480` and `:2416` (the final mixer too), through `launch_q8`, which
  goes ahead of our GR_FORK / GR_V3 read. So exact7, the screen, validate's window rows and the follow-up see it.
- **Not read by** the prompt path. `prefill.cpp:3747` dequantizes per half to BF16. Those values are bit-equal to the
  pack's `--compat-bf16` rounding: both are nearest-even of d x q in float32. So U's NLL score includes the pack
  rounding.

| item | 11-05 |
|---|---|
| U | `STRATA_HC_Q8=1` in `results/r23/ud31/configs/ud31-U.json`. exact7 U1 / U2 use it (U1's INFO line against `x28h-e7a` is P without it) |
| R | **on too.** R is U's KL reference, and its UD-Q4_K_XL stores hc as U does (headers read 11-05: 192 + 2 Q8_0, injects F32), so the switch reads R's own bytes. One R serves all arms: its prompt rows read the same BF16 values either way |
| P, S | off. `cfgcheck` requires U = R = "1", S absent, x28h absent |
| switch check | `hcline` on each engine's own log: after every quality arm (`hcq8_nll_X`), each arm's first screen pass (`hcq8_scr_X`) and the follow-up (`hcq8_dec_U`). U / R: the GGUF headers' Q8_0 sum (0.63 GiB) with all 192 layer rows Q8_0 in the file. P / S: no line. A FAIL makes the arm's NLL NOT DECIDED, U's exactness CHECK FAILED, its speed VOID |
| pack forms | `hcforms_U` / `hcforms_R` (INFO, after each pack): the hc records in `conversions.json`. The injects are read from the pack on every path: exact, or flagged |
| asymmetry | our ISTA file stores hc down / up / inject and output_hc as **BF16** (`day1-check/files/*.tensors.tsv`). P / S read their HC projections unrounded; U's (and R's) are rounded at pack time |

**The frozen rule.** Every U NLL / KL verdict carries "includes pack rounding (the prompt path reads U's Q8_0 HC
projections as BF16 from the pack)".
- **U's text NLL is WORSE (d > band + m) or inside its margin (band < d <= band + m):**
  - `nll_U` = INCLUDES PACK ROUNDING; the class is kept in `nll_U_class`;
  - decision.txt says `=> U DECODE-PATH FOLLOW-UP: WANTED`, and decision.json has `quality.pack_rounding.dec_followup`.
- **Otherwise** (d <= band): the class stands, and the follow-up is NOT NEEDED.
- **U's KL:** recorded the same way, but it gets no follow-up (R's decode path is not read).
- A new v3.1 attempt also moves `results/r23/ud31/dec/` to `prev-*`.

## 10 v3.1 decode-path follow-up (`gap-ud31-dec.sh`; written 11-05, not run): ~55-60 min with 8080 down, deadline 70 min (`UD31DEC_MAX_MIN`)

Karl 11-05: "Before deciding, queue a decode-path teacher-forced score of U with HC_Q8=1, using the decode-path gap's
scorer." It is already in `gap-series.sh` `STEPS`, right after `gap-ud31.sh`. It runs only if the v3.1 decision says
WANTED. Otherwise it exits 1, the series skips it, and 8080 is untouched. Rules: `ud31_rules.py`, THE DECODE-PATH
FOLLOW-UP.

| step | what | min |
|---|---|---|
| 0 | pre-gap (no GPU; 8080 untouched): `dec-pre` checks that the v3.1 decision.json and .txt both say WANTED; that the decode-path gap's dec arm exists (rows, `run_dec` + `env_dec` PASS, >= 3 texts, x28h, logpos, no `--env`); and that U's config = `configs`' U (`STRATA_HC_Q8=1`), with the v3.1 gap's `dl_sha` + `pack_U` PASS, the pack files and the shard sizes. Then preflight (lock, other gap, servers, 8081), the kernel watcher, P028x's sha, >= 5 GB free | - |
| 1 | `port_gap4.sh begin`; memory wait; a kernel check | ~3 |
| 2 | **arm U**: decpath's runner unchanged via `dec-run`. It gets dec's own texts in order, dec's cuts, and dec's `--max-context` / `--short-read`; a text may be cut further, but not below decpath's min cut. Config `ud31-U.json`. Budget `UD31DEC_ARM_MIN` = 52 min, capped so that 16 remain. `dec-envwatch --kill` (decpath's env rule: the switch is required); watchdog at budget + 10 (rc 2 keeps the finished texts). Then `dec-args` (U's engine args = dec's except U's three paths), `hcline` (0.63 GiB), and a kernel check | ~52 |
| 3 | `port_gap4.sh end` + a kernel check. After the gap (CPU, nice 19, MemAvailable >= 14 GB): `dec-compare`, then `dec-decide` -> `results/r23/ud31/dec/decision.txt` | ~2 + 1 |

**P is not rerun.** Its rows are `results/r23/decpath/gap/dec` (x28h as served). A rerun of the decode-path gap moves
them to that gap's `prev-*`, and the pre-check then refuses.

**The rules.**
- **Positions:** dec's compare positions, every 8th from 1,024 to cut - 2. Both lines' target must be the text's next
  token.
- **Distance:** d_dec = mean(NLL_U - NLL_P), per length range (1-4K / 4-16K / 16-32K) and overall.
- **Band and statistics:** the v3.1 decision's band, z, se cap, blocks, bootstrap and seed.
- **Classes:** WORSE / BETTER / UNDERPOWERED / WITHIN THE ROUNDING BAND. A range with < 500 positions or < 2 texts is
  THIN. The overall class is the headline: "the verdict on the file that the v3.1 gap deferred".
- **INFO:** top-1 agreement; KL(P || U) over P's top 64 (decpath's floor rule); the prompt path's d at the same
  positions (from the v3.1 `rows.tsv`) and d_prompt - d_dec with its CI.
- **No pack-rounding caveat** on this verdict. Two things are named: the injects' pack exactness (from
  `pack-u/conversions.json`) and the different hc read kernel (a summation order).
- **NOT JUDGED** if any of these holds: `run_decU` / `env_decU` / `dec_args` / `hcq8_dec_U` not PASS; no compare;
  < 3 texts in common; a target mismatch; no v3.1 band.

Outputs: `results/r23/ud31/dec/`: `gap-ud31-dec-starts.log`, `decision.txt` / `.json`, and `gap/` (summary.txt,
gates.txt, t0.txt, U/ with score.tsv + index.json + stderr.txt, U.run.txt, result.json, compare.txt). Earlier attempts
move to `dec/prev-*`. Exits 0 / 1 / 3 / 4 as the other gaps.

**Checks done (11-05; no GPU, no engine, no gap component run).**
- `bash -n` on both drivers. Both Python files compile.
- `ud31_rules.py selftest`: 0 failures in 79 checks. The checks added 11-05 cover:
  - the configs (U and R on; S and x28h off; each wrong switch fails `cfgcheck`);
  - the hc forms read from the headers: ISTA is all BF16; U (downloaded shards and header files) and R (HF cache) have
    192 + 2 Q8_0 = 675,430,400 B, injects F32;
  - `hcline` on synthetic logs (0.63 PASS; 0.62, no line, a mixed pair and a line on P all FAIL);
  - `hcforms`;
  - the frozen rule: d +0.03 WORSE -> INCLUDES PACK ROUNDING + WANTED; +0.008 inside the margin -> the same;
    +0.002 -> WITHIN, NOT NEEDED; -0.05 -> BETTER; KL likewise; `hcq8` FAILs;
  - the rules snapshot (a change is flagged);
  - `dec-run` on decpath's mock engine with dec's plan (its texts, cuts and L); `dec-args` (a changed setting and a
    foreign path both fail); decpath's env rule without the switch fails;
  - `dec-pre` refusals (not WANTED, the .txt disagreeing, `run_dec` FAIL, < 3 texts);
  - `dec-compare` on synthetic logpos rows (positions, a wrong target counted and dropped, d, KL, the prompt-path
    line);
  - `dec-decide` (WORSE, WITHIN, NOT JUDGED on `dec_args` FAIL and on < 3 texts).
- The CLI of every new subcommand, on the selftest's scratch data.
- The installed `results/r23/ud31/configs/ud31-{U,S,R}.json` equal the copies that pass `cfgcheck` in the selftest
  (S unchanged).

**Judgement calls (Karl may want them changed).**
- **R gets the switch** (above). Leaving R off would change only R's validate and its window rows, not the KL rows.
- **The trigger is d_U > band.** "Inside the margin" is read as band < d <= band + m, whatever the class
  (WITHIN or UNDERPOWERED). BETTER, and WITHIN with d <= band, are not triggers.
- **The follow-up judges the NLL only.** It uses the v3.1 band, which was measured on the prompt path. No
  decode-path rounding pair exists.
- **The switch changes U's hc read kernel as well** (`launch_q8` replaces our fork's read), so U's decode path differs
  from P's by a summation order besides the weights.

**11-05 revision of section 8's statistics (Karl 11-05, before any analysis).** `decpath_rules.py` was replaced
(new file, then `mv`). Only compare, decide and the selftest changed; every subcommand the gap's steps call before
the analysis is unchanged (an AST comparison confirms it). `rules.txt` keeps the old text and appends the revision.
- **The unit is the whole text.** The 8 distinct texts; the dec plan never reads the duplicates.
- **The fixed distance:** per text, the mean KL(dec || path) over 65 bins.
- **5 paths** once the aliases are grouped.
- **The rule:** OUTLIER if the default is the farthest in >= 7 of 8 texts; NOT AN OUTLIER if <= 4; else INCONCLUSIVE.
  - Chance at A = 5: 0.000084 / 0.9896 / 0.0103.
  - Fewer than 8 texts read: the same proportions, flagged. Fewer than 5: NOT JUDGED.
- **Intervals** come from whole texts (t(N-1) / CR1, and a whole-text bootstrap). The 2,048-block SE is printed
  beside them, labelled "not used for the verdict".
- **Secondary, information only:**
  - (a) short (pp4k, rep9k) against long;
  - (b) |dNLL| in the bins 0-2K / 2-8K / 8-16K / 16K+ (against ref on all 8 texts from the gaps' rows.tsv, and on
    the dec positions against ref and against dec);
  - (c) the 1-row check, with its SOUND rule.
- **Selftest:** 0 failures, on synthetic data. The 8 synthetic texts have the default farthest in 7, so the rule
  gives OUTLIER. The chance rates, CR1 and the D_t means are checked by hand.

## 7b / 10 revision (11-05, before any run): the NLL bound revoked, the KL rules at the text level

The bound is revoked in `results/r23/nll-many/gap/ADOPTED-BOUND.REVOKED.json`; the reason is in
`results/r23/nll-many/recompute/REPORT.md`. Karl: "Basalt a/b, the v3.1 gap and later gates go back to the KL rules.
Report many-positions NLL as information only ... carry my frozen rule over to whatever replaces the bound." This
supersedes the NLL parts of sections 7, 7a and 10. Rule text: `ud31_rules.py`'s docstring (QUALITY; THE PACK-ROUNDING
RULE; THE DECODE-PATH FOLLOW-UP).

- **Preflight (`prenll`).** It now requires only `validate_ref` PASS. `ADOPTED-BOUND.json` is not read and the NLL gap's
  decision status is not required. The band code is removed.
- **The texts.** The compare's `rows.tsv` is deduplicated as the recompute did: 32k and tf-long64k are kept; pp32k,
  tf-long96k and pp8k are dropped. That leaves 8 distinct texts, and the text is the unit.
- **The verdict (U, S vs P): the KL rules' four metrics against R.** These are mean KL(R || X), p90, KL > 1 rows and
  changed top-1, taken per text.
  - **Per text:** worse if X > 1.10 x P (+ 1 for the counts); better if P > 1.10 x X (+ 1). A text with both arms under
    the floor (0.01 nats for mean / p90, 5 for the counts) is inside; rep9k's KL is ~1e-4.
  - **Per metric:** WORSE / BETTER means >= 6 of the 8 texts on that side and <= 1 on the other.
  - **Arm:** WORSE THAN P if any metric is WORSE. BETTER THAN P if the mean is BETTER and no metric is WORSE. Otherwise
    INSIDE THE MARGIN, ABOVE or AT OR BELOW P by the pooled mean.
- **Why 1.10 and 6.** 1.10 is the KL rules' own tolerance. The 6 is calibrated on the recompute's real rows, all against
  ref:
  - the two rounding references (cpushare vs unfused, either way) reach at most 3 texts on one side for any metric;
  - v2 (a kernel change the KL rules pass) reaches at most 5;
  - so 6 does not arise from rounding. The selftest re-checks these numbers.
- **The frozen rule, moved** (corrected 11-05 to Karl's words). U WORSE THAN P, or INSIDE THE MARGIN on either side, gives INCLUDES PACK ROUNDING and
  `FOLLOW-UP: WANTED`. Only BETTER THAN P gives NOT NEEDED.
- **Uncertainty (labelled).** The pooled KL ratio and the NLL d are given with the whole-text bootstrap CI (8 texts,
  crude), with the 2,048-token-block figure beside it marked "understates".
- **Text NLL.** INFO only, per arm and per text. No verdict.
- **The follow-up (`gap-ud31-dec.sh`).**
  - It refuses unless the decision says WANTED (unchanged). It also needs a dec arm with >= 6 texts.
  - There is no R on the decode path, so it judges U vs P text NLL per text, against `margin_t` = 1.10 x the larger
    |d| of the NLL gap's two rounding references on that text. The margins are written in the rules (32k 0.188 ...
    pp4k 0.547).
  - It uses the same counts (6 / 1). The pooled d gets a whole-text CI with the 2,048-block figure beside it; the
    length ranges are INFO.
  - It is NOT JUDGED with < 6 texts in common.
- **Checks:** `bash -n` on both drivers; compile; `ud31_rules.py selftest` 0 failures in 88 checks. The new checks
  cover prenll without the bound file; dedup (duplicates made "worse" do not count); every verdict class with its
  trigger; the floor; the calibration on the real recompute rows; the follow-up's five verdict cases and NOT JUDGED
  cases; and the CLI on scratch data.
- **Judgement calls.**
  - The follow-up judges NLL, the only quality measure on the decode path. Its per-text margins come from prompt-path
    rounding pairs, so U must differ by ~0.14-0.55 nats on 6 texts to be called worse or better there.
  - ABOVE / AT OR BELOW P (by the pooled mean) is a label only; both inside cases trigger the follow-up.

## 10c follow-up rule chosen by Karl (11-05, before any run)

Karl: "Use your recommended rule: U vs P on decode-path text NLL, by consistency across the 8 texts." This supersedes
section 7b's per-text margins for `gap-ud31-dec.sh`.
- **Per text** (only texts that both U and P have): lower / higher = U's mean decode-path NLL vs P's on the same
  positions. A tie (|d_t| < 1e-6) counts as neither side.
- **N = 8:** BETTER if lower in >= 6 and higher in <= 1; WORSE is the mirror image; anything else is INCONCLUSIVE.
  INCONCLUSIVE prints "if the file choice hinges on it, Karl decides on a separate R decode-path gap".
- **Fewer texts:** scaled as the decode-path check does, rounding the demanding way: at least ceil(6N/8), at most
  floor(N/8).
  - N 7: 6 / 0; N 6: 5 / 0; N 5: 4 / 0. These are flagged as "written for 8 texts".
  - Under 5 texts: NOT JUDGED. `dec-pre` now needs >= 5 texts in the dec arm.
- **Beside the verdict:** the pooled d with its whole-text interval. The 2,048-block figure is labelled "not used for
  the verdict".
- **INFO only, no extra engine time: the rounding cost per text**, (U decode - U prompt) - (P decode - P prompt) at the
  positions all four have. Signs and a whole-text interval are reported.
  - U decode: this gap.
  - U prompt: the v3.1 gap's `rows.tsv` nll_U.
  - P decode: the decode-path gap's dec rows.
  - P prompt: the NLL gap's ref rows (= x28h), `results/r23/nll-many/gap/rows.tsv` nll_ref.
  - It also cross-checks the v3.1 gap's own P rows against them (0 expected).
- **No R** in the follow-up.
- **Checks:** selftest 0 failures in 100 checks: thresholds N 5-8, ties, 10 counting cases, end-to-end
  WORSE / BETTER / INCONCLUSIVE / 7 texts / 4 texts, and the rounding cost = d_dec - d_prompt.
