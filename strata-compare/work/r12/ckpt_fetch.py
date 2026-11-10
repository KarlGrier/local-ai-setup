#!/usr/bin/env python3
"""ckpt_fetch.py ple|embd OUT.gguf — round 11 Phase E: the two tensors of Qwen/Qwen3.8-Flash-Next (pinned revision, the
one tools/mtp_fetch.py uses) that the higher-precision options need, fetched by HTTP range requests (only their bytes)
and written straight into the one-tensor GGUFs the engine reads — byte for byte what upstream's own packers write from
a downloaded checkpoint:
  ple  : the n-gram table (from Qwen/Qwen3.8-Flash-Next-FP8: the BF16 checkpoint stores it as BF16), 128 shards of FP8 E4M3 [2500012, 160] + its BF16 weight_scale (51.2 GB) ->
         tools/ple_fp8_pack.py's GGUF (per_layer_token_embd.weight, I8 bytes, strata.ple.format f8_e4m3) for --ple-gguf
  embd : the text token embedding, BF16 [248320, 2560] (1.27 GB) -> tools/embd_bf16_pack.py's GGUF for --embd-gguf
Resumable: the .part file's size says how far it got.  Disk space checked first (keeps >= 100 GB free)."""
import json
import os
import shutil
import struct
import sys
import time
import urllib.request
from pathlib import Path

REV = "de4b8e4d43b917e7706784d8bb445c9af86a3540"          # Qwen/Qwen3.8-Flash-Next (BF16; the embedding)
BASE = f"https://huggingface.co/Qwen/Qwen3.8-Flash-Next/resolve/{REV}/"
REV8 = "236dfdf285828023ca3bcd3f37366c58a3469b13"         # Qwen/Qwen3.8-Flash-Next-FP8 (the FP8 n-gram table; its BF16
BASE8 = f"https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8/resolve/{REV8}/"   # checkpoint stores the table as BF16)
WS = Path("/home/USER/ai-speed-testing/strata-compare")
INDEX = WS / "tmp/r12/ckpt/index.json"
INDEX8 = WS / "tmp/r12/ckpt/index-fp8.json"
CHUNK = 16 << 20
ALIGN = 32


def get(url, a, b, tries=20):
    """bytes [a, b) of url, retried with backoff"""
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b - 1}", "User-Agent": "strata-compare/r11"})
            with urllib.request.urlopen(req, timeout=120) as r:
                if r.status != 206:
                    raise IOError(f"HTTP {r.status} (no range support?)")
                data = r.read()
            if len(data) != b - a:
                raise IOError(f"short read {len(data)} of {b - a}")
            return data
        except Exception as e:  # noqa: BLE001
            wait = min(300, 5 * 2 ** k)
            print(f"  retry {k + 1}: {e!r}; waiting {wait} s", flush=True)
            time.sleep(wait)
    sys.exit(f"giving up on {url} [{a}, {b})")


_hdr = {}


def header(fname, base_url=None):
    if fname not in _hdr:
        url = (base_url or BASE) + fname
        (n,) = struct.unpack("<Q", get(url, 0, 8))
        _hdr[fname] = (json.loads(get(url, 8, 8 + n)), 8 + n)
    return _hdr[fname]


def gs(s):
    b = s.encode("utf-8")
    return struct.pack("<Q", len(b)) + b


def kv_s(k, v):
    return gs(k) + struct.pack("<I", 8) + gs(v)


def kv_f(k, v):
    return gs(k) + struct.pack("<I", 6) + struct.pack("<f", v)


