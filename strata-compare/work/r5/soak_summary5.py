"""soak_summary4.py LABEL ENGINE_LOG [MONITOR_PREFIX] — round-4 big-chat soak: requests per kind, errors, going back to
a chat (kept in the chat cache vs read again), chat-cache budget (parked total rebuilt from the engine log's park /
restore / drop lines, against --chat-cache-mib), memory over time from the 1 s monitor (engine RSS, MemAvailable
minimum), and the 10-minute probes (a fresh 32K read + 512 tokens) to show slowdowns over time."""
import collections, csv, json, re, statistics, sys
WS = "/home/USER/ai-speed-testing/strata-compare"
L, ELOG = sys.argv[1], sys.argv[2]
MON = sys.argv[3] if len(sys.argv) > 3 else f"{WS}/logs/r5/monitor-{L}"
BUDGET_MIB = 16384
rows = [json.loads(l) for l in open(f"{WS}/results/runs.jsonl")]
rows = [r for r in rows if r.get("config") == L and str(r.get("scenario", "")).startswith("soak_")]
print(f"{L}: {len(rows)} requests, {rows[0]['started'] if rows else ''} .. {rows[-1]['started'] if rows else ''}")
print("by kind:", dict(collections.Counter(r["scenario"] for r in rows)))
print("errors:", sum(1 for r in rows if r.get("error")), "| Stop pressed:", sum(1 for r in rows if r.get("stopped")),
      "| finished:", sum(1 for r in rows if r.get("finish_reason")))
def s(v): return f"n={len(v)} median {statistics.median(v):.2f} s, max {max(v):.2f} s" if v else "n=0"
back = [r for r in rows if r["scenario"] == "soak_back" and r.get("ttft_s")]
hit = [r for r in back if (r.get("engine") or {}).get("reused", 0) > 0.9 * (r.get("engine") or {}).get("prompt", 1)]
miss = [r for r in back if r not in hit]
print("going back to a big chat, kept (reused > 90 %):", s([r["ttft_s"] for r in hit]),
      f"| prompts {min((r['engine']['prompt'] for r in hit), default=0)}..{max((r['engine']['prompt'] for r in hit), default=0)} tokens")
print("going back to a big chat, dropped earlier (read again):", s([r["ttft_s"] for r in miss]))
docs = [r for r in rows if r["scenario"] == "soak_doc" and r.get("ttft_s")]
for size in ("32k", "64k", "120k"):
    v = [r["ttft_s"] for r in docs if r["item"].endswith(size)]
    print(f"new chat with a pasted {size} document:", s(v))
# chat-cache budget from the engine log (only this soak's part: from the first line after the soak started)
txt = open(ELOG, errors="replace").read().splitlines()
parked = collections.OrderedDict()   # key -> (tokens, MiB)
events = collections.Counter(); peak = 0.0; over = 0; seq = 0
for ln in txt:
    if "chat cache:" not in ln:
        continue
    if (m := re.search(r"parked a conversation of (\d+) tokens \((\d+) checkpoints, (\d+) MiB\)", ln)):
        seq += 1; parked[seq] = (int(m[1]), float(m[3])); events["park"] += 1
    elif (m := re.search(r"dropped an older copy \((\d+) tokens\)", ln)):
        k = next((k for k, v in parked.items() if v[0] == int(m[1])), None)
        if k: parked.pop(k)
        events["drop older copy"] += 1
    elif (m := re.search(r"dropped a conversation of (\d+) tokens \((\d+) MiB\)", ln)):
        k = next((k for k, v in parked.items() if v[0] == int(m[1]) and abs(v[1] - float(m[2])) < 2), None)
        if k: parked.pop(k)
        events["LRU drop"] += 1
    elif (m := re.search(r"restored a conversation of (\d+) tokens", ln)):
        k = next((k for k, v in reversed(parked.items()) if v[0] == int(m[1])), None)
        if k: parked.pop(k)
        events["restore"] += 1
    tot = sum(v[1] for v in parked.values())
    peak = max(peak, tot)
    over += tot > BUDGET_MIB and len(parked) > 1
print("chat cache (whole engine log):", dict(events), f"| parked total peak {peak:.0f} MiB of {BUDGET_MIB} budget; "
      f"times over budget with >1 parked: {over}")
# monitor: engine RSS and MemAvailable every second
try:
    mon = [r for r in csv.DictReader(open(f"{MON}.sys.csv"))]
    t0 = float(mon[0]["t"])
    ma = [(float(r["t"]) - t0, int(r["memavail_mib"]), int(r["rss_mib"] or 0), int(r.get("swapused_mib") or 0)) for r in mon]
    low = min(ma, key=lambda x: x[1])
    print(f"monitor: {len(ma)} samples over {ma[-1][0] / 3600:.2f} h; MemAvailable min {low[1] / 1024:.1f} GB at "
          f"+{low[0] / 60:.0f} min; engine RSS {min(x[2] for x in ma if x[2]) / 1024:.1f} .. {max(x[2] for x in ma) / 1024:.1f} GB; "
          f"swap max {max(x[3] for x in ma)} MiB")
    for q in range(0, int(ma[-1][0] // 1800) + 1):                     # per half hour
        seg = [x for x in ma if q * 1800 <= x[0] < (q + 1) * 1800]
        if seg:
            print(f"   {q * 30:3d}-{q * 30 + 30:3d} min: MemAvailable min {min(x[1] for x in seg) / 1024:.1f} GB, "
                  f"RSS max {max(x[2] for x in seg) / 1024:.1f} GB")
    g = [l.strip().split(", ") for l in open(f"{MON}.gpu.csv") if l.count(",") >= 5]
    gpu = [int(x[1]) for x in g if x[1].isdigit()]
    print(f"GPU used {min(gpu)}..{max(gpu)} MiB")
except Exception as e:  # noqa: BLE001
    print("monitor:", e)
pr = [r for r in rows if r["scenario"] == "soak_probe"]
print("probes (fresh 32K read + 512 tokens):")
for r in pr:
    print(f"   {r['started']}  TTFT {r['ttft_s']:.2f} s  decode {r.get('decode_tps') or 0:.1f} tok/s  "
          f"RSS {r['engine_rss_mib'] / 1024:.1f} GB  MemAvailable {r['memavail_mib_after'] / 1024:.1f} GB")
lr = [r for r in rows if r["scenario"] == "soak_reason" and r.get("decode_tps")]
if lr:
    print("long reasoning decode (tok/s) in order:", [round(r["decode_tps"], 1) for r in lr])
