#!/usr/bin/env python3
"""gap9_verdicts.py - round 22 gap 9 (10-23) verdicts, written before the runs.

  pcie DIR              the user's pcie-frac rule (10-22 12:5x): PC (the served build without the forced --pcie-frac 0)
                        vs C (the served build), records DIR/<arm><pass><n|a|r>.jsonl (abarm.sh). "Adopt it if the
                        research calls and tool-call turns gain at least 3 % on average and W1-W3 is no more than 2 %
                        slower" - read as: the mean of the per-workload decode gains over the four research-call replays
                        (R1 verify, R2 report, R3 extract, R4 agent turn) and the tool-call turns >= +3 %, and the W1-W3
                        mean >= -2 %; at least 4 passes per arm.
  e7div L_A L_B [L_C L_D]  the decode-side check: exact7 outputs (bringup/out/logs/prof/<L>-<item>.out, token ids)
                        compared item by item - identical, or the first differing token. With L_C L_D: the rounding
                        reference (the same build at two slot counts) printed beside it. PASS when the first pair has
                        no more items differing than the reference pair + 1, and its median matching prefix over the
                        decode items is at least half the reference's (pcie moves expert work between the CPU and the
                        GPU the way a cache-size change does; the user, 10-22: cache-size changes are judged as rounding).
  cont ENGLOG [...]     the answer_room continuations in engine-log slices: a continuation = a request whose prompt is
                        the previous request's prompt + what it generated (+ <= 64 tokens); a hit reads <= 64 tokens, a
                        miss re-reads the thinking.
"""
import json
import pathlib
import re
import statistics
import sys

PROF = pathlib.Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
W = ("W1-think", "W2-code", "W3-research")
R = ("R1-verify20k", "R2-report54k", "R3-extract5k", "R4-agent33k")


def pct(x, y):
    return 100 * (x / y - 1) if y else float("nan")


def pcie(d: str) -> int:
    recs = []
    for f in pathlib.Path(d).glob("*.jsonl"):
        if not f.name.endswith(".wu.jsonl") and re.match(r"^(C|PC)\d[nar]\.jsonl$", f.name):
            recs += [json.loads(x) for x in open(f) if x.strip()]

    def vals(arm, kind, wid=None, key="decode_tps"):
        out = {}
        for r in recs:
            m = re.match(r"^(C|PC)(\d)([nar])$", r["arm"])
            if m and m.group(1) == arm and m.group(3) == kind and r.get(key) and (wid is None or r["id"] == wid):
                out.setdefault(int(m.group(2)), []).append(r[key])
        return out

    def mean(by):
        v = [x for xs in by.values() for x in xs]
        return statistics.mean(v) if v else float("nan")

    rows = [("W1-W3", "n", None)] + [(w, "n", w) for w in W] + [("tool-call turns", "a", None)] + [(w, "r", w) for w in R]
    print("| workload | C tok/s (per pass) | PC tok/s (per pass) | C | PC | PC vs C | PC ahead in |")
    print("|---|---|---|---|---|---|---|")
    g = {}
    for name, kind, wid in rows:
        c, p = vals("C", kind, wid), vals("PC", kind, wid)
        per = lambda by: " / ".join(f"{statistics.mean(v):.1f}" for _, v in sorted(by.items()))
        both = [k for k in c if k in p]
        ahead = sum(statistics.mean(p[k]) > statistics.mean(c[k]) for k in both)
        g[name] = pct(mean(p), mean(c))
        print(f"| {name} | {per(c)} | {per(p)} | {mean(c):.1f} | {mean(p):.1f} | {g[name]:+.1f} % | {ahead} of {len(both)} |")
    for name, kind, wid in [("tool-call turns", "a", None)] + [(w, "r", w) for w in R]:
        c, p = vals("C", kind, wid, "ttft_s"), vals("PC", kind, wid, "ttft_s")
        print(f"  time to first token {name}: C {mean(c):.2f} s, PC {mean(p):.2f} s ({pct(mean(p), mean(c)):+.1f} %)")
    passes = min(len(vals(a, "n")) for a in ("C", "PC"))
    focus = [g["tool-call turns"]] + [g[w] for w in R]
    avg = statistics.mean(focus)
    ok = passes >= 4 and avg >= 3 and g["W1-W3"] >= -2
    print(f"PC vs C: research calls + tool-call turns {avg:+.1f} % on average (per workload: "
          f"{', '.join(f'{x:+.1f}' for x in focus)}; needs >= +3 %), W1-W3 {g['W1-W3']:+.1f} % (needs >= -2 %), "
          f"{passes} passes per arm (needs >= 4) -> {'PASS' if ok else 'FAIL'}")
    print(f"PCIE-SPEED {'PASS' if ok else 'FAIL'}")
    return 0


