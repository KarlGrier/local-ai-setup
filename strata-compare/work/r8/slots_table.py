"""slots_table.py LABEL,... — round 8 A.6 chat-cache slot screens (chatsoak many --n-chats 16): going back to each of
16 conversations (pasted 4K-30K-token documents), twice (oldest first, then shuffled): TTFT median / mean / max, how
many came back from the cache (engine reused > 0), and the server's peak RSS / lowest MemAvailable (monitor)."""
import csv, json, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
print("| run | back r1: median / mean / max TTFT (s), reused | back r2: median / mean / max, reused | peak RSS GB / min MemAvailable GB |")
print("|---|---|---|---|")
for L in sys.argv[1].split(","):
    rs = [r for r in runs if r["config"] == L and r["scenario"] == "many_back" and not r.get("error")]
    cells = []
    for rnd in ("r1", "r2"):
        x = [r for r in rs if r["item"].endswith(rnd)]
        t = [r["ttft_s"] for r in x if r.get("ttft_s") is not None]
        reused = sum(1 for r in x if (r.get("engine") or {}).get("reused", 0) > 0)
        cells.append(f"{statistics.median(t):.2f} / {statistics.mean(t):.2f} / {max(t):.2f}, {reused}/{len(x)}" if t else "–")
    try:
        rows = [r for r in csv.DictReader(open(WS / f"logs/r8/monitor-{L}.sys.csv")) if r["pid"]]
        mon = f"{max(int(r['rss_mib']) for r in rows) / 1024:.1f} / {min(int(r['memavail_mib']) for r in rows) / 1024:.1f}"
    except Exception:
        mon = "–"
    print(f"| {L} | {cells[0]} | {cells[1]} | {mon} |")
