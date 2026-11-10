#!/usr/bin/env python3
"""mtp_from_gguf.py - our MTP drafter (Strata's rt dir) from a publisher's llama.cpp-format MTP GGUF.

Karl 11-04 (Qwen4 day-one kit, the drafter fallback). Our drafter `strata-v0115/mtp/rt` was made from Qwen's BF16
checkpoint (Qwen/Qwen3.8-Flash-Next@de4b8e4d) by the tree's tools/mtp_fetch.py -> mtp_pack.py (--experts q2_0) ->
mtp_rt.py. Unsloth ships the same block as separate GGUFs (MTP/mtp-<model>-{BF16,Q8_0,Q4_K_M}.gguf + "shared"
variants: `<arch>.nextn_shared_target_tensors = true`, no token_embd / output - those come from the main model, as in
our rt). This tool maps such a file back to the checkpoint's 31 `mtp.*` tensors and writes them exactly as
mtp_pack.py + mtp_rt.py do:

  experts.bin  per expert: Q2_0 (mtp_pack's per-block MSE scale search) of gate_up [2F, H] and down [H, F], in
               mtp_rt's blob layout (gate/up rows interleaved, code plane then fp16 scale plane)
  dense.bin    in sorted checkpoint-name order, each tensor 256-byte aligned: the ten large projections Q8_0
  dense.txt    (mtp_rt's ggml-reference rounding), the hyper-connection / router / shared-gate weights BF16, the 1-D
               norms F32 with the Gemma "+1" (rt value = f32(bf16 w) + 1); one line "name kind rows cols off bytes"
  draft_vocab.bin  copied (a token subset of the main head; not part of the MTP weights)

GGUF -> checkpoint (L = the nextn layer, block_count - nextn_predict_layers):
  blk.L.nextn.eh_proj [2H, H]        -> fc_embedding = columns 0..H-1, fc_hidden = H..2H-1 (--eh-order; auto = by the
                                        pinned checkpoint's sha256 when a manifest is given, else embedding first,
                                        llama.cpp's nextn convention "eh_proj over [enorm(e) | hnorm(h)]")
  blk.L.nextn.enorm / hnorm          -> pre_fc_norm_embedding / pre_fc_norm_hidden
  blk.L.nextn.hc_head_{norm,down,up} -> hyper_connection_mixer.{hc_norm, input_mix_weight_down, input_mix_weight_up}
  blk.L.hc_{attn,ffn}_{norm,down,up,inject} -> layers.0.{attn,mlp}_hyper_connection.{hc_norm, input_mix_weight_down,
                                        input_mix_weight_up, block_inject_weight}
  blk.L.attn_{q,k,v,output}, attn_{q,k}_norm -> layers.0.self_attn.{q,k,v,o}_proj, {q,k}_norm
  blk.L.indexer.{q,k}_proj           -> layers.0.self_attn.indexer.index_qk_proj = rows [q; k] (--qk-order; llama.cpp's
                                        qwen4exp converter splits the main model's this way: q = the first n_q rows)
  blk.L.indexer.{q,k}_norm           -> layers.0.self_attn.indexer.{q,k}_layernorm
  blk.L.ffn_{gate,up}_exps           -> layers.0.mlp.experts.gate_up_proj = [gate; up] on the row axis (llama.cpp's split)
  blk.L.ffn_down_exps                -> layers.0.mlp.experts.down_proj
  blk.L.ffn_gate_inp (F32)           -> layers.0.mlp.gate.weight (BF16 if the values are; exactness is checked)
  blk.L.ffn_gate_inp_shexp [H] (F32) -> layers.0.mlp.shared_expert_gate.weight [1, H]
  blk.L.ffn_{gate,up,down}_shexp     -> layers.0.mlp.shared_expert.{gate,up,down}_proj
  token_embd / output (non-shared files only) -> not used (our drafter takes the main model's embedding and head)
Norms: llama.cpp writes f32(w) + 1 (checked on the ISTA main file: v - 1 is BF16-exact); --norms auto decides per
tensor (v - 1 BF16-exact and v not: "+1 stored"; v BF16-exact and v - 1 not: raw) and falls back to the majority.

Exactness: a BF16 source (and F32 holding BF16 values) reproduces our rt bit for bit when its values are the
checkpoint's; a Q8_0 source reproduces the ten Q8_0 projections (re-quantizing Q8_0 values is the identity) but
rounds the BF16 tensors and gives other Q2_0 experts; Q4_K_M is lossy everywhere. Every tensor is reported.

  python -I -B mtp_from_gguf.py inspect GGUF [--manifest M]
        header only (head-only files with NAME.size work): the mapping, dims, types, the exactness forecast
  python -I -B mtp_from_gguf.py verify GGUF [--ref-rt RT] [--manifest M] [--report J]
        nothing written: the rt bytes in memory against RT's files, the checkpoint tensors against M's sha256s
  python -I -B mtp_from_gguf.py convert GGUF --out NEWDIR [--ref-rt RT] [--manifest M] [--draft-vocab F]
        writes NEWDIR (refuses an existing non-empty dir and anything under strata-v0115/); conversion.json beside
  python -I -B mtp_from_gguf.py selftest --out DIR [--ckpt-dir D] [--experts N] [--max-mbps X]
        offline: tool-function equality, a small synthetic GGUF (gguf-py's writer) in Unsloth's layout and variants,
        our checkpoint's BF16 tensors laid out as Unsloth's file -> must reproduce strata-v0115/mtp/rt byte for byte

GGUF bytes are data: parsed with struct / numpy only (run under python -I), never executed. CPU-light: nice -n 19.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import struct  # noqa: E402
import time  # noqa: E402
from collections import Counter, OrderedDict  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
GGUF_PY = WS / "ext/llama.cpp-3cf03257/gguf-py"
sys.path.insert(0, str(GGUF_PY))
from gguf.constants import GGML_QUANT_SIZES, GGMLQuantizationType as QT  # noqa: E402

REF_RT = WS / "strata-v0115/mtp/rt"                       # our drafter (read only)
MANIFEST = WS / "strata-v0115/mtp/mtp-manifest.json"      # the pinned checkpoint's 31 tensors + sha256 (read only)
CKPT_DIR = WS / "strata/mtp"                              # mtp_fetch.py's raw BF16 tensors (tensors/*.bin), read only
TOOLS = WS / "strata-v0115/tools"                         # mtp_pack.py / mtp_rt.py (read only: the reference functions)
VERSION = "mtp_from_gguf.py 2026-11-04"
PROTECTED = (WS / "strata-v0115", WS / "strata", WS / "configs", WS / "tools")

F32, F16, BF16, Q8_0, Q2_0 = int(QT.F32), int(QT.F16), int(QT.BF16), int(QT.Q8_0), int(QT.Q2_0)
TYPES = {int(q): (q.name, *GGML_QUANT_SIZES[q]) for q in QT if q in GGML_QUANT_SIZES}

# mtp_rt.py's Q8 set (short names): the projections the engine's MMVQ runs; every other 2-D tensor stays BF16
Q8 = {"fc_embedding.weight", "fc_hidden.weight", "self_attn.q_proj.weight", "self_attn.k_proj.weight",
      "self_attn.v_proj.weight", "self_attn.o_proj.weight", "self_attn.indexer.index_qk_proj.weight",
      "mlp.shared_expert.gate_proj.weight", "mlp.shared_expert.up_proj.weight", "mlp.shared_expert.down_proj.weight"}
GATE_UP, DOWN = "mtp.layers.0.mlp.experts.gate_up_proj", "mtp.layers.0.mlp.experts.down_proj"


# =====================================================================================================================
# 1. The reference arithmetic: copied verbatim from strata-v0115/tools (mtp_pack.py q2_0, mtp_rt.py q8_0 / blob_of with
#    its constants made parameters). `selftest` checks them against the tools' own functions.
# =====================================================================================================================
def q2_0(w: np.ndarray) -> np.ndarray:
    """mtp_pack.py q2_0: [..., n] float32 -> bytes of Q2_0 blocks (fp16 d, 16 bytes of 2-bit codes, code = q + 1)."""
    x = w.reshape(-1, 64).astype(np.float32)
    amax = np.abs(x).max(axis=1, keepdims=True)
    best_err = np.full((x.shape[0], 1), np.inf, dtype=np.float32)
    best_d = np.zeros_like(amax)
    for f in np.linspace(0.5, 1.0, 17, dtype=np.float32):
        d = amax * f
        inv = np.where(d > 0, 1.0 / np.where(d > 0, d, 1.0), 0.0)
        q = np.clip(np.rint(x * inv), -1, 2)
        err = ((q * d - x) ** 2).sum(axis=1, keepdims=True)
        better = err < best_err
        best_err = np.where(better, err, best_err)
        best_d = np.where(better, d, best_d)
    d16 = best_d.astype(np.float16)
    d = d16.astype(np.float32)
    inv = np.where(d > 0, 1.0 / np.where(d > 0, d, 1.0), 0.0)
    codes = (np.clip(np.rint(x * inv), -1, 2) + 1).astype(np.uint8)
    c = codes.reshape(-1, 16, 4)
    packed = (c[:, :, 0] | (c[:, :, 1] << 2) | (c[:, :, 2] << 4) | (c[:, :, 3] << 6)).astype(np.uint8)
    out = np.empty((x.shape[0], 18), dtype=np.uint8)
    out[:, :2] = d16.view(np.uint8).reshape(-1, 2)
    out[:, 2:] = packed
    return out.reshape(-1)


def q8_0(x: np.ndarray) -> bytes:
    """mtp_rt.py q8_0: ggml quantize_row_q8_0_ref over rows (32-value blocks, fp16 d = amax / 127)."""
    b = x.reshape(-1, 32).astype(np.float32)
    amax = np.abs(b).max(axis=1)
    d = amax / 127.0
    inv = np.where(d > 0, 1.0 / np.where(d > 0, d, 1.0), 0.0).astype(np.float32)
    v = b * inv[:, None]
    q = (np.sign(v) * np.floor(np.abs(v) + 0.5)).astype(np.int8)
    out = np.empty((b.shape[0], 34), dtype=np.uint8)
    out[:, :2] = d.astype(np.float16).view(np.uint8).reshape(-1, 2)
    out[:, 2:] = q.view(np.uint8)
    return out.tobytes()


def blob_of(gu: np.ndarray, dn: np.ndarray, H: int, FF: int) -> bytes:
    """mtp_rt.py blob_of: gu (2FF, H/64*18) Q2_0 rows (gate 0..FF-1, up FF..2FF-1); dn (H, FF/64*18)."""
    gub = gu.reshape(2 * FF, H // 64, 18)
    inter = np.empty_like(gub)
    inter[0::2] = gub[:FF]
    inter[1::2] = gub[FF:]
    dnb = dn.reshape(H, FF // 64, 18)
    parts = [inter[:, :, 2:].tobytes(), dnb[:, :, 2:].tobytes(), inter[:, :, :2].tobytes(), dnb[:, :, :2].tobytes()]
    out = b"".join(parts)
    assert len(out) == 3 * (H * FF * 18 // 64), len(out)
    return out


def bf16_to_f32(u16: np.ndarray) -> np.ndarray:
    return (np.asarray(u16).astype(np.uint32) << 16).view(np.float32)


def f32_to_bf16(f: np.ndarray):
    """(u16, exact): the BF16 bytes of f32 values; exact when every low half is zero, else round-to-nearest-even."""
    u = np.ascontiguousarray(f, dtype=np.float32).view(np.uint32)
    if not np.any(u & 0xFFFF):
        return (u >> 16).astype(np.uint16), True
    r = ((u.astype(np.uint64) + 0x7FFF + ((u >> 16) & 1)) >> 16).astype(np.uint16)
    return r, False


def short_of(name):
    s = name[len("mtp."):] if name.startswith("mtp.") else name
    return s[len("layers.0."):] if s.startswith("layers.0.") else s


# =====================================================================================================================
# 2. GGUF (struct parsing only; head-only files with NAME.size beside them are read for their header)
# =====================================================================================================================
class Truncated(ValueError):
    pass


class TInfo:
    __slots__ = ("name", "ne", "type", "offset", "nbytes")

    def __init__(self, name, ne, typ, offset, nbytes):
        self.name, self.ne, self.type, self.offset, self.nbytes = name, tuple(ne), typ, offset, nbytes

    @property
    def shape(self):                       # numpy order = ggml ne reversed
        return tuple(reversed(self.ne))

    @property
    def tname(self):
        return TYPES.get(self.type, (f"type{self.type}",))[0]


SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


class GGUF:
    """A GGUF file's header + tensor table; raw(name) memory-maps one tensor's bytes (read-only)."""

    def __init__(self, path):
        self.path = Path(path)
        side = Path(str(path) + ".size")
        self.head_only = side.exists()
        self.real_size = self.path.stat().st_size
        self.size = int(side.read_text().split()[0]) if self.head_only else self.real_size
        self.kv, self.tensors = OrderedDict(), OrderedDict()
        with open(self.path, "rb", buffering=1 << 20) as f:
            self._f = f
            if f.read(4) != b"GGUF":
                raise ValueError(f"{self.path.name}: not a GGUF file")
            self.version = self._u32()
            if self.version not in (2, 3):
                raise ValueError(f"GGUF version {self.version}")
            nt, nkv = self._u64(), self._u64()
            if nt > 1 << 20 or nkv > 1 << 20:
                raise ValueError(f"{nt} tensors / {nkv} keys: not a sane header")
            for _ in range(nkv):
                k = self._s()
                vt = self._u32()
                self.kv[k] = self._val(vt)
            raw = []
            for _ in range(nt):
                name = self._s()
                nd = self._u32()
                if nd > 8:
                    raise ValueError(f"{name}: {nd} dims")
                ne = [self._u64() for _ in range(nd)]
                typ = self._u32()
                off = self._u64()
                raw.append((name, ne, typ, off))
            self.header_end = f.tell()
            del self._f
        align = self.kv.get("general.alignment", 32)
        if not isinstance(align, int) or align <= 0 or align & (align - 1) or align > 1 << 16:
            raise ValueError(f"general.alignment {align!r}")
        self.alignment = align
        self.data_start = (self.header_end + align - 1) // align * align
        for name, ne, typ, off in raw:
            if typ not in TYPES:
                raise ValueError(f"{name}: unknown ggml type {typ}")
            _nm, bs, ts = TYPES[typ]
            n = int(np.prod(ne, dtype=np.int64)) if ne else 1
            if not ne or ne[0] % bs:
                raise ValueError(f"{name}: rows of {ne[0] if ne else 0} are not whole {_nm} blocks")
            nbytes = n // bs * ts
            if self.data_start + off + nbytes > self.size:
                raise ValueError(f"{name}: data ends at {self.data_start + off + nbytes:,}, the file is {self.size:,}")
            if name in self.tensors:
                raise ValueError(f"{name} twice")
            self.tensors[name] = TInfo(name, ne, typ, off, nbytes)

    # -- the reader
    def _take(self, n):
        b = self._f.read(n)
        if len(b) != n:
            raise Truncated(f"truncated header at {self._f.tell()}")
        return b

    def _u32(self):
        return struct.unpack("<I", self._take(4))[0]

    def _u64(self):
        return struct.unpack("<Q", self._take(8))[0]

    def _s(self):
        n = self._u64()
        if n > 1 << 28:
            raise ValueError(f"a {n}-byte string")
        return self._take(n).decode("utf-8", errors="replace")

    def _val(self, vt):
        if vt == 8:
            return self._s()
        if vt == 9:
            et, n = self._u32(), self._u64()
            if n > 1 << 26:
                raise ValueError(f"an array of {n}")
            if et == 8:                         # string arrays (the tokenizer): only the count is kept
                for _ in range(n):
                    k = self._u64()
                    if k > 1 << 28:
                        raise ValueError("string length")
                    self._f.seek(k, 1)
                return ("<strings>", n)
            if et == 9:
                return [self._val(9) for _ in range(n)]
            if et not in SCALAR:
                raise ValueError(f"array of value type {et}")
            sz = struct.calcsize(SCALAR[et])
            if n > 4096:
                self._f.seek(sz * n, 1)
                return ("<array>", n)
            return list(struct.unpack("<" + SCALAR[et][1] * n, self._take(sz * n)))
        if vt not in SCALAR:
            raise ValueError(f"value type {vt}")
        return struct.unpack(SCALAR[vt], self._take(struct.calcsize(SCALAR[vt])))[0]

    def raw(self, name) -> np.ndarray:
        if self.head_only:
            raise ValueError(f"{self.path.name} is a head-only file: no tensor data")
        t = self.tensors[name]
        return np.memmap(self.path, dtype=np.uint8, mode="r", offset=self.data_start + t.offset, shape=(t.nbytes,))

    def vocab(self):
        v = self.kv.get("tokenizer.ggml.tokens")
        return v[1] if isinstance(v, tuple) else (len(v) if isinstance(v, list) else None)


class DictSrc:
    """A source built in memory (selftest): name -> (TInfo, bytes ndarray); the same interface as GGUF."""

    def __init__(self, kv, items, label="in-memory"):
        self.kv, self.tensors, self._raw = OrderedDict(kv), OrderedDict(), {}
        self.path, self.head_only, self.size, self.data_start = Path(label), False, 0, 0
        for name, (typ, ne, data) in items.items():
            _nm, bs, ts = TYPES[typ]
            n = int(np.prod(ne, dtype=np.int64))
            self.tensors[name] = TInfo(name, ne, typ, 0, n // bs * ts)
            self._raw[name] = data
        self.version = 3

    def raw(self, name):
        return self._raw[name]

    def vocab(self):
        v = self.kv.get("tokenizer.ggml.tokens")
        return v[1] if isinstance(v, tuple) else None


# ---- decoding one tensor (or a slice of whole rows) to numpy-ordered values
def _row_bytes(t: TInfo):
    _nm, bs, ts = TYPES[t.type]
    return t.ne[0] // bs * ts


def decode_f32(t: TInfo, raw: np.ndarray, shape=None) -> np.ndarray:
    shape = shape or t.shape
    raw = np.asarray(raw)
    if t.type == F32:
        return raw.view("<f4").reshape(shape)
    if t.type == F16:
        return raw.view("<f2").astype(np.float32).reshape(shape)
    if t.type == BF16:
        return bf16_to_f32(raw.view("<u2")).reshape(shape)
    if t.type == Q8_0:
        b = raw.reshape(-1, 34)
        d = b[:, :2].copy().view("<f2").astype(np.float32)
        q = b[:, 2:].view(np.int8).astype(np.float32)
        return (q * d).reshape(shape)
    import gguf.quants as GQ                 # the pinned gguf-py's reference dequantizers (K-quants, IQ, ...)
    rows = int(np.prod(shape[:-1], dtype=np.int64)) if len(shape) > 1 else 1
    return GQ.dequantize(raw.reshape(rows, -1), QT(t.type)).astype(np.float32).reshape(shape)


def decode_bf16(t: TInfo, raw: np.ndarray, shape=None):
    """(u16 BF16 bytes in numpy order, exact)."""
    shape = shape or t.shape
    if t.type == BF16:
        return np.asarray(raw).view("<u2").reshape(shape), True
    u, ex = f32_to_bf16(decode_f32(t, raw, shape))
    return u.reshape(shape), ex


# =====================================================================================================================
# 3. The mapping: GGUF tensors -> the checkpoint's 31 mtp.* tensors
# =====================================================================================================================
class CT:
    """One checkpoint tensor reconstructed from the source. kind: norm (1-D, rt f32 +1) | mat (2-D) | experts (3-D)."""

    def __init__(self, name, shape, kind, sources, how):
        self.name, self.shape, self.kind, self.sources, self.how = name, tuple(shape), kind, sources, how
        self.plus1 = self.consistent = False
        self.exact = None             # all values exactly the checkpoint's BF16 (as far as the source can tell)
        self.f32 = self.u16 = None    # callables (mat / norm)
        self.rt_f32 = None            # norm: the rt's F32 values
        self.expert = None            # experts: e -> (f32 rows, u16 rows or None)
        self.note = ""


def nextn_layer(src):
    arch = src.kv.get("general.architecture", "?")
    bc, nx = src.kv.get(f"{arch}.block_count"), src.kv.get(f"{arch}.nextn_predict_layers")
    lays = sorted({int(n.split(".")[1]) for n in src.tensors if n.startswith("blk.") and ".nextn." in n})
    if isinstance(bc, int) and isinstance(nx, int) and nx >= 1 and (bc - nx) in lays:
        return bc - nx, arch
    if len(lays) == 1:
        return lays[0], arch
    raise ValueError(f"no single nextn layer (block_count {bc}, nextn_predict_layers {nx}, nextn tensors in {lays})")


def entries(L):
    g = lambda s: f"blk.{L}.{s}"  # noqa: E731
    hc = lambda part, gg: [  # noqa: E731
        (f"mtp.layers.0.{part}.block_inject_weight.weight", "mat", [g(f"hc_{gg}_inject.weight")]),
        (f"mtp.layers.0.{part}.hc_norm.weight", "norm", [g(f"hc_{gg}_norm.weight")]),
        (f"mtp.layers.0.{part}.input_mix_weight_down.weight", "mat", [g(f"hc_{gg}_down.weight")]),
        (f"mtp.layers.0.{part}.input_mix_weight_up.weight", "mat", [g(f"hc_{gg}_up.weight")])]
    E = [("mtp.fc_embedding.weight", "eh0", [g("nextn.eh_proj.weight")]),
         ("mtp.fc_hidden.weight", "eh1", [g("nextn.eh_proj.weight")]),
         ("mtp.hyper_connection_mixer.hc_norm.weight", "norm", [g("nextn.hc_head_norm.weight")]),
         ("mtp.hyper_connection_mixer.input_mix_weight_down.weight", "mat", [g("nextn.hc_head_down.weight")]),
         ("mtp.hyper_connection_mixer.input_mix_weight_up.weight", "mat", [g("nextn.hc_head_up.weight")])]
    E += hc("attn_hyper_connection", "attn")
    E += [(DOWN, "experts", [g("ffn_down_exps.weight")]),
          (GATE_UP, "experts", [g("ffn_gate_exps.weight"), g("ffn_up_exps.weight")]),
          ("mtp.layers.0.mlp.gate.weight", "mat", [g("ffn_gate_inp.weight")]),
          ("mtp.layers.0.mlp.shared_expert.down_proj.weight", "mat", [g("ffn_down_shexp.weight")]),
          ("mtp.layers.0.mlp.shared_expert.gate_proj.weight", "mat", [g("ffn_gate_shexp.weight")]),
          ("mtp.layers.0.mlp.shared_expert.up_proj.weight", "mat", [g("ffn_up_shexp.weight")]),
          ("mtp.layers.0.mlp.shared_expert_gate.weight", "row", [g("ffn_gate_inp_shexp.weight")])]
    E += hc("mlp_hyper_connection", "ffn")
    E += [("mtp.layers.0.self_attn.indexer.index_qk_proj.weight", "qk", [g("indexer.q_proj.weight"), g("indexer.k_proj.weight")]),
          ("mtp.layers.0.self_attn.indexer.k_layernorm.weight", "norm", [g("indexer.k_norm.weight")]),
          ("mtp.layers.0.self_attn.indexer.q_layernorm.weight", "norm", [g("indexer.q_norm.weight")]),
          ("mtp.layers.0.self_attn.k_norm.weight", "norm", [g("attn_k_norm.weight")]),
          ("mtp.layers.0.self_attn.k_proj.weight", "mat", [g("attn_k.weight")]),
          ("mtp.layers.0.self_attn.o_proj.weight", "mat", [g("attn_output.weight")]),
          ("mtp.layers.0.self_attn.q_norm.weight", "norm", [g("attn_q_norm.weight")]),
          ("mtp.layers.0.self_attn.q_proj.weight", "mat", [g("attn_q.weight")]),
          ("mtp.layers.0.self_attn.v_proj.weight", "mat", [g("attn_v.weight")]),
          ("mtp.pre_fc_norm_embedding.weight", "norm", [g("nextn.enorm.weight")]),
          ("mtp.pre_fc_norm_hidden.weight", "norm", [g("nextn.hnorm.weight")])]
    return E


NOT_USED = ("token_embd.weight", "output.weight", "nextn.embed_tokens.weight", "nextn.shared_head_head.weight")


def sha_u16(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def load_manifest(path):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    m = json.loads(p.read_text())
    return {t["name"]: t for t in m}


def norm_rule(v: np.ndarray):
    """('plus1' | 'raw' | 'either' | 'neither') for stored F32 norm values (see the module text)."""
    u = np.ascontiguousarray(v, dtype=np.float32).view(np.uint32)
    raw_ok = not np.any(u & 0xFFFF)
    m1 = (np.ascontiguousarray(v, dtype=np.float32) - np.float32(1.0)).astype(np.float32).view(np.uint32)
    p1_ok = not np.any(m1 & 0xFFFF)
    return {(True, False): "plus1", (False, True): "raw", (True, True): "either", (False, False): "neither"}[(p1_ok, raw_ok)]


def build(src, eh_order="auto", qk_order="auto", norms="auto", manifest=None, data=True):
    """The 31 checkpoint tensors (OrderedDict name -> CT, sorted) + a report dict. data=False: header only."""
    L, arch = nextn_layer(src)
    rep = OrderedDict([("source", str(src.path)), ("arch", arch), ("nextn_layer", L), ("head_only", bool(src.head_only)),
                       ("shared_flag", src.kv.get(f"{arch}.nextn_shared_target_tensors")), ("warnings", [])])
    T = src.tensors
    used = set()
    ents = entries(L)
    missing = [s for _n, _k, ss in ents for s in ss if s not in T]
    if missing:
        raise ValueError(f"tensors missing from {src.path.name}: {missing}")
    extra = [n for n in T if n not in {s for _n, _k, ss in ents for s in ss}]
    rep["not_used"] = [n for n in extra if n.endswith(NOT_USED) or n in NOT_USED]
    rep["unmapped"] = [n for n in extra if n not in rep["not_used"]]
    if rep["unmapped"]:
        rep["warnings"].append(f"tensors this mapping does not know: {rep['unmapped']}")
    rep["shared"] = not any(n in T for n in ("token_embd.weight", "output.weight"))
    H = T[f"blk.{L}.nextn.enorm.weight"].ne[0]
    gt = T[f"blk.{L}.ffn_gate_exps.weight"]
    FF, NE = gt.ne[1], gt.ne[2]
    rep["dims"] = {"H": H, "FF": FF, "experts": NE, "hc_width": T[f"blk.{L}.nextn.hnorm.weight"].ne[0],
                   "hc_low_rank": T[f"blk.{L}.nextn.hc_head_down.weight"].ne[1],
                   "q_rows": T[f"blk.{L}.attn_q.weight"].ne[1], "indexer_q": T[f"blk.{L}.indexer.q_proj.weight"].ne[1],
                   "indexer_k": T[f"blk.{L}.indexer.k_proj.weight"].ne[1]}
    if T[f"blk.{L}.nextn.eh_proj.weight"].ne != (2 * H, H):
        raise ValueError(f"eh_proj is {T[f'blk.{L}.nextn.eh_proj.weight'].ne}, expected ({2 * H}, {H})")
    # ---- orders and the norm rule, decided once (auto: the pinned checkpoint's sha256 when a manifest is given)
    orders = {"eh": eh_order, "qk": qk_order}
    if data:
        eh = T[f"blk.{L}.nextn.eh_proj.weight"]
        ehu, ehx = decode_bf16(eh, src.raw(eh.name))
        if eh_order == "auto":
            orders["eh"], why = "eh", "assumed: embedding first (llama.cpp's nextn convention [enorm(e) | hnorm(h)])"
            if manifest and ehx:
                a, b = sha_u16(ehu[:, :H]), sha_u16(ehu[:, H:])
                me, mh = manifest["mtp.fc_embedding.weight"]["sha256"], manifest["mtp.fc_hidden.weight"]["sha256"]
                if (a, b) == (me, mh):
                    why = "decided: columns 0..H-1 hash to the checkpoint's fc_embedding"
                elif (a, b) == (mh, me):
                    orders["eh"], why = "he", "decided: columns 0..H-1 hash to the checkpoint's fc_hidden"
                else:
                    why = "neither half hashes to the checkpoint's fc_embedding / fc_hidden: " + why
            rep["eh_order_why"] = why
        qn, kn = T[f"blk.{L}.indexer.q_proj.weight"], T[f"blk.{L}.indexer.k_proj.weight"]
        if qk_order == "auto":
            orders["qk"], why = "qk", "assumed: q rows first (conversion/qwen4exp.py splits index_qk_proj as q = rows[:n_q])"
            qu, qx = decode_bf16(qn, src.raw(qn.name))
            ku, kx = decode_bf16(kn, src.raw(kn.name))
            if manifest and qx and kx:
                m = manifest["mtp.layers.0.self_attn.indexer.index_qk_proj.weight"]["sha256"]
                if sha_u16(np.concatenate([qu, ku])) == m:
                    why = "decided: [q; k] hashes to the checkpoint's index_qk_proj"
                elif sha_u16(np.concatenate([ku, qu])) == m:
                    orders["qk"], why = "kq", "decided: [k; q] hashes to the checkpoint's index_qk_proj"
                else:
                    why = "neither row order hashes to the checkpoint's index_qk_proj: " + why
            rep["qk_order_why"] = why
    for k_, d_ in (("eh", "eh"), ("qk", "qk")):
        if orders[k_] == "auto":                  # header only: the defaults (the data decides in verify / convert)
            orders[k_] = d_
            rep[f"{k_}_order_why"] = "default (header only: verify / convert decide it from the data and the manifest)"
    rep["eh_order"], rep["qk_order"] = orders["eh"], orders["qk"]
    # ---- the norm rule
    norm_votes = OrderedDict()
    if data:
        for n, k, ss in ents:
            if k == "norm":
                t = T[ss[0]]
                norm_votes[n] = norm_rule(decode_f32(t, src.raw(t.name))) if t.type == F32 else f"stored {t.tname}"
    p1 = sum(1 for v in norm_votes.values() if v == "plus1")
    rw = sum(1 for v in norm_votes.values() if v == "raw")
    default = "plus1" if p1 >= rw else "raw"
    rep["norm_votes"], rep["norm_default"] = norm_votes, (norms if norms != "auto" else default)
    out = OrderedDict()
    for n, k, ss in ents:
        ts = [T[s] for s in ss]
        if k == "norm":
            c = CT(n, (ts[0].ne[0],), "norm", ss, f"{ts[0].tname} {list(ts[0].ne)}")
            if data:
                t = ts[0]
                v = decode_f32(t, src.raw(t.name)).reshape(-1)
                rule = norms if norms != "auto" else (norm_votes[n] if norm_votes[n] in ("plus1", "raw") else default)
                if rule == "plus1":
                    c.rt_f32 = v.astype(np.float32)
                    w = (v - np.float32(1.0)).astype(np.float32)
                else:
                    c.rt_f32 = (v.astype(np.float32) + np.float32(1.0)).astype(np.float32)
                    w = v
                u, ex = f32_to_bf16(w)
                c.u16 = (lambda u=u: u)
                c.exact = ex and t.type in (F32, BF16, F16)
                c.plus1 = rule == "plus1"
                # "+1 stored" loses |w| < 2^-16 (fl(1 + w) rounds them): the rt value fl(w + 1) is still the stored one
                # exactly when some BF16 w0 reproduces every stored value
                c.consistent = bool(np.array_equal((bf16_to_f32(u) + np.float32(1.0)).astype(np.float32).view(np.uint32),
                                                   v.astype(np.float32).view(np.uint32))) if c.plus1 else ex
                c.how = f"{t.tname} {t.ne}, norm stored {'with' if rule == 'plus1' else 'without'} the +1 ({norm_votes[n]})"
            out[n] = c
        elif k in ("mat", "row"):
            t = ts[0]
            shape = t.shape if k == "mat" else (1, t.ne[0])
            c = CT(n, shape, "mat", ss, f"{t.tname} {list(t.ne)}" + (" -> [1, H]" if k == "row" else ""))
            if data:
                c.u16 = (lambda t=t, shape=shape: decode_bf16(t, src.raw(t.name), shape)[0])
                c.f32 = (lambda t=t, shape=shape: decode_f32(t, src.raw(t.name), shape))
                c.exact = decode_bf16(t, src.raw(t.name), shape)[1]
            out[n] = c
        elif k in ("eh0", "eh1"):
            t = ts[0]
            half = (0 if k == "eh0" else 1) if orders["eh"] == "eh" else (1 if k == "eh0" else 0)
            sl = slice(half * H, (half + 1) * H)
            c = CT(n, (H, H), "mat", ss, f"{t.tname} {list(t.ne)} columns {sl.start}..{sl.stop - 1} ({orders['eh']})")
            if data:
                c.f32 = (lambda t=t, sl=sl: np.ascontiguousarray(decode_f32(t, src.raw(t.name))[:, sl]))
                c.u16 = (lambda t=t, sl=sl: np.ascontiguousarray(decode_bf16(t, src.raw(t.name))[0][:, sl]))
                c.exact = decode_bf16(t, src.raw(t.name))[1]
            out[n] = c
        elif k == "qk":
            q, kk = ts
            first, second = (q, kk) if orders["qk"] == "qk" else (kk, q)
            c = CT(n, (q.ne[1] + kk.ne[1], q.ne[0]), "mat", ss,
                   f"rows [{first.name.split('.')[-2]}; {second.name.split('.')[-2]}] ({q.tname}, {kk.tname})")
            if data:
                c.f32 = (lambda a=first, b=second: np.concatenate([decode_f32(a, src.raw(a.name)), decode_f32(b, src.raw(b.name))]))
                c.u16 = (lambda a=first, b=second: np.concatenate([decode_bf16(a, src.raw(a.name))[0], decode_bf16(b, src.raw(b.name))[0]]))
                c.exact = decode_bf16(q, src.raw(q.name))[1] and decode_bf16(kk, src.raw(kk.name))[1]
            out[n] = c
        elif k == "experts":
            if n == GATE_UP:
                g_, u_ = ts
                c = CT(n, (NE, 2 * FF, H), "experts", ss, f"[gate; up] rows ({g_.tname}, {u_.tname})")
                parts = [g_, u_]
            else:
                c = CT(n, (NE, H, FF), "experts", ss, f"{ts[0].tname} {list(ts[0].ne)}")
                parts = ts
            if data:
                raws = [src.raw(p.name) for p in parts]

                def expert(e, parts=parts, raws=raws, want_u16=True):
                    fs, us, ex = [], [], True
                    for p, r in zip(parts, raws):
                        rb = _row_bytes(p) * p.ne[1]                       # one expert = ne[1] rows
                        sl = np.asarray(r[e * rb:(e + 1) * rb])
                        shape = (p.ne[1], p.ne[0])
                        f = decode_f32(p, sl, shape)
                        fs.append(f)
                        if want_u16:
                            if p.type == BF16:
                                us.append(sl.view("<u2").reshape(shape))
                            else:
                                u, x = f32_to_bf16(f)
                                us.append(u.reshape(shape))
                                ex = ex and x
                    return np.concatenate(fs) if len(fs) > 1 else fs[0], \
                        ((np.concatenate(us) if len(us) > 1 else us[0]) if want_u16 else None), ex
                c.expert = expert
                c.exact = all(p.type == BF16 for p in parts) or None   # F32 / F16 sources: known per expert
            out[n] = c
    rep["types"] = {n: c.how for n, c in out.items()}
    return OrderedDict(sorted(out.items())), rep, (H, FF, NE)


# =====================================================================================================================
# 4. The rt writer (mtp_rt.py's order and layout) with an in-memory comparison against a reference rt
# =====================================================================================================================
def parse_dense_txt(path):
    rows = OrderedDict()
    for line in Path(path).read_text().splitlines():
        if line.strip():
            n, kind, r, c, off, b = line.split()
            rows[n] = (kind, int(r), int(c), int(off), int(b))
    return rows


def dense_diff(kind, ours: bytes, ref: bytes, rows, cols):
    """A short description of how two encodings of one tensor differ."""
    a, b = np.frombuffer(ours, np.uint8), np.frombuffer(ref, np.uint8)
    if a.size != b.size:
        return f"sizes {a.size} vs {b.size}"
    nd = int(np.count_nonzero(a != b))
    if kind == "f32":
        x, y = a.view("<f4"), b.view("<f4")
        return f"{nd} bytes differ; max |diff| {float(np.max(np.abs(x - y))):.3g}"
    if kind == "bf16":
        x, y = a.view("<u2"), b.view("<u2")
        dv = bf16_to_f32(x) - bf16_to_f32(y)
        return f"{int(np.count_nonzero(x != y))} of {x.size} values differ; max |diff| {float(np.max(np.abs(dv))):.3g}"
    xa, xb = a.reshape(-1, 34), b.reshape(-1, 34)
    fa = xa[:, 2:].view(np.int8).astype(np.float32) * xa[:, :2].copy().view("<f2").astype(np.float32)
    fb = xb[:, 2:].view(np.int8).astype(np.float32) * xb[:, :2].copy().view("<f2").astype(np.float32)
    rel = float(np.sqrt(((fa - fb) ** 2).mean()) / (np.sqrt((fb ** 2).mean()) + 1e-30))
    return f"{int(np.count_nonzero((xa != xb).any(axis=1)))} of {xa.shape[0]} Q8_0 blocks differ; relative RMS {rel:.3g}"


def q2_dequant(blob, n):
    b = blob.reshape(-1, 18)
    d = b[:, :2].copy().view(np.float16).astype(np.float32)
    qs = b[:, 2:]
    codes = np.stack([(qs >> s) & 3 for s in (0, 2, 4, 6)], axis=2).reshape(-1, 64).astype(np.float32)
    return ((codes - 1.0) * d).reshape(-1)[:n]


def drop_cache(path):
    """Drop a file's clean pages from the page cache (what was read for the check stays out of the gaps' way)."""
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)
    except OSError:
        pass


class Throttle:
    def __init__(self, mbps):
        self.rate, self.t0, self.n = (mbps or 0) * 1e6, time.monotonic(), 0

    def add(self, nbytes):
        if self.rate <= 0:
            return
        self.n += nbytes
        lag = self.n / self.rate - (time.monotonic() - self.t0)
        if lag > 0:
            time.sleep(lag)


def write_rt(cts, dims, out_dir=None, ref_rt=None, manifest=None, experts=None, throttle=None, draft_vocab=None, log=print):
    """Encode every tensor as mtp_rt.py does; compare with ref_rt (in memory); write out_dir when given.
    experts: None = all, or an iterable of expert indices (a partial check: nothing is written then)."""
    H, FF, NE = dims
    res = OrderedDict([("dense", OrderedDict()), ("experts", {}), ("source_sha", OrderedDict())])
    ref_rows = parse_dense_txt(Path(ref_rt) / "dense.txt") if ref_rt else None
    ref_dense = np.memmap(Path(ref_rt) / "dense.bin", np.uint8, "r") if ref_rt else None
    # ---- dense.bin / dense.txt
    lines, chunks, off = [], [], 0
    for name, c in cts.items():
        if c.kind == "experts":
            continue
        short = short_of(name)
        if c.kind == "norm":
            raw, kind, rows, cols = c.rt_f32.astype(np.float32).tobytes(), "f32", 1, c.rt_f32.size
            u = c.u16()
        else:
            u = c.u16()
            u2 = u.reshape(c.shape[0], -1)
            rows, cols = u2.shape
            if short in Q8:
                f = c.f32().astype(np.float32) if not c.exact else bf16_to_f32(u2)
                raw, kind = q8_0(f.reshape(rows, cols)), "q8_0"
            else:
                raw, kind = u2.tobytes(), "bf16"
        pad = (-off) % 256
        chunks.append(b"\0" * pad)
        off += pad
        chunks.append(raw)
        lines.append(f"{short} {kind} {rows} {cols} {off} {len(raw)}")
        d = OrderedDict([("kind", kind), ("rows", rows), ("cols", cols), ("off", off), ("bytes", len(raw)),
                         ("exact_source", bool(c.exact)), ("how", c.how), ("sha256", hashlib.sha256(raw).hexdigest())])
        if manifest and name in manifest:
            d["source_matches_checkpoint"] = (sha_u16(u) == manifest[name]["sha256"]) if c.exact else None
            if d["source_matches_checkpoint"] is False and getattr(c, "plus1", False) and getattr(c, "consistent", False):
                d["source_matches_checkpoint"] = "rt-equivalent"     # see build(): tiny |w| not recoverable, rt the same
        if ref_rows is not None:
            r = ref_rows.get(short)
            if r is None:
                d["ref"] = "not in the reference dense.txt"
            elif (kind, rows, cols, off, len(raw)) != r:
                d["ref"] = f"index differs: ours {(kind, rows, cols, off, len(raw))}, ref {r}"
            else:
                rb = bytes(ref_dense[r[3]:r[3] + r[4]])
                d["ref"] = "identical" if rb == raw else "DIFFERS: " + dense_diff(kind, raw, rb, rows, cols)
        res["dense"][short] = d
        off += len(raw)
    dense_bin = b"".join(chunks)
    dense_txt = "\n".join(lines) + "\n"
    res["dense_bytes"] = len(dense_bin)
    res["dense_sha256"] = hashlib.sha256(dense_bin).hexdigest()
    if ref_rt:
        rt_txt = (Path(ref_rt) / "dense.txt").read_text()
        res["dense_txt_identical"] = rt_txt == dense_txt
        res["dense_bin_identical"] = (Path(ref_rt) / "dense.bin").stat().st_size == len(dense_bin) and \
            all(v.get("ref") == "identical" for v in res["dense"].values()) and \
            bytes(ref_dense[:]) == dense_bin
    # ---- experts.bin
    gu, dn = cts[GATE_UP], cts[DOWN]
    blob = 3 * (H * FF * 18 // 64)
    ref_exp = np.memmap(Path(ref_rt) / "experts.bin", np.uint8, "r") if ref_rt else None
    if ref_exp is not None and ref_exp.size != NE * blob:
        res["experts"]["ref_size"] = f"reference experts.bin is {ref_exp.size:,} B, ours {NE * blob:,}"
    todo = list(range(NE)) if experts is None else list(experts)
    write = out_dir is not None and experts is None
    fo = None
    if write:
        out = Path(out_dir)
        (out / "dense.bin").write_bytes(dense_bin)
        (out / "dense.txt").write_text(dense_txt, encoding="utf-8")
        fo = open(out / "experts.bin", "wb")
    sha_out = hashlib.sha256()
    sha_src = {GATE_UP: hashlib.sha256(), DOWN: hashlib.sha256()}
    same, differ, src_ok, src_exact = 0, [], True, True
    diffs = []
    t0 = time.time()
    for i, e in enumerate(todo):
        fg, ug, xg = gu.expert(e)
        fd, ud, xd = dn.expert(e)
        src_exact = src_exact and xg and xd
        if xg and xd:
            gf, df = bf16_to_f32(ug), bf16_to_f32(ud)        # mtp_pack quantizes the BF16 values (as f32)
        else:
            gf, df = fg, fd
        sha_src[GATE_UP].update(np.ascontiguousarray(ug).tobytes())
        sha_src[DOWN].update(np.ascontiguousarray(ud).tobytes())
        b = blob_of(q2_0(gf).reshape(2 * FF, H // 64 * 18), q2_0(df).reshape(H, FF // 64 * 18), H, FF)
        sha_out.update(b)
        if ref_exp is not None and ref_exp.size == NE * blob:
            rb = bytes(ref_exp[e * blob:(e + 1) * blob])
            if rb == b:
                same += 1
            else:
                differ.append(e)
                if len(diffs) < 4:
                    a1 = np.frombuffer(b, np.uint8)
                    b1 = np.frombuffer(rb, np.uint8)
                    diffs.append({"expert": e, "bytes_differing": int(np.count_nonzero(a1 != b1))})
        if fo is not None:
            fo.write(b)
            if i % 64 == 63:
                fo.flush()
                os.fdatasync(fo.fileno())
                os.posix_fadvise(fo.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        if throttle is not None:
            throttle.add(np.asarray(ug).nbytes + np.asarray(ud).nbytes)
        if i % 64 == 63:
            log(f"  experts {i + 1}/{len(todo)} ({time.time() - t0:.0f} s)")
    if fo is not None:
        fo.flush()
        os.fdatasync(fo.fileno())
        os.posix_fadvise(fo.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        fo.close()
        if draft_vocab:
            (Path(out_dir) / "draft_vocab.bin").write_bytes(Path(draft_vocab).read_bytes())
    res["experts"].update({"checked": len(todo), "of": NE, "blob_bytes": blob, "exact_source": bool(src_exact),
                           "seconds": round(time.time() - t0, 1)})
    if experts is None:
        res["experts"]["sha256"] = sha_out.hexdigest()
        if manifest:
            for n in (GATE_UP, DOWN):
                if n in manifest:
                    res["source_sha"][n] = (sha_src[n].hexdigest() == manifest[n]["sha256"]) if src_exact else None
    if ref_exp is not None:
        res["experts"]["identical"] = same
        res["experts"]["differ"] = differ[:20]
        res["experts"]["n_differ"] = len(differ)
        res["experts"]["examples"] = diffs
    return res


def summarize(res, rep, log=print):
    ok = True
    log(f"source: {rep['source']} (arch {rep['arch']}, nextn layer {rep['nextn_layer']}, "
        f"{'shared' if rep['shared'] else 'standalone'}; shared flag {rep['shared_flag']})")
    log(f"  dims {rep['dims']}; eh order {rep['eh_order']} ({rep.get('eh_order_why', 'given')}); qk order {rep['qk_order']} "
        f"({rep.get('qk_order_why', 'given')}); norms: default {rep['norm_default']}, votes "
        f"{dict(Counter(rep['norm_votes'].values()))}")
    for w in rep["warnings"]:
        log(f"  WARNING: {w}")
    if rep["not_used"]:
        log(f"  not used (the main model's): {rep['not_used']}")
    for short, d in res["dense"].items():
        st = d.get("ref", "-")
        sm = d.get("source_matches_checkpoint")
        log(f"  {short:58s} {d['kind']:5s} {d['rows']:>6} x {d['cols']:<6} {'exact' if d['exact_source'] else 'ROUNDED'}"
            f"  ckpt {'~' if sm == 'rt-equivalent' else '=' if sm else '-' if sm is None else 'DIFFERS'}  rt {st}")
        if "ref" in d and d["ref"] != "identical":
            ok = False
        if sm is False:
            ok = False
    if "dense_txt_identical" in res:
        log(f"  dense.txt identical: {res['dense_txt_identical']}; dense.bin identical: {res['dense_bin_identical']} "
            f"({res['dense_bytes']:,} B, sha256 {res['dense_sha256'][:16]})")
        ok = ok and res["dense_txt_identical"] and res["dense_bin_identical"]
    ex = res["experts"]
    log(f"  experts: {ex['checked']} of {ex['of']} encoded in {ex['seconds']} s; source exact {ex['exact_source']}"
        + (f"; identical to the reference {ex['identical']} / differ {ex['n_differ']} {ex['differ'][:8]}" if "identical" in ex else "")
        + (f"; sha256 {ex['sha256'][:16]}" if "sha256" in ex else "")
        + (f"; checkpoint sha256: {dict(res['source_sha'])}" if res["source_sha"] else ""))
    if ex.get("n_differ"):
        ok = False
    if any(v is False for v in res["source_sha"].values()):
        ok = False
    return ok


# =====================================================================================================================
# 5. Commands
# =====================================================================================================================
def forecast(src, rep, cts):
    """Header-only: per checkpoint tensor, can this file reproduce our rt bytes?"""
    L = rep["nextn_layer"]
    out = []
    for n, c in cts.items():
        ts = [src.tensors[s] for s in c.sources]
        types = {t.tname for t in ts}
        short = short_of(n)
        if c.kind == "experts":
            v = "exact (BF16 -> Q2_0 as mtp_pack)" if types == {"BF16"} else \
                f"OTHER Q2_0 experts (re-quantized from {'/'.join(sorted(types))} values)"
        elif c.kind == "norm":
            v = "exact if the values are f32(bf16)+1 or f32(bf16)" if types <= {"F32", "BF16", "F16"} else "rounded"
        elif short in Q8:
            v = ("exact (BF16 -> mtp_rt's Q8_0)" if types == {"BF16"} else
                 "exact if the values are BF16" if types <= {"F32", "F16"} else
                 "exact if the publisher's Q8_0 is ggml's reference rounding of the same BF16 (re-quantizing is the identity)"
                 if types == {"Q8_0"} else "rounded (lossy source)")
        else:
            v = ("exact" if types == {"BF16"} else "exact if the values are BF16" if types <= {"F32", "F16"} else
                 "ROUNDED to BF16 from " + "/".join(sorted(types)))
        out.append((n, c.kind, c.shape, c.how, v))
    _ = L
    return out


def cmd_inspect(a):
    src = GGUF(a.gguf)
    man = load_manifest(a.manifest)
    cts, rep, dims = build(src, a.eh_order, a.qk_order, a.norms, man, data=False)
    print(f"{src.path.name}: GGUF v{src.version}, {len(src.tensors)} tensors, {src.size:,} B"
          f"{' (head-only)' if src.head_only else ''}; arch {rep['arch']}, nextn layer {rep['nextn_layer']}, "
          f"{'SHARED (no token_embd / output: the main model gives them)' if rep['shared'] else 'standalone (own token_embd / output - unused by our rt)'}; "
          f"{rep['arch']}.nextn_shared_target_tensors = {rep['shared_flag']}")
    print(f"dims {rep['dims']}; vocab {src.vocab()}")
    if rep["unmapped"]:
        print(f"UNMAPPED tensors: {rep['unmapped']}")
    print(f"not used: {rep['not_used'] or '-'}")
    for n, kind, shape, how, v in forecast(src, rep, cts):
        man_shape = (man or {}).get(n, {}).get("shape")
        print(f"  {n:66s} {kind:7s} {list(shape)}{'' if man_shape in (None, list(shape)) else ' (MANIFEST ' + str(man_shape) + ')'}"
              f"  <- {how}: {v}")
    if man:
        bad = [n for n, c in cts.items() if n in man and list(c.shape) != man[n]["shape"]]
        miss = sorted(set(man) - set(cts))
        print(f"against {a.manifest}: {len(cts)} tensors mapped, {len(miss)} of the manifest's missing {miss or ''}, "
              f"{len(bad)} shape mismatches {bad or ''}")
        if bad or miss:
            return 1
    return 0


def _common_build(a):
    src = GGUF(a.gguf)
    if src.head_only:
        sys.exit(f"{src.path.name} is head-only: `inspect` reads it; verify / convert need the whole file")
    man = load_manifest(a.manifest)
    cts, rep, dims = build(src, a.eh_order, a.qk_order, a.norms, man, data=True)
    return src, man, cts, rep, dims


def cmd_verify(a):
    src, man, cts, rep, dims = _common_build(a)
    exp = None if a.experts is None else range(min(a.experts, dims[2]))
    res = write_rt(cts, dims, None, a.ref_rt, man, exp, Throttle(a.max_mbps))
    drop_cache(src.path)
    ok = summarize(res, rep)
    if a.report:
        Path(a.report).write_text(json.dumps({"version": VERSION, "report": rep, "result": res, "ok": ok}, indent=1,
                                             default=str) + "\n")
    print("VERIFY:", "IDENTICAL to the reference rt" if ok and a.ref_rt else "OK" if ok else "DIFFERENCES (see above)")
    return 0 if ok else 1


def cmd_convert(a):
    out = Path(a.out).resolve()
    for p in PROTECTED:
        if out == p.resolve() or p.resolve() in out.parents:
            sys.exit(f"refused: {out} is inside {p} (read-only trees)")
    if out.exists() and any(out.iterdir()):
        sys.exit(f"refused: {out} exists and is not empty (never overwritten)")
    src, man, cts, rep, dims = _common_build(a)
    dv = a.draft_vocab
    if dv is None:
        cand = Path(a.ref_rt or REF_RT) / "draft_vocab.bin"
        if src.vocab() == 248320 and cand.exists():
            dv = cand
            rep["warnings"].append(f"draft_vocab.bin copied from {cand} (the served tokenizer's 248,320-token vocab)")
        else:
            rep["warnings"].append("no draft_vocab.bin (another vocab: make one with the release's tools/draft_vocab.py; "
                                   "without it the draft head is the whole main head)")
    out.mkdir(parents=True, exist_ok=True)
    res = write_rt(cts, dims, out, a.ref_rt, man, None, Throttle(a.max_mbps), dv)
    drop_cache(src.path)
    ok = summarize(res, rep)
    (out.parent / f"{out.name}.conversion.json").write_text(json.dumps(
        {"version": VERSION, "source": str(src.path), "source_size": src.size, "report": rep, "result": res, "ok": ok,
         "draft_vocab": str(dv) if dv else None}, indent=1, default=str) + "\n")
    print(f"wrote {out} (dense.bin {res['dense_bytes']:,} B, experts.bin {dims[2] * 3 * (dims[0] * dims[1] * 18 // 64):,} B"
          f"{', draft_vocab.bin' if dv else ''}); report {out.parent / (out.name + '.conversion.json')}")
    return 0 if ok or not a.ref_rt else 1


# =====================================================================================================================
# 6. Self-test (offline)
# =====================================================================================================================
def tool_functions(tools=None):
    """mtp_pack.q2_0, mtp_rt.q8_0 and mtp_rt.blob_of from the read-only tree, extracted by ast (their modules import
    gguf-py through _paths at import time; only the function bodies are taken)."""
    import ast
    ns = {"np": np, "H": 2560, "FF": 640, "NE": 512}
    ns["BLOB"] = 3 * (ns["H"] * ns["FF"] * 18 // 64)
    got = {}
    tools = Path(tools or TOOLS)
    for fn, names in (("mtp_pack.py", ("q2_0",)), ("mtp_rt.py", ("q8_0", "blob_of"))):
        tree = ast.parse((tools / fn).read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                code = compile(ast.Module(body=[node], type_ignores=[]), str(tools / fn), "exec")
                d = dict(ns)
                exec(code, d)                  # our own trusted tool code (read-only tree), not downloaded data
                got[f"{fn}:{node.name}"] = d[node.name]
    return got


def ckpt_u16(ckdir, man, name):
    t = man[name]
    return np.memmap(Path(ckdir) / t["file"], dtype="<u2", mode="r", shape=tuple(t["shape"]))


def unsloth_layout_from_ckpt(get, shapes, L, H, norms_plus1=True, router_f32=True, shared=True, vocab=None,
                             mat_type="BF16", eh_first=True, q_first=True):
    """The forward direction, written independently of entries(): what a llama.cpp-style converter makes of the
    checkpoint's mtp.* tensors (GGUF ne = numpy shape reversed). get(name) -> u16 array (checkpoint layout)."""
    g = lambda s: f"blk.{L}.{s}"  # noqa: E731
    items = OrderedDict()

    def mat(name, u16):
        a = np.ascontiguousarray(u16)
        if mat_type == "BF16":
            items[name] = (BF16, list(reversed(a.shape)), a.view(np.uint8).reshape(-1))
        else:                                                  # Q8_0 (ggml reference rounding of the BF16 values)
            items[name] = (Q8_0, list(reversed(a.shape)), np.frombuffer(q8_0(bf16_to_f32(a)), np.uint8))

    def f32(name, v):
        v = np.ascontiguousarray(v, dtype=np.float32)
        items[name] = (F32, list(reversed(v.shape)), v.view(np.uint8).reshape(-1))

    def norm(name, ck):
        w = bf16_to_f32(get(ck)).reshape(-1)
        f32(name, (w + np.float32(1.0)).astype(np.float32) if norms_plus1 else w)

    fe, fh = get("mtp.fc_embedding.weight"), get("mtp.fc_hidden.weight")
    mat(g("nextn.eh_proj.weight"), np.concatenate([fe, fh] if eh_first else [fh, fe], axis=1))
    norm(g("nextn.enorm.weight"), "mtp.pre_fc_norm_embedding.weight")
    norm(g("nextn.hnorm.weight"), "mtp.pre_fc_norm_hidden.weight")
    norm(g("nextn.hc_head_norm.weight"), "mtp.hyper_connection_mixer.hc_norm.weight")
    mat(g("nextn.hc_head_down.weight"), get("mtp.hyper_connection_mixer.input_mix_weight_down.weight"))
    mat(g("nextn.hc_head_up.weight"), get("mtp.hyper_connection_mixer.input_mix_weight_up.weight"))
    for part, gg in (("attn_hyper_connection", "attn"), ("mlp_hyper_connection", "ffn")):
        p = f"mtp.layers.0.{part}."
        mat(g(f"hc_{gg}_inject.weight"), get(p + "block_inject_weight.weight"))
        norm(g(f"hc_{gg}_norm.weight"), p + "hc_norm.weight")
        mat(g(f"hc_{gg}_down.weight"), get(p + "input_mix_weight_down.weight"))
        mat(g(f"hc_{gg}_up.weight"), get(p + "input_mix_weight_up.weight"))
    a = "mtp.layers.0.self_attn."
    for gn, ck in (("attn_q", "q_proj"), ("attn_k", "k_proj"), ("attn_v", "v_proj"), ("attn_output", "o_proj")):
        mat(g(f"{gn}.weight"), get(a + ck + ".weight"))
    norm(g("attn_q_norm.weight"), a + "q_norm.weight")
    norm(g("attn_k_norm.weight"), a + "k_norm.weight")
    qk = get(a + "indexer.index_qk_proj.weight")
    nq = shapes["indexer_q"]
    q_, k_ = (qk[:nq], qk[nq:]) if q_first else (qk[-nq:], qk[:-nq])
    items[g("indexer.q_proj.weight")] = (BF16, list(reversed(q_.shape)), np.ascontiguousarray(q_).view(np.uint8).reshape(-1))
    items[g("indexer.k_proj.weight")] = (BF16, list(reversed(k_.shape)), np.ascontiguousarray(k_).view(np.uint8).reshape(-1))
    norm(g("indexer.q_norm.weight"), a + "indexer.q_layernorm.weight")
    norm(g("indexer.k_norm.weight"), a + "indexer.k_layernorm.weight")
    m = "mtp.layers.0.mlp."
    gate = get(m + "gate.weight")
    if router_f32:
        f32(g("ffn_gate_inp.weight"), bf16_to_f32(gate))
    else:
        mat(g("ffn_gate_inp.weight"), gate)
    f32(g("ffn_gate_inp_shexp.weight"), bf16_to_f32(get(m + "shared_expert_gate.weight")).reshape(-1))
    for gn, ck in (("ffn_gate_shexp", "gate_proj"), ("ffn_up_shexp", "up_proj"), ("ffn_down_shexp", "down_proj")):
        mat(g(f"{gn}.weight"), get(m + "shared_expert." + ck + ".weight"))
    gu = get(GATE_UP)
    FF = gu.shape[1] // 2
    for gn, sl in (("ffn_gate_exps", slice(0, FF)), ("ffn_up_exps", slice(FF, 2 * FF))):
        part = gu[:, sl, :]
        if mat_type == "BF16":
            items[g(f"{gn}.weight")] = (BF16, list(reversed(part.shape)), _LazyBytes(part))
        else:
            items[g(f"{gn}.weight")] = (Q8_0, list(reversed(part.shape)),
                                        np.frombuffer(q8_0(bf16_to_f32(np.ascontiguousarray(part))), np.uint8))
    dn = get(DOWN)
    items[g("ffn_down_exps.weight")] = (BF16, list(reversed(dn.shape)), _LazyBytes(dn)) if mat_type == "BF16" else \
        (Q8_0, list(reversed(dn.shape)), np.frombuffer(q8_0(bf16_to_f32(np.ascontiguousarray(dn))), np.uint8))
    if not shared and vocab:
        rng = np.random.default_rng(5)
        emb = rng.integers(0, 1 << 16, size=(vocab, H), dtype=np.uint16) & 0x3FFF
        mat("token_embd.weight", emb)
        mat("output.weight", emb)
    return items