def toks(label):
    t = (PROF / f"{label}.out").read_text(errors="replace")
    m = re.search(r"^output\s*:\s*(.*)$", t, re.M)
    return m[1].split() if m else []


ITEMS = ("x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k")
DECODE = ("x-math", "s-math", "x-code", "s-code")


def pair(a, b):
    out = {}
    for it in ITEMS:
        x, y = toks(f"{a}-{it}"), toks(f"{b}-{it}")
        n = next((i for i, (u, v) in enumerate(zip(x, y)) if u != v), None)
        out[it] = (len(x), None if n is None and len(x) == len(y) else (n if n is not None else min(len(x), len(y))))
    return out


def e7div(a, b, c=None, d=None) -> int:
    pa = pair(a, b)
    pr = pair(c, d) if c and d else None
    print(f"| item | {a} vs {b} | " + (f"{c} vs {d} (rounding reference) |" if pr else "") )
    print("|---|---|" + ("---|" if pr else ""))
    fmt = lambda v: "identical" if v[1] is None else f"first difference at token {v[1]} of {v[0]}"
    for it in ITEMS:
        print(f"| {it} | {fmt(pa[it])} | " + (f"{fmt(pr[it])} |" if pr else ""))
    diff = lambda p: sum(v[1] is not None for v in p.values())
    pre = lambda p: statistics.median(v[0] if v[1] is None else v[1] for k, v in p.items() if k in DECODE)
    print(f"{a} vs {b}: {7 - diff(pa)}/7 identical, median matching prefix over the decode items {pre(pa):.0f} tokens")
    if pr:
        print(f"{c} vs {d}: {7 - diff(pr)}/7 identical, median matching prefix over the decode items {pre(pr):.0f} tokens")
        ok = diff(pa) <= diff(pr) + 1 and pre(pa) >= 0.5 * pre(pr)
        print(f"E7DIV {'PASS' if ok else 'FAIL'} (needs: items differing <= the reference's + 1, median prefix >= half the reference's)")
    return 0


def cont(*logs) -> int:
    hit = miss = 0
    for lg in logs:
        prev_tot = prev_gen = 0
        for line in open(lg, errors="replace"):
            m = re.search(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read .*?, (\d+) generated", line)
            if not m:
                continue
            tot, reused, read, gen = map(int, m.groups())
            # a continuation's prompt = the previous prompt + what it generated (+ the wrap-up, <= 64 tokens)
            if prev_gen > 0 and 0 <= tot - (prev_tot + prev_gen) <= 64:
                if read <= 64:
                    hit += 1
                else:
                    miss += 1
                print(f"  {pathlib.Path(lg).name}: continuation {tot} tokens = {reused} reused + {read} read -> {'hit' if read <= 64 else 'MISS'}")
            prev_tot, prev_gen = tot, gen
    print(f"continuations: {hit} hits, {miss} misses")
    return 0


if __name__ == "__main__":
    m, a = sys.argv[1], sys.argv[2:]
    sys.exit(pcie(a[0]) if m == "pcie" else e7div(*a) if m == "e7div" else cont(*a))
