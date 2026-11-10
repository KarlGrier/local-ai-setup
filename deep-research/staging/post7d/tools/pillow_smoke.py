#!/usr/bin/env python3
"""pillow_smoke.py - Karl 11-05: after the pillow 12.3.0 -> 13.0.0 update (staging/post7d/install-ldr-fixes.sh), "a short
smoke run (fetch and extract a PDF and an HTML page) before the first real post-7d run". Runs in the LDR venv with
LDR's own fetch path - local_deep_research.content_fetcher.ContentFetcher, the class the deep fetch tool
(_fetch_raw_content) uses, with its downloaders (arXiv / direct PDF -> BaseDownloader.extract_text_from_pdf (pypdf);
HTML -> AutoHTMLDownloader with patch 0006's fetch guard), timeout 30 s per request, max_length 120,000 chars as the
deep fetch, JavaScript rendering off (the default). It never starts the LDR web app, searches or uses a paid source;
LDR_DATA_DIR and the fetch guard's log point into staging/post7d/scratch/smoke (Karl's data/ and logs/ untouched).

  pillow_smoke.py dry                       offline: imports, PIL / pypdf versions, URL classes, downloaders build
  pillow_smoke.py run --label L --out JSON [--baseline JSON] [--log TXT]
        per kind (pdf, html) the candidates in order, each fetched in its own process with a hard time limit (150 s,
        4 GiB address space); the first one that passes counts. A page that refuses or fails is logged and the next
        tried (no work-around of a block). Pass: status success, text >= MIN_CHARS, and for pdf at least one
        extract_text_from_pdf call that returned text. With --baseline (the pre-update run): only the URLs that passed
        there are tried, in the same order, and the text must be >= half the baseline's length. Exit 0 = both kinds
        passed.
  pillow_smoke.py one URL                   (internal) one fetch; prints one JSON line
"""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
SMOKE = WS / "staging" / "post7d" / "scratch" / "smoke"
PY = str(WS / ".venv" / "bin" / "python")
CANDIDATES = {
    "pdf": ["https://arxiv.org/pdf/1706.03762",                          # arXiv -> ArxivDownloader (PDF text)
            "https://www.rfc-editor.org/rfc/pdfrfc/rfc9110.txt.pdf",     # direct PDF -> DirectPDFDownloader
            "https://www.irs.gov/pub/irs-pdf/fw4.pdf"],
    "html": ["https://en.wikipedia.org/wiki/Mixture_of_experts",
             "https://docs.python.org/3/library/pathlib.html",
             "https://www.rfc-editor.org/rfc/rfc9110.html"],
}
MIN_CHARS = {"pdf": 5000, "html": 1500}
TIME_LIMIT_S = 150
MAX_LENGTH = 120_000          # the deep fetch's CONTENT_MAX_LENGTH (profile LDR_DEEP_FETCH_MAX_CHARS at 131K)


def child_env() -> dict:
    SMOKE.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in os.environ.items() if k in ("HOME", "PATH", "LANG", "LC_ALL", "TZ")}
    keep.update({"LDR_DATA_DIR": str(SMOKE / "data"), "LDR_FETCH_GUARD_LOG": str(SMOKE / "fetch-guard.jsonl"),
                 "PYTHONDONTWRITEBYTECODE": "1"})
    return keep


def versions() -> dict:
    import PIL
    import pypdf
    return {"pillow": PIL.__version__, "pypdf": pypdf.__version__}


def cmd_one(url: str) -> int:
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    from local_deep_research.content_fetcher import ContentFetcher
    from local_deep_research.content_fetcher.url_classifier import URLClassifier
    from local_deep_research.research_library.downloaders.base import BaseDownloader
    calls = []
    orig = BaseDownloader.extract_text_from_pdf

    def counted(pdf_content: bytes):
        t = orig(pdf_content)
        calls.append({"bytes": len(pdf_content or b""), "chars": len(t or "")})
        return t
    BaseDownloader.extract_text_from_pdf = staticmethod(counted)
    t0 = time.time()
    with ContentFetcher(timeout=30, enable_js_rendering=False) as f:
        r = f.fetch(url, max_length=MAX_LENGTH)
    out = {"url": url, "class": URLClassifier.classify(url).name, "status": r.get("status"),
           "source_type": r.get("source_type"), "chars": len(r.get("content") or ""), "title": (r.get("title") or "")[:120],
           "error": (r.get("error") or "")[:300], "pdf_extract_calls": calls, "seconds": round(time.time() - t0, 1),
           "head": " ".join((r.get("content") or "")[:240].split())} | versions()
    try:
        from local_deep_research.research_library.downloaders.extraction import fetch_guard
        out["fetch_guard"] = fetch_guard.counts()
    except Exception as e:  # noqa: BLE001
        out["fetch_guard"] = f"? {e}"[:120]
    print(json.dumps(out))
    return 0


def limit():
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
    os.nice(10)


def fetch_one(url: str) -> dict:
    try:
        p = subprocess.run([PY, "-I", "-B", __file__, "one", url], env=child_env(), capture_output=True, text=True,
                           timeout=TIME_LIMIT_S, preexec_fn=limit, cwd=str(SMOKE))
    except subprocess.TimeoutExpired:
        return {"url": url, "status": "timeout", "error": f"no result within {TIME_LIMIT_S} s (killed)"}
    line = [l for l in p.stdout.splitlines() if l.startswith("{")]
    if p.returncode != 0 or not line:
        return {"url": url, "status": "crash", "error": f"rc {p.returncode}: {p.stderr.strip()[-400:]}"}
    return json.loads(line[-1])


