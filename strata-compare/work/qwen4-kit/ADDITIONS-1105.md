# Qwen4 day-one kit: Karl's four additions (11-05 evening)

Written 2026-11-05, before any Qwen4 release.
- No GPU was used. The only GPU contact was a read-only `nvidia-smi -L` to confirm the UUID order.
- No server was started or stopped, no gap driver or gate component was run, and nothing was queued or posted.
- Heavy runs went through `work/r23/nogap-run.sh`, and scratch stayed in `work/qwen4-kit/scratch-e/`.
- Hugging Face: one API call (repo metadata) and two range reads of 128 KiB each (262,144 bytes in total). There was
  no token, and no request was refused.

## What changed

| file | change |
|---|---|
| `dayone.py` | sections 9-14 are new: the pre-check, the n-gram placement, publishers + the comparison, `fit`, `dense`, and the selftest / dry run. `plan` dispatches per publisher. `list_repo` survives an unpublished repo. `prefer_default` now goes through `v31_default`. `kl_driver` gets `name` / `no_base` / `force_base`. `write_driver` takes the kinds `speed_ab`, `exact_dense` and `speed_dense`. `--dest-root REPO=DIR` and `--scratch` are new. `local_candidate` reads `NAME.size` |
| `q4_rules.py` | new: `densecheck`, `uvidecide`, `speeddecide --tag`, cfgcheck's dense rules, and the U-vs-ISTA and DENSE rule sections in the docstring |
| `README.md` | a new section, "dayone.py: Karl's four additions" |
| backups | `dayone.py.before-1105e`, `q4_rules.py.before-1105e`, `README.md.before-1105e` |

**Existing behaviour is kept.**
- `dayone.py dryrun` (rerun into `scratch-e/dryrun-orig`) reproduces the 11-05 dry run's picks, slot counts and prefer
  variants. All six drivers are identical once timestamps and paths are normalised.
- Configs differ only in the `_dayone` note block: a new `ngram_placement` line and the time.
- The existing `selftest` passes, and so does `q4_rules.py selftest`.
- One deliberate fix: `prefer_default` read `kl_U_class` first. That would have turned a loss RECORDED AS INCLUDES PACK
  ROUNDING into "ista", against Karl's frozen rule. Today nothing changes, because decision.json does not exist yet.

## 1 Quant timing

- **Unpublished repos.** `plan --repo <unsloth> --repo <ista>`: a repo that is not out yet (HF 401 / 404, or 403
  recorded as a refusal) is listed as NOT AVAILABLE. The plan goes on.
