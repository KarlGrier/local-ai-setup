"""soak_summary.py LABEL — the chat-page soak's rows in results/runs.jsonl: requests per kind, errors, stops, TTFT of
turns that continued a chat (reused > 0) vs read from scratch, chat-cache parks/restores/drops, RSS/MemAvailable/GPU."""
import collections, json, statistics, sys
L = sys.argv[1]
rows = [json.loads(l) for l in open("/home/USER/ai-speed-testing/strata-compare/results/runs.jsonl")]
rows = [r for r in rows if r.get("config") == L and str(r.get("scenario", "")).startswith("chat_")]
print(f"{L}: {len(rows)} requests, {rows[0]['started'] if rows else ''} .. {rows[-1]['started'] if rows else ''}")
kinds = collections.Counter(r["scenario"] for r in rows)
print("by kind:", dict(kinds))
print("errors:", sum(1 for r in rows if r.get("error")), "| stopped (Stop button):", sum(1 for r in rows if r.get("stopped")),
      "| finished:", sum(1 for r in rows if r.get("finish_reason")))
cont = [r for r in rows if (r.get("engine") or {}).get("reused", 0) > 0 and r.get("ttft_s")]
fresh = [r for r in rows if (r.get("engine") or {}).get("reused", 1) == 0 and r.get("ttft_s")]
def s(v): return f"n={len(v)} median {statistics.median(v):.2f} s, max {max(v):.2f} s" if v else "n=0"
print("TTFT, continuing a chat (reused > 0):", s([r["ttft_s"] for r in cont]))
big = [r for r in cont if r["engine"].get("prompt", 0) > 8000]
print("   ... of which prompts > 8K tokens:", s([r["ttft_s"] for r in big]),
      "| reused share", f"{statistics.mean(r['engine']['reused'] / r['engine']['prompt'] for r in big):.3f}" if big else "")
print("TTFT, read from scratch (reused 0):", s([r["ttft_s"] for r in fresh]))
cc = collections.Counter()
for r in rows:
    for e in (r.get("engine") or {}).get("chat_cache", []):
        cc[e.split(" a conversation")[0].split(" an older")[0]] += 1
print("chat cache events:", dict(cc))
rss = [r["engine_rss_mib"] for r in rows if r.get("engine_rss_mib", -1) > 0]
mem = [r["memavail_mib_after"] for r in rows]
gpu = [r["gpu_used_mib_after"] for r in rows if r.get("gpu_used_mib_after", -1) > 0]
if rss: print(f"engine RSS {min(rss)/1024:.1f} .. {max(rss)/1024:.1f} GB; MemAvailable min {min(mem)/1024:.1f} GB; GPU {min(gpu)}..{max(gpu)} MiB")
long = max(rows, key=lambda r: r.get("t_total_s", 0)) if rows else None
if long: print(f"longest request: {long['scenario']} {long['item']} {long['t_total_s']:.0f} s")
