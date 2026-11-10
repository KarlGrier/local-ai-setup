"""The research clock and per-job settings for deep runs started by the research runner (workspace patch, 2026-10-17).

* Research clock: strata-proxy's gate holds model calls while a research is paused (by the user, the night pause, a
  test holding the GPUs, or yielding to another Strata client) and records the total time it was closed in
  ``LDR_DEEP_CLOCK_FILE`` (run/research-clock.json). ``clock()`` / ``mono()`` are time.time() / time.monotonic()
  minus that pause total, so every deadline of a deep run (research budget, subagent shares, the subagent pool's
  backstop) stops while the research is held.
* Job settings: the runner writes ``LDR_DEEP_NEXT_FILE`` (run/next-research.json) just before it starts a research:
  the research time for this job, the user's files, and the evidence folders of earlier runs to continue from.
  ``take_job(query)`` consumes it when that research starts (matched by the question text).
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from loguru import logger

_WS = Path("/home/USER/ai/deep-research")
CLOCK_FILE = Path(os.environ.get("LDR_DEEP_CLOCK_FILE") or _WS / "run" / "research-clock.json")
NEXT_FILE = Path(os.environ.get("LDR_DEEP_NEXT_FILE") or _WS / "run" / "next-research.json")

_cache = {"t": 0.0, "total": 0.0, "closed": False, "updated": 0.0}
_lock = threading.Lock()


def paused_total() -> float:
    """Seconds the proxy gate has been closed (all-time total, extrapolated to now while it is closed)."""
    now = time.time()
    with _lock:
        if now - _cache["t"] > 1.0:
            try:
                d = json.loads(CLOCK_FILE.read_text())
                _cache.update(total=float(d.get("paused_total_s") or 0.0), closed=d.get("gate") == "closed",
                              updated=float(d.get("updated") or now))
            except (OSError, ValueError, TypeError):
                pass
            _cache["t"] = now
        total = _cache["total"]
        if _cache["closed"]:
            # the file is rewritten every second while the proxy runs; a stale closed gate still counts as paused
            total += max(0.0, now - _cache["updated"])
        return total


def clock() -> float:
    """Wall-clock time minus pauses: use instead of time.time() for research deadlines."""
    return time.time() - paused_total()


def mono() -> float:
    """time.monotonic() minus pauses: for monotonic deadlines (the subagent pool's backstop)."""
    return time.monotonic() - paused_total()


def take_job(query: str) -> dict | None:
    """The runner's settings for this research (consumed), or None for a research started some other way."""
    try:
        d = json.loads(NEXT_FILE.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or (d.get("question") or "").strip() != (query or "").strip():
        return None
    if time.time() - float(d.get("written") or 0) > 3600:
        logger.warning("deep: ignoring a stale next-research.json")
        return None
    try:
        NEXT_FILE.rename(NEXT_FILE.with_name(f"next-research.used-{int(time.time())}.json"))
    except OSError:
        pass
    logger.info(f"deep: job {d.get('job_id')}: budget {d.get('budget_s')} s, {len(d.get('files') or [])} files, "
                f"{len(d.get('seed_dirs') or [])} seed runs")
    return d
