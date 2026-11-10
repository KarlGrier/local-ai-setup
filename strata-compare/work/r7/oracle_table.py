#!/usr/bin/env python3
"""oracle_table.py BASE_LABEL[,BASE_LABEL...] ARM_LABEL[,...] ... — round 7 item 1: per-window times of oracle arms vs a
baseline, from the oracle's per-window logs (tmp/r7/oracle/LABEL.csv: w,T,pos0,ms,aligned,calls,cpu_true,staged,used,
warmed; ms = graph launch -> the window's GPU work and copies done, i.e. the 48 layers incl. every CPU phase).

Only windows that are ALIGNED in every compared run are used (same routing = same trajectory, so the same window sizes
and the same experts); a window index is kept only if it is aligned in all arms (the baseline logs are recordings, so
they are aligned by definition).  Groups of labels separated by commas are repeats: their per-window times are averaged.
Prints, per window size T and overall (weighted by the baseline's window-size mix): mean ms per window, the saving vs
the baseline, and the arm's staged/used/CPU expert counts."""
import csv
import statistics
import sys
from pathlib import Path

D = Path("/home/USER/ai-speed-testing/strata-compare/tmp/r7/oracle")


def load(label):
    rows = {}
    for r in csv.DictReader(open(D / f"{label}.csv")):
        rows[int(r["w"])] = {k: float(v) for k, v in r.items()}
    return rows


def group(spec):
    runs = [load(x) for x in spec.split(",")]
    common = set.intersection(*(set(r) for r in runs))
    out = {}
    for w in common:
        rs = [r[w] for r in runs]
        if any(x["T"] != rs[0]["T"] for x in rs):
            continue
        out[w] = dict(rs[0])
        out[w]["ms"] = statistics.mean(x["ms"] for x in rs)
        out[w]["aligned"] = min(x["aligned"] for x in rs)
        out[w]["n"] = len(rs)
    return out


def main():
    specs = sys.argv[1:]
    all_windows = "--all" in specs     # teacher-forced runs: the same windows by construction (only rare router near-ties differ)
    specs = [x for x in specs if x != "--all"]
    groups = [group(s) for s in specs]
    base = groups[0]
    keep = set(base)
    for g in groups[1:]:
        keep &= {w for w, r in g.items() if all_windows or r["aligned"] >= 1}
    keep = sorted(w for w in keep if w > 0)   # window 0 holds the first-use kernel loading
    Ts = sorted({int(base[w]["T"]) for w in keep})
    mix = {T: sum(1 for w in keep if base[w]["T"] == T) for T in Ts}
    print(f"windows compared: {len(keep)} (aligned in every arm, window 0 excluded); mix " +
          " ".join(f"T{T}:{mix[T]}" for T in Ts))
    hdr = f"{'arm':<40}" + "".join(f"{'T' + str(T) + ' ms':>10}" for T in Ts) + f"{'all ms':>9}{'saving':>9}" \
          f"{'CPU/win':>9}{'staged':>8}{'used':>7}{'warmed':>8}"
    print(hdr)
    b_all = None
    for spec, g in zip(specs, groups):
        cells, tot = [], 0.0
        for T in Ts:
            v = [g[w]["ms"] for w in keep if base[w]["T"] == T and w in g]
            m = statistics.mean(v) if v else float("nan")
            cells.append(m)
            tot += m * mix[T]
        tot /= max(1, sum(mix.values()))
        if b_all is None:
            b_all = tot
        n = max(1, len(keep))
        cpu = sum(g[w]["cpu_true"] for w in keep if w in g) / n
        stg = sum(g[w]["staged"] for w in keep if w in g) / n
        used = sum(g[w]["used"] for w in keep if w in g) / n
        warm = sum(g[w]["warmed"] for w in keep if w in g) / n
        sav = 100.0 * (b_all - tot) / b_all
        print(f"{spec[:40]:<40}" + "".join(f"{c:>10.3f}" for c in cells) + f"{tot:>9.3f}{sav:>8.1f}%" +
              f"{cpu:>9.1f}{stg:>8.1f}{used:>7.1f}{warm:>8.1f}")
    # the window-level spread of the baseline repeats, as the noise reference
    b_runs = specs[0].split(",")
    if len(b_runs) >= 2:
        rs = [load(x) for x in b_runs]
        d = []
        for w in keep:
            if all(w in r for r in rs):
                d.append(100.0 * (rs[1][w]["ms"] - rs[0][w]["ms"]) / rs[0][w]["ms"])
        if d:
            print(f"baseline repeat 2 vs 1: mean {statistics.mean(d):+.2f} % per window (sd {statistics.pstdev(d):.1f} %)")


if __name__ == "__main__":
    main()
