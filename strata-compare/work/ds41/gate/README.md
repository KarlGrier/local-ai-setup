# DeepSeek V4.1 Flash gate: A (daily) vs B (5080 alone) vs C (B + Lucebox DSpark on the 4060 Ti)

Karl's gate of 11-03. The study behind it is `results/ds41/gate-5080-alone-study.md`. All paths below are relative to
`/home/USER/ai-speed-testing/strata-compare`.

Everything CPU- or disk-heavy runs **inside the gap** (Karl, 11-03). The LDR runs of 7d are live between gaps and use the
CPU for experts. So there is no separate prep step: the drafter conversion, the header re-read, the new pack,
`--pack-info` and the long prompts all run in gate.sh after `port_gap4.sh begin`.

## Status after the first gap (11-03 16:45-17:48, `results/ds41/gate-1103-1354/`)

- A and B ran.
- **B's KL check against A failed narrowly on 2 of 5:**
  - changed top-1 picks: 38, against a bound of 37.4;
  - text NLL: B is 0.007 above A, against a bound of 0.0037.
- B passes against stock v0.2.6's stored references, as A does.
- AL, BL and C did not run. `make_long.py` stopped 0.5 % short of the 64k text, and the converter passed `raw_shape`
  for quantized tensors. The user has fixed both (backups `*.before-tolerance`, `*.before-shapefix`).

## Second gap: `gap-next.sh` → `gate.sh next` (after gap 17 part b, between 7d questions)

Karl's rule for B, set on 11-04 before any result. It replaces the A-vs-A repeat, which is byte-identical by construction.
`kl_noise.py` writes it verbatim to `kl-noise/rule.txt` before any scoring:

> "compare A against two placement variants of A that happen in normal use, on the same KL harness and prompts: (a) A with
> a different VRAM expert-slot count, like the 3,238 vs 3,300 seen between starts; (b) A with the expert cache warmed by a
> different prompt first. The noise band is the largest top-1 change count and the largest NLL difference among those
> A-vs-variant pairs. B passes if both of its failing numbers fall inside that band; otherwise B stays off. The
> long-prompt memory arms and my OK are still needed before any switch."

**How the rule is applied:**
- band_top1 is the larger of Aa's and Ab's changed top-1 picks against A.
- band_nll is the larger of |NLL(Aa) − NLL(A)| and |NLL(Ab) − NLL(A)|.
- B passes when both hold, with no 1.10 factor:
  - B's 38 changed picks ≤ band_top1;
  - B's NLL distance (0.007, recomputed from the stored scores) ≤ band_nll.
- A is the first gate's A scoring, reused. kl_noise.py first checks that the engine, config, scripts, segments and
  profile snapshot are unchanged; if not, it scores A again in this gap.

**Variant (a), Aa: `--vram-experts 0.98`, which is 2 % fewer VRAM experts.**
- Karl's 3,238 / 3,300 were the Qwen engine's 5080 and 4060 Ti slots in one run, not two starts.
- DeepSeek's daily config gets the same count at every real start at 128K: 451 + 857 = 1,308.
  - We logged 9 such starts from 10-26 to 11-03: ctx-128k, long100k, lc-e50, id-old, id-new, id-old-again, slotram-test,
    sweep-ds-on-v10 and gate-A. logs/ds41/engine-daily.log shows the same count.
- The count is set at load (model.cu:3926-3958):
  - the budget is the free VRAM after weights and caches, less `--reserve-mib`, times `--vram-experts`;
  - each layer then gets floor(share x 384);
  - the profile only picks which experts fill the slots.
- It moves only with the context size: 32K 1,330, 64K 1,320, 128K 1,308. In the KL harness, at 16K, A has
  462 + 873 = 1,335.
- Since the count never varies between starts, Karl's example ratio is used: 3,238 / 3,300 = 0.981, so 2 % fewer.
  The start line reports the count actually reached.

**Variant (b), Ab: A warmed by a different prompt first.**
- The engine does move experts in and out of VRAM during a run.
  - Its adaptive cache swaps the hottest CPU-lane picks into VRAM between windows (cache_tick, model.cu:8433 / 8644).
  - A 512-token decode made 1,171 moves (teacher/cli-decode-final).
  - The cache's starting heat is the profile (model.cu:4019-4024).
