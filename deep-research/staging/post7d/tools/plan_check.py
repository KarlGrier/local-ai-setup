#!/usr/bin/env python3
"""plan_check.py - read-only check of bench2 queue plans (staged 11-04, staging/post7d). Nothing is started, written
or sent: it reads the plan files, the question files (ids and kinds only - never prints a question), the run folders,
tools/paid-route.json, the model profiles and the bench2.py that will run the plan.

  plan_check.py [--bench2 FILE] [--profiles-dir DIR] [--queue FILE] PLAN [PLAN ...]
      PLAN = a file name in results/bench2/ (as BENCH2_PLAN) or a path.
      --bench2: the bench2.py whose SETS must know every set (default tools/bench2.py; Phase 5 needs the staged
                staging/post7d/tools/bench2.py, which adds p5-harder / p5-o01).
      --profiles-dir: where a step's "model_profile" name is looked up (default profiles/; the C3c profile is staged in
                staging/post7d/profiles/ until the switch installs it).

Per plan: every run in queue order (as `bench2.py next` would hand them out if each one finished), with its budget,
paid route and model profile; problems (exit 1): unknown set (argparse in `bench2.py run` would refuse it), an id not
in the set, a "needs" file missing, an item bench2-queue.sh does not switch, a route not in tools/paid-route.json, a
model profile missing / not "measured" (run-ldr.sh refuses a draft in the queue), a value with spaces, a run folder that
already has bench.json (`next` would skip it as done), the same run in two steps; and a GPU-hour estimate. Across the
plans: two plans writing the same run folder.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
B = WS / "results" / "bench2"
REPORT_ALLOWANCE_MIN = {"deep": {"checkable": 60, "open": 90}, "baseline": {"checkable": 10, "open": 15}}
# measured wall per run (min): deep runs end by their whole-run budget (Fix 6; 171-min runs took 169-176), the
# pristine baseline ~1.5 min checkable / ~30 min open (phase 3); + ~1.5 min for the queue's fresh LDR per question
BASELINE_WALL = {"checkable": 1.5, "open": 30.0}
FRESH_LDR_MIN = 1.5
RUN_CAP = 30


def sets_of(bench2: Path) -> list[str]:
    tree = ast.parse(bench2.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "SETS" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise SystemExit(f"{bench2}: no SETS")


def queue_items(queue: Path) -> set[str]:
    """The items bench2-queue.sh switches: its `case ",$ITEMS," in *,NAME,*)` lines (11-04: names like fix:steps)."""
    t = queue.read_text()
    return set(re.findall(r'case ",\$ITEMS," in \*,([a-z0-9:]+),\*\)', t))


def routes() -> set[str]:
    try:
        return set(json.loads((WS / "tools" / "paid-route.json").read_text())["profiles"])
    except (OSError, ValueError, KeyError):
        return set()


def profile_status(p: Path) -> str | None:
    if not p.exists():
        return None
    st = "measured"
    for line in p.read_text().splitlines():
        m = re.match(r"\s*LDR_PROFILE_STATUS\s*=\s*([^#\s]*)", line)
        if m:
            st = m.group(1)
    return st


def qmeta(set_: str) -> dict[str, str]:
    p = B / f"questions-{set_}.jsonl"
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip():
                q = json.loads(line)
                out[q["id"]] = q.get("kind", "checkable")
    return out


def check(plan_path: Path, sets: list[str], items_ok: set[str], routes_ok: set[str], prof_dir: Path,
          seen_runs: dict[str, str]) -> tuple[list[str], list[dict]]:
    bad, runs = [], []
    steps = json.loads(plan_path.read_text())
    if not isinstance(steps, list) or not steps:
        return [f"{plan_path.name}: not a non-empty list"], []
    for i, st in enumerate(steps, 1):
        where = f"{plan_path.name} step {i}"
        for k in ("set", "profile"):
            if k not in st:
                bad.append(f"{where}: no {k!r}")
        set_, prof, label = st.get("set"), st.get("profile"), st.get("label", "")
        if set_ not in sets:
            bad.append(f"{where}: set {set_!r} is not in this bench2.py's SETS ({', '.join(sets)})")
        if prof not in ("deep", "baseline"):
            bad.append(f"{where}: profile {prof!r}")
        if st.get("needs") and not (B / st["needs"]).exists():
            bad.append(f"{where}: needs {st['needs']}, which does not exist")
        meta = qmeta(set_)
        if not meta:
            bad.append(f"{where}: no question file questions-{set_}.jsonl")
        ids = st.get("ids") or sorted(meta)
        for q in ids:
            if q not in meta:
                bad.append(f"{where}: id {q} not in questions-{set_}.jsonl")
        unknown = sorted(set(st.get("items") or []) - items_ok)
        if unknown:
            bad.append(f"{where}: items {unknown} not switched by bench2-queue.sh ({' '.join(sorted(items_ok))})")
        if prof == "baseline" and (st.get("items") or st.get("effort") or st.get("paid_route")):
            bad.append(f"{where}: a baseline step takes no items, effort or paid route")
        r = st.get("paid_route")
        if r and r not in routes_ok:
            bad.append(f"{where}: paid_route {r!r} not in tools/paid-route.json ({', '.join(sorted(routes_ok))})")
        mp = st.get("model_profile")
        if mp:
            p = Path(mp) if ("/" in mp or mp.endswith(".env")) else prof_dir / f"{mp}.env"
            s = profile_status(p)
            if s is None:
                bad.append(f"{where}: model profile {mp}: no file {p}")
            elif s != "measured":
                bad.append(f"{where}: model profile {mp} is {s!r} - run-ldr.sh refuses it in the queue")
        row = [set_, prof, "x", st.get("effort") or "-", label or "-", st.get("verify_effort") or "-",
               ",".join(st.get("items") or []) or "-", r or "-",
               "-" if st.get("paid_cache") is None else ("on" if st["paid_cache"] else "off"), mp or "-"]
        if any(len(str(x).split()) != 1 for x in row):
            bad.append(f"{where}: a value with spaces or empty: {row}")
        # `next` hands out open questions of a step first (bench2.py sorts them that way)
        for q in sorted(ids, key=lambda x: meta.get(x, "checkable") == "checkable"):
            kind = meta.get(q, "checkable")
            folder = f"{set_}-{prof}{'-' + label if label else ''}"
            key = f"{folder}/{q}"
            if key in seen_runs:
                bad.append(f"{where}: run {key} is already in {seen_runs[key]}")
            seen_runs[key] = f"{plan_path.name} step {i}"
            if (B / "runs" / folder / q / "bench.json").exists():
                bad.append(f"{where}: runs/{key}/bench.json exists - `next` would skip it as done")
            budget = st.get("checkable_min", 30) if kind == "checkable" else st.get("open_min", 120)
            wall = (BASELINE_WALL[kind] if prof == "baseline" else float(budget)) + FRESH_LDR_MIN
            runs.append({"run": key, "kind": kind, "budget_min": budget, "wall_min": wall,
                         "max_min": budget + REPORT_ALLOWANCE_MIN.get(prof, {}).get(kind, 0) + 30,
                         "route": r or "-", "paid_cap": RUN_CAP if r else 0, "model_profile": mp or "flash-next"})
    return bad, runs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--bench2", default=str(WS / "tools" / "bench2.py"))
    ap.add_argument("--profiles-dir", default=str(WS / "profiles"))
    ap.add_argument("--queue", default=str(WS / "tools" / "bench2-queue.sh"),
                    help="the bench2-queue.sh whose item cases count (11-04: the staged one knows fix:steps)")
    a = ap.parse_args()
    sets, items_ok, routes_ok = sets_of(Path(a.bench2)), queue_items(Path(a.queue)), routes()
    seen: dict[str, str] = {}
    rc = 0
    for p in a.plans:
        path = Path(p) if "/" in p else B / p
        bad, runs = check(path, sets, items_ok, routes_ok, Path(a.profiles_dir), seen)
        h = sum(r["wall_min"] for r in runs) / 60
        paid = sum(r["paid_cap"] for r in runs)
        print(f"== {path.name}: {len(runs)} runs, ~{h:.1f} GPU h at the budgets, paid-search cap {paid} "
              f"(bench2.py {Path(a.bench2).relative_to(WS) if Path(a.bench2).is_relative_to(WS) else a.bench2})")
        for n, r in enumerate(runs, 1):
            print(f"  {n:2d} {r['run']:<34} {r['kind']:<9} budget {r['budget_min']:>3} min (client stop "
                  f"{r['max_min']}) route {r['route']:<3} profile {r['model_profile']}")
        for b in bad:
            print(f"  PROBLEM: {b}")
        rc |= 1 if bad else 0
    print("all plans ok" if rc == 0 else "PROBLEMS above")
    return rc


if __name__ == "__main__":
    sys.exit(main())
