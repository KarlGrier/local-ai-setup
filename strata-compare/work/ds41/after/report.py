#!/usr/bin/env python3
"""report.py QWEN_LABEL DS50_LABEL DS75_LABEL OUTDIR - 10-26 (the user: "For each prompt and setting, report: grade, thinking
tokens, time to first answer token, total time, and whether thinking hit the 8,192 cap. Include the set's tool-call prompts
... Summary: quality per model and effort level, average and worst wait per answer, and a suggested daily effort default
for DeepSeek. Karl decides"). Reads suite/results/<label>/{answers,grades.json,scores.json} after `regrade`.
- grade: the suite's checker score (0-1; the checkers see the answer only - never the model or the thinking)
- thinking hit the cap: reasoning tokens >= 8,100 (each request carries reasoning_budget_tokens 8,192 and max_tokens
  16,384, the same for both models) - "B"; an answer that still stopped at max_tokens is "truncated" (the user, 10-26:
  "Report any truncated answers separately ("truncated"), not as plain failures"), with the reason: "context" when the
  suite had to fit max_tokens below 16,384 to the context (DeepSeek's 32K with a long prompt), else "max_tokens"
- agentic items: steps summed (time to the first answer token = the first step's)
- OUTDIR/REPORT.md, OUTDIR/rows.csv, OUTDIR/blind/<research item>/packet.md + OUTDIR/blind/KEY-do-not-open-before-grading.json
  (answers A/B/C shuffled per question: the answer text only - no label, model id, endpoint or thinking; sentences in
  which a model names itself are replaced by "[self-identification removed]")"""
import csv
import glob
import json
import os
import random
import re
import statistics as stt
import sys

SC = "/home/USER/ai-speed-testing/strata-compare"
BUDGET = 8100
FULL = 16384
SELF = re.compile(r"[^.!?\n]*\b(I am|I'm|as an AI (?:model )?(?:developed|made|built|trained) by|my name is)\b[^.!?\n]*"
                  r"\b(Qwen|DeepSeek|Alibaba|Strata|Maya)\b[^.!?\n]*[.!?]?", re.I)


def load(label):
    """one label, or several joined with "+" (10-26 night: DeepSeek e50's long-context items ran later as their own label)"""
    if "+" in label:
        rows, s = {}, {"categories": {}}
        for part in label.split("+"):
            r, ps = load(part)
            rows.update(r)
            s["categories"].update(ps.get("categories") or {})
        return rows, s
    d = f"{SC}/suite/results/{label}"
    g = json.load(open(f"{d}/grades.json")) if os.path.exists(f"{d}/grades.json") else {}
    s = json.load(open(f"{d}/scores.json")) if os.path.exists(f"{d}/scores.json") else {}
    rows = {}
    for f in sorted(glob.glob(f"{d}/answers/*/*.json")):
        a = json.load(open(f))
        cat = f.split("/")[-2]
        item = f"{cat}/{os.path.basename(f).split('.r')[0]}"
        gr = g.get(f"{item}#r{a.get('run', 0)}") or {}
        if cat == "agentic":
            steps = [x for x in a.get("steps") or [] if isinstance(x, dict)]
            reas = sum(((x.get("tokens") or {}).get("reasoning") or 0) for x in steps)
            wall = sum(((x.get("timing") or {}).get("wall_s") or 0) for x in steps)
            tfa = ((steps[0].get("timing") or {}).get("t_first_answer_s")) if steps else None
            hit = any(((x.get("tokens") or {}).get("reasoning") or 0) >= BUDGET for x in steps)
            cut = any(x.get("cut_off") for x in steps)
            n_steps = len(steps)
            mt = min([((x.get("request") or {}).get("max_tokens") or FULL) for x in steps] or [FULL])
        else:
            t, tm = a.get("tokens") or {}, a.get("timing") or {}
            reas, wall, tfa = t.get("reasoning") or 0, tm.get("wall_s"), tm.get("t_first_answer_s")
            hit, cut, n_steps = reas >= BUDGET, bool(a.get("cut_off")), None
            mt = (a.get("request") or {}).get("max_tokens")
        rows[item] = {"cat": cat, "grade": gr.get("score"), "detail": (gr.get("detail") or "")[:120], "think": reas,
                      "t_answer": tfa, "wall": wall, "budget": hit, "cut": cut, "steps": n_steps,
                      "cut_why": ("context" if (mt or FULL) < FULL else "max_tokens") if cut else None,
                      "prompt": a.get("prompt"), "content": ((a.get("response") or {}).get("content") or ""), "mt": mt}
    return rows, s