class _LazyBytes:
    """A 3-D u16 tensor (a memmap view) served as its flat bytes on slicing, without copying the whole thing."""

    def __init__(self, a):
        self.a = a
        self.e = a.shape[0]
        self.per = int(np.prod(a.shape[1:])) * 2
        self.size = self.e * self.per

    def __getitem__(self, sl):
        start, stop = sl.start or 0, sl.stop
        e = start // self.per
        assert start % self.per == 0 and stop - start == self.per, (start, stop)
        return np.ascontiguousarray(self.a[e]).view(np.uint8).reshape(-1)

    def __array__(self, dtype=None, copy=None):
        return np.ascontiguousarray(self.a).view(np.uint8).reshape(-1)


def cmd_selftest(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "selftest.log", "w", encoding="utf-8")

    def log(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    results = OrderedDict()
    log(f"{VERSION} selftest {time.strftime('%F %T')}; numpy {np.__version__}")
    # ---- T0: the copied arithmetic equals the tools' own functions (random data incl. edge cases)
    tf = tool_functions(a.tools)
    rng = np.random.default_rng(11)
    cases = [rng.standard_normal((64, 2560)).astype(np.float32), np.zeros((4, 2560), np.float32),
             (rng.standard_normal((16, 2560)) * 1e-6).astype(np.float32),
             (rng.standard_normal((8, 2560)) * 300).astype(np.float32),
             bf16_to_f32(rng.integers(0, 1 << 16, size=(32, 2560), dtype=np.uint16) & 0xBFFF)]
    ok0 = all(np.array_equal(tf["mtp_pack.py:q2_0"](c), q2_0(c)) for c in cases) and \
        all(tf["mtp_rt.py:q8_0"](c) == q8_0(c) for c in cases)
    gu = rng.integers(0, 256, size=(1280, 720), dtype=np.uint8)
    dn = rng.integers(0, 256, size=(2560, 180), dtype=np.uint8)
    ok0 = ok0 and tf["mtp_rt.py:blob_of"](gu, dn) == blob_of(gu, dn, 2560, 640)
    results["T0 tool functions"] = ok0
    log(f"T0 q2_0 / q8_0 / blob_of equal to {a.tools or TOOLS}'s own (5 random / edge cases): {'PASS' if ok0 else 'FAIL'}")
    # ---- T1: a small synthetic GGUF in Unsloth's layout, written by gguf-py's GGUFWriter (an independent writer)
    import gguf
    H, FF, NE, HC, R, NQ, NK = 128, 64, 4, 4, 32, 32, 16
    shp = {"mtp.fc_embedding.weight": (H, H), "mtp.fc_hidden.weight": (H, H),
           "mtp.hyper_connection_mixer.hc_norm.weight": (HC * H,),
           "mtp.hyper_connection_mixer.input_mix_weight_down.weight": (R, HC * H),
           "mtp.hyper_connection_mixer.input_mix_weight_up.weight": (HC * H, R),
           DOWN: (NE, H, FF), GATE_UP: (NE, 2 * FF, H), "mtp.layers.0.mlp.gate.weight": (NE, H),
           "mtp.layers.0.mlp.shared_expert.down_proj.weight": (H, FF),
           "mtp.layers.0.mlp.shared_expert.gate_proj.weight": (FF, H),
           "mtp.layers.0.mlp.shared_expert.up_proj.weight": (FF, H), "mtp.layers.0.mlp.shared_expert_gate.weight": (1, H),
           "mtp.layers.0.self_attn.indexer.index_qk_proj.weight": (NQ + NK, H),
           "mtp.layers.0.self_attn.indexer.k_layernorm.weight": (16,),
           "mtp.layers.0.self_attn.indexer.q_layernorm.weight": (16,), "mtp.layers.0.self_attn.k_norm.weight": (32,),
           "mtp.layers.0.self_attn.k_proj.weight": (32, H), "mtp.layers.0.self_attn.o_proj.weight": (H, 64),
           "mtp.layers.0.self_attn.q_norm.weight": (32,), "mtp.layers.0.self_attn.q_proj.weight": (128, H),
           "mtp.layers.0.self_attn.v_proj.weight": (32, H), "mtp.pre_fc_norm_embedding.weight": (H,),
           "mtp.pre_fc_norm_hidden.weight": (HC * H,)}
    for part in ("attn_hyper_connection", "mlp_hyper_connection"):
        p = f"mtp.layers.0.{part}."
        shp.update({p + "block_inject_weight.weight": (HC, HC * H), p + "hc_norm.weight": (HC * H,),
                    p + "input_mix_weight_down.weight": (R, HC * H), p + "input_mix_weight_up.weight": (HC * H, R)})
    assert len(shp) == 31
    ck = {}
    for n, s in shp.items():
        v = rng.standard_normal(s).astype(np.float32) * (0.05 if len(s) == 1 else 0.02)
        u, _ = f32_to_bf16(v)
        ck[n] = u.reshape(s)
    man_syn = {n: {"name": n, "shape": list(s), "sha256": sha_u16(ck[n])} for n, s in shp.items()}
    # the reference rt for the synthetic checkpoint: the same writer fed straight from the checkpoint tensors
    ref_cts = ckpt_cts(lambda n: ck[n], shp)
    ref_dir = out / "t1-ref-rt"
    ref_dir.mkdir(exist_ok=True)
    for f in ref_dir.iterdir():
        f.unlink()
    write_rt(ref_cts, (H, FF, NE), ref_dir, log=lambda *x: None)
    variants = [("bf16-shared-plus1", dict()), ("bf16-standalone-plus1", dict(shared=False, vocab=64)),
                ("bf16-shared-raw-norms", dict(norms_plus1=False)), ("bf16-router-bf16", dict(router_f32=False)),
                ("bf16-he-order", dict(eh_first=False)), ("bf16-kq-order", dict(q_first=False)),
                ("q8_0-shared", dict(mat_type="Q8_0"))]
    for label, kw in variants:
        items = unsloth_layout_from_ckpt(lambda n: ck[n], {"indexer_q": NQ}, 2, H, **kw)
        path = out / f"t1-{label}.gguf"
        w = gguf.GGUFWriter(str(path), "qwen4exp")
        w.add_uint32("qwen4exp.block_count", 3)
        w.add_uint32("qwen4exp.nextn_predict_layers", 1)
        w.add_uint32("qwen4exp.embedding_length", H)
        w.add_uint32("qwen4exp.expert_count", NE)
        w.add_uint32("qwen4exp.expert_feed_forward_length", FF)
        if kw.get("shared", True):
            w.add_bool("qwen4exp.nextn_shared_target_tensors", True)
        for name, (typ, ne, data) in items.items():
            arr = np.asarray(data)
            if typ == F32:
                w.add_tensor(name, arr.view(np.float32).reshape(tuple(reversed(ne))))
            elif typ == BF16:
                w.add_tensor(name, arr.view(np.uint16).reshape(tuple(reversed(ne))), raw_dtype=gguf.GGMLQuantizationType.BF16)
            else:
                rows = tuple(reversed(ne))[:-1]
                w.add_tensor(name, arr.reshape(*rows, -1), raw_dtype=gguf.GGMLQuantizationType.Q8_0)
        w.write_header_to_file()
        w.write_kv_data_to_file()
        w.write_tensors_to_file()
        w.close()
        src = GGUF(path)
        cts, rep, dims = build(src, "auto", "auto", "auto", man_syn, data=True)
        res = write_rt(cts, dims, None, ref_dir, man_syn, None, log=lambda *x: None)
        lines = []
        ok = summarize(res, rep, log=lines.append)
        if label.startswith("q8_0"):
            # expected: the Q8_0 projections identical, BF16 tensors rounded, experts re-quantized (not identical)
            q8_same = all(d["ref"] == "identical" for s, d in res["dense"].items() if d["kind"] == "q8_0")
            f32_same = all(d["ref"] == "identical" for s, d in res["dense"].items() if d["kind"] == "f32")
            bf_diff = [s for s, d in res["dense"].items() if d["kind"] == "bf16" and d["ref"] != "identical"]
            ok = q8_same and f32_same and len(bf_diff) > 0 and res["experts"]["n_differ"] > 0
            lines.append(f"  expected for a Q8_0 source: Q8_0 projections identical {q8_same}, norms identical {f32_same}, "
                         f"BF16 tensors rounded {bf_diff}, experts re-quantized ({res['experts']['n_differ']} differ)")
        results[f"T1 {label}"] = ok
        log(f"T1 synthetic {label}: {'PASS' if ok else 'FAIL'} (eh {rep['eh_order']}, qk {rep['qk_order']}, norms "
            f"{rep['norm_default']}, shared {rep['shared']}, not used {rep['not_used']})")
        for x in lines:
            logf.write("     " + x + "\n")
        path.unlink()                                    # the test's own scratch file
    for f in ref_dir.iterdir():
        f.unlink()
    ref_dir.rmdir()
    # ---- T2: our checkpoint's BF16 tensors laid out as Unsloth's file -> must reproduce strata-v0115/mtp/rt exactly
    man = load_manifest(MANIFEST)
    ckdir = Path(a.ckpt_dir)
    man_ck = load_manifest(ckdir / "mtp-manifest.json")
    same_man = man_ck is not None and all(man_ck[n]["sha256"] == man[n]["sha256"] for n in man)
    log(f"T2 checkpoint: {ckdir} (its manifest {'=' if same_man else 'DIFFERS from'} {MANIFEST})")
    t_hash = time.time()
    bad = []
    if a.hash_ckpt:
        thr = Throttle(a.max_mbps)
        for n, t in man.items():
            h = hashlib.sha256()
            with open(ckdir / t["file"], "rb") as f:
                while True:
                    b = f.read(16 << 20)
                    if not b:
                        break
                    h.update(b)
                    thr.add(len(b))
                os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            if h.hexdigest() != t["sha256"]:
                bad.append(n)
        log(f"   the 31 raw tensors hash to the manifest: {'yes' if not bad else 'NO: ' + str(bad)} ({time.time() - t_hash:.0f} s)")
    get = lambda n: ckpt_u16(ckdir, man, n)  # noqa: E731
    shapes = {"indexer_q": 512}
    items = unsloth_layout_from_ckpt(get, shapes, 48, 2560)
    kv = {"general.architecture": "qwen4exp", "qwen4exp.block_count": 49, "qwen4exp.nextn_predict_layers": 1,
          "qwen4exp.nextn_shared_target_tensors": True}
    src = DictSrc(kv, items, label="our checkpoint in Unsloth's shared-BF16 layout (in memory)")
    exp = None if a.experts is None else range(a.experts)
    cts, rep, dims = build(src, "auto", "auto", "auto", man, data=True)
    res = write_rt(cts, dims, None, REF_RT, man, exp, Throttle(a.max_mbps), log=log)
    for t in man.values():
        drop_cache(ckdir / t["file"])
    for f in ("dense.bin", "experts.bin"):
        drop_cache(REF_RT / f)
    ok2 = summarize(res, rep, log=log) and not bad
    for n, c in cts.items():                              # what the "+1 stored" norms lose (diagnostic)
        if c.kind == "norm" and res["dense"][short_of(n)].get("source_matches_checkpoint") == "rt-equivalent":
            w_true = bf16_to_f32(np.asarray(get(n))).reshape(-1)
            w0 = bf16_to_f32(c.u16()).reshape(-1)
            dif = np.nonzero(w_true != w0)[0]
            log(f"   {short_of(n)}: {dif.size} of {w0.size} values not recoverable from f32(w)+1 (|w| <= "
                f"{float(np.abs(w_true[dif]).max()):.3g}; rt bytes identical)")
    results["T2 our checkpoint -> strata-v0115/mtp/rt"] = ok2
    log(f"T2 our checkpoint in Unsloth's layout -> {'IDENTICAL to strata-v0115/mtp/rt' if ok2 else 'DIFFERS'} "
        f"(experts checked {res['experts']['checked']} of {res['experts']['of']})")
    json.dump({"version": VERSION, "results": results, "t2": {"report": rep, "result": res}},
              open(out / "selftest.json", "w"), indent=1, default=str)
    allok = all(results.values())
    log("SELFTEST " + ("ALL PASS" if allok else "FAIL: " + ", ".join(k for k, v in results.items() if not v)))
    return 0 if allok else 1


def ckpt_cts(get, shapes):
    """CTs straight from checkpoint tensors (mtp_pack's input): the reference path for the synthetic test."""
    out = OrderedDict()
    for n in sorted(shapes):
        s = shapes[n]
        if n in (GATE_UP, DOWN):
            c = CT(n, s, "experts", [n], "checkpoint")

            def expert(e, n=n):
                u = np.asarray(get(n)[e])
                return bf16_to_f32(u), u, True
            c.expert, c.exact = expert, True
        elif len(s) == 1:
            c = CT(n, s, "norm", [n], "checkpoint")
            u = np.asarray(get(n))
            c.rt_f32 = (bf16_to_f32(u).astype(np.float32) + 1.0).astype(np.float32)
            c.u16, c.exact = (lambda u=u: u), True
        else:
            c = CT(n, s, "mat", [n], "checkpoint")
            c.u16 = (lambda n=n: np.asarray(get(n)))
            c.f32 = (lambda n=n: bf16_to_f32(np.asarray(get(n))))
            c.exact = True
        out[n] = c
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p, data=True):
        p.add_argument("gguf")
        p.add_argument("--manifest", default=str(MANIFEST), help="the pinned checkpoint's manifest (sha256 per tensor); '' = none")
        p.add_argument("--eh-order", default="auto", choices=["auto", "eh", "he"])
        p.add_argument("--qk-order", default="auto", choices=["auto", "qk", "kq"])
        p.add_argument("--norms", default="auto", choices=["auto", "plus1", "raw"])
        if data:
            p.add_argument("--ref-rt", default=str(REF_RT), help="the rt to compare with ('' = none)")
            p.add_argument("--max-mbps", type=float, default=400, help="read-rate cap for the expert pass (0 = none)")
    p = sub.add_parser("inspect")
    common(p, data=False)
    p = sub.add_parser("verify")
    common(p)
    p.add_argument("--experts", type=int, help="check only the first N experts (default all)")
    p.add_argument("--report", help="write the full comparison as JSON here")
    p = sub.add_parser("convert")
    common(p)
    p.add_argument("--out", required=True)
    p.add_argument("--draft-vocab", help="draft_vocab.bin to copy (default: the reference rt's, if the vocab is 248,320)")
    p = sub.add_parser("selftest")
    p.add_argument("--out", required=True)
    p.add_argument("--ckpt-dir", default=str(CKPT_DIR))
    p.add_argument("--experts", type=int, help="T2: only the first N experts (default all 512)")
    p.add_argument("--max-mbps", type=float, default=400)
    p.add_argument("--hash-ckpt", action="store_true", help="T2: also hash the raw checkpoint tensors (5.2 GB read)")
    p.add_argument("--tools", help="T0: the tree's tools/ with mtp_pack.py + mtp_rt.py (default strata-v0115/tools; on "
                                   "Qwen4 day one the release's, to see that its rt arithmetic is still these functions)")
    a = ap.parse_args()
    for k in ("manifest", "ref_rt"):
        if getattr(a, k, None) == "":
            setattr(a, k, None)
    if a.cmd == "inspect":
        return cmd_inspect(a)
    if a.cmd == "verify":
        return cmd_verify(a)
    if a.cmd == "convert":
        return cmd_convert(a)
    if a.cmd == "selftest":
        return cmd_selftest(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
