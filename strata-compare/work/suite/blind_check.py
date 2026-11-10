#!/usr/bin/env python3
"""blind_check.py - 2026-10-13: open a blind page in the suite's headless Chrome (render.py's binary) two ways, as a
lone file (copied into an empty folder: what the document portal exposes) and over http from the local results
server, and check that every embedded screenshot decodes, click-to-enlarge works, "Open live" opens (the served file
over http, the embedded copy as a file) and a saved pick survives a reload.  Sandboxed like render.py (bwrap), but
with the host's loopback: DNS resolves nothing except 127.0.0.1 (--host-resolver-rules) and every request that is not
127.0.0.1:<port>, file: or data: is failed, so nothing leaves the machine.  A temporary profile: the user's browser
and picks are untouched.  Screenshots of the page go to --shots."""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "suite"))
from msuite import render  # noqa: E402
from msuite.common import RESULTS, TMP  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--page", required=True)
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--shots", required=True)
a = ap.parse_args()
SHOTS = Path(a.shots)
SHOTS.mkdir(parents=True, exist_ok=True)
ALLOW = (f"http://127.0.0.1:{a.port}/", "file://", "data:", "about:")


class Chrome(render.Chrome):
    def __init__(self, workdir: Path, portal: Path):
        self.work = Path(workdir)
        (self.work / "home").mkdir(parents=True, exist_ok=True)
        r_cmd, w_cmd = os.pipe()
        r_ev, w_ev = os.pipe()
        args = ["/usr/bin/bwrap", "--die-with-parent", "--unshare-all", "--share-net", "--new-session",
                "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
                "--ro-bind", "/bin", "/bin", "--ro-bind", "/etc", "/etc", "--ro-bind", render.CHROME_APP, render.CHROME_APP,
                "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/dev/shm", "--tmpfs", "/tmp",
                "--ro-bind", str(portal), "/portal", "--bind", str(self.work), "/work", "--chdir", "/work", "--clearenv",
                "--setenv", "HOME", "/work/home", "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "LANG", "C.UTF-8",
                render.CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader", "--no-first-run", "--no-default-browser-check",
                "--disable-background-networking", "--disable-component-update", "--disable-sync",
                "--disable-extensions", "--disable-default-apps", "--mute-audio",
                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                "--remote-debugging-pipe", "--user-data-dir=/work/home/profile", "--window-size=1400,1000",
                "about:blank"]

        def child():
            x, y = os.dup(r_cmd), os.dup(w_ev)
            x2, y2 = os.dup2(x, 200), os.dup2(y, 201)
            os.dup2(x2, 3)
            os.dup2(y2, 4)
            os.set_inheritable(3, True)
            os.set_inheritable(4, True)

        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, preexec_fn=child, close_fds=False,
                                     start_new_session=True)
        os.close(r_cmd)
        os.close(w_ev)
        self.w, self.r = w_cmd, r_ev
        self.buf = b""
        self.n = 0
        self.events = []


