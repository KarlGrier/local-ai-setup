#!/usr/bin/env python3
"""flashqla_bench.py DIR [--reps N] — round 8 A.5: QwenLM FlashQLA's chunked gated-delta-rule forward on the SAME fixture
Strata's prompt recurrence was captured on (STRATA_GDN_CAPTURE, engine-r8o), vs the engine's own FP32 result and an
FP64 sequential reference computed here (the engine's recurrence, token by token, in double).

Strata's layout (h row = q 16x128 | k 16x128 | v 48x128 after conv + L2; gate = log decay; state[k][head][v]) is
converted to FlashQLA's ([1, T, H, 128] q/k/v, g, beta [1, T, 48], initial state [1, 48, K, V]).  FlashQLA accepts only
BF16/FP16 q/k/v, so they are cast to BF16 - LOWER precision than the engine's FP32 inputs (reported, not adoptable as
is).  Output o = scale * S^T q is passed through the engine's output norm (the same formula, FP32) and compared with the
captured y; the final state with the captured state1.  Timing (CUDA events): FlashQLA forward alone, and forward + the
conversions both ways (slice/cast in, permute/cast out + the norm) = what replacing gdn_recurrence would cost."""
import argparse
import math
import os
import sys
import time

import numpy as np
import torch

S, HK, HV, C = 128, 16, 48, 10240


def load(d, name, shape):
    return torch.from_numpy(np.fromfile(os.path.join(d, name), dtype=np.float32).reshape(shape))


def ref_fp64(h, gate, beta, s0):
    """the engine's recurrence (gdn_rec_cols_kernel) in float64, token by token, all heads at once:
    kv = S^T k; delta = (v - g kv) beta; S = g S + k delta^T; o = S^T q / sqrt(S)"""
    T = h.shape[0]
    q = h[:, :HK * S].view(T, HK, S).double()
    k = h[:, HK * S:2 * HK * S].view(T, HK, S).double()
    v = h[:, 2 * HK * S:].view(T, HV, S).double()
    grp = HV // HK
    st = s0.double().permute(1, 0, 2).contiguous()          # [HV, K, V]
    o = torch.empty(T, HV, S, dtype=torch.float64, device=h.device)
    g = torch.exp(gate.double())                              # [T, HV]
    b = beta.double()
    for t in range(T):
        # the engine maps value head `head` to q/k head `head % HK` (kernels.cu: qh = head % HK)
        qt = q[t][torch.arange(HV, device=h.device) % HK]
        kt = k[t][torch.arange(HV, device=h.device) % HK]
        kv = torch.einsum("hkv,hk->hv", st, kt)
        delta = (v[t] - g[t][:, None] * kv) * b[t][:, None]
        st = g[t][:, None, None] * st + kt[:, :, None] * delta[:, None, :]
        o[t] = torch.einsum("hkv,hk->hv", st, qt) / math.sqrt(S)
    return o, st.permute(1, 0, 2).contiguous()


