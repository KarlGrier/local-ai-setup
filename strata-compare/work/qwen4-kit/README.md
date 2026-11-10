# Qwen4 day-one kit (b): `day1.py`

Karl's item 1 (b), written 2026-11-04, before any Qwen4 release. When the Qwen4 Flash GGUFs appear, one command
tells us within minutes what we can run on this PC and writes the first tests' configs and commands. The script
reads headers only. It reads no tensor data, downloads nothing, and starts no engine or GPU work. The other parts
of the kit are separate: `results/qwen4-kit/SHAPES.md` (every hard-coded shape) and `UPSTREAM-QWEN4.md` (upstream's
Qwen4 preparation).

```
WS=/home/USER/ai-speed-testing/strata-compare
nice -n 19 taskset -c 31 timeout 120 $WS/.venv/bin/python -I -B $WS/work/qwen4-kit/day1.py check \
    <quant A shard 1>.gguf <quant B shard 1>.gguf ... --name q4d1 --out $WS/results/qwen4-kit/<run>
```

- **Inputs:** any shard of a split file; the other shards are found beside it.
- **Head-only files work:** these are `bringup/fetch_model.py heads` output, with `NAME.size` beside each file.
  That means the check can run before the download.
- **How long:** ~6 s for 11 files (the self-test).
- **Python:** the repo's `.venv` with `-I -B`, and gguf-py from `ext/llama.cpp-3cf03257/gguf-py`. The script uses
  gguf-py's type enums and block sizes, and reads Strata's extra trellis types from the tree's
  `tools/gguf_reader.py`. It writes no `__pycache__` anywhere.

## What it does

1. **Headers.** Every metadata key goes to `files/<file>.keys.txt`; long arrays such as the tokenizer get a hash.
   The report covers:
   - the architecture and every `<arch>.*` shape key;
   - the tokenizer and template: vocabulary, ids, think tags, effort names, the thinking-off kwarg and the
     tool-call format, each compared with the served Flash-Next file;
   - whether MTP / nextn, n-gram (PLE) and vision tensors are present;
   - every tensor's name, type, shape, size, shard and verdict, in `files/<file>.tensors.tsv`.
2. **Types against the engine.** The tables are read from the source of `strata-r22p0210` at run time, and each
   one is cited as file:line in the report. Use `--tree` to point at another tree.
   - **Routed experts** (`STRATA_GU_FMTS` / `STRATA_D_FMTS`, `iq_kernels.cu`):
     - The 5080 (sm_120) and the 4060 Ti helper (sm_89) use one kernel set: the build is `89;120`, and the helper
       runs the same `native_expert_layout`.
     - Rules: the same gate/up type in each layer (`iq_pack.py`), whole blocks, and NVFP4 experts need their
       `.scale` tensors.
     - It also reports the prompt path (MMQ, else the FP16 dequantizer; the fused int8 kernels are 5080-only) and the
       CPU pool (any ggml-cpu dot product, plus the AVX-512 / AVX2 fast paths).
   - **Dense projections and the head:** `native_mmvq_supported`.
   - **Embedding:** `embed_type_supported`.
   - **Float-form roles:** `iq_pack.py`'s `FORM` table, which says which float form the engine reads for each role
     (BF16, F32 or F16).
   - **The n-gram table:** `ngram.cpp` `kPleFormats`.
   - **The load gate:** `read_geometry` + `geometry_unsupported`, i.e. the compiled shape.
   - **setup.py's name check:** for information only, since our configs do not go through setup.

   Each tensor group gets one verdict:

   | verdict | meaning |
   |---|---|
   | OK | runs as stored |
   | OK (build option) | needs a build option |
   | PACK (exact) | widening |
   | PACK (exact if the values allow) | F32 to BF16 or F16: iq_pack checks the values |
   | PACK (rounding) | needs `--compat-bf16`, or `q8_dense_gguf.py` for a dense / head type |
   | TOOL (conversion) | `embd_bf16_pack.py`, or `ple_fp8_pack.py` from the checkpoint |
   | UNKNOWN | a role no file Strata runs has |
   | REFUSED | with the reason and the source line |