- The score mode cannot take a warm-up prompt in the same process. With `DS4_SCORE_PREFIX` set it joins every segment
  into the one scored stream (ds4_main.cpp:1019-1027).
- So the warm-up goes in through the profile, which is how a prompt reaches the next start in daily use:
  - one command-line decode of the screen's W1 prompt (512 tokens), on a copy of the snapshot;
  - the engine writes its routing counts back into that copy at exit;
  - Ab's 8 segments then start from the warmed copy.
- The report gives how many profile counts changed, and whether Ab's scores differ from A's at all.

**Run order (gap-next.sh; deadline 150 min):**

| step | what | estimate |
|---|---|---|
| gap | `port_gap4.sh begin`: hold set, the running 7d question allowed to finish, the test lock taken, 8080 down. Then a kernel check. | 1 min plus the wait for the question |
| queue | When the queue's log shows "hold file: waiting" and no research run holds `run/bench.lock`, `deep-research-bench.service` is restarted once. The old and new pid and the queue's new hold line are logged. If the queue has not reached the hold within 10 min, a background watcher restarts it once it does, while the gate runs. | 0-10 min |
| KLV | Aa (~5.5 min), then the W1 warm-up (~1 min), then Ab (~5.5 min), then the verdict under the rule above. | ~13 min (+5.5 if A must be scored again) |
| long, AL, BL | Run with everything up. BL passes when L64 and L97 are both answered, no stop or swap failure occurs, and the lowest MemAvailable is ≥ 14 GB. The 13 / 12 GB lines are reported too. | ~15 min |
| CP | Conversion, header re-read, new pack and `--pack-info`, inside the gap. | 3-5 min |
| CG | Greedy identity: C0f, C1f, C2f, plus C0r if the texts differ. | ~11 min (+4) |
| C0, C1, C2 | Speed, 3 passes each. **Only if the greedy check is IDENTICAL**; otherwise this part is skipped. | ~63 min |
| end | report.md, the daily config check, `port_gap4.sh end` (P028x back on 8080, queue released), a kernel check. | ~2 min |

**Time with 8080 down:**
- **About 1 h 50 min** for everything, plus up to 10 min if the queue is slow to reach the hold.
- **About 50 min** if the greedy check fails.
- About 35 min if C does not start.

A kernel-check failure leaves the gap open, and Karl decides.

Start it with: `systemd-run --user --unit=ds41-gap-next bash /home/USER/ai-speed-testing/strata-compare/work/ds41/gate/gap-next.sh`.
Results go to `results/ds41/gate-MMDD-HHMM/`: `gap.txt` is the wrapper's log, `summary.txt` is gate.sh's, plus
`report.md` and `kl-noise/`.

The rest of this file describes the full gate (`gate.sh` with no argument). Its steps, rules and disk use apply to the
second gap's steps too.

## After the second gap (11-04, `results/ds41/gate-1104-0725/`): daily stays A

Results:
- **B's KL check passes** under Karl's noise-band rule: band 40 top-1 changes / 0.00701 NLL; B has 38 / 0.00698.
- **B fails the long-prompt memory arm.** L97 fell to 13.75 GB with the daily services up (a 9.8 GB dip), and the soft
  stop ended it. L64 stayed at 16.7 GB.
- **C's greedy check failed.** On G-P4K0, C1f and C2f leave C0f at char 126 ("... Version 2.0 text" vs "... terms"). C0r
  reproduced C0f, so the reference is repeatable.

### (5) B with a smaller RAM store: estimate (no GPU), and `gate.sh bstore`

**How much smaller.**
- At 97,001 tokens, B's one-card layer-major prompt path pins 12 chunks x 755 MB = 9.06 GB (8.44 GiB) of chunk states.
  On top of that it adds a layer cache: the largest layer's experts that are neither in VRAM nor in the store.
- L64 measured that layer cache: its 7.7 GiB dip, minus its 5.6 GiB of states (8 chunks), leaves 2.1 GiB.
- So L97's full dip is about 10.5 GiB. The 9.8 GiB seen is a lower bound, because the soft stop ended the request at
  13.7 GiB.
