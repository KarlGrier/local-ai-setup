"""Render model-written SVG / HTML in headless Chromium, inside the sandbox with no network.

Chrome (the installed flatpak Google Chrome binary, run directly) runs under bwrap with --unshare-all, so it has no
network at all; it is driven over --remote-debugging-pipe (file descriptors 3/4), not a socket.  Every request the
page makes is intercepted (CDP Fetch): the page's own files are served from its throwaway folder, CDN URLs of the
common browser libraries are served from local copies (suite/vendor: Three.js 0.128.0 / 0.160.0 / 0.186.1, and since
2026-10-14 the packages in vendor/npm/INDEX.json - p5, d3, GSAP, Chart.js, PixiJS, Phaser, React, Vue, Tailwind ...,
from jsDelivr / unpkg / cdnjs / esm.sh / Skypack / jspm URLs and a few library hosts), everything else is refused and
logged (Google Fonts included: pages fall back to local fonts).  Console errors and
uncaught exceptions are recorded; screenshots are taken at fixed times (and, for games, after a few key presses).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from .common import TMP, VENDOR

CHROME = "/var/lib/flatpak/app/com.google.Chrome/current/active/files/extra/chrome"
CHROME_APP = "/var/lib/flatpak/app/com.google.Chrome"
ORIGIN = "http://suite.local/"
W, H = 1024, 768
MIME = {".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".js": "text/javascript", ".mjs": "text/javascript",
        ".cjs": "text/javascript", ".json": "application/json", ".png": "image/png", ".css": "text/css"}


THREE_VERSIONS = ("0.128.0", "0.160.0", "0.186.1")
EXT_MIME = {".js": "text/javascript", ".mjs": "text/javascript", ".cjs": "text/javascript", ".css": "text/css",
            ".json": "application/json", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
            ".otf": "font/otf", ".eot": "application/vnd.ms-fontobject", ".svg": "image/svg+xml", ".png": "image/png",
            ".wasm": "application/wasm"}
JSD = "https://cdn.jsdelivr.net/npm/"


def _three_root(ver: str | None) -> Path:
    """The vendored Three.js for a requested version: the same one if vendored, else by range (< r150: 0.128.0,
    r150-r169: 0.160.0, r170 and later or no version: 0.186.1)."""
    if ver and (VENDOR / "three" / ver).is_dir():
        return VENDOR / "three" / ver
    n = _vnum(ver) if ver else 999
    return VENDOR / "three" / ("0.128.0" if n < 150 else "0.160.0" if n < 170 else "0.186.1")


def _three(url: str):
    m = re.search(r"three@([0-9.]+)/(build/[^?#]+|examples/[^?#]+)", url)
    if m:
        p = _three_root(m.group(1)) / m.group(2)
        return p if p.is_file() else None
    m = re.search(r"cdnjs\.cloudflare\.com/ajax/libs/three\.js/r?(\d+)(?:\.\d+)*/(.+?)(?:[?#]|$)", url)
    if m:
        root = _three_root("0." + m.group(1))
        for cand in (root / "build" / m.group(2), root / m.group(2)):
            if cand.is_file():
                return cand
        return None
    m = re.search(r"^https?://threejs\.org/((?:build|examples)/[^?#]+)", url)
    if m:
        p = _three_root(None) / m.group(1)
        return p if p.is_file() else None
    m = re.search(r"cdn\.jsdelivr\.net/gh/mrdoob/three\.js@r?(\d+)[^/]*/((?:build|examples)/[^?#]+)", url)
    if m:
        p = _three_root("0." + m.group(1)) / m.group(2)
        return p if p.is_file() else None
    m = re.search(r"(?:esm\.sh|cdn\.skypack\.dev|unpkg\.com|cdn\.jsdelivr\.net/npm|ga\.jspm\.io/npm:)/?three(?:@([^/?#]+))?/?(\S*?)(?:[?#]|$)", url)
    if m:
        ver = m.group(1) if m.group(1) and re.match(r"^\d+\.\d+\.\d+$", m.group(1)) else None
        rel = m.group(2)
        root = _three_root(ver)
        if not rel or rel in ("", "/", "+esm"):
            return root / "build" / "three.module.js"
        p = root / rel
        return p if p.is_file() else None
    return None


_NPM = None


def _npm_index() -> dict:
    global _NPM
    if _NPM is None:
        try:
            _NPM = json.loads((VENDOR / "npm" / "INDEX.json").read_text())
        except (OSError, ValueError):
            _NPM = {"packages": {}, "cdnjs": {}}
    return _NPM


def _vkey(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _pick_version(name: str, want: str | None):
    """(version, note): the vendored version for a requested one - exact, else the newest of the same major (0.x: the
    same minor), else the nearest major."""
    vers = sorted(_npm_index()["packages"][name]["versions"], key=_vkey)
    if not want or want in ("latest", "next"):
        return vers[-1], None
    want = want.strip()
    if want.lstrip("v=") in vers:
        return want.lstrip("v="), None
    m = re.match(r"^[\^~>=<v ]*(\d+)(?:\.(\d+|x|\*))?", want)
    if not m:
        return vers[-1], f"{name}@{want} -> {vers[-1]}"
    maj = int(m.group(1))
    mnr = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else None
    same = [v for v in vers if _vkey(v)[0] == maj and (maj > 0 or mnr is None or _vkey(v)[1] == mnr)]
    if same:
        got = same[-1]
    else:
        got = min(vers, key=lambda v: (abs(_vkey(v)[0] - maj), -_vkey(v)[0]))
    return got, (None if got == want else f"{name}@{want} -> {got}")


def _npm_file(name: str, ver: str, rel: str, by_basename: bool = False):
    root = VENDOR / "npm" / name / ver
    rel = rel.lstrip("/")

    def inside(c):
        p = (root / c).resolve()
        return p if p.is_file() and root.resolve() in p.parents else None

    if inside(rel):
        return inside(rel)
    if by_basename:              # cdnjs lays files out its own way: the same file name, a build folder's copy first
        base = rel.rsplit("/", 1)[-1]
        for b in (base, base[:-7] + ".js" if base.endswith(".min.js") else None):
            if not b:
                continue
            hits = sorted((p for p in root.rglob(b) if p.is_file()),
                          key=lambda p: (not set(p.relative_to(root).parts[:-1]) & {"dist", "build", "lib", "umd"},
                                         len(p.parts), str(p)))
            if hits:
                return hits[0]
        return None
    cands = []
    if rel.endswith(".min.js"):
        cands.append(rel[:-7] + ".js")            # jsDelivr minifies on request
    if not re.search(r"\.[a-z0-9]+$", rel):
        cands += [rel + ".js", rel + ".mjs", rel + "/index.js"]
    for c in cands:
        if inside(c):
            return inside(c)
    return None


def _npm_spec(spec: str):
    """'@scope/name@ver/path' or 'name@ver/path' -> (name, ver or None, path)."""
    parts = spec.split("/")
    if spec.startswith("@"):
        if len(parts) < 2:
            return None, None, ""
        head, rest = parts[0] + "/" + parts[1], parts[2:]
    else:
        head, rest = parts[0], parts[1:]
    name, _, ver = head[1:].partition("@") if head.startswith("@") else head.partition("@")
    name = "@" + name if head.startswith("@") else name
    return name, (ver or None), "/".join(rest)


def vendor_lookup(url: str):
    """A CDN URL -> {"file": Path, "note": str|None} or {"redirect": url, "note": ...} (a bare package URL is sent to
    the vendored entry file's own URL, so relative imports inside it resolve), or None (not vendored: blocked)."""
    p = _three(url)
    if p is not None:
        return {"file": p, "note": None}
    u = re.split(r"[?#]", url, 1)
    base, query = u[0], (url[len(u[0]):] if len(u) > 1 else "")
    idx = _npm_index()
    pk = idx.get("packages", {})
    m = re.match(r"^https?://code\.jquery\.com/jquery-(\d+\.\d+\.\d+)((?:\.slim)?(?:\.min)?\.js)$", base)
    if m and "jquery" in pk:
        ver, note = _pick_version("jquery", m.group(1))
        f = _npm_file("jquery", ver, "dist/jquery" + m.group(2))
        return {"file": f, "note": note} if f else None
    if re.match(r"^https?://cdn\.tailwindcss\.com/?", base) and idx.get("tailwind_play_cdn"):
        t = idx["tailwind_play_cdn"]
        return {"file": VENDOR / "npm" / t["file"], "note": "Tailwind Play CDN " + t["version"] + (" (plugins ignored)" if "plugins" in query else "")}
    m = re.match(r"^https?://cdn\.babylonjs\.com/(?:v[0-9.]+/)?babylon\.js$", base)
    if m and "babylonjs" in pk:
        ver, _ = _pick_version("babylonjs", None)
        return {"file": VENDOR / "npm" / "babylonjs" / ver / "babylon.js", "note": None}
    m = re.match(r"^https?://d3js\.org/d3\.v(\d+)(?:\.min)?\.js$", base)
    if m and "d3" in pk:
        ver, note = _pick_version("d3", m.group(1))
        return {"file": VENDOR / "npm" / "d3" / ver / "dist" / "d3.min.js", "note": note}
    m = re.match(r"^https?://cdn\.plot\.ly/plotly-(latest|\d+\.\d+\.\d+)(?:\.min)?\.js$", base)
    if m and "plotly.js-dist-min" in pk:
        ver, note = _pick_version("plotly.js-dist-min", None if m.group(1) == "latest" else m.group(1))
        return {"file": VENDOR / "npm" / "plotly.js-dist-min" / ver / "plotly.min.js", "note": note}
    m = re.match(r"^https?://cdnjs\.cloudflare\.com/ajax/libs/([^/]+)/([^/]+)/(.+)$", base)
    if m:
        lib, want, rel = m.groups()
        names = [n for n in idx.get("cdnjs", {}).get(lib, []) if n in pk]
        if not names:
            return None
        # several packages under one cdnjs name (font-awesome 4 / 6): the one with the same major, else the newest
        wmaj = _vkey(want)[0] if _vkey(want) else None
        name = next((n for n in names if any(_vkey(v)[0] == wmaj for v in pk[n]["versions"])), names[0])
        ver, note = _pick_version(name, want)
        f = _npm_file(name, ver, rel, by_basename=True)
        return {"file": f, "note": note} if f else None
    kind, spec = None, None
    for pat, k in ((r"^https?://cdn\.jsdelivr\.net/npm/(.+)$", "script"), (r"^https?://(?:unpkg\.com|npmcdn\.com)/(.+)$", "script"),
                   (r"^https?://esm\.sh/(?:v\d+/|stable/)?(.+)$", "esm"), (r"^https?://cdn\.skypack\.dev/(.+)$", "esm"),
                   (r"^https?://ga\.jspm\.io/npm:(.+)$", "esm")):
        mm = re.match(pat, base)
        if mm:
            kind, spec = k, mm.group(1)
            break
    if spec is None:
        return None
    name, want, rel = _npm_spec(spec)
    if name not in pk:
        return None
    if rel in ("+esm", "") and (rel == "+esm" or "module" in query):
        kind, rel = "esm", ""
    ver, note = _pick_version(name, want)
    if not rel:
        e = pk[name]["versions"][ver].get(kind)   # an import gets no script build: blocked, as before
        if not e:
            return None
        return {"redirect": f"{JSD}{name}@{ver}/{e}", "note": note}
    if rel.endswith("/+esm"):
        rel = rel[:-5]
    f = _npm_file(name, ver, rel)
    return {"file": f, "note": note} if f else None


def vendor_path(url: str):
    """Map a CDN URL to a vendored file, or None (kept for callers that only want a file)."""
    r = vendor_lookup(url)
    return r.get("file") if r else None


def _vnum(v: str) -> int:
    try:
        return int(v.split(".")[1]) if v.startswith("0.") else int(v)
    except (ValueError, IndexError):
        return 160


class Chrome:
    """One headless Chrome in the sandbox, CDP over pipes."""

    def __init__(self, workdir: Path):
        self.work = Path(workdir)
        (self.work / "home").mkdir(parents=True, exist_ok=True)
        r_cmd, w_cmd = os.pipe()          # we write commands -> chrome reads fd 3
        r_ev, w_ev = os.pipe()            # chrome writes fd 4 -> we read
        args = ["/usr/bin/bwrap", "--die-with-parent", "--unshare-all", "--new-session", "--hostname", "sandbox",
                "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
                "--ro-bind", "/bin", "/bin", "--ro-bind", "/etc", "/etc", "--ro-bind", CHROME_APP, CHROME_APP,
                "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/dev/shm", "--tmpfs", "/tmp",
                "--bind", str(self.work), "/work", "--chdir", "/work", "--clearenv",
                "--setenv", "HOME", "/work/home", "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "LANG", "C.UTF-8",
                CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader", "--no-first-run", "--no-default-browser-check",
                "--disable-background-networking", "--disable-component-update", "--disable-sync",
                "--disable-extensions", "--disable-default-apps", "--mute-audio", "--hide-scrollbars",
                "--remote-debugging-pipe", "--user-data-dir=/work/home/profile", f"--window-size={W},{H}",
                "about:blank"]

        def child():                      # move both ends out of the way first, then onto 3 and 4
            a, b = os.dup(r_cmd), os.dup(w_ev)
            a2, b2 = os.dup2(a, 200), os.dup2(b, 201)
            os.dup2(a2, 3)
            os.dup2(b2, 4)
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

    # -------------------------------------------------------------------------------------------- protocol
    def send(self, method, params=None, session=None):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        os.write(self.w, json.dumps(msg).encode() + b"\0")
        return self.n

    def _read_msg(self, timeout):
        end = time.monotonic() + timeout
        while b"\0" not in self.buf:
            left = end - time.monotonic()
            if left <= 0:
                return None
            import select
            rr, _, _ = select.select([self.r], [], [], left)
            if not rr:
                return None
            chunk = os.read(self.r, 1 << 20)
            if not chunk:
                raise RuntimeError("chrome closed the pipe")
            self.buf += chunk
        raw, self.buf = self.buf.split(b"\0", 1)
        return json.loads(raw)

    def call(self, method, params=None, session=None, timeout=30, handler=None):
        mid = self.send(method, params, session)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            m = self._read_msg(end - time.monotonic())
            if m is None:
                break
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            (handler or self.events.append)(m)
        raise TimeoutError(method)

    def pump(self, secs, handler):
        end = time.monotonic() + secs
        while True:
            left = end - time.monotonic()
            if left <= 0:
                return
            m = self._read_msg(left)
            if m is None:
                return
            handler(m)

    def close(self):
        try:
            self.send("Browser.close")
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
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


KEYS = {"ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40, " ": 32, "Enter": 13, "c": 67}


def render_page(chrome: Chrome, site: Path, entry: str, shots: list[float], out_dir: Path, game: bool = False) -> dict:
    """Load http://suite.local/<entry> (files from `site`), take screenshots, return the log."""
    out_dir.mkdir(parents=True, exist_ok=True)
    log = {"console": [], "exceptions": [], "served": [], "vendor": [], "blocked": [], "shots": [], "notes": []}
    tid = chrome.call("Target.createTarget", {"url": "about:blank"})["targetId"]
    sess = chrome.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    def handle(m):
        if m.get("sessionId") != sess:
            return
        meth, p = m.get("method", ""), m.get("params", {})
        if meth == "Fetch.requestPaused":
            url = p["request"]["url"]
            rid = p["requestId"]
            body, ctype = None, None
            if url == ORIGIN + "favicon.ico":            # the browser's own request, not the page's
                chrome.send("Fetch.fulfillRequest", {"requestId": rid, "responseCode": 204, "responseHeaders": []}, sess)
                return
            if url.startswith(ORIGIN):
                rel = url[len(ORIGIN):].split("?")[0].split("#")[0] or "index.html"
                f = (site / rel).resolve()
                if f.is_file() and site.resolve() in f.parents and not (site / rel).is_symlink():
                    body, ctype = f.read_bytes(), MIME.get(f.suffix, "application/octet-stream")
                    log["served"].append(rel)
            elif url.startswith("data:") or url.startswith("blob:"):
                chrome.send("Fetch.continueRequest", {"requestId": rid}, sess)
                return
            else:
                vr = vendor_lookup(url)
                if vr is not None and vr.get("redirect"):
                    log["vendor"].append(url)
                    if vr.get("note"):
                        log["notes"].append("vendored " + vr["note"])
                    chrome.send("Fetch.fulfillRequest", {
                        "requestId": rid, "responseCode": 302,
                        "responseHeaders": [{"name": "Location", "value": vr["redirect"]},
                                            {"name": "Access-Control-Allow-Origin", "value": "*"}]}, sess)
                    return
                if vr is not None and vr.get("file") is not None:
                    vp = vr["file"]
                    body, ctype = vp.read_bytes(), EXT_MIME.get(vp.suffix, "application/octet-stream")
                    log["vendor"].append(url)
                    if vr.get("note"):
                        log["notes"].append("vendored " + vr["note"])
            if body is None:
                log["blocked"].append(url[:300])
                chrome.send("Fetch.failRequest", {"requestId": rid, "errorReason": "BlockedByClient"}, sess)
            else:
                chrome.send("Fetch.fulfillRequest", {
                    "requestId": rid, "responseCode": 200,
                    "responseHeaders": [{"name": "Content-Type", "value": ctype},
                                        {"name": "Access-Control-Allow-Origin", "value": "*"},
                                        {"name": "Cache-Control", "value": "no-store"}],
                    "body": base64.b64encode(body).decode()}, sess)
        elif meth == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            log["exceptions"].append((d.get("exception", {}).get("description") or d.get("text") or "")[:500])
        elif meth == "Runtime.consoleAPICalled" and p.get("type") in ("error", "assert"):
            log["console"].append(" ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))[:500])
        elif meth == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
            e = p["entry"]
            log["console"].append(f"[{e.get('source')}] {e.get('text')} {e.get('url', '')}"[:500])

    try:
        for meth, params in (("Fetch.enable", {"patterns": [{"urlPattern": "*"}]}), ("Runtime.enable", {}),
                             ("Log.enable", {}), ("Page.enable", {}),
                             ("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1,
                                                                     "mobile": False})):
            chrome.call(meth, params, sess, handler=handle)
        t0 = time.monotonic()
        chrome.call("Page.navigate", {"url": ORIGIN + entry}, sess, handler=handle)
        prev = None
        for i, at in enumerate(shots):
            wait = at - (time.monotonic() - t0)
            if wait > 0:
                chrome.pump(wait, handle)
            png = base64.b64decode(chrome.call("Page.captureScreenshot", {"format": "png"}, sess, handler=handle,
                                               timeout=60)["data"])
            name = f"shot{i + 1}.png"
            (out_dir / name).write_bytes(png)
            h = hashlib.sha256(png).hexdigest()[:12]
            log["shots"].append({"file": name, "t": at, "sha": h, "changed": prev is not None and h != prev})
            prev = h
        if game:
            chrome.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": W // 2, "y": H // 2, "button": "left",
                                                     "clickCount": 1}, sess, handler=handle)
            chrome.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": W // 2, "y": H // 2,
                                                     "button": "left", "clickCount": 1}, sess, handler=handle)
            seq = ["ArrowLeft", "ArrowLeft", "ArrowUp", "ArrowRight", " ", "ArrowDown", "ArrowDown", "ArrowUp", " "]
            for k in seq:
                code = {" ": "Space"}.get(k, k if k.startswith("Arrow") else "Key" + k.upper())
                for typ in ("keyDown", "keyUp"):
                    chrome.call("Input.dispatchKeyEvent", {"type": typ, "key": k, "code": code,
                                                           "windowsVirtualKeyCode": KEYS[k],
                                                           "nativeVirtualKeyCode": KEYS[k]}, sess, handler=handle)
                chrome.pump(0.25, handle)
            for j, extra in enumerate((1.0, 3.0)):
                chrome.pump(extra, handle)
                png = base64.b64decode(chrome.call("Page.captureScreenshot", {"format": "png"}, sess, handler=handle,
                                                   timeout=60)["data"])
                name = f"shot{len(log['shots']) + 1}.png"
                (out_dir / name).write_bytes(png)
                h = hashlib.sha256(png).hexdigest()[:12]
                log["shots"].append({"file": name, "t": "after keys +%.0fs" % (1.0 if j == 0 else 4.0), "sha": h,
                                     "changed": h != prev})
                prev = h
            log["notes"].append("keys sent: " + " ".join(k if k != " " else "Space" for k in seq))
    except (TimeoutError, RuntimeError) as e:
        log["notes"].append(f"render problem: {e}")
    finally:
        try:
            chrome.call("Target.closeTarget", {"targetId": tid}, handler=handle, timeout=10)
        except Exception:
            pass
    log["vendor"] = sorted(set(log["vendor"]))
    log["served"] = sorted(set(log["served"]))
    return log


def svg_wrapper() -> str:
    return ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;height:100%;background:#fff}"
            "img{display:block;width:100vw;height:100vh;object-fit:contain}</style></head>"
            "<body><img src='image.svg' alt='svg'></body></html>")


def new_browser() -> tuple[Chrome, Path]:
    d = TMP / "render" / f"chrome-{os.getpid()}-{int(time.time() * 1000)}"
    d.mkdir(parents=True)
    return Chrome(d), d


def cleanup_browser(chrome: Chrome, d: Path):
    chrome.close()
    if TMP in Path(d).parents:
        shutil.rmtree(d, ignore_errors=True)
