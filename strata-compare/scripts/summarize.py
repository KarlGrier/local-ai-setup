"""Summaries of results/runs.jsonl: median [min-max] n per config x scenario x item.

    summarize.py [--configs A,B,C0] [--sessions S1,S2] [--scenario speed] [--md]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, read_jsonl  # noqa: E402

ORDER = {"1k": 0, "4k": 1, "32k": 2, "64k": 3, "120k": 4}


def fmt(vals, nd=1):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "–"
    m = statistics.median(vals)
    if len(vals) == 1:
        return f"{m:.{nd}f} (n=1)"
    return f"{m:.{nd}f} [{min(vals):.{nd}f}–{max(vals):.{nd}f}] n={len(vals)}"


def valid(r):
    return not r.get("error") and r.get("ttft_s") is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="")
    ap.add_argument("--sessions", default="")
    ap.add_argument("--scenario", default="speed")
    a = ap.parse_args()
    runs = read_jsonl(RESULTS / "runs.jsonl")
    cfgs = a.configs.split(",") if a.configs else sorted({r["config"] for r in runs})
    sess = set(a.sessions.split(",")) if a.sessions else None
    groups = defaultdict(list)
    for r in runs:
        if r["scenario"] != a.scenario or r["config"] not in cfgs or (sess and r["session"] not in sess):
            continue
        groups[(r["config"], r["item"])].append(r)
    items = sorted({k[1] for k in groups}, key=lambda x: (ORDER.get(x, 99), x))
    print(f"### {a.scenario}  (median [min–max] n; invalid = error; S = swap during run)\n")
    print("| config | item | prompt tok | TTFT s | prompt tok/s | decode tok/s | gen tok | total s | notes |")
    print("|---|---|---|---|---|---|---|---|---|")
    for c in cfgs:
        for it in items:
            rs = groups.get((c, it), [])
            if not rs:
                continue
            ok = [r for r in rs if valid(r)]
            bad = len(rs) - len(ok)
            sw = sum(1 for r in ok if r.get("swap_out_pages") or r.get("swap_in_pages"))
            short = sum(1 for r in ok if (r.get("completion_tokens") or 0) < min(512, r.get("max_tokens", 512)))
            notes = ", ".join(x for x in [f"{bad} invalid" if bad else "", f"{sw} S" if sw else "",
                                          f"{short} gen<512" if short and a.scenario == "speed" else "",
                                          ", ".join(sorted({str(r.get('finish_reason')) for r in ok}))] if x)
            print(f"| {c} | {it} | {fmt([r.get('prompt_tokens') for r in ok], 0)} | {fmt([r['ttft_s'] for r in ok], 2)} | "
                  f"{fmt([r.get('prompt_tps_client') for r in ok])} | {fmt([r.get('decode_tps') for r in ok], 2)} | "
                  f"{fmt([r.get('completion_tokens') for r in ok], 0)} | {fmt([r['t_total_s'] for r in ok])} | {notes} |")


if __name__ == "__main__":
    main()
