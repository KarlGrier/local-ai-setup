#!/usr/bin/env python3
"""gap8_verdicts.py - round 22 gap 8 (10-22): the two checks that decide the switch (the user, 10-21: "if both checks
pass in the next gap ... switch 8080 mid-Phase 4 to P021 plus the two lossless ports"), written down before the gap.

  kernel PFY_MD           the 40-prompt yardstick (work/r22/pf_yardstick.py compare output; "long (2K-32K)" rows). A
                          prompt-kernel variant is rounding-level when it is within the spread of our own two rounding
                          references against the same reference build: the unfused prompt kernels (PF_FUSED=0) and the
                          served CPU share (STRATA_PREFILL_CPU_SHARE=0.4). The user, 10-22: beating one reference on a
                          single maximum or mean is a coin flip for an equally good kernel, so:
                            KL mean <= 1.10 x the larger of the two references' KL means,
                            KL max (the worst single position: one logit row per prompt) <= 1.5 x the worse of the two
                              references' KL max (still fails a gap 7 v2g-type spike, ~3x its references),
                            top-1 agreement (in prompts) at most ONE prompt below the lower of the two references';
                              two or more below fails (the user, 10-22).
                          Prints PASS/FAIL per variant and "CHOSEN v2=<1|3|2|none>": the first that passes of v2 (all
                          three kernels), v2d (down only), v2g (gate/up only) - in that order of speed (gap 7: -4.9 /
                          -2.5 / -2.0 % TTFT).
                          IMMA: immai8 against refi8, with unfusedi8 and cpusharei8 (both with the served int8 K/V) as
                          the two references, the same rule.
  cvsa DIR                C (spec 7 + STRATA_DRAFT_CUM) vs A (P021 today) from abrun's records (client decode tok/s):
                          PASS when C's W1-W3 mean is >= +3 % over A's AND C is ahead in at least 3 of the 4 passes
                          (the user, 10-22: W1 alone swings about +-10 %), AND neither the tool-call turns' nor the
                          research-shaped call's mean is more than 3 % slower. The pcie arms (PA = A without the forced
                          --pcie-frac 0, PC = C without it) are reported against A and C.
  pcvsc DIR               PC vs C under the same rule (the user, 10-22 12:2x: pcie pre-approved for this switch when PC
                          beats C by >= 3 % on W1-W3, ahead in >= 3 of 4 passes, tool-call turns and research call >= -3 %).
  kernelx PFY_MD NAME REFS  one variant (e.g. pcie) under the kernel rule against REFS (comma-separated).
"""
import json
import pathlib
import re
import statistics
import sys


TOL_MEAN, TOL_MAX = 1.10, 1.5


def kernel(md: str, only=None, only_refs=None) -> int:
    rows = {}
    for line in open(md):
        m = re.match(r"^(\S+)\s+long \(2K-32K\)\s+(\d+)\s+([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", line)
        if m:
            rows[m.group(1)] = {"n": int(m.group(2)), "top1": float(m.group(3)), "kl_mean": float(m.group(4)),
                                "kl_max": float(m.group(6))}

    def judge(name, refs):
        r, have = rows.get(name), [x for x in refs if x in rows]
        if not r or not have:
            print(f"{name}: no data ({'missing ' + name if not r else 'missing ' + ' and '.join(refs)})")
            return False
        mean_b = TOL_MEAN * max(rows[x]["kl_mean"] for x in have)
        max_b = TOL_MAX * max(rows[x]["kl_max"] for x in have)
        # top-1 in prompts (the table prints a percentage of n): at most one prompt below the lower reference
        hits = lambda x: round(rows[x]["top1"] * rows[x]["n"] / 100)
        top1_floor = min(hits(x) for x in have) - 1
        top1_b = 100 * top1_floor / r["n"]
        ok = r["kl_mean"] <= mean_b and r["kl_max"] <= max_b and hits(name) >= top1_floor
        refs_txt = ", ".join(f"{x} {rows[x]['top1']:.1f} % / {rows[x]['kl_mean']:.6f} / {rows[x]['kl_max']:.6f}" for x in have)
        print(f"{name}: top-1 {r['top1']:.1f} % = {hits(name)}/{r['n']} (>= {top1_floor}/{r['n']} = {top1_b:.1f} %), KL mean {r['kl_mean']:.6f} (<= {mean_b:.6f}), "
              f"KL max {r['kl_max']:.6f} (<= {max_b:.6f}) -> {'PASS' if ok else 'FAIL'}   [references (top-1 / KL mean / "
              f"KL max): {refs_txt}{'; MISSING ' + ', '.join(x for x in refs if x not in rows) if len(have) < len(refs) else ''}]")
        return ok
    if only:
        judge(only, tuple(only_refs.split(",")))
        return 0
    chosen = "none"
    for name, val in (("v2", "1"), ("v2d", "3"), ("v2g", "2")):
        if judge(name, ("unfused", "cpushare")) and chosen == "none":
            chosen = val
    print(f"CHOSEN v2={chosen}")
    print(f"IMMA {'PASS' if judge('immai8', ('unfusedi8', 'cpusharei8')) else 'FAIL'}")
    return 0