def chunked_fp(h, gate, beta, s0, C=64, dtype=torch.float32):
    """the engine's recurrence in CHUNKED (WY) form with real FP32 GEMMs (TF32 off): S_t = a_t (I - b_t k_t k_t^T) S_{t-1}
    + b_t k_t v_t^T, o_t = S_t^T q_t / sqrt(S), a_t = exp(gate_t); within a chunk g = cumulative log decay,
    A = tril(diag(b) (K K^T * exp(g_i - g_j)), -1), T = (I + A)^-1, W = T diag(b) (K * exp(g)), U = T diag(b) V,
    V' = U - W S0, O = (Q * exp(g)) S0 + tril(Q K^T * exp(g_i - g_j)) V', S_C = exp(g_C) S0 + (K * exp(g_C - g))^T V'.
    The same mathematics as the token loop, summed in another order (rounding-level), all in `dtype`."""
    T = h.shape[0]
    dev = h.device
    idx = torch.arange(HV, device=dev) % HK
    q = h[:, :HK * S].view(T, HK, S)[:, idx].to(dtype).permute(1, 0, 2)        # [HV, T, K]
    k = h[:, HK * S:2 * HK * S].view(T, HK, S)[:, idx].to(dtype).permute(1, 0, 2)
    v = h[:, 2 * HK * S:].view(T, HV, S).to(dtype).permute(1, 0, 2)              # [HV, T, V]
    g = gate.to(dtype).t()                                                        # [HV, T] log decay
    b = beta.to(dtype).t()
    st = s0.to(dtype).permute(1, 0, 2).contiguous()                               # [HV, K, V]
    out = torch.empty(HV, T, S, dtype=dtype, device=dev)
    eye = torch.eye(C, dtype=dtype, device=dev)
    tril1 = torch.tril(torch.ones(C, C, dtype=torch.bool, device=dev), -1)
    tril0 = torch.tril(torch.ones(C, C, dtype=torch.bool, device=dev), 0)
    for c0 in range(0, T, C):
        c1 = min(T, c0 + C); n = c1 - c0
        qc, kc, vc = q[:, c0:c1], k[:, c0:c1], v[:, c0:c1]
        gc = torch.cumsum(g[:, c0:c1], dim=1)                                    # [HV, n]
        bc = b[:, c0:c1]
        dec = torch.exp(gc[:, :, None] - gc[:, None, :])                          # [HV, n, n] exp(g_i - g_j)
        kk = torch.einsum("hik,hjk->hij", kc, kc)
        A = torch.where(tril1[:n, :n], bc[:, :, None] * kk * dec, torch.zeros((), dtype=dtype, device=dev))
        Tm = torch.linalg.solve_triangular(eye[:n, :n] + A, eye[:n, :n].expand(HV, n, n), upper=False)
        W = Tm @ (bc[:, :, None] * kc * torch.exp(gc)[:, :, None])
        U = Tm @ (bc[:, :, None] * vc)
        Vp = U - W @ st
        qk = torch.einsum("hik,hjk->hij", qc, kc)
        att = torch.where(tril0[:n, :n], qk * dec, torch.zeros((), dtype=dtype, device=dev))
        out[:, c0:c1] = ((qc * torch.exp(gc)[:, :, None]) @ st + att @ Vp) / math.sqrt(S)
        gC = gc[:, -1]
        st = torch.exp(gC)[:, None, None] * st + (kc * torch.exp(gC[:, None] - gc)[:, :, None]).transpose(1, 2) @ Vp
    return out.permute(1, 0, 2), st.permute(1, 0, 2).contiguous()


def out_norm(o, gamma, z, eps=1e-6):
    """gdn_out_norm_kernel: v = oc * rsqrt(mean(oc^2) + eps) * gamma * sigmoid(z), per (token, head)"""
    ms = (o.float() ** 2).mean(-1, keepdim=True)
    return o.float() * torch.rsqrt(ms + eps) * gamma * torch.sigmoid(z)


