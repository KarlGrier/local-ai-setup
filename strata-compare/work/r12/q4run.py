#!/usr/bin/env python3
"""q4run.py LABEL ENGINE_LOG [q4|signal] — round 10 D.3 (plan "signal": your Signal addition - the five correctness
items (4,096-token cap) and long reasoning math + code with an 8,192-token cap, so answers can finish, then the 8K and
~32K prompts): the Q4 retest's requests on a running server (127.0.0.1:8081), each with the
NVMe's read bytes (/proc/diskstats, nvme0n1) and the system's swap-in / swap-out pages around it, and the engine's own
file-tier figures (bytes read from the mapped GGUF, which may be the page cache): long reasoning math and code (2,048-token
cap, your settings), one 8K prompt and one ~32K prompt (+64 tokens).  Records -> results/runs.jsonl (bench.Runner) and
results/r12/q4io-LABEL.json."""
import argparse, copy, json, re, sys, time
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); sys.path.insert(0, str(WS / "scripts"))
import bench
L, elog = sys.argv[1], Path(sys.argv[2])
PLAN = sys.argv[3] if len(sys.argv) > 3 else "q4"
def disk():
    for l in open("/proc/diskstats"):
        f = l.split()
        if f[2] == "nvme0n1": return int(f[5]) * 512
def vm():
    d = {}
    for l in open("/proc/vmstat"):
        k, v = l.split()
        if k in ("pswpin", "pswpout"): d[k] = int(v)
    return d
FT = re.compile(r"expert tiers: GPU (\d+) hits this request; since the start RAM (\d+) blobs, files (\d+) blobs ([\d.]+) MB read")
def ftier():
    m = FT.findall(elog.read_text(errors="replace"))
    return (int(m[-1][2]), float(m[-1][3])) if m else (0, 0.0)
a = argparse.Namespace(model="x", base="http://127.0.0.1:8081", engine_log=str(elog), config=L, session=L, extra="", max_tokens=0, items="", rep=0)
R = bench.Runner(a)
lr = {p["id"]: p for p in bench.load("longreason")}
p32 = next(p for p in bench.load("speed") if p["size"] == "32k" and p["rep"] == 0)
m8 = copy.deepcopy(p32["messages"]); m8[-1]["content"] = m8[-1]["content"][: len(m8[-1]["content"]) // 4]
m32 = copy.deepcopy(p32["messages"]); m32[-1]["content"] = m32[-1]["content"][: int(len(m32[-1]["content"]) * 0.97)]
plan = [("longreason", "math", lr["math"]["messages"], 2048), ("longreason", "code", lr["code"]["messages"], 2048),
        ("speed", "8k", m8, 64), ("speed", "32k-cut", m32, 64)]
if PLAN == "signal":
    plan = [("correctness", p["id"], p["messages"], 4096) for p in bench.load("correctness")] + \
           [("longreason", "math", lr["math"]["messages"], 8192), ("longreason", "code", lr["code"]["messages"], 8192),
            ("speed", "8k", m8, 64), ("speed", "32k-cut", m32, 64)]
out = []
for sc, item, msgs, mt in plan:
    d0, v0, f0 = disk(), vm(), ftier()
    rec = R.call(sc, item, 0, msgs, mt, keep_pieces=(sc == "longreason"), save_text=(sc == "longreason"))
    time.sleep(0.5)
    d1, v1, f1 = disk(), vm(), ftier()
    e = rec.get("engine") or {}
    rounds = max(1, e.get("generated", 0) - e.get("drafts_accepted", 0))
    o = {"item": item, "ttft_s": rec.get("ttft_s"), "decode_tps": e.get("decode_tps"), "generated": e.get("generated"),
         "rounds": rounds, "nvme_read_mb": (d1 - d0) / 1e6, "file_tier_mb": f1[1] - f0[1], "file_tier_blobs": f1[0] - f0[0],
         "swap_in_pages": v1["pswpin"] - v0["pswpin"], "swap_out_pages": v1["pswpout"] - v0["pswpout"],
         "drafts_accepted": e.get("drafts_accepted"), "drafts_offered": e.get("drafts_offered"),
         "acceptance": (e["drafts_accepted"] / e["drafts_offered"]) if e.get("drafts_offered") else None,
         "tokens_per_round": (e.get("generated", 0) / rounds) if e.get("generated") else None, "output_tokens": rec.get("completion_tokens"),
         "finish": rec.get("finish_reason"), "t_total_s": rec.get("t_total_s")}
    o["nvme_mb_per_round"] = o["nvme_read_mb"] / rounds; o["file_mb_per_round"] = o["file_tier_mb"] / rounds
    out.append(o); print(json.dumps(o), flush=True)
(WS / f"results/r12/q4io-{L}.json").write_text(json.dumps(out, indent=1))