def fmt(x, nd=1):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def main():
    labs, out = sys.argv[1:4], sys.argv[4]
    names = ["Qwen P021m (medium)", "DeepSeek effort 50", "DeepSeek effort 75"]
    os.makedirs(out, exist_ok=True)
    data = [load(l) for l in labs]
    items = sorted(set().union(*[set(r) for r, _ in data]), key=lambda x: (x.split("/")[0], x))
    shared = sorted(set.intersection(*[{c for c, v in (s.get("categories") or {}).items() if v.get("score") is not None}
                                       for _, s in data]) - {"freshness", "visual"})
    L = ["# Graded set: Qwen vs DeepSeek (suite quick; thinking budget 8,192, max_tokens 16,384)", "",
         "Grades: the suite's checkers (hidden unit tests, recomputed math answers, rule checkers, tool-call schemas, the "
         "research key): they read the answer only, never the model's name or its thinking. Research answers also go to "
         "the Phase 4 blind grader (blind/). Thinking hit the cap: reasoning >= 8,100 tokens (budget 8,192); truncated = the answer stopped at max_tokens "
         "(listed separately with its reason, never hidden).", "", "## Quality per model and effort", "",
         "| category | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for c in shared + [c for c in ("longctx",) if c not in shared]:
        cells = []
        for _, s in data:
            v = (s.get("categories") or {}).get(c) or {}
            cells.append(f"{v['score'] * 100:.1f} ({v.get('lo', 0) * 100:.0f}-{v.get('hi', 0) * 100:.0f})" if v.get("score") is not None else "n/a")
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    tot = []
    for _, s in data:
        sc = [((s.get("categories") or {}).get(c) or {}).get("score") for c in shared]
        tot.append(f"**{stt.mean(sc) * 100:.1f}**" if all(x is not None for x in sc) else "n/a")
    L += [f"| total ({len(shared)} shared categories, unweighted) | " + " | ".join(tot) + " |"]
    ex, tr = [], []
    for r, _ in data:
        cats = {}
        for it, v in r.items():
            if v["cat"] in shared and not v["cut"] and v["grade"] is not None:
                cats.setdefault(v["cat"], []).append(v["grade"])
        ex.append(f"{stt.mean(stt.mean(x) for x in cats.values()) * 100:.1f}" if len(cats) == len(shared) else "n/a")
        t = [v for v in r.values() if v["cut"] and v["cat"] in shared]
        tr.append(f"{len(t)} ({sum(v['cut_why'] == 'context' for v in t)} context, {sum(v['cut_why'] == 'max_tokens' for v in t)} max_tokens)")
    L += ["| truncated answers (graded as they are above) | " + " | ".join(tr) + " |",
          "| total without the truncated answers (per-item mean per category) | " + " | ".join(ex) + " |", ""]
    # (10-26: DeepSeek's runs are samples - effort 50 a spread of each category, effort 75 a subset of its math and
    # coding - so the categories are also compared on the prompts each setting that ran the category answered)
    # (10-26 18:20, Karl: "flag every category where both models are at or near the ceiling (e.g. >= 90%, or all pass) as
    # 'can't tell apart', so a tie there isn't read as equal quality")
    L += ["### The same prompts (each category's prompts answered by every setting that ran it; mean grade x 100)", "",
          "\"can't tell apart\" = every setting that ran the category is at or near the ceiling (>= 90 % on these prompts, "
          "or all pass): a tie or a small gap there says nothing about which model is better.", "",
          "| category | prompts | " + " | ".join(names) + " | reading |", "|---|---|" + "---|" * len(names) + "---|"]
    for c in sorted({v["cat"] for r, _ in data for v in r.values()}):
        who = [i for i, (r, _) in enumerate(data) if any(v["cat"] == c for v in r.values())]
        common = set.intersection(*[{k for k, v in data[i][0].items() if v["cat"] == c} for i in who])
        cells, ms = [], []
        for i in range(len(data)):
            gs = [data[i][0][k]["grade"] for k in common] if i in who else []
            ok = gs and all(g is not None for g in gs)
            cells.append(f"{stt.mean(gs) * 100:.1f}" if ok else "-")
            if ok:
                ms.append(stt.mean(gs))
        ceiling = len(ms) >= 2 and all(m >= 0.90 for m in ms)
        L.append(f"| {c} | {len(common)} | " + " | ".join(cells) + f" | {'**can not tell apart** (ceiling)' if ceiling else 'below the ceiling' if len(ms) >= 2 else '-'} |")
    L += [""]
    # Qwen's 10-17 effort levels on the full quick set (results/r21/effort-levels.md; xhigh = 10-15's c18-iq3s-quick, the
    # same engine and weights), with the same ceiling reading against today's runs
    o17 = {"xhigh (10-15)": "c18-iq3s-quick", "medium (10-17)": "c18t-quick-medium", "low (10-17)": "c18t-quick-low"}
    sc17 = {}
    for n, lab in o17.items():
        try:
            sc17[n] = json.load(open(f"{SC}/suite/results/{lab}/scores.json")).get("categories") or {}
        except (OSError, ValueError):
            sc17[n] = {}
    L += ["### Qwen's quick-set scores by effort level, 10-17 (the full quick set; the same model, weights and engine "
          "family as today's P021m)", "", "| category | " + " | ".join(o17) + " | Qwen P021m medium today | reading |",
          "|---|" + "---|" * (len(o17) + 2)]
    today = data[0][1].get("categories") or {}
    for c in ("coding", "agentic", "math", "instruct", "tools", "longctx", "honesty", "research"):
        vals = [((sc17[n].get(c) or {}).get("score")) for n in o17] + [(today.get(c) or {}).get("score")]
        cells = [f"{v * 100:.1f}" if v is not None else "-" for v in vals]
        known = [v for v in vals if v is not None]
        L.append(f"| {c} | " + " | ".join(cells) + " | " + ("at the ceiling at every level (>= 90 %)" if known and all(v >= 0.90 for v in known)
                                                            else "below the ceiling at some level") + " |")
    L += ["", "Medium's long context on 10-17 pooled with its rerun: 75.0 (12 answers). 10-17 wall time: xhigh 2.93 h, "
          "medium 0.82 h, low 0.77 h for the whole quick set.", ""]
    if len(data) > 2:   # effort 50 vs 75 on effort 75's prompts (math, coding)
        com = {k for k, v in data[2][0].items()} & set(data[1][0])
        if com:
            g1 = [data[1][0][k]["grade"] for k in com if data[1][0][k]["grade"] is not None]
            g2 = [data[2][0][k]["grade"] for k in com if data[2][0][k]["grade"] is not None]
            w1 = [data[1][0][k]["wall"] for k in com if data[1][0][k]["wall"] is not None]
            w2 = [data[2][0][k]["wall"] for k in com if data[2][0][k]["wall"] is not None]
            if g1 and g2 and w1 and w2:
                L += [f"Effort 50 vs 75 on effort 75's {len(com)} prompts: grade {stt.mean(g1) * 100:.1f} vs {stt.mean(g2) * 100:.1f}, "
                      f"mean total {stt.mean(w1):.0f} s vs {stt.mean(w2):.0f} s, worst {max(w1):.0f} s vs {max(w2):.0f} s.", ""]
    L += ["## Waits per answer (single-turn items; agentic loops listed separately)", "",
          "| | answers | mean total s | worst total s (item) | mean s to the first answer token | worst s to the first answer token | thinking hit the cap | truncated |",
          "|---|---|---|---|---|---|---|---|"]
    for n, (r, _) in zip(names, data):
        one = {k: v for k, v in r.items() if v["cat"] != "agentic" and v["wall"] is not None}
        if not one:
            L.append(f"| {n} | 0 | | | | | | |")
            continue
        w = max(one.items(), key=lambda kv: kv[1]["wall"])
        ta = [v["t_answer"] for v in one.values() if v["t_answer"] is not None]
        wa = max(((k, v) for k, v in one.items() if v["t_answer"] is not None), key=lambda kv: kv[1]["t_answer"], default=(None, {}))
        L.append(f"| {n} | {len(one)} | {stt.mean(v['wall'] for v in one.values()):.1f} | {w[1]['wall']:.1f} ({w[0]}) | "
                 f"{fmt(stt.mean(ta)) if ta else '-'} | {fmt(wa[1].get('t_answer'))} ({wa[0] or '-'}) | "
                 f"{sum(v['budget'] for v in one.values())} | {sum(v['cut'] for v in one.values())} |")
    L += ["", "## Per prompt", "", "grade (or truncated) / thinking tokens / s to the first answer token / total s / B = the "
          "thinking hit the 8,192 budget", "", "| item | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    with open(f"{out}/rows.csv", "w", newline="") as fc:
        cw = csv.writer(fc)
        cw.writerow(["item", "setting", "grade", "thinking_tokens", "s_first_answer", "s_total", "thinking_hit_cap", "truncated", "truncated_why", "steps", "detail"])
        for it in items:
            cells = []
            for n, (r, _) in zip(names, data):
                v = r.get(it)
                if not v:
                    cells.append("not run")
                    continue
                g = f"truncated ({v['cut_why']}; graded {fmt(v['grade'], 2)})" if v["cut"] else fmt(v["grade"], 2)
                cells.append(f"{g} / {v['think']} / {fmt(v['t_answer'])} / {fmt(v['wall'])}" + (" / B" if v["budget"] else "")
                             + (f" ({v['steps']} steps)" if v["steps"] else ""))
                cw.writerow([it, n, v["grade"], v["think"], v["t_answer"], v["wall"], v["budget"], v["cut"], v["cut_why"], v["steps"], v["detail"]])
            L.append(f"| {it} | " + " | ".join(cells) + " |")
    # blind research packets for the Phase 4 grader
    bd = f"{out}/blind"
    os.makedirs(bd, exist_ok=True)
    rng, key = random.Random(20261026), {}
    for it in [i for i in items if i.startswith("research/")]:
        # (10-26 18:30: only the settings that answered, and only questions at least two of them answered - a packet
        # with "(no answer)" in it would show which setting is which)
        order = [k for k in range(len(labs)) if it in data[k][0]]
        if len(order) < 2:
            continue
        rng.shuffle(order)
        lab = {chr(65 + j): names[k] for j, k in enumerate(order)}
        key[it] = lab
        q = next((r[it]["prompt"] for r, _ in data if it in r and r[it]["prompt"]), "")
        if isinstance(q, dict):
            q = q.get("prompt") or json.dumps(q, indent=1)[:6000]
        P = [f"# {it.split('/')[1]}", "", "## Question", "", q if isinstance(q, str) else json.dumps(q)[:6000], ""]
        for j, k in enumerate(order):
            v = data[k][0].get(it)
            txt = SELF.sub("[self-identification removed]", v["content"]) if v else "(no answer)"
            txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
            P += [f"## Answer {chr(65 + j)}", "", txt.strip() or "(empty)", ""]
        d = f"{bd}/{it.split('/')[1]}"
        os.makedirs(d, exist_ok=True)
        open(f"{d}/packet.md", "w").write("\n".join(P) + "\n")
    json.dump(key, open(f"{bd}/KEY-do-not-open-before-grading.json", "w"), indent=1)
    L += ["", f"Blind research packets: {bd} ({len(key)} questions; the key file is opened after the grades)."]
    L += blind_section(bd)
    open(f"{out}/REPORT.md", "w").write("\n".join(L) + "\n")
    print(f"{out}/REPORT.md")


def blind_section(bd):
    """the blind grades already given (bd/grades.jsonl: one record per question, de-blinded after grading) - kept in the
    report on every rebuild (10-26 night: a rebuild had dropped the hand-added section)"""
    p = f"{bd}/grades.jsonl"
    if not os.path.exists(p):
        return []
    G = [json.loads(l) for l in open(p) if l.strip()]
    cols = sorted({n for g in G for n in g["revealed"]}, key=lambda n: (not n.startswith("Qwen"), n))
    L = ["", "## Blind research grades (Phase 4 method: answer text only, shuffled, a fresh grader per question, 5-item "
         "checklist 0-2 each = /10; key opened after)", "", "| question | " + " | ".join(cols) + " | grader's rank |",
         "|---|" + "---|" * (len(cols) + 1)]
    for g in G:
        r = g["revealed"]
        rank = " > ".join(g["key"][x] for x in g["rank"])
        if len(set(r.values())) == 1:
            rank += " (tie on points)"
        L.append(f"| {g['id']} | " + " | ".join(fmt(r.get(c)) for c in cols) + f" | {rank} |")
    L.append("| mean | " + " | ".join(f"**{stt.mean(g['revealed'][c] for g in G if c in g['revealed']):.1f}**" for c in cols) + " | |")
    L += ["", f"{len(G)} questions; per-question notes in blind/*/grades.json."]
    return L


if __name__ == "__main__":
    main()