def cvsa(d: str, base="A", cand="C") -> int:
    recs = []
    for f in pathlib.Path(d).glob("*.jsonl"):
        if f.name.endswith(".wu.jsonl"):
            continue
        recs += [json.loads(x) for x in open(f) if x.strip()]
    # arm names: <arm><pass><n|a|r>, e.g. A1n, PC3r
    def sel(arm, kind, ids=None):
        out = {}
        for r in recs:
            m = re.match(r"^([A-Z]+)(\d)([nar])$", r["arm"])
            if not m or m.group(1) != arm or m.group(3) != kind or not r.get("decode_tps"):
                continue
            if ids and r["id"] not in ids:
                continue
            out.setdefault(int(m.group(2)), []).append(r["decode_tps"])
        return out
    W = ("W1-think", "W2-code", "W3-research")
    def mean_all(by):
        v = [x for xs in by.values() for x in xs]
        return statistics.mean(v) if v else float("nan")
    tab = {}
    for arm in ("A", "C", "PA", "PC"):
        tab[arm] = {k: sel(arm, *k2) for k, k2 in (("normal", ("n", W)), ("agent", ("a",)), ("research", ("r",)))}
    def pct(x, y):
        return 100 * (x / y - 1) if y == y and y else float("nan")
    print("| arm | W1-W3 tok/s (per pass) | mean | tool-call turns | research call |")
    print("|---|---|---|---|---|")
    for arm in ("A", "C", "PA", "PC"):
        t = tab[arm]
        per = " / ".join(f"{statistics.mean(v):.1f}" for _, v in sorted(t["normal"].items()))
        print(f"| {arm} | {per} | {mean_all(t['normal']):.1f} | {mean_all(t['agent']):.1f} | {mean_all(t['research']):.1f} |")
    a, c = tab[base], tab[cand]
    gain = pct(mean_all(c["normal"]), mean_all(a["normal"]))
    passes = [k for k in a["normal"] if k in c["normal"]]
    ahead = sum(statistics.mean(c["normal"][k]) > statistics.mean(a["normal"][k]) for k in passes)
    ag = pct(mean_all(c["agent"]), mean_all(a["agent"]))
    rs = pct(mean_all(c["research"]), mean_all(a["research"]))
    ok = gain >= 3 and len(passes) >= 4 and ahead >= 3 and ag >= -3 and rs >= -3
    print(f"{cand} vs {base}: W1-W3 {gain:+.1f} % (ahead in {ahead} of {len(passes)} passes; needs 3 of 4), tool-call turns {ag:+.1f} %, "
          f"research call {rs:+.1f} % (each needs >= -3 %) -> {'PASS' if ok else 'FAIL'}")
    tc = [r.get("tool_call_chars", 0) for r in recs if r["arm"].endswith("a")]
    print(f"tool-call turns: {len(tc)} replies, tool-call characters min {min(tc) if tc else 0} / median "
          f"{statistics.median(tc) if tc else 0} (gap 7: 45-105 tokens - these must carry code)")
    for x, b0 in (("PA", "A"), ("PC", "C")):
        print(f"{x} vs {b0} (no forced pcie-frac 0): W1-W3 {pct(mean_all(tab[x]['normal']), mean_all(tab[b0]['normal'])):+.1f} %, "
              f"tool-call turns {pct(mean_all(tab[x]['agent']), mean_all(tab[b0]['agent'])):+.1f} %, "
              f"research call {pct(mean_all(tab[x]['research']), mean_all(tab[b0]['research'])):+.1f} %  "
              f"(runs per prompt: {min((sum(1 for r in recs if re.match('^' + x + r'[0-9]n$', r['arm']) and r['id'] == w) for w in W), default=0)})")
    print(f"{'CVSA' if (base, cand) == ('A', 'C') else cand + 'VS' + base} {'PASS' if ok else 'FAIL'}")
    return 0


if __name__ == "__main__":
    m = sys.argv[1]
    sys.exit(kernel(sys.argv[2]) if m == "kernel" else kernel(sys.argv[2], sys.argv[3], sys.argv[4]) if m == "kernelx"
             else cvsa(sys.argv[2], "C", "PC") if m == "pcvsc" else cvsa(sys.argv[2]))
