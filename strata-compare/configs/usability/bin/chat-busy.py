#!/usr/bin/python3 -I
"""chat-busy.py [--quiet-s N] [--port P] - is the model on 8080 answering someone? (Karl 11-06)

Asked of the server, not of an app, so every client counts: Jan, DS Harness, OpenCode, Codex, a script.
  exit 0  busy: a request is running or queued, or one finished less than N s ago (default 120: a multi-step turn in
          DS Harness shows idle between its model calls, while a tool runs), or the server is up but did not answer in time
  exit 1  quiet
  exit 2  nothing to wait for: nothing listens on the port, or what answers is not a Strata server
Used by the DeepSeek / Qwen switch (deepseek-session.sh) and by a gap's start (work/r22/port_gap4.sh). Prints only states
and times, never a request's content.
"""
import argparse
import http.client
import json
import socket
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet-s", type=float, default=120.0)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--timeout", type=float, default=5.0)
    a = ap.parse_args()
    try:
        c = http.client.HTTPConnection("127.0.0.1", a.port, timeout=a.timeout)     # direct: no proxy variable applies
        c.request("GET", "/metrics")
        r = c.getresponse()
        raw = r.read()
        c.close()
    except (socket.timeout, TimeoutError):
        print("the server did not answer /metrics in time")
        return 0
    except (OSError, http.client.HTTPException):
        print("nothing answers")
        return 2
    try:
        m = json.loads(raw)
        live = m["live"]
    except (ValueError, KeyError, TypeError):
        print("not a Strata server")
        return 2
    if live.get("state") not in (None, "idle"):
        print(f"answering: {live.get('state')}")
        return 0
    if int(live.get("queued") or 0):
        print(f"{live.get('queued')} queued")
        return 0
    now = float(m.get("time") or time.time())
    ended = [float(q.get("time") or 0) + float(q.get("duration_s") or 0) for q in m.get("requests") or []]
    ago = now - max(ended) if ended else None
    if ago is not None and ago < a.quiet_s:
        print(f"a request finished {ago:.0f} s ago")
        return 0
    print("quiet")
    return 1


if __name__ == "__main__":
    sys.exit(main())
