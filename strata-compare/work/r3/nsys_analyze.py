#!/usr/bin/env python3
"""nsys_analyze.py LABEL [--csv] — round 3: the decode path in an nsys trace of the trace build (work/r3/nsys.sh).

Reads logs/r3/nsys/LABEL.sqlite (kernels, memcpys, NVTX ranges of the host thread) and reports, over the captured
verify windows:
  1. per window: wall time, GPU busy time (union of kernel intervals, split into "waiting" = the spin kernels that
     wait for the host's flags, and "working" = everything else), idle gaps between kernels, kernel count;
  2. per kernel name: launches and time per window, mean duration (where the GPU half of decode goes);
  3. per layer: the host's "wait" (spinning for the doorbell) and "pool" (CPU experts) intervals, how much GPU work
     ran inside each pool interval (= the overlap of GPU and CPU expert work), and how long the GPU sat in the flag
     wait for the CPU;
  4. the critical path per layer: from the host raising the flag (end of "pool") to the next doorbell (end of the
     next "wait"): GPU working time inside it vs gaps.
"""
import collections
import sqlite3
import statistics
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
label = sys.argv[1]
db = sqlite3.connect(WS / f"logs/r3/nsys/{label}.sqlite")
cur = db.cursor()


def cols(table):
    return [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]


tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
strings = dict(cur.execute("SELECT id, value FROM StringIds")) if "StringIds" in tables else {}

kc = cols("CUPTI_ACTIVITY_KIND_KERNEL")
name_col = "shortName" if "shortName" in kc else "demangledName"
K = [(s, e, strings.get(n, str(n)), st) for s, e, n, st in
     cur.execute(f"SELECT start, end, {name_col}, streamId FROM CUPTI_ACTIVITY_KIND_KERNEL ORDER BY start")]
M = []
if "CUPTI_ACTIVITY_KIND_MEMCPY" in tables:
    M = list(cur.execute("SELECT start, end, bytes, copyKind, streamId FROM CUPTI_ACTIVITY_KIND_MEMCPY ORDER BY start"))
nc = cols("NVTX_EVENTS")
txt = "COALESCE(text, (SELECT value FROM StringIds WHERE id = textId))" if "textId" in nc else "text"
pay = "int64Value" if "int64Value" in nc else "NULL"
R = list(cur.execute(f"SELECT start, end, {txt}, {pay} FROM NVTX_EVENTS WHERE end IS NOT NULL ORDER BY start"))
by = collections.defaultdict(list)
for s, e, t, p in R:
    by[t].append((s, e, p))
windows = by.get("window", [])
print(f"trace {label}: {len(K)} kernels, {len(M)} memcpys, NVTX: " +
      ", ".join(f"{k} {len(v)}" for k, v in sorted(by.items())))
if not windows:
    sys.exit("no 'window' ranges (was the trace build used and the capture range hit?)")

WAIT_NAMES = ("wait_flag_ge",)


def is_wait(name):
    return any(w in name for w in WAIT_NAMES)


def union(iv):
    tot, cs, ce = 0, None, None
    for s, e in sorted(iv):
        if cs is None or s > ce:
            if cs is not None:
                tot += ce - cs
            cs, ce = s, e
        else:
            ce = max(ce, e)
    if cs is not None:
        tot += ce - cs
    return tot


import bisect
kstarts = [k[0] for k in K]


def kernels_in(a, b):
    i = bisect.bisect_left(kstarts, a - 50_000_000)
    out = []
    while i < len(K) and K[i][0] < b:
        s, e, n, st = K[i]
        if e > a:
            out.append((max(s, a), min(e, b), n, st, s, e))
        i += 1
    return out


# ---- 1. per window
rows = []
per_name = collections.defaultdict(lambda: [0, 0])     # name -> [count, ns]
main_streams = collections.Counter()
for (a, b, T) in windows:
    ks = kernels_in(a, b)
    for k in ks:
        main_streams[k[3]] += 1
    work = [(s, e) for s, e, n, *_ in ks if not is_wait(n)]
    wait = [(s, e) for s, e, n, *_ in ks if is_wait(n)]
    busy = union([(s, e) for s, e, *_ in ks])
    ks_sorted = sorted(ks)
    gaps = 0
    ngap = 0
    last_e = None
    for s, e, *_ in ks_sorted:
        if last_e is not None and s > last_e:
            gaps += s - last_e
            ngap += 1
        last_e = e if last_e is None else max(last_e, e)
    for s, e, n, st, s0, e0 in ks:
        per_name[n][0] += 1
        per_name[n][1] += e - s
    rows.append(dict(T=T, wall=(b - a) / 1e6, busy=busy / 1e6, work=union(work) / 1e6, wait=union(wait) / 1e6,
                     gaps=gaps / 1e6, n=len(ks), first=(ks_sorted[0][0] - a) / 1e6 if ks else 0))
