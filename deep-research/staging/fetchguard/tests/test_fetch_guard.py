"""Offline tests of the staged fetch guard (patch 0006) with the two saved 11-03 pages, through a loopback HTTP server.

usage (LDR venv python, isolated, no bytecode):
  nice -n 19 taskset -c 31 timeout 120 prlimit --as=4294967296 \
    /home/USER/ai/deep-research/.venv/bin/python -I -B tests/test_fetch_guard.py PAGES_DIR WORK_DIR
PAGES_DIR holds teamgroup.html (263.7 MB) and gskill-qvl.html (66.6 KB). WORK_DIR gets two import overlays: "ovs" =
the staged html.py / playwright_html.py / extraction/pipeline.py / extraction/fetch_guard.py, "ovp" = the pristine
LDR 1.10.7 files (src/whl). Both use stubs for LDR's base/security/constants (a plain requests.Session instead of
SafeSession, which refuses 127.0.0.1) and the venv's real extractors (trafilatura, newspaper4k, bs4, ...).
Nothing touches the network beyond 127.0.0.1 or the installed package.
"""
import gzip
import http.server
import importlib
import json
import os
import shutil
import socketserver
import sys
import threading
import time
import unittest

WS = "/home/USER/ai/deep-research"
VENV_LDR = WS + "/.venv/lib/python3.12/site-packages/local_deep_research"
PRISTINE = WS + "/src/whl/local_deep_research"
STAGED = WS + "/staging/fetchguard/site/local_deep_research"
DL = "research_library/downloaders"
PAGES, WORK = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (None, None)
GUARD_LOG = None

STUB_CONSTANTS = 'BROWSER_USER_AGENT = "Mozilla/5.0 (test)"\nUSER_AGENT = "LDR-test"\n'
STUB_SECURITY = 'def sanitize_error_for_client(s, max_length=None):\n    return s\n'
STUB_SAFE_REQUESTS = '_MAX_REDIRECTS = 10\n_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})\n' \
                     'def _resolve_redirect_method(method, status_code):\n    return method\n'
STUB_BASE = '''
from enum import Enum
from typing import NamedTuple, Optional
import requests


class ContentType(Enum):
    PDF = "pdf"
    TEXT = "text"


class DownloadResult(NamedTuple):
    content: Optional[bytes] = None
    skip_reason: Optional[str] = None
    is_success: bool = False
    status_code: Optional[int] = None


class _Tracker:
    def __init__(self):
        self.outcomes = []

    def apply_rate_limit(self, engine_type):
        return 0.0

    def record_outcome(self, **kw):
        self.outcomes.append(kw)


class BaseDownloader:
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False      # no proxies from the environment: loopback only
        self.rate_tracker = _Tracker()

    def close(self):
        self.session.close()
'''


