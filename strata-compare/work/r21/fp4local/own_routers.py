#!/usr/bin/env python3
"""own_routers.py - r21 item 7 (your 10-16 OK): FP4-Local with its own routers.  NVIDIA's QAD retrained the 48 MoE
routers along with the experts (dense_check.py: rel 1.1-1.5 %, the shared-expert gates identical), and our FP4-Local
pack serves the GPTQ pack's routers.  This builds models/fp4local/pack-own-routers: the same experts.bin, index.txt,
native_experts.txt and tokenizer (hard links), and a COPY of dense.bin with the 48 `blk.L.ffn_gate_inp.weight`
entries (BF16 [512 x 2560], the engine reads the router from the pack, src/core/layer.cpp moe_route) replaced by
FP4-Local's `model.language_model.layers.L.mlp.gate.weight` (BF16, range-read from its shard 15).  Nothing else changes;
the GPTQ pack and models/fp4local/pack are not touched.

Checks: each router entry is 2,621,440 B at its index offset; before patching, the pack's bytes equal the dense GGUF's
`blk.L.ffn_gate_inp.weight` bytes (the same layout the engine and the GGUF use); FP4-Local's tensor is BF16 [512, 2560];
after patching, the copy's router bytes equal FP4-Local's and every other byte equals the original dense.bin.
Writes results/r21/fp4local/own-routers.json (per layer: rel. difference, sha256 of the new bytes)."""
import hashlib
import json
import os
import shutil
import struct
import sys
import urllib.request
from pathlib import Path

import numpy as np

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "strata-cstar18/third_party/llama.cpp/gguf-py"))
import gguf  # noqa: E402

URL = "https://huggingface.co/nvidia/Qwen3.8-Flash-Next-FP4-Local/resolve/main/tensors/model-00015-of-00021.safetensors"
SRC = WS / "models/fp4local/pack"
DST = WS / "models/fp4local/pack-own-routers"
GG = WS / "models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata/qwen-nvfp4-gptq-dense.gguf"
OUT = WS / "results/r21/fp4local/own-routers.json"
NBYTES = 512 * 2560 * 2


def rng(a, b):
    r = urllib.request.Request(URL, headers={"Range": f"bytes={a}-{b - 1}"})
    for _ in range(4):
        try:
            data = urllib.request.urlopen(r, timeout=120).read()
            if len(data) == b - a:
                return data
        except OSError:
            pass
    raise SystemExit(f"range {a}-{b} failed")


def bf16(raw):
    return (np.frombuffer(raw, np.uint16).astype(np.uint32) << 16).view(np.float32)


def main():
    if DST.exists():
        raise SystemExit(f"{DST} exists - remove it first")
    ents = {}
    for line in (SRC / "index.txt").read_text().splitlines():
        f = line.split()
        if f and f[0].endswith(".ffn_gate_inp.weight") and f[0].startswith("blk."):
            ents[int(f[0].split(".")[1])] = (int(f[3]), int(f[4]))
    if sorted(ents) != list(range(48)) or any(s != NBYTES for _, s in ents.values()):
        raise SystemExit(f"index: {len(ents)} router entries, sizes {set(s for _, s in ents.values())}")
    G = {t.name: t for t in gguf.GGUFReader(GG).tensors}
    n = struct.unpack("<Q", rng(0, 8))[0]
    hdr = json.loads(rng(8, 8 + n))
    base = 8 + n
    new, rows = {}, {}
    fd = open(SRC / "dense.bin", "rb")
    for L in range(48):
        off, size = ents[L]
        fd.seek(off)
        old = fd.read(size)
        g = np.asarray(G[f"blk.{L}.ffn_gate_inp.weight"].data)
        if g.tobytes() != old:
            raise SystemExit(f"layer {L}: the pack's router bytes differ from the dense GGUF's")
        e = hdr[f"model.language_model.layers.{L}.mlp.gate.weight"]
        if e["dtype"] != "BF16" or e["shape"] != [512, 2560]:
            raise SystemExit(f"layer {L}: FP4-Local router is {e['dtype']} {e['shape']}")
        a, b = e["data_offsets"]
        raw = rng(base + a, base + b)
        x, y = bf16(raw), bf16(old)
        rows[L] = {"rel": float(np.linalg.norm(x - y) / np.linalg.norm(y)), "identical": raw == old,
                   "min_row_cos": float(min(
                       np.dot(xr, yr) / (np.linalg.norm(xr) * np.linalg.norm(yr))
                       for xr, yr in zip(x.reshape(512, 2560), y.reshape(512, 2560)))),
                   "sha256": hashlib.sha256(raw).hexdigest()}
        new[L] = raw
        print(f"layer {L:2d}: rel {rows[L]['rel']:.4f}  min row cos {rows[L]['min_row_cos']:.5f}", flush=True)
    DST.mkdir(parents=True)
    for name in ("experts.bin", "index.txt", "native_experts.txt"):
        os.link(SRC / name, DST / name)
    shutil.copytree(SRC / "tokenizer", DST / "tokenizer", copy_function=os.link)
    tmp = DST / "dense.bin.part"            # stream: copy, patch in place, then compare chunk by chunk
    shutil.copyfile(SRC / "dense.bin", tmp)
    with open(tmp, "r+b") as f:
        for L, raw in new.items():
            f.seek(ents[L][0])
            f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    spans = sorted((off, off + size, L) for L, (off, size) in ents.items())
    with open(tmp, "rb") as f:
        size_all = os.fstat(f.fileno()).st_size
        if size_all != os.fstat(fd.fileno()).st_size:
            raise SystemExit("the copy's size differs")
        regions, pos = [], 0                 # (start, end, layer or None): None = must equal the original
        for s0, s1, L in spans:
            regions += [(pos, s0, None), (s0, s1, L)]
            pos = s1
        regions.append((pos, size_all, None))
        for r0, r1, L in regions:
            for c0 in range(r0, r1, 64 << 20):
                c1 = min(c0 + (64 << 20), r1)
                f.seek(c0)
                got = f.read(c1 - c0)
                if L is None:
                    fd.seek(c0)
                    if got != fd.read(c1 - c0):
                        raise SystemExit(f"bytes {c0}-{c1} changed outside the routers")
                elif got != new[L][c0 - r0:c1 - r0]:
                    raise SystemExit(f"layer {L}: patched bytes do not read back")
        os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    fd.close()
    tmp.rename(DST / "dense.bin")
    os.chmod(DST / "dense.bin", 0o444)
    OUT.write_text(json.dumps({"source": URL, "layers": rows}, indent=1))
    rel = [r["rel"] for r in rows.values()]
    print(f"{DST}: 48 routers replaced, rel min {min(rel):.4f} median {sorted(rel)[24]:.4f} max {max(rel):.4f}; "
          "every other byte unchanged")


if __name__ == "__main__":
    main()
