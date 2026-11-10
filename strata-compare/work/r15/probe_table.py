#!/usr/bin/env python3
"""probe_table.py NAME — round 15 step 3: the probe table of one stand-in's placements (results/r15/s3/r15-NAME-X-probe.txt
and the --stats outputs of the agreeing pair), and the full-set choice: the best placement by decode, placement B, and
the runner-up when it is within 10 % of the best (your rules)."""
import json
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
PF = WS / "bringup/out/logs/prof"
name = sys.argv[1]


def stats(label):
    f = PF / f"{label}.out"
    if not f.exists():
        return {}
    t = f.read_text(errors="replace")
    d = {}
    m = re.search(r"^decode\s+\d+ tokens in [\d.]+ ms\s+->\s+([\d.]+) tok/s", t, re.M)
    if m: d["tps"] = float(m[1])
    m = re.search(r"^speculation\s+(\d+) rounds of \d+, drafts accepted (\d+) of (\d+) \(([\d.]+)\), ([\d.]+) tokens per round", t, re.M)
    if m:
        d["acc"] = float(m[4]); d["tpr"] = float(m[5])
        if "tps" in d: d["ms_round"] = 1000 / d["tps"] * d["tpr"]
    m = re.search(r"verify window\s+wait for rings ([\d.]+)\s+pool ([\d.]+)", t)
    if m: d["rings"] = float(m[1]); d["pool"] = float(m[2])
    m = re.search(r"expert tiers\s+decode: RAM (\d+) blobs, files (\d+) blobs, ([\d.]+) MB read from the files \(([\d.]+) MB/round, ([\d.]+) ms/round of reading", t)
    if m: d["ram_blobs"] = int(m[1]); d["file_blobs"] = int(m[2]); d["file_mb_round"] = float(m[4]); d["file_ms_round"] = float(m[5])
    m = re.search(r"page cache held ([\d.]+) MB, not ([\d.]+) MB", t)
    if m: d["pc_held"] = float(m[1]); d["pc_miss"] = float(m[2])
    m = re.search(r"decode waited ([\d.]+) ms/round in the fetches", t)
    if m: d["fetch_wait"] = float(m[1])
    m = re.search(r"R4 expert-cache hits\s+(\d+) of (\d+)", t)
    if m: d["hits"] = int(m[1]); d["routed"] = int(m[2])
    m = re.search(r"CUDA1 experts\s+(\d+) routed", t)
    if m: d["cuda1"] = int(m[1])
    m = re.search(r"min_MemAvailable=([\d.]+)GiB", t)
    if m: d["minavail"] = float(m[1])
    m = re.search(r"max_swap_used=([\d.]+)GiB", t)
    if m: d["swap"] = float(m[1])
    m = re.search(r"min_5080_free=(\d+)MiB", t)
    if m: d["min5080"] = int(m[1])
    m = re.search(r"^prefill\s+(\d+) tokens in ([\d.]+) ms", t, re.M)
    if m: d["ttft_ms"] = float(m[2])   # the prompt read itself (the CLI's "time to first token" includes the load / page-locking)
    return d


def f(v, n=1):
    return "–" if v is None else f"{v:.{n}f}"


