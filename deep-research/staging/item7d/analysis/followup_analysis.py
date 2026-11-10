"""Item 7d evidence (11-03): opening vs follow-up searches in the past item 7 runs, and a replay of the STAGED rule.

Reads only bench test outputs: logs/paid-route.jsonl (kind "test" rows; p7b o03's discarded first attempt left out),
results/bench2/runs/<run>/deep/evidence.jsonl (each search's agent, time and results; fetches and reads) and
deep/report.md (cited URLs). Never Karl's own research (jobs/, reports/, results/deep-runs/, results/quick-runs/, data/).
Writes followup-analysis.json and followup-analysis.txt next to this file. python -I -B followup_analysis.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))            # the staged 7d search_route (the rule that would run)
import search_route as R  # noqa: E402

WS = Path("/home/USER/ai/deep-research")
RUNS = WS / "results" / "bench2" / "runs"
LOG = WS / "logs" / "paid-route.jsonl"
OPEN = ["screen-deep-p7b/o01", "screen-deep-p7b/o02", "screen-deep-p7b/o03", "screen-deep-p7c/o01",
        "screen-deep-p7c/o02", "screen-deep-p7c/o03", "screen-deep-p7a/o01", "screen-deep-p7a/o02", "screen-deep-p7a/o03",
        "screen-deep-p4s8/o01", "screen-deep-p4s8/o02", "screen-deep-p4s8/o03",
        "shop-7e-deep-p7ex/s1", "shop-7e-deep-p7ex/s2", "shop-7e-deep-p7ex/s3", "shop-7e-deep-p7ex/s4",
        "shop-7e-deep-p7ew/s1", "shop-7e-deep-p7ew/s2", "shop-7e-deep-p7ew/s3", "shop-7e-deep-p7ew/s4"]
HARD = [f"hard-screen-deep-{a}/{h}" for a in ("p4s8", "p7b", "p7c", "p7a") for h in ("h02", "h04", "h05", "h06", "h08")]
PAID_ARMS = ("screen-deep-p7b", "screen-deep-p7c", "shop-7e-deep-p7ex")   # paid searches actually sent (first 30)
SEL = R.SELECT_DEFAULT
URLRX = re.compile(r"https?://[^\s)\]>\"']+")
STORES = re.compile(r"\b(?:amazon|newegg|best ?buy|micro ?center|b&h|walmart|ebay|bestvaluegpu|hardwareswap|"
                    r"techpowerup|manualslib|rtx\.live|pcpartpicker|centralcomputer)\b", re.I)
NUMTOK = re.compile(r"\b(?:v?\d+\.\d+(?:\.\d+)?|\d{3,5}[a-z]*|[a-z]+-?\d{2,}[a-z]*|\d+\s?(?:gb|tb|mb|w|mm|gbps|mt/s))\b",
                    re.I)


def norm(u) -> str:
    return str(u or "").strip().split("#", 1)[0].rstrip("/")


def route_rows() -> dict[str, list[dict]]:
    out = collections.defaultdict(list)
    for line in filter(None, LOG.read_text().split("\n")):     # "\n" only: strings may hold U+2028
        r = json.loads(line)
        if r.get("kind") != "test":
            continue
        if r["run"] == "screen-deep-p7b/o03" and r["t"] < "2026-11-01T00:50":
            continue                                       # the discarded first attempt (60 Tavily, 10-31)
        out[r["run"]].append(r)
    return out


ROUTE = route_rows()


def load(run: str) -> dict:
    """The run's searches in hook order with agent, time (s since the first search), SearXNG count, tag, paid flag."""
    ev = [json.loads(x) for x in (RUNS / run / "deep" / "evidence.jsonl").read_text().split("\n") if x]
    S = [r for r in ev if r["type"] == "search"]
    used = {norm(r["url"]) for r in ev if r["type"] in ("fetch", "read")}
    rep = (RUNS / run / "deep" / "report.md").read_text(encoding="utf-8", errors="replace")
    cited = {norm(u.rstrip(".,;")) for u in URLRX.findall(rep)}
    rows = ROUTE.get(run)
    out = []
    if rows:                                               # hook order = the route log's order
        byq = collections.defaultdict(list)
        for s in S:
            byq[s["query"]].append(s)
        for r in rows:
            s = byq[r["query"]].pop(0) if byq[r["query"]] else None
            if s is None:
                continue
            out.append(dict(q=r["query"], agent=s["agent"], t=s["t"], nsx=r["searxng"], res=s["results"], tag=r["tag"],
                            sent=any(a.get("outcome") == "sent" and a.get("source") in ("exa", "tavily")
                                     for a in r["actions"])))
    else:
        for s in S:
            out.append(dict(q=s["query"], agent=s["agent"], t=s["t"], nsx=len(s["results"]), res=s["results"],
                            tag=R.classify(s["query"], 2026)[0], sent=False))
    t0 = out[0]["t"] if out else 0.0
    subs = lead_after = False
    rank = collections.Counter()
    seen: set[str] = set()
    allsx = {norm(y["url"]) for x in out for y in x["res"][:x["nsx"]]}
    for i, x in enumerate(out):
        a = x["agent"]
        if a == "lead":
            x["phase"] = "lead-follow" if subs else "lead-open"
            lead_after = lead_after or subs
        else:
            subs = True
            x["phase"] = "wave2+" if lead_after else "wave1"
        rank[a] += 1
        x.update(i=i + 1, rank=rank[a], dt=x["t"] - t0)
        sxu = [norm(y["url"]) for y in x["res"][:x["nsx"]]]
        x["sx_new"] = sum(u not in seen for u in sxu)
        x["sx_n"] = len(sxu)
        x["sx_used"] = sum((u in used) or (u in cited) for u in sxu)
        seen.update(sxu)
        pu = [norm(y["url"]) for y in x["res"][x["nsx"]:] if norm(y["url"]) not in allsx] if x["sent"] else []
        x["paid_unique"] = len(pu)
        x["paid_used"] = sum((u in used) or (u in cited) for u in pu)
        x["paid_cited"] = sum(u in cited for u in pu)
    return {"run": run, "s": out}


