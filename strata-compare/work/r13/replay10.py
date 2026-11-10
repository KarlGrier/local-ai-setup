#!/usr/bin/env python3
"""replay10.py PROFILE TRACE.r6 [TRACE.r6 ...] [--n0 4559] [--n1 3300] [--lag 2] [--every 4] [--swaps 96]
[--helper-mode 0|1|2] — round 10 A.4: round 6's cache replay (work/r6/cache_replay.py) extended to BOTH expert tiers of
C*11's config, on routing traces v2 (STRATA_R6_ROUTE, work/r6/route_parse.py).

* The 5080's tier: the profile's first N0 ranked (layer, expert) pairs at start, then the engine's adaptive tier as
  generate.cpp's serve loop runs it: usage += 1 per routed entry of every verify row (prompt-part windows included),
  every `every` decode windows (the serve loop's process-wide round count: window w adapts when (w + 1) % every == 0)
  candidates (not on the 5080, usage >= 2; with --helper-mode 1 not held by the helper, 2: helper-held at half use)
  replace victims (resident, lowest usage) while cand >= vict + 1.5, all layers' swaps by gain, at most `swaps`,
  usage *= 0.7; an evicted expert is a miss at once, a new one resident from window w + lag (STRATA_ADAPT_LAND=2).
* The helper's tier (static, remote_experts.cpp open): the next N1 ranked pairs that are not on the 5080 at start; it
  computes the entries the 5080 does not hold.
* Everything else: the CPU.
Validation (with the profile the trace was recorded with): the replayed placement of every entry against the
engine's own (kind 0 VRAM / 2 helper / -1 CPU).  Report: entries per tier, distinct experts per layer-window per tier
(the CPU pool's cost driver is its distinct experts' bytes), decode windows only unless --all."""
import argparse
import struct
import sys

import numpy as np

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r6")
from route_parse import load_v2  # noqa: E402

L, E = 48, 512


def profile_pairs(path):
    b = open(path, "rb").read()
    assert b[:4] == b"STRP", path
    n = struct.unpack_from("<I", b, 20)[0]
    return np.frombuffer(b, "<u2", 2 * n, 24).reshape(n, 2).astype(np.int64)


def replay(windows, pairs, n0, n1, lag, every, swaps_max, helper_mode, collect):
    res = np.zeros((L, E), bool)
    for l, e in pairs[:n0]:
        res[l, e] = True
    helper = np.zeros((L, E), bool)
    k = 0
    for l, e in pairs[n0:]:
        if k >= n1:
            break
        if not res[l, e]:
            helper[l, e] = True
            k += 1
    usage = np.zeros((L, E))
    pending, land_at, rounds = None, None, 0
    for w in windows:
        if w["kind"] == 0 and pending is not None and rounds >= land_at:
            for l, a, _ in pending:
                res[l, a] = True
            pending = None
        for r in w["layers"]:
            l = r["layer"]
            ids = r["ids"].reshape(-1)
            collect(w, r, res[l], helper[l])
            np.add.at(usage[l], ids, 1.0)
        if w["kind"] != 0:
            continue
        if (rounds + 1) % every == 0 and pending is None:
            sw = []
            for l in range(L):
                u = usage[l].copy()
                if helper_mode == 2:
                    u = np.where(helper[l], 0.5 * u, u)
                ok = ~res[l] & (u >= 2.0)
                if helper_mode == 1:
                    ok &= ~helper[l]
                cand = np.where(ok)[0]
                vict = np.where(res[l])[0]
                if len(cand) == 0 or len(vict) == 0:
                    continue
                cand = cand[np.argsort(-u[cand], kind="stable")]
                vict = vict[np.argsort(usage[l][vict], kind="stable")]
                for i in range(min(len(cand), len(vict))):
                    if u[cand[i]] < usage[l][vict[i]] + 1.5:
                        break
                    sw.append((u[cand[i]] - usage[l][vict[i]], l, cand[i], vict[i]))
            sw.sort(key=lambda x: -x[0])
            sw = sw[:swaps_max]
            for _, l, a, b in sw:
                res[l, b] = False          # evicted at once
            pending = [(l, a, b) for _, l, a, b in sw] or None
            land_at = rounds + 1 + lag - 1
            usage *= 0.7
        rounds += 1
    return res, helper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("traces", nargs="+")
    ap.add_argument("--n0", type=int, default=4559)
    ap.add_argument("--n1", type=int, default=3300)
    ap.add_argument("--lag", type=int, default=2)
    ap.add_argument("--every", type=int, default=4)
    ap.add_argument("--swaps", type=int, default=96)
    ap.add_argument("--helper-mode", type=int, default=0)
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()
    pairs = profile_pairs(a.profile)
    tot = {"gpu0": 0, "helper": 0, "cpu": 0}
    dist = {"gpu0": 0, "helper": 0, "cpu": 0}
    agree = [0, 0, 0, 0]   # same, all; engine-helper replayed-helper, engine-helper
    nrec = [0]
    for path in a.traces:
        W = load_v2(path)

        def col(w, r, res_row, hel_row):
            if w["kind"] != 0:
                return
            ids = r["ids"].reshape(-1)
            g0 = res_row[ids]
            h = ~g0 & hel_row[ids]
            c = ~g0 & ~h
            tot["gpu0"] += int(g0.sum()); tot["helper"] += int(h.sum()); tot["cpu"] += int(c.sum())
            dist["gpu0"] += len(set(ids[g0].tolist())); dist["helper"] += len(set(ids[h].tolist()))
            dist["cpu"] += len(set(ids[c].tolist()))
            nrec[0] += 1
            if a.validate:
                kd = r["kind"].reshape(-1)
                rep = np.where(g0, 0, np.where(h, 2, -1))
                agree[0] += int((rep == kd).sum()); agree[1] += len(ids)
                agree[2] += int(((kd == 2) & (rep == 2)).sum()); agree[3] += int((kd == 2).sum())

        replay(W, pairs, a.n0, a.n1, a.lag, a.every, a.swaps, a.helper_mode, col)
    n = sum(tot.values()) or 1
    print(f"profile {a.profile.split('/')[-1]}  traces {len(a.traces)}  decode layer-windows {nrec[0]}  "
          f"(n0 {a.n0}, n1 {a.n1}, lag {a.lag}, helper-mode {a.helper_mode})")
    print(f"  entries: 5080 {100 * tot['gpu0'] / n:.2f} %  helper {100 * tot['helper'] / n:.2f} %  CPU {100 * tot['cpu'] / n:.2f} %")
    print(f"  distinct experts per layer-window: 5080 {dist['gpu0'] / max(1, nrec[0]):.3f}  helper "
          f"{dist['helper'] / max(1, nrec[0]):.3f}  CPU {dist['cpu'] / max(1, nrec[0]):.3f}")
    if a.validate:
        print(f"  VALIDATION: replayed placement = engine's on {100 * agree[0] / max(1, agree[1]):.2f} % of entries; "
              f"engine helper entries replayed as helper {100 * agree[2] / max(1, agree[3]):.2f} %")


if __name__ == "__main__":
    main()