nw = len(rows)


def med(key, sel=None):
    v = [r[key] for r in rows if sel is None or r["T"] == sel]
    return statistics.mean(v) if v else 0


print(f"\n== {nw} windows (mean over all; T = tokens in the window) ==")
print(f"{'T':>3} {'n':>4} {'wall ms':>8} {'GPU busy':>9} {'working':>8} {'flag-wait':>9} {'gaps':>7} {'kernels':>8}")
for T in sorted({r['T'] for r in rows}) + [None]:
    sel = [r for r in rows if T is None or r["T"] == T]
    if not sel:
        continue
    m = lambda k: statistics.mean(r[k] for r in sel)
    print(f"{'all' if T is None else T:>3} {len(sel):>4} {m('wall'):8.2f} {m('busy'):9.2f} {m('work'):8.2f} "
          f"{m('wait'):9.2f} {m('gaps'):7.2f} {m('n'):8.0f}")

print(f"\n== kernels per window (all windows; top 30 by time) ==")
print(f"{'kernel':<60} {'per win':>8} {'ms/win':>8} {'us each':>8}")
for n, (c, ns) in sorted(per_name.items(), key=lambda x: -x[1][1])[:30]:
    print(f"{n[:60]:<60} {c / nw:8.1f} {ns / nw / 1e6:8.3f} {ns / c / 1e3:8.2f}")

# ---- 3./4. per layer, from the host ranges
waits, pools = by.get("wait", []), by.get("pool", [])
if pools:
    ov, pool_ms, gpu_flag, crit_work, crit_len = [], [], [], [], []
    per_layer = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])
    wi = 0
    for idx, (a, b, l) in enumerate(pools):
        ks = kernels_in(a, b)
        w_in = union([(s, e) for s, e, n, *_ in ks if not is_wait(n)])
        ov.append(w_in / 1e6)
        pool_ms.append((b - a) / 1e6)
        # the GPU's flag wait that ends after this pool interval (the one the host released)
        fw = [(s0, e0) for s, e, n, st, s0, e0 in kernels_in(a, b + 200_000) if is_wait(n) and e0 >= b - 5_000]
        g = min(fw, key=lambda x: abs(x[1] - b)) if fw else None
        gpu_flag.append(((g[1] - max(g[0], a)) / 1e6) if g else 0)
        # critical path: from b (flag raised) to the end of the next wait range (next doorbell seen)
        nxt = next(((s, e) for s, e, _ in waits if s >= b - 1000), None)
        if nxt and nxt[1] - b < 5_000_000:
            ks2 = kernels_in(b, nxt[1])
            crit_work.append(union([(s, e) for s, e, n, *_ in ks2 if not is_wait(n)]) / 1e6)
            crit_len.append((nxt[1] - b) / 1e6)
        pl = per_layer[l]
        pl[0] += 1; pl[1] += (b - a) / 1e6; pl[2] += w_in / 1e6
    print(f"\n== per layer over {len(pools)} (layer, window) pool intervals ==")
    print(f"host pool interval (CPU experts)        {statistics.mean(pool_ms) * 1000:8.1f} us")
    print(f"  GPU working inside it (overlap)       {statistics.mean(ov) * 1000:8.1f} us "
          f"({100 * sum(ov) / max(1e-9, sum(pool_ms)):.0f} % of the pool time)")
    if waits:
        wms = [(e - s) / 1e6 for s, e, _ in waits]
        print(f"host wait interval (GPU to doorbell)    {statistics.mean(wms) * 1000:8.1f} us")
    if crit_len:
        print(f"flag raised -> next doorbell seen       {statistics.mean(crit_len) * 1000:8.1f} us, of which GPU working "
              f"{statistics.mean(crit_work) * 1000:.1f} us ({100 * sum(crit_work) / sum(crit_len):.0f} %)")
    print(f"\n{'layer':>5} {'n':>5} {'pool us':>8} {'overlap us':>10}")
    for l in sorted(per_layer):
        c, p, o, *_ = per_layer[l]
        if l in (0, 1, 2, 3, 12, 23, 24, 46, 47) or c and l % 8 == 0:
            print(f"{l:>5} {c:>5} {1000 * p / c:8.1f} {1000 * o / c:10.1f}")