def features(q: str) -> dict:
    return {"words": len(q.split()), "quoted": '"' in q, "number": bool(NUMTOK.search(q)),
            "operator": bool(re.search(r"\b(?:site|filetype):|\bOR\b", q)), "store": bool(STORES.search(q))}


def fcfs(stream, cap=30):
    return [x for x in stream][:cap]


def replay(stream, sel=SEL, cap=30):
    """The staged rule over a past run (the run cap of 30 as paid_budget applies it)."""
    st = R.new_state(0.0)
    picked = []
    for x in stream:
        p, _ = R.select_step(st, x["agent"], sel, x["dt"])
        if p and len(picked) < cap:
            picked.append(x)
    return picked, st


def summary(picked, stream):
    return {"paid": len(picked), "agents": len({x["agent"] for x in picked}),
            "lead": sum(x["agent"] == "lead" for x in picked),
            "followup_phase": sum(x["phase"] in ("lead-follow", "wave2+") for x in picked),
            "first": picked[0]["i"] if picked else None, "last": picked[-1]["i"] if picked else None,
            "sx_new_pct": round(100 * sum(x["sx_new"] for x in picked) / max(1, sum(x["sx_n"] for x in picked)), 1),
            "product": sum(x["tag"] == "product" for x in picked), "searches": len(stream)}


