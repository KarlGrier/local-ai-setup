"""grid_table.py PREFIX — round 8 A.6: the speculation grid's decscreens (labels PREFIX*) in one table: engine decode
(accepted output tokens / decode time, all requests > 100 tokens: 4K reasoning math + code, correctness x5, 768 after
32K), ms per verify round, tokens per round, acceptance; each screen vs the mean of the two nearest baseline screens
(labels containing 'base', run in between for drift)."""
import json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
pre = sys.argv[1]
order, seen = [], set()
for r in runs:
    if r["config"].startswith(pre) and r["config"] not in seen:
        seen.add(r["config"]); order.append(r["config"])
def agg(L, scen=("longreason", "correctness", "speed")):
    e = [r["engine"] for r in runs if r["config"] == L and not r.get("error") and r.get("engine") and r["scenario"] in scen
         and r.get("completion_tokens", 0) > 100]
    if not e:
        return None
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    rounds = sum(x["generated"] - x["drafts_accepted"] for x in e)
    acc = sum(x["drafts_accepted"] for x in e) / max(1, sum(x["drafts_offered"] for x in e))
    return g / (ms / 1000), ms / max(1, rounds), g / max(1, rounds), acc, g
res = {L: agg(L) for L in order}
bases = [i for i, L in enumerate(order) if "base" in L and res[L]]
print(f"baselines (--spec 4 --spec-min-p 0.5): " + ", ".join(f"{order[i]} {res[order[i]][0]:.1f}" for i in bases))
print("| screen | decode tok/s | vs nearest baselines | ms/round | tokens/round | acceptance | tokens |")
print("|---|---|---|---|---|---|---|")
rows = []
for i, L in enumerate(order):
    v = res[L]
    if not v:
        print(f"| {L} | – | | | | | |"); continue
    near = sorted(bases, key=lambda b: abs(b - i))[:2] if "base" not in L else []
    ref = sum(res[order[b]][0] for b in near) / len(near) if near else None
    d = f"{(v[0] / ref - 1) * 100:+.1f} %" if ref else ("(baseline)" if "base" in L else "–")
    rows.append((L, v, d))
    print(f"| {L} | {v[0]:.1f} | {d} | {v[1]:.2f} | {v[2]:.2f} | {v[3]:.3f} | {v[4]} |")
