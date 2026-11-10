#!/usr/bin/env python3
"""mtp_accept.py - the drafter check's table: our drafter (arm A) vs the converted one (arm B), from the counters the
engine already prints. Read-only on the logs; CPU only. results/qwen4-kit/mtp-fallback/CHECK-PLAN.md says how the runs
are made.

  mtp_accept.py cli A_LABEL B_LABEL [--runs x-math,x-code,...]
        bringup/out/logs/prof/<LABEL>-<run>.out (strata generate --stats; exact7.sh / run.sh labels): output hash,
        "speculation N rounds of W, drafts accepted A of D", "accepted per round", "suffix drafts", decode tok/s;
        the slot counts from the .err ("expert cache N slots", "CUDA1: N additional experts")
  mtp_accept.py log ELOG_A[:OFFSET[:END]] ELOG_B[:OFFSET[:END]]
        engine logs of served runs (byte ranges: with_server.sh / abarm.sh offsets): every
        "strata serve: ... generated in ... (X tok/s), drafts accepted A of D, ..., W windows" and "suffix drafts:" line

Verdict rules (CHECK-PLAN.md): greedy outputs identical (hashes) and slots matched - mandatory (the target verifies
every draft, so no drafter may change a greedy output); acceptance, pooled over the greedy runs and over the sampled /
served runs separately: |rate B - rate A| <= 1.5 points and two-proportion |z| < 2 on the MTP draft counts (the suffix
drafter's counts taken out); tokens per round within 3 %. A byte-identical drafter must give delta 0 and every hash
equal, the sampled ones included (--identical).
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

PROF = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
RUNS = ["x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k"]


def parse_cli(label):
    p = PROF / f"{label}.out"
    t = p.read_text(errors="replace")
    d = {"label": label}
    m = re.search(r"^output\s*:\s*(.*)$", t, re.M)
    d["out"] = hashlib.sha256(m[1].strip().encode()).hexdigest()[:8] if m else "-"
    m = re.search(r"speculation\s+(\d+) rounds of (\d+), drafts accepted (\d+) of (\d+) \(([\d.]+)\), ([\d.]+) tokens per round", t)
    if m:
        d.update(rounds=int(m[1]), acc=int(m[3]), drafted=int(m[4]), tpr=float(m[6]))
    m = re.search(r"suffix drafts\s+(\d+) windows, drafts accepted (\d+) of (\d+)", t)
    d["sfx_acc"], d["sfx_drafted"] = (int(m[2]), int(m[3])) if m else (0, 0)
    m = re.search(r"accepted per round\s+(.*)$", t, re.M)
    d["per_round"] = {int(a): int(b) for a, b in re.findall(r"(\d+):(\d+)", m[1])} if m else {}
    m = re.search(r"decode\s+(\d+) tokens in ([\d.]+) ms\s+->\s+([\d.]+) tok/s", t)
    d["tps"] = float(m[3]) if m else None
    m = re.search(r"mtp\s+([\d.]+) ms/round drafting", t)
    d["draft_ms"] = float(m[1]) if m else None
    try:
        e = (PROF / f"{label}.err").read_text(errors="replace")
        s = re.findall(r"expert cache (\d+) slots", e)
        h = re.findall(r"CUDA1: (\d+) additional experts", e)
        dl = re.findall(r"draft layer loaded, (\d+) MiB", e)
        d["slots"] = (int(s[-1]) if s else 0, int(h[-1]) if h else 0)
        d["drafter_mib"] = int(dl[-1]) if dl else None
    except OSError:
        d["slots"], d["drafter_mib"] = None, None
    # the MTP drafter's own counts: the round totals less the suffix drafter's
    if "acc" in d:
        d["mtp_acc"], d["mtp_drafted"] = d["acc"] - d["sfx_acc"], d["drafted"] - d["sfx_drafted"]
    return d


SERVE = re.compile(r"strata serve: prompt (\d+) tokens .*?, (\d+) generated in (\d+) ms \(([\d.]+) tok/s\), drafts accepted "
                   r"(\d+) of (\d+), \d+ checkpoints, (\d+) windows")
SFX = re.compile(r"strata serve: suffix drafts: (\d+) windows, (\d+) of (\d+) drafts accepted")


def parse_log(spec):
    parts = spec.split(":")
    path, off = Path(parts[0]), int(parts[1]) if len(parts) > 1 and parts[1] else 0
    end = int(parts[2]) if len(parts) > 2 and parts[2] else None
    with open(path, "rb") as f:
        f.seek(off)
        t = f.read(None if end is None else end - off).decode(errors="replace")
    reqs = []
    lines = t.splitlines()
    for i, line in enumerate(lines):
        m = SERVE.search(line)
        if not m:
            continue
        r = {"prompt": int(m[1]), "gen": int(m[2]), "ms": int(m[3]), "tps": float(m[4]), "acc": int(m[5]),
             "drafted": int(m[6]), "windows": int(m[7]), "sfx_acc": 0, "sfx_drafted": 0}
        for nxt in lines[i + 1:i + 4]:                    # the request's own suffix line follows it
            s = SFX.search(nxt)
            if s:
                r["sfx_acc"], r["sfx_drafted"] = int(s[2]), int(s[3])
                break
            if SERVE.search(nxt):
                break
        r["mtp_acc"], r["mtp_drafted"] = r["acc"] - r["sfx_acc"], r["drafted"] - r["sfx_drafted"]
        reqs.append(r)
    return reqs


def ztest(a1, n1, a2, n2):
    if not n1 or not n2:
        return None
    p = (a1 + a2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0
    return ((a2 / n2) - (a1 / n1)) / se if se else 0.0


def rate(a, n):
    return a / n if n else float("nan")


def cmd_cli(a):
    runs = a.runs.split(",") if a.runs else RUNS
    ok = True
    print(f"{'run':10s} {'A out':>9s} {'B out':>9s} {'same':>5s}  {'A acc/drafted':>15s} {'B acc/drafted':>15s} {'A rate':>7s} "
          f"{'B rate':>7s} {'delta':>7s} {'A tok/r':>7s} {'B tok/r':>7s} {'A tok/s':>8s} {'B tok/s':>8s}  slots A / B")
    tot = {"g": [0, 0, 0, 0], "s": [0, 0, 0, 0]}
    tpr = {"A": [], "B": []}
    for r in runs:
        try:
            A, B = parse_cli(f"{a.a}-{r}"), parse_cli(f"{a.b}-{r}")
        except FileNotFoundError as e:
            print(f"{r:10s} missing: {e.filename}")
            ok = False
            continue
        greedy = r.startswith("x-") or a.all_greedy
        same = A["out"] == B["out"]
        ra, rb = rate(A.get("mtp_acc", 0), A.get("mtp_drafted", 0)), rate(B.get("mtp_acc", 0), B.get("mtp_drafted", 0))
        k = "g" if greedy else "s"
        for i, v in enumerate((A.get("mtp_acc", 0), A.get("mtp_drafted", 0), B.get("mtp_acc", 0), B.get("mtp_drafted", 0))):
            tot[k][i] += v
        if A.get("tpr") and B.get("tpr"):
            tpr["A"].append(A["tpr"])
            tpr["B"].append(B["tpr"])
        flag = ""
        if greedy and not same:
            flag, ok = " GREEDY OUTPUT DIFFERS", False
        if A.get("mtp_drafted", 0) >= 500 and abs(rb - ra) > 0.05:
            flag += " (info: >5 points on this run)"
        if a.identical and not same:
            flag += " (--identical: every hash must match)"
            ok = False
        if A.get("slots") != B.get("slots"):
            flag += " SLOTS DIFFER"
            ok = False
        print(f"{r:10s} {A['out']:>9s} {B['out']:>9s} {'=' if same else 'DIFF':>5s}  "
              f"{A.get('mtp_acc', 0):>6}/{A.get('mtp_drafted', 0):<8} {B.get('mtp_acc', 0):>6}/{B.get('mtp_drafted', 0):<8} "
              f"{ra:7.3f} {rb:7.3f} {100 * (rb - ra):+6.2f}p {A.get('tpr', 0):7.2f} {B.get('tpr', 0):7.2f} "
              f"{A.get('tps') or 0:8.1f} {B.get('tps') or 0:8.1f}  {A.get('slots')} / {B.get('slots')}{flag}")
    for k, nm in (("g", "greedy"), ("s", "sampled")):
        a1, n1, a2, n2 = tot[k]
        if not (n1 and n2):
            continue
        d = rate(a2, n2) - rate(a1, n1)
        z = ztest(a1, n1, a2, n2)
        good = (d == 0 and a1 == a2) if a.identical else (abs(d) <= 0.015 and abs(z) < 2)
        ok = ok and good
        print(f"{nm:8s} pooled MTP acceptance A {rate(a1, n1):.4f} ({a1}/{n1})  B {rate(a2, n2):.4f} ({a2}/{n2})  "
              f"delta {100 * d:+.2f} points, z {z:+.2f}  -> {'OK' if good else 'FAIL'}")
    if tpr["A"]:
        ga, gb = sum(tpr["A"]) / len(tpr["A"]), sum(tpr["B"]) / len(tpr["B"])
        good = abs(gb / ga - 1) <= 0.03
        ok = ok and good
        print(f"tokens per round: A {ga:.3f}  B {gb:.3f}  ({100 * (gb / ga - 1):+.1f} %) -> {'OK' if good else 'FAIL'}")
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def cmd_log(a):
    A, B = parse_log(a.a), parse_log(a.b)
    ok = True
    for nm, R in (("A", A), ("B", B)):
        acc, dr = sum(r["mtp_acc"] for r in R), sum(r["mtp_drafted"] for r in R)
        gen, ms = sum(r["gen"] for r in R), sum(r["ms"] for r in R)
        print(f"arm {nm}: {len(R)} requests, MTP drafts accepted {acc} of {dr} ({rate(acc, dr):.4f}), suffix "
              f"{sum(r['sfx_acc'] for r in R)} of {sum(r['sfx_drafted'] for r in R)}, {gen} tokens in {ms / 1000:.1f} s "
              f"({gen / (ms / 1000) if ms else 0:.1f} tok/s)")
    if len(A) != len(B):
        print(f"WARNING: {len(A)} vs {len(B)} requests - not the same workload")
        ok = False
    a1, n1 = sum(r["mtp_acc"] for r in A), sum(r["mtp_drafted"] for r in A)
    a2, n2 = sum(r["mtp_acc"] for r in B), sum(r["mtp_drafted"] for r in B)
    z, d = ztest(a1, n1, a2, n2), rate(a2, n2) - rate(a1, n1)
    good = z is not None and abs(z) < 2 and abs(d) <= 0.015
    print(f"pooled MTP acceptance delta {100 * d:+.2f} points, z {z if z is None else round(z, 2)} -> {'OK' if good else 'FAIL'}")
    for i, (x, y) in enumerate(zip(A, B)):
        print(f"  req {i:2d}: prompt {x['prompt']:>6}/{y['prompt']:<6} A {x['mtp_acc']:>5}/{x['mtp_drafted']:<5} "
              f"B {y['mtp_acc']:>5}/{y['mtp_drafted']:<5} A {x['tps']:6.1f} B {y['tps']:6.1f} tok/s")
    ok = ok and good
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("cli")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--runs")
    c.add_argument("--all-greedy", action="store_true", help="treat every run as greedy (hash must match)")
    c.add_argument("--identical", action="store_true", help="a byte-identical drafter: every hash and count must match")
    lg = sub.add_parser("log")
    lg.add_argument("a")
    lg.add_argument("b")
    a = ap.parse_args()
    if a.cmd == "cli":
        return cmd_cli(a)
    if a.cmd == "log":
        return cmd_log(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
