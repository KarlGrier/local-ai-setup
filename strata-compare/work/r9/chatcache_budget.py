#!/usr/bin/env python3
"""chatcache_budget.py ENGINE_LOG BUDGET_MIB — round 9: the chat cache's parked total rebuilt from one engine process's
log, in the engine's own order: when a request swaps a parked conversation in, the engine takes it OUT of the store
first, then parks the live one (where the budget is enforced), then logs "restored" — so a "restored" line that follows
a "parked" line (with only drops between, same request) is applied before that park. (round 5's soak_summary applies it
after, which counts the swapped-in conversation twice for a moment.)"""
import re, sys
L = [ln for ln in open(sys.argv[1], errors="replace").read().splitlines() if "chat cache:" in ln or "strata serve: prompt" in ln]
budget = float(sys.argv[2])
ev = []
for i, ln in enumerate(L):
    if (m := re.search(r"parked a conversation of (\d+) tokens \((\d+) checkpoints, (\d+) MiB\)", ln)): ev.append(["park", int(m[1]), float(m[3])])
    elif (m := re.search(r"dropped a conversation of (\d+) tokens \((\d+) MiB\)", ln)): ev.append(["drop", int(m[1]), float(m[2])])
    elif (m := re.search(r"dropped an older copy \((\d+) tokens\)", ln)): ev.append(["older", int(m[1]), 0.0])
    elif (m := re.search(r"restored a conversation of (\d+) tokens", ln)): ev.append(["restore", int(m[1]), 0.0])
    else: ev.append(["prompt", 0, 0.0])
# move each restore in front of the park it follows within the same request
for i in range(len(ev)):
    if ev[i][0] == "restore":
        j = i - 1
        while j >= 0 and ev[j][0] == "drop": j -= 1
        if j >= 0 and ev[j][0] == "park":
            r = ev.pop(i); ev.insert(j, r)
# the total is read where the engine's own check has finished: at each request boundary (the next "prompt" line) and at
# the end - the engine itself holds a just-parked conversation for a moment before it drops older ones
parked = []; peak = 0.0; over = 0; n = {"park": 0, "drop": 0, "restore": 0, "older": 0}
def check():
    global peak, over
    tot = sum(v[1] for v in parked); peak = max(peak, tot); over += tot > budget and len(parked) > 1
for k, t, mb in ev + [["prompt", 0, 0.0]]:
    if k == "prompt":
        check(); continue
    n[k] += 1
    if k == "park": parked.append((t, mb))
    elif k == "drop":
        idx = next((x for x, v in enumerate(parked) if v[0] == t and abs(v[1] - mb) < 2), None)
        if idx is not None: parked.pop(idx)
    elif k in ("restore", "older"):
        idx = next((x for x in range(len(parked) - 1, -1, -1) if parked[x][0] == t), None)
        if idx is not None: parked.pop(idx)
print(f"events {n}; parked total peak {peak:.0f} MiB of {budget:.0f}; times over budget with >1 parked: {over}; at the end {len(parked)} parked")