- Staying at 14 GiB plus a 1.5-2 GiB margin needs MemAvailable before the prompt of 26-26.5 GiB. BL had 23.5.
- A store slot is 10.3 MB and holds on average a 7.8 MB expert (49.4 GB for 6,363 experts; untouched pages are not
  resident). So 1 GB less `--ssd-cache` frees about 0.75 GB.
  - A smaller store also adds about 2.5 % of the cut back to the layer cache.
- **Result: `--ssd-cache` 64 frees ~3.0 GB; projected L97 lowest ~15.8 GiB. 62 frees ~4.5 GB; projected ~17.2 GiB.**
  - About ±1 GB of uncertainty: L64 started 0.9 GB higher than L97.
- A full ~128K prompt (16 chunks, a ~13.4 GiB dip) would need about 59-60 GB.

**What it costs.** No B data exists at other store sizes, so these figures come from two-card (A-type) runs.
- 10-26 (v0.2.6, 10/30, 1 pass):
  - 66 GB: 27.74 tok/s, 0.0885 SSD GB / token;
  - 68 GB: 27.69 tok/s, 0.0845;
  - 74 GB: 27.99 tok/s, 0.0759.
- 10-24 (v0.2.4, 2 passes): 48 GB 19.34, 60 GB 21.22, 70 GB 22.64 (0.6-0.8 % per GB).
- 10-25 screen: 74 vs 70 GB, +2.9 %.
- Range: 0-0.8 % decode per GB and ~2.5 % more SSD reads per GB.
  - **64 GB: decode 0 to -3 %**, SSD reads +~10 %.
  - **62 GB: 0 to -4.5 %**, SSD reads +~15 %.
- 62-64 GB lies inside the measured 48-76 GB range. The open question is the transfer from two cards to one card: B has
  711 VRAM experts against A's 1,308, so the per-GB effect on B is probably similar or a little larger.
- B's own decode (28.12) is level with A's (28.05). At 64 GB, B would sit between level and ~3 % below A, and keep its
  prompt gains (P4K +34 %, P20K +6 %). P20K's speed depends on the drive more than on the store.
- The cost is small enough to measure, so here is the gate.

**`gate.sh bstore`** (configs `DS41-gate-B64.json` and `DS41-gate-B62.json`: B with `--ssd-cache` 64 / 62, written by
make_configs.py; the A, B and noise-band results are linked in from the first two gates):

| step | what | estimate |
|---|---|---|
| BSL | Everything up, then BL64: warm-up, P20K, L64, L97. The arm passes when both prompts are answered, nothing stops, and the lowest MemAvailable is ≥ 14 GB (bl_verdict.py). If BL64 fails, BL62 runs. | ~7 min (+6 for 62) |
| KLBS | The passing size on the KL harness vs A, judged by Karl's noise band (40 / 0.00701; kl_bstore.py). It may be byte-identical to B, since the store changes only where bytes come from. | ~5 min |
| BSS | That size's speed, 3 passes, against A and B. | ~20 min |

**Time with 8080 down: ~35 min (~41 if 62 is needed), plus ~3 min to open and close the gap.** Deadline 90.

### (6) C's divergence: the near-tie check, and `gate.sh csample`

The greedy runs kept only text, so the top-2 log-probabilities have to be measured.
`tie_check.py` does it on C's frozen placement exactly as C0f / C1f ran, through `cliarm.sh`, which keeps the config's
`--dspark` / `--no-expert-cache` / `--max-context` as the server passes them:
1. It renders G-P4K0 with the server's own template code. The result must be the 4,115 tokens C0f logged.
2. It decodes 512 tokens greedily on C0f's and on C1f's configs. The C0f text must equal the served one; that line is
   then the first divergent token j.
3. It scores the prompt plus C0f's tokens teacher-forced:
   - with `--window 1`: C0f's path, so its top-1 must equal C0f's token at every position;
   - with `--window 2` at both alignments: C1f's 2-row verify windows.
   - It reports the top-64 at every generated position up to j.

**"Within rounding" is defined before looking** and written to `tie/rule.txt`. The gap is measured in C0f's own numbers:
logprob(C0f's token) − logprob(C1f's token) at j. It must be ≤ **4.331 nats**.
- That is the largest gap among the 69 top-1 flips that A's placement variants Aa / Ab caused against A in the KL harness
  (median 0.20, p90 0.59), computed from the stored scores.
