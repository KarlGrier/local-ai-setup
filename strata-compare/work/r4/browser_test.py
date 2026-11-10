#!/usr/bin/env python3
"""browser_test.py — round 4, item 3: Strata's chat page in a real (headless) Chrome.

Chrome = the installed Google Chrome binary run directly (NOT through flatpak, so it never sees ~/.var/app or your
profile), with HOME, XDG dirs, TMPDIR and a fresh --user-data-dir all inside the workspace (tmp/r4/chrome-*),
--headless=new --disable-gpu, background networking off, DevTools on 127.0.0.1 only.  Driven over the DevTools
protocol (websocket-client).  The page talks to a running Strata server (--base, default 127.0.0.1:8081).

Tests: sampling drawer defaults · chat list / switching / New chat keeps the old chat · delete + Undo · attach a
file, reload, ask again · Stop.  Console errors and page exceptions are collected throughout.  Screenshots go to
logs/r4/browser/.  Prints PASS/FAIL per check and a JSON summary (results/browser-test.json).
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
import websocket

WS = Path("/home/USER/ai-speed-testing/strata-compare")
CHROME = "/var/lib/flatpak/app/com.google.Chrome/current/active/files/extra/chrome"
SHOTS = WS / "logs/r4/browser"
results = []


def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  — ' + str(detail) if detail else ''}", flush=True)
    return ok


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=300, suppress_origin=True)
        self.n = 0
        self.console = []

    def call(self, method, **params):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self._event(msg)

    def _event(self, msg):
        m = msg.get("method", "")
        p = msg.get("params", {})
        if m == "Runtime.exceptionThrown":
            self.console.append(("exception", json.dumps(p.get("exceptionDetails", {}))[:400]))
        elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "assert"):
            self.console.append(("console." + p["type"], " ".join(str(a.get("value", a.get("description", "")))
                                                                  for a in p.get("args", []))[:400]))
        elif m == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
            e = p["entry"]
            self.console.append(("log.error", f"{e.get('source')}: {e.get('text')} {e.get('url', '')}"[:400]))

    def pump(self, secs):
        """read events for secs (keeps the console log current while waiting)"""
        end = time.time() + secs
        self.ws.settimeout(0.2)
        try:
            while time.time() < end:
                try:
                    self._event(json.loads(self.ws.recv()))
                except websocket.WebSocketTimeoutException:
                    pass
        finally:
            self.ws.settimeout(300)

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(f"js error: {r['exceptionDetails'].get('text')} {json.dumps(r['exceptionDetails'])[:300]}")
        return r.get("result", {}).get("value")

    def wait(self, expr, timeout=120, step=0.25):
        end = time.time() + timeout
        while time.time() < end:
            v = self.js(expr)
            if v:
                return v
            self.pump(step)
        return None

    def shot(self, name):
        SHOTS.mkdir(parents=True, exist_ok=True)
        data = self.call("Page.captureScreenshot", format="png")["data"]
        (SHOTS / f"{name}.png").write_bytes(base64.b64decode(data))

    def navigate(self, url):
        self.call("Page.navigate", url=url)
        self.wait("document.readyState === 'complete' && typeof health === 'object' && health.max_context > 0", 60)
        self.pump(0.5)


def launch(tag):
    base = WS / f"tmp/r4/chrome-{tag}"
    if base.exists():
        shutil.rmtree(base)
    home, prof = base / "home", base / "profile"
    for d in (home, prof, base / "tmp", base / "xdg-cache", base / "xdg-config", base / "xdg-data"):
        d.mkdir(parents=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(base / "tmp"), "XDG_CACHE_HOME": str(base / "xdg-cache"),
           "XDG_CONFIG_HOME": str(base / "xdg-config"), "XDG_DATA_HOME": str(base / "xdg-data"), "LANG": "en_US.UTF-8"}
    args = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-breakpad",
            "--disable-crash-reporter", "--disable-component-update", "--disable-background-networking", "--disable-sync",
            "--disable-extensions", "--metrics-recording-only", "--no-pings", "--password-store=basic",
            "--disable-features=MediaRouter,OptimizationHints,Translate", "--window-size=1400,1000",
            f"--user-data-dir={prof}", "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
            "--no-sandbox", "about:blank"]
    log = open(base / "chrome.log", "w")
    p = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    port_file = prof / "DevToolsActivePort"
    for _ in range(200):
        if port_file.exists() and port_file.read_text().strip():
            break
        time.sleep(0.1)
    port = int(port_file.read_text().split()[0])
    tabs = requests.get(f"http://127.0.0.1:{port}/json", timeout=10).json()
    page = next(t for t in tabs if t["type"] == "page")
    return p, CDP(page["webSocketDebuggerUrl"]), base, port


def send(c, text, timeout=600):
    """type text into the composer and send it; wait until the answer is finished (busy cleared)"""
    c.js(f"(() => {{ const i = $('input'); i.value = {json.dumps(text)}; i.dispatchEvent(new Event('input')); "
         f"$('send-btn').click(); return true; }})()")
    c.wait("busy !== null", 10)
    ok = c.wait("busy === null", timeout, step=0.5)
    return c.js("(() => { const m = messages[messages.length - 1]; return {text: m.text, reasoning_len: (m.reasoning||'').length, "
                "error: m.error || null, stopped: !!m.stopped, meta: m.meta || ''}; })()") if ok else None


def engine_tail(elog, n):
    return [l for l in Path(elog).read_text(errors="replace").splitlines() if "strata serve: prompt" in l][-n:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--engine-log", required=True)
    ap.add_argument("--tag", default="t1")
    a = ap.parse_args()
    url = a.base + "/"
    proc, c, base, port = launch(a.tag)
    try:
        for dom in ("Runtime", "Page", "Log"):
            c.call(f"{dom}.enable")
        c.navigate(url)
        c.shot("00-start")
        check("page loads, health read", c.js("health.max_context") == 131072, c.js("health.model"))

        # ---- 5. sampling drawer (fresh profile: the page's built-in defaults)
        c.js("$('sampling-btn').click(); true")
        c.wait("$('drawer').dataset.open === 'true'", 5)
        c.pump(1.0)                     # loadShared() fetch
        d = c.js("""(() => { const sel = [...$('s-thinking').children].find(b => b.getAttribute('aria-checked') === 'true');
            return {thinking: sel ? sel.dataset.v : null, thinking_label: sel ? sel.textContent.trim() : null,
                    temp: $('s-temp').value, o_temp: $('o-temp').textContent, topp: $('s-topp').value, o_topp: $('o-topp').textContent,
                    topk: $('s-topk').value, max: $('s-max').value, max_placeholder: $('s-max').placeholder,
                    seed: $('s-seed').value, share: $('s-share').getAttribute('aria-checked')}; })()""")
        c.shot("01-sampling-drawer")
        check("drawer: Thinking High", d["thinking"] == "high", d["thinking_label"])
        check("drawer: temperature 0.60", d["o_temp"] == "0.60" and float(d["temp"]) == 0.6, d["o_temp"])
        check("drawer: top-p 0.95", d["o_topp"] == "0.95", d["o_topp"])
        check("drawer: top-k 20", d["topk"] == "20", d["topk"])
        check("drawer: max tokens empty", d["max"] == "", f"placeholder '{d['max_placeholder']}'")
        check("drawer: 'use for other apps too' reflects the server's shared settings", d["share"] == "true", d["share"])
        c.js("$('s-apply').click(); true")
        c.pump(1.0)
        c.navigate(url)                 # reload: the applied settings come back from browser storage
        c.js("$('sampling-btn').click(); true"); c.pump(1.0)
        d2 = c.js("""(() => { const sel = [...$('s-thinking').children].find(b => b.getAttribute('aria-checked') === 'true');
            return [sel && sel.dataset.v, $('o-temp').textContent, $('o-topp').textContent, $('s-topk').value, $('s-max').value]; })()""")
        check("drawer after Apply + reload: same values", d2 == ["high", "0.60", "0.95", "20", ""], d2)
        body = c.js("(() => { const b = {reasoning_effort: settings.thinking}; if (settings.temperature > 0) Object.assign(b, "
                    "{temperature: +settings.temperature, top_p: +settings.top_p, top_k: +settings.top_k}); "
                    "if (settings.max) b.max_tokens = +settings.max; return b; })()")
        check("request body the page will send", body == {"reasoning_effort": "high", "temperature": 0.6, "top_p": 0.95, "top_k": 20}, body)
        c.js("$('drawer-close').click(); true")

        # ---- 1. chat list, switching, New chat keeps the old chat
        rA = send(c, "Chat A. What is 17 * 23? Answer in one short sentence.")
        check("chat A answered", rA and "391" in rA["text"], (rA or {}).get("text", "")[:80])
        idA = c.js("chatId")
        c.js("$('new-btn').click(); true"); c.pump(0.5)
        check("New chat: empty composer view", c.js("messages.length === 0 && chatId === null"))
        check("New chat: old chat still in the list", c.js(f"chats.some(x => x.id === {json.dumps(idA)})"))
        rB = send(c, "Chat B. Name the three largest planets of the solar system, one line.")
        check("chat B answered", rB and "Jupiter" in rB["text"], (rB or {}).get("text", "")[:80])
        idB = c.js("chatId")
        c.js("$('chats-btn').click(); true"); c.pump(0.5)
        rows = c.js("[...document.querySelectorAll('#chat-list .chat-row')].map(r => [r.querySelector('.chat-row__title').textContent, r.getAttribute('aria-current')])")
        c.shot("02-chat-list")
        check("chat list shows both chats, B current", len(rows) == 2 and rows[0][1] == "true" and rows[0][0].startswith("Chat B"), rows)
        c.js("document.querySelectorAll('#chat-list .chat-row')[1].click(); true"); c.pump(0.5)
        check("switch to A: A's messages shown", c.js(f"chatId === {json.dumps(idA)} && messages.length === 2 && messages[0].text.startsWith('Chat A')")
              and c.js("document.querySelectorAll('#chat .st-msg').length") == 2)
        check("switch closes the drawer", c.js("$('chats-drawer').dataset.open") == "false")
        rA2 = send(c, "Now divide that result by 17. One short sentence.")
        check("follow-up in A uses A's history", rA2 and "23" in rA2["text"], (rA2 or {}).get("text", "")[:80])
        tail = engine_tail(a.engine_log, 1)
        check("server: A's follow-up reused A's earlier prompt (chat cache)", tail and " 0 reused" not in tail[-1], tail[-1] if tail else "")
        c.navigate(url)
        check("reload: current chat A, 2 chats, A's 4 messages", c.js(f"chatId === {json.dumps(idA)} && chats.length === 2 && messages.length === 4"))

        # ---- 2. delete + Undo
        c.js("$('chats-btn').click(); true"); c.pump(0.3)
        rows = c.js("[...document.querySelectorAll('#chat-list .chat-row')].map(r => r.querySelector('.chat-row__title').textContent)")
        iB = next(i for i, t in enumerate(rows) if t.startswith("Chat B"))
        c.js(f"document.querySelectorAll('#chat-list .chat-row')[{iB}].querySelector('button').click(); true"); c.pump(0.3)
        c.shot("03-deleted-toast")
        check("delete B: list has 1 chat, B's storage removed", c.js("chats.length") == 1 and
              c.js(f"localStorage.getItem('strata.chat.' + {json.dumps(idB)}) === null"))
        has_undo = c.js("[...document.querySelectorAll('#toasts button')].some(b => b.textContent === 'Undo')")
        check("toast offers Undo", has_undo)
        c.js("[...document.querySelectorAll('#toasts button')].find(b => b.textContent === 'Undo').click(); true"); c.pump(0.3)
        check("Undo: B back in the list and in storage", c.js("chats.length") == 2 and
              c.js(f"JSON.parse(localStorage.getItem('strata.chat.' + {json.dumps(idB)})).length === 2") and
              c.js("document.querySelectorAll('#chat-list .chat-row').length") == 2)
        c.navigate(url)
        check("Undo survives a reload", c.js("chats.length") == 2 and c.js(f"chats.some(x => x.id === {json.dumps(idB)})"))
        # delete the CURRENT chat (A) → the page switches to the other one
        c.js("$('chats-btn').click(); true"); c.pump(0.3)
        rows = c.js("[...document.querySelectorAll('#chat-list .chat-row')].map(r => [r.querySelector('.chat-row__title').textContent, r.getAttribute('aria-current')])")
        iA = next(i for i, r in enumerate(rows) if r[1] == "true")
        c.js(f"document.querySelectorAll('#chat-list .chat-row')[{iA}].querySelector('button').click(); true"); c.pump(0.3)
        check("delete the current chat: switches to the remaining one", c.js(f"chatId === {json.dumps(idB)} && messages.length === 2"))
        c.js("[...document.querySelectorAll('#toasts button')].find(b => b.textContent === 'Undo').click(); true"); c.pump(0.3)
        check("Undo of the current chat: back in the list", c.js("chats.length") == 2)
        c.js("openChats(false); true")

        # ---- 3. attach a file, reload, ask again
        att = base / "notes-attach.txt"
        att.write_text("Project Zephyr notes\n\nThe vault combination for Project Zephyr is 7318-4406.\n"
                       "The project lead is Ingrid Haldorsen.\n")
        c.js("$('new-btn').click(); true"); c.pump(0.3)
        doc = c.call("DOM.getDocument", depth=-1, pierce=True)
        node = c.call("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="#file")["nodeId"]
        c.call("DOM.setFileInputFiles", files=[str(att)], nodeId=node)
        ok = c.wait("attachments.length === 1 && attachments[0].kind === 'file'", 10)
        check("file attached (chip shown)", ok and c.js("document.querySelectorAll('#attachments .chip').length") == 1,
              c.js("attachments.map(a => a.name)"))
        c.shot("04-attached")
        r1 = send(c, "What is the vault combination in the attached file? Reply with just the combination.")
        check("answer uses the file", r1 and "7318-4406" in r1["text"], (r1 or {}).get("text", "")[:80])
        idF = c.js("chatId")
        saved = c.js(f"JSON.parse(localStorage.getItem('strata.chat.' + {json.dumps(idF)}))[0].files")
        check("the file's text is saved with the chat", saved and saved[0].get("text", "").startswith("Project Zephyr"), saved and saved[0]["name"])
        c.navigate(url)
        check("after reload: file chip on the message", c.js(f"chatId === {json.dumps(idF)}") and
              c.js("document.querySelectorAll('#chat .st-msg')[0].textContent.includes('notes-attach.txt')"))
        n_before = len(engine_tail(a.engine_log, 10000))
        r2 = send(c, "Who is the project lead named in that file? Just the name.")
        check("after reload the model still sees the file", r2 and "Haldorsen" in r2["text"], (r2 or {}).get("text", "")[:80])
        tail = engine_tail(a.engine_log, 10000)[n_before:]
        check("server: the turn after the reload reused the earlier prompt (same history sent)",
              tail and " 0 reused" not in tail[-1], tail[-1] if tail else "")
        c.shot("05-after-reload")

        # ---- 4. Stop
        c.js("$('new-btn').click(); true"); c.pump(0.3)
        c.js("(() => { const i = $('input'); i.value = 'Write a very detailed 3000-word history of the printing press.'; "
             "$('send-btn').click(); return true; })()")
        started = c.wait("busy !== null && (busy.msg.reasoning.length + busy.msg.text.length) > 200", 120)
        check("long answer streaming", started)
        check("Stop button visible while writing", c.js("!$('stop-btn').hidden"))
        t0 = time.time()
        c.js("$('stop-btn').click(); true")
        stopped = c.wait("busy === null", 15)
        dt = time.time() - t0
        m = c.js("(() => { const m = messages[messages.length - 1]; return {stopped: !!m.stopped, meta: m.meta || '', err: m.error || null}; })()")
        check("Stop ends the answer at once", stopped and dt < 5 and m["stopped"] and not m["err"], f"{dt:.2f} s, {m}")
        check("Stop button hidden again, Send enabled", c.js("$('stop-btn').hidden && !$('send-btn').disabled"))
        c.shot("06-stopped")
        c.pump(1.5)
        srv = requests.get(a.base + "/status", timeout=5).json()
        check("server idle after Stop", not srv.get("busy"), srv)
        r3 = send(c, "Say OK.")
        check("next request after Stop answers normally", r3 and r3["text"].strip() != "" and not r3["error"], (r3 or {}).get("text", "")[:40])
        # ---- 6. two tabs of the page (same browser storage): a chat started in one must survive a save in the other
        t2 = requests.put(f"http://127.0.0.1:{port}/json/new?{url}", timeout=10).json()
        c2 = CDP(t2["webSocketDebuggerUrl"])
        for dom in ("Runtime", "Page", "Log"):
            c2.call(f"{dom}.enable")
        c2.wait("document.readyState === 'complete' && typeof health === 'object' && health.max_context > 0", 60)
        c2.js("$('new-btn').click(); true")
        rt = send(c2, "Tab two chat. Say hello in five words.")
        id2 = c2.js("chatId")
        check("tab 2: new chat answered and saved", rt and id2 and c2.js(f"JSON.parse(localStorage.getItem('strata.chats')).some(x => x.id === {json.dumps(id2)})"))
        r4 = send(c, "Tab one again: say OK.")           # tab 1 saves its chat afterwards
        idx = c.js("JSON.parse(localStorage.getItem('strata.chats')).map(x => x.id)")
        check("two tabs: tab 2's chat still in the saved list after tab 1 saves", id2 in idx, f"{len(idx)} chats saved")
        c.js("$('chats-btn').click(); true"); c.pump(0.3)
        check("two tabs: tab 1's Chats list shows tab 2's chat", c.js(f"chats.some(x => x.id === {json.dumps(id2)})"))
        c.js("openChats(false); true")
        c.console += [("tab2 " + k, v) for k, v in c2.console]
        try:
            c2.call("Page.close")
        except Exception:  # noqa: BLE001
            pass
        c.pump(0.5)
        check("no page exceptions / console errors", not c.console, c.console[:5])
        c.shot("07-end")
    finally:
        try:
            c.call("Browser.close")
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.wait(10)
        except Exception:  # noqa: BLE001
            os.killpg(proc.pid, 15)
    summary = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "base": a.base, "passed": sum(r["ok"] for r in results),
               "failed": sum(not r["ok"] for r in results), "checks": results, "console": c.console}
    json.dump(summary, open(WS / f"results/browser-test-{a.tag}.json", "w"), indent=1)
    print(f"BROWSER TEST {a.tag}: {summary['passed']} passed, {summary['failed']} failed")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
