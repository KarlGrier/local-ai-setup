#!/usr/bin/env python3
"""hard_report.py OUTDIR QWEN_MEDIUM QWEN_XHIGH DS50 DS75 DS25_HONESTY - 10-26 (Karl: "The summary should answer: is
DeepSeek better than Qwen at its best on hard questions, and by how much?"; 19:00: "Main result: DeepSeek's better
setting minus Qwen's better setting, per item, with the interval ... Report cut-off answers per model"). Reads the hard
set's labels after `regrade` (report.load): per item and setting the grade (the suite's checkers), thinking tokens, total
time, the max_tokens the answer was allowed (30,000 unless DeepSeek's 32K context left less) and whether it was cut off
(stopped at max_tokens - listed, graded as it is). "Better setting" = the one with the higher total over the items all
four main settings answered (each item weighs the same). DeepSeek's better minus Qwen's better: the mean per-item
difference with a paired bootstrap 95 % interval (10,000 resamples of the items, seed 20261026); also each model's
per-item best of its two settings (an upper bound no single setting reaches). Effort 25 ran the honesty items only: an
honesty table across all five settings. Blind research packets (every setting that answered, shuffled per question,
answer text only) -> OUTDIR/blind/, the key opened after the grades. -> OUTDIR/REPORT.md, OUTDIR/rows.csv"""
import csv
import json
import os
import random
import re
import statistics as stt
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/after")
import report as RP  # noqa: E402

NAMES = ["Qwen medium", "Qwen xhigh", "DeepSeek effort 50", "DeepSeek effort 75", "DeepSeek effort 25"]


