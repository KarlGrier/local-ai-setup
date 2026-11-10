#!/usr/bin/env python3
"""a1_screens.py SESSION_PREFIX [...] — round 12 A1: per screen session (results/runs.jsonl), per request kind: engine
decode tok/s (generated / decode ms), draft acceptance (accepted / offered) and accepted drafts per generated token.
With --suffix-draft 0 every drafted window is an MTP window: MTP-only acceptance per request kind."""
import json
import sys
from collections import defaultdict
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
for pre in sys.argv[1:]:
    recs = [json.loads(l) for l in open(WS / "results/runs.jsonl") if f'"session": "{pre}-' in l]
    agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for r in recs:
        e = r.get("engine") or {}
        if not e.get("generated"):
            continue
        sc = r["scenario"]
        k = (r.get("note") or r["item"].split("-")[-1]) if sc.startswith("ldr-") else f"{sc}:{r['item']}"
        for key in (k, "ALL"):
            a = agg[key]
            a[0] += e["generated"]; a[1] += e["decode_ms"]; a[2] += e.get("drafts_accepted", 0); a[3] += e.get("drafts_offered", 0)
    print(f"\n### {pre} ({len(recs)} records)")
    print("| kind | tokens | decode tok/s | acceptance | offered per token |\n|---|---|---|---|---|")
    for k in sorted(agg, key=lambda x: (x == "ALL", x)):
        g, ms, acc, off = agg[k]
        print(f"| {k} | {g:.0f} | {1000*g/ms:.1f} | {acc/max(off,1):.3f} | {off/max(g,1):.3f} |")
