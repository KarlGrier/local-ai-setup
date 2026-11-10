#!/usr/bin/env python3
"""pcie_empty.py LABEL — round 10 B.4 (#363's idea on our PR245 kernels): from a served nsys trace (logs/r10/prof/LABEL.sqlite),
what the verify window's PCIe expert call costs per window at --pcie-frac 0, where it never has a group.

Per layer of a window (the main stream, split at each doorbell_publish_kernel) the grouped expert kernels run twice:
the VRAM call (native_gus_kernel + native_down4_kernel) and then the PCIe call (the same two kernels on the PCIe plan's
empty group list).  Reported: the second call's two kernels' durations, the idle stream time around them (from the end
of the VRAM call's down4 to the start of the next kernel after the PCIe call's down4, minus the flag-B wait between), and
the same for the VRAM call for scale."""
import bisect
import collections
import sqlite3
import statistics
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
db = sqlite3.connect(WS / f"logs/r10/prof/{sys.argv[1]}.sqlite")
cur = db.cursor()
strings = dict(cur.execute("SELECT id, value FROM StringIds"))
kc = [r[1] for r in cur.execute("PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)")]
name_col = "shortName" if "shortName" in kc else "demangledName"
K = [(s, e, strings.get(n, str(n)), st) for s, e, n, st in
     cur.execute(f"SELECT start, end, {name_col}, streamId FROM CUPTI_ACTIVITY_KIND_KERNEL ORDER BY start")]
nc = [r[1] for r in cur.execute("PRAGMA table_info(NVTX_EVENTS)")]
txt = "COALESCE(text, (SELECT value FROM StringIds WHERE id = textId))" if "textId" in nc else "text"
W = [(s, e) for s, e, t in cur.execute(f"SELECT start, end, {txt} FROM NVTX_EVENTS WHERE end IS NOT NULL ORDER BY start")
     if t == "window"]
starts = [k[0] for k in K]
main = collections.Counter(k[3] for k in K if "doorbell_publish" in k[2]).most_common(1)[0][0]
vram_k, pcie_k, pcie_gap, layers, per_win = [], [], [], 0, []
for a, b in W:
    i = bisect.bisect_left(starts, a)
    ks = []
    while i < len(K) and K[i][0] < b:
        if K[i][3] == main:
            ks.append(K[i])
        i += 1
    win_pcie = 0.0
    # split at doorbells
    seg_starts = [j for j, k in enumerate(ks) if "doorbell_publish" in k[2]] + [len(ks)]
    for x, y in zip(seg_starts, seg_starts[1:]):
        seg = ks[x:y]
        g = [j for j, k in enumerate(seg) if k[2].startswith("native_gus")]
        d = [j for j, k in enumerate(seg) if k[2].startswith("native_down4")]
        if len(g) < 2 or len(d) < 2:
            continue
        layers += 1
        vram_k.append((seg[g[0]][1] - seg[g[0]][0] + seg[d[0]][1] - seg[d[0]][0]) / 1e3)
        pk = (seg[g[1]][1] - seg[g[1]][0] + seg[d[1]][1] - seg[d[1]][0]) / 1e3
        pcie_k.append(pk)
        # stream time from the VRAM call's down4 end to the kernel after the PCIe call's down4, minus the waits between
        nxt = seg[d[1] + 1][0] if d[1] + 1 < len(seg) else seg[d[1]][1]
        span = (nxt - seg[d[0]][1]) / 1e3
        waits = sum((k[1] - k[0]) / 1e3 for k in seg[d[0] + 1:g[1]] if "wait_flag" in k[2])
        pcie_gap.append(span - waits)
        win_pcie += span - waits
    per_win.append(win_pcie)
print(f"trace {sys.argv[1]}: {len(W)} windows, {layers} layers with both calls (main stream {main})")
print(f"VRAM call (gus + down4) per layer: mean {statistics.mean(vram_k):.2f} us")
print(f"PCIe call (gus + down4, empty) per layer: kernels {statistics.mean(pcie_k):.2f} us; stream time from the VRAM "
      f"call's end to the next kernel, waits excluded: {statistics.mean(pcie_gap):.2f} us")
print(f"per window: PCIe call kernels {sum(pcie_k) / len(W) / 1000:.3f} ms; stream time {statistics.mean(per_win) / 1000:.3f} ms "
      f"(bar for building #363's idea: >= 0.1 ms)")
