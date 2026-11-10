#!/usr/bin/env python3
"""ldr_table.py NAME=LABEL,LABEL ... — round 10: the LDR-shaped screen's A/B table from results/runs.jsonl (this round's
runs only, SINCE): decode = the engine's accepted output tokens / decode time over every request of the set; ms per verify
round, tokens per round, acceptance; decode by request kind; TTFT (client side) of the short, mid and long prompts; the
full request time of all requests (what you wait for).  B vs A in percent when two arms are given."""
import json, os, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from desk_load import label_load  # noqa: E402
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SINCE = os.environ.get("SINCE", "2026-10-04T02:53")
runs = [r for r in (json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8"))
        if r.get("started", "") >= SINCE and str(r.get("scenario", "")).startswith("ldr-")]
def rs(L): return [r for r in runs if r["config"] == L and not r.get("error")]
def agg(rows):
    e = [r["engine"] for r in rows if r.get("engine") and (r.get("completion_tokens") or 0) > 100]
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    if not ms: return None, None, None, None
    rounds = sum(x["generated"] - x["drafts_accepted"] for x in e); off = sum(x["drafts_offered"] for x in e)
    return g / (ms / 1000), ms / max(1, rounds), g / max(1, rounds), (sum(x["drafts_accepted"] for x in e) / off if off else None)
def kind_dec(k): return lambda L: agg([r for r in rs(L) if r.get("note") == k])[0]
def ttft(lo, hi): return lambda L: (lambda v: statistics.mean(v) if v else None)(
    [r["ttft_s"] for r in rs(L) if r.get("ttft_s") is not None and lo <= (r.get("prompt_tokens") or 0) < hi])
M = [("decode, all requests (tok/s)", lambda L: agg(rs(L))[0], 1), ("ms per verify round", lambda L: agg(rs(L))[1], 2),
     ("tokens per round", lambda L: agg(rs(L))[2], 3), ("acceptance", lambda L: agg(rs(L))[3], 3)] + \
    [(f"decode, {k} (tok/s)", kind_dec(k), 1) for k in ("queries", "triage", "toolcall", "analysis", "synthesis", "followup", "copy", "quote", "chat")] + \
    [("TTFT prompts < 4K, mean (s)", ttft(0, 4000), 2), ("TTFT prompts 4–16K, mean (s)", ttft(4000, 16000), 2),
     ("TTFT prompts ≥ 16K, mean (s)", ttft(16000, 10**9), 2),
     ("output tokens, all requests", lambda L: sum(r.get("completion_tokens") or 0 for r in rs(L)), 0),
     ("all requests, total time (s)", lambda L: sum(r.get("t_total_s") or 0 for r in rs(L)), 1),
     ("desktop on the 4060 Ti, graphics SM % (round 11)", lambda L: label_load(rs(L)), 1)]
arms = [(n, ls.split(",")) for n, ls in (a.split("=", 1) for a in sys.argv[1:])]
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
    pct = ""
    if len(arms) == 2 and means[0] and means[1]:
        pct = f" {100 * (means[1] / means[0] - 1):+.1f} % |"
    if len(arms) > 2:
        pct = "".join(f" {100 * (m / means[0] - 1):+.1f} % |" if means[0] and m else " – |" for m in means[1:])
    print(f"| {name} | " + " | ".join(cells) + (" |" + pct if len(arms) != 1 else " |"))
