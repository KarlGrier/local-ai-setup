#!/usr/bin/python3 -I
"""ds-harness-task.py running|cancel [--home DIR] [--port N] - DS Harness's own view of its running tasks (Karl 11-07).

  running   prints "running N" (exit 0), or "unreadable: why" (exit 2)
  cancel    DS Harness's own cancel for each running task (what the page's stop button calls): prints "cancel accepted N"
            (exit 0), "cancel refused: what" (exit 1), or "unreadable: why" (exit 2). The session and its workspace stay.

Asks the service on 127.0.0.1 (POST /api/session/list, /api/session/cancel). It signs in the way the browser does: the
page's token is read from the mode 600 service log and the signed cookie stays in this process's memory. A sign-in doesn't
affect the browser's own cookie. Prints counts only: never the token, the cookie, a session id, a title or any content.
The session list carries titles; only its "running", "sessionId" and "parentSessionId" fields are looked at.
"""
import argparse
import http.client
import json
import os
import re
import sys
import urllib.parse
import uuid


class Unreadable(Exception):
    pass


def request(port, method, path, body=None, cookie=None, timeout=20):
    headers = {"Host": f"127.0.0.1:{port}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)     # direct: no proxy variable applies
    try:
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse()
        return r.status, r.getheaders(), r.read()
    except (OSError, http.client.HTTPException) as e:
        raise Unreadable(f"the service did not answer ({type(e).__name__})") from None
    finally:
        c.close()


def sign_in(home, port):
    try:
        with open(os.path.join(home, "service.log"), errors="replace") as f:
            urls = re.findall(r"^dsh web: (http\S+)", f.read(), re.M)
    except OSError as e:
        raise Unreadable(f"no service log ({type(e).__name__})") from None
    if not urls:
        raise Unreadable("the service log has no page address")
    tokens = urllib.parse.parse_qs(urllib.parse.urlsplit(urls[-1]).query).get("token")
    if not tokens:
        raise Unreadable("the page address has no token")
    status, headers, _ = request(port, "GET", "/?" + urllib.parse.urlencode({"token": tokens[0]}))
    cookies = [v.split(";", 1)[0] for k, v in headers if k.lower() == "set-cookie"]
    if status != 303 or not cookies:
        raise Unreadable(f"sign-in was refused (HTTP {status})")
    return "; ".join(cookies)


def rpc(port, cookie, method, payload):
    rid = str(uuid.uuid4())
    body = json.dumps({"type": "client-request", "rpcId": rid, "method": method, "payload": payload})
    status, _, raw = request(port, "POST", "/api/" + method, body=body, cookie=cookie)
    if status != 200:
        raise Unreadable(f"{method} answered HTTP {status}")
    try:
        m = json.loads(raw)
    except ValueError:
        raise Unreadable(f"{method} did not answer JSON") from None
    res = m.get("result")
    if m.get("rpcId") != rid or not isinstance(res, dict):
        raise Unreadable(f"{method} answered an unexpected envelope")
    if res.get("ok") is not True:
        code = (res.get("error") or {}).get("code")             # the code only: a message can carry a session id
        raise Unreadable(f"{method} answered an error ({code})")
    return res.get("value")


def running_items(port, cookie):
    r = rpc(port, cookie, "session/list", {"args": {"_request": {}}})
    items = r.get("items") if isinstance(r, dict) else None
    if not isinstance(items, list):
        raise Unreadable("session/list has no items")
    run = [i for i in items if i.get("running") is True]
    known = {i.get("sessionId"): i for i in items}
    roots = set()
    for i in run:                       # a running subagent is cancelled through the top-level task that owns it
        while i.get("parentSessionId") in known:
            i = known[i["parentSessionId"]]
        roots.add(i.get("sessionId"))
    return len(run), roots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["running", "cancel"])
    ap.add_argument("--home", default=os.path.expanduser("~/.dsh-deepseek"))
    ap.add_argument("--port", type=int, default=3081)
    a = ap.parse_args()
    try:
        cookie = sign_in(a.home, a.port)
        n, roots = running_items(a.port, cookie)
        if a.what == "running":
            print(f"running {n}")
            return 0
        done = 0
        for sid in roots:
            r = rpc(a.port, cookie, "session/cancel", {"args": {"request": {"sessionId": sid}}})
            if not (isinstance(r, dict) and r.get("accepted") is True):
                print(f"cancel refused: {done} of {len(roots)} accepted")
                return 1
            done += 1
        print(f"cancel accepted {done}")
        return 0
    except Unreadable as e:
        print(f"unreadable: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
