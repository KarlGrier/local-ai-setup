# Gap 17 - the v0.2.10 port's gates and pricing (written 11-03, not run)

Karl 11-02 ("approved as written", `results/PORT-V0210-PLAN.md`), and his 11-03 answers below. Gap 17 tests our port to
Strata v0.2.10. **Nothing switches.** P028x stays served on 8080 until item 7 is done. A switch that passes here becomes a
candidate for after item 7, and switching it on is Karl's call then.

- **The build under test:** `engine-r22p0210` (89379c28f361), built in gap 18 from branch `r22-port0210` @ fdd2fffa8 in the
  worktree `strata-r22p0210`.
- **Its config:** `configs/P0210x.json`. Its pins were not edited. Its `_comment` still says "NOT BUILT YET", which is now
  out of date; it was left alone under the rule.

| file | what it is |
|---|---|
| `work/r22/gap17.sh a` / `gap17.sh b` | the gap, one part per gap (`all` still exists but is not the plan) |
| `work/r22/g17_rules.py` | the decision rules, fixed before the gap (its docstring) |
| `configs/P0210x-h*.json` (incl. `-gdntc`, `-gdncv`), `s0210-h`, `s028-h`, `P0210x-RTpin-vision`, `P0210t-*`, `s0210t-hnospec` | the arms. Made by `results/r22/gap17-prep/scratch/make_configs17.py` |
| `basalt-ab/scripts/abrun.py` | gained the frozen `edit` set (backup `abrun.py.before-edit`) |
| worktrees `strata-r22p0210m` (`r22-port0210-meas`) and `strata-r22s0210t` (`r22-stock0210-meas`) | the MEASUREMENT twins, hand-ported 11-03, **not compiled**. Part b builds them at its start |
| `results/r22/gap17/` | the output: `summary.txt`, `gates.txt`, `decision.txt`, `speed/`, `pfy/`, `bp90*/`, `sp/` |

Checks done: `bash -n`, `py_compile`, `git diff --check`, and a read-through of every resolution. Nothing was run, built
or started.

## Karl's answers (11-03)

1. Parts a and b run in **separate gaps** between 7d questions.
2. The 5 MEASUREMENT commits are **hand-ported** (below). **The stock tree's 1-token check (2) stays**, for information
   only. Part b builds both twins at its start, inside the gap, with build-port0210.sh's flags (the 8-row build). The memory
   guard now covers `strata-r22s0210t*` and `strata-v0210stock*`.
3. **GDN as ONE stack** (TC=1 + CONVL2=2); the two paths are split only if the stack fails the KL rule. If the stack
   passes, **each path alone is ALSO priced**: speed only, no KL, on the 16K / 64K cold prompts and the 9-workload screen,
   so a path that adds nothing can stay off.
4. The `GR_FORK=0` control pair stays as written: a diagnostic, run only if the greedy lookup items differ.
5. **`STRATA_GR_R2` stays pinned 0.** If upstream claims a GR_R2 gain on sm_120, put it on a later gate list.
6. The thresholds as proposed, **plus a no-loss condition**:
   - GDN candidate: one long prompt above +max(noise, 1 %).
   - Lookup gain: E1 above +max(noise, 2 %).
   - A GDN or lookup-window gain only counts if **no workload of the 9-workload screen gets slower beyond the noise**. Per
     workload, decode and prompt each: the arm's pass mean against P's, allowing the larger of the two arms'
     pass-to-pass spreads for that workload (`g17_rules.py wl_noloss`).

## The MEASUREMENT twins: the port status per commit

Both twins are local commits by KarlGrier (noreply), with no trailers. Each commit keeps its original message plus one
line, "ported to v0.2.10: ...".

- **Series check:** the twin's changed lines are those of `r22-port028x-meas`, line for line, except the 4 lines added by
  hand below (189 against 187).
- **`r22-port0210-meas`:** = `r22-port0210` + 5 = v0.2.10 + 33, head **d94a3850d**.

