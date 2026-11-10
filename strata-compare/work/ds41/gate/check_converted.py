#!/usr/bin/env python3
"""check_converted.py OUT REF [SRC] - 11-03 (Karl's gate, arm C): the header re-read of the converted Lucebox drafter
(convert_lucebox_dspark.py's OUT) before it is packed. Reads only the GGUF headers (streamed: the tensor data is never
read), standard library only. Checks, against unsloth's 1017 Q8_0 drafter (REF) and the engine's load rules
(results/ds41/gate-5080-alone-study.md section 2.7):
  - general.architecture = dflash; the keys pack_gguf.py reads: dflash.block_count, block_size, expert_count,
    expert_used_count, target_layers - each equal to REF's;
  - the same tensor names as REF, each with REF's shape (dims); the data of every tensor inside the file;
  - routed experts (ffn_gate/up/down_exps): MXFP4 or one low-bit K type for gate and up (Q2_K / Q3_K / Q4_K; down may
    differ), never MXFP4 and a low-bit type in one block;
  - dense matrices (attn_q_a / q_b / kv / output_a / output_b, the shared expert, fc): BF16, Q8_0, Q4_K, Q5_K or Q6_K
    (no Q2_K / Q3_K dense: the load would fail);
  - router, norms, hyper-connection and sink tensors, conf_proj: F32, F16, BF16 or Q8_0;
  - markov_w1 BF16 and markov_w2 F16 or BF16, both [256, vocab];
  - with SRC (Lucebox's file): every blk.* tensor keeps SRC's type and byte size (nothing requantized).
Prints one line per finding and a verdict; exit 0 = PASS, 1 = FAIL.
"""
import os
import struct
import sys

T = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K",
     13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S", 20: "IQ4_NL", 21: "IQ3_S",
     22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64", 29: "IQ1_M", 30: "BF16", 39: "MXFP4"}
BLOCK = {"F32": (1, 4), "F16": (1, 2), "BF16": (1, 2), "Q8_0": (32, 34), "Q2_K": (256, 84), "Q3_K": (256, 110),
         "Q4_K": (256, 144), "Q5_K": (256, 176), "Q6_K": (256, 210), "MXFP4": (32, 17)}
SZ = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
EXPERT = (".ffn_gate_exps.", ".ffn_up_exps.", ".ffn_down_exps.")
DENSE = (".attn_q_a.", ".attn_q_b.", ".attn_kv.", ".attn_output_a.", ".attn_output_b.", ".ffn_gate_shexp.",
         ".ffn_up_shexp.", ".ffn_down_shexp.")
FLOAT_OK = {"F32", "F16", "BF16", "Q8_0"}
DENSE_OK = {"BF16", "Q8_0", "Q4_K", "Q5_K", "Q6_K"}
LOWBIT = {"Q2_K", "Q3_K", "Q4_K"}


class R:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.size = os.path.getsize(path)

    def rd(self, fmt):
        n = struct.calcsize("<" + fmt)
        b = self.f.read(n)
        if len(b) != n:
            raise SystemExit("header ends early (truncated file?)")
        return struct.unpack("<" + fmt, b)[0]

    def rs(self):
        n = self.rd("Q")
        return self.f.read(n).decode("utf-8", "replace")

    def val(self, t):
        if t == 8:
            return self.rs()
        if t == 9:
            et, n = self.rd("I"), self.rd("Q")
            v = [self.val(et) for _ in range(n)]
            return v if n <= 16 else ("array", n, et)
        return self.rd(SZ[t])


def header(path):
    r = R(path)
    if r.f.read(4) != b"GGUF":
        raise SystemExit(f"{path}: not a GGUF file")
    ver, nt, nk = r.rd("I"), r.rd("Q"), r.rd("Q")
    kv = {}
    for _ in range(nk):
        k = r.rs()
        kv[k] = r.val(r.rd("I"))
    ts = {}
    for _ in range(nt):
        name = r.rs()
        dims = [r.rd("Q") for _ in range(r.rd("I"))]
        ty, off = r.rd("I"), r.rd("Q")
        ts[name] = (T.get(ty, str(ty)), dims, off)
    align = int(kv.get("general.alignment", 32))
    pos = r.f.tell()
    data_start = (pos + align - 1) // align * align
    r.f.close()
    return {"version": ver, "kv": kv, "t": ts, "data_start": data_start, "size": r.size}


def nbytes(ty, dims):
    if ty not in BLOCK:
        return None
    per, bpb = BLOCK[ty]
    n = 1
    for d in dims:
        n *= d
    return n // per * bpb