if M:
    per_kind = collections.defaultdict(lambda: [0, 0, 0])
    for s, e, byt, kind, st in M:
        if any(a <= s < b for a, b, _ in windows):
            per_kind[kind][0] += 1; per_kind[kind][1] += e - s; per_kind[kind][2] += byt
    for k, (c, ns, byt) in per_kind.items():
        print(f"memcpy kind {k}: {c / nw:.1f} per window, {ns / nw / 1e6:.3f} ms/window, {byt / nw / 1e6:.2f} MB/window")
print("\nstreams seen inside windows:", dict(main_streams.most_common(5)))

# ---- 5. what runs on the critical path: from the flag (end of "pool" l) to the doorbell of layer l+1 (end of the next
#         "wait"), same window only; kernel time by name, split by the NEXT layer's kind (GDN / QSA: every 4th is QSA)
if pools and waits:
    wins = sorted(windows)
    def win_of(t):
        i = bisect.bisect_right([w[0] for w in wins], t) - 1
        return i if i >= 0 and t <= wins[i][1] else -1
    crit = {"gdn": collections.defaultdict(float), "qsa": collections.defaultdict(float)}
    nlay = collections.Counter()
    span = collections.defaultdict(float)
    wait_starts = [w[0] for w in waits]
    for (a, b, l) in pools:
        j = bisect.bisect_left(wait_starts, b - 1000)
        if j >= len(waits):
            continue
        s2, e2, l2 = waits[j]
        if l2 != l + 1 or win_of(b) != win_of(e2) or win_of(b) < 0:
            continue
        kind = "qsa" if (l + 1) % 4 == 3 else "gdn"
        nlay[kind] += 1
        span[kind] += (e2 - b) / 1e3
        for s, e, n, *_ in kernels_in(b, e2):
            crit[kind][n] += (e - s) / 1e3
    for kind in ("gdn", "qsa"):
        c = nlay[kind]
        if not c:
            continue
        tot = sum(crit[kind].values()) / c
        print(f"\n== critical path into a {kind.upper()} layer ({c} samples): flag -> next doorbell {span[kind] / c:.1f} us, "
              f"kernel time {tot:.1f} us ==")
        for n, us in sorted(crit[kind].items(), key=lambda x: -x[1])[:18]:
            print(f"   {n[:58]:<58} {us / c:7.1f} us")

# ---- 6. outside the layer loop: the host ranges per window, and the gap from one window's end to the next's start
print("\n== per window, outside the 48-layer loop (host NVTX ranges, mean ms) ==")
for name in ("tail", "commit", "mtp"):
    v = by.get(name, [])
    if v:
        print(f"   {name:<8} {statistics.mean((e - s) / 1e6 for s, e, _ in v):7.3f} ms   (n={len(v)})")
ws = sorted(windows)
gaps = [(ws[i + 1][0] - ws[i][1]) / 1e6 for i in range(len(ws) - 1) if ws[i + 1][0] - ws[i][1] < 50_000_000]
if gaps:
    print(f"   window end -> next window start (commit + mtp + host): {statistics.mean(gaps):.3f} ms")
wl = [(e - s) / 1e6 for s, e, _ in windows]
lay = collections.defaultdict(float)
for s, e, l in waits + pools:
    lay[win_of(s) if pools else 0] += (e - s) / 1e6
if pools:
    loop = statistics.mean(lay[i] for i in range(len(wins)) if i in lay)
    print(f"   window {statistics.mean(wl):.3f} ms, of which the 48 layers' wait+pool {loop:.3f} ms")
# the tail's kernels (after the last pool of a window until the window's end)
tailk = collections.defaultdict(float)
for s, e, _ in by.get("tail", []):
    for ks, ke, n, *_ in kernels_in(s, e):
        tailk[n] += (ke - ks) / 1e3
if tailk:
    nt = len(by.get("tail", []))
    print("   kernels inside 'tail' (us per window):", ", ".join(f"{n[:30]} {us / nt:.1f}" for n, us in
                                                        sorted(tailk.items(), key=lambda x: -x[1])[:6]))
