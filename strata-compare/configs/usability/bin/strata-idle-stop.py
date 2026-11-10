#!/usr/bin/env python3
"""strata-idle-stop.py - stop Strata on 127.0.0.1:8080 after a while with no requests (2026-10-17).

Run by the systemd user service strata-idle-stop.service (configs/usability/systemd/). Once a minute it reads Strata's
GET /metrics: a request being answered or queued counts as activity, and so does every finished request (its start +
duration). When the last activity is `minutes` old it stops the server the usual way (`STRATA_PORT=8080
./run-strata.sh stop`) and shows a desktop notification; the next app launcher starts it again.

The setting: configs/usability/strata-idle-stop.conf, one line `minutes = 45`; 0 turns the stop off. It is read every
minute, so a change applies without restarting the service. Never stops while a measurement holds tmp/gpu-test.lock or
the test queue holds tmp/suite/heavy.lock. Log: logs/run/strata-idle-stop.log.
"""
import fcntl
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
CONF = WS / "configs/usability/strata-idle-stop.conf"
LOG = WS / "logs/run/strata-idle-stop.log"
URL = "http://127.0.0.1:8080"
LOCKS = [(WS / "tmp/gpu-test.lock", fcntl.LOCK_EX), (WS / "tmp/suite/heavy.lock", fcntl.LOCK_SH)]
CHECK_S = 60


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def minutes():
    try:
        m = re.search(r"^\s*minutes\s*=\s*([0-9.]+)", CONF.read_text(), re.M)
        return float(m.group(1)) if m else 45.0
    except OSError:
        return 45.0


def held():
    """A measurement or the test queue holds its lock (tried without waiting, released at once)."""
    for path, mode in LOCKS:
        if not path.exists():
            continue
        with open(path, "a") as f:
            try:
                fcntl.flock(f, mode | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
            except BlockingIOError:
                return path.name
    return None


def metrics():
    with urllib.request.urlopen(URL + "/metrics", timeout=10) as r:
        return json.load(r)


def server_pid():
    out = subprocess.run(["ss", "-H", "-ltnp", "( sport = :8080 )"], capture_output=True, text=True).stdout
    m = re.search(r"pid=(\d+)", out)
    return int(m.group(1)) if m else None


def main():
    log(f"started (setting: {minutes():g} min; {CONF})")
    seen_pid, since = None, time.time()      # since: the last activity of the server we watch
    while True:
        time.sleep(CHECK_S)
        limit = minutes()
        pid = server_pid()
        if pid is None:
            seen_pid = None
            continue
        if pid != seen_pid:                  # a new server: its start counts as activity
            seen_pid, since = pid, time.time()
            log(f"watching the server on 8080 (pid {pid}); stop after {limit:g} min without requests")
        try:
            m = metrics()
        except Exception as e:  # noqa: BLE001 - loading, or busy answering: try again next minute
            since = max(since, time.time() - CHECK_S)
            continue
        live = m.get("live") or {}
        if live.get("state") not in (None, "idle") or live.get("queued"):
            since = time.time()
            continue
        for r in m.get("requests") or []:
            since = max(since, float(r.get("time") or 0) + float(r.get("duration_s") or 0))
        idle_min = (time.time() - since) / 60
        if limit <= 0 or idle_min < limit:
            continue
        lock = held()
        if lock:
            log(f"idle {idle_min:.0f} min, but {lock} is held (a test): not stopped")
            continue
        log(f"no requests for {idle_min:.0f} min (setting {limit:g}): stopping Strata (pid {pid})")
        r = subprocess.run(["./run-strata.sh", "stop"], cwd=WS, env={**os.environ, "STRATA_PORT": "8080"},
                           capture_output=True, text=True)
        log("run-strata: " + " / ".join(x for x in (r.stdout + r.stderr).splitlines() if x.strip())[-300:])
        subprocess.run(["notify-send", "-a", "Strata", "-i", "jan-strata", "Strata stopped",
                        f"No requests for {limit:g} minutes: the model is unloaded and the GPUs are free. "
                        "Opening Jan, OpenCode, Codex or dsh starts it again."], capture_output=True)
        seen_pid = None


if __name__ == "__main__":
    main()
