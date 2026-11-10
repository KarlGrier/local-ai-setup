#!/usr/bin/env python3
"""paid_tracker.py - one month of paid search against Karl's rule (phase 4 item 7, staged 10-29; not installed).

Reads, never writes: the month counters (exa-usage.json in dollars, tavily-usage.json in credits), paid_budget's run
counts (paid-runs.json), the providers' logs (exa-fallback.jsonl, tavily-fallback.jsonl: one line per search with
client, kind, run and outcome) and the router's log (paid-route.jsonl: cache hits). Only those files are opened - never
the key files next to the counters - and no query text is printed.

Prints (or writes with --write DIR: paid-<month>.json and paid-<month>.txt) a table per month:
* per provider: used vs the month's credit, left, and the two thresholds - tests and research stop at 25 % left
  (Exa $7.50, Tavily 750 used), every caller at 10 % left (Exa $9.00, Tavily 900);
* per provider and caller kind (chat / test / research): searches sent, refused, used, cache hits and what they saved;
* per run: searches sent per provider, the run cap (test 30, research 100), left, paid_budget's own count, cache hits.

The month is the counters' UTC calendar month. The provider logs carry local time ("t"), so a search in the first or
last hours of a month can fall into the neighbouring one there; the counters are the reference for "used" while they
hold the month asked for, the logs otherwise. Log lines from before item 7 have no kind: "ldr" is research, every other
client chat.

  paid_tracker.py [--month YYYY-MM] [--json] [--write DIR] [--exa-usage F] [--tavily-usage F] [--runs F]
                  [--exa-log F] [--tavily-log F] [--route-log F]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paid_budget  # noqa: E402

CFG = Path.home() / ".config" / "deep-research"
LOGS = Path("/home/USER/ai/deep-research/logs")
DEFAULTS = {"exa_usage": CFG / "exa-usage.json", "tavily_usage": CFG / "tavily-usage.json",
            "runs": CFG / "paid-runs.json", "exa_log": LOGS / "exa-fallback.jsonl",
            "tavily_log": LOGS / "tavily-fallback.jsonl", "route_log": LOGS / "paid-route.jsonl"}
PROVIDERS = {"exa": {"credit": 10.0, "unit": "usd", "est": 0.004},
             "tavily": {"credit": 1000.0, "unit": "credits", "est": 1.0}}


def _json(p: Path) -> dict:
    try:
        d = json.loads(Path(p).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _lines(p: Path):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    yield d
    except OSError:
        return


def _kind(rec: dict) -> str:
    k = str(rec.get("kind") or "")
    if k in paid_budget.KINDS:
        return k
    return "research" if rec.get("client") == "ldr" else "chat"


def fmt(provider: str, v: float) -> str:
    return f"${v:.3f}" if PROVIDERS[provider]["unit"] == "usd" else f"{v:g}"


def collect(month: str, paths: dict) -> dict:
    kinds = {p: {k: {"sent": 0, "refused": 0, "errors": 0, "used": 0.0, "cache_hits": 0, "saved": 0.0}
                 for k in paid_budget.KINDS} for p in PROVIDERS}
    runs: dict[str, dict] = {}
    log_used = {p: 0.0 for p in PROVIDERS}
    log_sent = {p: 0 for p in PROVIDERS}

    def run_row(run, kind):
        key = run or f"(no run id: {kind})"
        return runs.setdefault(key, {"run": key, "kind": kind, "exa": 0, "tavily": 0, "refused": 0, "cache_hits": 0})

    for p in PROVIDERS:
        for r in _lines(paths[f"{p}_log"]):
            if str(r.get("t", ""))[:7] != month:
                continue
            k = _kind(r)
            row = kinds[p][k]
            if "skipped" in r:
                row["refused"] += 1
                if k != "chat":
                    run_row(r.get("run"), k)["refused"] += 1
                continue
            if "results" not in r and "error" not in r:
                continue
            cost = PROVIDERS[p]["est"]
            if p == "exa" and isinstance(r.get("cost_usd"), (int, float)):
                cost = float(r["cost_usd"])
            row["sent"] += 1
            row["errors"] += "error" in r
            row["used"] += cost
            log_used[p] += cost
            log_sent[p] += 1
            if k != "chat":
                run_row(r.get("run"), k)[p] += 1
    for r in _lines(paths["route_log"]):
        if str(r.get("month") or str(r.get("t", ""))[:7]) != month:
            continue
        k = _kind(r)
        for a in r.get("actions") or []:
            if isinstance(a, dict) and a.get("outcome") == "cache hit" and a.get("source") in PROVIDERS:
                p = a["source"]
                kinds[p][k]["cache_hits"] += 1
                kinds[p][k]["saved"] += float(a.get("saved") or PROVIDERS[p]["est"])
                if k != "chat":
                    run_row(r.get("run"), k)["cache_hits"] += 1

    rf = _json(paths["runs"])
    rf_runs = rf.get("runs", {}) if rf.get("month") == month else {}
    for run, n in rf_runs.items():
        row = runs.get(run) or run_row(run, "?")
        row["runs_file"] = n
    for row in runs.values():
        row["total"] = row["exa"] + row["tavily"]
        cap = paid_budget.RUN_CAP.get(row["kind"])
        row["cap"] = cap
        row["left"] = None if cap is None or row["run"].startswith("(no run id") else max(0, cap - max(row["total"], row.get("runs_file", 0)))
        row.setdefault("runs_file", None)

    providers = {}
    for p, spec in PROVIDERS.items():
        c = _json(paths[f"{p}_usage"])
        if c.get("month") == month:
            used = float(c.get("usd" if p == "exa" else "count") or 0.0)
            src = "counter"
        else:
            used, src = round(log_used[p], 6), "logs"
        credit = spec["credit"]
        stop_tests = credit * (1 - paid_budget.KEEP_FOR_CHAT)
        stop_all = credit * (1 - paid_budget.ALL_STOP)
        status = ("all stopped (provider said out of credit)" if c.get("closed") else
                  "all stopped (10 % left)" if used >= stop_all - 1e-9 else
                  "tests/research stopped (25 % left kept for chat)" if used >= stop_tests - 1e-9 else "ok")
        providers[p] = {"unit": spec["unit"], "credit": credit, "used": round(used, 6), "used_from": src,
                        "left": round(max(0.0, credit - used), 6), "left_pct": round(100 * max(0.0, credit - used) / credit, 1),
                        "stop_tests_research_at": stop_tests, "to_go_tests_research": round(max(0.0, stop_tests - used), 6),
                        "stop_all_at": stop_all, "to_go_all": round(max(0.0, stop_all - used), 6),
                        "status": status, "closed": bool(c.get("closed")), "sent_in_logs": log_sent[p],
                        "cache_hits": sum(kinds[p][k]["cache_hits"] for k in kinds[p]),
                        "saved": round(sum(kinds[p][k]["saved"] for k in kinds[p]), 6)}
    for p in kinds:
        for k in kinds[p]:
            kinds[p][k]["used"] = round(kinds[p][k]["used"], 6)
            kinds[p][k]["saved"] = round(kinds[p][k]["saved"], 6)
    return {"month": month, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "providers": providers, "kinds": kinds,
            "runs": sorted(runs.values(), key=lambda r: (r["kind"], r["run"])),
            "rule": {"run_cap": paid_budget.RUN_CAP, "keep_for_chat": paid_budget.KEEP_FOR_CHAT,
                     "all_stop": paid_budget.ALL_STOP},
            "sources": {k: {"path": str(v), "present": Path(v).is_file()} for k, v in paths.items()}}


def text(rep: dict) -> str:
    L = [f"Paid search, {rep['month']} (UTC month; counters and logs, read-only)", ""]
    L.append(f"{'provider':<9}{'used':>10}{'of':>10}{'left':>8}   {'tests/research stop at':<26}{'all stop at':<22}status")
    for p, d in rep["providers"].items():
        L.append(f"{p:<9}{fmt(p, d['used']):>10}{fmt(p, d['credit']):>10}{d['left_pct']:>7.1f}%   "
                 f"{fmt(p, d['stop_tests_research_at']) + ' (' + fmt(p, d['to_go_tests_research']) + ' to go)':<26}"
                 f"{fmt(p, d['stop_all_at']) + ' (' + fmt(p, d['to_go_all']) + ' to go)':<22}{d['status']}"
                 + ("" if d["used_from"] == "counter" else "  [from logs]"))
    L += ["", f"{'provider / kind':<20}{'sent':>6}{'refused':>9}{'errors':>8}{'used':>11}{'cache hits':>12}{'saved':>10}"]
    for p, ks in rep["kinds"].items():
        for k, d in ks.items():
            if any(d[x] for x in ("sent", "refused", "cache_hits")):
                L.append(f"{p + ' / ' + k:<20}{d['sent']:>6}{d['refused']:>9}{d['errors']:>8}{fmt(p, d['used']):>11}"
                         f"{d['cache_hits']:>12}{fmt(p, d['saved']):>10}")
    L += ["", f"runs (cap: test {rep['rule']['run_cap']['test']}, research {rep['rule']['run_cap']['research']}; "
              "both providers together)"]
    L.append(f"{'run':<28}{'kind':<10}{'exa':>5}{'tavily':>8}{'total':>7}{'cap':>5}{'left':>6}{'runs file':>11}"
             f"{'refused':>9}{'cache hits':>12}")
    for r in rep["runs"]:
        L.append(f"{r['run'][:27]:<28}{r['kind']:<10}{r['exa']:>5}{r['tavily']:>8}{r['total']:>7}"
                 f"{'' if r['cap'] is None else r['cap']:>5}{'' if r['left'] is None else r['left']:>6}"
                 f"{'' if r['runs_file'] is None else r['runs_file']:>11}{r['refused']:>9}{r['cache_hits']:>12}")
    if not rep["runs"]:
        L.append("(no test or research runs this month)")
    missing = [k for k, v in rep["sources"].items() if not v["present"]]
    if missing:
        L += ["", "missing (counted as empty): " + ", ".join(missing)]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--month", default=time.strftime("%Y-%m", time.gmtime()))
    ap.add_argument("--json", action="store_true", help="print JSON instead of the table")
    ap.add_argument("--write", metavar="DIR", help="also write paid-<month>.json and .txt into DIR")
    for k, v in DEFAULTS.items():
        ap.add_argument("--" + k.replace("_", "-"), dest=k, default=str(v))
    a = ap.parse_args(argv)
    paths = {k: Path(getattr(a, k)) for k in DEFAULTS}
    rep = collect(a.month, paths)
    out = json.dumps(rep, indent=1) if a.json else text(rep)
    sys.stdout.write(out if out.endswith("\n") else out + "\n")
    if a.write:
        d = Path(a.write)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"paid-{a.month}.json").write_text(json.dumps(rep, indent=1) + "\n")
        (d / f"paid-{a.month}.txt").write_text(text(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