def passes(kind: str, r: dict, base: dict | None) -> tuple[bool, str]:
    if r.get("status") != "success":
        return False, f"{r.get('status')}: {r.get('error')}"
    if r.get("chars", 0) < MIN_CHARS[kind]:
        return False, f"only {r.get('chars')} chars (< {MIN_CHARS[kind]})"
    if kind == "pdf" and not any(c["chars"] > 0 for c in r.get("pdf_extract_calls") or []):
        return False, "no PDF text extraction ran (extract_text_from_pdf not called or empty)"
    if base and r["chars"] < 0.5 * base["chars"]:
        return False, f"{r['chars']} chars vs {base['chars']} before the update (< half)"
    return True, "ok"


def cmd_run(label: str, out: Path, baseline: Path | None, log: Path | None) -> int:
    base = json.loads(baseline.read_text()) if baseline else None
    res = {"label": label, "t": time.strftime("%Y-%m-%d %H:%M:%S %z"), "kinds": {}}
    lines = [f"== {res['t']} smoke {label}"]
    ok_all = True
    for kind, urls in CANDIDATES.items():
        if base:
            want = base["kinds"].get(kind, {}).get("passed")
            urls = [u for u in urls if u == want]
        tried, passed = [], None
        for u in urls:
            r = fetch_one(u)
            ok, why = passes(kind, r, (base or {}).get("kinds", {}).get(kind, {}).get("result") if base else None)
            tried.append({"result": r, "ok": ok, "why": why})
            pdfc = r.get("pdf_extract_calls")
            lines.append(f"  {kind:<4} {'PASS' if ok else 'fail'} {u} - {r.get('status')} {r.get('source_type') or ''}, "
                         f"{r.get('chars', 0)} chars, {r.get('seconds', '?')} s, pillow {r.get('pillow', '?')}"
                         f"{', pdf extractions ' + str(pdfc) if pdfc else ''} - {why}")
            if ok:
                passed = r
                break
        res["kinds"][kind] = {"passed": passed["url"] if passed else None, "result": passed, "tried": tried}
        if not passed:
            ok_all = False
            lines.append(f"  {kind:<4} NO CANDIDATE PASSED")
    res["ok"] = ok_all
    lines.append(f"  -> {'SMOKE OK' if ok_all else 'SMOKE FAILED'}")
    out.write_text(json.dumps(res, indent=1))
    if log:
        with open(log, "a") as f:
            f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok_all else 1


def cmd_dry() -> int:
    """Offline: what the smoke will use exists and builds (no network)."""
    env = child_env()
    code = ("import json; from local_deep_research.content_fetcher import ContentFetcher; "
            "from local_deep_research.content_fetcher.url_classifier import URLClassifier, URLType; "
            "from local_deep_research.research_library.downloaders.base import BaseDownloader; "
            "from local_deep_research.research_library.downloaders.extraction import fetch_guard; "
            "import PIL, pypdf; f = ContentFetcher(timeout=30, enable_js_rendering=False); "
            f"urls = {json.dumps(CANDIDATES)}; "
            "cls = {k: [URLClassifier.classify(u).name for u in v] for k, v in urls.items()}; "
            "d = {t.name: type(f._get_downloader(t)).__name__ for t in (URLType.ARXIV, URLType.PDF, URLType.HTML)}; f.close(); "
            "print(json.dumps({'pillow': PIL.__version__, 'pypdf': pypdf.__version__, 'classes': cls, 'downloaders': d, "
            "'extract_text_from_pdf': callable(BaseDownloader.extract_text_from_pdf), 'fetch_guard': fetch_guard.ENABLED}))")
    p = subprocess.run([PY, "-I", "-B", "-c", code], env=env, capture_output=True, text=True, timeout=120, cwd=str(SMOKE))
    line = [l for l in p.stdout.splitlines() if l.startswith("{")]
    if p.returncode != 0 or not line:
        print(f"dry: FAILED rc {p.returncode}: {p.stderr.strip()[-600:]}")
        return 1
    d = json.loads(line[-1])
    print("dry: " + json.dumps(d))
    bad = []
    if not all(c in ("ARXIV", "PDF") for c in d["classes"]["pdf"]):
        bad.append(f"a pdf candidate is not classed ARXIV / PDF: {d['classes']['pdf']}")
    if any(c != "HTML" for c in d["classes"]["html"]):
        bad.append(f"an html candidate is not classed HTML: {d['classes']['html']}")
    if not d["extract_text_from_pdf"] or not d["fetch_guard"]:
        bad.append("extract_text_from_pdf missing or the fetch guard off")
    if "NoneType" in d["downloaders"].values():
        bad.append(f"a downloader did not build: {d['downloaders']}")
    for b in bad:
        print("dry: PROBLEM " + b)
    return 1 if bad else 0


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    if a[0] == "dry":
        return cmd_dry()
    if a[0] == "one":
        return cmd_one(a[1])
    if a[0] == "run":
        opts = dict(zip(a[1::2], a[2::2]))
        return cmd_run(opts["--label"], Path(opts["--out"]), Path(opts["--baseline"]) if "--baseline" in opts else None,
                       Path(opts["--log"]) if "--log" in opts else None)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
