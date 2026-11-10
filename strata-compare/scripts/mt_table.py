"""Multi-turn TTFT per turn: configs x (plain, with side requests)."""
import sys
sys.path.insert(0, "scripts")
from common import RESULTS, read_jsonl
cfg_sess = [x.split("=") for x in sys.argv[1].split(",")]   # CONFIG=SESSION
runs = read_jsonl(RESULTS / "runs.jsonl")
print("| config | chat | " + " | ".join(f"turn {k} TTFT s" for k in range(1, 8)) + " | reused on turn 7 |")
print("|---|---|" + "---|" * 8)
for c, s in cfg_sess:
    for scen, name in (("multiturn", "plain"), ("multiturn_side", "+ title request between turns")):
        rs = {r["item"]: r for r in runs if r["config"] == c and r["session"] == s and r["scenario"] == scen}
        if not rs:
            continue
        t7 = rs.get("turn7", {})
        reuse = t7.get("engine", {}).get("reused") if t7.get("engine") else (t7.get("server_timings") or {}).get("cache_n")
        print(f"| {c} | {name} | " + " | ".join(f"{rs[f'turn{k}']['ttft_s']:.1f}" if f"turn{k}" in rs else "–" for k in range(1, 8))
              + f" | {reuse if reuse is not None else '–'} |")
