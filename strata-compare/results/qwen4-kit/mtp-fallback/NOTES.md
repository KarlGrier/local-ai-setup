# The drafter fallback: Unsloth's MTP GGUF -> our rt format (11-04)

Karl's item (2) of the Qwen4 day-one kit. The converter is `work/qwen4-kit/mtp_from_gguf.py`. Its offline self-test
passes: `selftest/selftest.log`, `selftest/selftest.json`. Nothing was downloaded, no GPU was used and nothing was
installed. The GPU check is only planned: `CHECK-PLAN.md`.

## Answer first

- **File to download: `MTP/mtp-Qwen3.8-Flash-Next-shared-BF16.gguf`.** Pinned at commit
  `d96201194f103c906994f283f504209dc8d2a10c`: 5,227,963,456 B, LFS sha256
  `32473fa74e8ed0f0026219b09b43d303f52f328c0f8b0caf4b24bf8834cc596b` (from `work/qwen4-kit/unsloth-v31/dl/tree.json`).
  - **Why BF16:** it is the only published format that can rebuild our rt bit for bit. Our rt is the BF16 checkpoint
    run through mtp_pack's Q2_0 and mtp_rt's Q8_0, with BF16 kept for the mixers. A Q8_0 file still gives the ten Q8_0
    projections exactly, but it rounds the ten BF16 tensors and yields different Q2_0 experts (test T1 `q8_0-shared`).
    Q4_K_M is lossy everywhere.
  - **Why "shared":** it holds the same MTP tensors as the standalone file. The only difference is that it leaves out
    `token_embd.weight` and `output.weight`, which are 2.54 GB in BF16. Our drafter takes both from the main model and
    never stores them, so the shared file is the full source and 2.5 GB smaller (5.23 GB against 7.77 GB).
  - **What the file holds, predicted from its size:**
    - all matrices are BF16 (the experts alone are 5,033,164,800 B);
    - the router, the shared-expert gate and the 9 norms are F32;
    - that makes 5,217,016,832 B of data, plus the same 10,946,624-B header as shared-Q8_0, which is exactly the file
      size.
    - So all 31 checkpoint tensors arrive in a format that can be exact.
- **Our rt is the BF16 checkpoint, reproduced exactly (offline, our own checkpoint copy):**
  - our raw checkpoint tensors (`strata/mtp/tensors/`, which hash to the manifest) were laid out the way Unsloth's
    shared-BF16 file is;
  - the converter turned that into dense.txt, dense.bin (sha256 c724dc0b…) and all 512 experts of experts.bin
    (09398406…);
  - all of these are **byte-identical** to `strata-v0115/mtp/rt`, using today's numpy 2.5.3.
  - So if Unsloth's BF16 values are the checkpoint's (revision de4b8e4d), `verify` will say IDENTICAL. Then the GPU
    check is only a confirmation (CHECK-PLAN outcome I, about 10 minutes with 8080 down).
- **Still unknown until the file is here:** whether Unsloth used the same checkpoint revision, and their layout
  choices: the eh_proj half order, the q/k order and the "+1" on norms. `verify` settles every one of them per tensor
  against the pinned checkpoint's sha256s. Any tensor that differs is named.

## How our drafter is made (the reference)

`strata-v0115/setup.py:987-998` (also NOTES.md:36 and :4390) chains three tools, all in `strata-v0115/tools/` and all
unchanged in the served `strata-r22p028x/tools/` except mtp_fetch's download code:

1. **`mtp_fetch.py`** range-reads the 31 `mtp.*` BF16 tensors from Qwen/Qwen3.8-Flash-Next (28 of 131 shards, 5.214
   GB; pinned to `de4b8e4d` by `scripts/mtp_fetch_pinned.py`).
   - Output: `mtp-manifest.json` with each tensor's dtype, shape and sha256.
   - The raw tensors are still in `strata/mtp/tensors/`.
2. **`mtp_pack.py --experts q2_0`** writes `mtp-q2_0.gguf` (889 MB):
   - the 1-D tensors as F32 = f32(bf16);
   - every 2-D tensor as raw BF16;
   - the two fused expert tensors as Q2_0: 64-value blocks, the fp16 scale chosen per block by the smallest squared
     error over 17 candidates from amax/2 to amax, codes q+1 in 2 bits.