- The largest is used because Karl's noise band for B takes the largest pair. A gap that rounding-level changes of A
  did overturn is one rounding can overturn.

**`gate.sh csample`** (CP first, which checks and does not redo):

| step | what | estimate |
|---|---|---|
| TIE | The near-tie check above: 2 decodes and 3 short scorings, ~25-60 s each. | ~5 min |
| C0, C1, C2 | **Only if within rounding:** speed with our normal sampling (T 1.0 / 0.95 / 20 / min-p 0.05), 3 passes each. report.py adds the drafter's acceptance under sampling. | ~63 min |

If C1 or C2 beats A's decode beyond the noise, the report says so. Karl's next step would then be the sampled
distribution harness and a 1017-matched drafter proposal; neither is built until Karl says so.

**Time with 8080 down: ~1 h 15 min, or ~10 min if the gap is not within rounding**, plus ~3 min to open and close. Deadline 120.

Both modes can share one gap: `GATE_STEPS="BSL KLBS BSS TIE C0 C1 C2" GATE_DEADLINE_MIN=150 gate.sh csample`, about 1 h 50 min.
`gap-next.sh` runs `gate.sh next`. For these modes, start gate.sh directly (it opens and closes its own gap), or adapt the
wrapper's last call.

### (7) 11-05 csample: the command-line path did not diverge; 11-06 the served-path rerun

**11-05 result** (`results/ds41/gate-1105-2032-csample/`, 23:24-23:26, 2 min with 8080 down; dated note
`NOTE-1106-cli-no-divergence.md` there):
- TIE exited 2, with no verdict.
- C0f's command-line decode reproduced its served text.
- **C1f's command-line decode did not leave C0f's within 512 tokens:** all 512 ids are identical, and `engine.stdout`
  is byte-identical between the two.
- On 11-04 the served C1f left C0f at char 126.
- C0-C2 were skipped.
- What the served runs had that the command line lacked:
  - G-P4K0 was the third request on one server, after G-W1 and G-W2;
  - the drafter's counts differ (served 205 offered / 192 kept, command line 200 / 184).

**Karl 11-06:** "C rerun: (a). Run the near-tie check through the served path, where the divergence appeared. Record that
the command-line path didn't diverge within 512 tokens. Add it to the series as a step after the Basalt rerun, between
questions. If it needs more than about 90 min with 8080 down, tell me first."

**The rerun: `gap-ctie-served.sh` + `tie_served.py`.** Written 11-06, not run, no `.ready` yet. Details are in
`CTIE-SERVED-1106.md`.
- **The rule is unchanged.** tie_served.py rebuilds it with `tie_check.threshold()`. It refuses unless the text equals
  the 11-05 `tie/rule.txt` byte for byte.
- **Only where the divergence is found changes:**
  - C0f and C1f run served, as 11-04's CG step ran them: tunearm.sh + greedy_client.py, G-W1, G-W2, G-P4K0 on one
    server each.
  - `STRATA_DEBUG=1` makes server.py print the generated ids. The engine binary has no such string.
  - j is taken from those ids.
- **tie_check's own scoring then runs on cfg-C0f** (window 1 decides, window 2 is reported).
- **Exits are tie_check's:** 0 within rounding, 1 not, 2 could not run or reproduce, 3 kernel error.
- **On 0, C0-C2 run under sampling in the same gap** (`gate.sh csample` with `GATE_STEPS="C0 C1 C2"`), but only if
  ≥ 68 min are left of the 90.

**Time with 8080 down:** ~10 min without a pass, ~1 h 15 min with one. Capped at 90 min.

## Files

