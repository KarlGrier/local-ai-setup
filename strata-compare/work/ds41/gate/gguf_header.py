#!/usr/bin/env python3
"""gguf_header.py FILE - 11-03: print a GGUF file's metadata keys (scalars, short arrays) and its tensors' names, types
and shapes from the header bytes only (a partial download is enough). Standard library only."""
import struct, sys, collections
T = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K",
     13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S", 20: "IQ4_NL", 21: "IQ3_S",
     22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64", 29: "IQ1_M", 30: "BF16", 39: "MXFP4"}
b = open(sys.argv[1], "rb").read(); o = 0
def rd(fmt):
    global o
    v = struct.unpack_from("<" + fmt, b, o); o += struct.calcsize("<" + fmt); return v[0]
def rs():
    n = rd("Q"); global o; s = b[o:o + n].decode("utf-8", "replace"); o += n; return s
SZ = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
def val(t):
    if t == 8: return rs()
    if t == 9:
        et = rd("I"); n = rd("Q"); vals = [val(et) for _ in range(n)]
        return vals if n <= 8 else f"[{n} x type {et}]"
    return rd(SZ[t])
assert b[:4] == b"GGUF", "not a GGUF file"
o = 4; ver = rd("I"); nt = rd("Q"); nk = rd("Q")
print(f"GGUF v{ver}: {nt} tensors, {nk} metadata keys")
for _ in range(nk):
    k = rs(); t = rd("I"); v = val(t)
    if not (isinstance(v, str) and len(v) > 200): print(f"  {k} = {v}")
types = collections.Counter(); rows = []
for _ in range(nt):
    name = rs(); nd = rd("I"); dims = [rd("Q") for _ in range(nd)]; ty = rd("I"); off = rd("Q")
    types[T.get(ty, ty)] += 1; rows.append((name, T.get(ty, ty), dims))
print("tensor types:", dict(types))
for name, ty, dims in rows:
    if not any(x in name for x in (".ffn_gate_exps", ".ffn_up_exps", ".ffn_down_exps")) or name.startswith("blk.0."):
        print(f"  {name} {ty} {dims}")
