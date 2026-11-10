# C's near-tie check through the served path (gap-ctie-served.sh, 11-06)

**Status:** written 11-06 and not run. There is no `.ready` file yet; Claude reviews it first. Nothing here started an
engine, a server or a GPU query.

Karl's decision on the 11-05 csample gap, verbatim:

> "C rerun: (a). Run the near-tie check through the served path, where the divergence appeared. Record that the
> command-line path didn't diverge within 512 tokens. Add it to the series as a step after the Basalt rerun, between
> questions. If it needs more than about 90 min with 8080 down, tell me first."

**Time with 8080 down: about 10 min if C does not pass, about 1 h 15 min if it does.** The driver caps it at 90 min.
That is under Karl's ~90 min, so it does not need his OK first. See the time section below.

## Why: what 11-05 showed

The record is in `results/ds41/gate-1105-2032-csample/NOTE-1106-cli-no-divergence.md` and in README section (7).
- tie_check.py's command-line C0f reproduced 11-04's served C0f text.
- Command-line C1f gave the **same 512 ids** as C0f. Its `engine.stdout` is byte-identical.
- So no divergent token was found. The result was exit 2, with no verdict, and C0-C2 were skipped.
- On 11-04 the served C1f left C0f at char 126 of G-P4K0. There, G-P4K0 was the third request on the server, after
  G-W1 and G-W2.
- The drafter's offers also differ between the two paths:
  - served C1f: 205 offered, 192 kept;
  - command-line C1f: 200 offered, 184 kept.

## What the driver does

`work/ds41/gate/gap-ctie-served.sh` runs in one gap: `work/r22/port_gap4.sh begin` … `end`.

| step | what | 8080 down |
|---|---|---|
| 0 preflight (exit 1, 8080 untouched) | Refuses unless all of these hold: no strata-dsv41 running; `tmp/gpu-test.lock` free; no gap open; port 8085 free; the Lucebox download not running; the engine's sha256 = its SHA256 file; C's files present; `make_configs.py` reproduces the gate configs; `tie_served.py selftest` passes. It then derives `cfg-C0f` / `cfg-C1f`, which must equal 11-04's except for their own slot folders `logs/ds41/gate-slots/ctie-C0f` / `ctie-C1f`. Last, it writes `tie/rule.txt` (the frozen text) and `tie/where.txt`, before any engine run. | – |
| 1 gap | port_gap4.sh begin (the running question finishes first), a kernel check. The converted drafter's sha256 must be 11-05's, and the new pack's file 5 must be the converted drafter. | ~0.3 min |
| 2 served C0f, C1f | Each arm runs exactly as 11-04's CG step: `tunearm.sh` with all its guards, plus `greedy_client.py`. The client sends G-W1, G-W2, G-P4K0 to one fresh server, with thinking off, temperature 0 and 512 tokens. Each arm gets the 11-04 snapshot b54bd76a, cold model files and its own emptied slot folder. The client first runs `tie_served.py envcheck` on the engine; a mismatch means no request is sent. A kernel check follows each arm. `greedy_compare.py` then compares the two arms, for the record. | ~2.75 + ~2.6 min |
| 3 TIE (`tie_served.py judge`) | First the reproduction checks (below). Then j is taken from the served ids, and tie_check's own three scorings run on cfg-C0f through `cliarm.sh`. Each scoring engine's env is watched by `/proc/PID/exe`, and a mismatch is stopped by its PID. The frozen rule is applied at j, and the results go to `tie/tie.md`, `tie.json` and `served.json`. A kernel check follows. | ~2-3 min |
| 4 C0, C1, C2 | **Only after exit 0**, and only if ≥ 68 min of the 90 are left. Runs `gate.sh csample` with `GATE_IN_GAP=1 GATE_STEPS="C0 C1 C2"`: speed under T 1.0 / 0.95 / 20 / min-p 0.05, 3 passes each, plus the drafter's acceptance. CP is checked, not redone, and report.py runs. The deadline it gets leaves no arm starting with under 22 min to the cap. | ~64 min |
| 5 end | Checks that DS41-daily.json is unchanged. Then port_gap4.sh end (P028x back, the queue released) and a kernel check. | ~0.5 min |

**Exits:**
- 0: done. The outcome is in `tie/tie.md` and `gap.txt`.
- 1: refused before the gap opened (8080 untouched).
- 3: a kernel-check failure. The gap stays open and Karl decides.
- 4: port_gap4.sh end failed.

