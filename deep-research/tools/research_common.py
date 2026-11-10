"""research_common.py - shared by the research runner (tools/research-runner.py) and the Jan MCP server
(tools/research-mcp.py): paths, the settings file, job files and their lock. Standard library only.

A job is one research question: jobs/<id>/job.json. The MCP server creates jobs and sets the user's wishes
(user_paused, cancel_requested); the runner owns everything else (state, runs, report). Every read-modify-write
of a job file happens under jobs/.lock.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
JOBS = WS / "jobs"
REPORTS = WS / "reports"
RUN = WS / "run"
SETTINGS_FILE = WS / "research.conf"
CONTROL_FILE = RUN / "research-control.json"     # runner -> proxy gate
CLOCK_FILE = RUN / "research-clock.json"         # proxy gate -> runner, LDR (the research clock's pause total)
NEXT_FILE = RUN / "next-research.json"           # runner -> the deep patch: the next research's job settings
CALL_LOG = WS / "logs" / "llm-calls.jsonl"
BENCH_LOCK = RUN / "bench.lock"                  # held by tools/bench2.py while a measurement uses LDR
SC = Path("/home/USER/ai-speed-testing/strata-compare")
TEST_LOCKS = ((SC / "tmp" / "gpu-test.lock", fcntl.LOCK_EX), (SC / "tmp" / "suite" / "heavy.lock", fcntl.LOCK_SH))

ACTIVE = ("starting", "running", "paused")
FINAL = ("finished", "failed", "cancelled")

DEFAULTS = {
    "yield_minutes": 5.0,               # hold research while another client used Strata in the last N minutes; 0 = never
    "night_pause": "23:00-09:00",       # research pauses between model calls in this window; "off" = never
    "default_budget_minutes": 180.0,    # research time per question when none is given
    "max_budget_minutes": 600.0,
    "ldr_idle_stop_minutes": 15.0,      # stop LDR + its SearXNG when no job has run for this long
    "verify_max_claims": 120.0,         # claims the citation check verifies per report (0 = all); applies when LDR starts
    "quick_wait_seconds": 25.0,         # research_quick waits this long for the answer (keep under Jan's tool timeout)
}


def settings() -> dict:
    """research.conf: 'key = value' lines, '#' comments. Read on every use (no restart needed)."""
    out = dict(DEFAULTS)
    try:
        for line in SETTINGS_FILE.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" not in line:
                continue
            k, v = (x.strip() for x in line.split("=", 1))
            if k not in DEFAULTS:
                continue
            if isinstance(DEFAULTS[k], float):
                try:
                    out[k] = float(v)
                except ValueError:
                    pass
            else:
                out[k] = v
    except OSError:
        pass
    return out


def night_window(s: dict | None = None) -> tuple[int, int] | None:
    """(start_min, end_min) of the night pause in minutes after midnight, or None when off."""
    s = s or settings()
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", str(s.get("night_pause") or ""))
    if not m:
        return None
    a, b, c, d = (int(x) for x in m.groups())
    return a * 60 + b, c * 60 + d


def is_night(now: float | None = None, s: dict | None = None) -> bool:
    w = night_window(s)
    if not w:
        return False
    t = datetime.fromtimestamp(now or time.time())
    m = t.hour * 60 + t.minute
    a, b = w
    return (a <= m or m < b) if a > b else (a <= m < b)


def night_end_text(s: dict | None = None) -> str:
    w = night_window(s)
    return f"{w[1] // 60:02d}:{w[1] % 60:02d}" if w else "-"


@contextmanager
def jobs_lock():
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / ".lock", "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_job(job_id: str) -> dict | None:
    try:
        return json.loads((JOBS / job_id / "job.json").read_text())
    except (OSError, ValueError):
        return None


def save_job(job: dict) -> None:
    d = JOBS / job["id"]
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "job.json.tmp"
    tmp.write_text(json.dumps(job, indent=1, ensure_ascii=False))
    os.replace(tmp, d / "job.json")


def all_jobs() -> list[dict]:
    out = []
    if JOBS.exists():
        for d in JOBS.iterdir():
            if d.is_dir():
                j = load_job(d.name)
                if j:
                    out.append(j)
    return sorted(out, key=lambda j: j.get("created", 0))


def find_job(ref: str | None) -> dict | None:
    """A job by id (or a unique id prefix); None/'' = the active job, else the newest one."""
    jobs = all_jobs()
    if not jobs:
        return None
    if ref:
        ref = ref.strip()
        hits = [j for j in jobs if j["id"] == ref] or [j for j in jobs if j["id"].startswith(ref)]
        return hits[0] if len(hits) == 1 else None
    act = [j for j in jobs if j.get("state") in ACTIVE]
    return act[0] if act else jobs[-1]


def new_job_id(question: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:40].strip("-") or "research"
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}"


def test_lock_held() -> str | None:
    """A measurement or the test queue holds strata-compare's lock (tried without waiting, released at once)."""
    for path, how in TEST_LOCKS:
        if not path.exists():
            continue
        try:
            with open(path, "a") as f:
                try:
                    fcntl.flock(f, how | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
                except BlockingIOError:
                    return path.name
        except OSError:
            pass
    return None


def bench_running() -> bool:
    """A measurement (tools/bench2.py) holds run/bench.lock: it owns LDR; jobs wait, LDR is not stopped."""
    if not BENCH_LOCK.exists():
        return False
    try:
        with open(BENCH_LOCK, "a") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
                return False
            except BlockingIOError:
                return True
    except OSError:
        return False


def read_clock() -> dict:
    try:
        return json.loads(CLOCK_FILE.read_text())
    except (OSError, ValueError):
        return {}


def paused_total(now: float | None = None) -> float:
    """The research clock's pause total (seconds the proxy gate was closed), extrapolated to now."""
    c = read_clock()
    total = float(c.get("paused_total_s") or 0.0)
    if c.get("gate") == "closed" and c.get("updated"):
        total += max(0.0, (now or time.time()) - float(c["updated"]))
    return total


def fmt_minutes(s: float | None) -> str:
    if s is None:
        return "-"
    m = int(round(s / 60))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


# ------------------------------------------------------------------------------------------------ search services
# 2026-10-21 (the user): SearXNG 8889 (LDR main), 8890 (LDR baseline) and 8888 (the chat page) are systemd user services
# of their own, and every runner checks them before each step: stage 1's "not yet" check ran with every search failing
# after 8889 had been stopped at 08:29 (the research runner's idle stop) and nothing looked.
SEARXNG_UNITS = {8889: "searxng-ldr.service", 8890: "searxng-ldr-baseline.service", 8888: "searxng-chat.service"}


def searxng_answers(port: int, timeout: float = 5) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=timeout) as r:
            return r.status == 200
    except OSError:
        return False


