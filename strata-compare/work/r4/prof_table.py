"""Speculation profile table from logs/r4/prof-LABEL-T.out (`strata generate --stats`, sampled):
decode tok/s, tokens per verify window, acceptance, ms per window (GPU wait / CPU pool / MTP), CPU experts per layer,
MB of expert weights the CPU pool streams from RAM per token (= GB/s over the rows phases x their ms / tokens per
window), and MB copied over PCIe per token by the adaptive tier (swaps x mean blob 2.045 MB / tokens).
    prof_table.py T LABEL[,LABEL...]"""
import re, sys
T, labels = sys.argv[1], sys.argv[2].split(",")
print("| config | decode tok/s | tokens/window | acceptance | ms/window: GPU wait / CPU pool / MTP | CPU experts/layer (distinct) | RAM MB streamed per token | PCIe MB/token (tier swaps) | VRAM hit rate |")
print("|---|---|---|---|---|---|---|---|---|")
for L in labels:
    s = open(f"/home/USER/ai-speed-testing/strata-compare/logs/r4/prof-{L}-{T}.out").read()
    g = lambda p: re.search(p, s)
    sp = g(r"speculation\s+(\d+) rounds of \d+, drafts accepted (\d+) of (\d+) \(([\d.]+)\), ([\d.]+) tokens per round")
    vw = g(r"wait for rings ([\d.]+)\s+pool ([\d.]+)\s+host ([\d.]+)\s+commit ([\d.]+) ms/round; CPU experts ([\d.]+) distinct")
    pm = g(r"gate/up ([\d.]+)\s+quantize [\d.]+\s+down ([\d.]+) ms/round; ([\d.]+) GB/s")
    ad = g(r"adaptive tier\s+(\d+) experts swapped")
    mt = g(r"mtp\s+([\d.]+) ms/round")
    dc = g(r"decode\s+(\d+) tokens in ([\d.]+) ms\s+->\s+([\d.]+) tok/s")
    hr = g(r"expert-cache hits\s+\d+ of \d+ = ([\d.]+)")
    tpr = float(sp.group(5)); rounds = int(sp.group(1))
    mb_tok = float(pm.group(3)) * (float(pm.group(1)) + float(pm.group(2))) / tpr    # GB/s * ms = MB
    pcie = int(ad.group(1)) * 2.045 / int(dc.group(1)) if ad else 0
    print(f"| {L} | {float(dc.group(3)):.1f} | {tpr:.2f} | {float(sp.group(4)):.3f} | {float(vw.group(1)):.1f} / {float(vw.group(2)):.1f} / "
          f"{float(mt.group(1)):.1f} | {float(vw.group(5)):.2f} | {mb_tok:.0f} | {pcie:.0f} | {float(hr.group(1)):.3f} |")
