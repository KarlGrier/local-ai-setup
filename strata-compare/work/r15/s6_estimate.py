#!/usr/bin/env python3
"""s6_estimate.py LABEL:EXPERTS_GIB:GPU_GIB:SERVED_TPS ... — round 15 step 6: an ESTIMATE (not a measurement) of the decode
speed with every expert in RAM, from step 3's measured split (the CLI --stats of the full-set placement, warm):
  measured round = GPU ~(round - pool) + the CPU pool (its RAM experts + the file tier's reading)
  all in RAM     = the round - the file tier's reading time + the same bytes read at the pool's own measured RAM rate
                   ("pool multi ... GB/s over the rows phases") - i.e. the SSD part replaced by RAM reads, nothing else
tokens per round, the GPU's share and the pool's RAM part are kept as measured; the served estimate scales the served
decode by the same factor. Also: the RAM all-in-RAM would need (experts - what the GPUs hold + the rest of the process
and your 6 GiB floor + ~5 GiB for the desktop and services)."""
import re
import sys
from pathlib import Path

PF = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
print("| placement | measured round (CLI) ms | of it: GPU ~ / CPU RAM experts / SSD reading | SSD MB per round | pool RAM rate GB/s | "
      "**estimated round, all in RAM** ms | CLI tok/s measured → **estimated** | served tok/s measured → **estimated** | RAM needed (GiB) |")
print("|---|---|---|---|---|---|---|---|---|")
for arg in sys.argv[1:]:
    label, experts, gpu, served = arg.split(":")
    t = (PF / f"{label}-split-warm.out").read_text(errors="replace")
    tps = float(re.search(r"^decode\s+\d+ tokens in [\d.]+ ms\s+->\s+([\d.]+) tok/s", t, re.M)[1])
    tpr = float(re.search(r"([\d.]+) tokens per round", t)[1])
    pool = float(re.search(r"verify window\s+wait for rings [\d.]+\s+pool ([\d.]+)", t)[1])
    m = re.search(r"\(([\d.]+) MB/round, ([\d.]+) ms/round of reading", t)
    fmb, fms = float(m[1]), float(m[2])
    rate = float(re.search(r"([\d.]+) GB/s over the rows phases", t)[1])
    rnd = 1000 / tps * tpr
    gpu_ms = rnd - pool
    ram_ms = pool - fms
    est = rnd - fms + fmb / 1e3 / rate * 1e3
    f = rnd / est
    need = float(experts) - float(gpu) + 7.5 + 6 + 5      # + the engine's own (~7.5 GiB at 2 GiB chat cache) + floor + desktop
    print(f"| {label} | {rnd:.1f} | {gpu_ms:.0f} / {ram_ms:.0f} / {fms:.0f} | {fmb:.0f} | {rate:.1f} | **{est:.1f}** | "
          f"{tps:.1f} → **{tps * f:.1f}** | {float(served):.1f} → **{float(served) * f:.1f}** | {need:.0f} |")
print("\nESTIMATE, not measured: the SSD part of the round replaced by RAM reads at the pool's measured rate; the CPU's RAM "
      "bandwidth is shared, so the real number would sit somewhat lower.")
