#!/usr/bin/env python3
"""ab_table.py NAME_A=LABEL,LABEL... NAME_B=LABEL,LABEL... — round 9 Phase A: a two-arm A/B from results/runs.jsonl
(decode screens or full screens; labels in run order), per label and per arm mean, and B vs A in percent.
Decode = the engine's accepted output tokens / decode time over every 768+-token answer (+ correctness answers > 100
tokens); ms per verify round and tokens per round at equal footing; acceptance; long reasoning math / code; TTFT 32K
(and 64K / 120K for full screens); full request time of all requests."""
import json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from desk_load import label_load  # noqa: E402
WS = Path("/home/USER/ai-speed-testing/strata-compare")
import os  # round 10: only this round's runs (SINCE, ISO time) - labels may repeat across rounds
runs = [r for r in (json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")) if r.get("started", "") >= os.environ.get("SINCE", "2026-10-04T02:53")]
def rs(L): return [r for r in runs if r["config"] == L and not r.get("error")]
def one(L, sc, it, key):
    v = [r[key] for r in rs(L) if r["scenario"] == sc and r["item"] == it and r.get(key) is not None]
    return v[-1] if v else None
def agg(L):
    e = [r["engine"] for r in rs(L) if r.get("engine") and r["scenario"] in ("speed", "longreason", "correctness")
         and r.get("completion_tokens", 0) > 100]
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    rounds = sum(x["generated"] - x["drafts_accepted"] for x in e); off = sum(x["drafts_offered"] for x in e)
    if not ms: return None, None, None, None
    return g / (ms / 1000), ms / max(1, rounds), g / max(1, rounds), (sum(x["drafts_accepted"] for x in e) / off if off else None)
def total(L): return sum(r.get("t_total_s") or 0 for r in rs(L))
M = [("decode (tok/s)", lambda L: agg(L)[0], 1), ("ms per verify round", lambda L: agg(L)[1], 2),
     ("tokens per round", lambda L: agg(L)[2], 3), ("acceptance", lambda L: agg(L)[3], 3),
     ("long reasoning math (tok/s)", lambda L: one(L, "longreason", "math", "decode_tps"), 1),
     ("long reasoning code (tok/s)", lambda L: one(L, "longreason", "code", "decode_tps"), 1),
     ("TTFT 32K (s)", lambda L: one(L, "speed", "32k", "ttft_s"), 2), ("TTFT 64K (s)", lambda L: one(L, "speed", "64k", "ttft_s"), 2),
     ("TTFT 120K (s)", lambda L: one(L, "speed", "120k", "ttft_s"), 2), ("all requests, total time (s)", total, 1),
     ("desktop on the 4060 Ti, graphics SM % (round 11)", lambda L: label_load(rs(L)), 1)]
arms = [a.split("=", 1) for a in sys.argv[1:]]
arms = [(n, ls.split(",")) for n, ls in arms]
fmt = lambda v, d: "–" if v is None else f"{v:.{d}f}"
extra = [f"{n} vs {arms[0][0]}" for n, _ in arms[1:]] if len(arms) > 2 else []
print("| metric | " + " | ".join(f"{n}: {' / '.join(ls)} → mean" for n, ls in arms) + (" | B vs A |" if len(arms) == 2 else " |") + "".join(f" {x} |" for x in extra))
print("|---|" + "---|" * len(arms) + ("---|" if len(arms) == 2 else "") + "---|" * len(extra))
for name, fn, d in M:
    cells, means = [], []
    for n, ls in arms:
        vals = [fn(L) for L in ls]
        ok = [v for v in vals if v is not None and v != 0]
        m = statistics.mean(ok) if ok else None
        means.append(m)
        cells.append(" / ".join(fmt(v, d) for v in vals) + f" → **{fmt(m, d)}**")
    rel = ""
    if len(arms) == 2:
        rel = f" | {100 * (means[1] / means[0] - 1):+.1f} %" if means[0] and means[1] else " | –"
    if len(arms) > 2:
        rel = "".join(f" | {100 * (m / means[0] - 1):+.1f} %" if means[0] and m else " | –" for m in means[1:])
    if all(m is None for m in means): continue
    print(f"| {name} | " + " | ".join(cells) + rel + " |")
