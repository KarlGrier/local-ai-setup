#!/bin/bash
# sgpack.sh — round 10 (your addition after D.3): the Signal AP-Q4_K_XL file Round 1's llama.cpp arm used (read-only in the
# HF cache), packed INSIDE the workspace with v0.1.35's tools/iq_pack.py (--compat-bf16, as for UD-Q4_K_XL; no
# --experts-bin). If the packer rejects a tensor format, that is reported and the Signal test stops (marker file).
set -uo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; source $WS/work/r11/env.sh
G=/home/USER/.cache/huggingface/hub/models--agentionai--Signal-3.8-Flash-Next-GGUF/snapshots/eba565bea194b899480ebd8a8ab63d537917004b/AP-Q4_K_XL/Signal-3.8-Flash-Next-AP-Q4_K_XL.gguf
OUT=$WS/work/r11/signal/packs/ap-q4_k_xl; rm -f $WS/work/r11/signal/STOP; mkdir -p $(dirname $OUT)
cd $WS/strata-v36
t0=$(date +%s)
STRATA_GGUF_PY=$WS/strata-v36/third_party/llama.cpp/gguf-py $WS/.venv/bin/python tools/iq_pack.py --gguf $G --out $OUT --compat-bf16 > $WS/logs/r11/sgpack.log 2>&1
rc=$?
tail -25 $WS/logs/r11/sgpack.log
if [ $rc -ne 0 ]; then
  echo "PACKER REJECTED the file (exit $rc) - see above; the Signal test stops here" | tee $WS/work/r11/signal/STOP; exit 1
fi
echo "pack built in $(( $(date +%s) - t0 )) s"; ls -la $OUT; du -sh $OUT
(cd $OUT && find . -type f | sort | xargs sha256sum) > $WS/results/r11/signal-pack.sha256
diff -r -q $OUT/tokenizer $WS/strata-v0115/packs/iq3_s/tokenizer && echo "tokenizer identical to the IQ3_S pack's"
grep -iE 'type|format|q[0-9]_k|iq[0-9]' $OUT/native_experts.txt | head -5