3. **Fit (Karl's quant rule, `bench2/QWEN4-DAY1-PLAN.md` "Quant choice").** The rule: take the largest quant whose
   experts fit RAM + VRAM. All candidates are grouped per model (the same arch, shape and tokenizer; `--group-by
   name` also splits fine-tunes). The pick is the largest one that fits and runs, and the report flags a margin under
   2 GiB. The room today is built up as follows (every input is a flag):

   | part | how it is computed |
   |---|---|
   | **5080** | 16,303 MiB − 2.11 GiB overhead (fitplan.py's calibration; includes Flash-Next's 0.82 GiB drafter) − dense weights on the GPU (from the header, in the pack's forms) − resident K/V (32,768 cells) − 713 MiB reserve − 89 MiB draft head |
   | **4060 Ti** | 7.56 GiB free − 512 MiB = 7.06 |
   | **RAM tier** | MemTotal 92.0 GiB − floor 12 − everything else 16.3 − headroom 5.7 = 58.0 |

   About the RAM tier:
   - The 16.3 GiB is everything except the tier: the engine, the 1.55 GiB of pinned K/V, a 2 GiB chat cache, the
     OS, the desktop and the daily services. It was measured when the 64 GiB splice arms hit the 12 GiB guard on
     11-03.
   - The 5.7 GiB headroom makes the tier the 58 GiB that ran clean.
   - For a new model the script adjusts the K/V at the served context, the embedding table and the chat-cache cap.

   For Flash-Next this gives 8.75 (measured: 8.75) + 7.06 + 58.0 = 73.8 GiB. With section 8's guessed Qwen4 dense
   part it is the plan's ~72 GiB.

   **Printed per file:** expert bytes and bpw, dense / embedding / n-gram / in-file MTP bytes, active parameters,
   K/V at 128K, the room, the SSD spill, the disk check (>= 100 GB free after), and the page-lock note (> 60 GiB:
   stressapptest first).

   **Tier split and decode:** these use the model of `results/sweep-1103/UPGRADE-ESTIMATE.md` sections 8-9
   (`scratch-estimate/qwen4.py` and `lc_placement.py`, with `curves.json`):
   - the splice's main-card hit curve, at the fraction of experts held;
   - a helper slot = 0.7 of a main slot;
   - CPU 65 µs per 4.0 MB entry, and the SSD fit;
   - the serial GPU part = 2.2 ms × the active-parameter ratio to Flash-Next;
   - section 9's per-helper entries and exposed wait.

   The report compares the result with Karl's 40-60 tok/s target. It also checks the model against the two
   measured points when those files are in the run.
4. **Day-one pieces** for each pick go in `OUT/day1/`:
   - **`<name>.json` + `.shared-settings.json`:** built with `configs/P028x.json` as the template (only read):
     - our series' switches are dropped and listed under `_day1`;
     - it sets fitplan's lossless pins and v0.2.10's 14 pins;
     - no `--vision`, test port 8081, and an explicit helper slot count;
     - `--resident-budget-gib` when the experts exceed the RAM tier, and `--chat-cache-mib` at the fit's cap;
     - the expert profile only when its layers × experts shape matches.

     `exe` / `server` stay `<SET: ...>` until the release exists (`--exe`, `--server`). The file goes to
     `configs/<name>.json` only with `--install-config`, which never overwrites a file and refuses `P028x*` names.
   - **`params-<name>.json`:** every model-specific input of the tests:
     - the chat template (efforts, the thinking-off kwarg, the tool format) and the tokenizer (same as Flash-Next?
       think-tag ids, turn token, `--turn-token` if it differs);
     - the prompt folder and the Flash-Next token length of each frozen prompt;
     - the drafter and the expert profile (shape);
     - exact7's `PIN_CACHE` (70 % of the 5080's room in largest blobs; Flash-Next's 2500 is 71 %) and `REF` (its own
       first run);
     - the KL reference (published table / a local reference config), the screen's workloads and effort, bp90's
       fixture tokenizer, and the speed target.
   - **`commands-<name>.txt`:** the sequence, to run by hand after Karl's go, never as a script:
     1. pack;
     2. re-tokenize the prompts, if needed;
     3. Strata run: a CLI smoke test + exact7 twice;
     4. KL against the reference: pf_yardstick long40 through `day1.py pfy`, plus quant_quality;
     5. the graded set: the suite quick run at medium;
     6. speed: the 9-workload screen × 3 (`work/r22/abarm.sh`), then Basalt's bp90 cold fixtures × 3.

     Every GPU step holds `tmp/gpu-test.lock`, runs inside a `port_gap4.sh` gap, and is followed by kcheck. No
     command line carries an engine-serve or process-matching pattern; servers start only through `with_server.sh`.

## Helpers for the model-specific inputs

| command | what |
|---|---|
| `day1.py retok --new-gguf NEW --out DIR [--names a,b]` | the frozen prompts (`bringup/out/r20a/prompts`: Flash-Next ids with the template applied) decoded with Flash-Next's tokenizer and encoded with the new one (the tree's `strata_tokenizer`, special tokens parsed); `retok.json` lists old / new lengths. Pure-Python BPE: minutes for the 120K files |
| `day1.py pfy PROMPT_DIR --check` | lists `pf_yardstick.py`'s long40 cuts against each text's length (a new tokenizer changes lengths; cuts past the text are flagged) |
| `day1.py pfy PROMPT_DIR -- run CFG OUTDIR --set long40` / `-- compare REF RUN` | `work/r22/pf_yardstick.py` with its hard-coded prompt folder replaced (module attribute; the script itself is untouched) |
| `day1.py kr3 PROMPT_DIR -- PFYDIR --ref ref --refs unfused,cpushare --cands X` | `work/r22/kernel_rule3.py` (with the NLL check) reading the text's next tokens from PROMPT_DIR |