3. **`mtp_rt.py`** writes the rt directory from that GGUF, in sorted checkpoint-name order:
   - `dense.txt`: 29 lines of `name kind rows cols off bytes`;
   - `dense.bin`: each tensor 256-byte aligned;
   - the kinds in dense.bin:

     | kind | count | tensors | how |
     |---|---|---|---|
     | q8_0 | 10 | fc_embedding, fc_hidden, the four attention projections, index_qk_proj, the three shared-expert projections | ggml's reference rounding |
     | bf16 | 10 | the 6 hyper-connection mixers, 2 injects, mlp.gate, shared_expert_gate | raw BF16 |
     | f32 | 9 | 3 hc_norms, 2 pre_fc norms, q/k norm, indexer q/k layernorm | f32(bf16 w) **+ 1** (Gemma) |

   - `experts.bin`: 512 blobs of 1,382,400 B each. Gate/up rows are interleaved (2r = gate r, 2r+1 = up r), followed
     by the down rows. The layout is code planes first, then the fp16 scale planes: [gu codes | dn codes | gu scales |
     dn scales].
4. **`draft_vocab.bin`**: setup copies it from `data/draft_vocab.bin`. It holds 40,525 token ids (162,100 B), the draft
   head's subset of the main head. It is tokenizer data, not MTP weights.

How the engine reads it (`strata-r22p028x/src/core/mtp.cpp`):
- It loads dense.txt, dense.bin and experts.bin (mtp.cpp:305-353).
- It requires nine q8_0 projections (mtp.cpp:355).
- `index_qk_proj` is in the file but is not used at run time: the draft layer does dense attention (mtp.cpp:380).
- The token embedding and the head (with the draft_vocab subset) come from the main model (mtp.cpp:962, :1268).

## Unsloth's MTP files (headers in `work/qwen4-kit/unsloth-v31/headers/MTP/`, read with python -I)

`qwen4exp`, block_count 49, `nextn_predict_layers` 1; one layer `blk.48`; the same 37 shape keys and tokenizer as the
main files. llama.cpp names, with ggml `ne` = the checkpoint shape reversed:

| GGUF (blk.48.) | checkpoint (mtp.) | transform |
|---|---|---|
| `nextn.eh_proj` [5120, 2560] | `fc_embedding`, `fc_hidden` (2560 x 2560 each) | column halves: 0..2559 = fc_embedding (default; llama.cpp's nextn convention "eh_proj over [enorm(e) \| hnorm(h)]", strata-r22p0210/src/qwen35/q36_engine.cu:867) |
| `nextn.enorm` / `nextn.hnorm` | `pre_fc_norm_embedding` / `pre_fc_norm_hidden` | norm |
| `nextn.hc_head_{norm,down,up}` | `hyper_connection_mixer.{hc_norm, input_mix_weight_down, _up}` | (the main model's `output_hc_*` analogue) |
| `hc_attn_*`, `hc_ffn_*` ({norm,down,up,inject}) | `layers.0.{attn,mlp}_hyper_connection.{hc_norm, input_mix_weight_down, _up, block_inject_weight}` | - |
| `attn_{q,k,v,output}`, `attn_{q,k}_norm` | `layers.0.self_attn.{q,k,v,o}_proj`, `{q,k}_norm` | - |
| `indexer.q_proj` [2560, 512] + `indexer.k_proj` [2560, 128] | `layers.0.self_attn.indexer.index_qk_proj` [640, 2560] | rows [q; k] (llama.cpp's conversion/qwen4exp.py:124 splits the main model's as q = rows[:n_q]) |
| `indexer.{q,k}_norm` | `...indexer.{q,k}_layernorm` | norm |
| `ffn_gate_exps` + `ffn_up_exps` [2560, 640, 512] | `layers.0.mlp.experts.gate_up_proj` [512, 1280, 2560] | rows [gate; up] (conversion/qwen.py:104-117 splits it so) |
| `ffn_down_exps` [640, 2560, 512] | `layers.0.mlp.experts.down_proj` [512, 2560, 640] | - |
| `ffn_gate_inp` [2560, 512] F32 | `layers.0.mlp.gate.weight` | F32 -> BF16 (exactness checked) |
| `ffn_gate_inp_shexp` [2560] F32 | `layers.0.mlp.shared_expert_gate.weight` [1, 2560] | 1-D -> [1, H], F32 -> BF16 |
| `ffn_{gate,up,down}_shexp` | `layers.0.mlp.shared_expert.{gate,up,down}_proj` | - |
| `token_embd`, `output` (standalone files only) | - | not used (the main model's) |

- **"shared" means:**
  - `qwen4exp.nextn_shared_target_tensors = true`, 32 tensors instead of 34;
  - no `token_embd.weight` / `output.weight`: the drafter takes the target's embedding and head (size label 512x95M
    instead of 512x1.4B);
  - checked on the Q8_0 pair: names, types and shapes are otherwise identical, and the offsets are shifted by exactly
    the two missing tensors (2 x 675,430,400 B). The BF16 pair's sizes differ by 2,542,796,864 B, which is the BF16
    embedding plus head plus 64 header bytes.
- **Norms:**
  - Our rt stores f32(w) + 1. llama.cpp's qwen4exp converter applies the same "+1" in F32: on the ISTA main file
    every norm v has v - 1 BF16-exact (hc_attn_norm, indexer.k_norm, attn_q_norm, output_hc_norm).
  - `--norms auto` decides per tensor: v - 1 BF16-exact and v not means "+1 stored"; v BF16-exact means raw. It falls
    back to the majority vote.
  - Storing w + 1 in F32 loses weights with |w| < 2^-16. In our checkpoint this is 1 value each in
    `mlp_hyper_connection.hc_norm` (|w| 6.5e-6) and `pre_fc_norm_hidden` (2.1e-7). The rt bytes are still identical,
    because the rt holds fl(w + 1) too; the tool reports these as `ckpt ~`.

## The converter (`work/qwen4-kit/mtp_from_gguf.py`)

```
P=.venv/bin/python; K=work/qwen4-kit/mtp_from_gguf.py         # run with nice -n 19; GGUF bytes are parsed, never run
$P -I -B $K inspect GGUF                     # header only (head-only files work): mapping, dims, exactness forecast
$P -I -B $K verify  GGUF --report J.json     # nothing written: rt bytes in memory vs strata-v0115/mtp/rt, and each
                                             # reconstructed checkpoint tensor vs the manifest's sha256
$P -I -B $K convert GGUF --out NEW_DIR       # writes dense.bin / dense.txt / experts.bin / draft_vocab.bin + NEW_DIR.conversion.json
$P -I -B $K selftest --out DIR [--hash-ckpt] # the offline tests below
```

- **Behaviour:**
  - The arithmetic is mtp_pack's `q2_0` and mtp_rt's `q8_0` / `blob_of`, copied verbatim. Test T0 checks them against
    the tools' own functions, which it extracts from `strata-v0115/tools` by AST. `--tools` can point it at another
    tree; the 0.2.10 tree passes.
  - Sources can be BF16 (exact), F32/F16 holding BF16 values (exact), Q8_0 (exact for the Q8_0 kinds only, because
    re-quantizing ggml-reference Q8_0 gives the same bytes) or any other type (dequantized by the pinned gguf-py, then
    rounded).
  - The eh / qk order is `auto`: decided by sha256 against the manifest, otherwise the defaults above. `--eh-order` and
    `--qk-order` override it.
  - Every tensor is reported: exact or rounded, `ckpt =` / `~` / `DIFFERS`, `rt identical` / `DIFFERS` with the
    number of differing blocks or values and the largest difference.
- **Safety:**
  - It refuses to write into a directory that exists and is not empty, and into `strata-v0115/`, `strata/`,
    `configs/` or `tools/`.
  - It reads at most `--max-mbps` (400 by default) during the expert pass, and drops the pages it read afterwards.
  - It writes experts.bin with an fdatasync and DONTNEED every 64 experts.
- **Dims are taken from the file** (H, FF, experts, hc width, low rank), so it would work for a Qwen4 MTP GGUF of the
  same shape family. Our engine's rt reader is compiled for Flash-Next's blob size, though; a Qwen4 release brings its
  own.

### Self-test (`selftest/`, 11-04 13:10, final code sha256 bd3ac761…; 87 s at nice 19, the checkpoint read at most 300 MB/s)

| test | what | result |
|---|---|---|
| T0 | q2_0 / q8_0 / blob_of = strata-v0115/tools' functions (normal, zero, 1e-6, x300, random-BF16 inputs) | PASS |
| T1 x 7 | a tiny GGUF in Unsloth's layout, written by gguf-py's GGUFWriter (an independent writer), against the rt the same writer makes straight from the checkpoint. Variants: shared, standalone (token_embd + output, reported unused), raw norms, router BF16, eh halves swapped (auto picks "he"), q/k swapped (auto picks "kq"), all-Q8_0 (as expected: Q8_0 projections and norms identical, the BF16 tensors rounded, the experts re-quantized) | 7 PASS |
| T2 | the 31 raw checkpoint tensors (sha256 = the manifest) laid out as Unsloth's shared-BF16 file in memory -> rt | **identical to strata-v0115/mtp/rt**: dense.txt, dense.bin, 512/512 experts; checkpoint sha256s = manifest (2 norm values not recoverable, rt unaffected) |

Also checked:
- `inspect` on both real headers: all 31 tensors map, with the manifest's shapes and nothing unmapped. Saved in
  `inspect-shared-Q8_0.txt` and `inspect-Q8_0.txt`.
- On a tiny GGUF file through the CLI: `verify` = IDENTICAL; `convert` gives four files that `cmp` equal to the
  reference; both refusals work.
- `verify` on a head-only file stops with a message.

What T2 does not prove: that Unsloth made the same choices. T2's forward direction is my model of their converter, and
it was written separately from the converter's mapping. The real file decides.

## When the file is here (no GPU, about 2 min)

```
WS=/home/USER/ai-speed-testing/strata-compare; P=$WS/.venv/bin/python; K=$WS/work/qwen4-kit/mtp_from_gguf.py
G=<DEST>/mtp-Qwen3.8-Flash-Next-shared-BF16.gguf      # sha256 checked by gentle_dl.py
nice -n 19 $P -I -B $K inspect $G
nice -n 19 $P -I -B $K verify  $G --report $WS/results/qwen4-kit/mtp-fallback/verify-shared-BF16.json
nice -n 19 $P -I -B $K convert $G --out $WS/work/qwen4-kit/mtp-fallback/rt-ud-shared-bf16
for f in dense.bin dense.txt experts.bin draft_vocab.bin; do cmp $WS/work/qwen4-kit/mtp-fallback/rt-ud-shared-bf16/$f $WS/strata-v0115/mtp/rt/$f; done
```

How to read the outcome:
- **IDENTICAL:** Unsloth's file is our checkpoint. The fallback is proven offline, and the GPU check reduces to
  outcome I in CHECK-PLAN.
- **Some tensors differ:** the report names each one, with "ckpt DIFFERS" (other weights or another revision) or
  "ROUNDED" (a non-BF16 type). Typical causes:
  - a "+1" computed in BF16: the f32 norms differ at about 2^-8;
  - an eh order the sha could not decide: both halves would show DIFFERS;
  - another checkpoint revision: everything differs.
  - In any of these cases run CHECK-PLAN outcome II: acceptance against ours on the GPU.

## For Qwen4 day one

1. First try the checkpoint route (`tools/mtp_fetch.py` of the release). If it cannot read Qwen4's checkpoint, use the
   publisher's MTP GGUF:
   - `inspect` shows whether the names map. A new tensor shows as "unmapped"; extend `entries()`.
   - Take the BF16 shared variant.
2. Check the release's `mtp_rt.py` with `selftest --tools <release>/tools` (T0). If its kinds or Q8 set change, the
   converter's `Q8` / norm rules must follow.
3. There is no manifest for a new model, so the eh / qk orders fall back to the defaults. Confirm them from the
   publisher's converter or llama.cpp's graph (the `ggml_concat(enorm, hnorm)` order). A wrong half order shows as an
   acceptance near zero in the GPU check.
4. `draft_vocab.bin` is per tokenizer: make it with the release's `tools/draft_vocab.py`. Without one, the draft head
   is the whole main head.

## Files

- `work/qwen4-kit/mtp_from_gguf.py`: the converter.
- `work/qwen4-kit/mtp-fallback/mtp_accept.py`: the GPU check's table and verdict.
- `results/qwen4-kit/mtp-fallback/`:
  - `selftest/`, `inspect-*.txt`;
  - `P028x-mtp-ours.json` / `P028x-mtp-ud.json`: the check's two arms, copies of P028x that differ only in `--mtp`
    (own logs, no fallback; not installed);
  - `CHECK-PLAN.md`.
- Scratch: `work/qwen4-kit/scratch-c/`.
