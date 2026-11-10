#!/usr/bin/env python3
"""replay12.py ROUTE_LABEL --n0 SLOTS [--n1 3300] [--rej W ...] [--held-topics ...] — round 13 A3 (rejected drafts in
the usage counter): Round 10's two-tier replay (work/r10/replay10.py) on the R12 routing dump (tmp/r13/route-LABEL.bin,
every verified row of a served run from the server's start: prompt-part windows, MTP and lookup decode windows, each
row with its fate). The 5080's tier = the profile's first N0 ranked pairs at start, then the adaptive tier as the serve
loop runs it (usage += W per routed entry of a row, W = 1 for kept rows and --rej for rejected ones [the engine: 1 for
every row]; every 4th decode round: candidates not on the 5080 and not helper-held (STRATA_ADAPT_HELPER=1) with
usage >= 2 replace the lowest-usage residents while cand >= vict + 1.5, at most 96 swaps by gain, usage *= 0.7; a
new expert lands 2 rounds later (STRATA_ADAPT_LAND=2), an evicted one leaves at once). The helper = the next N1
ranked pairs not on the 5080 (static). Everything else: the CPU.
Validation (--rej 1 = the engine's rule): the replayed computer of every routed entry vs the engine's own (dump).
Score: CPU-side entries and distinct CPU experts per layer-window of the KEPT rows of decode windows (the work the CPU
pool must do), over all windows or the held-out topics' windows."""
import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

WS = Path("/home/USER/ai-speed-testing/strata-compare")
L, E = 48, 512


def profile_pairs(path):
    b = open(path, "rb").read()
    assert b[:4] == b"STRP", path
    n = struct.unpack_from("<I", b, 20)[0]
    return np.frombuffer(b, "<u2", 2 * n, 24).reshape(n, 2).astype(np.int64)


def windows(label):
    """yields dicts: req, sfx (-1 prompt part, 0 MTP, 1 lookup), T, a, rows: list of (layer, row, ids[k], kinds[k])"""
    buf = (WS / f"tmp/r13/route-{label}.bin").read_bytes()
    i, n = 0, len(buf)
    cur, req = None, 0
    while i < n:
        tag = struct.unpack_from("<i", buf, i)[0]
        if tag == -3:
            _, req, _, _ = struct.unpack_from("<4i", buf, i); i += 16
        elif tag == -2:
            _, layers, ne = struct.unpack_from("<3i", buf, i); i += 12 + layers * ne
        elif tag == -1:
            h = struct.unpack_from("<8i", buf, i); i += 32 + 4 * max(h[1], 0)
            if cur is not None:
                yield cur
            cur = {"req": h[7], "T": h[1], "a": h[2], "sfx": h[4], "rows": []}
        else:
            layer, row, k = struct.unpack_from("<3i", buf, i); i += 12
            ids = np.frombuffer(buf, "<i4", k, i); i += 4 * k
            kinds = np.frombuffer(buf, "<i4", k, i); i += 4 * k
            if cur is not None:
                cur["rows"].append((layer, row, ids, kinds))
    if cur is not None:
        yield cur


def replay(wins, pairs, n0, n1, rej, every=4, lag=2, swaps_max=96, score=None):
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
    for w in wins:
        dec = w["sfx"] >= 0
        if dec and pending is not None and rounds >= land_at:
            for l, a, _ in pending:
                res[l, a] = True
            pending = None
        for layer, row, ids, kinds in w["rows"]:
            kept = (not dec) or row <= w["a"]
            if score is not None and dec:
                score(w, layer, row, kept, ids, kinds, res[layer], helper[layer])
            np.add.at(usage[layer], ids, 1.0 if kept else rej)
        if not dec:
            continue
        if (rounds + 1) % every == 0 and pending is None:
            sw = []
            for l in range(L):
                u = usage[l]
                ok = ~res[l] & (u >= 2.0) & ~helper[l]
                cand = np.where(ok)[0]
                vict = np.where(res[l])[0]
                if len(cand) == 0 or len(vict) == 0:
                    continue
                cand = cand[np.argsort(-u[cand], kind="stable")]
                vict = vict[np.argsort(u[vict], kind="stable")]
                for i in range(min(len(cand), len(vict))):
                    if u[cand[i]] < u[vict[i]] + 1.5:
                        break
                    sw.append((u[cand[i]] - u[vict[i]], l, cand[i], vict[i]))
            sw.sort(key=lambda x: -x[0])
            sw = sw[:swaps_max]
            for _, l, a, b in sw:
                res[l, b] = False
            pending = [(l, a, b) for _, l, a, b in sw] or None
            land_at = rounds + 1 + lag - 1
            usage *= 0.7
        rounds += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--n0", type=int, required=True)
    ap.add_argument("--n1", type=int, default=3300)
    ap.add_argument("--rej", type=float, nargs="+", default=[1.0, 0.5, 0.25, 0.0])
    ap.add_argument("--profile", default=str(WS / "strata-v0115/data/expert-profile.bin"))
    ap.add_argument("--held", default="", help="json file: request indices of the held-out conversations")
    a = ap.parse_args()
    pairs = profile_pairs(a.profile)
    wins = list(windows(a.label))
    held = set(json.loads(Path(a.held).read_text())) if a.held else None
    print(f"route-{a.label}: {len(wins)} windows ({sum(1 for w in wins if w['sfx'] >= 0)} decode); n0 {a.n0}, n1 {a.n1}")
    for rej in a.rej:
        st = {"cpu": 0, "all": 0, "dcpu": 0, "lw": 0, "agree": 0, "n": 0}

        def score(w, layer, row, kept, ids, kinds, res_row, hel_row):
            g0 = res_row[ids]
            h = ~g0 & hel_row[ids]
            c = ~g0 & ~h
            rep = np.where(g0, 0, np.where(h, 2, 3))
            st["agree"] += int((rep == np.where(kinds == 1, 3, kinds)).sum()); st["n"] += len(ids)
            if not kept or (held is not None and w["req"] not in held):
                return
            st["cpu"] += int(c.sum()); st["all"] += len(ids)

        replay(wins, pairs, a.n0, a.n1, rej, score=score)
        print(f"rej weight {rej:.2f}: kept decode rows' entries on the CPU {100 * st['cpu'] / max(st['all'], 1):.3f} % "
              f"({st['cpu']} of {st['all']}); replayed computer = engine's on {100 * st['agree'] / max(st['n'], 1):.2f} % of "
              f"entries (meaningful only at weight 1)")


if __name__ == "__main__":
    main()
