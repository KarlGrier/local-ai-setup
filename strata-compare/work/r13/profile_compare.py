#!/usr/bin/env python3
"""profile_compare.py NAME=PROFILE ... [--n0 4559] [--n1 3300] — round 10 A.4: what each expert profile puts on the RTX 5080
at start (its first n0 ranked pairs; `--expert-cache auto` fills by rank) and on the 4060 Ti helper (the next n1 ranked
pairs the 5080 does not hold, as RemoteExperts::open selects them), and how much those sets overlap between profiles
(pairs in common; per-layer counts' spread).  The engine logs the real slot counts; n0 / n1 are C*11's."""
import struct
import sys
from itertools import combinations

L, E = 48, 512


def pairs(path):
    b = open(path, "rb").read()
    assert b[:4] == b"STRP", path
    n = struct.unpack_from("<I", b, 20)[0]
    return [tuple(x) for x in zip(*[iter(struct.unpack_from(f"<{2 * n}H", b, 24))] * 2)]


args = [a for a in sys.argv[1:] if "=" in a and not a.startswith("--")]
n0 = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--n0=")), 4559))
n1 = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--n1=")), 3300))
sets = {}
for a in args:
    name, path = a.split("=", 1)
    pp = pairs(path)
    g0 = set(pp[:n0])
    h = []
    for p in pp[n0:]:
        if len(h) >= n1:
            break
        if p not in g0:
            h.append(p)
    sets[name] = (g0, set(h), len(pp))
    per = [0] * L
    for l, _ in g0:
        per[l] += 1
    print(f"{name}: {len(pp)} ranked pairs; 5080 at start {len(g0)} (per layer min {min(per)} max {max(per)}), helper {len(h)}")
print("\n| pair | 5080 sets in common | helper sets in common | 5080 ∪ helper in common |\n|---|---|---|---|")
for a, b in combinations(sets, 2):
    ga, ha, _ = sets[a]
    gb, hb, _ = sets[b]
    print(f"| {a} vs {b} | {len(ga & gb)} of {len(ga)} ({100 * len(ga & gb) / len(ga):.1f} %) | {len(ha & hb)} of {len(ha)} "
          f"({100 * len(ha & hb) / max(1, len(ha)):.1f} %) | {len((ga | ha) & (gb | hb))} of {len(ga | ha)} |")