**Results** go to `results/ds41/gate-MMDD-HHMM-ctie/`: `gap.txt`, `selftest.txt`, `cfg-C0f.json` / `cfg-C1f.json`, the
`C0f` / `C1f` arm links and `tie/`. After a pass they also hold gate.sh's `summary.txt`, `report.md` and the C0-C2 links.

**Conventions:**
- `set -u -o pipefail` and `exec 8>&- 9>&-`; children also get `8>&- 9>&-`.
- Every `STRATA_` / `DS4_` / `DSV4_` / `GGML_` variable is unset at the start.
- Engines are found by exact name or `/proc/PID/exe` only.
- No `cd`, no sudo.

## The rule is unchanged; only where the divergence is found changes

**The rule.**
- tie_served.py imports tie_check.py, which is not edited.
- It builds the rule text with tie_check's own `threshold()` and tie_check's own words.
- Unless that text equals `results/ds41/gate-1105-2032-csample/tie/rule.txt` byte for byte, nothing runs: preflight
  exit 1, or judge exit 2.
- So the rule stays: **gap ≤ 0.5883 nats (the p90) decides**, and the max, 4.3312, is reported beside it.
- The measurement is tie_check's:
  - teacher-forced scoring of the prompt + C0f's ids up to j + 2, on cfg-C0f, with `DS4_SCORE_PREFIX` set;
  - `--window 1` decides; `--window 2` at both alignments is reported;
  - the top-64 at every generated position up to j.

**Where the divergence is found:**
- j = the first index where the served C1f's G-P4K0 ids leave the served C0f's.
- The ids come from server.py itself: with `STRATA_DEBUG=1` it prints `[strata] raw ids: [...]` per request.
  - server.py reads `STRATA_DEBUG` in 2 places, both prints.
  - The engine binary contains no `STRATA_DEBUG` string, so the engine cannot read it.
  - The selftest checks both points.
- This is the one addition to 11-04's served arms. The other difference is the slot folder's name.

**Reproduction checks (any miss = exit 2, no verdict):**
- Both arms' env checked OK, with no guard and no soft stop.
- All three requests answered, in order.
- Three id lines printed, each decoding to its streamed text.
- The placement lines equal 11-04's: the CUDA0 / CUDA1 layers and expert counts, the CPU lane, experts per word.
- **C0f's G-P4K0 text = 11-04's.**
- **C1f leaves C0f** within its 512 tokens.
- If C1f leaves at a place other than char 126, the check goes on. The rule is applied at this gap's first divergence,
  and tie.md says so.
- Also reported:
  - whether C0f's served ids equal 11-05's command-line ids;
  - whether C1f's text equals 11-04's;
  - the G-W1 / G-W2 comparison;
  - the drafter's counts.

**Two validity conditions.** Neither changes the threshold or the definition. Each gives exit 2, where tie_check.py
would have said 1:
- there is no window-1 row at j;
- C1f's token is outside the scored top-64, so the gap is only a lower bound, and that bound is ≤ the threshold.

**Env checks.** Every engine is checked, served and scoring alike, by `/proc/PID/exe`:
- every config env key must match exactly;
- the served engine must also have `STRATA_DEBUG=1`; the scoring engines must have `DS4_SCORE_PREFIX=` the prompt
  length (or +1);
- no other `DS4_` / `DSV4_` / `STRATA_` / `GGML_` key that the binary can read may be set. Keys it cannot read are
  noted only.
- argv must be the config's args in order: after `--serve` for the served engine; with `--vision off` plus the scoring
  args for a scoring engine.

## Time with 8080 down (from the earlier gates' measured steps)

| part | measured | estimate |
|---|---|---|
| open: kernel check, C's file checks | 11-05 CP took 4 s in all | ~0.3 min |
| served C0f, C1f | 11-04 CG: C0f 09:49:58-09:52:43, C1f 09:52:43-09:55:20 (with the 60 s cool-down) | ~5.4 min |
| TIE scorings (3 runs) | 11-05: command-line runs of 49 / 44 s each, with ~26 / 23 s of 512-token decode. A scoring reads the same 4,115-token prompt plus ~30 rows. | ~2-3 min |
| end: port_gap4.sh end + kernel check | 11-04 and 11-05: 22 s | ~0.5 min |
| **no pass (exit 1 / 2)** | | **~9-10 min** |
| C0, C1, C2 (3-pass speed arms) | 11-03: A 16:45:18-17:06:53 (21.6 min), B 17:06:53-17:27:49 (20.9 min) | ~64 min |
| **pass** | | **~74-76 min (~1 h 15 min)** |

