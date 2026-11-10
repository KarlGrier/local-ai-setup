# Models

These are the model files this setup runs, with where each came from, its sha256, and how to get it back. No weights are in this repo.

Paths are relative to the workspace folder `strata-compare/` unless they say otherwise. Sizes are in bytes.

## What the served configs use

| Config | What | Packs used |
|---|---|---|
| `configs/P028x.json` (Qwen, port 8080) | The daily | A (IQ3_S, both shards), B (picture reader), C (MTP draft layer), D1 (pack), E (expert profile) |
| `configs/P021m.json` | The Qwen rollback | The same files, with another engine |
| `configs/Cstar18-single.json` | The one-GPU fallback | A, C, D2, E |
| `configs/DS41-daily.json` (DeepSeek, port 8086) | The DeepSeek daily (`./switch-model.sh deepseek`) | F1, F3 (converted drafter), F-pack-2, F5 |
| `configs/DS41-daily.json.before-c2` | The DeepSeek rollback | F1, F2 (Q8_0 drafter), F-pack-1, F5 |

## A. Qwen3.8-Flash-Next GSQ-RCO IQ3_S (served)

- **Source:** [ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF), revision `2a55d75962e22f7a4a1d9963ab6eae3678537831`. Strata's `setup.py` pins the same two hashes at revision `ed59f92082b1e93c0e96d60a8b11aab089b52f09`.
- **Folder:** `models/ISTA-GSQ-RCO/IQ3_S/`

| File | Bytes | sha256 |
|---|---|---|
| `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` | 54,817,524,224 | `4c1eb2ceb4915e1192f4f386021897bde56a97f40a0bb78bb86465e0f7d2aca3` |
| `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` | 28,800,138,432 | `316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113` |

```
hf download ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF --revision 2a55d75962e22f7a4a1d9963ab6eae3678537831 \
   --include 'IQ3_S/*' --local-dir models/ISTA-GSQ-RCO
sha256sum models/ISTA-GSQ-RCO/IQ3_S/*.gguf
```

## B. The picture reader's mmproj (served)

- **Source:** the same ISTA repo, revision `ed59f92082b1e93c0e96d60a8b11aab089b52f09`.
- **File:** `models/vision-r22/mmproj-Qwen3.8-Flash-Next-BF16.gguf`, 907,543,008 bytes, sha256 `b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0`.
- The reader binary `strata-vision` is built with the engine.

## C. The MTP draft layer `rt` (served)

**Folder:** `strata-v0115/mtp/rt/`. The same files are hard-linked into `strata/mtp/rt/`, `models/mtp-stock/rt/` and `models/mtp-basalt/rt-tuned/`. Keep the links, or the backup stores them four times.

| File | Bytes | sha256 |
|---|---|---|
| `dense.bin` | 116,099,072 | `c724dc0b0822ada5d2977bf5bde821605feabaa64ea2e0045b67ca656329070a` |
| `dense.txt` | 1,851 | `991456cf4eb266eb8a888c349e548d11bc640f5dbd9149439aa9786af0f732fd` |
| `draft_vocab.bin` | 162,100 | `369151522226a5edaa5f12cfd1e2ae7db8f4fbdbd222f3dcf327dced9597fb25` |
| `experts.bin` | 707,788,800 | `09398406be61f1f54c93861f449e48b8df0bfccbc9ec9b2b7636775a6ea9244f` |

Rebuild it either of two ways.

**From Qwen's BF16 checkpoint** ([Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) at `de4b8e4d43b917e7706784d8bb445c9af86a3540`). Only the 31 `mtp.*` tensors are needed, about 5.2 GB, fetched by HTTP range reads. Run these with Strata v0.1.6's tools:
```
python scripts/mtp_fetch_pinned.py strata de4b8e4d43b917e7706784d8bb445c9af86a3540 fetch --out strata/mtp
python strata/tools/mtp_pack.py --src strata/mtp --experts q2_0 --out strata/mtp/mtp-q2_0.gguf
python strata/tools/mtp_rt.py --gguf strata/mtp/mtp-q2_0.gguf --out strata/mtp/rt
```
Then copy `data/draft_vocab.bin` from Strata v0.1.6.

**From Unsloth's shared-BF16 MTP file** (`unsloth/Qwen3.8-Flash-Next-GGUF` at `d96201194f103c906994f283f504209dc8d2a10c`, sha256 `32473fa74e8ed0f0026219b09b43d303f52f328c0f8b0caf4b24bf8834cc596b`). Use `work/qwen4-kit/mtp_from_gguf.py`; on 11-04 it gave a byte-identical result.

