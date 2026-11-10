# Engine-scope labels (staged 10-29, NOT installed)

When the task is about ONE engine of a multi-engine project (here: Strata's DeepSeek-V4.1 engine, `strata-dsv41`),
sources and doc sections that describe ANOTHER engine of that project (Strata's Qwen engine) are labelled where the
model reads them, so wrong-engine settings are stopped at research time, not only by the version check afterwards.
Same shape and same switch as the version labels installed at 07:48 (off unless `LDR_DEEP_FIX` has `version`).

Why: in run-full-bundle-verpin the 7 wrong names were already in the lead's research answer, from code-tool reads of
v0.2.4 pages that describe the Qwen engine (docs/MULTI_GPU.md, the community RTX 5080 / 4x 7900 XT benchmarks,
PREFILL_HEAD_ALIAS.md) and from code-search hits in Qwen-engine files (results/bench2/codetool/SUMMARY-VERPIN-1029.md).

## What it does

- **The task's engine** (`enginescope.task_scopes`): for each project in `deep/engines/<project>.json` that the task
  (or the setup profile) names, the one engine the task names (DeepSeek / DSV4 / dsv41 / V4.1-Flash vs Qwen /
  Flash-Next); from the setup profile only when the task names none. No engine or several named: no labels at all.
- **A source's engine** (`enginescope.classify`):
  - GitHub page of the project: by path - engine folders / doc files from the table, **per version** (Karl 10-29):
    always `src/dsv41`, `include/strata/dsv41`, `tools/dsv41`, `tools/dsv41_lab`, `data/dsv41`, `docs/DEEPSEEK41.md`
    vs `src/program`, `src/qwen35`, `src/spec` (+ include/, tools/qwen35, the sycl/ and metal/ ports' program / prefill
    / ngram / engine folders), `docs/QWEN36.md`, `docs/GYRO.md`. `folders_by_version` in strata.json, picked by the
    user's pinned version (the version labels' pins: store.pins, else derive_pins on the task / profile; the newest
    entry at or below it):
    - **v0.2.4 (also v0.2.4.x, v0.2.5) and v0.2.6:** src/core, src/platform, src/prefill, src/ngram (+ include/strata/),
      sycl/src/platform (the Intel port's) and tests/platform = the Qwen engine's; src/core/device.cu and
      include/strata/hip_compat/ stay shared (Karl 10-29). sycl/src/platform and tests/platform checked at v0.2.4,
      v0.2.5, v0.2.6: no DeepSeek reference, not in the strata-dsv41 build.
    - **v0.2.7 and later:** they are shared (the base map, left as found - sycl/src/platform and tests/platform too).
    - **no pin, below v0.2.4 or unparseable:** the base map, the conservative one (all four shared).
    Shared always: kernels, artifact, plan, hip_compat, serve, strata_control, strata_cli, apps, tools/, tests/,
    setup.py, CMakeLists.txt. Launcher lines stay unlabelled (Fix 1b's case, Karl 10-29). Other code files: no label.
  - What the clone shows (git show / git grep at the tag, recorded in strata.json): at v0.2.4 / v0.2.4.2 / v0.2.5 /
    v0.2.6 strata-dsv41 links strata_dsv41_kernels, runtime, BLAS, strata_kernels_cpu (STRATA_NATIVE_EXPERTS) and
    strata_core ONLY `if(WIN32 AND STRATA_ENABLE_HIP)` (src/core/device.cu's hip_compat::mem_get_info, the WDDM
    budget); src/dsv41 includes only strata/dsv41 and strata/kernels headers. At v0.2.7 / v0.2.7.1 it links
    strata_prefill on every build (the RDNA3 WMMA GEMM), which links strata_engine -> strata_core + strata_kernels
    (src/platform/direct_file.cpp, src/ngram/ple_reader.cpp): shared from v0.2.7.
  - docs, bench results, release notes, issues, other sites: marker counts (model names, engine names, Qwen-only
    settings such as --mtp / --spec / --ple-gguf, DS4_ prefixes). Whole page = other engine when it has >= 3 of its
    markers and >= 8x the task engine's; a page naming both engines is labelled per markdown section (a section with
    weak / no markers takes its parent heading's verdict; the page's own title section is not inherited). A bench
    run's config / script is placed by its run's README.
  - Other projects (Xolotl, Abyss, project-maya, Strata-DSV4.1, llama.cpp, ...) and github.com search pages: no label.
- **Where the model reads it:**
  - code tool: `code_read` gets a line under the URL (`[OTHER ENGINE: this page describes Strata's Qwen engine; the
    task is about its DeepSeek engine - its flags, settings and numbers are not the DeepSeek engine's unless that
    engine's code shows them]`, or `this file is part of ...` for code); a mixed doc gets `[PARTLY OTHER ENGINE: ...]`
    plus `[OTHER ENGINE from here ...]` / `[end of the OTHER ENGINE part]` lines around the marked parts.
    `code_search` hits in such files / parts get `[OTHER ENGINE: Strata's Qwen engine]` and one legend line; an opened
    issue / PR gets the note. The evidence keeps the plain text.
  - fetch tool (deep mode and full mode): the note under the URL; on a mixed page each extracted quote from a marked
    part is prefixed `[OTHER ENGINE: Strata's Qwen engine]`.
  - web_search results: the short mark ahead of the title (path, or a snippet with clear markers); copies only.
  - writers: the note ahead of the title next to the version note in every source label (outline, sections), marked
    quotes / passages for mixed pages, and the citation check's source blocks. One rule line in the section prompt and
    one in the lead's and subagents' prompts - only when the task has an engine scope.

## Files (each `*.orig` = the installed file at 14:12 today; sha256 in installed-sha256.txt)

| file | change |
|---|---|
| deep/enginescope.py | new, 727 lines, standard library only (derive_pins from codetool.py when in the package) |
| deep/engines/strata.json | new, the Strata table (folders, docs, markers, shared, content_dirs, folders_by_version with what the clone showed per tag) |
| deep/codetool.py (.diff) | +89 -4: `_enginescope()` loader (also works when code-mcp.py loads the file on its own), code_read / code_search / github_issues labels |
| deep/report.py (.diff) | +27 -2: `_engine_note` next to `_version_note` in `_label` and the citation check, `_engine_quotes` on extractions and page passages, the conditional section rule |
| fetch/__init__.py (.diff) | +17 -2: `_engine_output` in the summary and full fetch tools |
| strategies/langgraph_agent_strategy.py (.diff) | +28 -1: search-result titles, the rule line in the lead's system prompt and the subagent prompt |
| patches/make-patches.sh (.diff) | +1 -1: 0001-deep-package.patch also takes deep/engines/*.json |
| c3-merged/ | the same edits applied to staging/c3's copies of codetool.py, report.py and the strategy (`*.c3.diff` against c3) |
| make_staged.py | the change as exact (old, new) edits; `--check` says whether every edit still applies; `--base c3` writes c3-merged/ |
| tests/test_enginescope.py | the offline tests (below) |

The plain `.diff` files apply to the installed tree with `patch -p1` (checked on a copy), but NOT cleanly to c3's
copies (codetool.py's docstring hunk fails) - for c3 use c3-merged/ or `make_staged.py --base c3`.

## Offline tests (no model, no services, no network, no GPU)

`nice -n 19 .venv/bin/python -I -B staging/enginescope/tests/test_enginescope.py [--variant c3]` - 75 / 75 pass on
both variants (staged over the installed package; c3-merged over staging/c3). Output: tests/test-output.txt,
results.json, samples/ (rendered fetch / code_read / code_search output, writer labels, a section's evidence block,
a citation-check prompt); tests/variant-c3/. The code tool runs on `git archive v0.2.4` of the local clone
(scratch/strata-v0.2.4, 91 MB; rebuilt if missing) put in as an already-open clone.

- Scopes: the 10-24 question -> dsv41; no engine named, both named, or llama.cpp only -> no scope; profile fallback.
- Paths at v0.2.4: Qwen folders and src/core, src/platform, src/prefill, src/ngram (+ include/) labelled ("... Qwen
  engine at v0.2.4"); dsv41 folders, device.cu, hip_compat, kernels, serve, launcher, setup not; with no pin
  core / platform / prefill / ngram are shared. Version rule: v0.2.3 / main / none -> base, v0.2.4.2 / v0.2.5 ->
  v0.2.4, v0.2.6 -> v0.2.6, v0.2.7.1 / v0.3.0 -> v0.2.7.
- Per-version maps against the clone (git show / git grep at each entry's tag): no folder the DeepSeek engine links
  (outside the Windows-HIP guard) or includes is called the Qwen engine's. src/core/expert_cache.cpp for a DeepSeek
  task: labelled at v0.2.4 and v0.2.6 (the clone shows it Qwen-only there), shared for a v0.2.7 task and an unpinned one.
- Verpin evidence: 7 of 539 read sources labelled - MULTI_GPU.md (2 reads), both community bench READMEs (3 reads),
  PREFILL_HEAD_ALIAS.md (whole page) and the repo root page (PARTLY: its Qwen sections). DEEPSEEK41.md, all src/dsv41
  and tools/dsv41 reads, the 0.2.4 release notes, newreleases.io, forks / other projects: unlabelled. The code tool
  (whole file) and the writer (the evidence's ranges of the file) agree on all 38 Strata reads. Nothing labelled for a
  task naming no engine or another project.
- Mixed page: README.md -> its Gyro / other sizes / speed / build / credits sections labelled, its DeepSeek section
  not; a quote from each is marked / unmarked accordingly.
- Fetch, code_read, code_search, writer prompts: labelled where expected; byte-identical to the installed (or c3)
  tools and writer when nothing is labelled, when no engine is named, and with `version` off.
- **The 7 wrong names (with the v0.2.4 map):** 4 of 7 (--pcie-frac, --adapt-every, STRATA_IO_THREADS,
  STRATA_UNBUFFERED_LOAD) appear ONLY in read sources that would be labelled (unchanged: no read source of the rerun is
  in src/core or src/platform). Counting the code-search hits the research saw (its 374 distinct v0.2.4 greps replayed
  on the local tree): **2 of 7** (STRATA_UNBUFFERED_LOAD, STRATA_IO_THREADS). Marked hit lines per name: --pcie-frac 65/71,
  --adapt-every 53/56, --trim-stage-weights 42/45, --vram-reserve-mib 65/106 (was 63), STRATA_IO_THREADS 70/70 (was
  56; src/platform, its header, sycl/src/platform and tests/platform now marked), STRATA_UNBUFFERED_LOAD 40/40, --layer-split 58/63. The
  unmarked rest: launcher / app / tools files (strata_control, apps/host, tools/batch_test.py - Fix 1b's);
  --vram-reserve-mib
  also in project-maya, --layer-split in Xolotl / Abyss (and dsv41 parses --layer-split itself).

## Install order

1. **c3 first** (INSTALL-ORDER-1029.md row 1 touches the same three files). Then install from `c3-merged/` - or, at
   install time, `make_staged.py --base installed` against the live tree (re-checks every edit) and copy its output.
   If this goes in before c3, c3's codetool.py / report.py / strategy must get the same edits (`make_staged.py --base c3`).
2. **fix1b / k4: independent** (they change deep/checks.py only). Note: k4's checks.py (= fix1b + K4) was installed at
   14:27 today (`checks.py.before-fix1b-k4`) - not by this task.
3. runner-bench, item7, item8, bench2-merged, phase5, c4: no shared files.

Steps (holding run/bench.lock, no LDR run / Jan job / replay live; LDR restart afterwards):
```
WS=/home/USER/ai/deep-research; P=$WS/.venv/lib/python3.12/site-packages/local_deep_research; S=$WS/staging/enginescope
$WS/.venv/bin/python -I -B $S/make_staged.py --check          # every edit still applies to what is installed
for f in deep/codetool.py deep/report.py advanced_search_system/tools/fetch/__init__.py advanced_search_system/strategies/langgraph_agent_strategy.py; do cp -p $P/$f $P/$f.before-enginescope; done
$WS/.venv/bin/python -I -B $S/make_staged.py --out $S/install-now   # from the live (c3-installed) files
cp $S/install-now/deep/{codetool,report,enginescope}.py $P/deep/; mkdir -p $P/deep/engines; cp $S/deep/engines/strata.json $P/deep/engines/
cp $S/install-now/fetch/__init__.py $P/advanced_search_system/tools/fetch/__init__.py
cp $S/install-now/strategies/langgraph_agent_strategy.py $P/advanced_search_system/strategies/
$WS/.venv/bin/python -m py_compile $P/deep/enginescope.py $P/deep/codetool.py $P/deep/report.py
cp -p $WS/patches/ldr/make-patches.sh $WS/patches/ldr/make-patches.sh.before-enginescope; cp $S/patches/make-patches.sh $WS/patches/ldr/
bash $WS/patches/ldr/make-patches.sh
```
Then re-run the tests (they compare with the then-installed files, so expect the "identical to installed" checks to
say so only for unlabelled cases).

## Later GPU check (not done)

1. Report-stage replay on the verpin evidence (~50-60 min): first, before installing, a base replay for the
   variance (`b-w-verpin-base`); then after installing:
   `.venv/bin/python -I tools/fix-replay.py write --fix all,read,claims --setup --critic --budget-left 3600 --label b-w-verpin-enginescope --run results/bench2/codetool/run-full-bundle-verpin --question results/bench2/codetool/question.txt`.
   The lead answer already holds the 7 names, so this measures only the writer side (labels + section rule). Count
   wrong-engine names in the main list and K1-K7, graded blind in one round.
2. Ideally a research rerun (240 min): `codetool-test.py full --bundle --suffix=enginescope`, graded blind with the
   six-fix, first bundle and verpin reruns (Karl's keep rule). Its labels can be recounted offline from evidence.jsonl
   with this module (deterministic).

## Open questions

1. sycl/ and metal/ (the Intel and Mac ports of the Qwen engine): their program / prefill / ngram / engine folders are
   labelled Qwen at every version (sycl/src/platform from v0.2.4 to v0.2.6), their core / kernels left shared - right?
2. Many v0.2.4 docs describe the Qwen engine with too few markers to label (e.g. LOGIT_BIAS.md, KV_PREFETCH.md); a
   "docs older than the DeepSeek engine" rule would be version-specific - wanted?
3. The markers were checked at v0.2.4 (v0.2.6 / v0.2.7: same folders; DEEPSEEK41.md still has no MTP / --spec / IQ3
   markers; v0.2.6's MULTI_GPU.md becomes mixed and its DeepSeek section stays unlabelled). Add a folders_by_version
   entry (and recheck the markers) at each port; tags after the newest entry take its map.
4. A search hit is labelled only by its path or a snippet with >= 3 markers, so most docs are labelled only once read.
