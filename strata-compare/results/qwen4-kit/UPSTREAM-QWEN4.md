# Qwen4 day-one kit (c): upstream Strata's Qwen4 preparation

2026-11-04. Read-only.
- `git -C strata fetch origin` updated refs only; no checkout, merge or worktree change.
- The `gh` queries were read-only; nothing was posted, commented on or starred.
- Upstream = `github.com/Niko1221/Strata` (the `origin` of `strata-compare/strata`).

## Bottom line

**Upstream has no Qwen4 preparation.** I found:
- no branch, commit, issue, PR or doc about Qwen4;
- no new GGUF architecture name;
- no shape-generalization work aimed at a larger qwen4exp.

The one mention is a contributor's aside from 10-02. Upstream's pattern for a model of another shape is a separate
engine path per family, not generalized kernels: `src/qwen35` for Qwen3.6, `src/dsv41` for DeepSeek, and a build-time
model switch in the imported split engine. A Qwen4 with new widths would most likely get the same treatment, so day one
would see a refusal rather than a run unless a release adds it.

## Refs after the fetch

- The fetch moved `origin/main` from `870aedd9e` (10-29) to `ffa80d731`, which is **v0.2.10** (11-02 23:37 +0100). That
  is our port base, `r22-port0210`'s parent. There are no commits past v0.2.10.
- **Remote branches** (`git ls-remote --heads`): `main` and `rc/0.1.30`. The local `origin/pr245` is a stale
  remote-tracking ref.
- **Newest tag:** v0.2.10.

## Code at origin/main

- **Architectures the engine knows:** `qwen4exp` (Qwen3.8-Flash-Next) and `qwen35moe` (Qwen3.6-35B-A3B), in
  `include/strata/artifact/model_family.hpp:15-25`, plus the DeepSeek engine `src/dsv41` as its own program. Anything
  else is refused by name: "architecture is 'X', this engine requires 'qwen4exp'" (`gguf_reader.hpp:681`).
- **`git grep` for `qwen 4`, `qwen4[-_ ]`, `qwen4moe`, `qwen4next`, `Qwen4-` and `"qwen4"`, excluding `qwen4exp` /
  `qwen4_exp`, over code and docs: no hits.** The only near hits are vLLM's `qwen4_exp` MTP name in
  `include/strata/core/mtp.hpp:3` and `sycl/include/strata/core/mtp.hpp:3`.
- **The served GGUF itself** says `general.description = "A Preview of the Qwen4 Architecture"`. The vendored llama.cpp
  (`ext/llama.cpp-3cf03257`, gguf-py `constants.py:523-525`) knows `QWEN35`, `QWEN35MOE` and `QWEN4EXP` and no `qwen4`.
  - llama.cpp's own commit titles already say "qwen4" for this arch. Upstream #4589 quotes llama.cpp b11062:
    "CUDA: enable sparse fa for qwen4 (#28770)", 09-20.
  - **So a real Qwen4 GGUF could arrive as `qwen4` / `qwen4moe` or similar, which fails at `gguf_reader.hpp:681`.**

## Shape-generalization history (upstream commits)

None of these targets Qwen4. Together they are the machinery a Qwen4 port would build on:

| date | commit | what |
|---|---|---|
| 10-05 | dd32704d4 | prefill: the APR sign vectors are looked up at the layout's widths, not 640 / N |
| 10-12 | f812e9a16 | core: the geometry is read from the GGUF and **checked against the shape the kernels are compiled for** (`geometry.hpp`, `kCompiledGeometry`, `read_geometry`, `geometry_unsupported`) |
| 10-12 | 14ba7a627 | model families: Qwen3.6 (`qwen35moe`) recognised, geometry and layout from the GGUF |
| 10-12 | 51329cff3 | `read_geometry` refuses another architecture by name before reading any qwen4exp key |
| 10-12 | 8825d337c | prompt-chunk sizing and the state fingerprint take their QSA shapes from `qsa_shapes(g)` |
| 10-13 | 4cfeaa0f4 | merge f-qwen36: the qwen4exp guard is kept; Qwen3.6 gets its own family guard and a **separate engine path** (`src/qwen35`) |
| 10-14 | fb51ae6fb | iq_kernels: the V2K gate/up kernels take Qwen3.6's expert geometry (n_embd 2048, n_ff 512) |
| 10-26 | 25a62e0fb | KVA keeps a geometry gate (48 layers / 512 experts); `STRATA_KVA_ANY_MODEL=1` overrides |
| 11-01 | b8668d038 | the split engine (sFNX, johnfink8, MIT) imported. All shapes are `constexpr`, picked at build time with `make FNX_MODEL=fnx\|27b`: Flash-Next, or Qwen3.8-27B dense (N 5120, 64 layers). It reads the PLE hash constants from the GGUF. |

