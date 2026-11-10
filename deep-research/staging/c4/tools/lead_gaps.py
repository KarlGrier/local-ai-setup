#!/usr/bin/env python3
"""lead_gaps.py - C4, after the $3 pilots: the gaps between the lead agent's calls, read from the guard's
lead-gaps-<run>.jsonl (times and token counts only; no prompt content is in that file), so Karl can decide whether to
turn on the lead's 1-hour cache lifetime (GUARD_LEAD_CACHE_1H=1 in the arm file; off by default, Karl 10-29).

  .venv/bin/python -I staging/c4/tools/lead_gaps.py <arm>/guard [<dir or lead-gaps-*.jsonl> ...] [--json]

Gaps are start to start: every lead call reads (and so refreshes) the lead's cached prefix when it starts, so a gap
longer than the 5-minute lifetime means the next lead call finds the prefix gone and writes it again. Idle time
(the previous lead call's end to the next start) is shown too.

The estimate (from a 5m pilot): with the lead at 1 h, a lead call after a 5-60 min gap would read the previous lead
call's prompt (cache-read rate) instead of writing it again (5m write rate); every other lead cache write would cost
the 1h rate instead of the 5m rate. Rates from pricing.json next to this folder (--pricing to change). It is an
estimate on the pilot's own calls, not a forecast of the main run.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

DEFAULT_PRICING = Path(__file__).resolve().parent.parent / "pricing.json"


def load(paths: list[str]) -> dict[str, list[dict]]:
    """run id -> its lead calls (sorted by start), from files or the lead-gaps-*.jsonl files in folders."""
    files: list[Path] = []
    for p in map(Path, paths):
        files += sorted(p.glob("lead-gaps-*.jsonl")) if p.is_dir() else [p]
    runs: dict[str, list[dict]] = {}
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and isinstance(r.get("t"), (int, float)):
                runs.setdefault(str(r.get("run") or f.stem), []).append(r)
    for calls in runs.values():
        calls.sort(key=lambda r: r["t"])
    return runs


def pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def summarise(calls: list[dict], rates: dict, ttl_s: float = 300.0, long_s: float = 3600.0) -> dict:
    gaps, idles, at_stake, cold_after_long = [], [], 0, 0
    n_long = 0
    for prev, cur in zip(calls, calls[1:]):
        g = cur["t"] - prev["t"]                                    # start to start (computed: restarts included)
        gaps.append(g)
        idles.append(max(0.0, cur["t"] - (prev["t"] + float(prev.get("duration_s") or 0.0))))
        if g > ttl_s:
            n_long += 1
            pt, cr = cur.get("prompt_tokens"), cur.get("cache_read")
            if pt and cr is not None and cr < 0.5 * pt:
                cold_after_long += 1                                # seen cold (real API; the mock never expires)
            if g <= long_s and prev.get("prompt_tokens"):
                at_stake += int(prev["prompt_tokens"])              # what a 1 h entry would still have held
    writes = sum(int(c.get("cache_write") or 0) for c in calls)
    w5, w1, rd = rates["cache_write_5m"], rates["cache_write_1h"], rates["cache_read"]
    saved = at_stake * (w5 - rd) / 1e6
    extra = max(0, writes - at_stake) * (w1 - w5) / 1e6
    return {"lead_calls": len(calls), "gaps": len(gaps), "ttl_s": ttl_s,
            "gaps_over_ttl": n_long, "gaps_over_1h": sum(1 for g in gaps if g > long_s),
            "idle_over_ttl": sum(1 for i in idles if i > ttl_s),
            "gap_median_s": round(statistics.median(gaps), 1) if gaps else None,
            "gap_p90_s": round(pct(gaps, 0.9), 1) if gaps else None,
            "gap_max_s": round(max(gaps), 1) if gaps else None,
            "cold_after_long_gap": cold_after_long,
            "lead_cache_write_tokens": writes, "prefix_tokens_rewritten_after_5_60min_gaps": at_stake,
            "est_1h_saves_usd": round(saved, 4), "est_1h_costs_usd": round(extra, 4),
            "est_1h_net_usd": round(saved - extra, 4)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", help="guard folders (<arm>/guard) or lead-gaps-*.jsonl files")
    ap.add_argument("--pricing", default=str(DEFAULT_PRICING))
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--ttl-s", type=float, default=300.0, help="the default cache lifetime in seconds (5 min)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rates = json.loads(Path(a.pricing).read_text(encoding="utf-8"))[a.model]
    runs = load(a.paths)
    if not runs:
        print("lead_gaps: no lead calls found (lead-gaps-*.jsonl)", file=sys.stderr)
        return 1
    out = {run: summarise(calls, rates, a.ttl_s) for run, calls in sorted(runs.items())}
    if a.json:
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0
    for run, s in out.items():
        mins = a.ttl_s / 60
        print(f"{run}: {s['lead_calls']} lead calls, {s['gaps']} gaps - over {mins:g} min: {s['gaps_over_ttl']} "
              f"(idle over {mins:g} min: {s['idle_over_ttl']}), over 1 h: {s['gaps_over_1h']}; median "
              f"{s['gap_median_s']} s, p90 {s['gap_p90_s']} s, max {s['gap_max_s']} s")
        print(f"  lead calls after a gap over {mins:g} min that read less than half their prompt from the cache: "
              f"{s['cold_after_long_gap']} of {s['gaps_over_ttl']}")
        print(f"  lead at 1 h (estimate on these calls): saves ~${s['est_1h_saves_usd']:.4f} (re-writes after "
              f"{mins:g}-60 min gaps become reads), costs ~${s['est_1h_costs_usd']:.4f} (its other writes at the 1h "
              f"rate), net ~${s['est_1h_net_usd']:.4f}")
        verdict = ("no gap over the lifetime - the switch would only cost more" if s["gaps_over_ttl"] == 0 else
                   "the switch would have paid on this pilot" if s["est_1h_net_usd"] > 0 else
                   "the switch would not have paid on this pilot")
        print(f"  -> {verdict}; Karl decides (GUARD_LEAD_CACHE_1H=1 in the arm file turns it on)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