- **One plan per publisher.** Each publisher gets its own plan (Karl's rule inside it) in `DIR/unsloth/` and `DIR/ista/`.
- **The default.**
  - One publisher out: that one ("take whichever is available first").
  - Both out: the v3.1 result decides, through `v31_default`. It reads `results/r23/ud31/decision.json` + `.txt` and
    `dec/decision.json` + `.txt` by ud31_rules.py's own rules:

    | v3.1 result | default |
    |---|---|
    | `kl_U` BETTER THAN P | unsloth |
    | INCLUDES PACK ROUNDING, then the follow-up says BETTER THAN P | unsloth |
    | INCLUDES PACK ROUNDING, then the follow-up says WORSE THAN P | ista |
    | INCLUDES PACK ROUNDING, then the follow-up says INCONCLUSIVE | NO DIFFERENCE: Karl's size rule; a tie goes to the comparison |
    | missing / NOT JUDGED / the .json and .txt disagree | PENDING: the first one out stays the default |

  - U's v3.1 exactness and speed lines are printed as flags beside the result.
- **The comparison.** When both are out, `DIR/uvi/` gets two drivers:
  - `gap-<name>-uvi-kl.sh`: the KL rules against R. With two new files it gives the pair verdict. A new file against
    the served file runs as X vs P, as in gap-ud31.sh.
  - `gap-<name>-uvi-speed.sh`: the screen A vs B, the no-loss rule both ways, then `uvidecide` writes
    `decision-uvi.txt`. That file re-reads the default when it runs and says CONFLICT if the comparison points the
    other way.
  - Plus `QUEUE.txt`. No `.ready` file is written.
- **The watcher.** With one publisher out, PLAN.md prints the `dayone.py watch` line and its systemd timer form (not
  installed).
- **To queue the comparison:** Claude reviews both drivers and writes `<driver>.ready`. Then the two paths go into the
  STEPS of the next series start (a restart waiter as `work/r23/series-restart-after-*.sh`), with one question between
  them.

Dry run (`scratch-e/dryrun/arrival-1`, then `arrival-2`):
- **Stage 1** (Unsloth v3.1 listing; ISTA simulated absent): FIRST AVAILABLE, unsloth UD-IQ3_XXS (46.84 GiB of experts).
- **Stage 2:** `watch` with a synthetic ISTA listing of our local IQ3_S files.
  - The ISTA plan picks IQ3_S, which is the served file here.
  - Both comparison drivers were written: `bash -n` OK, no `.ready`.
  - The KL driver's arms are P, X and R (dump data, as in gap-ud31).
  - cfgcheck passes on X and on R (`--quality-only`).
  - Default: PENDING, so unsloth stays, because decision.json is not written yet.
- **Two new files** (`scratch-e/uvi-test`): KL arms X1, X2 and R with no base (the pair verdict); the speed driver
  checks both arms.
- **`uvidecide` on synthetic decision files** (`scratch-e/uvidecide-synth`): PENDING keeps A; the KL half favouring B is
  reported as CONFLICT, Karl decides.
- **selftest-e:** seven v3.1 cases, the .json/.txt disagreement case, and the `--prefer` overrides all pass.

## 2 Pack pre-check

- **How it reads the headers.** Each shard's header comes from one of: the finished download, a saved head, a
  head-only file, or HF range requests (fetch_model's 206 rule; 128 KiB first, doubling, appended).
- **How it checks them.** The headers are written into sparse stand-ins: each shard's header bytes, cut to the real
  size as a hole. The release tree's own `tools/iq_pack.py` then runs on them in its own process:
  - `Model()`: shards, split keys, every tensor's type and size.
  - `expert_layout()`: the gate == up rule at r22p028x `tools/iq_pack.py:460` (r23p0211 :461), whole blocks, the
    routers, NVFP4 scales.
  - `hadamard_spec()`.
  - index_standalone's pre-write type rules, using iq_pack's own tables, with a guard that warns if their source changes.
  - Value checks (an F32 that is not exactly BF16) stay at pack time.
- **Refused quants.** A refused quant never reaches day1 or the download plan, and PLAN.md says "fell to the next quant".

| test | result |
|---|---|
| upstream's v3.1 header fixture, both trees, 8 sets | UD-IQ1_S REFUSES "layer 18: gate and up differ in type" (gate IQ2_S, up IQ2_XXS), as upstream's test says. The 7 others ACCEPT (48 layers; Q5_0 downs 33 / 20 / 1 / 1 / 0 / 0 as upstream; UD-IQ3_XXS v4) |
| HF live: UD-IQ1_S shards 2-3 at d9620119 | 77,728 + 173 header bytes; tensor directories identical to the fixture; REFUSES layer 18. Shard 1 (10.9 MB, metadata only) was not fetched under the few-MB limit: upstream's stand-in was used. In production it is read in full |
| local UD-IQ3_XXS: whole files and saved heads | ACCEPTS, v4, needs `--compat-bf16` (195 Q8_0 FORM tensors), which matches day1 |
| served ISTA IQ3_S | ACCEPTS, v3, no `--compat-bf16` |
| UD-IQ2_XS heads | ACCEPTS (1 Q5_0 down) |
| DeepSeek ISTA IQ2_XXS | NOT CHECKED: deepseek41 is packed by strata-dsv41's `tools/dsv41/pack_gguf.py`. INFO: gate == up in every layer (IQ1_M x16, IQ2_XXS x15, IQ2_XS x7) |
| DeepSeek UD-Q8_K_XL | only shard 1 of 9 is here (metadata, 0 tensors): NOT CHECKED. Pass `--repo` to read the other eight from HF |
| a plan with UD-IQ3_XXS heads patched (layer 7 up IQ2_S -> IQ1_M) next to UD-IQ2_XS | the pre-check refuses "layer 7: gate and up differ in type"; the pick falls to UD-IQ2_XS, and PLAN.md gives the reason |
| a shard whose size is short of its tensor table | REFUSES (`iq_pack.Model`) |

## 3 Fit budget

**The placement in a plan.**
- `plan --ngram-placement ssd` is today's setting: `--ple-io direct`, no RAM tier, recorded explicitly.
- `ram` adds the table to day1's `--other-gib`, and the config gets `--ple-io ram`.
- Dry run with the table in RAM: the RAM tier drops from 58.0 to 31.2 GiB, and the pick falls from UD-IQ3_XXS (0.3 GiB
  over) to UD-IQ2_XS.

**`dayone.py fit`** uses UPGRADE-ESTIMATE 8.1's conventions (bpw = budget x 8 / expert parameters):
- expert parameters = total - 7.75B dense, with the totals WITHOUT the n-gram table;
- the 5080 holds 7.3 GiB of experts;
- a 5060 Ti holds 15.0 GiB;
- MemTotal at 2x64 GB is 124 GiB.

| hardware | n-gram table | budget GiB | 250B | 300B | 400B |
|---|---|---|---|---|---|
| today (5080 + 4060 Ti, 96 GB) | SSD | **72.4** | 2.57 (IQ2_S) | 2.13 (IQ2_XXS) | 1.58 (< IQ1_M) |
| today | RAM, 26.8 GiB | 45.5 | 1.61 | 1.34 | 1.00 |
| 5080 + 5060 Ti, 96 GB | SSD | 80.3 | 2.85 (IQ2_S) | 2.36 (IQ2_XXS) | 1.76 (IQ1_M) |
| 5080 + 5060 Ti, 96 GB | RAM, 26.8 | 53.5 | 1.90 | 1.57 | 1.17 |
| 5080 + 4060 Ti, 2x64 GB | SSD | 104.4 | 3.70 (IQ3_S) | 3.07 (IQ3_XXS) | 2.29 (IQ2_XXS) |
| 5080 + 4060 Ti, 2x64 GB | RAM, 26.8 | 77.5 | 2.75 | 2.28 | 1.70 |
| 5080 + 5060 Ti, 2x64 GB | SSD | 112.3 | 3.98 (IQ3_S) | 3.30 (IQ3_XXS) | 2.46 (IQ2 mix) |
| 5080 + 5060 Ti, 2x64 GB | RAM, 26.8 | 85.5 | 3.03 | 2.51 | 1.87 |

- The full table, with a 1.6x table (42.9 GiB), is in `scratch-e/dryrun/fit-guess/fit.md`.
- `--gguf` uses a real file's own numbers. On the served file: 8.75 + 7.06 + 58.0 = 73.8 GiB.
- Below IQ1_M, the experts would need the SSD expert tier. It is marked "DeepSeek only so far, Karl decides".

## 4 Dense fallback: does Strata run a dense Qwen3.8-27B today? No.

The evidence is read at run time from both trees (r22p028x / r23p0211):
- **Main engine families.** `include/strata/artifact/model_family.hpp:21-24` maps only `qwen4exp` and `qwen35moe`, and
  `:54` runs only Qwen4Exp on the main path.
- **Architecture guard.** `gguf_reader.hpp:681` refuses any architecture but qwen4exp.
- **Compiled shape.** `core/geometry.hpp:24` and `:53` fix n_embd 2560 and 512 experts.
- **The other path.** The only other path is MoE. `generate.cpp:2961` / `:3370` switches only for qwen35moe, and
  `qwen35/q36_engine.cu:966` refuses everything else.
- **The pack.** `tools/iq_pack.py:438` refuses a file without experts.
- **The split engine.** It exists only in r23p0211, as vendored sFNX.
  - It has the 27B's geometry under `FNX_27B` (`src/split/src/model.hpp:22`).
  - The 27B's architecture is `qwen35` (`model.cpp:1268`), and it runs Q8_0 matrices only (`:684`).
  - Every CMake target builds with `FNX_27B=0` (`src/split/CMakeLists.txt:114`), and the `s27_*` sources are not in
    the tree.
  - Our build has `STRATA_BUILD_SPLIT:BOOL=OFF` (`build/CMakeCache.txt:927`).
  - It requires every card to be the build's one compute capability (`card_check.hpp:19`). The 5080 is sm_120 and the
    4060 Ti sm_89, so the pair cannot run it.
- **Two cards in VRAM.** The only mode for this is the main engine's layer split with `--trim-stage-weights` (MULTI_GPU.md).

**`dayone.py dense`:**
- It checks the tree, then computes the VRAM fit:
  - A: the 5080 alone with at least 32K context.
  - B: a layer split, with the 4060 Ti first and the 5080 last.
- Then the pick: the largest quant that fits A, else the largest that fits B.
- Then a config, params, and the kit's exactness and speed drivers in dense form. `densecheck` refuses until a release
  runs the architecture.

Dry run on synthetic 27B headers (sFNX's FNX_27B shape, 26.9B parameters, 16 attention + 48 GDN layers):

| quant | 5080 alone, max context | both cards | decode INFO, A / B |
|---|---|---|---|
| Q3_K_M | 55,296 (fits) | - | ~62 tok/s |
| IQ4_XS | 4,096 (under 32K) | - | - |
| Q5_K_M | - | K=20, 45,056 | ~24 tok/s |
| Q8_0 / Q6_K | - | no split fits | - |

- **Pick: Q3_K_M on the 5080 alone.**
- With only Q4_K_M to Q6_K given, the pick is Q5_K_M across both cards. Its config has CUDA_VISIBLE_DEVICES 4060 Ti
  then 5080, `--layer-split 20` and `--trim-stage-weights`.
- cfgcheck's only failure is the `<SET>` engine, which is expected.
- `densecheck` REFUSES "strata-r22p028x does not run 'qwen35'".

## Open questions

1. **Item 1, what decides the default.** Only the v3.1 quality verdict decides it. A NOT REPEATABLE or a speed LOSS for U
   is shown as a flag. Should either of them veto Unsloth? Also: when the v3.1 result picks a publisher, its quant can
   be the smaller of the two picks. Is that the intended reading of Karl's quant rule?
2. **Item 1, the timer.** The watcher timer is printed, not installed. Karl's go is needed for it, and for queueing the
   two comparison gaps (about 45-60 minutes each, with 8080 down).
3. **Item 2, deferred checks.** Value checks stay at pack time. A new architecture name can pass iq_pack and still be
   refused by the engine; day1's geometry check catches that.
4. **Item 3, assumptions to confirm.** The totals exclude the n-gram table. The 5060 Ti room is estimated. Does a 2x64 GB
   dual-rank kit hold 6000 MT/s on this board? Qwen4's table or Engram size is unknown; DeepSeek's is 110.6 GB, which
   rules out RAM placement at 96 GB.
5. **Item 4, unknowns for a dense release.**
   - Its architecture name, its flags (the drafter's, and whether exact7's `--expert-cache 0` is accepted) and its
     VRAM overheads (1.6 GiB, and 1.0 GiB per extra stage, assumed).
   - On the 5080 alone, the rule takes a Q3 over a Q5 that runs across both cards (~62 vs ~24 tok/s INFO). Is that the
     intended reading?
   - No dense KL driver was written: no reference fits in VRAM.
   - A 5060 Ti (sm_120) would satisfy strata-split's one-compute-capability rule, if a release builds the 27B.

# 11-06: Karl's decisions, and the Hugging Face watch

Same rules as before: no GPU (not even nvidia-smi), no server, no gap driver run, nothing queued or published. The
tests and dry run waited behind an open measurement gap via nogap-run.sh.

## The Unsloth exactness veto

Karl, verbatim: "Unsloth first-out: a failed v3.1 exactness result vetoes it, unless the failure goes away with
STRATA_HC_Q8 off and that config passes. In that case, day one uses Unsloth with the switch off. Speed and quality
don't veto: Unsloth is the stopgap until ISTA lands, and then the comparison decides."

- **Which lines count.** `u_exact_state` reads only the v3.1 gap's EXACTNESS verdict for U: `decision.json`
  `exactness.U`, and decision.txt's `  U: <verdict>.` line under EXACTNESS (ud31_rules.py decide). The two must agree.
  - That verdict comes from the exact7 runs (e7_U1, e7_U2), the env gates and the lossless / start / hcq8 checks.
  - The decode-path follow-up (`dec/decision.*`) is decode-path text NLL, so quality, and is not read.
  - The SPEED and QUALITY sections are never read.
- **No HC_Q8-off result exists.** gap-ud31.sh runs U only with STRATA_HC_Q8=1 (`hcwant U = on`). The S arm is another
  file. So the check needs its own run: **`work/qwen4-kit/hcoff/gap-ud31-hcoff.sh`** (written, no .ready).
  - It uses the v3.1 U config with exactly `STRATA_HC_Q8 1 -> 0` and no fallback, and runs the kit's smoke + exact7 twice
    at pin 2500.
  - `ud31_rules.py hcline --want off` checks the switch in the engine log.
  - `q4_rules.py hcoffneed` refuses (exit 1) unless U failed.
  - It takes ~24 min with 8080 down. It would be queued after gap-ud31-dec.sh; see `hcoff/QUEUE.txt`.
- **States:**

  | v3.1 verdict for U | HC_Q8-off check | state | day one |
  |---|---|---|---|
  | REPEATABLE | - | AS IS | Unsloth as shipped |
  | NOT REPEATABLE / CHECK FAILED | REPEATABLE | HC_Q8 OFF | Unsloth with STRATA_HC_Q8=0 (cfgcheck enforces it) |
  | NOT REPEATABLE / CHECK FAILED | anything else, not run, or older than the v3.1 decision | VETOED | no Unsloth plan, no download |
  | VOID / NOT RUN / no file / disagreement | - | NOT DECIDED | no veto (flagged) |

- **Once both are out, the comparison decides** (`uvidecide`, and `publisher_default` from its record):
  1. A veto gives the ISTA arm.
  2. Otherwise the comparison's quality verdict picks the arm.
  3. Until it has run, the stopgap (the first one out) stays.
  4. If it finds no quality difference, the v3.1 result is the tie-break, then Karl's size rule.
  - Speed is reported and never decides.

## Dense 27B: Q3 on the 5080 stays the plan; the Q4 split is a day-one quality comparison

Karl, verbatim: "Dense 27B: yes, Q3 on the 5080 alone as the plan. Add a Q4 split across both cards as a day-one quality
comparison."

- **Can Strata run the Q4 split? No.**
  - The main engine has no dense family (section 4).
  - strata-split needs every card to be its build's one compute capability (`src/split/src/card_check.hpp:19`; the 5080
    is sm_120, the 4060 Ti sm_89). It is also built with `FNX_27B=0`, its s27 sources are absent, and it is OFF in our
    build.
  - The main engine's layer split does run mixed cards (MULTI_GPU.md: 4060 Ti + 5080 measured), but only for families it
    runs. If a release adds the dense family there, re-plan the comparison on Strata.
- **So it is planned on the pinned llama.cpp, quality only, with no speed claim.**
  - The pinned source `ext/llama.cpp-3cf03257` names `qwen35` (`src/llama-arch.cpp:41`).
  - It is source only: there is no build of it. The only built llama.cpp here is Unsloth's prebuilt in `~/.unsloth`,
    which has no git, no llama-perplexity, and was not used.
  - The build commands are printed in DENSE-PLAN.md (cmake for sm_89;120 with CUDA 13.3, under nogap-run.sh): Karl's go.
  - `lcppcheck` refuses the driver until that build exists.
- **Design:** `gap-<name>-q4split.sh`.
  - Arms, all on llama.cpp:
    - R: the largest quant, with the layers that don't fit the cards on the CPU.
    - Q3: the plan's file, on the 5080 alone.
    - Q4: the largest Q4-class quant, a layer split with the 4060 Ti first.
  - All arms use `-fa on`, q8_0 K/V, and memwait / memwatch / watchdog.
  - Texts: the kit's 8 distinct texts, decoded with Flash-Next's tokenizer; llama.cpp tokenizes them itself. -c is
    min(32768, length/2), and the second half of one chunk is scored.
  - Per text, llama-perplexity's KL mode gives mean KLD, 90 % KLD and changed top-1 (from "Same top p").
  - `lcppdecide` judges Q4 against Q3 with ud31_rules.py's own `side()` / `metric_verdict()`. The kit's "KL > 1 rows"
    metric is not in llama.cpp's output.
  - One ≤ 4 GB base file is kept at a time.

## The Hugging Face watch (staged, NOT installed)

`dayone.py watch` without `--plan` makes one read-only poll.
- **Polling.** One listing call per org (Qwen, unsloth, ISTA-DASLab; their 100 most recently modified repos, with sha,
  gated and private). Repo names match `qwen[-_. ]?4` and not a following digit. A repo's metadata and file tree are
  fetched only when it is new, or its sha / gated / private state changed.
- **State.** `hfwatch/state.json` makes each new weight-file set, and each access change, alert once.
- **The alert.**
  - `notify-send -a Strata -u critical "Qwen4 files on Hugging Face" "<org/repo>: <license>, <GB>, fit pick: <quant> <bpw> bpw | Flash open; gates ~N h 8080 down"`.
  - Plus a NOTES.md line, plus ntfy once `work/qwen4-kit/hfwatch/ntfy-topic` holds the topic URL (read inside the code
    only).
- **Open Flash GGUF.**
  1. The plan runs with the pack pre-check first; a refused quant falls to the next, and the NOTES line says why.
  2. Disk check: free - the quant must stay at or above 110 GB, else "disk does not allow (need X GB more)".
  3. Then one user unit `q4dl-<name>-<time>` runs: gentle_dl.py on the pick only, with `--rate 35`, chained to the pack
     under nogap-run.sh.
     - 35 MB/s is fetch_model's standing research-safe cap; the DS4.1 download ran at it beside LDR.
     - gentle_dl's default would leave LDR 25 % of the line, so this is lower.
     - It pauses while a gap is open. Nothing GPU, no gate, the weekend chain is never paused.
  - The NOTES line gives the day-one gates' 8080-down minutes (the generated drivers' MAXM: exactness + quality + speed).
- **Otherwise.** 27B only, gated, safetensors only, or nothing: report only.
- **The timer.** `qwen4-hfwatch.timer` (every 15 min, Persistent=false). The service exits without polling after
  2026-11-08 23:59.

Install, after review:
```
cp /home/USER/ai-speed-testing/strata-compare/work/qwen4-kit/qwen4-hfwatch.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now qwen4-hfwatch.timer
systemctl --user list-timers qwen4-hfwatch.timer        # check; after Sunday: systemctl --user disable --now qwen4-hfwatch.timer
```

## 11-06 test and dry-run results (`scratch-e/`; run after the ~07:27-08:46 measurement gap closed, via nogap-run.sh)

- **`selftest-e`: 0 failures**, covering:
  - the veto: 7 cases, including a stale HC_Q8-off result, which is not counted;
  - `hcoffneed`, and publisher_default with the veto and with the comparison;
  - `STRATA_HC_Q8=0` in the config and cfgcheck on it;
  - the HC_Q8-off driver;
  - `lcppdecide` on synthetic llama-perplexity output: better / inside / worse.
- **`q4_rules.py selftest`: 0 failures.**
- **The 11-05 `dryrun` still reproduces** its picks, all six drivers and the prefer variants.
- **Veto inside a plan** (synthetic v3.1 files):
  - NOT REPEATABLE, then HC_Q8 off REPEATABLE: the Unsloth plan's config has `STRATA_HC_Q8=0`, and cfgcheck PASSES.
  - CHECK FAILED with no HC_Q8-off result: no Unsloth plan, default NONE.
- **HC_Q8-off driver, real:** `work/qwen4-kit/hcoff/gap-ud31-hcoff.sh` (bash -n OK, no .ready). Its config differs from
  ud31-U.json only in `STRATA_HC_Q8` (1 -> 0), the fallback, the log and the model name.
- **Dense Q4 split on synthetic 27B headers:**
  - R Q8_0 (40 of 64 layers on the cards), Q3_K_M on the 5080 alone, Q4_K_M split K=13.
  - 8 texts, -c 2048-32768; ~126 min with 8080 down.
  - `lcppcheck` REFUSES: not built.
- **HF watch, live:** one read-only poll. Qwen, unsloth and ISTA-DASLab listed 100 repos each, 0 Qwen4 yet, 0 alerts.
- **HF watch, synthetic, two polls:**
  - Poll 1: 3 alerts.
    - "Qwen/Qwen4-27B: apache-2.0, 55 GB, fit pick: - | 27B only" (report only).
    - "Qwen/Qwen4-Flash: qwen, 594 GB, fit pick: - | Flash gated" (report only).
    - "unsloth/Qwen4-Flash-GGUF: apache-2.0, 1863 GB, fit pick: UD-IQ3_XXS 3.33 bpw | Flash open; gates ~2.0 h 8080 down"
      (the v3.1 Flash-Next listing as the stand-in). Pre-check ACCEPTS. **Disk: 133 GB free, quant 84 GB -> "disk does
      not allow (need 61 GB more)": NOT started.** Gates: exact 24 + quality 54 + speed 44 = 122 min.
  - The teaser repo without weights: noted, no alert.
  - Poll 2: 0 alerts.

**Disk today: 133 GB free.** A 250-300B Qwen4 Flash pick (~70-90 GB) would not start unless ~50-70 GB is freed first.
That is Karl's call.
