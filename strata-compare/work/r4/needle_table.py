"""needle_table.py LABEL[,LABEL...] — results/needle.jsonl: per engine and document size, correct answers over the runs
(codes = the 6-digit numbers, names = who signed), by depth, TTFT, reasoning length, finish."""
import collections, json, statistics, sys
rows = [r for r in (json.loads(l) for l in open("/home/USER/ai-speed-testing/strata-compare/results/needle.jsonl")) if not r.get("error")]   # client-side 400s (answer cap over the context) left out
labels = sys.argv[1].split(",")
print("| engine | document | runs | codes right | names right | by depth ~2/25/50/75/98 % (code+name, of 2 per run) | TTFT (s) | reasoning chars | finish |")
print("|---|---|---|---|---|---|---|---|---|")
for L in labels:
    for size in ("32k", "64k", "120k"):
        rs = [r for r in rows if r["label"] == L and r["size"] == size]
        if not rs:
            continue
        depth = [sum(r["per_fact"][i]["code"] + r["per_fact"][i]["name"] for r in rs) for i in range(5)]
        ttft = [r["ttft_s"] for r in rs if r.get("ttft_s")]
        print(f"| {L} | {size} ({rs[0]['prompt_tokens']:,} tok) | {len(rs)} | {sum(r['codes_ok'] for r in rs)}/{5 * len(rs)} | "
              f"{sum(r['names_ok'] for r in rs)}/{5 * len(rs)} | {' · '.join(f'{d}/{2 * len(rs)}' for d in depth)} | "
              f"{statistics.median(ttft):.1f} | {int(statistics.median(r['reasoning_chars'] for r in rs)):,} | "
              f"{dict(collections.Counter(r['finish'] for r in rs))} |")
    rs = [r for r in rows if r["label"] == L]
    if rs:
        print(f"| **{L} total** | | {len(rs)} | **{sum(r['codes_ok'] for r in rs)}/{5 * len(rs)}** | **{sum(r['names_ok'] for r in rs)}/{5 * len(rs)}** | | | | |")