| file | what it does |
|---|---|
| `configs/DS41-gate-{A,B,C0,C1,C2}.json` | Written by `make_configs.py` from `DS41-daily.json`, which is only read. |
| `work/ds41/gate/gate.sh` | The whole gate, as one user unit; `gate.sh next` runs the second gap. |
| `work/ds41/gate/kl-b.sh` | B vs A KL check. Runs inside gate.sh's gap, or on its own in a later gap (`kl-b.sh gap`). |
| `gate_speed.py`, `greedy_client.py` | The clients that tunearm.sh starts. |
| `kl_b.py`, `greedy_compare.py`, `report.py` | The checks and the report. |
| `kl_bstore.py`, `bl_verdict.py`, `tie_check.py`, `cliarm.sh` | gate.sh bstore (B with a smaller store) and csample (C's near-tie check), 11-04. |
| `kl_noise.py` | The second gap's KL noise band (A vs Aa / Ab) and B's verdict under Karl's 11-04 rule (`gate.sh next`, step KLV). |
| `gap-ctie-served.sh`, `tie_served.py` | 11-06 (Karl's (a)): the near-tie check through the served path, in its own gap. tie_check.py's rule is unchanged; the first divergence comes from served C0f / C1f runs. C0-C2 follow a pass. `CTIE-SERVED-1106.md`. |
| `gap-next.sh` | The second gap's wrapper: opens the gap, restarts the bench queue once, runs `gate.sh next`, ends the gap. |
| `check_converted.py`, `compare_packs.py`, `make_long.py`, `make_configs.py` | Helpers that gate.sh calls. |
| `convert_lucebox_dspark.py`, `gguf_header.py`, `get-lucebox-dspark.sh` | Already there (the user's). |

## The arms

A test arm differs from `DS41-daily.json` only in these three things:
- `log` is the test log that tunearm.sh reads.
- `--expert-profile` is `logs/ds41/gate/profile-arm.bin`. This is a fresh copy of one snapshot of
  `logs/ds41/daily-profile.bin`, taken at the gap's start and copied again before every arm.
- `STRATA_DS4_SLOT_DIR` is `logs/ds41/gate-slots/<arm>`, emptied before each arm. The daily `logs/ds41/ds4-slots` is
  never used.

The arms:
- **A**: the daily config. 4060 Ti first, DS4_SPLIT 8,32, `--tp 2`. `--dspark auto` does not load the drafter.
- **B**: the 5080 alone.
  - `CUDA_VISIBLE_DEVICES` is the 5080 only, `--tp 1`, no DS4_SPLIT, `--vram-experts 1.0`.
  - `--experts 6` and `--prefill-chunk 8192` stay pinned.
  - `need_vram_mib` is 15400.
- **C0 / C1 / C2**: the new pack `pack-ist-das-2.00bpw-lucebox-q2k`.
  - The pack is the daily pack's index with the converted Lucebox Q2K/Q4K drafter as file 5. `compare_packs.py` checks
    that nothing else differs.
  - DS4_SPLIT 0,40, so all 40 trunk layers sit on the 5080. The drafter goes on the first device, the 4060 Ti.
  - `--vram-experts 1.0`, `--dspark-conf 0.65`, `--tp 2` as daily.
  - C0 runs `--dspark off`: the drafter is loaded and never used.
  - C1 runs `--dspark on --dspark-block 1`. C2 runs `--dspark on --dspark-block 2`.
- **C0f / C1f / C2f / C0r**: C0 / C1 / C2 plus `--no-expert-cache`. gate.sh derives them into the run folder.
- **AL / BL**: A's and B's configs, each with its own slot folder.

## Run order (gate.sh, `GATE_STEPS="A B KL AL BL CG C0 C1 C2"`)

| step | what | estimate |
|---|---|---|
| before | Cheap checks only. `make_configs.py` must reproduce the five configs, and DS41-daily.json's sha256 is recorded. gate.sh refuses to start if a strata-dsv41 is running, `tmp/gpu-test.lock` is held, or `get-lucebox-dspark.service` is running or waiting (it would write to the model drive during the arms). | seconds |
| 0 | `port_gap4.sh begin`: the queue is held after the running research run, the test lock is taken, 8080 is stopped. Then a kernel check and the profile snapshot. | 1 min plus the wait for a research run |
| A | Speed: 3 passes of W1-W3 decode, 3 x P4K, 3 x P20K (PASSES=3, NPROMPT=3). | ~21 min (10-26 ctx-128k reference: 20.8 min) |
| B | The same. | ~20 min |
| KL | `kl-b.sh inside`: 4 configs x 8 teacher-forced segments. Skipped if under 45 min are left. | ~22 min, up to ~40 |
| long | `make_long.py` builds the ~64K / ~97K prompts with DeepSeek's tokenizer. This runs once; the result is kept in `scratch/`. | 1-3 min |
| AL, BL | Run with **everything up** (see below). Each arm: warm-up, one P20K (fills the RAM store), L64, L97. | ~6 + ~6 min, plus 0.5-1.5 min to bring the services up |
| CP | C's files. Lucebox's download is checked (size and sha256). If it is missing, every C step is skipped. Then the conversion (`--plan`, then the real write), the header re-read (`check_converted.py`, `gguf_header.py` on the first 16 MiB), the new pack (pack_gguf.py, the daily recipe, plus `compare_packs.py`), and `--pack-info` (host only; run with no GPU visible, and with the GPUs only if that fails). | 3-5 min |
| CG | C0f, then C1f and C2f: greedy at temperature 0, frozen placement, text for text against C0f. If the texts differ, C0r repeats C0f. C0f is also C's start check. | ~11 min (+4 for C0r) |
| C0, C1, C2 | Speed as for A, 3 passes each. C1 and C2 also log the drafter's acceptance. **Skipped unless the greedy check is IDENTICAL.** A non-exact C cannot be adopted, so the gate ends early. | ~63 min |
| end | `report.py` writes report.md. Then the daily config's sha256 is checked, the ballast is released, `port_gap4.sh end` runs (P028x back on 8080), and a final kernel check. | ~2 min |

**Time with 8080 down:**
- **About 2 h 40 min** for everything (range ~2 h 30 min to ~3 h 10 min).
- **About 1 h 40 min** if the greedy check fails: C0 / C1 / C2 are skipped.
- **About 1 h 20 min** if Lucebox's file is not there: only A, B, KL, AL and BL run.

How the arm estimates were made:
- Today's sweep took 8.6 min for a 1-pass arm. 3 passes add two more W1-W3 rounds (~4.9 min each at ~28 tok/s) and
  2 x (P4K + P20K). That makes ~20-21 min, the same as the 10-26 3-pass A arm.
- Deadline: no new step starts after `GATE_DEADLINE_MIN` (210 min).

Why this order:
- A, B and the KL check come first because B needs all of them before any switch to B.
- The long prompts get their own arms, after the KL check, so that a memory stop or a kernel event there cannot cost the
  speed arms or the KL check.
- C goes last. It is the probe.
- A later gap can rerun only part of the gate, for example `GATE_STEPS="CG C0 C1 C2"` or `kl-b.sh gap`.

## The long prompts' memory load (AL, BL)

These two arms run with the daily services' memory load, so the MemAvailable lows are the real ones. This is what
ctx128.py's 10-27 97K run did ("everything up").
- **SearXNG 8889/8890:** `searxng-ldr.service` and `searxng-ldr-baseline.service` must be up. gate.sh starts them if
  they are not. It stops afterwards only the units it started itself.
- **The ballast:** `ballast.py` holds LDR's 3.54 GiB plus SearXNG 8889's 1.74 GiB, less what those two already hold at
  that moment (measured by `svcmem.py`).
  - This is ctx128.py's own sizing, `3.54 + max(0, 1.74 - SearXNG's RSS)`. ctx128.py's version assumed LDR was stopped;
    here LDR's web process may be up, so its own RSS counts toward the 3.54.
  - If no reading comes back, the ballast is the full 5.28 GiB.
  - The ballast is released on every exit, including a kernel stop.
- **The guards stay as they are:** 12 GB hard stop, 14 GB soft stop, and the swap rule.
  - For A this fits. The 10-27 97K run with exactly this load had its lowest point at 18.9 GB.
  - For B, the study projects a ~9-11 GB transient at 97K, so B's L97 is expected to reach the soft or the hard stop.
    That would be the finding, not a reason to shrink the ballast, so the ballast is not resized.
  - The ballast's pages are idle memory and can be swapped out under pressure. The swap rule then judges the run, as it
    did in the 10-26 daily memory runs.

## Rules every arm obeys (tunearm.sh, unchanged)

- Memory:
  - Hard stop: MemAvailable < 12 GB kills the engine.
  - Soft stop: MemAvailable < 14 GB (`SOFT_GB=14`, as today's sweep) stops the server.
  - The 10-26/27 swap rule: any engine VmSwap fails the run, and so do swap-in/out streaks of 4 MB or more after the
    first push-out.
- VRAM: the 5080 must keep at least 300 MiB free.
- Kernel checks before, during (every ~60 s) and after each arm, and after CP. A failure stops the gate with the gap
  **open** and logs ktriage.py's verdict, as sweep-gap.sh does.
- Cold start: the model files are dropped from the page cache (dropcache.py, plus the Lucebox and converted files). The
  drive must cool to 50 C or below, with at least 60 s of cool-down.
- Isolation:
  - Servers start with `8>&- 9>&-`.
  - tunearm refuses to start if port 8085 is busy or a strata-dsv41 is already running.
  - The engine is found by name or by `/proc/PID/exe`, and the ballast by its PID; never by a command-line pattern.
- Sampling:
  - Speed and long prompts use T 1.0 / 0.95 / 20 / min-p 0.05. W1-W3 use effort medium, as every earlier arm did.
  - The greedy check uses temperature 0, which is the point of that check.
- The KL scoring runs (scorearm.sh) have their own guards: 12 GB, the 5080's 300 MiB, kernel checks, and 900 s per
  segment.

## Disk use

- The converted drafter is about 4.9 GB, written read-only in `lucebox-dspark/`. Lucebox's 4.92 GB download stays as it is.
- The new pack index is about 9 MB.
- `scratch/` holds the long prompts (~1 MB). A 16 MiB header cut is made there and removed straight away.
- Results take about 25 MB: the arm folders (~0.3 MB each), the KL scores (~4.3 MB per config) and `prep/` logs.
- The slot folders in `logs/ds41/gate-slots/` are capped at 2 GB each. Expect about 1 GB in total. They can be deleted
  after the report.
- The model drive has 165 GB free now. The conversion needs at least 111 GB free.

## Starting it

1. Wait until `get-lucebox-dspark.service` has finished. Its log is `logs/ds41/get-lucebox-dspark.log`. If the download
   failed, the gate still runs A, B, KL, AL and BL.
2. Tell Karl the time. Then start the gap as a user unit:
   `systemd-run --user --unit=ds41-gate bash /home/USER/ai-speed-testing/strata-compare/work/ds41/gate/gate.sh`.
   Check that the unit, its pid and the first summary line exist.
   - The results go to `results/ds41/gate-MMDD-HHMM/`: `summary.txt`, `report.md`, one link per arm, `kl/`, `prep/`,
     `svcmem.jsonl` and `c-status.json`.
   - `GATE_STEPS`, `GATE_DEADLINE_MIN` and `GATE_OUT` can be set on the unit with `--setenv`.

## Choices made here that Karl may want to change

- **Greedy runs in frozen arms.** The greedy check runs in separate arms with placement frozen (`--no-expert-cache`),
  not as requests inside the adaptive C arms.
  - In the adaptive arms, the drafter's verify windows change the routing counts. That moves different experts between
    VRAM and the CPU lane. Rounding-level variants flip ~1.5 % of top-1 picks (10-26: ~30 of 2,040 positions), so the
    512-token greedy texts would almost surely differ for reasons that have nothing to do with DSpark.
  - With the placement frozen, the 10-24 test gave identical text on three fresh engines.
  - Cost: ~11 min.
- **The greedy rule for running C's speed arms.** They run only on IDENTICAL.
  - "NOT SHOWN" (C0r differs from C0f, so the reference itself is not repeatable) skips them too.
  - So does "INCOMPLETE" (a greedy run is missing).
- **A kernel-check failure stops the gate with the gap open.** This is sweep-gap.sh's rule. The 10-25 automatic drop for
  a page-allocation failure alone is not applied, but the ktriage verdict is logged.
- **The KL check may not cover B's layer-major path.** The 12,000-token prefix (the round's long8 segments) is 2 chunks,
  and lm_begin's cost test (model.cu:8113) may stream it chunk by chunk instead.
  - kl_b.py adds the print-only `DS4_FLOW_STATS=1` and reports how many of B's 8 segments ran layer-major.
  - If none did, covering that path needs a 3-chunk prefix, and that means raising scorearm.sh's fixed
    `--max-context 16384`.

## Checks done while writing

Only static checks: `bash -n` on gate.sh and kl-b.sh, and `py_compile` on the Python files.
`make_configs.py` was run once to write the five configs. It only reads `DS41-daily.json`, whose sha256 is unchanged:
5a8ccd8a...
Nothing else was run, started, converted or downloaded.