def at_limit(v):
    """thinking reached the room limit: both servers close the thinking at max_tokens - min(max(512, M // 4), M // 2)
    (22,500 at 30,000); DeepSeek's token split is an estimate, so 2 % slack. Single-turn answers only."""
    m = v.get("mt") or 30000
    return v["steps"] is None and v["think"] >= 0.98 * (m - min(max(512, m // 4), m // 2))


def boot(diffs, n=10000, seed=20261026):
    rng = random.Random(seed)
    k = len(diffs)
    ms = sorted(stt.mean(rng.choice(diffs) for _ in range(k)) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def line(label, d):
    lo, hi = boot(d)
    return f"{label}: **{stt.mean(d) * 100:+.1f}** points per item (95 % {lo * 100:+.1f} to {hi * 100:+.1f})"


def main():
    out, labs = sys.argv[1], sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    data = [RP.load(l)[0] if os.path.isdir(f"{RP.SC}/suite/results/{l}") else {} for l in labs]
    names = NAMES[:len(data)]
    items = sorted(set().union(*[set(r) for r in data]), key=lambda x: (x.split("/")[0], x))
    main4 = [i for i in items if all(i in data[k] and data[k][i]["grade"] is not None for k in range(4))]
    g = lambda k, i: data[k][i]["grade"]
    tot = [stt.mean(g(k, i) for i in main4) for k in range(4)]
    q, d = (0 if tot[0] >= tot[1] else 1), (2 if tot[2] >= tot[3] else 3)
    diff = [g(d, i) - g(q, i) for i in main4]
    orc = [max(g(2, i), g(3, i)) - max(g(0, i), g(1, i)) for i in main4]
    L = ["# Hard set: DeepSeek (effort 50 / 75) vs Qwen (medium / xhigh)", "",
         f"{len(main4)} items graded for all four main settings (of {len(items)}); one run each. The same room for every answer: "
         "max_tokens 30,000 and no separate thinking budget (both servers keep a quarter of max_tokens for the answer, so the "
         "thinking stops at ~22,500); where DeepSeek's 32K context left less, the suite fitted max_tokens to it (the 'room' "
         "column). Grades: the suite's checkers (hidden unit tests, recomputed math answers, rule checkers, tool-call schemas, "
         "the research key); research also blind-graded (blind/).", "",
         "## The answer", "",
         "- Totals (mean grade per item x 100): " + ", ".join(f"{names[k]} **{tot[k] * 100:.1f}**" for k in range(4)) +
         f". Better settings: Qwen = {names[q]}, DeepSeek = {names[d]}.",
         "- " + line(f"DeepSeek's better ({names[d]}) minus Qwen's better ({names[q]})", diff),
         f"- Items: DeepSeek better on {sum(x > 0.001 for x in diff)}, worse on {sum(x < -0.001 for x in diff)}, equal on "
         f"{sum(abs(x) <= 0.001 for x in diff)}.",
         "- " + line("Upper bounds (each model's better answer per item, which no single setting reaches)", orc),
         "- Each pairing: " + "; ".join(f"{names[a]} minus {names[b]} {stt.mean([g(a, i) - g(b, i) for i in main4]) * 100:+.1f}"
                                         for a in (2, 3) for b in (0, 1)) + ".", "",
         "## Per category (mean grade x 100)", "", "| category | items | " + " | ".join(names[:4]) + " |", "|---|---|" + "---|" * 4]
    for c in sorted({i.split("/")[0] for i in main4}):
        its = [i for i in main4 if i.startswith(c + "/")]
        L.append(f"| {c} | {len(its)} | " + " | ".join(f"{stt.mean(g(k, i) for i in its) * 100:.1f}" for k in range(4)) + " |")
    hon = [i for i in items if i.startswith("honesty/") and all(i in r and r[i]["grade"] is not None for r in data)]
    if hon and len(data) > 4:
        L += ["", f"## Honesty by effort ({len(hon)} items: made-up questions; full marks = says it does not know)", "",
              "| setting | score | mean thinking tokens | mean total s |", "|---|---|---|---|"]
        for k, n in enumerate(names):
            L.append(f"| {n} | {stt.mean(data[k][i]['grade'] for i in hon) * 100:.1f} | "
                     f"{stt.mean(data[k][i]['think'] for i in hon):.0f} | {stt.mean((data[k][i]['wall'] or 0) for i in hon):.1f} |")
    L += ["", "## Time, room and cut-offs", "",
          "| setting | answers | mean total s | worst total s (item) | mean thinking tokens | thinking reached the room limit (~22,500; the answer still had its quarter) | cut off (stopped at max_tokens) | answers given less than 30,000 |",
          "|---|---|---|---|---|---|---|---|"]
    for n, r in zip(names, data):
        one = {k: v for k, v in r.items() if v["wall"] is not None}
        if not one:
            continue
        w = max(one.items(), key=lambda kv: kv[1]["wall"])
        cut = [k for k, v in one.items() if v["cut"]]
        less = [f"{k} {v['mt']}" for k, v in one.items() if (v.get("mt") or 30000) < 30000]
        lim = [k for k, v in one.items() if at_limit(v)]
        lim_txt = f"{len(lim)} ({', '.join(lim)})" if lim else "0"
        cut_txt = f"{len(cut)} ({', '.join(cut)})" if cut else "0"
        less_txt = f"{len(less)} ({', '.join(less)})" if less else "0"
        L.append(f"| {n} | {len(one)} | {stt.mean(v['wall'] for v in one.values()):.1f} | {w[1]['wall']:.1f} ({w[0]}) | "
                 f"{stt.mean(v['think'] for v in one.values()):.0f} | {lim_txt} | {cut_txt} | {less_txt} |")
    L += ["", "## Per item", "", "grade (cut off / thinking at the limit marked) / thinking tokens / total s", "", "| item | " + " | ".join(names) + " |",
          "|---|" + "---|" * len(names)]
    with open(f"{out}/rows.csv", "w", newline="") as fc:
        cw = csv.writer(fc)
        cw.writerow(["item", "setting", "grade", "thinking_tokens", "s_total", "max_tokens", "thinking_at_limit", "cut_off", "detail"])
        for it in items:
            cells = []
            for n, r in zip(names, data):
                v = r.get(it)
                if not v:
                    cells.append("-")
                    continue
                gr = RP.fmt(v["grade"], 2) + (" (cut off)" if v["cut"] else "") + (" (thinking at the limit)" if at_limit(v) else "")
                cells.append(f"{gr} / {v['think']} / {RP.fmt(v['wall'])}" + (f" ({v['steps']} steps)" if v["steps"] else ""))
                cw.writerow([it, n, v["grade"], v["think"], v["wall"], v.get("mt"), at_limit(v), v["cut"], v["detail"]])
            L.append(f"| {it} | " + " | ".join(cells) + " |")
    bd = f"{out}/blind"
    os.makedirs(bd, exist_ok=True)
    rng, key = random.Random(20261027), {}
    for it in [i for i in items if i.startswith("research/")]:
        order = [k for k in range(len(data)) if it in data[k]]
        if len(order) < 2:
            continue
        rng.shuffle(order)
        key[it] = {chr(65 + j): names[k] for j, k in enumerate(order)}
        qq = next((r[it]["prompt"] for r in data if it in r and r[it]["prompt"]), "")
        if isinstance(qq, dict):
            qq = qq.get("prompt") or json.dumps(qq, indent=1)[:6000]
        P = [f"# {it.split('/')[1]}", "", "## Question", "", qq if isinstance(qq, str) else json.dumps(qq)[:6000], ""]
        for j, k in enumerate(order):
            txt = RP.SELF.sub("[self-identification removed]", data[k][it]["content"])
            txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
            P += [f"## Answer {chr(65 + j)}", "", txt.strip() or "(empty)", ""]
        os.makedirs(f"{bd}/{it.split('/')[1]}", exist_ok=True)
        open(f"{bd}/{it.split('/')[1]}/packet.md", "w").write("\n".join(P) + "\n")
    json.dump(key, open(f"{bd}/KEY-do-not-open-before-grading.json", "w"), indent=1)
    L += ["", f"Blind research packets: {bd} ({len(key)} questions; the key is opened after the grades)."]
    L += RP.blind_section(bd)   # (10-27: the blind grades, once given, kept on every rebuild)
    open(f"{out}/REPORT.md", "w").write("\n".join(L) + "\n")
    print(f"{out}/REPORT.md")


if __name__ == "__main__":
    main()