The precedent is clear:
- a fine-tune or a pruned variant of the same shapes loads through the qwen4exp path (the 256-expert Coder,
  #3640 / #2783);
- a model of other shapes gets its own path (Qwen3.6, DeepSeek) or its own build (the split engine's 27B).

## Issues, PRs and discussions

The searches, all on `--repo Niko1221/Strata`:
- `"Qwen4"`, `"Qwen 4"`, `"Qwen4 Flash"`, `qwen4moe`, `"qwen4next"`, `"Qwen4-"`;
- `"new architecture"`, `"model support"`, `"other models"`, `generalize shapes`, `geometry`, `"model family"`,
  `n_embd`, `"compiled for"`, `block_count`, `expert_count`, `kCompiledGeometry`, `read_geometry`;
- `"Qwen3.9"`, `"Qwen 3.9"`;
- PRs on `"Qwen4"`, and the 40 newest open PRs (11-03 / 11-04).

**Discussions are disabled on the repo** (`has_discussions: false`; the GraphQL discussion search returns 0).

**Qwen4 itself:**
- **#479** (closed 10-02, a DeepSeek V4 Flash request): contributor hendrikp wrote "lets first get qwen4, that one
  should be same architecture ;)". The owner (Niko1221) answered about DeepSeek only: "Strata is built around
  Qwen3.8-Flash-Next's architecture ... fine-tunes of the same model come first." DeepSeek later arrived as its own
  engine anyway.
- No other issue or PR mentions Qwen4. #2227 and #4589 matched only on text, #4589 through the llama.cpp commit title
  above.

**Nearby, open, and relevant to a Qwen4 GGUF:**

| # | state | what it says | why it matters for Qwen4 |
|---|---|---|---|
| 4449 | open (10-28) | A qwen4exp GGUF with its NextN (MTP) block inside (`block_count 49`, `nextn_predict_layers 1`; llama.cpp also writes `attention.recurrent_layers`) does not load: the engine wants exactly 48 layers | llama.cpp-converted Qwen4 GGUFs will likely ship the MTP in-file. Our fork has only part of #619 (pack tool and native_dense, not the load guard). |
| 4843 | open (10-31) | Support the dense `qwen35` family; refused with "architecture is 'qwen35', this engine requires 'qwen4exp'" | the exact refusal a `qwen4` arch string would get |
| 4319 | open (10-27) | Proposal: GLM-5.3-Flash and MiniMax-M3.1-Flash as self-contained families ("following the `src/dsv41` pattern") | the accepted way to add a family |
| 4706 | open (10-30) | 256-expert pruned models on Metal | expert count is free on CUDA, not everywhere |
| 4160 | open (10-25) | Let a modified GGUF of a supported model load (the Terminal already runs it) | app-side gating by known files |
| 5065 | open (11-03) | "Only pre-determined models work"; reply: "If the model isn't supported, it won't run" (therealMKD) | the app's catalog also needs an entry |
| 3640 | open (10-21) | Gyro-Coder: a 256-expert qwen4exp, "already supported" | n_expert < 512 precedent |
| 2783 | closed (10-16) | Third-party qwen4exp GGUFs through `tools/iq_pack.py` | how a non-ISTA qwen4exp file is packed |
| 2396 | closed (10-14) | All-zero `attention.compress_ratios` refused (fixed: treated as absent) | converter variance in the same keys |

## What to watch on release day

1. **The arch string in the first Qwen4 GGUF** (Unsloth, ISTA, llama.cpp's converter):
   - `qwen4exp` with the same widths means the engine loads it (subject to SHAPES.md section 5);
   - anything else means a refusal at `gguf_reader.hpp:681`.
2. **Whether upstream adds a family entry or a new engine path.** tagwatch / qwenpath.py already flag releases that
   touch our served path. A new `src/qwen4*` directory or a `model_family.hpp` change is the signal. Per the standing
   rule, tell Karl when Strata adds Qwen4 support.
3. **Whether #4449 (in-file MTP) is fixed first.** Qwen4 GGUFs from llama.cpp would need it.
