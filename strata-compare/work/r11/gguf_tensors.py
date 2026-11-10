#!/usr/bin/env python3
"""gguf_tensors.py FILE [NAME...] — round 11: the tensor table of a GGUF (header only, read-only): name, type, shape;
and the metadata keys that hold the vocabulary / embedding sizes."""
import struct
import sys

T = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K",
     13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S", 20: "IQ4_NL", 21: "IQ3_S",
     22: "IQ2_S", 23: "IQ4_XS", 29: "IQ1_M", 30: "BF16"}


def rd(f, fmt):
    return struct.unpack("<" + fmt, f.read(struct.calcsize("<" + fmt)))


def rstr(f):
    (n,) = rd(f, "Q")
    return f.read(n).decode("utf-8", "replace")


def rval(f, t):
    sz = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
    if t in sz:
        return rd(f, sz[t])[0]
    if t == 8:
        return rstr(f)
    if t == 9:
        (et,) = rd(f, "I")
        (n,) = rd(f, "Q")
        return [rval(f, et) for _ in range(n)] if n < 64 else f"<array of {n}>" + ("" if (et != 8 and [f.seek(f.tell() + n * struct.calcsize('<' + sz[et]))]) else str([rval(f, et) for _ in range(n)][:0]))
    raise ValueError(t)


with open(sys.argv[1], "rb") as f:
    assert f.read(4) == b"GGUF"
    (ver,) = rd(f, "I")
    (nt,) = rd(f, "Q")
    (nk,) = rd(f, "Q")
    meta = {}
    for _ in range(nk):
        k = rstr(f)
        (t,) = rd(f, "I")
        meta[k] = rval(f, t)
    want = set(sys.argv[2:])
    for _ in range(nt):
        name = rstr(f)
        (nd,) = rd(f, "I")
        shape = rd(f, "Q" * nd)
        (ty,) = rd(f, "I")
        (off,) = rd(f, "Q")
        if not want or name in want:
            print(f"{name}: {T.get(ty, ty)} {list(shape)}")
    for k, v in meta.items():
        if any(s in k for s in ("vocab", "embedding_length", "architecture", "tokenizer.ggml.model")) and not str(v).startswith("<array"):
            print(f"meta {k} = {v}")
        elif k == "tokenizer.ggml.tokens":
            print(f"meta {k} = {v}")