def build_overlay(name, src_root, extra_files):
    """WORK/<name>/... : a package with LDR's downloaders + extraction dir, stubs for the rest."""
    root = os.path.join(WORK, name)
    shutil.rmtree(root, ignore_errors=True)
    files = {
        "__init__.py": "", "constants.py": STUB_CONSTANTS, "security/__init__.py": STUB_SECURITY,
        "security/ssrf_validator.py": "", "security/safe_requests.py": STUB_SAFE_REQUESTS,
        "research_library/__init__.py": "", f"{DL}/__init__.py": "", f"{DL}/base.py": STUB_BASE,
    }
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        with open(os.path.join(root, rel), "w") as f:
            f.write(text)
    shutil.copytree(os.path.join(VENV_LDR, DL, "extraction"), os.path.join(root, DL, "extraction"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    for rel in (f"{DL}/html.py", f"{DL}/playwright_html.py", f"{DL}/extraction/pipeline.py"):
        shutil.copy(os.path.join(src_root, rel), os.path.join(root, rel))
    for rel in extra_files:
        shutil.copy(os.path.join(STAGED, rel), os.path.join(root, rel))
    return root


class Pages(http.server.BaseHTTPRequestHandler):
    """/tg.gz: the Team Group page gzip-encoded, no Content-Length (as the real server sent it);
    /tg.cl: plain with Content-Length; /tg4: its first 4 MiB (under the cap); /gskill: the G.Skill QVL page."""
    bodies = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        body, enc, with_len = self.bodies[self.path]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if enc:
            self.send_header("Content-Encoding", enc)
        if with_len:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            for i in range(0, len(body), 1 << 20):
                self.wfile.write(body[i:i + (1 << 20)])
        except (BrokenPipeError, ConnectionResetError):
            pass


def vm_kb(field):
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith(field + ":"):
                return int(line.split()[1])


def guard_events():
    try:
        with open(GUARD_LOG) as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []


class FetchGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PAGES, "teamgroup.html"), "rb") as f:
            tg = f.read()
        with open(os.path.join(PAGES, "gskill-qvl.html"), "rb") as f:
            gs = f.read()
        tg4 = tg[:4 << 20]
        tg4 = tg4[:tg4.rfind(b"</tr>") + 5] if b"</tr>" in tg4 else tg4[:tg4.rfind(b">") + 1]
        Pages.bodies = {"/tg.gz": (gzip.compress(tg, compresslevel=1), "gzip", False), "/tg.cl": (tg, None, True),
                        "/tg4": (tg4, None, True), "/gskill": (gs, None, True)}
        cls.tg_len = len(tg)
        del tg
        socketserver.TCPServer.allow_reuse_address = True
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Pages)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.S = importlib.import_module("ovs.research_library.downloaders.html")
        cls.P = importlib.import_module("ovp.research_library.downloaders.html")
        cls.SA = importlib.import_module("ovs.research_library.downloaders.playwright_html")
        cls.G = importlib.import_module("ovs.research_library.downloaders.extraction.fetch_guard")
        cls.SP = importlib.import_module("ovs.research_library.downloaders.extraction.pipeline")

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_1_teamgroup_gzip_stopped_at_cap(self):
        """The 11-03 page (5.5 MB gzip -> 264 MB): download stops at 16 MiB decompressed, skipped, logged, counted."""
        n0 = len(guard_events())
        with open("/proc/self/clear_refs", "w") as f:
            f.write("5")
        rss0 = vm_kb("VmRSS")
        d = self.SA.AutoHTMLDownloader()
        t0 = time.monotonic()
        r = d.download_with_result(self.base + "/tg.gz")
        dt = time.monotonic() - t0
        peak_mb = (vm_kb("VmHWM") - rss0) / 1024
        print(f"\n  teamgroup gzip: {dt:.2f} s, peak +{peak_mb:.0f} MB, reason: {r.skip_reason}")
        self.assertFalse(r.is_success)
        self.assertTrue(r.skip_reason.startswith("[FETCH-GUARD] skipped: page larger than the 16.0 MB cap"))
        self.assertLess(dt, 10)
        self.assertLess(peak_mb, 400)
        ev = guard_events()[n0:]
        self.assertEqual([e["kind"] for e in ev], ["skipped"])
        self.assertGreater(ev[0]["bytes"], 16 << 20)
        self.assertEqual(self.G.counts().get("skipped"), 1)
        self.assertEqual(d.rate_tracker.outcomes[-1]["success"], True)   # a skip is not a rate-limit failure

    def test_2_teamgroup_content_length_refused_unread(self):
        n0 = len(guard_events())
        d = self.S.HTMLDownloader()
        t0 = time.monotonic()
        r = d.download_with_result(self.base + "/tg.cl")
        dt = time.monotonic() - t0
        print(f"\n  teamgroup Content-Length: {dt:.2f} s, reason: {r.skip_reason}")
        self.assertFalse(r.is_success)
        self.assertIn("Content-Length 251.4 MB > 16.0 MB cap (not downloaded)", r.skip_reason)
        self.assertLess(dt, 3)
        self.assertEqual([e["kind"] for e in guard_events()[n0:]], ["skipped"])

    def test_3_normal_pages_unchanged(self):
        """G.Skill QVL page and a 4 MiB prefix (under both caps): byte-identical text to pristine LDR, a page record."""
        for path in ("/gskill", "/tg4"):
            n0 = len(guard_events())
            new = self.SA.AutoHTMLDownloader().download_with_result(self.base + path)
            old = importlib.import_module("ovp.research_library.downloaders.playwright_html").AutoHTMLDownloader(
            ).download_with_result(self.base + path)
            self.assertTrue(new.is_success and old.is_success, (new.skip_reason, old.skip_reason))
            self.assertEqual(new.content, old.content)
            ev = guard_events()[n0:]
            self.assertEqual([e["kind"] for e in ev], ["page"])
            print(f"\n  {path}: {len(new.content)} bytes of text, identical; page record {ev[0]}")

    def test_4_tag_cap_before_parsing(self):
        """A page under the byte cap but over the tag cap is refused before any parser runs."""
        old = self.G.MAX_TAGS
        self.G.MAX_TAGS = 10_000          # the 4 MiB prefix has ~15.5k '<'
        try:
            n0 = len(guard_events())
            t0 = time.monotonic()
            r = self.S.HTMLDownloader().download_with_result(self.base + "/tg4")
            dt = time.monotonic() - t0
            self.assertFalse(r.is_success)
            self.assertIn("tags > 10000 cap (not parsed)", r.skip_reason)
            self.assertLess(dt, 2)
            self.assertEqual([e["kind"] for e in guard_events()[n0:]], ["skipped"])
        finally:
            self.G.MAX_TAGS = old

    def test_5_direct_pipeline_callers(self):
        """extract_content / extract_content_with_metadata (Wayback, full-content search) return None over the cap."""
        big = "<html><body>" + "<p>x</p>" * 30_000 + "</body></html>"
        old = self.G.MAX_TAGS
        self.G.MAX_TAGS = 50_000
        try:
            n0 = len(guard_events())
            self.assertIsNone(self.SP.extract_content(big, url="http://example.test/big"))
            self.assertIsNone(self.SP.extract_content_with_metadata(big))
            self.assertEqual([e["kind"] for e in guard_events()[n0:]], ["skipped", "skipped"])
        finally:
            self.G.MAX_TAGS = old

    def test_6_watchdog_logs_and_counts_slow_page(self):
        old = self.G.SLOW_S
        self.G.SLOW_S = 0.05
        try:
            n0 = len(guard_events())
            r = self.S.HTMLDownloader().download_with_result(self.base + "/tg4")
            self.assertTrue(r.is_success)
            kinds = [e["kind"] for e in guard_events()[n0:]]
            self.assertEqual(kinds, ["slow", "slow_done"])
        finally:
            self.G.SLOW_S = old

    def test_7_switch_off(self):
        """LDR_FETCH_GUARD=0 (ENABLED False): no cap; the G.Skill page still comes through unchanged."""
        old = self.G.ENABLED
        self.G.ENABLED = False
        try:
            r = self.S.HTMLDownloader().download_with_result(self.base + "/gskill")
            self.assertTrue(r.is_success)
        finally:
            self.G.ENABLED = old


if __name__ == "__main__":
    if not PAGES:
        raise SystemExit(__doc__)
    os.makedirs(WORK, exist_ok=True)
    GUARD_LOG = os.path.join(WORK, "fetch-guard-test.jsonl")
    if os.path.exists(GUARD_LOG):
        os.remove(GUARD_LOG)
    os.environ["LDR_FETCH_GUARD_LOG"] = GUARD_LOG
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="WARNING", format="  {level}: {message}")
    build_overlay("ovs", STAGED, [f"{DL}/extraction/fetch_guard.py"])
    build_overlay("ovp", PRISTINE, [])
    sys.path.insert(0, WORK)
    unittest.main(argv=[sys.argv[0], "-v"])
