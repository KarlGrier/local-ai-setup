#!/usr/bin/env python3
"""degenerate_census.py - 2026-10-13, the user's "count degenerate outputs per label and category": every saved answer
of every label (local and hosted), each generation in it (single answers; every step of agentic / research loops):
  guard   Strata's repeat guard ended it (finish "length" well below the token limit; grades: "server stopped it early")
  limit   it ran to the token limit (finish "length" at max_tokens)
  loop    the text ends in one short unit (1-12 chars) repeated >= 64 times (a loop still going when it stopped)
  run256  a run of one short unit repeated >= 250 times anywhere (the guard ends a reply at the 256th identical token,
          so a stopped one shows 255) (what trips Strata's guard when the unit is one
          token), counted separately when the generation then went on and finished normally ("recovered")
Text checked: content and reasoning (Claude's is the API's summarised thinking; agentic steps keep content only).
Output: results/r19/degenerate_census.json + a Markdown table on stdout."""
import json, re, sys, collections
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/suite/results")
RUN = re.compile(r"(.{1,12}?)\1{63,}", re.S)

def runs(text):
    out = []
    for m in RUN.finditer(text or ""):
        out.append((m.group(1), len(m.group(0)) // len(m.group(1)), m.start(), m.end()))
    return out

def gens(d):
    """(finish, completion tokens, texts, cut_off) for each generation in an answer."""
    if d.get("steps") and isinstance(d["steps"], list) and isinstance(d["steps"][0], dict) and "finish_reason" in d["steps"][0]:
        for s in d["steps"]:
            yield s.get("finish_reason"), (s.get("tokens") or {}).get("completion"), [s.get("content") or ""], s.get("cut_off")
    else:
        r = d.get("response") or {}
        yield r.get("finish_reason"), (d.get("tokens") or {}).get("completion"), [r.get("content") or "", r.get("reasoning") or ""], d.get("cut_off")

labels = sorted(p.name for p in R.iterdir() if (p / "answers").is_dir())
table = {}
examples = []
for lb in labels:
    grades = json.loads((R / lb / "grades.json").read_text()) if (R / lb / "grades.json").exists() else {}
    for f in sorted((R / lb / "answers").glob("*/*.json")):
        cat = f.parent.name
        if cat == "visual":
            pass
        d = json.loads(f.read_text())
        key = f"{cat}/{f.name.rsplit('.r', 1)[0]}#r{d.get('run', 0)}"
        g = grades.get(key) or {}
        cr = str(g.get("cut_reason") or "")
        c = table.setdefault((lb, cat), collections.Counter())
        c["answers"] += 1
        flags = set()
        for fin, ntok, texts, cut in gens(d):
            rr = [x for t in texts for x in runs(t)]
            tail_loop = any(t and RUN.search(t[-1500:]) and t.rstrip(". \n").endswith(t.rstrip(". \n")[-1]) and
                            re.search(r"(.{1,12}?)\1{63,}[.\s]*$", t[-4000:], re.S) for t in texts)
            if fin in ("length", "max_tokens"):
                if "server stopped it early" in cr or (ntok and ntok < 0.9 * (d.get("request") or {}).get("max_tokens", 10**9) and lb[:2] in ("c1", "r1", "v0")):
                    flags.add("guard")
                else:
                    flags.add("limit")
                if tail_loop:
                    flags.add("loop_at_stop")
            if any(n >= 250 for _, n, _, _ in rr):
                flags.add("run256")
                if fin not in ("length", "max_tokens"):
                    flags.add("run256_recovered")
            if rr and len(examples) < 400:
                u, n, s0, e0 = max(rr, key=lambda x: x[1])
                if n >= 250 or fin in ("length", "max_tokens"):
                    examples.append({"label": lb, "answer": key, "finish": fin, "unit": u, "repeats": n,
                                     "score": g.get("score"), "cut_reason": cr})
        for fl in flags:
            c[fl] += 1
        if flags & {"guard", "limit", "run256"}:
            c["degenerate_or_cut"] += 1
            if g.get("score") is not None and g["score"] < 1:
                c["of_which_scored_below_1"] += 1

out = {f"{lb}|{cat}": dict(v) for (lb, cat), v in table.items()}
Path("/home/USER/ai-speed-testing/strata-compare/results/r19/degenerate_census.json").write_text(
    json.dumps({"by_label_category": out, "examples": examples}, indent=1, ensure_ascii=False))
cols = ["answers", "guard", "limit", "loop_at_stop", "run256", "run256_recovered", "of_which_scored_below_1"]
print("| label | category | " + " | ".join(cols) + " |")
print("|---|---|" + "---|" * len(cols))
for (lb, cat), v in sorted(table.items()):
    if any(v[k] for k in cols[1:]):
        print(f"| {lb} | {cat} | " + " | ".join(str(v[k]) for k in cols) + " |")
print()
print("| label | answers | guard | limit | loop_at_stop | run256 | run256_recovered |")
print("|---|---|---|---|---|---|---|")
for lb in labels:
    tot = collections.Counter()
    for (l2, cat), v in table.items():
        if l2 == lb and cat != "visual":
            tot.update(v)
    print(f"| {lb} | {tot['answers']} | {tot['guard']} | {tot['limit']} | {tot['loop_at_stop']} | {tot['run256']} | {tot['run256_recovered']} |")