## Which pieces are model-specific

The KL rules (`kernel_rule2.py` / `kernel_rule3.py`, `g17_rules.py`) compare **builds** of one model against that
model's own rounding references. They belong to the port's gates, after day one. Day one's quality step is KL
against the published reference plus the graded set.

| test | model-specific | parameter |
|---|---|---|
| exact7 (`bringup/lib/exact7.sh`, `run.sh`) | prompt token files; slot pin (byte budget in largest blobs); reference hashes (C*13's do not apply); evicted files | `PROMPT_DIR`, `PIN_CACHE`, `REF=<own first run>`, `EVICT_GLOB` |
| pf_yardstick long40 | prompt token files (PR); cut lengths in tokens; `--expert-profile` in the config (quant_quality's engine args) | `day1.py pfy PROMPT_DIR`, `--check` |
| kernel_rule2 / 3 + NLL | next tokens from the prompt files; the two rounding references (unfused = `STRATA_PF_FUSED=0`, cpushare = `STRATA_PREFILL_CPU_SHARE=0.4`) re-measured on the model | `day1.py kr3 PROMPT_DIR` |
| 9-workload screen (`abarm.sh` / `abrun.py`) | effort name and thinking-off kwarg (template); prompt lengths in tokens (R2 ~54K must fit the context) | `params.screen` |
| Basalt bp90 | fixtures are Flash-Next ids: keep `--gguf` / `--tree` at Flash-Next's to decode them; the token counts no longer match with another tokenizer | `params.bp90` |
| the graded set (`suite/run.sh`) | effort (`--extra-body`), the tokenizer for token counts (the pack's, via `/config`) | `params.screen.effort` |
| KL vs reference | the publisher's KLD / top-1 table for the file; or a larger local quant's config | `--kl-ref`, `--kl-ref-config` |
| the config | engine + server of the release, drafter (`--mtp`), expert profile of its shape, `--turn-token` if `<|im_start|>` moved | `--exe`, `--server`, `--mtp`, `--expert-profile` |

## Self-test (11-04)

Results: `results/qwen4-kit/day1-selftest/`. The test read 11 files, headers only (see its `SELFTEST.md`).

## Drafter fallback

`mtp_from_gguf.py` converts an Unsloth MTP GGUF (use the BF16 one) to our drafter rt format; on Flash-Next it reproduced
`strata-v0115/mtp/rt` byte for byte (results/qwen4-kit/mtp-fallback/). Day-one steps: QWEN4-DAY1-PLAN.md "Drafter fallback".
day1.py 11-04: same-model swap mode (`--files-at`, `--no-swap`), tie warning, allowed-down-types line (flags in its docstring).

## dayone.py: the one entry point (11-05)

`dayone.py plan --repo OWNER/NAME[@REV] [--local SHARD1] --name N --out DIR [--prefer auto|ista|unsloth|any]
[--kl-ref-gguf SHARD1] [--no-swap] ...` runs these steps in order:

1. pins the listing (HF API);
2. groups the files by quant;
3. reads headers (saved ones, files on disk, or range requests for the quants near the fit boundary);
4. runs `day1.py check`;
5. picks by Karl's rule. A tie goes to `--prefer`; `auto` reads the v3.1 gap result, and today that means `any`, so
   quality decides;
6. checks disk (>= 100 GB after);
7. plans the download (`gentle_dl.py`, this folder's day-one copy; Karl 11-05 default `--window measure`: at once,
   paused only while a gap is open, no fixed cap, 25 % of the line left while an LDR run holds bench.lock);
8. plans the pack (iq_pack under `nogap-run.sh`);
9. plans the drafter fallback (`mtp_from_gguf.py`);
10. writes the configs, with explicit `--expert-cache` / `--expert-cache-device1` counts from the slot model
    (F1-frame-pools.md, reproduced exactly on the served file), and the KL reference's config;
11. generates three gap drivers: exactness smoke, KL against the named reference (every arm waits for memory before
    it starts and is stopped by PID before it can swap: Karl 11-05), and speed screen. Their rules are in
    `q4_rules.py`. No `.ready` file is written.

`dayone.py execute download|pack|drafter --plan DIR/plan.json` prints each step's commands; `--go` runs them.
`dayone.py dryrun` runs the whole thing on the Flash-Next stand-in. `dayone.py selftest` and
`q4_rules.py selftest --dir scratch-d/...` test the slot model, the pick and the rules.

Results: `results/qwen4-kit/dayone-dryrun/` (`DRYRUN.md`, `RELEASE-DAY-ONLY.md`).

## dayone.py: Karl's four additions (11-05e)

Written 11-05 evening; no GPU, no server, NOT RUN on a release. Details, dry-run results and open questions:
`work/qwen4-kit/ADDITIONS-1105.md`. Backups: `dayone.py.before-1105e`, `q4_rules.py.before-1105e`, `README.md.before-1105e`.

| item | how | command |
|---|---|---|
| 1 quant timing | `plan` with repos of both publishers runs one plan per publisher (`DIR/<publisher>/`); a repo not out yet (HF 401 / 404) is recorded, not fatal. The DEFAULT: one publisher out -> it; both -> the v3.1 result (`v31_default`: results/r23/ud31/decision.json + .txt, dec/decision.json + .txt, by ud31_rules.py's own rules, the frozen pack-rounding rule included); PENDING -> the first one out stays. Both out -> the U-vs-ISTA comparison in `DIR/uvi/` (a KL pair driver + an A/B speed driver + QUEUE.txt; no .ready) | `dayone.py watch --plan DIR --repo OTHER` (one poll; the timer line is printed, not installed) |
| 2 pack pre-check | every quant's shard headers (the download, saved heads, head-only files, or HF range requests from 128 KiB up) -> sparse stand-ins -> the release tree's own `tools/iq_pack.py`: `Model`, `expert_layout`, `hadamard_spec`, index_standalone's pre-write type rules. A refused quant is left out of the pick (Karl's rule takes the next) and PLAN.md says why | `dayone.py precheck --local SHARD1 / --repo R@REV --quant L / --fixture SET` |
| 3 fit budget | `plan --ngram-placement ssd|ram` (ram: the table comes out of the RAM tier via day1's --other-gib; the config gets `--ple-io ram`); the table per hardware option | `dayone.py fit [--gguf SHARD1]` |
| 4 dense fallback | whether the release tree runs the file's architecture (file:line, at run time; today: no), the VRAM fit (A: the 5080 alone with >= 32K; B: a layer split, 4060 Ti first), the pick, a config, params, the exactness + speed drivers in their dense form (`q4_rules.py densecheck` refuses until a release runs it) | `dayone.py dense --local SHARD1 ... --name N --out DIR` |

`dayone.py selftest-e` (upstream's v3.1 header fixture on both trees, the v3.1 default rule, the fit arithmetic, the dense
evidence; 0 failures 11-05) and `dayone.py dryrun-e --out work/qwen4-kit/scratch-e/dryrun [--live]` run every new piece
without a GPU; `dayone.py dryrun` (the 11-05 dry run) reproduces its picks, slots and drivers unchanged.

## 11-06: Karl's decisions, the HF watch

| what | how | command |
|---|---|---|
| Unsloth exactness veto | `u_exact_state`: the v3.1 gap's EXACTNESS verdict for U (decision.json + its decision.txt line; speed / quality never veto). REPEATABLE -> as is; NOT REPEATABLE / CHECK FAILED -> `hcoff/gap-ud31-hcoff.sh` decides (the v3.1 U config with STRATA_HC_Q8=0, exact7 x2): REPEATABLE -> day one uses Unsloth with STRATA_HC_Q8=0, else VETOED (no Unsloth plan / download). Both out -> the U-vs-ISTA comparison decides (uvidecide); until it runs the stopgap stays | `dayone.py hcoff` (written: `hcoff/`, no .ready) |
| dense Q4 split | `dense` also plans the largest Q4 quant across both cards as a QUALITY comparison against the plan's Q3 (5080 alone), both against R. Strata cannot run it, so it is planned on the pinned llama.cpp (ext/llama.cpp-3cf03257, source only: build commands printed; `lcppcheck` refuses until built for sm_89 + sm_120); llama-perplexity KL per text; `lcppdecide` by ud31's own side() / metric_verdict(); no speed claim | part of `dayone.py dense` |
| HF watch | `dayone.py watch` without `--plan`: one poll of Qwen / unsloth / ISTA-DASLab (one listing call per org, a repo's metadata + tree only when new or changed; state.json: one alert per new file set / access change); alert = notify-send -a Strata -u critical + a NOTES.md line (+ ntfy when `hfwatch/ntfy-topic` exists). Open Flash GGUF -> the plan (pre-check first), the disk check (free - quant >= 110 GB), the pick's download (gentle_dl --rate 35, pauses during gaps) chained to its pack under nogap-run.sh as a user unit; 27B only / gated / nothing -> report only; the day-one gates' 8080-down minutes in the alert | `dayone.py watch [--dry]`; units staged: `qwen4-hfwatch.service` / `.timer` |
