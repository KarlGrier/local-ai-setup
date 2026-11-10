#!/usr/bin/env python3
"""adapter_head.py — round 12 A1 adapter pilot, step 2: the draft head as the engine has it - the main head's
(output.weight, Q6_K [2560, 248320]) rows of the 40,525 draft-vocabulary ids (strata-v0115/mtp/rt/draft_vocab.bin, the
order of the engine's subset), dequantized with gguf-py (tmp/r12/dhead.npy, fp32 40525 x 2560); and a check of the
emulated quantized path - the hidden vector (fp32) -> q8_1 blocks of 32 (scale amax / 127, round half to even, as the
CUDA quantizer) -> the dequantized rows - against the raw logits the oracle recorded (top 64) on 2,000 positions."""
import glob
import sys
from pathlib import Path

import numpy as np

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "strata-v0115/third_party/llama.cpp/gguf-py"))
import gguf  # noqa: E402
from gguf.quants import dequantize  # noqa: E402

N = 2560
dv = np.fromfile(WS / "strata-v0115/mtp/rt/draft_vocab.bin", dtype=np.int32)
out = WS / "tmp/r12/dhead.npy"
if not out.exists():
    r = gguf.GGUFReader(sorted(glob.glob(str(WS / "models/ISTA-GSQ-RCO/IQ3_S/*00001-of-00002.gguf")))[0])
    t = next(t for t in r.tensors if t.name == "output.weight")
    rows = np.asarray(t.data)[dv]                       # raw Q6_K bytes of the subset's rows
    W = dequantize(rows, t.tensor_type).astype(np.float32).reshape(len(dv), N)
    np.save(out, W)
W = np.load(out, mmap_mode="r")
print(f"draft head: {W.shape}, from {out}")


def q8_1(x):
    """x: (..., 2560) -> the dequantized q8_1 values (blocks of 32)."""
    b = x.reshape(*x.shape[:-1], N // 32, 32)
    amax = np.abs(b).max(-1, keepdims=True)
    d = (amax / 127.0).astype(np.float32)
    q = np.where(d > 0, np.rint(b / np.where(d > 0, d, 1)), 0)
    return (q * d).reshape(x.shape).astype(np.float32)


if __name__ == "__main__":
    z = np.load(WS / "results/r12/adapter-A1R.npz")
    H = np.memmap(WS / "results/r12/oracle/A1R.txt.h", dtype=np.float32, mode="r").reshape(-1, N)
    sub = np.arange(0, len(z["hrec"]), max(1, len(z["hrec"]) // 2000))[:2000]
    h = np.asarray(H[z["hrec"][sub]])
    Wf = np.asarray(W)
    idx = {int(t): i for i, t in enumerate(dv)}
    lg = q8_1(h) @ Wf.T                                  # (n, 40525)
    err = []
    top_agree = 0
    for k, i in enumerate(sub):
        ids = z["L_ids"][i]; rec = z["L_lg"][i]
        cols = [idx[int(t)] for t in ids if t >= 0]
        e = lg[k, cols]
        err.append(np.abs(e - rec[:len(cols)]).max())
        top_agree += int(np.argmax(lg[k]) == idx[int(ids[0])])
    print(f"emulated quantized head vs the recorded raw logits (top 64, {len(sub)} positions): max |diff| median "
          f"{np.median(err):.4f}, 99th pct {np.percentile(err, 99):.4f}, max {max(err):.4f}; top-1 agrees {top_agree}/{len(sub)}")
