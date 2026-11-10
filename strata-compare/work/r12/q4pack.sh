#!/bin/bash
# q4pack.sh — round 9 Phase 0.4: the UD-Q4_K_XL pack, built INSIDE the workspace with stock v0.1.31's tools/iq_pack.py
# (--compat-bf16, as docs/UNSLOTH_Q4.md says; no --experts-bin), reading the read-only GGUF in the HF cache.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; source $WS/work/r12/env.sh
G=/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf
OUT=$WS/work/r12/q4/packs/ud-q4_k_xl; mkdir -p $(dirname $OUT)
cd $WS/strata-v0131
t0=$(date +%s)
STRATA_GGUF_PY=$WS/strata-v0131/third_party/llama.cpp/gguf-py $WS/.venv/bin/python tools/iq_pack.py --gguf $G --out $OUT --compat-bf16
echo "pack built in $(( $(date +%s) - t0 )) s"
ls -la $OUT; du -sh $OUT
(cd $OUT && find . -type f | sort | xargs sha256sum) > $WS/results/r12/q4-pack.sha256
# the tokenizer: the same as the IQ3_S pack's? (the draft vocabulary is a subset of these ids)
diff -r -q $OUT/tokenizer $WS/strata-v0115/packs/iq3_s/tokenizer && echo "tokenizer identical to the IQ3_S pack's"
