#!/bin/bash
# pack.sh - 10-23: v0.2.4's stock pack for the IST-DAS 2.00 bpw set (IQ2_XXS), the recipe setup.py runs (dsv41_pack_cmd: this
# and nothing else - --skip-tensors / --dense-override pack without an error and give garbage text): the four shards,
# --engram (the shared IQ4_NL table), --engram-meta (Unsloth's UD-Q8_K_XL shard 1: the Engram hash parameters),
# --dspark-gguf (the drafter), noise token 128799, markov rank 256. The pack is an index beside the files (no weights
# copied). Then the shipped hot-expert profile (data/dsv41/profile-2.00.bin, sha256 checked) as <pack>/expert-profile.bin
# and strata-dsv41 --pack-info (every file present).
set -euo pipefail
SC=/home/USER/ai-speed-testing/strata-compare; W=$SC/strata-v024
M=$SC/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF; P=$M/pack-ist-das-2.00bpw
S=(DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-0000{1,2,3,4}-of-00004.gguf)
[ -e $P ] && { echo "$P exists - not packing again"; exit 1; }
$SC/.venv/bin/python $W/tools/dsv41/pack_gguf.py --model $M --shards "${S[@]}" \
  --engram $M/DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf --engram-meta $M/DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL-00001-of-00009.gguf \
  --dspark-gguf $M/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf --dspark-noise-token 128799 --dspark-markov-rank 256 --out $P
( cd $W/data/dsv41 && sha256sum -c profile-2.00.bin.sha256 )
cp $W/data/dsv41/profile-2.00.bin $P/expert-profile.bin
LD_LIBRARY_PATH=/usr/local/cuda-13.3/lib64 $SC/engine-v024-ds41/strata-dsv41 --pack $P --pack-info
du -sh $P
