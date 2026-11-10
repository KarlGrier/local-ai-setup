#!/usr/bin/env python3
"""extract.py SHARD.safetensors STAGING_DIR - r21 item 7: one FP4-Local shard -> standard ModelOpt NVFP4 expert tensors.

For every routed-expert projection in the shard (model.language_model.layers.L.mlp.experts.E.{gate,up,down}_proj):
  weight (U8, kept), weight_scale.nvfp4_csf_{fixed,exceptions} -> weight_scale (F8_E4M3, decoded by csf.py), and
  weight_scale_2 (F32, kept).  input_scale lives in shard 15 for every expert and is not read: Strata's pack has no
  place for it and the converter defaults it to 1.0.
Every scale matrix gets the round-trip check: re-encoded with the checkpoint's own row bases (and its nibbles at the
exception positions) it must give back the stored streams byte for byte, and the decoded bytes must be valid E4M3
(no NaN, no sign bit).  A failure stops the extraction.
Output: STAGING_DIR/L{layer:02d}/s{shard:02d}.safetensors (one file per layer and shard) and
STAGING_DIR/s{shard:02d}.json (counts, the round-trip result, the sha256 of the shard as read).
Memory stays bounded: the shard is read through a memmap, one layer's tensors at a time.
"""
import hashlib
import json
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csf import checkpoint_round_trip, decode  # noqa: E402

ST_DT = {"U8": np.uint8, "U32": np.uint32, "F32": np.float32, "F8_E4M3": np.uint8, "BF16": np.uint16}
PAT = re.compile(r"^(model\.language_model\.layers\.(\d+)\.mlp\.experts\.(\d+)\.(gate|up|down)_proj)\.(.+)$")


def read_header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        h = json.loads(f.read(n))
    h.pop("__metadata__", None)
    return h, 8 + n


def write_safetensors(path: Path, tensors: dict):
    """tensors: name -> (dtype_str, shape, bytes)."""
    header, off, blobs = {}, 0, []
    for name in sorted(tensors):
        dt, shape, b = tensors[name]
        header[name] = {"dtype": dt, "shape": list(shape), "data_offsets": [off, off + len(b)]}
        off += len(b)
        blobs.append(b)
    hb = json.dumps(header, separators=(",", ":")).encode()
    hb += b" " * ((8 - len(hb) % 8) % 8)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        f.write(struct.pack("<Q", len(hb)))
        f.write(hb)
        for b in blobs:
            f.write(b)
    tmp.rename(path)


def main():
    shard, out = Path(sys.argv[1]), Path(sys.argv[2])
    sid = int(re.search(r"model-(\d+)-of-", shard.name).group(1))
    h, base = read_header(shard)
    mm = np.memmap(shard, dtype=np.uint8, mode="r")

    def arr(name):
        e = h[name]
        a, b = e["data_offsets"]
        return np.asarray(mm[base + a:base + b]).view(ST_DT[e["dtype"]]).reshape(e["shape"])

    groups = defaultdict(dict)
    for k in h:
        m = PAT.match(k)
        if m:
            groups[(int(m.group(2)), int(m.group(3)), m.group(4), m.group(1))][m.group(5)] = k
    by_layer = defaultdict(list)
    for (layer, e, role, prefix), parts in groups.items():
        by_layer[layer].append((e, role, prefix, parts))
    stats = {"shard": shard.name, "projections": 0, "exceptions": 0, "round_trip_failures": 0, "e4m3_bad": 0,
             "incomplete": 0, "layers": {}}
    for layer in sorted(by_layer):
        tensors = {}
        for e, role, prefix, parts in sorted(by_layer[layer]):
            need = ("weight", "weight_scale.nvfp4_csf_fixed", "weight_scale.nvfp4_csf_exceptions", "weight_scale_2")
            if any(p not in parts for p in need):
                stats["incomplete"] += 1          # only input_scale here (shard 15): nothing to extract
                continue
            fixed, exc = arr(parts["weight_scale.nvfp4_csf_fixed"]), arr(parts["weight_scale.nvfp4_csf_exceptions"])
            r = checkpoint_round_trip(fixed, exc)
            if not r["streams_identical"] or not r["scales_identical_after_own_encode"]:
                stats["round_trip_failures"] += 1
            if r["e4m3_nan"] or r["sign_bit_set"]:
                stats["e4m3_bad"] += 1
            sc = decode(fixed, exc)
            w = arr(parts["weight"])
            if w.shape[0] != sc.shape[0] or w.shape[1] * 2 != sc.shape[1] * 16:
                raise SystemExit(f"{prefix}: weight {w.shape} does not match scales {sc.shape}")
            s2 = arr(parts["weight_scale_2"])
            tensors[prefix + ".weight"] = ("U8", w.shape, w.tobytes())
            tensors[prefix + ".weight_scale"] = ("F8_E4M3", sc.shape, sc.tobytes())
            tensors[prefix + ".weight_scale_2"] = ("F32", s2.shape, s2.astype(np.float32).tobytes())
            stats["projections"] += 1
            stats["exceptions"] += r["exceptions"]
        if tensors:
            d = out / f"L{layer:02d}"
            d.mkdir(parents=True, exist_ok=True)
            write_safetensors(d / f"s{sid:02d}.safetensors", tensors)
            stats["layers"][layer] = len(tensors) // 3
    if stats["round_trip_failures"] or stats["e4m3_bad"]:
        (out / f"s{sid:02d}.json").write_text(json.dumps(stats, indent=1))
        raise SystemExit(f"{shard.name}: {stats['round_trip_failures']} round-trip failures, {stats['e4m3_bad']} bad E4M3")
    hsh = hashlib.sha256()
    with open(shard, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            hsh.update(chunk)
    stats["sha256"] = hsh.hexdigest()
    (out / f"s{sid:02d}.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: v for k, v in stats.items() if k != "layers"}), "layers", sorted(stats["layers"]))


if __name__ == "__main__":
    main()
