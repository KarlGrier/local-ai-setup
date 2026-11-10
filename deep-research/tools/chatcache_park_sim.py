"""Replay the chat cache (LRU, --chat-cache 16, --chat-cache-mib budget) over the logged requests under other policies."""
import json, sys, collections, statistics
reqs = json.load(open(sys.argv[1]))
ONE_OFF = {"extract", "compact", "report", "verify", "other"}
RATE = 4200.0   # tok/s, measured prefill read rate of research prompts (report/verify/compact)
# conversation ids: research calls from the proxy; others unique, except chains through actual restores
nr = 0; park_owner = {}
for i, r in enumerate(reqs):
    if r["cls"] == "non-research" or not r.get("conv"):
        nr += 1; r["cid"] = f"nr{nr}"
    else:
        r["cid"] = r["cls"][0] + ":" + r["conv"]
for i, r in enumerate(reqs):
    for kind, tok, mib in r["ev"]:
        if kind == "parked" and i:
            park_owner[(r["inst"], tok)] = reqs[i - 1]["cid"]
        elif kind == "restored" and r["cls"] == "non-research":
            o = park_owner.get((r["inst"], tok))
            if o: r["cid"] = o
cls_of = {r["cid"]: r["cls"] for r in reqs}

def sim(budget_mib, count=16, no_park=frozenset()):
    store = collections.OrderedDict()   # cid -> (mib, tokens); order = LRU
    hits = misses = 0; miss_tok = 0; hit_tok = 0; stage = []; hw = 0
    ever = set()
    for i, r in enumerate(reqs):
        if i == 0 or reqs[i - 1]["inst"] != r["inst"]:
            store.clear(); ever.clear(); prev = None
        else:
            prev = reqs[i - 1]
        parks = [(tok, mib) for k, tok, mib in r["ev"] if k == "parked"]
        if prev and parks and prev["cid"] != r["cid"]:
            tok, mib = parks[0]
            if cls_of.get(prev["cid"]) not in no_park:
                store.pop(prev["cid"], None); store[prev["cid"]] = (mib, tok); ever.add(prev["cid"])
                while len(store) > 1 and (len(store) > count or sum(v[0] for v in store.values()) > budget_mib):
                    store.popitem(last=False)
        if prev and r["cid"] != prev["cid"] and r["cid"] in ever:
            if r["cid"] in store:
                hits += 1; hit_tok += store.pop(r["cid"])[1]
            else:
                misses += 1; miss_tok += next((t for k, t, m in r["ev"] if k == "restored"), 0) or r["reused"] + r["read"] // 2
            ever.discard(r["cid"])
        tot = sum(v[0] for v in store.values()); hw = max(hw, tot)
        if r["cls"] in ("report", "verify"):
            stage.append(tot)
    return {"budget_mib": budget_mib, "no_park": sorted(no_park), "restore_hits": hits, "restore_misses": misses,
            "reprefill_min": round(miss_tok / RATE / 60, 1), "parked_highwater_gib": round(hw / 1024, 1),
            "report_stage_parked_gib_median": round(statistics.median(stage) / 1024, 1) if stage else None,
            "report_stage_parked_gib_max": round(max(stage) / 1024, 1) if stage else None}

for kw in ({"budget_mib": 12288}, {"budget_mib": 12288, "no_park": frozenset(ONE_OFF)},
           {"budget_mib": 12288, "no_park": frozenset({"report", "verify"})},
           {"budget_mib": 6144}, {"budget_mib": 4096}, {"budget_mib": 4096, "no_park": frozenset(ONE_OFF)}):
    print(json.dumps(sim(**kw)))
print("calls per class / distinct conversations:", {c: (sum(1 for r in reqs if r["cls"] == c), len({r['cid'] for r in reqs if r['cls'] == c})) for c in ("agent", "extract", "compact", "report", "verify", "other")})

# what is still parked during report stages with the one-off classes not parked
def composition(budget_mib=12288, count=16, no_park=frozenset(ONE_OFF)):
    store = collections.OrderedDict(); worst = (0, None, None)
    per_stage = []
    for i, r in enumerate(reqs):
        if i == 0 or reqs[i - 1]["inst"] != r["inst"]:
            store.clear(); prev = None
        else:
            prev = reqs[i - 1]
        parks = [(tok, mib) for k, tok, mib in r["ev"] if k == "parked"]
        if prev and parks and prev["cid"] != r["cid"] and cls_of.get(prev["cid"]) not in no_park:
            tok, mib = parks[0]; store.pop(prev["cid"], None); store[prev["cid"]] = (mib, tok)
            while len(store) > 1 and (len(store) > count or sum(v[0] for v in store.values()) > budget_mib):
                store.popitem(last=False)
        if prev and r["cid"] in store and r["cid"] != prev["cid"]:
            store.pop(r["cid"])
        if r["cls"] in ("report", "verify"):
            tot = sum(v[0] for v in store.values())
            per_stage.append(tot)
            if tot > worst[0]:
                worst = (tot, i, [(cls_of.get(c), v[1], v[0]) for c, v in store.items()])
    print("report-stage samples:", len(per_stage), "share above 4 GiB:", round(sum(1 for x in per_stage if x > 4096) / len(per_stage), 2))
    print("worst:", worst[0], "MiB at request", worst[1], "->", worst[2])
composition()

# flag + "drop research's parked conversations when the report stage starts" (Jan's parked chats kept)
def flag_and_drop(budget_mib=12288, count=16, no_park=frozenset(ONE_OFF)):
    store = collections.OrderedDict(); stage = []; jan_kept = jan_parked_now = 0
    for i, r in enumerate(reqs):
        if i == 0 or reqs[i - 1]["inst"] != r["inst"]:
            store.clear(); prev = None
        else:
            prev = reqs[i - 1]
        parks = [(tok, mib) for k, tok, mib in r["ev"] if k == "parked"]
        if prev and parks and prev["cid"] != r["cid"] and cls_of.get(prev["cid"]) not in no_park:
            tok, mib = parks[0]; store.pop(prev["cid"], None); store[prev["cid"]] = (mib, tok)
            while len(store) > 1 and (len(store) > count or sum(v[0] for v in store.values()) > budget_mib):
                store.popitem(last=False)
        if prev and r["cid"] in store and r["cid"] != prev["cid"]:
            store.pop(r["cid"])
        if r["cls"] in ("report", "verify"):
            for c in [c for c in store if cls_of.get(c) != "non-research"]:
                store.pop(c)
            stage.append(sum(v[0] for v in store.values()))
    print("flag + drop at report start: report-stage parked median", round(statistics.median(stage) / 1024, 2),
          "GiB, max", round(max(stage) / 1024, 2), "GiB (what is left is non-research, e.g. Jan chats)")
flag_and_drop()
