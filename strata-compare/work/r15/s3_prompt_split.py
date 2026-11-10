#!/usr/bin/env python3
"""s3_prompt_split.py LABEL ENGINE_LOG — round 15 (your addition for the 6-bit file): where a full set's prompt-read time
goes, per speed prompt (8K / 32K / 64K / 120K), from the engine's STRATA_PREFILL_TIMING lines:
  - the 5080 stage: one line per prompt (its whole GPU timeline, by phase). "wait copy" = the GPU waiting for expert
    uploads (the experts a chunk needs that are not in VRAM: from RAM, or from the SSD when not in the RAM budget)
  - the 4060 Ti stage (a layer split): one line per chunk; it runs chunk i-1 while the 5080 runs chunk i (overlapped)
  - the link: the hand-off of each chunk's residuals (5080 -> pinned host -> 4060 Ti) is copied on the 5080's stream
    inside its "embed+steps" phase, so that phase is its upper bound
  - the SSD: what the drive read while the prompt was read (logs/r15/ssd.csv, 10-s samples, interpolated)
Without a split (placement B) there is only the 5080's line."""
import bisect
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
label, elog = sys.argv[1], Path(sys.argv[2])
REQ = re.compile(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms")
PF = re.compile(r"strata prefill timing: (\d+) tokens, GPU timeline (\d+) ms, wall (\d+) ms, host staging \d+ ms:(.*)")
PH = re.compile(r" ([a-z+/ ]+?) (\d+) \([\d.]+%\)")

lines = elog.read_text(errors="replace").splitlines()
rows = [json.loads(l) for l in (WS / "results/runs.jsonl").open() if f'"{label}"' in l]
speed = {r["item"]: r for r in rows if r["scenario"] == "speed" and r["rep"] == 0}

ssd_t, ssd_gb = [], []
for r in csv.DictReader((WS / "logs/r15/ssd.csv").open()):
    ssd_t.append(dt.datetime.fromisoformat(r["time"]).timestamp()); ssd_gb.append(float(r["read_gb_cum"]))


def ssd_at(ts):
    i = bisect.bisect_left(ssd_t, ts)
    if i <= 0 or i >= len(ssd_t): return None
    f = (ts - ssd_t[i - 1]) / (ssd_t[i] - ssd_t[i - 1])
    return ssd_gb[i - 1] + f * (ssd_gb[i] - ssd_gb[i - 1])


pend = []
found = {}
for l in lines:
    m = PF.search(l)
    if m:
        pend.append((int(m[1]), float(m[2]), float(m[3]), {k.strip(): float(v) for k, v in PH.findall(m[4])}))
        continue
    m = REQ.search(l)
    if m:
        n = int(m[3])
        for k, sz in (("8k", 8000), ("32k", 32000), ("64k", 64000), ("120k", 120000)):
            if sz <= n < sz * 1.1 and int(m[2]) == 0:
                found[k] = (n, float(m[4]), pend)
        pend = []

print(f"## {label}: where the prompt read goes (STRATA_PREFILL_TIMING; seconds)\n")
print("| prompt | read (engine) | 5080 stage: total = expert uploads + dequant + expert GEMMs + attention/GDN/router/other "
      "+ host grouping + KV staging | the 4060 Ti stage (overlapped): busy, of it uploads; chunks | link: hand-off copy "
      "(at most) | SSD read during the read |")
print("|---|---|---|---|---|---|")
for k in ("8k", "32k", "64k", "120k"):
    if k not in found: continue
    n, read_ms, pl = found[k]
    big = max(pl, key=lambda x: x[0])
    small = [x for x in pl if x is not big]
    ph = big[3]
    up, dq = ph.get("wait copy", 0), ph.get("dequant", 0)
    gm = ph.get("gemm gate/up", 0) + ph.get("gemm down", 0)
    hg, kv, emb = ph.get("host grouping", 0), ph.get("kv stage", 0), ph.get("embed+steps", 0)
    other = big[1] - up - dq - gm - hg - kv - emb
    s0 = f"**{big[1] / 1e3:.1f}** = {up / 1e3:.1f} ({100 * up / big[1]:.0f} %) + {dq / 1e3:.1f} + {gm / 1e3:.1f} + {other / 1e3:.1f} + {hg / 1e3:.1f} + {kv / 1e3:.1f}"
    if small:
        busy = sum(x[2] for x in small); sup = sum(x[3].get("wait copy", 0) for x in small)
        s1 = f"{busy / 1e3:.1f}, {sup / 1e3:.1f}; {len(small)} chunks of {max(x[0] for x in small)}"
    else:
        s1 = "– (no split)"
    ssd = "–"
    r = speed.get(k)
    if r:
        t0 = dt.datetime.fromisoformat(r["started"]).timestamp()
        a, b = ssd_at(t0), ssd_at(t0 + r["ttft_s"])
        if a is not None and b is not None:
            ssd = f"{b - a:.0f} GB ({(b - a) / r['ttft_s']:.1f} GB/s)"
    print(f"| {k} | {read_ms / 1e3:.1f} | {s0} | {s1} | {('≤ %.2f' % (emb / 1e3)) if small else '–'} | {ssd} |")
print("\nthe 5080 stage is the critical path when its total ≈ the read; the 4060 Ti's chunks run beside it (its busy time "
      "overlaps); 'expert uploads' = the 5080 waiting for the experts each chunk needs (copies from RAM, and SSD reads "
      "of the experts outside the RAM budget, every chunk)")
