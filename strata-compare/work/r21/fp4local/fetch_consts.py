#!/usr/bin/env python3
"""fetch_consts.py OUT.safetensors - r21 item 7: the three PLE hash constants (int64, a few KB) the converter writes into
its GGUF metadata, range-read from FP4-Local's shard 15 (the tables themselves are not read).  convert_layer.py adds the
file to each layer's weight map; only the expert tensors of that GGUF are kept, so these constants never reach the pack."""
import json
import struct
import sys
import urllib.request

URL = "https://huggingface.co/nvidia/Qwen3.8-Flash-Next-FP4-Local/resolve/main/tensors/model-00015-of-00021.safetensors"
NAMES = [f"model.language_model.layers.1.ple.ple_embedding.{s}"
         for s in ("layer_multipliers", "ngram_heads_offsets", "ngram_heads_vocab_sizes")]


def rng(a, b):
    r = urllib.request.Request(URL, headers={"Range": f"bytes={a}-{b - 1}"})
    return urllib.request.urlopen(r, timeout=60).read()


n = struct.unpack("<Q", rng(0, 8))[0]
hdr = json.loads(rng(8, 8 + n))
base = 8 + n
header, blobs, off = {}, [], 0
for k in NAMES:
    e = hdr[k]
    a, b = e["data_offsets"]
    if b - a > 1 << 20:
        raise SystemExit(f"{k}: {b - a} bytes - not a small constant")
    data = rng(base + a, base + b)
    header[k] = {"dtype": e["dtype"], "shape": e["shape"], "data_offsets": [off, off + len(data)]}
    blobs.append(data)
    off += len(data)
    print(k, e["dtype"], e["shape"])
hb = json.dumps(header, separators=(",", ":")).encode()
hb += b" " * ((8 - len(hb) % 8) % 8)
with open(sys.argv[1], "wb") as f:
    f.write(struct.pack("<Q", len(hb)) + hb + b"".join(blobs))
