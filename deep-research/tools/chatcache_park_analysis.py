"""Which research calls the chat cache parks, and whether those parks are ever restored (2026-10-19, proposal 3).
Engine log: per request, the chat-cache events printed before its 'prompt N tokens = R reused' line.
Proxy log: class per call (agent/extract/compact/report/verify/other) with usage.prompt_tokens, matched in order."""
import json, re, sys, collections
ENG = "/home/USER/ai-speed-testing/strata-compare/logs/engine-Cstar18t.log"
PRX = "/home/USER/ai/deep-research/logs/llm-calls.jsonl"
reqs, pend, inst = [], [], 0
for l in open(ENG, errors="replace"):
    if "participating threads" in l:
        inst += 1; pend = []
        continue
    m = re.search(r"chat cache: (parked|restored|dropped a conversation|dropped an older copy)[^0-9]*?of (\d+) tokens(?: \((\d+) checkpoints?, (\d+) MiB\))?(?: in (\d+) ms)?", l)
    if m:
        pend.append((m.group(1), int(m.group(2)), int(m.group(4) or 0)))
        continue
    m = re.search(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms.*?(\d+) generated", l)
    if m:
        reqs.append({"inst": inst, "n": int(m.group(1)), "reused": int(m.group(2)), "read": int(m.group(3)),
                     "ms": int(m.group(4)), "gen": int(m.group(5)), "ev": pend, "cls": "non-research"})
        pend = []
calls = [json.loads(x) for x in open(PRX)]
calls = [c for c in calls if isinstance(c.get("usage"), dict) and c["usage"].get("prompt_tokens")]
# align: greedy in order, each proxy call to the next engine request with the same prompt size
j = 0; matched = 0
for c in calls:
    n = c["usage"]["prompt_tokens"]
    g = c["usage"].get("completion_tokens")
    for k in range(j, min(j + 3000, len(reqs))):
        if reqs[k]["n"] == n and reqs[k]["gen"] == g and reqs[k]["cls"] == "non-research":
            reqs[k]["cls"] = c["cls"]; reqs[k]["conv"] = c.get("conv"); j = k + 1; matched += 1; break
print(f"engine requests {len(reqs)} in {inst} engine starts; proxy calls with usage {len(calls)}; matched {matched}")
# park attribution: a 'parked' event in request i parks request i-1's conversation (same engine instance)
parked = {}   # id -> dict
stats = collections.defaultdict(lambda: collections.Counter())
live = collections.OrderedDict(); hw = 0; hw_by = None
pid = 0
for i, r in enumerate(reqs):
    prev = reqs[i - 1] if i and reqs[i - 1]["inst"] == r["inst"] else None
    if i and reqs[i - 1]["inst"] != r["inst"]:
        live.clear()
    for kind, tok, mib in r["ev"]:
        if kind == "parked":
            cls = prev["cls"] if prev else "?"
            pid += 1; parked[pid] = {"cls": cls, "tok": tok, "mib": mib, "restored": 0}
            live[pid] = parked[pid]
            stats[cls]["parks"] += 1; stats[cls]["park_mib"] += mib
        elif kind == "restored":
            hit = next((p for p, v in reversed(live.items()) if v["tok"] == tok), None)
            if hit:
                v = live.pop(hit); v["restored"] += 1
                stats[v["cls"]]["restored"] += 1; stats[v["cls"]]["restored_mib"] += v["mib"]
                stats[v["cls"]]["reused_by_restore"] += r["reused"]
                stats[v["cls"]]["restored_into_" + r["cls"]] += 1
        else:
            hit = next((p for p, v in live.items() if v["tok"] == tok), None)
            if hit:
                live.pop(hit)
    tot = sum(v["mib"] for v in live.values())
    if tot > hw:
        hw = tot; hw_by = collections.Counter(); [hw_by.update({v["cls"]: v["mib"]}) for v in live.values()]
print(f"parked high-water {hw} MiB: {dict(hw_by)}")
for cls, s in sorted(stats.items(), key=lambda x: -x[1]["park_mib"]):
    print(f"{cls:13s} parks {s['parks']:5d} = {s['park_mib']/1024:7.1f} GiB parked; restored {s['restored']:4d} "
          f"({s['restored_mib']/1024:.1f} GiB), reused after restore {s['reused_by_restore']} tok; "
          + ", ".join(f"{k[14:]}:{v}" for k, v in s.items() if k.startswith("restored_into_")))
# report/verify calls: size, and reuse they got themselves
for cls in ("report", "verify", "compact"):
    rs = [r for r in reqs if r["cls"] == cls]
    if rs:
        print(f"{cls}: {len(rs)} calls, prompt median {sorted(r['n'] for r in rs)[len(rs)//2]} tok, max {max(r['n'] for r in rs)}, "
              f"reused {sum(r['reused'] for r in rs)} of {sum(r['n'] for r in rs)} prompt tok; prefill read rate "
              f"{sum(r['read'] for r in rs)/max(1,sum(r['ms'] for r in rs))*1000:.0f} tok/s")
json.dump([{k: v for k, v in r.items() if k != "ev"} | {"ev": r["ev"]} for r in reqs], open(sys.argv[1], "w"))
