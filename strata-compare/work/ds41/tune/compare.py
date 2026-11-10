#!/usr/bin/env python3
"""compare.py REFDIR NEWDIR - 10-24 DeepSeek-V4.1 tuning round: keep or drop one change (the user: "Change one thing at a
time; keep a change only if it gains >=3% on decode or >=5% on prompt reading beyond pass-to-pass noise").
noise = the larger of the two arms' spreads (half the range of the pass means for decode; of the three prompts' tok/s for
P4K / P20K), in % of the mean. A gain counts when gain - noise >= the threshold; a loss when -gain - noise >= it.
Keep when decode gains (and neither prompt size loses >=5 % beyond noise), or when a prompt size gains and decode loses
nothing beyond its noise. A run that hit a guard, a soft stop or has no numbers is dropped. Prints one JSON line.
"""
import json
import os
import sys


def load(d):
    try:
        return json.load(open(f"{d}/arm.json"))
    except (OSError, ValueError):
        return None


def main():
    ref, new = sys.argv[1], sys.argv[2]
    a, b = load(ref), load(new)
    bad = [x for x in ("GUARD", "SOFTSTOP") if os.path.exists(f"{new}/{x}")]
    if not a or not b or "decode" not in b or bad or b["decode"]["n"] < 6:
        print(json.dumps({"keep": False, "why": f"no clean numbers ({', '.join(bad) or 'missing'})"})); return
    r = {"keep": False}
    g = 100 * (b["decode"]["mean"] / a["decode"]["mean"] - 1)
    n = max(a["decode"]["spread_pct"] or 0, b["decode"]["spread_pct"] or 0)
    r["decode"] = {"ref": a["decode"]["mean"], "new": b["decode"]["mean"], "gain_pct": round(g, 2), "noise_pct": round(n, 2)}
    dec_up, dec_down, dec_any_down = g - n >= 3, -g - n >= 3, -g - n > 0
    p_up, p_down = [], []
    for k in ("P4K", "P20K"):
        if k in a and k in b:
            pg = 100 * (b[k]["mean"] / a[k]["mean"] - 1)
            pn = max(a[k]["spread_pct"] or 0, b[k]["spread_pct"] or 0)
            r[k] = {"ref": a[k]["mean"], "new": b[k]["mean"], "gain_pct": round(pg, 2), "noise_pct": round(pn, 2),
                    "ssd_gb_ref": a[k].get("disk_gb_mean"), "ssd_gb_new": b[k].get("disk_gb_mean")}
            if pg - pn >= 5: p_up.append(k)
            if -pg - pn >= 5: p_down.append(k)
    if dec_up and not p_down:
        r["keep"], r["why"] = True, "decode gain beyond noise"
    elif p_up and not dec_any_down:
        r["keep"], r["why"] = True, f"prompt gain beyond noise ({', '.join(p_up)}), decode not lower beyond noise"
    else:
        r["why"] = ("decode loss beyond noise" if dec_down else "prompt loss beyond noise" if p_down else
                    "trade-off: prompt up, decode down" if p_up else "no gain beyond noise")
    print(json.dumps(r))


if __name__ == "__main__":
    main()
