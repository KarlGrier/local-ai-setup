#!/usr/bin/env python3
"""csf.py - r21 item 7: NVFP4-CSF block scales (nvidia/Qwen3.8-Flash-Next-FP4-Local, "weight_scale_encoding": "csf")
<-> standard ModelOpt NVFP4 E4M3 block scales.

The codec, `byte-window4-fixed-stream-u24-exceptions/1` (vLLM PR #60646's decoder, the same semantics as FlashInfer's
b12x nvfp4_csf.py codec 0):
  * `<name>.nvfp4_csf_fixed` (uint8, [rows // 16, 16 * (1 + cols // 2)]): per 16-row slab, one base byte per row
    (0..240), then the 16 rows' 4-bit codes, cols // 2 bytes per row, low nibble first.  A scale byte is base + code.
  * `<name>.nvfp4_csf_exceptions` (uint32, sorted): low 24 bits = row * cols + col, high 8 bits = the scale byte there.

decode() follows the reference decoder exactly.  encode() is ours: it rebuilds the two streams from decoded scales by
reusing the checkpoint's own row bases (or choosing them) and storing every byte outside [base, base + 15] as an
exception; with the checkpoint's bases and its nibble at exception positions it must give back the stored bytes.
"""
import numpy as np


def decode(fixed: np.ndarray, exceptions: np.ndarray) -> np.ndarray:
    """-> uint8 [rows, cols] (the E4M3 bit patterns)."""
    if fixed.dtype != np.uint8 or fixed.ndim != 2 or fixed.shape[1] % 16:
        raise ValueError(f"CSF fixed stream {fixed.dtype} {fixed.shape}")
    rows = fixed.shape[0] * 16
    cols = (fixed.shape[1] // 16 - 1) * 2
    bases = fixed[:, :16].reshape(rows, 1).astype(np.int16)
    if (bases > 240).any():
        raise ValueError("CSF row bases must be in 0..240")
    packed = fixed[:, 16:].reshape(rows, cols // 2)
    codes = np.stack((packed & 0xF, packed >> 4), axis=-1).reshape(rows, cols).astype(np.int16)
    out = (bases + codes).reshape(-1)
    words = np.asarray(exceptions).reshape(-1).astype(np.uint32).astype(np.int64)
    pos = words & 0xFFFFFF
    if pos.size and (int(pos.max()) >= rows * cols or (np.diff(pos) <= 0).any()):
        raise ValueError("CSF exceptions out of range or not strictly sorted")
    out[pos] = (words >> 24).astype(np.int16)
    return out.astype(np.uint8).reshape(rows, cols)


def encode(scales: np.ndarray, bases: np.ndarray | None = None, exc_code: np.ndarray | None = None):
    """uint8 [rows, cols] -> (fixed, exceptions).  bases: one byte per row (default: the row's minimum, capped at
    240); exc_code: the nibble stored where an exception overrides the byte (default 0)."""
    rows, cols = scales.shape
    s = scales.astype(np.int16)
    if bases is None:
        bases = np.minimum(s.min(axis=1), 240)
    b = bases.astype(np.int16).reshape(rows, 1)
    code = s - b
    inside = (code >= 0) & (code <= 15)
    nib = np.where(inside, code, 0 if exc_code is None else exc_code).astype(np.uint8)
    packed = (nib[:, 0::2] | (nib[:, 1::2] << 4)).astype(np.uint8)
    fixed = np.concatenate((b.astype(np.uint8).reshape(rows // 16, 16), packed.reshape(rows // 16, -1)), axis=1)
    flat = np.flatnonzero(~inside.reshape(-1))
    words = (flat.astype(np.uint32) | (scales.reshape(-1)[flat].astype(np.uint32) << 24)).astype(np.uint32)
    return fixed, words


def checkpoint_round_trip(fixed: np.ndarray, exceptions: np.ndarray) -> dict:
    """Decode the checkpoint's streams, re-encode with its own row bases and its nibbles at the exception positions,
    and compare byte for byte; also decode -> encode (our base rule) -> decode."""
    sc = decode(fixed, exceptions)
    rows, cols = sc.shape
    bases = fixed[:, :16].reshape(rows)
    packed = fixed[:, 16:].reshape(rows, cols // 2)
    nib = np.stack((packed & 0xF, packed >> 4), axis=-1).reshape(rows, cols)
    f2, e2 = encode(sc, bases=bases, exc_code=nib)
    same_streams = np.array_equal(f2, fixed) and np.array_equal(e2, np.asarray(exceptions).reshape(-1).astype(np.uint32))
    f3, e3 = encode(sc)
    same_scales = np.array_equal(decode(f3, e3), sc)
    e4m3_nan = int(((sc & 0x7F) == 0x7F).sum())
    return {"streams_identical": bool(same_streams), "scales_identical_after_own_encode": bool(same_scales),
            "rows": rows, "cols": cols, "exceptions": int(np.asarray(exceptions).size), "e4m3_nan": e4m3_nan,
            "sign_bit_set": int((sc >> 7).sum())}


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    for rows, cols in ((128, 64), (2560, 160), (1280, 40)):
        sc = rng.integers(40, 60, size=(rows, cols)).astype(np.uint8)
        sc[rng.random((rows, cols)) < 0.01] = rng.integers(0, 127, size=int((rng.random((rows, cols)) < 0.01).sum()) or 1)[:1]
        f, e = encode(sc)
        assert np.array_equal(decode(f, e), sc), (rows, cols)
        r = checkpoint_round_trip(f, e)
        assert r["streams_identical"] and r["scales_identical_after_own_encode"], r
    print("csf.py self-test: encode/decode round trips exact on synthetic matrices")
