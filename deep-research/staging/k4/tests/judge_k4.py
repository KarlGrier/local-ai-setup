#!/usr/bin/env python3
"""After the GPU replays (README "Later"): K4 caught? K1 kept? which pairs to judge by hand? Reads only
results/bench2/fixes/replays/<label>/consistency.json and calls.json (no model, no GPU, no network).

  .venv/bin/python -I staging/k4/tests/judge_k4.py b-k4-full:b-f5c-full b-k4-fixes:b-f5c-fixes

Each argument is NEW[:BASE]. Per replay:
  K4      a pair that sets a K4 claim ("the default --dspark auto loads the 8 GB drafter", "freeing the 8 GB drafter",
          "--dspark none ... recovers the measured 8-16 % loss", "mandatory first action") against the 1.5x rule (the
          other statement, or the pair's why / fix / evaluation, says the drafter is not loaded here):
          strong = the claim is the one marked wrong, weak = not settled, reversed = the claim is said to hold
  K4-rev  a pair that marks a correct "DSpark is auto-disabled / not loaded on this rig" statement wrong (a false alarm;
          the run-full-fixes report gets K4 right)
  K1      a pair that sets a layer-major claim against the single-device gate
  pairs   by step (main pass / focused / rule), and which are new against BASE (no quote shared) - judge these by hand
  rules   every rule the focused step evaluated, with its arithmetic and the code recheck
  time    the consistency calls' seconds against EST["consist"] x the report scale
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
REP = WS / "results" / "bench2" / "fixes" / "replays"
EST_CONSIST = 900

K4_CLAIM = re.compile(r"default --dspark auto loads|auto loads the 8 gb|freeing the 8 gb dspark drafter|"
                      r"recovers? the measured -?8\s*(?:-|to)\s*-?16|--dspark none.{0,60}mandatory first action|"
                      r"\+8\s*-\s*16 ?% net")
K4_RULE = re.compile(r"1\.5\s*x|n_mtp\s*=\s*0|not loaded|auto[- ]?disabl|auto-off|does not load|doesn't load|"
                     r"never loads?|leaves? the drafter out|not load(?:ed)? (?:the drafter|it)|drafter (?:is )?off")
K4_REV = re.compile(r"dspark.{0,80}(?:auto[- ]?disabl|not loaded|auto-off|correctly disabled|never loaded)|"
                    r"(?:auto[- ]?disabl|not loaded|never loaded).{0,80}dspark")
K1_CLAIM = re.compile(r"layer[-_ ]major|lm_begin")
K1_GATE = re.compile(r"single[- ]device|one device|single[- ]gpu|one gpu|exactly one|devs\.size\(\) != 1|"
                     r"two[- ]gpu split|2-gpu split|not implemented")


def norm(s) -> str:
    s = str(s or "").lower()
    for a, b in (("`", ""), ("*", ""), ("–", "-"), ("—", "-"), ("−", "-"), ("×", "x"), ("’", "'")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def load(label: str) -> tuple[dict | None, dict | None]:
    d = REP / label
    co = json.loads((d / "consistency.json").read_text()) if (d / "consistency.json").exists() else None
    ca = json.loads((d / "calls.json").read_text()) if (d / "calls.json").exists() else None
    return co, ca


def wrong_side(c: dict) -> str:
    r = str(c.get("right") or "unclear").lower()
    return "b" if r == "a" else "a" if r == "b" else ""


def extra(c: dict) -> str:
    ev = c.get("evaluation") if isinstance(c.get("evaluation"), dict) else {}
    return norm(" ".join([str(c.get("why") or ""), str(c.get("fix") or "")] + [str(v) for v in ev.values()]))


def k4(c: dict) -> str:
    """'' or strong / weak / reversed."""
    for side, other in (("a", "b"), ("b", "a")):
        q, o = norm(c.get("quote_" + side)), norm(c.get("quote_" + other))
        if K4_CLAIM.search(q) and not K4_CLAIM.search(o) and (K4_RULE.search(o) or K4_RULE.search(extra(c))):
            w = wrong_side(c)
            return "strong" if w == side else "weak" if not w else "reversed"
    return ""


def k4_rev(c: dict) -> bool:
    w = wrong_side(c)
    return bool(w) and bool(K4_REV.search(norm(c.get("quote_" + w))))


def k1(c: dict) -> bool:
    a, b = norm(c.get("quote_a")), norm(c.get("quote_b"))
    return bool((K1_CLAIM.search(a) or K1_CLAIM.search(b)) and (K1_GATE.search(a) or K1_GATE.search(b)
                                                                  or K1_GATE.search(extra(c))))


def judge(new: str, base: str | None) -> dict:
    co, ca = load(new)
    if co is None:
        print(f"== {new}: no consistency.json")
        return {}
    cs = [c for c in co.get("contradictions") or [] if isinstance(c, dict)]
    bq = set()
    if base:
        bco, _ = load(base)
        for c in (bco or {}).get("contradictions") or []:
            if isinstance(c, dict):
                bq |= {norm(c.get("quote_a"))[:80], norm(c.get("quote_b"))[:80]}
    out = {"label": new, "pairs": len(cs), "steps": {}, "k4": [], "k4_rev": [], "k1": [], "new": []}
    print(f"== {new}" + (f" (base {base})" if base else ""))
    for i, c in enumerate(cs):
        step = c.get("step") or "main"
        out["steps"][step] = out["steps"].get(step, 0) + 1
        tags = []
        if k4(c):
            out["k4"].append((i, k4(c)))
            tags.append("K4 " + k4(c))
        if k4_rev(c):
            out["k4_rev"].append(i)
            tags.append("K4-REVERSED FALSE ALARM")
        if k1(c):
            out["k1"].append(i)
            tags.append("K1")
        is_new = bool(base) and norm(c.get("quote_a"))[:80] not in bq and norm(c.get("quote_b"))[:80] not in bq
        if is_new and not tags:
            out["new"].append(i)
            tags.append("new: judge")
        print(f"  [{i}] {step:7} {c.get('setting') or '':22} right={c.get('right')} {' / '.join(tags)}")
        print(f"       A: {str(c.get('quote_a'))[:170]}")
        print(f"       B: {str(c.get('quote_b'))[:170]}")
        if c.get("why"):
            print(f"       why: {str(c.get('why'))[:220]}")
        if isinstance(c.get("evaluation"), dict):
            ev = c["evaluation"]
            print(f"       rule applied: {str(ev.get('arithmetic'))[:200]} -> holds {ev.get('holds')}: "
                  f"{str(ev.get('outcome'))[:150]}")
    rc = co.get("rule_checks") or []
    print(f"  rules evaluated: {len(rc)} (unknown: {sum(1 for r in rc if r.get('holds') == 'unknown')}; arithmetic not "
          f"recomputing: {sum(1 for r in rc if (r.get('recheck') or {}).get('wrong'))}); focused replies unparsed: "
          f"{co.get('focused_unparsed', 0)}")
    for r in rc:
        bad = (r.get("recheck") or {}).get("wrong")
        print(f"   - {r.get('setting')}: {str(r.get('condition'))[:90]} | {str(r.get('arithmetic'))[:140]} | holds "
              f"{r.get('holds')} -> {str(r.get('outcome'))[:100]} | claims no/yes "
              f"{sum(1 for x in r.get('claims') or [] if x.get('agrees') == 'no')}/"
              f"{sum(1 for x in r.get('claims') or [] if x.get('agrees') == 'yes')}" + (f" | RECHECK {bad}" if bad else ""))
    if ca:
        cons = [c for c in ca.get("calls") or [] if c.get("kind") == "consist"]
        sec = sum(c.get("seconds") or 0 for c in cons)
        scale = max(0.15, min(2.0, ((cons[0].get("prompt_tokens") or 0) - 2000) / 45000)) if cons else 1.0
        out["seconds"], out["est"] = round(sec), round(EST_CONSIST * scale)
        print(f"  time: {len(cons)} consist calls, {sec:.0f} s (estimate {EST_CONSIST} x ~{scale:.2f} = "
              f"{EST_CONSIST * scale:.0f} s); out chars {[c.get('out_chars') for c in cons]}")
    k4s = [s for _, s in out["k4"]]
    text = norm((REP / new / "input.md").read_text(encoding="utf-8")) if (REP / new / "input.md").exists() else ""
    has_k4, has_k1 = bool(K4_CLAIM.search(text)), bool(K1_CLAIM.search(text))   # does the report make the error?
    out["k4_state"] = ("strong" if "strong" in k4s else "weak" if "weak" in k4s else "reversed" if k4s
                       else "NOT caught" if has_k4 else "n/a (no K4 claim in the report)")
    out["k1_state"] = "kept" if out["k1"] else "MISSING" if has_k1 else "n/a (no layer-major in the report)"
    print(f"  SUMMARY {new}: pairs {len(cs)} {out['steps']}; K4 {out['k4_state']} {out['k4']}; K4-reversed false "
          f"alarms {out['k4_rev']}; K1 {out['k1_state']} {out['k1']}; new pairs to judge "
          f"{out['new'] if base else '(no base given)'}")
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    for a in argv:
        new, _, base = a.partition(":")
        judge(new, base or None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
