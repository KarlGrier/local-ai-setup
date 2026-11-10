# Fix 1b - the version check stops calling the launcher's / server's own settings "launcher-only" (staged 10-29)

STAGED ONLY - nothing installed. `checks.py` here = the installed `deep/checks.py` (identical to `staging/bundle-1028/deep/checks.py`;
copy kept as `checks.py.orig`) with the Fix 1 section changed; `checks.py.diff` is the unified diff. Every other
function is byte-identical (the diff only touches lines 806-946 of the original).

The problem: fix1-judge (`results/bench2/fixes/fix1-judge/`) had 11 false marks out of 68 on the DeepSeek replays. All 11
were settings the shared launcher or server applies on the DeepSeek path ("gpu", "gpu_order", --model, --plan, --tune,
--set x2, STRATA_DS4_AUTO_PIN), or names the search missed (SLOT_KEEP / SLOT_CAP, -DSTRATA_NATIVE_EXPERTS). The p4s6 o02
replay (v0.2.6) showed the same problem: "gpu_order", "args" and STRATA_SPLIT_UNIFORM were marked launcher-only, and
four planner constants were marked "another engine".

## What changed (deep/checks.py, Fix 1 section)

1. **Launcher / server trace** (`_Src`, `_trace`, `_launcher_use`, `_passed_on`). This runs for a name that has hits in
   the shared folders and that the engine's own code does not read as a quoted `"--x"` / `"X"` (a mention in a message
   does not count, e.g. dsv41's `pack.py --model <model>`). A config key is always traced. Each evidence item gets:
   - "Parsed as a command-line option at": each argparse definition of a flag, with its parser and help text (up to 4).
   - "Launcher / server use": up to 2 places in the shared scripts. For each place it shows the file, the function and
     the first line of its docstring, and the statement itself. Then it shows where the value goes:
     - the parsed value (`a.tune`) and where it is kept (`s.tune` → `Runner.tune_deepseek()`, `s.extra` →
       `derive_config()` → `cfg["args"]`);
     - the variable or key it is stored in, and where that is read;
     - the callers of the function that reads it (`gpu_list()` → `child_env()` "The engine's environment" →
       `env["CUDA_VISIBLE_DEVICES"]`).

     Places are ranked in this order: code over comments and docstrings; the name as a string of its own; for a flag,
     the parser of the command the report uses ("strata launch ..."); a top-level read; the engine's path (its
     arguments, environment or process, or a family check).
   - "Flags / variables in these lines, in the engine's own folders": each flag or engine variable the traced lines pass
     on, with its hits in the engine's own folders. For example, `--expert-profile-save` has no hits there, and
     `--layer-split` shows `(void) val(...) // the server's (this engine balances its own split)`.
   - A closing line when the name itself is not in the engine's folders, or is there only in text.
2. **Short names** (`_long_forms`). An environment-style name that never occurs on its own in the code, but is the end
   of a longer name, is judged by that longer name (SLOT_KEEP → STRATA_DS4_SLOT_KEEP). The longer name must be named in
   the report or found in the engine, shared or disputed folders, so AVX512_BF16 is *not* turned into
   GGML_AVX512_BF16. The results carry `long_forms`.
3. **-D build options**. The code is searched without the -D. The item says so and adds "Build files (CMake)": the
   `option()` line, then the CMake lines near the engine's folder name (e.g. `target_link_libraries(strata-dsv41 ...)`).
4. **Constants** (`_not_a_setting`). An ALL_CAPS name is not sent to the model when all of these hold:
   - the code defines it as a constant (Python `X = 8.0`, C `const`/`#define`);
   - no hit reads it as a setting (quoted, getenv/environ, `$X`, `X=1`, CMake `option`/`if`, `#if`/`defined()`);
   - there are 400 hits or fewer;
   - it does not hold a variable name (`SH_STREAM = "STRATA_SH_STREAM"` is kept).

   Such a name is listed as kind `not-a-setting`, which is never flagged.
5. **Prompt**. "this-version" now also covers a setting the launcher or server applies when it runs the engine, for
   every engine or for this one. That means either it passes the value on and the engine reads it, or it acts on it
   itself: picking the cards or the model, setting the engine's arguments or environment, running a tuner, printing a
   plan. "launcher-only" applies only when the code shown does neither: the setting is only parsed or stored, it is
   another engine's option, or the engine ignores, rejects or never parses what is passed on. There is also a line
   about short names and -D options.
6. Small changes:
   - Engine folders: a folder that one `engine_dirs` answer names as the engine's own and the other calls "shared" is
     now **disputed** (it was shared). This was the p4s6 o02 case: src/program, which made STRATA_SPLIT_UNIFORM
     launcher-only. It does not change the folders of the three DeepSeek replays or o01 (tested).
   - The model returns config keys without their quotes. The disputed-folder downgrade now matches them (`_bare`).
     Before this, `"gpu"` never matched `gpu`.
   - The evidence building moved into `version_evidence()`, which needs no model, and `_settle_dirs()`. The output of
     `version_check()` is the same except for the additions above. With no clone, the items are identical to before
     (checked).

## Offline test (`tests/test_fix1b.py`, no model, no GPU, `nice -n 19`)

The test builds the evidence with both the installed and the staged `version_check()`. It runs against `git archive`
copies of the local clone at v0.2.4 and v0.2.6 in `scratch/`, using the engine folders each replay's model answered
(a fake model returns them), and it captures the prompts.

**Result: ALL OK, 95 checks** (`tests/test-output.txt`). The old and new evidence for every name of the five replays
is in `tests/evidence-<replay>.txt`.

