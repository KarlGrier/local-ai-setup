#!/usr/bin/env python3
"""anthropic_unpause.py - 2026-10-12: the Anthropic key file gave 401 (invalid x-api-key), so the three Claude runs were
paused in tmp/suite/api_jobs/state.json (collect "no key"). This waits for the key file to change (mtime / size only),
then checks the new key with ONE free Models API call through the suite's own client (msuite.backend_anthropic: the key
is read only to hand it to the client; nothing about it is printed or logged, only the HTTP status). On success it
removes the three paused entries, so api_jobs.py restarts the Claude chain at its next pass, Opus 4.5 first. On another
401 it stays paused and waits for the next change. Log: logs/suite/api_jobs.log. Stops with tmp/suite/api_jobs/STOP."""
import json
import os
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "suite"))
from msuite import backend_anthropic as BA  # noqa: E402

KEY = BA.KEY_FILE
STATE = WS / "tmp/suite/api_jobs/state.json"
LOG = WS / "logs/suite/api_jobs.log"
LABELS = ("opus-4-5-quick", "sonnet-4-6-quick", "opus-4-6-quick")
DEADLINE = time.time() + 66 * 3600          # the api_jobs watcher's own 72 h end, 2026-10-15 ~13:00


def log(msg):
    with LOG.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} unpause: {msg}\n")


def sig():
    try:
        s = KEY.stat()
        return (s.st_mtime_ns, s.st_size)
    except FileNotFoundError:
        return None


def key_ok() -> str:
    import anthropic
    try:
        anthropic.Anthropic(api_key=BA._load_key(), max_retries=2, timeout=60).models.retrieve("claude-opus-4-5-20251101")
        return "ok"
    except anthropic.APIStatusError as e:
        return f"HTTP {e.status_code}"
    except Exception as e:                    # NoKey, network: the type only
        return type(e).__name__


last = sig()
log("waiting for the Anthropic key file to change (the Claude runs are paused after a 401)")
while time.time() < DEADLINE and not (WS / "tmp/suite/api_jobs/STOP").exists():
    time.sleep(30)
    now = sig()
    if now is None or now == last:
        continue
    time.sleep(5)                             # let the write finish
    last = sig()
    r = key_ok()
    if r != "ok":
        log(f"key file changed; Models API check: {r} - still paused")
        continue
    st = json.loads(STATE.read_text())
    for label in LABELS:
        if st.get(label, {}).get("collect") == "no key":
            st.pop(label)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    os.replace(tmp, STATE)
    log("key file changed; Models API check ok - the Claude runs are unpaused (Opus 4.5 first)")
    break