**The cap is 90 min (`CT_MAX_MIN`):**
- C0-C2 start only if ≥ 68 min are left after TIE.
- gate.sh's deadline then stops any arm from starting with under 22 min to the cap.
- So the worst case is about 90 min, plus a slow drive cool-down. tunearm waits until the drive is ≤ 50 C; every gate
  arm so far needed only the 60 s minimum.
- If the TIE part ran long and C passes, C0-C2 are not squeezed in. gap.txt says they need their own gap: about 65 min
  plus ~3 to open and close, using `gate.sh csample` with `GATE_STEPS="C0 C1 C2"`.

## What follows each outcome

- **0, within rounding (p90):**
  - C is not disqualified, so C0-C2 run under our normal sampling in the same gap.
  - report.py writes section 8 (the near-tie) and the drafter's acceptance under sampling.
  - If C1 or C2 beats A's decode beyond the noise, Karl's next step is the sampled distribution harness and a
    proposal for a 1017-matched small drafter. Neither is built until Karl says so.
  - Otherwise there is no harness and no proposal. DeepSeek stays on A in both cases until Karl decides.
- **1, not within rounding:** C stays out (not exact, and not a rounding-level tie). C0-C2 are not run. DeepSeek stays
  on A.
- **2, no verdict:** this covers a non-reproduced divergence (for example, the served C1f did not leave C0f this time),
  a failed run, an env mismatch, or a validity condition. tie.md says which. C0-C2 are not run, and Karl decides.
- **3, kernel error:** the gap stays open, 8080 is down, and Karl decides.

**Known display issue, not changed:** report.py section 8 prints "rule: <= {rule_max_gap}", which is the max, 4.3312.
Its "within rounding" word, though, is the p90 verdict. `tie/tie.md` states both correctly.

## Adding it to the series (Karl: after the Basalt rerun, between questions)

- In `work/r23/gap-series.sh`, add `work/ds41/gate/gap-ctie-served.sh` to `STEPS` after `work/r23/gap-basalt-fix.sh`.
  Use no `+` prefix, so a question runs in between.
- The series runs it only once `gap-ctie-served.sh.ready` exists. That file is written after Claude's review.
- The series is running now. Bash reads a script as it goes, so do not edit the running file in place. Use the
  restart-waiter route used before (the `gap-series.sh.before-*` backups).

## Checks done while writing (no engine, no GPU)

- `bash -n gap-ctie-served.sh`: OK.
- `tie_served.py` parses.
- `tie_served.py selftest` was run under `work/r23/nogap-run.sh` after the ud31 gap closed. It took about 1 s.
  - **SELFTEST OK** (`scratch-ctie/selftest-1106b.log`). The first run's only failure was a wrong expected value in a
    synthetic test (14, not 13); the code was right.
  - The rule rebuilt by tie_check is byte-identical to the frozen text: p90 0.5883, max 4.3312.
  - G-P4K0 renders to 4,115 ids, equal to 11-05's.
  - 11-04's char-126 divergence is confirmed, and C0r = C0f.
  - 11-05's command-line C1f = C0f at all 512 ids.
  - Both configs derive as 11-04's, but for their slot folders.
  - The engine's sha256 matches its SHA256 file, and the binary has no `STRATA_DEBUG` string.
  - All synthetic env and verdict cases come out as intended.
  - Char 126 falls in generated token **33**, so a reproduced served divergence should give j = 33.
- The modes were exercised in `scratch-ctie/modes/`:
  - `rule` wrote a `rule.txt` that is byte-identical to the 11-05 one;
  - `derive` wrote C1f; given a wrong source (C2), it refused with exit 1;
  - `judge` outside a gap refused with exit 2 and ran nothing.

## Files

- `work/ds41/gate/gap-ctie-served.sh`: the driver (new).
- `work/ds41/gate/tie_served.py`: the separate mode (new). It does not change tie_check.py.
- `results/ds41/gate-1105-2032-csample/NOTE-1106-cli-no-divergence.md`: the 11-05 record (new).
- `work/ds41/gate/README.md`: section (7) and the Files table updated.