Other copies of C:
- `models/mtp-stock/rt` uses Strata v0.2.1's draft vocabulary: 425,196 bytes, `b1e1d3a7a9e4bf862dcd5923ce661fb59bbd07907e594df5cf86a62ac235cb91`.
- `models/mtp-basalt/rt-tuned/dense.bin` is Basalt's tuned dense layer from [jesdga/Qwen3.8-Flash-Next-Basalt](https://huggingface.co/jesdga/Qwen3.8-Flash-Next-Basalt): 116,099,072 bytes, `dfe18647e0c95d05302907be88f021590119645a1567fcd770c8d309df852d75`.

Neither is served.

## D. Strata pack of the IQ3_S model (served)

**D1. `bringup/out/r20a/pack`** is served. Every file's sha256 is in `bringup/out/r20a/pack.sha256`. For example, `dense.bin` is 1,538,035,200 bytes, `d2af3d8331e5c7a1985d1d589747230f9d56719a6d33c7cddc9ee6b81cde6b13`. It was made in Strata v0.1.44.1 (`296b59d2f73c8f04a805df29c2fa97655adace78`):
```
STRATA_GGUF_PY=<its pinned llama.cpp>/gguf-py python tools/iq_pack.py \
   --gguf models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf --out bringup/out/r20a/pack
sha256sum -c bringup/out/r20a/pack.sha256
```
Rerunning `bringup/runbook.sh` with `bringup/out/r20a/run.env` does the same.

**D2. `strata-v0115/packs/iq3_s`** is the fallback's pack. It has the same bytes as D1, without `conversions.json`.

## E. The Qwen expert profile (served)

`strata-cstar18/data/expert-profile.bin`: 196,632 bytes, `8f59b4aa8873209dff11c11e37bcda9529a1335b724a1afeea37bf6388975baf`. It is a file of the Strata repository and comes with the engine checkout.

## F. DeepSeek-V4.1-Flash-1017 (the DeepSeek daily)

**Folder:** `models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/`