def stream(out, head, parts):
    """write head, then the byte ranges `parts` [(url, a, n)], resuming from an existing .part file"""
    tmp = out.with_suffix(out.suffix + ".part")
    total = len(head) + sum(n for _, _, n in parts)
    free = shutil.disk_usage(out.parent).free
    have = tmp.stat().st_size if tmp.exists() else 0
    if free - (total - have) < 100e9:
        sys.exit(f"not enough disk: {free / 1e9:.0f} GB free, need {(total - have) / 1e9:.0f} GB and 100 GB to spare")
    if have < len(head):
        with open(tmp, "wb") as w:
            w.write(head)
        have = len(head)
    t0, got0 = time.time(), have
    with open(tmp, "r+b") as w:
        w.truncate(have)
        w.seek(have)
        pos = len(head)
        for i, (url, a, n) in enumerate(parts):
            if pos + n <= have:
                pos += n
                continue
            skip = max(0, have - pos)
            off = skip
            while off < n:
                m = min(CHUNK, n - off)
                w.write(get(url, a + off, a + off + m))
                off += m
                done = pos + off
                if (done // CHUNK) % 32 == 0 or off == n:
                    rate = (done - got0) / max(1e-9, time.time() - t0) / 1e6
                    print(f"  part {i + 1}/{len(parts)}: {done / 1e9:.2f} / {total / 1e9:.2f} GB, {rate:.1f} MB/s", flush=True)
            pos += n
            w.flush()
    if tmp.stat().st_size != total:
        sys.exit(f"size check failed: {tmp.stat().st_size} != {total}")
    tmp.replace(out)
    print(f"wrote {out} ({total} bytes, header {len(head)} B)", flush=True)


def main():
    what, out = sys.argv[1], Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    wmap = json.loads(INDEX.read_text())["weight_map"]
    if what == "ple":
        global BASE
        BASE = BASE8
        wmap = json.loads(INDEX8.read_text())["weight_map"]
        shards, scale_name = {}, None
        for name in wmap:
            if ".ngram_embedding.shard_" in name and name.endswith(".weight"):
                shards[int(name.rsplit(".shard_", 1)[1].split(".")[0])] = name
            elif name.endswith(".ngram_embedding.weight_scale"):
                scale_name = name
        assert sorted(shards) == list(range(len(shards))) and scale_name, "shards / scale"
        h, base = header(wmap[scale_name])
        t = h[scale_name]
        assert t["dtype"] == "BF16" and t["shape"] in ([1], []), t
        (bits,) = struct.unpack("<H", get(BASE + wmap[scale_name], base + t["data_offsets"][0], base + t["data_offsets"][0] + 2))
        scale = struct.unpack("<f", struct.pack("<I", bits << 16))[0]
        parts, rows, dim = [], 0, None
        for k in range(len(shards)):
            name = shards[k]
            h, base = header(wmap[name])
            t = h[name]
            assert t["dtype"] == "F8_E4M3" and len(t["shape"]) == 2, (name, t)
            dim = dim or t["shape"][1]
            assert t["shape"][1] == dim and t["data_offsets"][1] - t["data_offsets"][0] == t["shape"][0] * dim
            parts.append((BASE + wmap[name], base + t["data_offsets"][0], t["shape"][0] * dim))
            rows += t["shape"][0]
        print(f"{len(parts)} shards in {len(set(wmap[shards[k]] for k in shards))} files, {rows} rows x {dim}, scale {scale:.9g}, "
              f"{rows * dim / 1e9:.2f} GB", flush=True)
        kvs = [kv_s("general.architecture", "strata-ple"), kv_s("general.name", "PLE n-gram table, FP8 E4M3 as shipped"),
               kv_s("strata.ple.format", "f8_e4m3"), kv_f("strata.ple.scale", scale),
               kv_s("strata.ple.source", f"Qwen3.8-Flash-Next-FP8@{REV8[:12]}")]
        head = b"GGUF" + struct.pack("<IQQ", 3, 1, len(kvs)) + b"".join(kvs)
        head += gs("per_layer_token_embd.weight") + struct.pack("<I", 2) + struct.pack("<QQ", dim, rows)
        head += struct.pack("<I", 24) + struct.pack("<Q", 0)
        head += b"\0" * ((-len(head)) % ALIGN)
        stream(out, head, parts)
    elif what == "embd":
        names = [n for n in wmap if n.endswith("embed_tokens.weight") and "visual" not in n and "mtp" not in n]
        assert len(names) == 1, names
        name = names[0]
        h, base = header(wmap[name])
        t = h[name]
        assert t["dtype"] == "BF16" and len(t["shape"]) == 2, t
        vocab, dim = t["shape"]
        n = vocab * dim * 2
        assert t["data_offsets"][1] - t["data_offsets"][0] == n
        print(f"{name}: {vocab} x {dim} BF16, {n / 1e9:.2f} GB in {wmap[name]}", flush=True)
        kvs = [kv_s("general.architecture", "strata-embd"), kv_s("general.name", "token embedding, BF16 as shipped"),
               kv_s("strata.embd.source", f"Qwen3.8-Flash-Next@{REV[:12]}")]
        head = b"GGUF" + struct.pack("<IQQ", 3, 1, len(kvs)) + b"".join(kvs)
        head += gs("token_embd.weight") + struct.pack("<I", 2) + struct.pack("<QQ", dim, vocab)
        head += struct.pack("<I", 30) + struct.pack("<Q", 0)
        head += b"\0" * ((-len(head)) % ALIGN)
        stream(out, head, [(BASE + wmap[name], base + t["data_offsets"][0], n)])
    else:
        sys.exit("ple | embd")


if __name__ == "__main__":
    main()
