#!/usr/bin/env python3
"""a1_counts.py LABEL ELOG — round 10 A.1: the counting build's per-request R10A lines, per segment of a1count.sh
(fresh screen / an hour of pool traffic / aged screen): (a) adaptive swaps whose incoming expert the helper holds,
(b) experts held by both cards at the end of the request, (c) who computed the verify windows' routed entries (5080 VRAM,
helper, CPU, PCIe), with each request's decode tokens and the host's wait for the helper."""
import re, sys
from pathlib import Path
L, elog = sys.argv[1], Path(sys.argv[2])
offs = [l.split() for l in Path(f"/home/USER/ai-speed-testing/strata-compare/logs/r13/{L}.offsets").read_text().split("\n") if l.strip()]
data = elog.read_bytes()
RQ = re.compile(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms \(([\d.]+) tok/s\), (\d+) generated in ([\d.]+) ms")
HL = re.compile(r"strata serve: CUDA1: (\d+) expert entries, (\d+) active layer launches.*?host (\d+) ms staging\+launching, (\d+) ms waiting")
RA = re.compile(r"R10A entries gpu0 (\d+) pcie (\d+) helper (\d+) cpu (\d+); distinct gpu0 (\d+) pcie (\d+) helper (\d+) cpu (\d+); "
                r"adapt calls (\d+) swaps (\d+) in_helper (\d+) out_helper (\d+); both_hold (\d+) helper_slots (\d+)")
out = [f"# A.1 counts — {L}", ""]
for i in range(len(offs) - 1):
    name, a, b = offs[i][0], int(offs[i][1]), int(offs[i + 1][1])
    seg = data[a:b].decode("utf-8", "replace").split("\n")
    rows, cur = [], {}
    for line in seg:
        if (m := RQ.search(line)):
            cur = dict(prompt=int(m[1]), gen=int(m[6]), dec_ms=float(m[7]))
        elif (m := HL.search(line)):
            cur["hwait"] = int(m[4])
        elif (m := RA.search(line)):
            v = list(map(int, m.groups()))
            cur.update(eg=v[0], ep=v[1], eh=v[2], ec=v[3], dg=v[4], dp=v[5], dh=v[6], dc=v[7], calls=v[8], swaps=v[9],
                       inh=v[10], outh=v[11], both=v[12], hslots=v[13])
            rows.append(cur); cur = {}
    if not rows:
        continue
    out += [f"## {name} ({len(rows)} requests)", "",
            "| # | prompt | generated | swaps | (a) in from helper's set | out to helper's set | (b) both hold (of helper slots) | (c) entries 5080 / helper / CPU / PCIe | distinct 5080 / helper / CPU | host waits for helper (ms / % of decode) |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for j, r in enumerate(rows, 1):
        te = r["eg"] + r["eh"] + r["ec"] + r["ep"] or 1
        td = r["dg"] + r["dh"] + r["dc"] + r["dp"] or 1
        out.append(f"| {j} | {r['prompt']} | {r['gen']} | {r['swaps']} | {r['inh']} ({100 * r['inh'] / max(1, r['swaps']):.0f} %) | {r['outh']} | "
                   f"{r['both']} ({100 * r['both'] / max(1, r['hslots']):.1f} %) | {100 * r['eg'] / te:.1f} / {100 * r['eh'] / te:.1f} / "
                   f"{100 * r['ec'] / te:.1f} / {100 * r['ep'] / te:.1f} % | {100 * r['dg'] / td:.1f} / {100 * r['dh'] / td:.1f} / {100 * r['dc'] / td:.1f} % | "
                   f"{r.get('hwait', 0)} / {100 * r.get('hwait', 0) / max(1.0, r['dec_ms']):.2f} % |")
    S = lambda k: sum(r[k] for r in rows)
    te = S("eg") + S("eh") + S("ec") + S("ep") or 1
    out += ["", f"**{name} total:** {S('swaps')} swaps, **{S('inh')} ({100 * S('inh') / max(1, S('swaps')):.1f} %) pulled in an "
            f"expert the helper holds**, {S('outh')} evicted one the helper holds; both cards hold **{rows[-1]['both']} of the helper's "
            f"{rows[-1]['hslots']} experts at the end** (first request: {rows[0]['both']}); routed entries 5080 "
            f"**{100 * S('eg') / te:.1f} %**, helper **{100 * S('eh') / te:.1f} %**, CPU **{100 * S('ec') / te:.1f} %**, PCIe "
            f"{100 * S('ep') / te:.1f} %; host waits for the helper {S('hwait')} ms = {100 * S('hwait') / max(1.0, sum(r['dec_ms'] for r in rows)):.2f} % of decode time", ""]
print("\n".join(out))
