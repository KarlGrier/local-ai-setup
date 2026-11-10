#!/usr/bin/env python3
"""adapter_train.py [--epochs 4] [--rank 8] [--device cuda] — round 12 A1 adapter pilot (offline, no model server loaded):
a rank-r adapter in front of the draft head, h' = h + B (A h) (A: r x 2560, B: 2560 x r, B starts at 0: the adapter starts
as the identity), everything else frozen. Trained on the FIT tasks' hidden vectors (A1R: the vector entering the draft
head at every MTP-drafted position) against the target's distribution after the full sampler chain (cross-entropy over
the draft vocabulary; target mass outside the vocabulary cannot be matched and is dropped). Evaluated on the HELD-OUT
tasks (whole tasks, the A1 split) through the emulated quantized draft path (q8_1 of h', the dequantized Q6_K subset
rows: matches the engine's raw logits to 0.007), then the request's sampler chain (top-k 20 / top-p 0.95 / min-p 0.05,
T 1): overlap sum min(p, q') per draft step, before and after. Writes results/r12/adapter-eval.json."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "work/r12"))
from adapter_head import q8_1  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=4)
ap.add_argument("--rank", type=int, default=8)
ap.add_argument("--lr", type=float, default=2e-3)
ap.add_argument("--batch", type=int, default=512)
ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--wd", type=float, default=0.0)
ap.add_argument("--tag", default="")
a = ap.parse_args()
N = 2560
dev = torch.device(a.device)
z = np.load(WS / "results/r12/adapter-A1R.npz")
H = np.memmap(WS / "results/r12/oracle/A1R.txt.h", dtype=np.float32, mode="r").reshape(-1, N)
dv = np.fromfile(WS / "strata-v0115/mtp/rt/draft_vocab.bin", dtype=np.int32)
sub = -np.ones(248320, np.int64); sub[dv] = np.arange(len(dv))
W = torch.from_numpy(np.load(WS / "tmp/r12/dhead.npy")).to(dev)          # (V, N) fp32
V = W.shape[0]
tasks = list(z["tasks"])
fit_t = set(range(0, len(tasks), 2))                                         # the A1 split: sorted tasks, every other one
task = z["task"].astype(int)
isfit = np.array([t in fit_t for t in task])
idx_f, idx_h = np.where(isfit)[0], np.where(~isfit)[0]
if a.limit:
    idx_f, idx_h = idx_f[:a.limit], idx_h[:a.limit]
P_ids, P_pr = z["P_ids"], z["P_pr"]


def targets(ix):
    """(n, 20) subset indices (or 0 with weight 0) and probabilities, renormalized over the draft vocabulary"""
    ids = P_ids[ix]; pr = P_pr[ix].copy()
    s = np.where(ids >= 0, sub[np.maximum(ids, 0)], -1)
    pr[s < 0] = 0
    tot = pr.sum(1, keepdims=True); pr = pr / np.maximum(tot, 1e-12)
    return torch.from_numpy(np.maximum(s, 0)).to(dev), torch.from_numpy(pr).to(dev)


def hid(ix):
    return torch.from_numpy(np.asarray(H[z["hrec"][ix]])).to(dev)


r = a.rank
A = torch.nn.Parameter(torch.randn(r, N, device=dev) * (1.0 / N ** 0.5))
B = torch.nn.Parameter(torch.zeros(N, r, device=dev))
opt = torch.optim.AdamW([A, B], lr=a.lr, weight_decay=a.wd)
t0 = time.time()
for ep in range(a.epochs):
    perm = np.random.default_rng(ep).permutation(idx_f)
    tot = 0.0
    for k in range(0, len(perm), a.batch):
        ix = np.sort(perm[k:k + a.batch])
        h = hid(ix)
        h2 = h + (h @ A.T) @ B.T
        lg = h2 @ W.T                                                         # (b, V)
        ls = torch.log_softmax(lg, dim=1)
        ti, tp = targets(ix)
        loss = -(tp * ls.gather(1, ti)).sum(1).mean()
        opt.zero_grad(); loss.backward(); opt.step()
        tot += loss.item() * len(ix)
    print(f"epoch {ep + 1}: fit cross-entropy {tot / len(idx_f):.4f} ({time.time() - t0:.0f} s)", flush=True)


def chain(lg):
    """the request's chain (top-k 20 on the raw logits, top-p 0.95 on their softmax, min-p 0.05, temperature 1) ->
    (n, 20) subset indices and probabilities"""
    z20, i20 = torch.topk(lg, 20, dim=1)
    e = torch.softmax(z20, dim=1)
    cum = torch.cumsum(e, 1)
    cut_p = torch.argmax((cum >= 0.95).int(), dim=1) + 1
    th = z20[:, :1] + np.log(0.05)
    col = torch.arange(20, device=dev)[None, :]
    below = (z20 < th) & (col < cut_p[:, None])
    cut = torch.where(below.any(1), torch.argmax(below.int(), dim=1), cut_p).clamp(min=1)
    mask = col < cut[:, None]
    q = torch.softmax(torch.where(mask, z20, torch.full_like(z20, -1e30)), dim=1) * mask
    return i20, q


def overlap(ix, adapt):
    res = []
    with torch.no_grad():
        for k in range(0, len(ix), 1024):
            b = ix[k:k + 1024]
            h = hid(b)
            if adapt:
                h = h + (h @ A.T) @ B.T
            hq = torch.from_numpy(q8_1(h.cpu().numpy())).to(dev)
            i20, q = chain(hq @ W.T)
            ids = P_ids[b]; pr = P_pr[b]
            ts = torch.from_numpy(np.where(ids >= 0, sub[np.maximum(ids, 0)], -2)).to(dev)
            tp = torch.from_numpy(pr).to(dev)
            m = (i20[:, :, None] == ts[:, None, :]).float()                  # (n, 20 q, 20 p)
            pq = (m * tp[:, None, :]).sum(2)                                 # p at each q entry
            res.append(torch.minimum(pq, q).sum(1).cpu().numpy())
    return np.concatenate(res)


out = {}
for name, ix in (("fit", idx_f), ("held-out", idx_h)):
    o0, o1 = overlap(ix, False), overlap(ix, True)
    js = z["j"][ix]; ldr = z["ldr"][ix]
    row = {}
    for s in range(3):
        sel = (js == s) & ldr
        row[f"step{s + 1}"] = [float(o0[sel].mean()), float(o1[sel].mean())]
    row["all LDR"] = [float(o0[ldr].mean()), float(o1[ldr].mean())]
    out[name] = row
    print(f"{name}: overlap before -> after (LDR): " + ", ".join(f"{k} {v[0]:.4f} -> {v[1]:.4f} ({100 * (v[1] - v[0]):+.2f} points)" for k, v in row.items()), flush=True)
json.dump({"rank": r, "epochs": a.epochs, "lr": a.lr, "wd": a.wd, **out}, open(WS / f"results/r12/adapter-eval{a.tag}.json", "w"), indent=1)
torch.save({"A": A.detach().cpu(), "B": B.detach().cpu()}, WS / "tmp/r12/adapter.pt")