def main() -> None:
    runs = [load(r) for r in OPEN]
    hard = [load(r) for r in HARD if (RUNS / r / "deep" / "evidence.jsonl").exists()]
    res: dict = {"rule": SEL, "runs": {}, "hard": {}}
    # A. structure + B. the two allocations
    for d in runs:
        s = d["s"]
        fu = next((x for x in s if x["phase"] == "lead-follow"), None)
        picked, st = replay(s)
        res["runs"][d["run"]] = {
            "searches": len(s), "first_lead_followup": fu["i"] if fu else None,
            "first_lead_followup_s": round(fu["dt"]) if fu else None,
            "phase_counts": dict(collections.Counter(x["phase"] for x in s)),
            "fcfs": summary(fcfs(s), s), "rule": summary(picked, s), "rule_follow_at": st["follow_at"]}
    for d in hard:
        picked, _ = replay(d["s"])
        res["hard"][d["run"]] = {"searches": len(d["s"]), "agents": sorted({x["agent"] for x in d["s"]}),
                                 "rule_paid": len(picked)}
    # C. what the searches look like, by phase (+ the first-30 slice of wave 1)
    groups = collections.defaultdict(list)
    for d in runs:
        for x in d["s"]:
            groups[x["phase"]].append(x)
            groups["searches 1-30" if x["i"] <= 30 else "searches 31+"].append(x)
    look = {}
    for g, xs in groups.items():
        f = [features(x["q"]) for x in xs]
        tags = collections.Counter(x["tag"] for x in xs)
        look[g] = {"n": len(xs), "words": round(sum(y["words"] for y in f) / len(f), 1),
                   "quoted_pct": round(100 * sum(y["quoted"] for y in f) / len(f)),
                   "number_pct": round(100 * sum(y["number"] for y in f) / len(f)),
                   "operator_pct": round(100 * sum(y["operator"] for y in f) / len(f)),
                   "store_pct": round(100 * sum(y["store"] for y in f) / len(f)),
                   "product_tag_pct": round(100 * tags["product"] / len(xs)),
                   "sx_new_pct": round(100 * sum(x["sx_new"] for x in xs) / max(1, sum(x["sx_n"] for x in xs))),
                   "sx_used_pct": round(100 * sum(x["sx_used"] for x in xs) / max(1, sum(x["sx_n"] for x in xs)), 1)}
    res["look"] = look
    # D. paid URLs that were used (fetched / read / cited), by the search's rank within its agent - sent searches only
    by = collections.defaultdict(lambda: collections.Counter())
    for d in runs:
        if not d["run"].startswith(PAID_ARMS):
            continue
        for x in d["s"]:
            if not x["sent"]:
                continue
            k = "rank 1" if x["rank"] == 1 else ("rank 2-3" if x["rank"] <= 3 else "rank 4+")
            for key in (k, "all"):
                c = by[key]
                c["searches"] += 1
                c["paid_unique"] += x["paid_unique"]
                c["paid_used"] += x["paid_used"]
                c["paid_cited"] += x["paid_cited"]
                c["sx_n"] += x["sx_n"]
                c["sx_used"] += x["sx_used"]
    res["paid_use"] = {k: {**v, "paid_used_pct": round(100 * v["paid_used"] / max(1, v["paid_unique"]), 1),
                           "sx_used_pct": round(100 * v["sx_used"] / max(1, v["sx_n"]), 1),
                           "paid_used_per_search": round(v["paid_used"] / max(1, v["searches"]), 2)}
                       for k, v in by.items()}
    # E. sx redundancy by position
    pos = collections.defaultdict(lambda: [0, 0])
    for d in runs:
        for x in d["s"]:
            b = next(f"{lo}-{hi}" for lo, hi in ((1, 30), (31, 60), (61, 100), (101, 150), (151, 999)) if lo <= x["i"] <= hi)
            pos[b][0] += x["sx_new"]
            pos[b][1] += x["sx_n"]
    res["sx_new_by_position"] = {k: round(100 * a / max(1, b)) for k, (a, b) in sorted(pos.items(), key=lambda kv: int(kv[0].split("-")[0]))}
    (HERE / "followup-analysis.json").write_text(json.dumps(res, indent=1))
    # text
    L = [f"Item 7d evidence - staged rule {SEL}", ""]
    L.append("run                       searches  1st lead follow-up (#, s)  | first come: agents lead fu-phase sxnew% | rule: paid agents lead fu-phase pos      sxnew% product")
    for run, v in res["runs"].items():
        f, r = v["fcfs"], v["rule"]
        L.append(f"{run:26s} {v['searches']:5d}   {str(v['first_lead_followup']):>5s} {str(v['first_lead_followup_s']):>6s}           |"
                 f" {f['agents']:6d} {f['lead']:4d} {f['followup_phase']:8d} {f['sx_new_pct']:6.0f}  |"
                 f" {r['paid']:4d} {r['agents']:6d} {r['lead']:4d} {r['followup_phase']:8d} {str(r['first'])+'-'+str(r['last']):>8s} {r['sx_new_pct']:6.0f} {r['product']:7d}")
    rr = list(res["runs"].values())
    m = lambda k, w: sum(v[w][k] for v in rr) / len(rr)  # noqa: E731
    L.append(f"{'MEAN':26s} {sum(v['searches'] for v in rr) / len(rr):5.0f}                              |"
             f" {m('agents', 'fcfs'):6.1f} {m('lead', 'fcfs'):4.1f} {m('followup_phase', 'fcfs'):8.1f} {m('sx_new_pct', 'fcfs'):6.0f}  |"
             f" {m('paid', 'rule'):4.1f} {m('agents', 'rule'):6.1f} {m('lead', 'rule'):4.1f} {m('followup_phase', 'rule'):8.1f} {'':>8s} {m('sx_new_pct', 'rule'):6.0f} {m('product', 'rule'):7.1f}")
    L += ["", "hard five (lead only): " + ", ".join(f"{k.split('-deep-')[1]} {v['searches']} searches -> {v['rule_paid']} paid"
                                                for k, v in res["hard"].items())]
    L += ["", "what the searches look like (all 20 runs):",
          "group           n     words quoted% number% operator% store% product% | SearXNG new-to-run% used%"]
    for g in ("lead-open", "searches 1-30", "wave1", "lead-follow", "wave2+", "searches 31+"):
        v = look.get(g)
        if v:
            L.append(f"{g:14s} {v['n']:5d} {v['words']:6.1f} {v['quoted_pct']:7d} {v['number_pct']:7d} {v['operator_pct']:9d}"
                     f" {v['store_pct']:6d} {v['product_tag_pct']:8d} | {v['sx_new_pct']:19d} {v['sx_used_pct']:5.1f}")
    L += ["", "SearXNG URLs new to the run, by search position: " + ", ".join(f"{k}: {v}%" for k, v in res["sx_new_by_position"].items())]
    L += ["", "paid URLs (not in any SearXNG list of the run) later fetched / read / cited, sent searches of p7b / p7c / p7ex (all at positions 1-30):"]
    for k in ("rank 1", "rank 2-3", "rank 4+", "all"):
        v = res["paid_use"].get(k)
        if v:
            L.append(f"  {k:8s} searches {v['searches']:3d}  paid URLs {v['paid_unique']:4d}  used {v['paid_used_pct']:5.1f}%"
                     f" (SearXNG URLs of the same searches {v['sx_used_pct']:4.1f}%)  used per search {v['paid_used_per_search']:.2f}")
    (HERE / "followup-analysis.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
