#!/usr/bin/env python3
"""hold12_table.py NAME_A=L1,L2 NAME_B=L3,L4 — round 14 step 8: Round 12's general holdout (work/r12/holdout12.py,
scenario holdout12, never run before Round 14) as an A/B: engine decode over every answer > 100 tokens (accepted output
tokens / decode time), the five long answers' decode, TTFT of the ~27K-token document (enginedoc) and of the three
short questions (median), total time of all nine requests. SINCE (ISO) keeps this round's runs."""
import json, os, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
since = os.environ.get("SINCE", "2026-10-06T07:28")
runs = [r for r in (json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8"))
        if r.get("scenario") == "holdout12" and r.get("started", "") >= since and not r.get("error")]
def m(L):
    rs = [r for r in runs if r["config"] == L]
    e = [r["engine"] for r in rs if r.get("engine") and r.get("completion_tokens", 0) > 100]
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    doc = [r["ttft_s"] for r in rs if r["item"] == "enginedoc" and r.get("ttft_s")]
    sh = [r["ttft_s"] for r in rs if r["item"].startswith("short") and r.get("ttft_s")]
    return {"decode (tok/s)": g / (ms / 1000) if ms else None, "output tokens": g,
            "TTFT document 27K (s)": doc[0] if doc else None, "TTFT short, median (s)": statistics.median(sh) if sh else None,
            "all 9 requests, total (s)": sum(r["t_total_s"] for r in rs), "requests": len(rs)}
arms = [a.split("=", 1) for a in sys.argv[1:3]]
vals = {n: [m(L) for L in ls.split(",")] for n, ls in arms}
(na, la), (nb, lb) = arms
print(f"| metric | {na}: {la.replace(',', ' / ')} → mean | {nb}: {lb.replace(',', ' / ')} → mean | B vs A |")
print("|---|---|---|---|")
for k in vals[na][0]:
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None
    a = [v[k] for v in vals[na]]; b = [v[k] for v in vals[nb]]
    ma, mb = mean(a), mean(b)
    f = lambda x: "–" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))
    d = f"{(mb / ma - 1) * 100:+.1f} %" if ma and mb is not None else ""
    print(f"| {k} | {' / '.join(f(x) for x in a)} → **{f(ma)}** | {' / '.join(f(x) for x in b)} → **{f(mb)}** | {d} |")
