#!/usr/bin/env python3
"""membw_gpu.py — round 8 A.1: the RTX 5080's achievable device-memory bandwidth (the roofline's ceiling): a 2 GiB
device-to-device copy (reads + writes counted) and a read-only reduction, CUDA events, median of 20. No model server."""
import torch
x = torch.empty(2 ** 29, dtype=torch.float32, device="cuda"); y = torch.empty_like(x); x.uniform_()
ev = [torch.cuda.Event(enable_timing=True) for _ in range(2)]
def t(f, reps=20):
    ts = []
    for _ in range(reps + 2):
        ev[0].record(); f(); ev[1].record(); torch.cuda.synchronize(); ts.append(ev[0].elapsed_time(ev[1]))
    return sorted(ts[2:])[reps // 2]
b = x.numel() * 4
c = t(lambda: y.copy_(x)); r = t(lambda: x.sum())
print(f"device copy {2 * b / c / 1e6:.0f} GB/s (read+write), read-only sum {b / r / 1e6:.0f} GB/s; {torch.cuda.get_device_name()}")
