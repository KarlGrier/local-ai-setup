#!/usr/bin/env python3
"""peek.py SHARD_PATH [N_EXPERTS] - range-read one FP4-Local shard's safetensors header and a few experts' CSF scale
streams from Hugging Face (KBs, not the shard), decode them and run the round-trip check (csf.py)."""
import json, struct, sys, urllib.request
import numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
from csf import checkpoint_round_trip, decode
URL = "https://huggingface.co/nvidia/Qwen3.8-Flash-Next-FP4-Local/resolve/main/" + sys.argv[1]
def rng(a, b):
    r = urllib.request.Request(URL, headers={"Range": f"bytes={a}-{b - 1}"})
    return urllib.request.urlopen(r, timeout=60).read()
n = struct.unpack("<Q", rng(0, 8))[0]
hdr = json.loads(rng(8, 8 + n)); base = 8 + n
meta = hdr.pop("__metadata__", {})
print("metadata:", meta)
names = sorted(k for k in hdr if k.endswith(".nvfp4_csf_fixed"))
print(len(hdr), "tensors,", len(names), "csf pairs; dtypes:", sorted({v["dtype"] for v in hdr.values()}))
for k in names[:int(sys.argv[2]) if len(sys.argv) > 2 else 3]:
    b = k[:-len(".nvfp4_csf_fixed")]
    f, e = hdr[k], hdr[b + ".nvfp4_csf_exceptions"]
    w = hdr.get(b.rsplit(".weight_scale", 1)[0] + ".weight")
    fixed = np.frombuffer(rng(base + f["data_offsets"][0], base + f["data_offsets"][1]), np.uint8).reshape(f["shape"])
    exc = np.frombuffer(rng(base + e["data_offsets"][0], base + e["data_offsets"][1]), np.uint32) if e["data_offsets"][1] > e["data_offsets"][0] else np.zeros(0, np.uint32)
    r = checkpoint_round_trip(fixed, exc)
    sc = decode(fixed, exc)
    print(b, "| fixed", f["dtype"], f["shape"], "| exc", e["dtype"], e["shape"], "| weight", w and (w["dtype"], w["shape"]))
    print("   ", r, "| scale bytes min/max", int(sc.min()), int(sc.max()), "| distinct", len(np.unique(sc)))
