#!/usr/bin/env python3
"""convert_layer.py LAYER - r21 item 7: one layer's FP4-Local routed experts (staged by extract.py, standard ModelOpt
NVFP4) -> Strata's tools/nvfp4_convert.py (llama.cpp's converter with Strata's policy: the lossless NVFP4 repack into
ggml's block_nvfp4 plus one F32 `.scale` per expert) -> that layer's 512 blobs written into experts.bin.

    VENV/bin/python work/r21/fp4local/convert_layer.py LAYER

experts.bin is laid out exactly like the GPTQ NVFP4 pack's (tools/iq_pack.py): per layer 512 blobs of
gate | up | down (ggml NVFP4 slices) | {s_gate, s_up, s_down, 0} F32, at the GPTQ pack's offsets
(native_experts.txt), so the GPTQ pack's index.txt and dense.bin serve it unchanged.
Checks: the GGUF's tensors are NVFP4 [*, *, 512]; the blob size equals the GPTQ pack's for the layer; every `.scale`
equals the staged weight_scale_2 bit for bit; the ggml repack round-trips (the dequantized values of 4 experts per
role equal the staged ModelOpt tensors' values exactly).  Then the layer's staging and GGUF are deleted.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

WS = Path("/home/USER/ai-speed-testing/strata-compare")
FP = WS / "tmp/fp4local"
STAGE = FP / "staging"
META = FP / "meta"            # config.json + tokenizer files of the FP4-Local checkpoint
GPTQ = WS / "models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata/pack"
OUTP = WS / "models/fp4local/pack"
TOOLS = WS / "strata-cstar18/tools"
sys.path.insert(0, str(WS / "strata-cstar18/third_party/llama.cpp/gguf-py"))
import gguf  # noqa: E402

ROLES = ("gate", "up", "down")
E2M1 = np.array([0, .5, 1, 1.5, 2, 3, 4, 6, -0., -.5, -1, -1.5, -2, -3, -4, -6], np.float32)


def e4m3(b):
    b = b.astype(np.int32)
    s = np.where(b >> 7, -1.0, 1.0)
    e = (b >> 3) & 15
    m = b & 7
    return (s * np.where(e == 0, m / 8 * 2.0 ** -6, (1 + m / 8) * 2.0 ** (e - 7))).astype(np.float32)


def read_st(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        h = json.loads(f.read(n))
    return h, 8 + n


def gptq_layout():
    rows = {}
    for line in (GPTQ / "native_experts.txt").read_text().splitlines():
        if line.startswith("#"):
            continue
        l, gt, dt, off, blob = map(int, line.split()[:5])
        rows[l] = (gt, dt, off, blob)
    return rows


def main():
    layer = int(sys.argv[1])
    sdir = STAGE / f"L{layer:02d}"
    files = sorted(sdir.glob("s*.safetensors"))
    weight_map, staged = {}, {}
    for f in files:
        h, base = read_st(f)
        for k, v in h.items():
            weight_map[k] = "model-" + f.name     # the converter reads only part files named model*.safetensors
            staged[k] = (f, base, v)
    n_proj = sum(k.endswith(".weight") for k in weight_map)
    if n_proj != 512 * 3:
        raise SystemExit(f"layer {layer}: {n_proj} projections staged, need 1536")
    work = FP / "conv" / f"L{layer:02d}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for p in META.iterdir():
        if p.is_file():
            os.symlink(p, work / p.name)
    for f in files:
        os.symlink(f, work / ("model-" + f.name))
    # the converter writes the PLE hash constants into its metadata (fetch_consts.py; not part of the pack)
    consts = FP / "ple-consts.safetensors"
    os.symlink(consts, work / ("model-" + consts.name))
    for k in read_st(consts)[0]:
        weight_map[k] = "model-" + consts.name
    (work / "model.safetensors.index.json").write_text(json.dumps({"metadata": {}, "weight_map": weight_map}))
    out_gguf = FP / "conv" / f"L{layer:02d}.gguf"
    r = subprocess.run([sys.executable, str(TOOLS / "nvfp4_convert.py"), "--model", str(work), "--outfile", str(out_gguf)],
                       capture_output=True, text=True)
    if r.returncode or not out_gguf.exists():
        raise SystemExit(f"layer {layer}: nvfp4_convert failed rc={r.returncode}\n{r.stdout[-3000:]}\n{r.stderr[-6000:]}")

    g = gguf.GGUFReader(out_gguf)
    T = {t.name: t for t in g.tensors}
    names = [f"blk.{layer}.ffn_{r}_exps.weight" for r in ROLES]
    for n in names:
        t = T.get(n)
        if t is None or t.tensor_type.name != "NVFP4" or int(t.shape[-1]) != 512:
            raise SystemExit(f"layer {layer}: {n} missing or not NVFP4 x 512 ({t and (t.tensor_type.name, list(t.shape))})")
    parts = [np.asarray(T[n].data).reshape(512, -1) for n in names]
    scales = [np.asarray(T[f"blk.{layer}.ffn_{r}_exps.scale"].data, dtype=np.float32).reshape(512) for r in ROLES]
    # .scale must be the staged weight_scale_2 bit for bit
    for r, sc in zip(ROLES, scales):
        want = np.empty(512, np.float32)
        for e in range(512):
            f, base, v = staged[f"model.language_model.layers.{layer}.mlp.experts.{e}.{r}_proj.weight_scale_2"]
            with open(f, "rb") as fh:
                fh.seek(base + v["data_offsets"][0])
                want[e] = np.frombuffer(fh.read(4), np.float32)[0]
        if not np.array_equal(sc.view(np.uint32), want.view(np.uint32)):
            raise SystemExit(f"layer {layer}: {r} .scale differs from the staged weight_scale_2")
    tail = np.zeros((512, 4), np.float32)
    tail[:, 0], tail[:, 1], tail[:, 2] = scales
    chunk = np.concatenate(parts + [tail.view(np.uint8)], axis=1)
    gt, dt, off, blob = gptq_layout()[layer]
    if chunk.shape != (512, blob) or T[names[0]].tensor_type.value != gt or T[names[2]].tensor_type.value != dt:
        raise SystemExit(f"layer {layer}: blob {chunk.shape} types {T[names[0]].tensor_type.value}/{T[names[2]].tensor_type.value}"
                         f" vs the GPTQ pack's {blob} {gt}/{dt}")
    # the repack is lossless: ggml NVFP4 rows dequantized == the staged ModelOpt values (4 experts per role)
    for r, n in zip(ROLES, names):
        data = np.asarray(T[n].data)                                            # [512, rows, row bytes]
        for e in (0, 1, 255, 511):
            qe = gguf.quants.dequantize(data[e], T[n].tensor_type)              # one expert: [rows, cols]
            pre = f"model.language_model.layers.{layer}.mlp.experts.{e}.{r}_proj"
            f, base, vw = staged[pre + ".weight"]
            _, _, vs = staged[pre + ".weight_scale"]
            with open(f, "rb") as fh:
                fh.seek(base + vw["data_offsets"][0]); w = np.frombuffer(fh.read(vw["data_offsets"][1] - vw["data_offsets"][0]), np.uint8).reshape(vw["shape"])
                fh.seek(base + vs["data_offsets"][0]); s = np.frombuffer(fh.read(vs["data_offsets"][1] - vs["data_offsets"][0]), np.uint8).reshape(vs["shape"])
            codes = np.stack((w & 15, w >> 4), -1).reshape(w.shape[0], -1)
            ref = E2M1[codes] * np.repeat(e4m3(s), 16, axis=1)
            if not np.array_equal(np.asarray(qe, np.float32).reshape(ref.shape), ref):
                raise SystemExit(f"layer {layer}: {r} expert {e}: the ggml NVFP4 values differ from the ModelOpt ones")
    OUTP.mkdir(parents=True, exist_ok=True)
    eb = OUTP / "experts.bin"
    total = sum(b * 512 for *_, b in gptq_layout().values())
    with open(eb, "r+b" if eb.exists() else "w+b") as fh:
        if fh.seek(0, 2) < total:
            fh.truncate(total)
        fh.seek(off)
        fh.write(chunk.tobytes())
        fh.flush()
        os.fsync(fh.fileno())
    done = OUTP / "layers.done.json"
    d = json.loads(done.read_text()) if done.exists() else {}
    d[str(layer)] = {"offset": off, "blob": blob, "sha256_first_blob": __import__("hashlib").sha256(chunk[0].tobytes()).hexdigest()}
    done.write_text(json.dumps(d, indent=1))
    shutil.rmtree(work)
    out_gguf.unlink()
    out_gguf.with_suffix(".manifest.json").unlink(missing_ok=True)
    shutil.rmtree(sdir)
    print(f"layer {layer}: 512 blobs of {blob} B at {off}, checks passed ({len(d)} layers done)")


if __name__ == "__main__":
    main()
