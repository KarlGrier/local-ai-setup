"""paid_policy.py - Karl's paid-search rule (10-27), applied by exa_fallback.py and tavily_fallback.py inside their
locked monthly counters, for every caller.

  * Allowances a month (Karl): Tavily about 850 searches, Exa about 2,250 Lite searches ($9.00 at $0.004).
  * Jan chat and the Strata chat page ("chat"): paid search until 10 % of the month is left.
  * Karl's own research ("research") and test runs ("test"): until 25 % is left (that quarter is Jan chat's), and at most
    100 (research) or 30 (test) paid searches per run.
  * A caller names itself in `client`: "jan", "chat", or "ldr:<research id>" - LDR's class comes from LDR_PAID_CLASS
    (run-ldr.sh: "research" for the Jan runner's jobs, "test" for phase 4 item 7's runs; default "research").
The counters are per calendar month (UTC), as before; the per-run counts sit in the same record ("runs").
"""
from __future__ import annotations

import os

STOP_ALL = 0.10            # all paid search stops with 10 % of the month left
KEEP_FOR_CHAT = 0.25       # research and tests stop with 25 % left
PER_RUN = {"research": 100, "test": 30}


def classify(client: str) -> tuple[str, str]:
    """(class, run id) of a caller."""
    c = (client or "?").strip()
    if c.startswith("ldr"):
        run = c.split(":", 1)[1] if ":" in c else ""
        k = os.environ.get("LDR_PAID_CLASS", "research").strip().lower()
        return (k if k in PER_RUN else "research"), run
    if c in ("jan", "chat"):
        return "chat", ""
    return "research", c                      # an unknown caller is held to the stricter rule


def check(used: float, cost: float, allowance: float, client: str, runs: dict) -> tuple[bool, str]:
    """May a search costing `cost` (in the counter's unit) go out, with `used` spent of `allowance` this month and
    `runs` = {run id: searches this month}? (ok, reason when not)."""
    klass, run = classify(client)
    limit = allowance * (1 - (STOP_ALL if klass == "chat" else KEEP_FOR_CHAT))
    if used + cost > limit + 1e-9:
        left = max(0.0, allowance - used) / allowance if allowance > 0 else 0.0
        return False, (f"{klass}: {left:.0%} of the month's allowance left (stops at "
                       f"{STOP_ALL if klass == 'chat' else KEEP_FOR_CHAT:.0%})")
    if klass in PER_RUN and run and (runs or {}).get(run, 0) >= PER_RUN[klass]:
        return False, f"{klass}: this run's {PER_RUN[klass]} paid searches are used"
    return True, ""


def count_run(d: dict, client: str) -> None:
    """Count one search for the caller's run in the month record d."""
    klass, run = classify(client)
    if klass in PER_RUN and run:
        runs = d.setdefault("runs", {})
        runs[run] = runs.get(run, 0) + 1
