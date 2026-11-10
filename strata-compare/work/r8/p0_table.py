#!/usr/bin/env python3
"""i0_table.py LABEL... — round 8 phase 0 (copy of r7 i0_table): the engine-level checks from logs/r8/prof/LABEL.out (generate --stats):
output hash (bit-identity of greedy runs), decode tok/s, rounds, ms per round, tokens per round, acceptance, window sizes,
prompt time, the drafter's prompt pass ("MTP prompt"), CPU experts per layer, pool ms per round."""
import hashlib
import re
import sys
from pathlib import Path

P = Path("/home/USER/ai-speed-testing/strata-compare/logs/r8/prof")


def parse(label):
    t = (P / f"{label}.out").read_text(errors="replace")
    d = {"label": label}
    m = re.search(r"^output\s*:\s*(.*)$", t, re.M)
    d["out"] = hashlib.sha256(m[1].strip().encode()).hexdigest()[:8] if m else "-"
    d["n_out"] = len(m[1].split()) if m else 0
    m = re.search(r"decode\s+(\d+) tokens in ([\d.]+) ms\s+->\s+([\d.]+) tok/s", t)
    if m:
        d["dec_tok"], d["dec_ms"], d["tps"] = int(m[1]), float(m[2]), float(m[3])
    m = re.search(r"prefill\s+(\d+) tokens in ([\d.]+) ms", t)
    if m:
        d["pf_tok"], d["pf_ms"] = int(m[1]), float(m[2])
    m = re.search(r"speculation\s+(\d+) rounds of (\d+), drafts accepted (\d+) of (\d+) \(([\d.]+)\), ([\d.]+) tokens per round", t)
    if m:
        d["rounds"], d["acc"], d["tpr"] = int(m[1]), float(m[5]), float(m[6])
    m = re.search(r"window sizes\s+(.*?)\s+\(", t)
    d["win"] = m[1] if m else ""
    m = re.search(r"MTP prompt ([\d.]+) ms", t)
    d["mtp_pf"] = float(m[1]) if m else None
    m = re.search(r"CPU experts ([\d.]+) distinct", t)
    d["cpu_exp"] = float(m[1]) if m else None
    m = re.search(r"CPU pool call ([\d.]+) ms/round", t)
    d["pool"] = float(m[1]) if m else None
    if d.get("rounds") and d.get("dec_ms"):
        d["ms_round"] = d["dec_ms"] / d["rounds"]
    return d


def main():
    f = lambda v, n=2: "–" if v is None else f"{v:.{n}f}"
    print(f"{'label':<22}{'out':>10}{'tok/s':>8}{'rounds':>7}{'ms/rnd':>8}{'tok/rnd':>8}{'accept':>7}{'CPU exp':>8}"
          f"{'pool ms':>8}{'prompt tok':>11}{'prompt ms':>10}{'MTP pf ms':>10}  windows")
    for L in sys.argv[1:]:
        try:
            d = parse(L)
        except FileNotFoundError:
            print(f"{L:<22} (missing)")
            continue
        print(f"{L:<22}{d['out']:>10}{f(d.get('tps'), 1):>8}{d.get('rounds', 0):>7}{f(d.get('ms_round')):>8}"
              f"{f(d.get('tpr')):>8}{f(d.get('acc'), 3):>7}{f(d.get('cpu_exp')):>8}{f(d.get('pool')):>8}"
              f"{d.get('pf_tok', 0):>11}{f(d.get('pf_ms'), 0):>10}{f(d.get('mtp_pf'), 1):>10}  {d['win']}")


if __name__ == "__main__":
    main()
