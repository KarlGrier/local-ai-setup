# Fix 1c - the Fix 1b overcorrection (10-30)

Fix 1b's five replays (10-29 night) cleared all 11 false marks but lost 33 of the 56 right ones
(results/bench2/fixes/fix1b-compare.txt). Causes, from each replay's versioncheck.json:

| lost | cause |
|---|---|
| 18 | "unsure" from a disputed folder: b-f1b-jan1024's two engine_dirs answers disagreed - one took Strata's core runtime (src/core, src/prefill, src/spec, ...) as the DeepSeek engine's - and Fix 1b's rule (a name found in a disputed folder is not flagged) caught every Qwen-only name there (--pcie-frac, STRATA_HOST_CORE, --adapt-every, --ple-inflight, ...) |
| 7 | "this version" for Qwen core names (STRATA_IO_PREFETCH, STRATA_READ_AHEAD, ...): the same answer ("core runtime it uses") |
| 7 | "attributed" in b-f1b-fixes for names the report sets for this rig (STRATA_ROUTE_TAIL_SKIP=0 in its top-three list; --speed) - model judgement; the use definitions did not change |
| 1 | layer_split left out of the model's answer |

25 of 33 trace to the model's guess at which folders are the engine's - the guess the staged engine-scope map
(staging/enginescope, deep/engines/strata.json folders_by_version; Karl 10-29: src/core + src/platform are the Qwen
engine's at v0.2.4, kept per version) answers from the build files.

## The change (deep/checks.py = the installed Fix 1b + K4 checks.py + the lines below; checks.py.diff)

1. `_map_dirs`: for a project of deep/engines/ at the user's pinned version (a map entry at or below it) and a task that
   names one of its engines, the engine's folders come from the map (its code folders - not tools/ or data/, whose lab
   scripts take flags the engine binary never parses), nothing is disputed, the other engines' folders are kept as
   such, and the model's launcher / server folders stay shared unless the map gives them to an engine (b-f1-fixes had
   src/program, the Qwen engine, as "shared"). Anything the map does not cover keeps the two model answers.
2. `_code_parts`: hits in another engine's folders get their own line, "In the Qwen engine's folders at the user's
   version (Strata v0.2.4 ...) - not this engine's code: N hit(s): ...".
3. A name the model's answer leaves out is asked once more (one extra call, at most 40 names).
4. "attributed" for a name of the SAME project (kind other-engine / other-version) holds only when every sentence of
   the report naming it also names its owner (another program, an upstream / fork / PR / issue reference, or a release
   other than the user's); else it is "described" (flagged). Other programs' names keep the model's word: on the five
   replays the rule for every kind would have turned 38 names, 31 of them new marks (mostly llama.cpp / ktransformers /
   vLLM flags whose owner sits in a table column or the next sentence).

Needs deep/enginescope.py + deep/engines/strata.json (copies of staging/enginescope's, here); without them (an
ImportError) checks.py behaves as Fix 1b. enginescope.py imported on its own changes nothing else: the code tool /
report / fetch edits of staging/enginescope stay staged.

## Offline test (no model, no GPU, no network)

`nice -n 19 .venv/bin/python -I staging/fix1c/tests/test_fix1c.py` -> tests/test-output.txt: 79 checks, 0 failures.
- b-f1b-jan1024's recorded answers -> the map: dirs src/dsv41 + include/strata/dsv41, nothing disputed, src/core and
  src/program the Qwen engine's; a project / version / task the map does not cover -> unchanged.
- The 25 folder-answer losses: sent, none in a disputed folder, each with the Qwen-folder line or no engine hit.
- The 7 "attributed" losses: 4 come back (STRATA_ROUTE_TAIL_SKIP, ROUTE_TAIL_SKIP, STRATA_PREFILL_CPU_SHARE, --speed);
  3 other-program ones stay lost (--moe-stream-io-threads, --cache-type-v, --lazy-mode). New marks to judge after the
  replays: --full-quality, --experts (b-f1b-fixes), --prefetch (p4s6 o01).
- The missing-name retry; Fix 1b's launcher / server lines for the cleared false marks (gpu, gpu_order, --model,
  --plan, --tune, --set) kept.

## GPU step (queued: work/r22/basalt-pr90/fix1c-chain.sh, after the Basalt check and the K4 tries)

Install under the bench lock with no Jan job (backups checks.py.before-fix1c; enginescope.py / engines/ are new files),
then the five `fix-replay.py check --fix version` replays as b-f1c-* and
`staging/fix1b/tests/compare_replays.py --prefix b-f1c-` -> fixes/fix1c-compare.txt. The version check runs only with
LDR_DEEP_FIX (bench runs and replays); Jan's research runner does not set it. Expected: the 11 false marks stay
cleared, the 25 + 4 right marks come back; model noise can still move single names.
