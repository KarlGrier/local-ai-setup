"""paid_budget.py - Karl's paid-search rule (10-27, phase 4 item 7) for every caller of exa_fallback / tavily_fallback.

Staged 10-28 (staging/item7); the live counters stay as they are until it is installed. Standard library only.

* Who is asking: PAID_SEARCH_KIND = test | research | chat. Unset, it follows the client name: "ldr" (LDR's searches)
  is Karl's research; "jan" (Jan's chat), "chat" (the Strata chat page) and anything else are chat. LDR is one shared
  process, so for "ldr" the job's starter writes ~/ai/deep-research/run/paid-run.json {"kind", "run"} (the bench queue
  for an item 7 test, the Jan research runner for Karl's research) and removes it at the end; the environment wins.
* Per run, both providers together: a test run at most 30 paid searches, a run of Karl's research at most 100
  (PAID_SEARCH_RUN = the run's id: the bench queue "<label>/<qid>", the Jan research runner its job id; without it the
  run caps cannot be counted, so a test or research caller without a run id gets no paid search at all). Chat has no
  run cap.
* Per month and provider (the counters' own calendar month, UTC): tests and research stop when 25 % of the month's
  credit is left, which stays for chat; every caller stops at 10 % left. Exa's month is $10 of free credit, Tavily's
  1,000 basic searches.
* Run counts in ~/.config/deep-research/paid-runs.json (file-locked; this month's runs only). A reserved search that the
  provider then turns down is given back, so a run's count is the searches actually sent.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path

RUNS_FILE = Path(os.environ.get("PAID_SEARCH_RUNS_FILE", str(Path.home() / ".config" / "deep-research" / "paid-runs.json")))
RUN_CAP = {"test": 30, "research": 100}
KEEP_FOR_CHAT = 0.25      # tests and research stop when this share of the month is left
ALL_STOP = 0.10           # every caller stops when this share is left
KINDS = ("test", "research", "chat")


RUN_NOW_FILE = Path(os.environ.get("PAID_SEARCH_RUN_NOW", "/home/USER/ai/deep-research/run/paid-run.json"))


def _run_now() -> dict:
    try:
        d = json.loads(RUN_NOW_FILE.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def kind(client: str = "?") -> str:
    k = os.environ.get("PAID_SEARCH_KIND", "").strip().lower()
    if k in KINDS:
        return k
    if client != "ldr":
        return "chat"
    k = str(_run_now().get("kind", "")).lower()
    return k if k in ("test", "research") else "research"


def run_id(client: str = "?") -> str:
    r = os.environ.get("PAID_SEARCH_RUN", "").strip()
    if r or client != "ldr":
        return r
    return str(_run_now().get("run") or "").strip()


def month_limit(budget: float, k: str) -> float:
    """The most of a month's budget this kind of caller may use."""
    return budget * (1.0 - (ALL_STOP if k == "chat" else KEEP_FOR_CHAT))


def _month() -> str:
    return time.strftime("%Y-%m", time.gmtime())


def _runs_update(fn):
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNS_FILE.with_suffix(".lock"), "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            d = json.loads(RUNS_FILE.read_text())
        except (OSError, ValueError):
            d = {}
        if d.get("month") != _month():
            d = {"month": _month(), "runs": {}}
        out = fn(d)
        tmp = RUNS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        os.replace(tmp, RUNS_FILE)
        return out


def run_reserve(k: str, client: str = "?") -> tuple[bool, str]:
    """Count one paid search against this run's cap. (True, "") or (False, why). Chat always passes."""
    if k == "chat":
        return True, ""
    run = run_id(client)
    if not run:
        return False, f"no PAID_SEARCH_RUN for a {k} caller"
    cap = int(os.environ.get("PAID_SEARCH_RUN_CAP", RUN_CAP[k]))

    def fn(d):
        n = d["runs"].get(run, 0)
        if n >= cap:
            return False, f"run cap {cap} reached ({run})"
        d["runs"][run] = n + 1
        return True, ""
    return _runs_update(fn)


def run_release(k: str, client: str = "?") -> None:
    """Give back a reserved search the provider did not send (over its month limit)."""
    run = run_id(client)
    if k == "chat" or not run:
        return

    def fn(d):
        if d["runs"].get(run, 0) > 0:
            d["runs"][run] -= 1
    _runs_update(fn)


def run_count(run: str) -> int:
    try:
        d = json.loads(RUNS_FILE.read_text())
    except (OSError, ValueError):
        return 0
    return d.get("runs", {}).get(run, 0) if d.get("month") == _month() else 0