**F1. The weights** come from [ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF](https://huggingface.co/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF) (MIT). The values below are Strata v0.2.6's pins at revision `cb02422c900df489cea5833e8a92171224059b3c`. Our download checked each file against the Hub's LFS hash, and the names and sizes match these pins.

| File | Bytes | sha256 |
|---|---|---|
| `DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00001-of-00004.gguf` | 39,075,714,624 | `d46efb67ccffd8fb5d7f18b423896381b9e06d8491e161c370ddf3b05b07e050` |
| `DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00002-of-00004.gguf` | 39,388,449,504 | `cec1b2c3da429dc768b8bb9bc4dc4403d81f74d34db660a6a34ee3e555bf2c70` |
| `DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00003-of-00004.gguf` | 39,246,891,616 | `9d9c2140fcb134a0b9a74dedd0e5167e68077af6d08ce7f856bce112f0a35dd3` |
| `DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00004-of-00004.gguf` | 20,527,837,312 | `9b790a2297ed3cdede379fc984f4a52bb95f3b23724c797af11d1fa6a69db059` |
| `DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf` | 110,595,290,816 | `eb19f30d368d393784e1fc54fdfaffc427ebb2110bf3762fdf5a8fbb9a2d740a` |

```
hf download ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF --revision cb02422c900df489cea5833e8a92171224059b3c \
   --include '*IQ2_XXS*' 'DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf' --local-dir models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF
```
Or rerun `work/ds41/download.py`, which checks the LFS hashes.

**F2. From [unsloth/DeepSeek-V4.1-Flash-1017-GGUF](https://huggingface.co/unsloth/DeepSeek-V4.1-Flash-1017-GGUF)** (MIT), revision `f924b94f19c1fea02c06a65c8475b0a45e2b88b1`. `work/ds41/fetch-extra.sh` fetches and checks both files.

| File | Bytes | sha256 |
|---|---|---|
| `DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL-00001-of-00009.gguf` (metadata only; the pack reads the Engram parameters from it) | 5,780,589 | `cc15d470afcb030558bbc4d8e2ccd840182e2e95de1a95198138efe63a5fd99f` |
| `dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf` (DeepSeek's DSpark drafter; the conversion template) | 7,976,914,240 | `6ba6ac1b331c540691a209e7fc97dec2a24e295acb1e755c84c7d24a4373927a` |

**F3. Lucebox's DSpark drafter** (MIT), folder `lucebox-dspark/`, used by the daily since 11-09:
- **Source:** `Lucebox/DeepSeek-V4.1-Flash-DSpark-GGUF` at `11403d34ca19eb1ac2b532b5a05e61a4b0c61485`, file `DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf`: 4,923,041,440 bytes, `5efffdb5ab4769bac7192fd2ce7c08cfa37945cad37be0825526c83139ef200a`. `work/ds41/gate/get-lucebox-dspark.sh` fetches and checks it.
- **Our conversion** is `dspark-lucebox-Q2K-Q4K-converted.gguf`: 4,928,310,816 bytes, `dac6177b613041709449443ffc98cf503dd2952f62e656e8aa562be7b5d56f4a`. It does no requantization: tensors are renamed into Unsloth's layout and two small tensors are widened exactly.
```
python -I work/ds41/gate/convert_lucebox_dspark.py lucebox-dspark/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf \
   dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf lucebox-dspark/dspark-lucebox-Q2K-Q4K-converted.gguf
python -I work/ds41/gate/check_converted.py ...
```

**F4. The packs** are index folders a few MB in size. Their `ds4.txt` names the model folder by absolute path, so rebuild the packs after moving the models.
- `pack-ist-das-2.00bpw/` is the rollback; `work/ds41/pack.sh` makes it with Strata v0.2.4's `tools/dsv41/pack_gguf.py`.
- `pack-ist-das-2.00bpw-lucebox-q2k/` is the daily. It is the same command with `--dspark-gguf` set to the converted F3 file, run by `work/ds41/gate/gate.sh` step CP.

**F5. The DeepSeek expert profile:** `configs/DS41-daily-profile.seed.bin`, 66,048 bytes, `8db93e483b34b15dbf63a0826601f1db2107a8cfea73774e7d21d8559e0a9568`. It equals Strata v0.2.4's `data/dsv41/profile-2.00.bin`. The engine rewrites its profile file on exit, so the daily config copies this seed.

## Kept, not served

| Pack | Source | sha256 |
|---|---|---|
| G. NVFP4-GPTQ Strata pack, `models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata/` (128 GB) | `Maximilian228/Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata` at `640a1db97446ddd5e89d2b70ecd0297987192c93`; `work/nvfp4/download.sh` | All 12 files, each in its `<name>.done` file |
| H. Round-15 splice, `models/r15/splice-q5/Qwen3.8-Flash-Next-r15splice-Q5experts-IQ3S.gguf` (131.7 GB) | `work/r15/splice.py`: the routed experts of Unsloth's UD-Q5_K_XL (`unsloth/Qwen3.8-Flash-Next-GGUF` at `38bb39ee97821de2c9009abb7e93950eec396e66`) plus everything else from A | `9cc459c8c5500e4dfb05e6ed8679bd3ff7da6966af3be4f398a4286f433f2a65`; the source shards' hashes are in `results/r19/integrity/models.tsv` |
| I. Basalt v2 pack, `basalt-020/models/Qwen3.8-FN-GSQ-RCO-IQ3_S.basalt` (87.6 GB) | `jesdga/Qwen3.8-Flash-Next-Basalt` (commit `f6fbe4e8df9af1d652896c7990ee781a4d171579` or later); `basalt-020/scripts/get-pack.sh` | `a09867acc927928509baca0d6ef046fae176cb7af87b9b82a8d1e3c6775ff10a` |
| J. GLM-5.3-Flash UD-Q2_K_XL (in the Hugging Face cache; always kept) | `unsloth/GLM-5.3-Flash-GGUF` at `a38483c8cd5df544f53d70fb281afe97369d5ab6` | The cache's etags (LFS sha256), e.g. shard 1 `2f32eba33ebc75a715e9c85a010faac4c67542e38e8970bd961d544bfe815f9e` |

## Checking everything

`work/r19/integrity/verify_models.py` hashes every model file and compares the copies. It last ran over all files on 2026-10-10, with the results in `results/r19/integrity/models.tsv`.

Weight licenses:

| Weights | License |
|---|---|
| Qwen3.8-Flash-Next quants | Apache-2.0, per the ISTA card |
| DeepSeek-V4.1-Flash sets | MIT, per the ISTA, Unsloth and Lucebox cards |
| Basalt `.basalt` pack | `qwen-community-1.0`, per its card |
