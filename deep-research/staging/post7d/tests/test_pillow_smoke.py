#!/usr/bin/env python3
"""Offline tests of staging/post7d/tools/pillow_smoke.py's run logic (fetch_one replaced by canned results; no
network, no LDR). Temp files in staging/post7d/scratch."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

S = Path("/home/USER/ai/deep-research/staging/post7d")
spec = importlib.util.spec_from_file_location("pillow_smoke", S / "tools" / "pillow_smoke.py")
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)
T = Path(tempfile.mkdtemp(prefix="smoke-test-", dir=S / "scratch"))
FAILS = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what)
    if not c:
        FAILS.append(what)


def good(url, chars, pdf=False):
    return {"url": url, "status": "success", "chars": chars, "source_type": "x", "seconds": 1.0, "pillow": "t",
            "pdf_extract_calls": [{"bytes": 100000, "chars": chars}] if pdf else []}


def run(results, label, base=None):
    ps.fetch_one = lambda u: results[u]
    out = T / f"{label}.json"
    rc = ps.cmd_run(label, out, base, T / "log.txt")
    return rc, json.loads(out.read_text())


P, H = ps.CANDIDATES["pdf"], ps.CANDIDATES["html"]
refuse = {"status": "error", "error": "HTTP 403", "chars": 0}
# 1 first pdf refuses, second passes; first html passes
res = {P[0]: {"url": P[0], **refuse}, P[1]: good(P[1], 90000, pdf=True), P[2]: good(P[2], 9000, pdf=True),
       H[0]: good(H[0], 30000), H[1]: good(H[1], 20000), H[2]: good(H[2], 50000)}
rc, pre = run(res, "pre")
check(rc == 0 and pre["kinds"]["pdf"]["passed"] == P[1] and pre["kinds"]["html"]["passed"] == H[0],
      "a refusing page is skipped (no work-around), the next candidate counts")
# 2 after the update: only the baseline's URLs; same length passes
rc, post = run(res, "post", T / "pre.json")
check(rc == 0 and [t["result"]["url"] for t in post["kinds"]["pdf"]["tried"]] == [P[1]], "post tries only the baseline's URL")
# 3 after the update the pdf text collapses -> fail (no fallback to another URL)
res2 = dict(res); res2[P[1]] = good(P[1], 20000, pdf=True)
rc, post2 = run(res2, "post2", T / "pre.json")
check(rc == 1 and post2["kinds"]["pdf"]["passed"] is None, "pdf text < half the baseline's -> SMOKE FAILED")
# 4 a pdf whose text did not come from the PDF extraction (e.g. an abstract page) fails
res3 = dict(res); res3[P[1]] = good(P[1], 90000, pdf=False); res3[P[2]] = good(P[2], 9000, pdf=False)
res3[P[0]] = {"url": P[0], **refuse}
rc, _ = run(res3, "pre3")
check(rc == 1, "no extract_text_from_pdf call -> the pdf kind fails")
# 5 a crash / timeout after the update fails
res4 = dict(res); res4[H[0]] = {"url": H[0], "status": "timeout", "error": "killed"}
rc, _ = run(res4, "post4", T / "pre.json")
check(rc == 1, "a timeout after the update -> SMOKE FAILED")
# 6 too short html fails
res5 = dict(res); res5[H[0]] = good(H[0], 300); res5[H[1]] = good(H[1], 200); res5[H[2]] = good(H[2], 100)
rc, _ = run(res5, "pre5")
check(rc == 1, "html under MIN_CHARS on every candidate -> fails")
import shutil  # noqa: E402
shutil.rmtree(T, ignore_errors=True)
print("ALL OK" if not FAILS else f"{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
