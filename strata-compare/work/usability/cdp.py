#!/usr/bin/env python3
"""cdp.py - a small headless-Chrome driver (CDP over pipes) for the usability round's web UI checks.

Chrome runs headless with software rendering (no GPU: Strata holds the 5080's memory), its own throw-away profile, and
every request that is not for 127.0.0.1 sent to the refusing proxy on 127.0.0.1:18999.

    from cdp import Browser
    b = Browser(); b.goto("http://127.0.0.1:3080/?token=..."); b.shot("x.png"); print(b.js("document.title"))
"""
import base64
import json
import os
import select
import shutil
import signal
import subprocess
import tempfile
import time

CHROME = "/var/lib/flatpak/app/com.google.Chrome/current/active/files/extra/chrome"


class Browser:
    def __init__(self, width=1600, height=1000):
        self.prof = tempfile.mkdtemp(prefix="cdp-profile-")
        r_cmd, w_cmd = os.pipe()
        r_ev, w_ev = os.pipe()
        args = [CHROME, "--headless=new", "--disable-gpu", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
                "--disable-component-update", "--disable-sync", "--disable-extensions", "--disable-default-apps",
                "--mute-audio", "--proxy-server=http://127.0.0.1:18999", "--proxy-bypass-list=127.0.0.1;localhost",
                "--remote-debugging-pipe", f"--user-data-dir={self.prof}", f"--window-size={width},{height}",
                "about:blank"]

        def child():
            a, b = os.dup(r_cmd), os.dup(w_ev)
            os.dup2(os.dup2(a, 200), 3)
            os.dup2(os.dup2(b, 201), 4)
            os.set_inheritable(3, True)
            os.set_inheritable(4, True)

        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, preexec_fn=child, close_fds=False,
                                     start_new_session=True)
        os.close(r_cmd)
        os.close(w_ev)
        self.w, self.r, self.buf, self.n, self.events = w_cmd, r_ev, b"", 0, []
        tid = self.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.sid = self.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        for m in ("Page.enable", "Runtime.enable"):
            self.call(m, session=self.sid)

    def _send(self, method, params=None, session=None):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        os.write(self.w, json.dumps(msg).encode() + b"\0")
        return self.n

    def _read(self, timeout):
        end = time.monotonic() + timeout
        while b"\0" not in self.buf:
            left = end - time.monotonic()
            if left <= 0:
                return None
            rr, _, _ = select.select([self.r], [], [], left)
            if not rr:
                return None
            chunk = os.read(self.r, 1 << 20)
            if not chunk:
                raise RuntimeError("chrome closed the pipe")
            self.buf += chunk
        raw, self.buf = self.buf.split(b"\0", 1)
        return json.loads(raw)

    def call(self, method, params=None, session=None, timeout=60):
        mid = self._send(method, params, session)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            m = self._read(end - time.monotonic())
            if m is None:
                break
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            self.events.append(m)
            del self.events[:-500]
        raise TimeoutError(method)

    # ---------------------------------------------------------------------------------------------- helpers
    def goto(self, url, wait=3.0):
        self.call("Page.navigate", {"url": url}, self.sid)
        time.sleep(wait)

    def js(self, expr, timeout=60):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True},
                      self.sid, timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:500])
        return r.get("result", {}).get("value")

    def shot(self, path):
        data = self.call("Page.captureScreenshot", {"format": "png"}, self.sid)["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path

    def insert_text(self, text):
        self.call("Input.insertText", {"text": text}, self.sid)

    def key(self, key, code=None, vk=None, modifiers=0):
        for t in ("keyDown", "keyUp"):
            p = {"type": t, "key": key, "code": code or key, "modifiers": modifiers}
            if vk:
                p["windowsVirtualKeyCode"] = vk
            self.call("Input.dispatchKeyEvent", p, self.sid)

    def click_xy(self, x, y):
        for t in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1},
                      self.sid)

    def close(self):
        try:
            self._send("Browser.close")
            self.proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for fd in (self.w, self.r):
            try:
                os.close(fd)
            except OSError:
                pass
        shutil.rmtree(self.prof, ignore_errors=True)