def check(chrome, url, tag):
    tid = chrome.call("Target.createTarget", {"url": "about:blank"})["targetId"]
    sess = chrome.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    log = {"blocked": [], "allowed": [], "exceptions": [], "loaded": 0}

    def handle(m):
        if m.get("sessionId") != sess:
            return
        meth, p = m.get("method", ""), m.get("params", {})
        if meth == "Fetch.requestPaused":
            u = p["request"]["url"]
            if u.startswith(ALLOW):
                log["allowed"].append(u[:120])
                chrome.send("Fetch.continueRequest", {"requestId": p["requestId"]}, sess)
            else:
                log["blocked"].append(u[:160])
                chrome.send("Fetch.failRequest", {"requestId": p["requestId"], "errorReason": "BlockedByClient"}, sess)
        elif meth == "Page.loadEventFired":
            log["loaded"] += 1
        elif meth == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            log["exceptions"].append((d.get("exception", {}).get("description") or d.get("text") or "")[:300])

    def js(expr, timeout=60):
        r = chrome.call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True},
                        sess, timeout=timeout, handler=handle)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:500])
        return r["result"].get("value")

    def wait_load(n):
        end = time.monotonic() + 60
        while log["loaded"] < n and time.monotonic() < end:
            chrome.pump(0.5, handle)

    def snap(name, clip_sel=None):
        p = {"format": "png"}
        if clip_sel:
            r = js(f"(()=>{{const r=document.querySelector({json.dumps(clip_sel)}).getBoundingClientRect();"
                   f"return [r.x+scrollX,r.y+scrollY,r.width,r.height]}})()")
            p.update({"clip": {"x": r[0], "y": r[1], "width": r[2], "height": min(r[3], 2400), "scale": 1},
                      "captureBeyondViewport": True})
        b = chrome.call("Page.captureScreenshot", p, sess, timeout=60, handler=handle)["data"]
        (SHOTS / f"{tag}-{name}.png").write_bytes(base64.b64decode(b))

    for meth, params in (("Fetch.enable", {"patterns": [{"urlPattern": "*"}]}), ("Runtime.enable", {}),
                         ("Page.enable", {}),
                         ("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1000, "deviceScaleFactor": 1,
                                                                 "mobile": False})):
        chrome.call(meth, params, sess, handler=handle)
    t0 = time.monotonic()
    chrome.call("Page.navigate", {"url": url}, sess, handler=handle)
    wait_load(1)
    res = {"url": url, "load_s": round(time.monotonic() - t0, 1)}
    # 1. every screenshot (main images and thumbnails), forced to load now, decodes
    res["images"] = js("""(async()=>{ const im=[...document.querySelectorAll('.shot-main, .thumbs img')];
      im.forEach(i=>i.loading='eager'); await Promise.all(im.map(i=>i.decode().catch(()=>null)));
      const bad=im.filter(i=>!(i.complete && i.naturalWidth>0));
      return {total: im.length, main: document.querySelectorAll('.shot-main').length, decoded: im.length-bad.length,
              failed: bad.length, not_data: im.filter(i=>!i.src.startsWith('data:image/')).length,
              sizes: [...new Set(im.map(i=>i.naturalWidth+'x'+i.naturalHeight))],
              main_width_px: Math.round(document.querySelector('.shot-main').getBoundingClientRect().width)}; })()""")
    snap("card1", ".card")
    # 2. click-to-enlarge: the first card with several screenshots; arrow key; Esc
    res["zoom"] = js("""(async()=>{ const c=[...document.querySelectorAll('.card')].find(c=>c.querySelectorAll('.thumbs img').length>1)
      || document.querySelector('.card'); c.scrollIntoView(); c.querySelector('.shot-main').click();
      const z=document.getElementById('zoom'), zi=z.querySelector('img'); await zi.decode().catch(()=>null);
      const first={shown: getComputedStyle(z).display, w: zi.naturalWidth, width_px: Math.round(zi.getBoundingClientRect().width),
                   cap: z.querySelector('.cap').textContent};
      document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight'})); await zi.decode().catch(()=>null);
      const next=z.querySelector('.cap').textContent;
      return {first, after_arrow: next}; })()""")
    snap("zoom")
    res["zoom"]["after_esc"] = js("""(()=>{ document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));
      return getComputedStyle(document.getElementById('zoom')).display; })()""")
    # 3. "Open live" on a Three.js answer and an SVG answer
    lives = {}
    for item in ("v03_voxel_pagoda", "v01_pelican_bicycle"):
        lives[item] = js(f"""(async()=>{{ const k=DATA.cards.findIndex(c=>c.id.startsWith({json.dumps(item)}+'.r'));
          const c=document.querySelectorAll('.card')[k]; c.scrollIntoView();
          const b=[...c.querySelectorAll('button')].find(b=>b.textContent==='Open live'); b.click();
          const f=c.querySelector('iframe'); await new Promise(r=>{{f.addEventListener('load',r); setTimeout(r,8000);}});
          await new Promise(r=>setTimeout(r,2500));
          return {{card: c.querySelector('h2').textContent, via: f.getAttribute('srcdoc')!==null?'embedded copy (srcdoc)':
                   (f.src.startsWith('data:')?'embedded copy (data: svg)':'served file '+f.getAttribute('src')),
                  sandbox: f.getAttribute('sandbox'), height: f.getBoundingClientRect().height}}; }})()""", timeout=30)
        js(f"(()=>{{const k=DATA.cards.findIndex(c=>c.id.startsWith({json.dumps(item)}+'.r'));"
           f"document.querySelectorAll('.card')[k].querySelector('iframe').scrollIntoView({{block:'center'}});}})()")
        chrome.pump(1.0, handle)
        snap(f"live-{item}")
    res["live"] = lives
    # 4. a saved pick survives a reload (localStorage at this address)
    js("""(()=>{ const c=document.querySelector('.card'); [...c.querySelectorAll('button')].find(b=>b.textContent==='Left is better').click(); })()""")
    before = js("document.getElementById('tally').textContent")
    chrome.call("Page.reload", {}, sess, handler=handle)
    wait_load(2)
    res["pick"] = {"before_reload": before, "after_reload": js("document.getElementById('tally').textContent"),
                   "button_on": js("[...document.querySelector('.card').querySelectorAll('button.on')].map(b=>b.textContent)")}
    res["requests_blocked"] = log["blocked"]
    res["requests_to_server"] = sorted({u for u in log["allowed"] if u.startswith("http")})
    res["page_exceptions"] = log["exceptions"]
    chrome.call("Target.closeTarget", {"targetId": tid})
    return res


page = RESULTS / a.page
portal = Path(a.shots) / "portal"
shutil.rmtree(portal, ignore_errors=True)
portal.mkdir(parents=True)
shutil.copy2(page, portal / page.name)                    # the HTML alone, nothing next to it
work = TMP / "render" / f"blindcheck-{os.getpid()}"
chrome = Chrome(work, portal)
out = {}
try:
    out["file"] = check(chrome, f"file:///portal/{page.name}", "file")
    out["http"] = check(chrome, f"http://127.0.0.1:{a.port}/{page.name}", "http")
finally:
    chrome.close()
    shutil.rmtree(work, ignore_errors=True)
print(json.dumps(out, indent=1))