def main():
    out, ref = header(sys.argv[1]), header(sys.argv[2])
    src = header(sys.argv[3]) if len(sys.argv) > 3 else None
    bad, notes = [], []
    kv, rk = out["kv"], ref["kv"]
    if kv.get("general.architecture") != "dflash":
        bad.append(f"general.architecture = {kv.get('general.architecture')!r}, not 'dflash'")
    for k in ("dflash.block_count", "dflash.block_size", "dflash.expert_count", "dflash.expert_used_count",
              "dflash.target_layers"):
        if k not in kv:
            bad.append(f"key {k} missing")
        elif kv[k] != rk.get(k):
            bad.append(f"key {k} = {kv[k]} but REF has {rk.get(k)}")
    notes.append(f"keys: block_count {kv.get('dflash.block_count')}, block_size {kv.get('dflash.block_size')}, experts "
                 f"{kv.get('dflash.expert_count')} x {kv.get('dflash.expert_used_count')}, target layers "
                 f"{kv.get('dflash.target_layers')}; name {kv.get('general.name')!r}")
    on, rn = set(out["t"]), set(ref["t"])
    if on != rn:
        bad.append(f"tensor names differ from REF: missing {sorted(rn - on)[:8]}, extra {sorted(on - rn)[:8]}")
    types = {}
    for name, (ty, dims, off) in sorted(out["t"].items()):
        types[ty] = types.get(ty, 0) + 1
        if name in ref["t"] and ref["t"][name][1] != dims:
            bad.append(f"{name}: shape {dims}, REF {ref['t'][name][1]}")
        nb = nbytes(ty, dims)
        if nb is None:
            bad.append(f"{name}: type {ty} has no size rule here (not one the engine reads for the drafter)")
        elif out["data_start"] + off + nb > out["size"]:
            bad.append(f"{name}: data ends past the file ({out['data_start'] + off + nb} > {out['size']})")
        if any(x in name for x in EXPERT):
            if ty != "MXFP4" and ty not in LOWBIT:
                bad.append(f"{name}: expert type {ty} (MXFP4 / Q2_K / Q3_K / Q4_K only)")
        elif any(x in name for x in DENSE) or name == "fc.weight":
            if ty not in DENSE_OK:
                bad.append(f"{name}: dense type {ty} (BF16 / Q8_0 / Q4_K / Q5_K / Q6_K only; Q2_K or Q3_K dense fails at load)")
        elif name == "markov_w1.weight":
            if ty != "BF16":
                bad.append(f"{name}: {ty}, the engine wants a BF16 embed")
        elif name == "markov_w2.weight":
            if ty not in ("F16", "BF16"):
                bad.append(f"{name}: {ty}, the engine wants F16 or BF16")
        elif ty not in FLOAT_OK:
            bad.append(f"{name}: {ty} (router / norms / small tensors: F32 / F16 / BF16 / Q8_0 only)")
        if src is not None and name.startswith("blk."):
            s = src["t"].get(name)
            if s is None:
                bad.append(f"{name}: not in SRC")
            elif s[0] != ty or nbytes(s[0], s[1]) != nb:
                bad.append(f"{name}: {ty} {nb} B here, SRC {s[0]} {nbytes(s[0], s[1])} B (blk.* must be copied as is)")
    for il in range(int(kv.get("dflash.block_count", 0) or 0)):
        g = out["t"].get(f"blk.{il}.ffn_gate_exps.weight", ("?",))[0]
        u = out["t"].get(f"blk.{il}.ffn_up_exps.weight", ("?",))[0]
        dn = out["t"].get(f"blk.{il}.ffn_down_exps.weight", ("?",))[0]
        if g != u:
            bad.append(f"blk.{il}: gate {g} and up {u} differ (one type for gate and up)")
        if ("MXFP4" in (g, u, dn)) and ({g, u, dn} & LOWBIT):
            bad.append(f"blk.{il}: MXFP4 and a low-bit type in one block ({g}/{u}/{dn})")
        notes.append(f"blk.{il} experts gate/up/down {g}/{u}/{dn}")
    for nm in ("markov_w1.weight", "markov_w2.weight"):
        if nm in out["t"]:
            dims = out["t"][nm][1]
            if len(dims) != 2 or dims[0] != 256:
                bad.append(f"{nm}: dims {dims}, want [256, vocab]")
    exp_b = sum(nbytes(ty, d) or 0 for n, (ty, d, _) in out["t"].items() if any(x in n for x in EXPERT))
    all_b = sum(nbytes(ty, d) or 0 for ty, d, _ in out["t"].values())
    notes.append(f"{len(out['t'])} tensors, types {types}; experts {exp_b / 1e9:.2f} GB "
                 f"({exp_b / (3 * int(kv.get('dflash.block_count', 3) or 3) * int(kv.get('dflash.expert_count', 128) or 128)) / 1e6:.2f} MB a matrix), "
                 f"all tensors {all_b / 1e9:.2f} GB, file {out['size'] / 1e9:.2f} GB")
    for n in notes:
        print("  " + n)
    for b in bad:
        print("  BAD " + b)
    print("check_converted: " + ("PASS" if not bad else f"FAIL ({len(bad)} findings)"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
