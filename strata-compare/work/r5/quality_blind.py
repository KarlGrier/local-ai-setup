#!/usr/bin/env python3
"""quality_blind.py export|unblind — round 5, phase 5: blind grading of the quality runs (same IQ3_S file, two engines).

  export    results/outputs/{L5,S5}/quality_<id>_r<rep>_*.json (llama.cpp and Strata, 3 sampled runs each) ->
            results/r5/blind/<id>/answer-<A..F>.md with the FINAL ANSWER only (the grading key grades final answers),
            labels shuffled per prompt with a random seed; the key goes to results/r5/blind-key.json (a separate file,
            not read while grading). Also writes results/r5/blind/INDEX.md (lengths, whether an answer was cut at the cap).
  unblind   reads results/r5/blind-scores.json {"<id>": {"A": score, ...}} (scores out of 20 from
            ~/ai-speed-testing/GRADING_KEY.md) + the key -> mean and spread per engine, per prompt and in total."""
import json
import os
import random
import statistics
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = WS / "results/r5/blind"
KEY = WS / "results/r5/blind-key.json"
SCORES = WS / "results/r5/blind-scores.json"
ENGINES = {"L5": "llama.cpp", "S5": "Strata"}


def load(cfg):
    out = {}
    for p in sorted((WS / "results/outputs" / cfg).glob("quality_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out.setdefault(r["item"], {})[int(r["rep"])] = r
    return out


def export():
    seed = int.from_bytes(os.urandom(4), "little")
    rng = random.Random(seed)
    key = {"seed": seed, "key": {}}
    data = {cfg: load(cfg) for cfg in ENGINES}
    items = sorted(set().union(*[set(d) for d in data.values()]))
    index = ["| prompt | label | answer chars | finish |", "|---|---|---|---|"]
    for item in items:
        entries = [(cfg, rep, r) for cfg, d in data.items() for rep, r in sorted(d.get(item, {}).items())]
        labels = [chr(ord("A") + i) for i in range(len(entries))]
        rng.shuffle(entries)
        (OUT / item).mkdir(parents=True, exist_ok=True)
        key["key"][item] = {}
        for lab, (cfg, rep, r) in zip(labels, entries):
            ans = (r.get("content") or "").strip()
            (OUT / item / f"answer-{lab}.md").write_text(f"# {item} — answer {lab}\n\n{ans}\n", encoding="utf-8")
            key["key"][item][lab] = {"engine": ENGINES[cfg], "config": cfg, "rep": rep,
                                     "finish": r.get("finish_reason"), "completion_tokens": r.get("completion_tokens")}
            index.append(f"| {item} | {lab} | {len(ans):,} | {r.get('finish_reason')} |")
    KEY.write_text(json.dumps(key, indent=1))
    (OUT / "INDEX.md").write_text("\n".join(index) + "\n")
    print("\n".join(index))


def unblind():
    key = json.loads(KEY.read_text())["key"]
    scores = json.loads(SCORES.read_text())
    per = {}           # engine -> item -> [scores]
    runs = {}          # (engine, rep) -> total
    for item, labs in scores.items():
        for lab, s in labs.items():
            if lab.startswith("_"):
                continue
            k = key[item][lab]
            per.setdefault(k["engine"], {}).setdefault(item, []).append(s)
            runs[(k["engine"], k["rep"])] = runs.get((k["engine"], k["rep"]), 0) + s
    items = sorted(scores)
    print("| prompt (out of 20) | " + " | ".join(f"{e} mean (runs)" for e in sorted(per)) + " |")
    print("|---|" + "---|" * len(per))
    for item in items:
        cells = []
        for e in sorted(per):
            v = per[e].get(item, [])
            cells.append(f"{statistics.mean(v):.1f} ({', '.join(f'{x:g}' for x in v)})" if v else "–")
        print(f"| {item} | " + " | ".join(cells) + " |")
    tot = []
    for e in sorted(per):
        t = [v for (en, rep), v in runs.items() if en == e]
        tot.append(f"{statistics.mean(t):.1f} ± {statistics.stdev(t) if len(t) > 1 else 0:.1f} (runs: "
                   f"{', '.join(f'{x:g}' for x in sorted(t))})")
    print("| **total (out of 100), mean ± sd over runs** | " + " | ".join(tot) + " |")


if __name__ == "__main__":
    {"export": export, "unblind": unblind}[sys.argv[1]]()
