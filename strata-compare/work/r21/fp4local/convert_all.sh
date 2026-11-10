#!/bin/bash
# convert_all.sh [FIRST] [LAST] - r21 item 7: every staged layer -> convert_layer.py (nvfp4_convert.py + the checks) ->
# models/fp4local/pack/experts.bin, then the pack directory is completed from the GPTQ pack: dense.bin, index.txt and the
# tokenizer as hard links (the same files: dense weights, PLE, embeddings and MTP come from our existing sources),
# native_experts.txt with the same layout and a header naming this source.  Layers already in layers.done.json are
# skipped, so a stopped run resumes.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
PY=$WS/tmp/fp4local/venv-conv/bin/python
GPTQ=$WS/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata/pack
OUT=$WS/models/fp4local/pack
FIRST=${1:-0}; LAST=${2:-47}
log() { echo "$(date +%H:%M:%S) $*"; }
done_layer() { [ -f "$OUT/layers.done.json" ] && python3 -c "import json,sys;sys.exit(0 if sys.argv[1] in json.load(open(sys.argv[2])) else 1)" "$1" "$OUT/layers.done.json"; }
t0=$(date +%s)
for L in $(seq "$FIRST" "$LAST"); do
  if done_layer "$L"; then log "layer $L already done"; continue; fi
  t1=$(date +%s)
  "$PY" "$WS/work/r21/fp4local/convert_layer.py" "$L" || { log "STOP: layer $L failed"; exit 2; }
  log "layer $L: $(( $(date +%s) - t1 )) s, free $(df -B1G --output=avail $WS | tail -1 | tr -d ' ') GB"
done
n=$(python3 -c "import json;print(len(json.load(open('$OUT/layers.done.json'))))")
log "$n of 48 layers converted ($(( $(date +%s) - t0 )) s this run)"
[ "$n" = 48 ] || exit 0
# the pack directory
ln -f "$GPTQ/dense.bin" "$OUT/dense.bin"
ln -f "$GPTQ/index.txt" "$OUT/index.txt"
mkdir -p "$OUT/tokenizer"
for f in "$GPTQ"/tokenizer/*; do ln -f "$f" "$OUT/tokenizer/$(basename "$f")"; done
python3 - "$GPTQ/native_experts.txt" "$OUT/native_experts.txt" <<'PY'
import sys
src, dst = sys.argv[1:]
lines = open(src).read().splitlines()
h = lines[0]
assert h.startswith("# strata native experts v3:") and "(n_expert 512, total " in h, h
total = h.split("total ", 1)[1].split(";", 1)[0]
lines[0] = (f"# strata native experts v3: layer gu_type d_type offset blob_bytes (n_expert 512, total {total}; experts.bin = "
            "nvidia/Qwen3.8-Flash-Next-FP4-Local's routed experts (QAD, ModelOpt 0.47.0): CSF block scales decoded to "
            "E4M3, repacked without loss by tools/nvfp4_convert.py - work/r21/fp4local)")
open(dst, "w").write("\n".join(lines) + "\n")
PY
size=$(stat -c %s "$OUT/experts.bin"); want=$(stat -c %s "$GPTQ/experts.bin")
[ "$size" = "$want" ] || { log "STOP: experts.bin is $size bytes, the GPTQ pack's $want"; exit 2; }
log "pack ready: $OUT (experts.bin $size bytes, $(du -h "$OUT/experts.bin" | cut -f1) on disk)"
ls -la "$OUT"