- **The 11 false marks.** The new evidence for each one has what the judge used:
  - "gpu": `gpu_list()` → `child_env()` → CUDA_VISIBLE_DEVICES;
  - "gpu_order": `ordered_gpus()` → `child_env()`;
  - --model and --plan: the `strata launch` parser's help (cmd.py:85, :138), plus `catalog.resolve(a.model ...)` and
    `if a.plan: plan = runner.plan()`;
  - --tune: `s.tune` → `Runner.tune_deepseek()` (tools/dsv41/tune.py);
  - --set (both replays): `s.extra` → `derive_config()` → `cfg["args"] = tune_knobs.apply_to_argv(...)`;
  - -DSTRATA_NATIVE_EXPERTS: hits in the engine's folders went from 0 to 7, and the CMake lines show `option(... ON)`
    and the strata-dsv41 link;
  - SLOT_KEEP and SLOT_CAP: judged by STRATA_DS4_SLOT_KEEP / _CAP (ds4_main.cpp:348 / :350);
  - STRATA_DS4_AUTO_PIN: `deepseek_shared_start()` "DeepSeek-V4.1 only", called under `self.family == "deepseek41"`.
- **The 56 right marks.**
  - Every line of the old evidence is still in the new evidence, for all of them except ROUTE_TAIL_SKIP. That name is
    now judged by STRATA_ROUTE_TAIL_SKIP, which still has no hit in the engine's folders.
  - Every traced flag or variable says the engine's folders lack it.
  - layer_split shows the engine ignoring --layer-split. expert_profile_save and _every show that
    --expert-profile-save and --expert-profile-save-every have no hits in the engine's folders.
  - No right mark is dropped as a constant. The doc names (MULTI_GPU, HOW_IT_WORKS, ...) are still sent.
- **p4s6 o02 / o01 (v0.2.6).**
  - o02: "gpu_order" is traced to CUDA_VISIBLE_DEVICES and "args" into `engine_args()`. SMALLEST_CARD_GB, RESERVE_GB,
    ISTA_DENSE_ON_GPU_GB and REST_RAM_GB are dropped; these are the only names dropped across all five replays.
    src/program is disputed, so STRATA_SPLIT_UNIFORM becomes unsure.
  - o01: AUTO_PIN is judged by STRATA_DS4_AUTO_PIN.
  - A fake answer run on o02 confirms three things: disputed becomes unsure, the constants are listed but not flagged,
    and `version_section` / `version_marks` still run.
- **Cost.**
  - Evidence building (CPU, greps and `ast`) went from 1.8-4.1 s to 4.3-7.1 s per report.
  - The prompt grew by 4-31% (jan1024 went from 95.7K to 125.3K characters over 2 calls, about +7.5K tokens).
  - `EST["version"]` (450 s) was not changed.
- **Existing tests.** No existing deep test covers checks.py. `tests/gate` tests the proxy gate and starts servers on
  8097/8098, so I did not run it.

## Later: install, then the GPU step (needs a GPU gap and no run live; not done)

```bash
WS=/home/USER/ai/deep-research; P=$WS/.venv/lib/python3.12/site-packages/local_deep_research/deep
# 1. install, holding run/bench.lock, with no run live
cp -p $P/checks.py $P/checks.py.before-fix1b && cp $WS/staging/fix1b/checks.py $P/checks.py \
  && $WS/.venv/bin/python -m py_compile $P/checks.py
cp -p $WS/patches/ldr/0001-deep-package.patch $WS/patches/ldr/0001-deep-package.patch.before-fix1b
bash $WS/patches/ldr/make-patches.sh
# 2. Fix 1 replays (each takes run/bench.lock itself; started from a script that holds a lock -> add 8>&- 9>&-)
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py"; R=$WS/results/bench2
$PY check --fix version --label b-f1b-jan1024 --report $R/codetool/src/jan1024/ds41q/report.md --question $R/codetool/question.txt
$PY check --fix version --label b-f1b-full --run $R/codetool/run-full
$PY check --fix version --label b-f1b-fixes --run $R/codetool/run-full-fixes
$PY check --fix version --label b-f1b-p4s6o01-code --run $R/runs/screen-deep-p4s6/o01
$PY check --fix version --label b-f1b-p4s6o02-code --run $R/runs/screen-deep-p4s6/o02
# 3. compare with fix1-judge (files only)
$WS/.venv/bin/python -I $WS/staging/fix1b/tests/compare_replays.py
```

How to read the result: `compare_replays.py` lists false marks still flagged, right marks lost, and new flags to judge
by hand. On the old replays its baseline is `false kept 11, right kept 56`. The goal is all 11 cleared and all 56 kept.
p4s6 o02's 9 flags should drop to about 2 (`--expert-cache-device1`, `--args`; their marks were not judged). Rollback is
`checks.py.before-fix1b`.

## Unresolved / watch in the GPU replays

- **The model's verdicts are untested.** The offline test only shows that the evidence is there; the GPU replays
  decide.
- **The choice of traced places is heuristic.** It looks for the engine's arguments, environment or process and for
  the words engine / family / arch, and it uses the report's own command to pick the parser. Some noise gets through:
  "gpu" also traces sd-cli's `image_env()` (labelled "sd-cli's environment"), and some flags trace launcher
  description tables. The --plan evidence rests on the help text. DeepSeek's placement in `runner.plan()` is two steps
  further and is not shown.
- **Some newly traced names were not flagged before.** jan1024 `--prefill` (this-version / described) now gets the line
  "`--prefill` itself has no hit in the engine's own folders". It may become a flag. That would be right in substance,
  but it is new, so judge it. In o02 several of the Qwen engine's flags now sit in the disputed src/program, so they can
  only end up unsure, not flagged.
- **Old behaviour I left alone.** `version_marks` finds the sentence to mark with `n in line`. For a bare config key
  like `gpu`, that can be the first line that merely contains "gpu".
