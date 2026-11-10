#!/usr/bin/env python3
"""searxng_watch.py - user service searxng-watch.service (the user, 10-21): SearXNG 8889 (LDR), 8890 (LDR baseline) and
8888 (the chat page) asked /healthz every 60 s; one that fails twice in a row gets a critical desktop notification
(notify-send) and a line in logs/searxng-watch.log, and another when it answers again. It only watches: systemd
restarts the units (Restart=always), the runners check them before each step (tools/services_check.py)."""
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, "/home/USER/ai/deep-research/tools")
import research_common as rc  # noqa: E402

LOG = rc.WS / "logs" / "searxng-watch.log"
PORTS = (8889, 8890, 8888)
NAME = {8889: "LDR's SearXNG (8889)", 8890: "LDR's baseline SearXNG (8890)", 8888: "the chat page's SearXNG (8888)"}


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def notify(title: str, body: str, urgency: str) -> None:
    try:
        subprocess.run(["notify-send", "-a", "SearXNG watch", "-i", "network-error" if urgency == "critical" else "network-idle",
                        "-u", urgency, title, body], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


fails = {p: 0 for p in PORTS}
down = {p: False for p in PORTS}
log(f"watch start: {', '.join(map(str, PORTS))} every 60 s")
while True:
    for p in PORTS:
        if rc.searxng_answers(p, timeout=10):
            if down[p]:
                log(f"{p} answering again")
                notify(f"{NAME[p]} is answering again", "Searches work again.", "normal")
            fails[p], down[p] = 0, False
        else:
            fails[p] += 1
            if fails[p] == 2 and not down[p]:
                down[p] = True
                st = subprocess.run(["systemctl", "--user", "is-active", rc.SEARXNG_UNITS[p]], capture_output=True,
                                    text=True, timeout=30).stdout.strip()
                log(f"{p} NOT ANSWERING (2 checks in a row; {rc.SEARXNG_UNITS[p]} {st})")
                notify(f"{NAME[p]} stopped answering",
                       f"{rc.SEARXNG_UNITS[p]} is {st}. Research and web searches that use it will fail until it is back.",
                       "critical")
    time.sleep(60)
