#!/usr/bin/env python3
"""After the GPU step (README "Later"): the Fix 1b replays' marks against fix1-judge's verdicts on the 68 old marks.
Reads only results/bench2/fixes/replays/<label>/versioncheck.json and fix1-judge/judged.jsonl (no model, no GPU).

  .venv/bin/python -I staging/fix1b/tests/compare_replays.py [--prefix b-f1b-]

Per replay: the 11 false marks - cleared (no longer flagged) or still flagged; the 56 right marks - still flagged or
lost; new flags (names not flagged before) to judge by hand; the p4s6 o01 / o02 flags old vs new.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
REP = WS / "results" / "bench2" / "fixes" / "replays"
BAD = {"other-engine", "other-version", "other-project", "not-found", "launcher-only"}


def flagged(label: str) -> dict[str, dict]:
    f = REP / label / "versioncheck.json"
    if not f.exists():
        return {}
    res = json.loads(f.read_text())
    out = {}
    for r in res.get("results") or []:
        use = str(r.get("use") or "").lower()
        if use in ("recommended", "described") and r.get("kind") in BAD:
            out[str(r["name"]).strip('"')] = r
    return out


def main() -> int:
    prefix = sys.argv[sys.argv.index("--prefix") + 1] if "--prefix" in sys.argv else "b-f1b-"
    judged = [json.loads(x) for x in (WS / "results/bench2/fixes/fix1-judge/judged.jsonl").read_text().splitlines() if x]
    tot = {"false cleared": 0, "false kept": 0, "right kept": 0, "right lost": 0, "new": 0}
    for old in ("b-f1-jan1024", "b-f1-full", "b-f1-fixes", "b-f1-p4s6o01-code", "b-f1-p4s6o02-code"):
        new = prefix + old[len("b-f1-"):]
        nf, of = flagged(new), flagged(old)
        if not (REP / new / "versioncheck.json").exists():
            print(f"{new}: not there yet")
            continue
        print(f"== {new} (was {old}): {len(of)} -> {len(nf)} flagged")
        for j in (j for j in judged if j["replay"] == old):
            n = j["name"]
            now = nf.get(n)
            if j["verdict"] == "false":
                k = "false kept" if now else "false cleared"
            elif j["verdict"] == "correct":
                k = "right kept" if now else "right lost"
            else:
                continue
            tot[k] += 1
            if k in ("false kept", "right lost"):
                print(f"  {k}: {n} ({j['kind']} -> {now['kind'] if now else 'not flagged'}; judge: {j['why'][:120]})")
        for n, r in nf.items():
            if n not in of:
                tot["new"] += 1
                print(f"  NEW flag to judge: {n} ({r['kind']}, {r.get('use')}): {r.get('note')}")
    print(tot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