| # | v0.2.8 twin | commit | on v0.2.10 | port twin |
|---|---|---|---|---|
| 1 | 6881e12b2 | `--teacher-force` (CLI) | **context fixed**: `verify.hpp`, our `head_logits()` after upstream's new DFlash2 tap API, both kept. The CLI block merged unchanged; its names and the `ver.run` / `ver.commit` signatures were checked. `head_logits_` holds `max_t` rows, so windows past 8 fit | 670557bc6 |
| 2 | 91641ea45 | force=N serve loop | **context fixed**: the serve decode loop's head moved (upstream's DFlash2 defer / draft lambdas), and our `forced.empty()` went onto upstream's loop line. The force loop and the pipeline condition merged unchanged. **Hand-added:** `exit_if_gpu_fatal` on the force loop's run and commit failures (v0.2.10's #4350 rule, as the decode loop has it) | 105d467fe |
| 3 | 0959eda9a | force= key + server hooks | applied clean, 3-way. The GEN parser takes `force=` beside upstream's `pen_from`; `Service.run` still gets the request as its sampling dict | 8ba89740c |
| 4 | 52b86ae2d | swaps land as decoding's | applied clean. **Hand-added:** both teacher-forced loops take decode's interval `o.adapt_iv(rounds)`, v0.2.10's warm-up interval, instead of `o.adapt_every`. Nothing changes without a warm-up interval, and our check arms run `--adapt-swaps 0` | 09edccc20 |
| 5 | 393916326 | `STRATA_FORCE_T1` | applied clean | d94a3850d |

- **`r22-stock0210-meas`:** = v0.2.10 + the same 5 (the port twin's v0.2.10 forms), head **123fd048a**: cddfde587,
  b8dece959, 790bdce54, 30681439b, 123fd048a.
  - One hand resolution, as in build-twin16.sh's s28t: the serve loop's bound is stock's `max_new` where the port has our
    `lim`.
  - Otherwise the same lines as the port twin.
- **Not compiled.** The first compile is part b's B1. If a twin fails to build, its gates stay missing (INCOMPLETE), and
  the build log is named.

## The arms

- **B** = `x28h`: P028x's test form.
- **P** = `P0210x-h`: the port with the 14 pins and our switches on, without pictures or a fallback.
- **On top of P:**
  - **L** = `-L12`: lookup windows up to 12.
  - **F** = `-pf133`: GR_V3_PF=133 with GR_FORK=1.
  - **R** = `-hcr`: PF_HC_REGION=1.
  - **G** = `-gdn`: the GDN stack.
  - **T** = `-gdntc`: GDN_TC alone (TC=1, CONVL2=0).
  - **V** = `-gdncv`: GDN_CONVL2 alone (TC=0, CONVL2=2).
- **For the release checks:** `P0210x-h-off` (our six switches off, no `--chat-cache`), `s0210-h` (plain stock v0.2.10,
  the same arguments and environment), and `s028-h` (stock v0.2.8, a diagnostic).
- **Part b:** `P0210t-hnospec` / `-t3` / `-ess` / `-ess-L12` on the port twin, and `s0210t-hnospec` on the stock twin.

Every serve arm runs `g17_rules.py envcheck` first. It finds the engine by `/proc/PID/exe` and checks:
- the config's environment exactly;
- on v0.2.10, no new default set behind the config;
- `STRATA_ROUTE_TAIL_SKIP=0`;
- two GPUs;
- `--kv-resident 32768` as the last value.

A sticky CUDA error now ends the v0.2.10 engine (the server restarts it). An arm with a fatal error, a stall, a restart or a
non-finite line is void (`fatal_*`).

## Run order and time (8080 down; plus the wait for the running question at `port_gap4.sh begin`, which took 2 h 50 min in gap 18)

Timings come from gaps 15, 16 and 18. The base figures: exact7 3.25 min a set; a screen pass 3.6 min for the 9 workloads,
plus 0.8 min for the 2 rewrites; pf_yardstick 8.5 min; a cold Basalt run 1.2 min; check (2) with the 1-token reference
31 min; a speculative-path arm 27 min.

**Part a: ~3.7 h, up to ~3.9 h with the conditional exact7 runs.** Deadline 260 min.

| step | what | min |
|---|---|---|
| A1 | builds: the port's tests (`strata-r22p0210/build-tests`); plain stock v0.2.10 (`strata-v0210stock`, a detached worktree the script creates; `engine-v0210stock`) | ~9 |
| A2 | ours, upstream's sampler tests, `prefill_fused_iq_test --v2`, server `unittest discover`, the four-backtick fence check | ~7 |
| A3 | exact7 at pin 2500, 10 sets: **release first** (s210, then p210off against it); x28h; p210a against x28h; p210b (repeat); nov2; pf133; hcr; the lookup pair L0 / L12. Conditional: s028 (if p210a is not 7/7 against P028x); the GR_FORK=0 control pair (if the greedy lookup items differ) | ~33 (+10) |
| A4 | pf_yardstick long40: p210, p210gdn, p210hcr; both KL rules. If the stack fails KL: also p210gdntc and p210gdncv with their KL rules | ~26 (+17) |
| A5 | the screen, 3 passes in turned order: B, P, L and F (with the rewrites, 4.4 min each), plus G, T and V (without them, 3.6 min each); R once | ~90 |
| A6 | Basalt's cold fixtures, 3 passes: M and H on decode, 16K and 64K; G, T and V on 16K and 64K (36 starts) | ~43 |
| A7 | the served form (chat cache, chat_drop, a picture); the live tool-call test, B vs P | ~11 |
| A8 | lossless, decision, P028x back | ~2 |

If the stack fails KL, G is not screened. T and V are then priced only if they pass KL alone, so part a is about the same
length either way.

**Part b: ~2.2 h.** Deadline 160 min.

| step | what | min |
|---|---|---|
| B1 | build the two twins (strata only, tests off, the 8-row build, the memory guard) | ~8 |
| B2 | check (2) in 1-token windows on the port twin (31) + the 3-token diagnostic (6); stock's check (2), information only (31) | ~68 |
| B3 | checks (1) + (2) on the speculative path: lookup windows off (27) and on (27) | ~54 |

`all` runs a, then b, in one gap: ~6 h. It still works, but it is not the plan.

## What each gate compares (the full rules: g17_rules.py's docstring)

### The baseline: is the pinned-off port the same as P028x?

- **First: "patched, every switch off = the release".** exact7 of `P0210x-h-off` against stock v0.2.10 must be 7/7 with
  MATCHED slots.
- **The port against P028x.** exact7 of P against x28h:
  - 7/7: bit-identical.
  - Not 7/7: stock 0.2.8 against stock 0.2.10 decides. If upstream moved too, it is INFO and the KL rules decide. If
    upstream did not move, it is a FAIL.
- **Repeat and v2.** P's repeat must be 7/7. v2 on against v2 off must be 7/7.
- **KL rules.** `kernel_rule2` AND `kernel_rule3` (with the NLL check), against gap 8's references.
- **Start lines.**
  - Present: the doorbell Q8_K, exact-sampling, cumulative-draft, cost-gate and v2 lines.
  - Absent: short of GPU memory, a PCIe start share, a lookup-12 line, graph drops, DFlash2 drafting.
  - The patch guards: 7 checked, 0 off.
- **The builds hold 8-row windows.**
- **Continuations.** The answer_room continuations resume from the session.
- **The served form:** the chat cache and a picture.
- **The tool-call test:** P's spurious calls <= B's, and P's lost calls <= B's.
- **lossless.**
- **The 14 pins.**
- **Speed:**
  - The 9-workload screen uses g16's rule: P >= B - 1.0 % on decode and on prompt, and no single workload's prompt more
    than 3 % below B; BORDERLINE between -1 % and the noise.
  - Basalt's cold fixtures use g16's rule, without the 10-30 long-prompt exception.
- **Part b:**
  - check (2): speculation off, against the twin's own 1-token reference.
  - checks (1) + (2) on the speculative path.
  - Stock v0.2.10's check (2) and the 3-token diagnostic are INFO.

### The gated switches, each against P

- **(0) The GDN stack (G).**
  - Both KL rules must pass.
  - Price: the cold 16K / 64K prompts, G against H, plus the 9-workload screen.
  - CANDIDATE: one long prompt above +max(noise, 1 %), neither below -noise, and no workload slower beyond its noise.
  - G against P028x is reported (the 10-30 cost: 16K -1.9 %, 64K -1.0 %).
  - **Each path alone (T, V):**
    - If the stack passes KL: speed only, by the same gain rule against P. CANDIDATE means the path adds a gain; NO GAIN
      means it adds nothing and can stay off.
    - If the stack fails KL: each path is KL-gated alone, and priced only if it passes.
- **(1) Lookup windows up to 12 (L).**
  - Exactness: the lookup pair.
    - exact7's 7 items through the CLI with `--suffix-draft 3`, with `--lookup-max-t 12` against `0`.
    - The 5 greedy items must be identical, with windows of 9+ rows actually used.
    - If the greedy items differ, the GR_FORK=0 control decides: WINDOW-VARIANT (the distribution checks decide), or
      FAIL if only the fork differs.
  - The lookup-12 start line must appear, with no graph drop (the VRAM against the 713 MiB reserve).
  - Continuations: as for P.
  - checks (1) + (2) with the windows on (part b).
  - No loss on the 9 workloads' geometric means.
  - **GAIN:** E1-rewrite above +max(noise, 2 %), and no workload slower beyond its noise. E2, A-edit and B-write are
    reported.
- **(2) GR_V3_PF=133 with GR_FORK=1 (F).** An identity check: exact7 7/7 plus no loss over 3 passes. There are no fork-off
  arms.
- **(3) PF_HC_REGION=1 with v2 (R).** It passes on exact7 7/7, plus 0 of 40 long40 logit files differing, plus one quick
  pass with no loss.

## The edit-turn workload: added (a frozen one existed)

- `prompts/edit.json` (09-27, `edit_compression`): a 5.9K-character Python module, returned whole with type hints.
- **E1-rewrite:** as served, with thinking on, effort medium, cap 10,240.
- **E2-rewrite-nothink:** thinking off, cap 4,096, `presence_penalty` 0 sent.
- The agent edit turn `A-edit` was already among the 9 workloads.
- The edit set runs on B, P, L, F and R; it is judged only for L.

## Still open (not writable yet)

1. **A real 9- or 12-row lookup window under the distribution checks.** arith-j3's tie never sits in one, so part b's L
   arm checks the 12-row default's machinery, not a 12-row window's draws.
   - **How to make the case:**
     1. Quote 40-60 tokens of a near-tie answer's preceding text in the prompt ("repeat this, then continue"), so the
        model copies 12+ tokens right before the tie.
     2. Keep the case only if the twin's 1-token probability of the tie token is between 0.3 and 0.7.
     3. Then run check (2) on `P0210t-ess-L12` and check (1) against `P0210t-hnospec`: about 1 h of GPU in a later gap.
2. **Never run, so the rules are untested:**
   - the twins' first compile (part b);
   - the `fence4` expectation (on a failure the gate prints what the parser returned);
   - the lookup pair's reading of the window histogram.
3. **Later gate lists:**
   - GR_R2: if upstream claims a GR_R2 gain on sm_120, put it on a later gate list.
   - Not gated in gap 17 (pinned off): QSA_FUSE_NR, IL_PAD, DF_PDL (gap 18: bitwise and no gain on P028x), PCIE_START,
     ARENA_RAM_FALLBACK, MTP_KEEP, SPILL_OFF, PENALTY_PROMPT, SMALL_UNR.