def err(a, b):
    d = (a.double() - b.double()).abs()
    return f"max abs {d.max().item():.3e}, rms {d.pow(2).mean().sqrt().item():.3e}, rel rms {(d.pow(2).mean().sqrt() / b.double().pow(2).mean().sqrt()).item():.3e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--no-ref", action="store_true")
    a = ap.parse_args()
    T = int(open(os.path.join(a.dir, "meta.txt")).read().split()[0].split("=")[1])
    dev = "cuda"
    h = load(a.dir, "h.f32", (T, C)).to(dev)
    gate = load(a.dir, "gate.f32", (T, HV)).to(dev)
    beta = load(a.dir, "beta.f32", (T, HV)).to(dev)
    z = load(a.dir, "z.f32", (T, HV, S)).to(dev)
    gamma = load(a.dir, "gamma.f32", (S,)).to(dev)
    s0 = load(a.dir, "state0.f32", (S, HV, S)).to(dev)
    s1 = load(a.dir, "state1.f32", (S, HV, S)).to(dev)
    y = load(a.dir, "y.f32", (T, HV, S)).to(dev)
    print(f"fixture {a.dir}: T={T}, torch {torch.__version__}, device {torch.cuda.get_device_name()}, FlashQLA auto_cp={os.environ.get('FQLA_AUTO_CP', '1')}", flush=True)

    y64 = st64 = None
    if not a.no_ref:
        t0 = time.time()
        o64, st64 = ref_fp64(h, gate, beta, s0)
        y64 = out_norm(o64, gamma, z)
        print(f"FP64 sequential reference ({time.time() - t0:.1f} s):")
        print("  engine FP32   vs FP64: y " + err(y, y64) + " | final state " + err(s1, st64))
    # the FP32 chunked (WY) form in plain PyTorch, TF32 off: its accuracy vs FP64 and its time = a realistic bound for
    # a chunked kernel that keeps today's FP32 precision (FlashQLA's BF16 inputs would not)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    oc32, sc32 = chunked_fp(h, gate, beta, s0)
    yc32 = out_norm(oc32, gamma, z)
    print("PyTorch FP32 chunked (C=64) vs the engine: y " + err(yc32, y) + " | final state " + err(sc32, s1))
    if not a.no_ref:
        print("  PyTorch FP32 chunked vs FP64: y " + err(yc32, y64) + " | final state " + err(sc32, st64))
        oc64, sc64 = chunked_fp(h, gate, beta, s0, dtype=torch.float64)
        print("  (check) FP64 chunked vs FP64 sequential: y " + err(out_norm(oc64, gamma, z), y64) + " | state " + err(sc64, st64))
    tt = []
    for r in range(5):
        e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        torch.cuda.synchronize(); e0.record(); oc32, sc32 = chunked_fp(h, gate, beta, s0); out_norm(oc32, gamma, z); e1.record()
        torch.cuda.synchronize(); tt.append(e0.elapsed_time(e1))
    tt.sort()
    print(f"PyTorch FP32 chunked incl. layout + norm: median {tt[len(tt) // 2]:.2f} ms (unfused eager ops; a fused kernel would be faster)")

    try:
        from flash_qla import chunk_gated_delta_rule
        import flash_qla.ops.gated_delta_rule.chunk as _fqc
        if not hasattr(_fqc, "aggregate_card_state"):
            # FlashQLA 0.1.3 on sm120: its own comment says aggregate_card_state is None there (only inter+intra CP needs it),
            # but the module never defines it and cp_preprocess_fwd imports it unconditionally -> ImportError. Supply None.
            _fqc.aggregate_card_state = None
        AUTO_CP = os.environ.get("FQLA_AUTO_CP", "1") == "1"
        idx = torch.arange(HV, device=dev) % HK

        def convert_in():
            q = h[:, :HK * S].view(1, T, HK, S)
            k = h[:, HK * S:2 * HK * S].view(1, T, HK, S)
            v = h[:, 2 * HK * S:].view(1, T, HV, S)
            # FlashQLA groups value heads as head // (HV/HK); the engine uses head % HK -> reorder the value heads so that
            # FlashQLA's grouping sees the engine's pairing (a permutation of heads: exact)
            perm = torch.cat([torch.nonzero(idx == j).flatten() for j in range(HK)])     # value heads grouped by q/k head
            return (q.to(torch.bfloat16), k.to(torch.bfloat16), v[:, :, perm].to(torch.bfloat16).contiguous(),
                    gate[:, perm].view(1, T, HV).contiguous(), beta[:, perm].view(1, T, HV).contiguous(),
                    s0.permute(1, 0, 2)[perm].unsqueeze(0).contiguous(), perm)

        def run(inp):
            q, k, v, g, b, h0, perm = inp
            # auto_cp=False: FlashQLA 0.1.3's automatic intra-card context parallelism imports aggregate_card_state, which
            # it does not provide on sm120 (ImportError on this RTX 5080) - the plain chunked path instead
            o, fs = chunk_gated_delta_rule(q=q, k=k, v=v, g=g, beta=b, scale=1.0 / math.sqrt(S), initial_state=h0,
                                           output_final_state=True, auto_cp=AUTO_CP)
            return o, fs

        def convert_out(o, fs, perm):
            inv = torch.empty_like(perm); inv[perm] = torch.arange(HV, device=dev)
            oo = o[0][:, inv].float()                      # [T, HV, S] back in the engine's head order
            yy = out_norm(oo, gamma, z)
            st = fs[0][inv].permute(1, 0, 2).float()        # [K, HV, V]
            return oo, yy, st

        t0 = time.time()
        inp = convert_in()
        o, fs = run(inp)        # first call: TileLang JIT
        torch.cuda.synchronize()
        print(f"first call (JIT compile + run) {time.time() - t0:.1f} s", flush=True)
        oo, yy, st = convert_out(o, fs, inp[6])
        print("FlashQLA (BF16 q/k/v) vs the engine (FP32):  y " + err(yy, y) + " | final state " + err(st, s1))

        if y64 is not None:
            print("  FlashQLA BF16 vs FP64: y " + err(yy, y64) + " | final state " + err(st, st64))

        ev = [torch.cuda.Event(enable_timing=True) for _ in range(4)]
        fwd, full = [], []
        for r in range(a.reps):
            torch.cuda.synchronize()
            ev[0].record()
            inp = convert_in()
            ev[1].record()
            o, fs = run(inp)
            ev[2].record()
            convert_out(o, fs, inp[6])
            ev[3].record()
            torch.cuda.synchronize()
            fwd.append(ev[1].elapsed_time(ev[2]))
            full.append(ev[0].elapsed_time(ev[3]))
        fwd.sort(); full.sort()
        print(f"FlashQLA forward alone: min {fwd[0]:.3f} median {fwd[len(fwd) // 2]:.3f} ms; with the conversions in and "
              f"out + the output norm: min {full[0]:.3f} median {full[len(full) // 2]:.3f} ms ({a.reps} reps)")
    except Exception as e:  # noqa: BLE001
        print(f"FlashQLA FAILED on this GPU: {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