def searxng_problems(ports=(8889, 8890, 8888), start: bool = True, wait_s: float = 30) -> dict[int, str]:
    """{port: why} for the instances that do not answer /healthz; with start=True a stopped unit is started once and
    given wait_s to answer first."""
    import subprocess
    bad = [p for p in ports if not searxng_answers(p)]
    if bad and start:
        for p in bad:
            subprocess.run(["systemctl", "--user", "start", SEARXNG_UNITS[p]], capture_output=True, timeout=60)
        t0 = time.time()
        while time.time() - t0 < wait_s and any(not searxng_answers(p) for p in bad):
            time.sleep(1)
    out = {}
    for p in bad:
        if not searxng_answers(p):
            st = subprocess.run(["systemctl", "--user", "is-active", SEARXNG_UNITS[p]], capture_output=True,
                                text=True, timeout=30).stdout.strip()
            out[p] = f"SearXNG {p} not answering ({SEARXNG_UNITS[p]} {st or '?'}{', start tried' if start else ''})"
    return out


# ------------------------------------------------------------------------------------------------ search failures
# 2026-10-21 (the user): "a research run (mine or a measurement) whose searches mostly fail must stop and be marked
# FAILED with the reason, not write a report from the model's own knowledge". LDR's SearXNG engine writes one line per
# search (patch 0005 part 2): t, pid, n (results after any fallback), sx_n (SearXNG's own), err. A search with no
# results counts as failed.
SEARCH_EVENTS = WS / "logs" / "search-events.jsonl"
SEARCH_MIN = 6            # during a run: judge after this many searches ...
SEARCH_TAIL = 6           # ... or when this many in a row (the latest) all failed


def search_events(since: float, pid: int | None = None) -> list[dict]:
    out = []
    try:
        with open(SEARCH_EVENTS, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("t", 0) >= since and (pid is None or e.get("pid") == pid):
                    out.append(e)
    except OSError:
        pass
    return out


def search_health(since: float, pid: int | None = None, final: bool = False) -> dict:
    """bad=True when the run's searches mostly failed: more than half of >= 6 searches, or the latest 6 in a row; at the
    end of a run (final) more than half of >= 3. No search at all is reported (reason) but not judged bad."""
    ev = search_events(since, pid)
    tried = len(ev)
    failed = sum(1 for e in ev if not e.get("n"))
    errs = [e.get("err") for e in ev if not e.get("n") and e.get("err")]
    tail = ev[-SEARCH_TAIL:]
    bad = (tried >= SEARCH_MIN and failed * 2 > tried) or \
          (len(tail) == SEARCH_TAIL and all(not e.get("n") for e in tail))
    if final and not bad:
        bad = tried >= 3 and failed * 2 > tried
    common = max(set(errs), key=errs.count) if errs else ("no results" if failed else None)
    if tried == 0:
        reason = "no web search was recorded for this run"
    else:
        reason = (f"{failed} of {tried} web searches failed" + (f" (mostly: {common})" if common else "")
                  + (f", the last {SEARCH_TAIL} in a row" if len(tail) == SEARCH_TAIL and all(not e.get('n') for e in tail) else ""))
    return {"tried": tried, "failed": failed, "error": common, "bad": bad, "reason": reason}
