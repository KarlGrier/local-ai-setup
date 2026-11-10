#!/usr/bin/env python3
"""rt_compare.py — round 5, phase 2a: compare the teacher-forced round-trip runs (work/r5/roundtrip.py outputs).

For each case (small, 40k):  direct1 vs direct2 (the residual of a static expert set: two fresh servers, same path),
park vs direct1 (a conversation parked behind a 64K paste + a short chat, then resumed), park-edit vs editref (an
earlier turn edited after the resume vs the same edit read directly). Per pair: tokens whose argmax differs, NLL
differences, drafter guesses (FDRAFT lines) that differ, and which parts of the engine's STATE_HASH match."""
import json
import sys
import re
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")


def load(tag, case):
    p = WS / f"results/r13/rt-{tag}-{case}.json"
    return json.loads(p.read_text())["forced"] if p.exists() else None


def hashes(s):
    return dict(re.findall(r"(\w+)=([0-9a-fx,]+)", s or ""))


def cmp(a, b):
    if not a or not b:
        return None
    n = min(len(a["argmax"]), len(b["argmax"]))
    am = sum(x != y for x, y in zip(a["argmax"][:n], b["argmax"][:n]))
    first = next((i for i in range(n) if a["argmax"][i] != b["argmax"][i]), None)
    dn = [abs(x - y) for x, y in zip(a["nll"][:n], b["nll"][:n])]
    nd = sum(x != y for x, y in zip(a["drafts"], b["drafts"]))
    ha, hb = hashes(a["state_hash"]), hashes(b["state_hash"])
    same = [k for k in ha if ha.get(k) == hb.get(k)]
    diff = [k for k in ha if ha.get(k) != hb.get(k)]
    return {"tokens": n, "argmax_changed": am, "first_change": first, "max_abs_dnll": max(dn) if dn else None,
            "mean_dnll": (sum(x - y for x, y in zip(a["nll"][:n], b["nll"][:n])) / n) if n else None,
            "nll_identical": sum(d == 0.0 for d in dn), "draft_lines": min(len(a["drafts"]), len(b["drafts"])),
            "drafts_changed": nd, "state_same": same, "state_diff": diff,
            "prompt_a": a["prompt"], "prompt_b": b["prompt"]}


def main():
    global PFX
    PFX = sys.argv[1] if len(sys.argv) > 1 else "r8-ours"
    print(f"### round trip, tags {PFX}-*\n")
    print("| case | comparison | tokens | argmax changed (first at) | NLL identical | max abs ΔNLL | mean ΔNLL | "
          "drafter guesses changed | state hash: same / different | prompt (tokens, reused, read) a vs b |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for case in ("small", "40k"):
        d1, d2, pk, er = (load(t, case) for t in (f"{PFX}-direct1", f"{PFX}-direct2", f"{PFX}-park", f"{PFX}-editref"))
        pairs = [("direct vs direct (residual)", d1 and d1.get("resume"), d2 and d2.get("resume")),
                 ("parked → resumed vs direct", pk and pk.get("resume"), d1 and d1.get("resume")),
                 ("resumed + edit vs edit read directly", pk and pk.get("edit"), er and er.get("edit"))]
        for name, a, b in pairs:
            r = cmp(a, b)
            if r is None:
                print(f"| {case} | {name} | – | (missing) | | | | | | |")
                continue
            print(f"| {case} | {name} | {r['tokens']} | {r['argmax_changed']} ({r['first_change']}) | "
                  f"{r['nll_identical']} | {r['max_abs_dnll']:.2e} | {r['mean_dnll']:+.2e} | "
                  f"{r['drafts_changed']} of {r['draft_lines']} | {','.join(r['state_same']) or '–'} / "
                  f"{','.join(r['state_diff']) or '–'} | {r['prompt_a']} vs {r['prompt_b']} |")


if __name__ == "__main__":
    main()