rows = {}
for X in "ABCDE":
    L = f"r15-{name}-{X}"
    p = WS / f"results/r15/s3/{L}-probe.txt"
    if not p.exists():
        continue
    t = p.read_text(errors="replace")
    if "started (served" in t:   # round 15: the layer split runs only under --serve (s3probe_srv.py)
        pr = [json.loads(q.read_text()) for q in sorted((WS / "results/r15/s3").glob(f"{L}-probe-[0-9].json"))]
        ag = re.search(r"^AGREED (\d) (\d)", t, re.M)
        sel = [pr[int(ag[1]) - 1], pr[int(ag[2]) - 1]] if ag else pr[-2:]
        mn = lambda k: (sum(x[k] for x in sel if x.get(k) is not None) / max(1, len([x for x in sel if x.get(k) is not None]))) if sel else None
        g = WS / f"bringup/out/logs/guard/srv-{L}.csv"
        import csv as _csv
        gr = list(_csv.DictReader(open(g))) if g.exists() else []
        k32 = re.search(r"32K: prompt \d+ tokens read in ([\d.]+) s", t)
        slots = re.search(r"expert cache (\d+) slots", t)
        rows[X] = dict(label=L + " (served)", started=True, ctx=131072, why=[], agreed=bool(ag), nprobes=len(pr), tps=mn("tps"),
                       ms_round=mn("ms_round"), tpr=mn("tpr"), acc=mn("acc"), pool=None, file_ms=None, file_mb=None,
                       fetch_wait=None, share5080=sel[-1].get("share5080") if sel else None,
                       share_cuda1=sel[-1].get("share_card2") if sel else None, pc_miss=None,
                       minavail=min((float(r["memavail_gib"]) for r in gr), default=None),
                       swap=max((float(r["swap_used_gib"]) for r in gr), default=None),
                       min5080=min((int(float(r["vram_free_mib"])) for r in gr), default=None),
                       ttft32k=float(k32[1]) * 1000 if k32 else None, slots=int(slots[1]) if slots else None)
        continue
    started = "started at" in t
    ctx = re.search(r"started at --max-context (\d+)", t)
    why = re.findall(r"did NOT start at --max-context (\d+): (.*)", t)
    probes = sorted({int(x) for x in re.findall(r"^probe (\d):", t, re.M)})
    # round 15: the agreement is re-checked here with the current rule (probe_agree.py: decode within 3 %), so a probe
    # file written under the first rule is read the same way as the later ones
    import subprocess
    ag = None
    for a_, b_ in zip(probes, probes[1:]):
        r_ = subprocess.run([sys.executable, str(WS / "work/r15/probe_agree.py"), f"{L}-probe-{a_}", f"{L}-probe-{b_}"],
                            capture_output=True, text=True)
        if r_.returncode == 0:
            ag = (None, str(a_), str(b_))
            break
    pair = [f"{L}-probe-{ag[1]}", f"{L}-probe-{ag[2]}"] if ag else []
    if not pair and probes:
        pair = [f"{L}-probe-{k}" for k in probes[-2:]]
    s = [stats(x) for x in pair]
    s = [x for x in s if x]
    mean = lambda k: (sum(x[k] for x in s if k in x) / len([x for x in s if k in x])) if any(k in x for x in s) else None
    last = s[-1] if s else {}
    k32 = stats(f"{L}-probe-32k")
    slots = re.search(r"expert cache (\d+) slots", t)
    rows[X] = dict(label=L, started=started, ctx=int(ctx[1]) if ctx else None, why=why, agreed=bool(ag), nprobes=len(probes),
                   tps=mean("tps"), ms_round=mean("ms_round"), tpr=mean("tpr"), acc=mean("acc"), pool=mean("pool"),
                   file_ms=mean("file_ms_round"), file_mb=mean("file_mb_round"), fetch_wait=mean("fetch_wait"),
                   share5080=(last["hits"] / last["routed"]) if last.get("routed") else None,
                   share_cuda1=(last.get("cuda1", 0) / last["routed"]) if last.get("routed") else None,
                   pc_miss=(last["pc_miss"] / (last["pc_held"] + last["pc_miss"])) if last.get("pc_held") is not None and (last["pc_held"] + last["pc_miss"]) else None,
                   minavail=min([x["minavail"] for x in s if "minavail" in x], default=None),
                   swap=max([x["swap"] for x in s if "swap" in x], default=None),
                   min5080=min([x["min5080"] for x in s if "min5080" in x], default=None),
                   ttft32k=k32.get("ttft_ms"), slots=int(slots[1]) if slots else None)
print(f"# Round 15 step 3 — probes of every placement, {name} (engine level, greedy math 1,024, warmed; the number = the mean "
      f"of two consecutive warm probes whose decode agrees within 3 %; your rule of 10-07 ~14:10)\n")
print("| placement | started (context) | probes / agreed | decode tok/s | ms / round | tokens / round | acceptance (greedy) | "
      "5080 share | helper share | CPU share | CPU pool ms / round | file-tier reading ms / round (MB) | fetch wait ms / round | "
      "not in the page cache | 5080 slots | min MemAvailable GiB | swap GiB | 5080 min free MiB | 32K prompt read s |")
print("|---|" + "---|" * 19)
for X, r in rows.items():
    if not r["started"]:
        print(f"| {X} | **no**: {'; '.join(f'{c}: {w[:160]}' for c, w in r['why'])} |" + " |" * 18)
        continue
    cpu = (1 - (r["share5080"] or 0) - (r["share_cuda1"] or 0)) if r["share5080"] is not None else None
    print(f"| {X} | {r['ctx']} | {r['nprobes']} / {'yes' if r['agreed'] else 'NO'} | **{f(r['tps'], 2)}** | {f(r['ms_round'])} | "
          f"{f(r['tpr'], 2)} | {f(r['acc'], 3)} | {f(r['share5080'], 3)} | {f(r['share_cuda1'], 3)} | {f(cpu, 3)} | {f(r['pool'])} | "
          f"{f(r['file_ms'])} ({f(r['file_mb'], 0)}) | {f(r['fetch_wait'])} | {f(r['pc_miss'], 2)} | {r['slots'] or '–'} | "
          f"{f(r['minavail'])} | {f(r['swap'], 2)} | {r['min5080'] if r['min5080'] is not None else '–'} | "
          f"{f(r['ttft32k'] / 1000 if r['ttft32k'] else None, 1)} |")
ok = {X: r for X, r in rows.items() if r["started"] and r["tps"]}
rank = sorted(ok, key=lambda X: -ok[X]["tps"])
full = []
if rank:
    full.append(rank[0])
    if len(rank) > 1 and ok[rank[1]]["tps"] >= 0.9 * ok[rank[0]]["tps"]:
        full.append(rank[1])
    if "B" in ok and "B" not in full:
        full.append("B")
print("\nranking by decode: " + " > ".join(f"{X} {ok[X]['tps']:.2f}" for X in rank))
print(f"FULL SET ON: {' '.join(full)}  (the best; the runner-up when within 10 % of it; placement B)")
(WS / f"results/r15/s3-probes-{name}.json").write_text(json.dumps({"rows": rows, "rank": rank, "full": full}, indent=1))
